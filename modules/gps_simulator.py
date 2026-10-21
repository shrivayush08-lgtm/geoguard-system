"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/gps_simulator.py
Purpose: Kinematic GPS Simulator for Mobile Response Assets along NH-58 Corridor
=============================================================================
Simulates realistic, smooth GPS movement for mobile emergency and patrol assets
along the Rishikesh–Joshimath NH-58 Himalayan corridor:
- Emergency Rescue Vehicles (NDRF Alpine QRT)
- Highway Patrol Units (Uttarakhand Police Interceptor)
- Heavy Clearance Equipment (BRO 753 Task Force)
- Critical Care Ambulances (Garhwal EMS)
- Geotechnical Field Inspection & Recon Teams

Features:
- Geographically accurate NH-58 valley waypoints
- Forward-azimuth heading calculation
- Speed curves with mountain terrain braking and accelerating
- Terrain altitude interpolation
- Battery discharge / alternator charging cycle simulation
- Automated emergency dispatch rerouting when disaster drill triggers
- Preservation of waypoint progress across Streamlit reruns
- Clear 'SIMULATED' telemetry labeling
=============================================================================
"""

import math
import random
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Section 1: NH-58 Corridor Waypoint Nodes (Rishikesh to Joshimath)
# ---------------------------------------------------------------------------
# Accurate geographic coordinates along the NH-58 Himalayan arterial route.
NH58_WAYPOINTS = [
    {"name": "Rishikesh Transit Terminal", "lat": 30.0869, "lon": 78.2676, "alt_m": 350.0},
    {"name": "Tapovan Gorge Checkpoint", "lat": 30.1310, "lon": 78.3240, "alt_m": 410.0},
    {"name": "Shivpuri Rafting Bend", "lat": 30.1360, "lon": 78.3880, "alt_m": 435.0},
    {"name": "Byasi Gorge (GG-001)", "lat": 30.1234, "lon": 78.4321, "alt_m": 620.0},
    {"name": "Kaudiyala Sector (GG-002)", "lat": 30.1567, "lon": 78.4890, "alt_m": 710.0},
    {"name": "Devprayag Confluence (GG-003)", "lat": 30.2012, "lon": 78.5123, "alt_m": 830.0},
    {"name": "Kirtinagar Bluffs (GG-004)", "lat": 30.2456, "lon": 78.5678, "alt_m": 950.0},
    {"name": "Srinagar Approach (GG-005)", "lat": 30.2810, "lon": 78.6140, "alt_m": 1040.0},
    {"name": "Rudraprayag Sangam Bridge", "lat": 30.2844, "lon": 78.9811, "alt_m": 1120.0},
    {"name": "Gauchar Airstrip Transit", "lat": 30.2910, "lon": 79.1520, "alt_m": 1180.0},
    {"name": "Karnaprayag Confluence", "lat": 30.2600, "lon": 79.2170, "alt_m": 1250.0},
    {"name": "Nandaprayag Ghat", "lat": 30.3300, "lon": 79.3100, "alt_m": 1310.0},
    {"name": "Chamoli Highway Depot", "lat": 30.4070, "lon": 79.3380, "alt_m": 1380.0},
    {"name": "Birahi Gorge Switchbacks", "lat": 30.4150, "lon": 79.3900, "alt_m": 1460.0},
    {"name": "Pipalkoti Staging Area", "lat": 30.4300, "lon": 79.4300, "alt_m": 1540.0},
    {"name": "Helang Escarpment", "lat": 30.5200, "lon": 79.5100, "alt_m": 1720.0},
    {"name": "Joshimath Military Base", "lat": 30.5564, "lon": 79.5637, "alt_m": 1875.0}
]

# ---------------------------------------------------------------------------
# Section 2: Default Mobile Asset Registry (5 Tracked Units)
# ---------------------------------------------------------------------------
DEFAULT_GPS_UNITS = [
    {
        "unit_id": "UNIT-SAR-01",
        "name": "NDRF Alpine QRT-1",
        "unit_type": "Emergency Rescue",
        "callsign": "Rescuer Alpha",
        "authority": "National Disaster Response Force (8th Bn)",
        "base_location": "Rishikesh Base",
        "lat": 30.1234,
        "lon": 78.4321,
        "altitude_m": 620.0,
        "speed_kmh": 42.0,
        "heading_deg": 65.0,
        "battery_pct": 94.5,
        "health_status": "NOMINAL",
        "incident_assignment": "Patrol — Sector 1 Byasi Gorge (GG-001)",
        "data_source": "SIMULATED",
        "is_simulated": True,
        "last_valid_ping": datetime.now(timezone.utc).isoformat(),
        "signal_quality": "EXCELLENT",
        "satellites_in_view": 11,
        "start_waypoint_idx": 1,
        "end_waypoint_idx": 4,
        "current_waypoint_idx": 2,
        "waypoint_progress": 0.45,
        "direction": 1,
        "icon_glyph": "🚑",
        "accent_color": "#EF4444"
    },
    {
        "unit_id": "UNIT-BRO-753",
        "name": "BRO 753 Heavy Clearance",
        "unit_type": "Heavy Engineering",
        "callsign": "Dozer One",
        "authority": "Border Roads Organisation",
        "base_location": "Devprayag Depot",
        "lat": 30.1850,
        "lon": 78.5040,
        "altitude_m": 780.0,
        "speed_kmh": 28.5,
        "heading_deg": 48.0,
        "battery_pct": 89.0,
        "health_status": "NOMINAL",
        "incident_assignment": "Rockfall Netting Inspection — SEC-03 Devprayag",
        "data_source": "SIMULATED",
        "is_simulated": True,
        "last_valid_ping": datetime.now(timezone.utc).isoformat(),
        "signal_quality": "GOOD",
        "satellites_in_view": 9,
        "start_waypoint_idx": 4,
        "end_waypoint_idx": 7,
        "current_waypoint_idx": 5,
        "waypoint_progress": 0.30,
        "direction": 1,
        "icon_glyph": "🚜",
        "accent_color": "#F97316"
    },
    {
        "unit_id": "UNIT-HP-04",
        "name": "NH-58 Highway Patrol 4",
        "unit_type": "Highway Police Patrol",
        "callsign": "Patrol Delta",
        "authority": "Uttarakhand Highway Police",
        "base_location": "Byasi Checkpost",
        "lat": 30.1450,
        "lon": 78.4620,
        "altitude_m": 665.0,
        "speed_kmh": 52.0,
        "heading_deg": 52.0,
        "battery_pct": 98.0,
        "health_status": "NOMINAL",
        "incident_assignment": "Speed Regulation & Chokepoint Transit Escort",
        "data_source": "SIMULATED",
        "is_simulated": True,
        "last_valid_ping": datetime.now(timezone.utc).isoformat(),
        "signal_quality": "EXCELLENT",
        "satellites_in_view": 12,
        "start_waypoint_idx": 2,
        "end_waypoint_idx": 5,
        "current_waypoint_idx": 3,
        "waypoint_progress": 0.70,
        "direction": 1,
        "icon_glyph": "🚔",
        "accent_color": "#38BDF8"
    },
    {
        "unit_id": "UNIT-EMS-08",
        "name": "Garhwal Critical Ambulance",
        "unit_type": "Emergency Medical",
        "callsign": "Medic Charlie",
        "authority": "Garhwal District Health Authority",
        "base_location": "Srinagar Base Hospital",
        "lat": 30.2680,
        "lon": 78.5950,
        "altitude_m": 1010.0,
        "speed_kmh": 46.0,
        "heading_deg": 40.0,
        "battery_pct": 91.0,
        "health_status": "NOMINAL",
        "incident_assignment": "Standby — Srinagar Trauma Centre Corridor",
        "data_source": "SIMULATED",
        "is_simulated": True,
        "last_valid_ping": datetime.now(timezone.utc).isoformat(),
        "signal_quality": "GOOD",
        "satellites_in_view": 10,
        "start_waypoint_idx": 5,
        "end_waypoint_idx": 8,
        "current_waypoint_idx": 6,
        "waypoint_progress": 0.50,
        "direction": 1,
        "icon_glyph": "🚑",
        "accent_color": "#10B981"
    },
    {
        "unit_id": "UNIT-GEO-SURV",
        "name": "DGRE Slope Recon Team",
        "unit_type": "Field Inspection",
        "callsign": "Geo Surveyor 1",
        "authority": "Defence Geoinformatics Research Establishment",
        "base_location": "Kirtinagar Forward Depot",
        "lat": 30.2240,
        "lon": 78.5420,
        "altitude_m": 890.0,
        "speed_kmh": 32.0,
        "heading_deg": 55.0,
        "battery_pct": 87.5,
        "health_status": "NOMINAL",
        "incident_assignment": "LiDAR Micro-Terrain & Creep Measurement Survey",
        "data_source": "SIMULATED",
        "is_simulated": True,
        "last_valid_ping": datetime.now(timezone.utc).isoformat(),
        "signal_quality": "EXCELLENT",
        "satellites_in_view": 14,
        "start_waypoint_idx": 4,
        "end_waypoint_idx": 7,
        "current_waypoint_idx": 4,
        "waypoint_progress": 0.85,
        "direction": 1,
        "icon_glyph": "🛰️",
        "accent_color": "#A855F7"
    }
]

# ---------------------------------------------------------------------------
# Section 3: Geodesic Math Helpers
# ---------------------------------------------------------------------------

def calculate_forward_heading(lat1, lon1, lat2, lon2):
    """
    Computes initial true bearing / azimuth heading in degrees [0, 360)
    from point (lat1, lon1) to point (lat2, lon2).
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    theta = math.atan2(y, x)
    heading = (math.degrees(theta) + 360.0) % 360.0
    return round(heading, 1)

def haversine_distance_km(lat1, lon1, lat2, lon2):
    """Computes great-circle distance between two coordinates in kilometers."""
    R = 6371.0 # Earth's mean radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

# ---------------------------------------------------------------------------
# Section 4: Simulation Stepper
# ---------------------------------------------------------------------------

def simulate_gps_tick(current_units, elapsed_sec=3.0, emergency=False, emergency_target="GG-001"):
    """
    Advances simulated mobile assets along their NH-58 corridor routes smoothly.
    - Preserves waypoint indices and sub-progress across calls
    - Computes authentic mountain speed variations and forward heading
    - Elevates speed and marks units 'DISPATCHED' when emergency drill is active
    - Always labels simulated records clearly as data_source='SIMULATED'
    """
    updated_units = []
    now_iso = datetime.now(timezone.utc).isoformat()
    total_waypoints = len(NH58_WAYPOINTS)

    for unit in current_units:
        # If this specific unit is receiving live hardware telemetry, do not overwrite with simulation
        if not unit.get("is_simulated", True) and unit.get("data_source") == "REAL_HARDWARE":
            updated_units.append(unit)
            continue

        u = dict(unit)
        start_idx = u.get("start_waypoint_idx", 0)
        end_idx = min(total_waypoints - 1, u.get("end_waypoint_idx", total_waypoints - 1))
        curr_idx = u.get("current_waypoint_idx", start_idx)
        prog = u.get("waypoint_progress", 0.0)
        direction = u.get("direction", 1)

        # Emergency dispatch override: SAR unit and BRO unit sprint to emergency target
        is_emergency_responder = emergency and u["unit_id"] in ["UNIT-SAR-01", "UNIT-BRO-753"]
        if is_emergency_responder:
            u["health_status"] = "DISPATCHED"
            u["incident_assignment"] = f"CRISIS DISPATCH — Emergency Response to {emergency_target} Byasi Gorge"
            target_speed = random.uniform(65.0, 78.0) # Emergency transit speed
        else:
            if u["health_status"] == "DISPATCHED" and not emergency:
                u["health_status"] = "NOMINAL"
                u["incident_assignment"] = "Routine Corridor Surveillance & Inspection"
            target_speed = random.uniform(32.0, 54.0) # Nominal mountain highway speed

        # Next waypoint index based on patrol direction
        next_idx = curr_idx + direction
        if next_idx > end_idx:
            direction = -1
            next_idx = curr_idx - 1
        elif next_idx < start_idx:
            direction = 1
            next_idx = curr_idx + 1

        next_idx = max(0, min(total_waypoints - 1, next_idx))

        wp_from = NH58_WAYPOINTS[curr_idx]
        wp_to = NH58_WAYPOINTS[next_idx]

        # Calculate leg distance in km
        leg_dist_km = haversine_distance_km(wp_from["lat"], wp_from["lon"], wp_to["lat"], wp_to["lon"])
        leg_dist_km = max(0.5, leg_dist_km)

        # Distance covered in this tick
        dist_covered_km = (target_speed / 3600.0) * elapsed_sec
        prog_step = dist_covered_km / leg_dist_km
        new_prog = prog + prog_step

        # Advance to next waypoint segment if completed
        if new_prog >= 1.0:
            curr_idx = next_idx
            new_prog = 0.0
            next_idx = curr_idx + direction
            if next_idx > end_idx:
                direction = -1
                next_idx = curr_idx - 1
            elif next_idx < start_idx:
                direction = 1
                next_idx = curr_idx + 1
            next_idx = max(0, min(total_waypoints - 1, next_idx))
            wp_from = NH58_WAYPOINTS[curr_idx]
            wp_to = NH58_WAYPOINTS[next_idx]

        # Interpolate coordinates between wp_from and wp_to
        clat = wp_from["lat"] + (wp_to["lat"] - wp_from["lat"]) * new_prog
        clon = wp_from["lon"] + (wp_to["lon"] - wp_from["lon"]) * new_prog
        calt = wp_from["alt_m"] + (wp_to["alt_m"] - wp_from["alt_m"]) * new_prog

        # Add small natural GPS jitter (±0.00005 deg ~ 5m)
        clat += random.uniform(-0.00005, 0.00005)
        clon += random.uniform(-0.00005, 0.00005)

        # Compute dynamic forward azimuth heading
        heading = calculate_forward_heading(wp_from["lat"], wp_from["lon"], wp_to["lat"], wp_to["lon"])

        # Update battery level (slow realistic alternator charge/discharge)
        batt = u.get("battery_pct", 95.0)
        batt = round(max(20.0, min(100.0, batt + random.uniform(-0.05, 0.02))), 1)

        # Update unit dictionary
        u["lat"] = round(clat, 5)
        u["lon"] = round(clon, 5)
        u["altitude_m"] = round(calt, 1)
        u["speed_kmh"] = round(target_speed, 1)
        u["heading_deg"] = heading
        u["battery_pct"] = batt
        u["current_waypoint_idx"] = curr_idx
        u["waypoint_progress"] = round(new_prog, 4)
        u["direction"] = direction
        u["last_valid_ping"] = now_iso
        u["data_source"] = "SIMULATED"
        u["is_simulated"] = True
        u["signal_quality"] = "EXCELLENT" if u.get("satellites_in_view", 10) >= 8 else "GOOD"

        updated_units.append(u)

    return updated_units
