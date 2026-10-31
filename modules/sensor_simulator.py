"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/sensor_simulator.py
Purpose: Realistic Physics-Based IoT Telemetry Simulator & Historical Seeder
=============================================================================
Generates physical sensor measurements for highway monitoring stations:
- Soil Saturation (ADC 1000-3800 & Calibrated VWC %)
- Rain Gauge (ADC 1000-3900 & Calibrated Precipitation mm/h, 24h accumulation)
- Tri-axial MEMS Inclinometer (Tilt degrees & Angular displacement rate deg/h)
- Piezoelectric Vibration Sensor (Trigger state & Peak acceleration in Gs)
- Battery state of charge (%)

Includes emergency event injection and automatic 24-hour historical seeding.
"""

import random
import math
from datetime import datetime, timedelta
from database.db import get_connection, log_telemetry

# Initial default station coordinates and environmental baselines (NH-58 Himalayan Corridor)
# Row 2 (GG-002) is Shivpuri (the single critical prototype node), others nominal.
DEFAULT_STATIONS = [
    {"id": "GG-001", "name": "NH-58 Mountain Pass", "corridor": "NH-58 km 42 (Byasi Gorge)", "lat": 30.1234, "lon": 78.4321, "soil_adc": 1800, "soil_moisture_pct": 26.5, "rain_adc": 1500, "rainfall_intensity_mmh": 0.0, "rain_intensity": 0.0, "tilt": 0.25, "vib": False, "acc_rain": 3.5, "temp_c": 14.5},
    {"id": "GG-002", "name": "Shivpuri", "corridor": "NH-58 km 58 (Shivpuri Sector)", "lat": 30.1567, "lon": 78.4890, "soil_adc": 3850, "soil_moisture_pct": 88.5, "rain_adc": 3750, "rainfall_intensity_mmh": 32.0, "rain_intensity": 32.0, "tilt": 3.85, "vib": True, "acc_rain": 38.2, "temp_c": 11.2},
    {"id": "GG-003", "name": "Ridge Tunnel Link", "corridor": "NH-58 km 71 (Devprayag Confluence)", "lat": 30.2012, "lon": 78.5123, "soil_adc": 1750, "soil_moisture_pct": 24.0, "rain_adc": 1450, "rainfall_intensity_mmh": 0.0, "rain_intensity": 0.0, "tilt": 0.28, "vib": False, "acc_rain": 2.8, "temp_c": 12.8},
    {"id": "GG-004", "name": "Highland Slope North", "corridor": "NH-58 km 89 (Kirtinagar Bluffs)", "lat": 30.2456, "lon": 78.5678, "soil_adc": 1650, "soil_moisture_pct": 21.0, "rain_adc": 1400, "rainfall_intensity_mmh": 0.0, "rain_intensity": 0.0, "tilt": 0.20, "vib": False, "acc_rain": 2.0, "temp_c": 15.0},
    {"id": "GG-005", "name": "Alaknanda Escarpment", "corridor": "NH-58 km 105 (Srinagar Approach)", "lat": 30.2810, "lon": 78.6140, "soil_adc": 1600, "soil_moisture_pct": 19.5, "rain_adc": 1350, "rainfall_intensity_mmh": 0.0, "rain_intensity": 0.0, "tilt": 0.18, "vib": False, "acc_rain": 1.5, "temp_c": 16.2}
]

def adc_to_moisture_pct(adc):
    """Calibrates 12-bit soil capacitive sensor ADC (1200 dry to 3800 saturated) to VWC %."""
    pct = ((adc - 1100) / 2600.0) * 100.0
    return round(max(5.0, min(98.0, pct)), 1)

def adc_to_rainfall_intensity(adc):
    """Calibrates optical/tipping rain sensor ADC to instantaneous mm/h."""
    if adc > 3400:
        return round(35.0 + (adc - 3400) * 0.035, 1)
    elif adc > 2600:
        return round(12.0 + (adc - 2600) * 0.025, 1)
    elif adc > 1800:
        return round(2.0 + (adc - 1800) * 0.012, 1)
    return 0.0

def generate_telemetry_tick(current_telemetry, emergency=True, emergency_target="GG-002"):
    """
    Simulates one realistic telemetry step for all configured stations.
    Only Shivpuri (GG-002) is critical during an alarm/emergency; all other 4 remain nominal.
    """
    updated = []
    now_iso = datetime.utcnow().isoformat()

    for stn in current_telemetry:
        item = dict(stn)
        is_target = emergency and (item["id"] == emergency_target)

        if is_target:
            # Acute geotechnical landslide precursors on Shivpuri (GG-002) with live dynamic micro-fluctuations
            item["soil_adc"] = max(3600, min(3950, item.get("soil_adc", 3850) + random.randint(-10, 10)))
            item["rain_adc"] = max(3500, min(3900, item.get("rain_adc", 3750) + random.randint(-10, 10)))
            item["soil_moisture_pct"] = round(max(82.0, min(94.0, item.get("soil_moisture_pct", 88.5) + random.uniform(-0.2, 0.2))), 1)
            item["rainfall_intensity_mmh"] = round(max(28.0, min(38.0, item.get("rainfall_intensity_mmh", 32.0) + random.uniform(-0.3, 0.3))), 1)
            item["rain_intensity"] = item["rainfall_intensity_mmh"]
            item["temp_c"] = round(max(10.5, min(12.5, item.get("temp_c", 11.2) + random.uniform(-0.1, 0.1))), 1)
            item["tilt"] = round(max(3.60, min(4.10, item.get("tilt", 3.85) + random.uniform(-0.02, 0.02))), 2)
            item["tilt_rate"] = round(max(0.40, min(0.65, item.get("tilt_rate", 0.55) + random.uniform(-0.01, 0.01))), 2)
            item["vib"] = True
            item["vib_g"] = round(max(1.50, min(2.10, item.get("vib_g", 1.85) + random.uniform(-0.04, 0.04))), 2)
            item["acc_rain"] = round(item.get("acc_rain", 38.2) + 0.05, 1)
            item["battery"] = 92.5
        else:
            # Nominal environmental walk (Normal / Low status for all other 4 stations)
            item["soil_adc"] = max(1500, min(2200, item.get("soil_adc", 1700) + random.randint(-10, 10)))
            item["rain_adc"] = max(1200, min(1700, item.get("rain_adc", 1400) + random.randint(-10, 10)))
            item["temp_c"] = round(max(8.0, min(25.0, item.get("temp_c", 14.0) + random.uniform(-0.1, 0.1))), 1)
            item["tilt"] = round(max(0.12, min(0.35, item.get("tilt", 0.22) + random.uniform(-0.01, 0.01))), 2)
            item["tilt_rate"] = 0.02
            item["vib"] = False
            item["vib_g"] = 0.02
            item["acc_rain"] = round(max(0.0, min(5.0, item.get("acc_rain", 2.5) + random.uniform(-0.02, 0.05))), 1)
            item["battery"] = 98.5
            item["soil_moisture_pct"] = adc_to_moisture_pct(item["soil_adc"])
            item["rainfall_intensity_mmh"] = 0.0
            item["rain_intensity"] = 0.0

        item["timestamp"] = now_iso
        item["is_simulated"] = True
        updated.append(item)

    return updated

def seed_historical_telemetry_if_needed():
    """
    Checks if telemetry_history in SQLite is empty or sparse (<30 records).
    If so, generates 24 hours of synthetic 15-minute interval historical readings
    for all 5 stations so that Historical Analytics and maps are immediately functional!
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM telemetry_history")
    count = cursor.fetchone()[0]
    
    if count >= 30:
        conn.close()
        return

    now = datetime.utcnow()
    # Generate 96 intervals (one every 15 minutes over past 24 hours)
    historical_records = []

    for step in range(96, 0, -1):
        ts = (now - timedelta(minutes=step * 15)).isoformat()
        diurnal_factor = math.sin((96 - step) / 96.0 * 2 * math.pi)

        for base in DEFAULT_STATIONS:
            stn_id = base["id"]
            # Add gradual rainstorm event around 6 hours ago on GG-001 and GG-003
            storm_boost = 0
            if step in range(20, 45) and stn_id in ["GG-001", "GG-003"]:
                storm_boost = 400 + (45 - abs(step - 32)) * 30

            soil_adc = int(base["soil_adc"] + diurnal_factor * 80 + storm_boost * 0.8 + random.randint(-20, 20))
            rain_adc = int(base["rain_adc"] + storm_boost + random.randint(-30, 30))
            soil_pct = adc_to_moisture_pct(soil_adc)
            rain_mmh = adc_to_rainfall_intensity(rain_adc)
            
            tilt = round(base["tilt"] + (storm_boost / 1800.0) * 0.5 + random.uniform(-0.02, 0.02), 2)
            tilt_rate = round(random.uniform(0.01, 0.08), 2)
            vib_detected = 1 if (storm_boost > 600 and random.random() > 0.6) else 0
            vib_g = round(random.uniform(0.8, 1.8), 2) if vib_detected else round(random.uniform(0.02, 0.1), 2)
            acc_rain = round(base["acc_rain"] + (96 - step) * 0.15 + (storm_boost / 40.0), 1)

            temp_c = round(base.get("temp_c", 12.0) + diurnal_factor * 3.5 + random.uniform(-0.4, 0.4), 1)

            historical_records.append((
                ts, stn_id, soil_adc, soil_pct, temp_c, rain_adc, rain_mmh, acc_rain,
                tilt, tilt_rate, vib_detected, vib_g, 97.5, 1
            ))

    cursor.executemany('''
        INSERT INTO telemetry_history (
            timestamp, station_id, soil_adc, soil_moisture_pct,
            temperature_c, rain_adc, rainfall_intensity_mmh, rain_acc_24h_mm,
            tilt_degrees, tilt_rate_deg_h, vibration_detected,
            vibration_intensity_g, battery_pct, is_simulated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', historical_records)

    conn.commit()
    conn.close()
