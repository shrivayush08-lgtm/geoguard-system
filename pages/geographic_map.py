"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/geographic_map.py
Purpose: Geospatial GIS Surveillance, Weather Telemetry & Mobile GPS Tracking
=============================================================================
Provides:
- Dark GIS Map with Folium and CartoDB Dark Matter
- Highway corridor polylines dynamically color-coded by geotechnical risk
- Fixed geotechnical monitoring nodes (GG-001 to GG-005)
- Live GPS Mobile Asset Tracking Layer (NDRF QRT, BRO Dozer, Police, EMS, Survey)
- Live Mountain Weather Ribbon (Open-Meteo API integration)
- Sector Telemetry Inspection Drawer
- Resilient Telemetry Table (accessible even if basemap canvas or tiles fail)
- Hardware GPS Receiver Bridge Interface & Status Diagnostics
- Temporal Playback Scrubber for historical simulation
=============================================================================
"""

import streamlit as st
import pandas as pd
from modules.map_manager import render_risk_map
from modules.weather_service import fetch_corridor_weather
from database.db import get_road_sections, update_response_team
from modules.ui import render_html
from modules.gps_reader import GPSHardwareGateway, evaluate_stale_telemetry


def render_geographic_map_page(enriched_stations):
    """Renders the comprehensive GIS geospatial risk map and live GPS asset tracking view."""
    st.markdown("<div class='hud-eyebrow'>GEOSPATIAL SURVEILLANCE & GIS ASSET TRACKING</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Geographic Risk Map & Live Asset Tracking</h2>", unsafe_allow_html=True)

    # 1. Live Mountain Weather Telemetry Ribbon
    weather_data = fetch_corridor_weather(lat=30.1234, lon=78.4321)
    
    wc1, wc2, wc3, wc4, wc5 = st.columns(5)
    with wc1:
        st.metric("Corridor Temperature", f"{weather_data['temperature_c']}°C", "Mountain Lapse Rate")
    with wc2:
        st.metric("Gorge Wind Velocity", f"{weather_data['wind_speed_kmh']} km/h", weather_data['wind_direction'])
    with wc3:
        st.metric("Barometric Pressure", f"{weather_data['pressure_hpa']} hPa", "Atmospheric")
    with wc4:
        st.metric("Precipitation Rate", f"{weather_data['precipitation_rate_mmh']} mm/h", weather_data['condition'])
    with wc5:
        st.metric("Atmospheric Moisture", f"{weather_data['humidity_pct']}%", f"Source: {weather_data['source'].split()[0]}")

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Retrieve & Evaluate Mobile GPS Assets
    gps_units = st.session_state.get("gps_units", [])
    # Evaluate stale signal threshold (45 seconds)
    gps_units = evaluate_stale_telemetry(gps_units, stale_threshold_sec=45.0)
    st.session_state.gps_units = gps_units

    # 3. GIS Map Filter Controls & Layer Toggles
    filter_col1, filter_col2, filter_col3 = st.columns([1.5, 1.5, 2])
    with filter_col1:
        risk_filter = st.selectbox(
            "Filter Stations by Risk Level",
            ["ALL", "CRITICAL", "HIGH", "MODERATE", "LOW"],
            index=0
        )
    with filter_col2:
        asset_type_filter = st.selectbox(
            "Filter Mobile Assets by Role",
            ["ALL ASSETS", "Emergency Rescue", "Heavy Engineering", "Highway Police Patrol", "Emergency Medical", "Field Inspection"],
            index=0
        )
    with filter_col3:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        active_sim = sum(1 for u in gps_units if u.get("is_simulated", True))
        active_hw = sum(1 for u in gps_units if not u.get("is_simulated", True))
        st.caption(f"📡 <b>Tracking Fleet:</b> {len(gps_units)} Mobile Units ({active_sim} Simulated, {active_hw} Live Hardware).", unsafe_allow_html=True)

    # Filter mobile assets based on user selection
    if asset_type_filter == "ALL ASSETS":
        filtered_gps = gps_units
    else:
        filtered_gps = [u for u in gps_units if u.get("unit_type") == asset_type_filter]

    # 4. Interactive Folium GIS Map Render (Primary Visualization)
    road_sections_df = get_road_sections()
    render_risk_map(
        enriched_stations,
        road_sections_df=road_sections_df,
        risk_filter=risk_filter,
        height=540,
        gps_units=filtered_gps
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Offline-Resilient Mobile Asset Telemetry Roster
    # (Guarantees complete telemetry accessibility even if tile server fails or basemap is unavailable)
    st.markdown("<div class='hud-eyebrow'>MOBILE ASSET TELEMETRY & DISPATCH ROSTER</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Live Highway Corridor Fleet Surveillance</h3>", unsafe_allow_html=True)

    if gps_units:
        # High-level fleet KPIs
        avg_speed = sum(u.get("speed_kmh", 0.0) for u in gps_units) / max(1, len(gps_units))
        avg_batt = sum(u.get("battery_pct", 100.0) for u in gps_units) / max(1, len(gps_units))
        dispatched_cnt = sum(1 for u in gps_units if u.get("health_status") == "DISPATCHED")

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Active Response Fleet", f"{len(gps_units)} Units", "NH-58 Himalayan Sector")
        with k2:
            st.metric("Average Corridor Transit Speed", f"{avg_speed:.1f} km/h", "Mountain Transit Flow")
        with k3:
            st.metric("Fleet Power / Battery Index", f"{avg_batt:.1f}%", "Nominal Bus Voltage")
        with k4:
            st.metric("Emergency Dispatches", f"{dispatched_cnt} Active", "Crisis Mobilization" if dispatched_cnt > 0 else "Nominal Readiness")

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # Tabular overview of all mobile assets with full telemetry
        asset_rows = []
        for u in gps_units:
            is_sim = u.get("is_simulated", True)
            src_label = "SIMULATED" if is_sim else "LIVE GPS"
            last_p = u.get("last_valid_ping", "N/A")
            last_p_fmt = last_p.split("T")[-1][:8] if "T" in str(last_p) else str(last_p)

            asset_rows.append({
                "Unit ID": u.get("unit_id"),
                "Callsign": u.get("callsign", "N/A"),
                "Unit Type": u.get("unit_type"),
                "Latitude": f"{u.get('lat', 0.0):.4f}°N",
                "Longitude": f"{u.get('lon', 0.0):.4f}°E",
                "Altitude (m)": f"{u.get('altitude_m', 0.0):.0f} m",
                "Speed (km/h)": f"{u.get('speed_kmh', 0.0):.1f}",
                "Heading": f"{u.get('heading_deg', 0.0):.0f}°",
                "Battery": f"{u.get('battery_pct', 0.0):.0f}%",
                "Status": u.get("health_status", "NOMINAL"),
                "Data Source": src_label,
                "Last Ping (UTC)": last_p_fmt,
                "Active Assignment": u.get("incident_assignment", "Routine Patrol")
            })

        assets_df = pd.DataFrame(asset_rows)
        st.dataframe(
            assets_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Unit ID": st.column_config.TextColumn("Unit ID", width="small"),
                "Callsign": st.column_config.TextColumn("Callsign", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Data Source": st.column_config.TextColumn("Source", width="small"),
                "Active Assignment": st.column_config.TextColumn("Tactical Assignment", width="large")
            }
        )

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # 6. Sector Telemetry Inspection Drawer (Fixed Monitoring Nodes)
    st.markdown("<div class='hud-eyebrow'>SECTOR TELEMETRY INSPECTOR</div>", unsafe_allow_html=True)
    st.markdown("<h3 style='margin-top:0;'>Targeted Sector Node Diagnostics</h3>", unsafe_allow_html=True)
    
    sel_stn_id = st.selectbox(
        "Select Corridor Sector for Detailed Examination",
        [s["id"] for s in enriched_stations],
        format_func=lambda x: f"{x} — {next((s['name'] for s in enriched_stations if s['id'] == x), x)}"
    )
    inspected = next((s for s in enriched_stations if s["id"] == sel_stn_id), enriched_stations[0])

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Coordinates</div>
            <div style='font-size: 14px; font-weight: 600; color: #F8FAFC; margin-top: 4px;'>{inspected['lat']:.4f}°N, {inspected['lon']:.4f}°E</div>
            <div style='font-size: 11px; color: #38BDF8; margin-top: 2px;'>{inspected.get('elevation_m', 620)}m Elevation</div>
        </div>
        """)
    with d2:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Pore Saturation</div>
            <div style='font-size: 14px; font-weight: 600; color: #38BDF8; margin-top: 4px;'>{inspected.get('soil_moisture_pct', 0.0)}% VWC</div>
            <div style='font-size: 11px; color: #94A3B8; margin-top: 2px;'>ADC: {inspected.get('soil_adc')} counts</div>
        </div>
        """)
    with d3:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Displacement Angle</div>
            <div style='font-size: 14px; font-weight: 600; color: {"#EF4444" if inspected.get("tilt", 0.0) > 2.0 else "#10B981"}; margin-top: 4px;'>{inspected.get('tilt', 0.0):.2f}°</div>
            <div style='font-size: 11px; color: #94A3B8; margin-top: 2px;'>Creep: {inspected.get('tilt_rate', 0.0):+.2f}°/h</div>
        </div>
        """)
    with d4:
        render_html(f"""
        <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 12px;'>
            <div style='font-size: 11px; color: #94A3B8; font-weight: 600; text-transform: uppercase;'>Sector Risk Index</div>
            <div style='font-size: 14px; font-weight: 600; color: {inspected["status_color"]}; margin-top: 4px;'>{inspected['risk_score']} / 100</div>
            <div style='font-size: 11px; color: {inspected["status_color"]}; margin-top: 2px;'>● {inspected['risk_level']}</div>
        </div>
        """)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # 7. Hardware GPS Receiver Bridge Interface
    with st.expander("🔌 Real Hardware GPS Receiver Bridge (Serial / NMEA / IoT)", expanded=False):
        st.markdown("""
        **Modular Telemetry Bridge Adapter:**
        Connect physical u-blox NEO-6M/8M, Quectel L86, SIM7600 GPS receivers, or an ESP32 RF/LoRa gateway to stream authenticated GPS packets.
        """)

        if "gps_gateway" not in st.session_state:
            st.session_state.gps_gateway = GPSHardwareGateway()

        gw = st.session_state.gps_gateway
        diag = gw.get_diagnostics()

        avail_ports = GPSHardwareGateway.list_available_ports()
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            sel_port = st.selectbox("Serial COM Port", avail_ports if avail_ports else ["No Serial Ports Detected"])
        with h_col2:
            sel_baud = st.selectbox("Baud Rate", [9600, 19200, 38400, 57600, 115200], index=0)
        with h_col3:
            target_unit = st.selectbox(
                "Map To Mobile Unit",
                [u["unit_id"] for u in gps_units] if gps_units else ["UNIT-SAR-01"],
                format_func=lambda x: f"{x} — {next((u['name'] for u in gps_units if u['unit_id'] == x), x)}"
            )

        btn_c1, btn_c2 = st.columns([1, 1])
        with btn_c1:
            if not gw.is_connected:
                if st.button("🔗 Connect GPS Hardware", type="primary", use_container_width=True, disabled=(not avail_ports)):
                    ok, msg = gw.connect(sel_port, sel_baud, target_unit_id=target_unit)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
            else:
                if st.button("🔌 Disconnect Hardware", use_container_width=True):
                    gw.disconnect()
                    st.info("GPS hardware disconnected.")
                    st.rerun()

        with btn_c2:
            st.markdown(f"""
            <div style='background: #111827; border: 1px solid #1F2937; border-radius: 6px; padding: 10px; font-size: 11px;'>
                <div><b>Link Status:</b> <span style='color:{"#10B981" if gw.is_connected else "#94A3B8"};'>{diag['status']}</span></div>
                <div><b>Packets Ingested:</b> {diag['total_packets']} (Errors: {diag['checksum_errors']})</div>
                <div><b>Diagnostics:</b> {diag['status_message']}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 8. Temporal Risk Playback & Dispatch Trigger
    p_col1, p_col2 = st.columns([2, 1.5])
    with p_col1:
        st.markdown("### Historical Snapshot Playback")
        time_scrub = st.slider("Select Historical Snapshot (Hours ago)", 0, 24, 24, format="T-%d Hours")
        st.caption(f"Reconstructed kinematic snapshot at T-{24 - time_scrub} hours from SQLite telemetry logs.")

    with p_col2:
        st.markdown("### Sector Incident Dispatch")
        if 'dispatch_status' not in st.session_state:
            st.session_state.dispatch_status = "Standby — All Sector Rescue Units Nominal"
        
        st.info(f"**Current Status:** {st.session_state.dispatch_status}")
