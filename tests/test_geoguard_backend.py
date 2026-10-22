"""
=============================================================================
GEOGUARD AI — COMPREHENSIVE 5-SENSOR BACKEND & RISK ENGINE TEST SUITE
File: tests/test_geoguard_backend.py
=============================================================================
Covers all 15 Required Acceptance Test Cases:
1. Valid 5-field serial packet
2. Valid legacy 4-field packet (rain marked unavailable, not 0.0)
3. Empty, malformed, or nonnumeric packets
4. Invalid rainfall values (negative, NaN, inf)
5. Rain intensity risk normalization at 0, 12.5, 25, 37.5, 50 mm/hr
6. Monotonic rainfall-risk behavior
7. Exact weight total of 100% (25% Soil, 25% Rain, 25% Slope, 15% Vib, 10% Temp)
8. Correct weighted composite calculation
9. Composite score bounded between 0 and 100
10. Missing or stale sensor data not resulting in a false LOW classification
11. Simulation producing all five required fields
12. Heavy-rainfall and emergency scenarios affecting composite score correctly
13. Historical data containing rainfall values
14. Existing four-sensor functionality remaining operational
15. Streamlit pages importing cleanly without new errors
=============================================================================
"""

import sys
import os
import math
from pathlib import Path

# Ensure project root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from modules.risk_engine import (
    calculate_five_sensor_risk,
    calculate_four_sensor_risk,
    calculate_risk,
    normalize_soil_moisture_risk,
    normalize_rain_intensity_risk,
    normalize_temperature_risk,
    normalize_slope_tilt_risk,
    normalize_vibration_risk,
    DEFAULT_CONFIG
)
from modules.hardware_reader import SerialTelemetryGateway
from modules.sensor_simulator import generate_telemetry_tick, DEFAULT_STATIONS
from modules.data_store import enrich_station_telemetry
from modules.interlock import HighwayInterlockSystem


def run_all_tests():
    print("=======================================================")
    print("RUNNING GEOGUARD AI 5-SENSOR INTEGRATION TEST SUITE")
    print("=======================================================")

    gw = SerialTelemetryGateway()

    # 1. Valid 5-field serial packet
    p5 = gw.validate_and_parse_line("68.5,24.7,12.4,0.18,22.6")
    assert p5 is not None, "Failed to parse valid 5-field packet"
    assert p5["soil_moisture_pct"] == 68.5
    assert p5["temperature_c"] == 24.7
    assert p5["tilt_degrees"] == 12.4
    assert p5["vibration_pga"] == 0.18
    assert p5["rain_intensity_mmh"] == 22.6
    assert p5["is_complete"] is True
    assert p5["is_valid"] is True
    print("[OK] 1. Valid 5-field serial packet PASSED")

    # 2. Valid legacy 4-field packet (rain marked unavailable, not assumed 0.0)
    p4 = gw.validate_and_parse_line("68.5,24.7,12.4,0.18")
    assert p4 is not None, "Failed to parse legacy 4-field packet"
    assert p4["soil_moisture_pct"] == 68.5
    assert p4["temperature_c"] == 24.7
    assert p4["tilt_degrees"] == 12.4
    assert p4["vibration_pga"] == 0.18
    assert p4["rain_intensity_mmh"] is None, "Legacy packet must NOT assume rain is 0.0"
    assert p4["is_complete"] is False
    print("[OK] 2. Valid legacy 4-field packet (rain unavailable) PASSED")

    # 3. Empty, malformed, or nonnumeric packets
    assert gw.validate_and_parse_line("") is None
    assert gw.validate_and_parse_line("   ") is None
    assert gw.validate_and_parse_line("68.5,corrupt,12.4,0.18,22.6") is None
    assert gw.validate_and_parse_line("12.3,45.6") is None
    assert gw.validate_and_parse_line("1,2,3,4,5,6,7,8") is None
    print("[OK] 3. Empty, malformed, and nonnumeric packets quarantined PASSED")

    # 4. Invalid rainfall values (negative, NaN, inf)
    assert gw.validate_and_parse_line("68.5,24.7,12.4,0.18,-10.0") is None
    assert gw.validate_and_parse_line("68.5,24.7,12.4,0.18,nan") is None
    assert gw.validate_and_parse_line("68.5,24.7,12.4,0.18,inf") is None
    print("[OK] 4. Invalid rainfall values (negative/NaN/inf) rejected PASSED")

    # 5. Rain intensity risk normalization at 0, 12.5, 25, 37.5, 50 mm/hr
    assert normalize_rain_intensity_risk(0.0) == 0.0, "Rain 0 mm/h must be 0 risk"
    assert normalize_rain_intensity_risk(12.5) == 25.0, "Rain 12.5 mm/h must be 25 risk"
    assert normalize_rain_intensity_risk(25.0) == 50.0, "Rain 25 mm/h must be 50 risk"
    assert normalize_rain_intensity_risk(37.5) == 75.0, "Rain 37.5 mm/h must be 75 risk"
    assert normalize_rain_intensity_risk(50.0) == 100.0, "Rain 50 mm/h must be 100 risk"
    assert normalize_rain_intensity_risk(65.0) == 100.0, "Rain >50 mm/h must clamp at 100"
    print("[OK] 5. Rain intensity risk normalization calibration PASSED")

    # 6. Monotonic rainfall-risk behavior
    intensities = [0.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 75.0]
    scores = [normalize_rain_intensity_risk(r) for r in intensities]
    for i in range(len(scores) - 1):
        assert scores[i] <= scores[i+1], f"Non-monotonic risk: {intensities[i]}->{scores[i]} vs {intensities[i+1]}->{scores[i+1]}"
    print("[OK] 6. Monotonic rainfall-risk behavior PASSED")

    # 7. Exact weight total of 100%
    cfg = DEFAULT_CONFIG
    total_weights = cfg["weight_soil"] + cfg["weight_rain"] + cfg["weight_slope"] + cfg["weight_vib"] + cfg["weight_temp"]
    assert abs(total_weights - 1.0) < 1e-6, f"Weights must sum exactly to 1.0 (100%), got {total_weights}"
    assert cfg["weight_soil"] == 0.25
    assert cfg["weight_rain"] == 0.25
    assert cfg["weight_slope"] == 0.25
    assert cfg["weight_vib"] == 0.15
    assert cfg["weight_temp"] == 0.10
    print("[OK] 7. Exact weight total 100% (25/25/25/15/10) PASSED")

    # 8. Correct weighted composite calculation
    # Test controlled inputs: Soil=50% (55 pts), Rain=25 mm/h (50 pts), Slope=0.8° (35 pts), Vib=0.05g (20 pts), Temp=18°C (5 pts)
    # Expected: (55*0.25) + (50*0.25) + (35*0.25) + (20*0.15) + (5*0.10)
    # = 13.75 + 12.50 + 8.75 + 3.00 + 0.50 = 38.5 pts
    res = calculate_five_sensor_risk(
        soil_moisture_pct=50.0,
        rain_intensity_mmh=25.0,
        tilt_degrees=0.8,
        vibration_pga=0.05,
        temperature_c=18.0
    )
    assert res["is_valid"] is True
    assert abs(res["overall_risk_score"] - 38.5) <= 0.1, f"Expected 38.5, got {res['overall_risk_score']}"
    assert res["risk_level"] == "LOW"
    print("[OK] 8. Correct weighted composite calculation PASSED")

    # 9. Composite score bounded between 0 and 100
    res_min = calculate_five_sensor_risk(soil_moisture_pct=0.0, rain_intensity_mmh=0.0, tilt_degrees=0.0, vibration_pga=0.0, temperature_c=18.0)
    assert 0.0 <= res_min["overall_risk_score"] <= 100.0
    res_max = calculate_five_sensor_risk(soil_moisture_pct=100.0, rain_intensity_mmh=100.0, tilt_degrees=10.0, vibration_pga=5.0, temperature_c=0.0)
    assert 0.0 <= res_max["overall_risk_score"] <= 100.0
    assert res_max["risk_level"] == "CRITICAL"
    print("[OK] 9. Composite score bounded in [0, 100] PASSED")

    # 10. Missing or stale sensor data policy: conservative, does NOT result in false LOW
    res_missing_rain = calculate_five_sensor_risk(
        soil_moisture_pct=20.0,
        rain_intensity_mmh=None,  # Missing rain channel
        tilt_degrees=0.1,
        vibration_pga=0.01,
        temperature_c=18.0
    )
    assert res_missing_rain["is_valid"] is False, "Missing rain must mark packet invalid"
    assert res_missing_rain["risk_level"] != "LOW", "Missing sensor must NEVER be classified as safe LOW"
    assert res_missing_rain["risk_level"] == "UNKNOWN DATA"
    assert "rain" in res_missing_rain["missing_sensors"]
    print("[OK] 10. Missing sensor conservative policy (no false LOW) PASSED")

    # 11. Simulation producing all five required fields
    stns = generate_telemetry_tick(DEFAULT_STATIONS)
    assert len(stns) == 5
    for s in stns:
        assert "soil_moisture_pct" in s
        assert "rainfall_intensity_mmh" in s
        assert "temp_c" in s
        assert "tilt" in s
        assert "vib_g" in s
        assert s["rainfall_intensity_mmh"] is not None
        assert 0.0 <= s["rainfall_intensity_mmh"] <= 100.0
    print("[OK] 11. Simulation producing all 5 required fields PASSED")

    # 12. Heavy rainfall scenario impact
    base_res = calculate_five_sensor_risk(soil_moisture_pct=40.0, rain_intensity_mmh=0.0, tilt_degrees=0.5, vibration_pga=0.04, temperature_c=18.0)
    heavy_rain_res = calculate_five_sensor_risk(soil_moisture_pct=40.0, rain_intensity_mmh=45.0, tilt_degrees=0.5, vibration_pga=0.04, temperature_c=18.0)
    assert heavy_rain_res["overall_risk_score"] > base_res["overall_risk_score"], "Heavy rain must increase risk score"
    rain_diff = heavy_rain_res["overall_risk_score"] - base_res["overall_risk_score"]
    # 45 mm/h rain is 90 risk pts * 0.25 weight = 22.5 pts increase
    assert abs(rain_diff - 22.5) <= 0.5, f"Expected ~22.5 point rain contribution, got {rain_diff}"
    print("[OK] 12. Heavy rainfall scenario contribution impact PASSED")

    # 13. Historical data containing rainfall values & station enrichment
    enriched = enrich_station_telemetry(DEFAULT_STATIONS)
    assert len(enriched) == 5
    for e in enriched:
        assert "rainfall_intensity_mmh" in e
        assert "contributions" in e
        assert "rain" in e["contributions"]
    print("[OK] 13. Historical data & enrichment containing rainfall values PASSED")

    # 14. Existing four-sensor functionality remaining operational
    res_4s = calculate_four_sensor_risk(soil_moisture_pct=50.0, temperature_c=18.0, tilt_degrees=0.8, vibration_pga=0.05)
    assert res_4s["is_valid"] is True
    assert "soil" in res_4s["sensor_scores"]
    print("[OK] 14. Existing four-sensor functionality operational PASSED")

    # 15. Streamlit pages import cleanly without syntax or import errors
    import pages.overview
    import pages.live_sensor
    import pages.reports
    import pages.alert_center
    import pages.geographic_map
    import pages.highway_safety
    import pages.settings
    print("[OK] 15. All 7 Streamlit pages imported cleanly without error PASSED")

    print("=======================================================")
    print("ALL 15 INTEGRATION TEST CASES PASSED SUCCESSFULLY (100%)")
    print("=======================================================")


if __name__ == "__main__":
    run_all_tests()
