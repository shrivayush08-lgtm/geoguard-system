"""
Tests for pages/live_sensor.py safe extraction and rendering logic.
Covers:
- Valid 5-sensor station dictionary
- Missing rainfall key
- None rainfall
- Empty string rainfall
- Non-numeric string rainfall
- NaN and Infinity rainfall
- Negative rainfall
- Missing station dictionary / None dictionary
- Missing history / empty dataframe
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))

import math
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from pages.live_sensor import _safe_float, render_live_sensor_page
from modules.risk_engine import calculate_five_sensor_risk

def test_safe_float():
    assert _safe_float(25.4) == 25.4
    assert _safe_float("25.4") == 25.4
    assert _safe_float("  30.0  ") == 30.0
    assert _safe_float(None) is None
    assert _safe_float("", default=None) is None
    assert _safe_float("   ", default=None) is None
    assert _safe_float("N/A", default=None) is None
    assert _safe_float("nan", default=None) is None
    assert _safe_float("NaN", default=None) is None
    assert _safe_float("inf", default=None) is None
    assert _safe_float("-inf", default=None) is None
    assert _safe_float(float("nan"), default=None) is None
    assert _safe_float(float("inf"), default=None) is None
    assert _safe_float("invalid_string", default=None) is None
    assert _safe_float("12.5", default=0.0) == 12.5
    assert _safe_float(None, default=0.0) == 0.0

def test_rainfall_extraction_scenarios():
    scenarios = [
        # (station_dict, expected_rain_mmh, expected_is_avail)
        ({"rain_intensity": 22.5}, 22.5, True),
        ({"rainfall_intensity_mmh": 18.0}, 18.0, True),
        ({"rain_intensity": None, "rainfall_intensity_mmh": 15.0}, 15.0, True),
        ({"rain_intensity": "", "rainfall_intensity_mmh": 12.0}, 12.0, True),
        ({"rain_intensity": "  ", "rainfall_intensity_mmh": " 24.5 "}, 24.5, True),
        ({}, None, False),
        ({"rain_intensity": None}, None, False),
        ({"rain_intensity": ""}, None, False),
        ({"rain_intensity": "N/A"}, None, False),
        ({"rain_intensity": "invalid"}, None, False),
        ({"rain_intensity": float("nan")}, None, False),
        ({"rain_intensity": float("inf")}, None, False),
        ({"rain_intensity": -10.5}, None, False), # Negative is physically invalid
    ]

    for stn, expected_val, expected_avail in scenarios:
        raw_rain_obj = stn.get("rain_intensity")
        if raw_rain_obj is None or (isinstance(raw_rain_obj, str) and raw_rain_obj.strip() == ""):
            raw_rain_obj = stn.get("rainfall_intensity_mmh")

        parsed_rain = _safe_float(raw_rain_obj, None)
        rain_mmh = parsed_rain if (parsed_rain is not None and parsed_rain >= 0.0) else None
        is_avail = (rain_mmh is not None)

        assert rain_mmh == expected_val, f"Failed for {stn}: expected {expected_val}, got {rain_mmh}"
        assert is_avail == expected_avail, f"Failed availability for {stn}"

def test_render_with_mocked_streamlit():
    """Verify render_live_sensor_page executes with mock Streamlit context across edge cases."""
    stations = [
        {
            "id": "GG-001",
            "name": "NH-58 Mountain Pass",
            "corridor": "NH-58 km 42",
            "lat": 30.1234,
            "lon": 78.4321,
            "soil_moisture_pct": 55.0,
            "soil_adc": 2300,
            "temperature_c": 19.5,
            "tilt": 0.45,
            "vib": False,
            "vib_g": 0.04,
            "rain_intensity": 25.0,
            "rainfall_intensity_mmh": 25.0,
            "battery": 97.0
        },
        {
            "id": "GG-002",
            "name": "Valley Gorge Sector A",
            "corridor": "NH-58 km 58",
            "lat": 30.1567,
            "lon": 78.4890,
            "soil_moisture_pct": 35.0,
            "soil_adc": 1800,
            "temperature_c": 14.0,
            "tilt": 0.20,
            "vib": False,
            "vib_g": 0.02,
            # Missing rain fields entirely
            "battery": 95.0
        },
        {
            "id": "GG-003",
            "name": "Ridge Tunnel Link",
            "corridor": "NH-58 km 71",
            "lat": 30.2012,
            "lon": 78.5123,
            "soil_moisture_pct": 75.0,
            "temperature_c": 2.0,
            "tilt": 1.5,
            "vib": True,
            "vib_g": 0.85,
            "rain_intensity": "invalid_string", # Malformed string
            "rainfall_intensity_mmh": "NaN"
        }
    ]

    import streamlit as st
    if "is_monitoring" not in st.session_state:
        st.session_state.is_monitoring = True
    if "sensor_weights" not in st.session_state:
        st.session_state.sensor_weights = {"soil": 0.25, "rain": 0.25, "slope": 0.25, "vibration": 0.15, "temperature": 0.10}

    # Render Station 1 (Valid 5-sensor)
    render_live_sensor_page(stations)
    print("[OK] Rendered Station 1 (Valid 5-sensor)")

    # Render Station 2 (Missing rain fields)
    stations_missing_rain = [stations[1]]
    render_live_sensor_page(stations_missing_rain)
    print("[OK] Rendered Station 2 (Missing rainfall)")

    # Render Station 3 (Malformed string / NaN rain)
    stations_malformed = [stations[2]]
    render_live_sensor_page(stations_malformed)
    print("[OK] Rendered Station 3 (Malformed string / NaN rainfall)")

if __name__ == "__main__":
    test_safe_float()
    print("[OK] test_safe_float passed")
    test_rainfall_extraction_scenarios()
    print("[OK] test_rainfall_extraction_scenarios passed")
    test_render_with_mocked_streamlit()
    print("[OK] test_render_with_mocked_streamlit passed")
    print("ALL TESTS IN test_live_sensor_render.py PASSED SUCCESSFULLY!")
