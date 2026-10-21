"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/map_manager.py
Purpose: Interactive Geospatial GIS Map, Highway Risk Corridors & Asset Tracking
=============================================================================
Renders an interactive Folium map modeled after high-tech disaster control rooms:
- Dark CartoDB Dark Matter base map (high-contrast command room aesthetic)
- Multi-station geotechnical sensor nodes (GG-001 through GG-005)
- Mobile GPS Asset Tracking Layer (Emergency QRTs, BRO Dozers, Highway Police, Ambulances)
- Color-coded highway corridor segments (NH-58 Himalayan corridor)
- Dynamic danger radius buffer zones for elevated/critical stations
- Road closure & incident warning overlays
- Rich HTML telemetry inspection popups for both stations and mobile assets
=============================================================================
"""

import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium

# Color mapping helper for geotechnical risk
RISK_COLOR_MAP = {
    "CRITICAL": "#FF2A4D",
    "HIGH": "#FF7A00",
    "MODERATE": "#FFB000",
    "LOW": "#00E5A3",
    "UNKNOWN": "#8B9BB4"
}

# Color mapping for mobile assets
ASSET_COLOR_MAP = {
    "Emergency Rescue": "#EF4444",
    "Heavy Engineering": "#F97316",
    "Highway Police Patrol": "#38BDF8",
    "Emergency Medical": "#10B981",
    "Field Inspection": "#A855F7"
}


def render_risk_map(enriched_stations, road_sections_df=None, risk_filter="ALL", height=500, gps_units=None):
    """
    Renders the professional GIS map with station nodes, highway risk corridors,
    and mobile GPS asset tracking layer.
    """
    # 1. Calculate map center from station coordinates
    lats = [s["lat"] for s in enriched_stations if s.get("lat") is not None]
    lons = [s["lon"] for s in enriched_stations if s.get("lon") is not None]
    center_lat = sum(lats) / len(lats) if lats else 30.18
    center_lon = sum(lons) / len(lons) if lons else 78.50

    # Initialize Folium Map with CartoDB Dark Matter
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="CartoDB dark_matter",
        control_scale=True
    )

    # 2. Add custom map title / status badge in upper left
    mobile_count = len(gps_units) if gps_units else 0
    mobile_badge = f" | {mobile_count} Mobile Units" if mobile_count > 0 else ""
    title_html = f"""
    <div style="position: fixed; 
                top: 15px; left: 55px; width: 280px; 
                background: rgba(14, 23, 37, 0.94); 
                border: 1px solid #263449; border-radius: 8px;
                padding: 10px 14px; z-index: 9999; font-family: 'DM Sans', sans-serif;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5); backdrop-filter: blur(5px);">
        <div style="font-size: 10px; color: #36D6E7; font-weight: 700; letter-spacing: 1.5px;">GIS GEOTECHNICAL GRID</div>
        <div style="font-size: 13px; color: #F1F5F9; font-weight: 700; margin-top: 2px;">NH-58 Himalayan Highway Sector</div>
        <div style="font-size: 11px; color: #94A3B8; margin-top: 4px;">
            Active Nodes: 5 Fixed Stations{mobile_badge}
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # 3. Render Highway Corridor Polyline Segments
    # Real-world approximate mountain highway coordinates connecting stations along the valley
    corridor_segments = [
        {
            "name": "Sector 1: Byasi - Kaudiyala (km 42-58)",
            "coords": [[30.1234, 78.4321], [30.1380, 78.4550], [30.1567, 78.4890]],
            "station": "GG-001"
        },
        {
            "name": "Sector 2: Kaudiyala - Devprayag (km 58-71)",
            "coords": [[30.1567, 78.4890], [30.1750, 78.4980], [30.2012, 78.5123]],
            "station": "GG-002"
        },
        {
            "name": "Sector 3: Devprayag - Kirtinagar (km 71-89)",
            "coords": [[30.2012, 78.5123], [30.2200, 78.5350], [30.2456, 78.5678]],
            "station": "GG-003"
        },
        {
            "name": "Sector 4: Kirtinagar - Srinagar (km 89-105)",
            "coords": [[30.2456, 78.5678], [30.2650, 78.5900], [30.2810, 78.6140]],
            "station": "GG-004"
        }
    ]

    # Map station risk to segment colors
    station_risk_lookup = {s["id"]: s for s in enriched_stations}

    for seg in corridor_segments:
        assoc_stn = station_risk_lookup.get(seg["station"])
        seg_risk = assoc_stn["risk_level"] if assoc_stn else "LOW"
        seg_color = RISK_COLOR_MAP.get(seg_risk, "#22C55E")
        line_weight = 6 if seg_risk in ["CRITICAL", "HIGH"] else 4
        dash_array = "8, 8" if seg_risk == "CRITICAL" else None

        folium.PolyLine(
            locations=seg["coords"],
            color=seg_color,
            weight=line_weight,
            opacity=0.85,
            dash_array=dash_array,
            tooltip=f"{seg['name']} | Risk: {seg_risk}",
            popup=f"<b>{seg['name']}</b><br>Governing Station: {seg['station']}<br>Sector Risk Level: {seg_risk}"
        ).add_to(m)

    # 4. Render Fixed Station Markers & Hazard Buffers
    for stn in enriched_stations:
        r_level = stn["risk_level"]

        # Apply Risk Level Filter
        if risk_filter != "ALL" and r_level != risk_filter:
            continue

        marker_color = RISK_COLOR_MAP.get(r_level, "#22C55E")

        # Add Hazard Buffer for High/Critical Risk
        if r_level == "CRITICAL":
            folium.Circle(
                location=[stn["lat"], stn["lon"]],
                radius=1000,
                color="#EF4444",
                weight=2,
                fill=True,
                fill_color="#EF4444",
                fill_opacity=0.25,
                tooltip=f"CRITICAL ZONE: {stn['id']} 1000m Geotechnical Buffer"
            ).add_to(m)
        elif r_level == "HIGH":
            folium.Circle(
                location=[stn["lat"], stn["lon"]],
                radius=600,
                color="#F97316",
                weight=1,
                fill=True,
                fill_color="#F97316",
                fill_opacity=0.18,
                tooltip=f"HIGH RISK ZONE: {stn['id']} 600m Caution Buffer"
            ).add_to(m)

        # High-Tech Dark Station Popup HTML
        popup_html = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    background: #0E1725; color: #F1F5F9; padding: 12px; 
                    border-radius: 8px; width: 230px; border: 1px solid #263449;">
            <div style="font-size: 10px; color: #36D6E7; font-weight: 700; letter-spacing: 1px;">
                FIXED SENSOR NODE: {stn['id']}
            </div>
            <div style="font-size: 14px; font-weight: 700; margin: 2px 0 6px 0;">
                {stn['name']}
            </div>
            <div style="font-size: 11px; color: #94A3B8; margin-bottom: 8px;">
                {stn.get('corridor', 'NH-58 Corridor')}
            </div>
            
            <div style="background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; font-size: 12px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                    <span style="color:#94A3B8;">Soil Saturation:</span>
                    <b>{stn.get('soil_moisture_pct', 0.0)}%</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                    <span style="color:#94A3B8;">Precipitation:</span>
                    <b>{stn.get('rainfall_intensity_mmh', 0.0)} mm/h</b>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                    <span style="color:#94A3B8;">Slope Tilt:</span>
                    <b>{stn.get('tilt', 0.0):.2f}°</b>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#94A3B8;">Tremor State:</span>
                    <b>{'TREMOR 🔴' if stn.get('vib') else 'STABLE 🟢'}</b>
                </div>
            </div>

            <div style="margin-top: 8px; display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:11px; color:#94A3B8;">Risk Score:</span>
                <span style="font-size: 13px; font-weight: 800; color:{marker_color};">
                    {stn['risk_score']} / 100 ({r_level})
                </span>
            </div>
        </div>
        """

        radius_size = 13 if r_level == "CRITICAL" else (11 if r_level == "HIGH" else 8)

        folium.CircleMarker(
            location=[stn["lat"], stn["lon"]],
            radius=radius_size,
            color=marker_color,
            weight=2,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"[STATION] {stn['id']}: {r_level} ({stn['risk_score']}/100)"
        ).add_to(m)

    # 5. Render Mobile GPS Asset Tracking Layer
    if gps_units:
        for unit in gps_units:
            ulat = unit.get("lat")
            ulon = unit.get("lon")

            # Validate coordinate presence and bounds
            if ulat is None or ulon is None:
                continue
            try:
                ulat = float(ulat)
                ulon = float(ulon)
                if not (-90.0 <= ulat <= 90.0) or not (-180.0 <= ulon <= 180.0):
                    continue
            except (ValueError, TypeError):
                continue

            u_type = unit.get("unit_type", "Emergency Rescue")
            u_color = unit.get("accent_color", ASSET_COLOR_MAP.get(u_type, "#38BDF8"))
            glyph = unit.get("icon_glyph", "🚗")
            callsign = unit.get("callsign", unit.get("name", "Asset"))
            u_id = unit.get("unit_id", "UNIT")
            speed = unit.get("speed_kmh", 0.0)
            heading = unit.get("heading_deg", 0.0)
            altitude = unit.get("altitude_m", 600.0)
            battery = unit.get("battery_pct", 95.0)
            health = unit.get("health_status", "NOMINAL")
            assignment = unit.get("incident_assignment", "Routine Corridor Surveillance")
            is_sim = unit.get("is_simulated", True)
            data_src = unit.get("data_source", "SIMULATED")
            last_ping = unit.get("last_valid_ping", "N/A")
            satellites = unit.get("satellites_in_view", 8)
            is_stale = (health == "STALE")

            # Source Badge styling
            if not is_sim and data_src == "REAL_HARDWARE":
                source_badge = """
                <span style="background: rgba(16, 185, 129, 0.2); color: #10B981; 
                             border: 1px solid #10B981; padding: 2px 6px; border-radius: 4px; 
                             font-size: 10px; font-weight: 700;">
                    ● LIVE GPS HARDWARE
                </span>
                """
            else:
                source_badge = """
                <span style="background: rgba(245, 158, 11, 0.2); color: #F59E0B; 
                             border: 1px solid #F59E0B; padding: 2px 6px; border-radius: 4px; 
                             font-size: 10px; font-weight: 700;">
                    ○ SIMULATED TELEMETRY
                </span>
                """

            # Health badge color
            h_color = "#EF4444" if health in ["CRITICAL", "DISPATCHED"] else ("#F59E0B" if health in ["WARNING", "STALE"] else "#10B981")

            # High-tech interactive asset popup card
            asset_popup_html = f"""
            <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        background: #0B1320; color: #F1F5F9; padding: 12px; 
                        border-radius: 8px; width: 260px; border: 1px solid #263449;
                        box-shadow: 0 8px 24px rgba(0,0,0,0.6);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px;">
                    <div style="font-size: 10px; color: #38BDF8; font-weight: 700; letter-spacing: 1px;">
                        MOBILE GPS UNIT: {u_id}
                    </div>
                    {source_badge}
                </div>
                <div style="font-size: 15px; font-weight: 700; color: #FFFFFF; margin: 2px 0;">
                    {unit.get('name', u_id)}
                </div>
                <div style="font-size: 11px; color: #94A3B8; margin-bottom: 8px;">
                    Callsign: <b style="color:#F1F5F9;">{callsign}</b> • {u_type}
                </div>

                <div style="background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; font-size: 11px; margin-bottom: 8px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                        <span style="color:#94A3B8;">Position:</span>
                        <b style="color:#38BDF8;">{ulat:.4f}°N, {ulon:.4f}°E</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                        <span style="color:#94A3B8;">Altitude:</span>
                        <b>{altitude:.1f} m AMSL</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                        <span style="color:#94A3B8;">Ground Speed:</span>
                        <b style="color:#10B981;">{speed:.1f} km/h</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                        <span style="color:#94A3B8;">Azimuth Heading:</span>
                        <b>{heading:.1f}° ({unit.get('heading_deg', 0):.0f}°)</b>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom: 3px;">
                        <span style="color:#94A3B8;">Battery Level:</span>
                        <b>{battery:.1f}%</b>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#94A3B8;">Constellation Fix:</span>
                        <b>{satellites} Satellites ({'Nominal' if not is_stale else 'Stale Signal'})</b>
                    </div>
                </div>

                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid #1E293B; border-radius: 6px; padding: 6px 8px; font-size: 11px; margin-bottom: 8px;">
                    <div style="color: #64748B; font-size: 10px; font-weight: 600;">ACTIVE ASSIGNMENT</div>
                    <div style="color: #E2E8F0; font-size: 11px; margin-top: 2px;">{assignment}</div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:center; font-size: 10px; color:#64748B;">
                    <span>Status: <b style="color:{h_color};">● {health}</b></span>
                    <span>Ping: {last_ping.split('T')[-1][:8] if 'T' in last_ping else last_ping} UTC</span>
                </div>
            </div>
            """

            # Directional heading indicator SVG arrow
            arrow_svg = f"""
            <svg width="24" height="24" viewBox="0 0 24 24" style="transform: rotate({heading}deg); transform-origin: 50% 50%;">
                <polygon points="12,2 18,22 12,17 6,22" fill="{u_color}" stroke="#FFFFFF" stroke-width="1.5" opacity="0.95"/>
            </svg>
            """

            # Distinct visual marker with beacon pulsing ring
            pulse_ring = f"""
            <div style="position: absolute; width: 44px; height: 44px; top: -10px; left: -10px; 
                        border-radius: 50%; border: 2px solid {u_color}; opacity: 0.6; 
                        animation: pulse 2s infinite ease-out;"></div>
            """ if not is_stale else ""

            stale_badge = f"""
            <div style="position: absolute; top: -6px; right: -8px; background: #EF4444; color: #FFFFFF; font-size: 8px; font-weight: 800; padding: 1px 4px; border-radius: 3px;">
                STALE
            </div>
            """ if is_stale else ""

            marker_div_html = f"""
            <div style="position: relative; width: 26px; height: 26px;">
                {pulse_ring}
                <div style="position: absolute; width: 26px; height: 26px; 
                            background: rgba(14, 23, 37, 0.95); border: 2px solid {u_color}; 
                            border-radius: 6px; display: flex; align-items: center; justify-content: center;
                            box-shadow: 0 0 10px {u_color}88; font-size: 13px;">
                    {glyph}
                </div>
                <div style="position: absolute; top: -14px; left: 1px; width: 24px; height: 24px; pointer-events: none;">
                    {arrow_svg}
                </div>
                {stale_badge}
            </div>
            """

            folium.Marker(
                location=[ulat, ulon],
                icon=folium.DivIcon(
                    icon_size=(26, 26),
                    icon_anchor=(13, 13),
                    html=marker_div_html
                ),
                popup=folium.Popup(asset_popup_html, max_width=280),
                tooltip=f"[ASSET] {u_id} ({callsign}) • {speed:.1f} km/h • {health}"
            ).add_to(m)

    # 6. Add Comprehensive GIS Legend in bottom-right corner
    legend_html = """
    <div style="position: fixed; 
                bottom: 25px; right: 25px; width: 190px; 
                background: rgba(14, 23, 37, 0.95); 
                border: 1px solid #263449; border-radius: 8px;
                padding: 10px 14px; z-index: 9999; font-family: 'DM Sans', sans-serif;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5); font-size: 11px;">
        <div style="font-weight: 700; color: #F1F5F9; margin-bottom: 6px; letter-spacing: 0.5px;">GIS LAYER OVERLAYS</div>
        <div style="font-size: 10px; color: #38BDF8; font-weight: 600; margin-bottom: 4px;">FIXED MONITORING STATIONS</div>
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <span style="height: 9px; width: 9px; background: #EF4444; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">Critical Risk (75-100)</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <span style="height: 9px; width: 9px; background: #F97316; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">High Risk (50-74)</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <span style="height: 9px; width: 9px; background: #EAB308; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">Moderate (25-49)</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
            <span style="height: 9px; width: 9px; background: #22C55E; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span style="color: #F1F5F9;">Low / Stable (0-24)</span>
        </div>
        
        <hr style="border:0; border-top: 1px solid #263449; margin: 6px 0;">
        <div style="font-size: 10px; color: #38BDF8; font-weight: 600; margin-bottom: 4px;">MOBILE GPS ASSETS</div>
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <span style="font-size: 11px; margin-right: 6px;">🚑</span>
            <span style="color: #F1F5F9;">NDRF Alpine QRT</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <span style="font-size: 11px; margin-right: 6px;">🚜</span>
            <span style="color: #F1F5F9;">BRO Clearance Unit</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <span style="font-size: 11px; margin-right: 6px;">🚔</span>
            <span style="color: #F1F5F9;">Highway Police Patrol</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 3px;">
            <span style="font-size: 11px; margin-right: 6px;">🛰️</span>
            <span style="color: #F1F5F9;">DGRE Slope Recon</span>
        </div>

        <hr style="border:0; border-top: 1px solid #263449; margin: 6px 0;">
        <div style="font-size: 10px; color: #94A3B8;">Polylines indicate NH-58 highway sectors color-coded by risk.</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # Render interactive map using streamlit-folium
    return st_folium(m, width="100%", height=height, returned_objects=[])
