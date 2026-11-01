"""
=============================================================================
GEOGUARD AI — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Page: pages/highway_safety.py
Purpose: Highway Corridor Transit Management, Road Closures & Bypass Advisories
=============================================================================
Manages:
- Corridor runway schematic across 5 monitored sectors
- Roadway status (OPEN, UNDER OBSERVATION, RESTRICTED, CLOSED, REOPENED)
- Traffic speed advisory modifications & vehicle weight limits
- Alternative bypass route advisories (Chamba / New Tehri route)
=============================================================================
"""

import streamlit as st
from database.db import get_road_sections, update_road_section, get_alerts
from modules.ui import render_highway_linear_schematic, render_html


def render_highway_safety_page(enriched_stations):
    """Renders the highway safety and corridor closure management view."""
    st.markdown("<div class='hud-eyebrow'>HIGHWAY TRAFFIC SURVEILLANCE & CLOSURES</div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:0;'>Highway Safety & Road Closure Control</h2>", unsafe_allow_html=True)

    # 1. Fetch Highway Road Sections from Database
    sections_df = get_road_sections()

        # Automatically synchronize live sensor risk with highway sections
    station_risk_map = {
        str(stn["id"]): str(stn["risk_level"]).upper()
        for stn in enriched_stations
    }

    for _, section in sections_df.iterrows():
        section_id = section["section_id"]
        station_id = str(section["associated_station"])

        live_risk = station_risk_map.get(station_id)

        if live_risk not in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            continue

        existing_status = str(section["status"]).upper()
        existing_risk = str(section["risk_level"]).upper()

        # Critical risk automatically closes the road.
        # Lower risk never automatically reopens a closed road.
        updated_status = (
            "CLOSED" if live_risk == "CRITICAL"
            else existing_status
        )

        if updated_status != existing_status or live_risk != existing_risk:
            update_road_section(
                section_id,
                updated_status,
                live_risk,
                section["condition_notes"],
                updated_by="GeoGuard Automated Risk Monitor"
            )

    # Fetch updated database records
    sections_df = get_road_sections()

    if sections_df.empty:
        st.warning("No highway road sections registered in database.")
        return

    # 2. Highway Linear Corridor Strip Schematic
    render_highway_linear_schematic(sections_df)

    
    # 3. Overall Highway Status Summary
    st.markdown("### Highway Overview")

    status_counts = (
        sections_df["status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .value_counts()
    )

    total_sections = len(sections_df)
    open_sections = int(status_counts.get("OPEN", 0))
    observation_sections = int(status_counts.get("UNDER OBSERVATION", 0))
    restricted_sections = int(status_counts.get("RESTRICTED", 0))
    closed_sections = int(status_counts.get("CLOSED", 0))
    reopened_sections = int(status_counts.get("REOPENED", 0))

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("Total Sections", total_sections)
    c2.metric("🟢 Open", open_sections)
    c3.metric("🟡 Observation", observation_sections)
    c4.metric("🟠 Restricted", restricted_sections)
    c5.metric("🔴 Closed", closed_sections)
    c6.metric("🔵 Reopened", reopened_sections)

    st.markdown("---")


    # Critical Closure and Risk Alerts
    st.markdown("### 🚨 Critical Highway Alerts")

    alert_sections = sections_df[
        sections_df["status"].fillna("").astype(str).str.strip().str.upper().eq("CLOSED")
        | sections_df["risk_level"].fillna("").astype(str).str.strip().str.upper().eq("CRITICAL")
    ]

    if alert_sections.empty:
        st.success("No active closure or CRITICAL-risk sections detected.")
    else:
        for _, alert_sec in alert_sections.iterrows():
            alert_status = str(alert_sec["status"]).strip().upper()
            alert_risk = str(alert_sec["risk_level"]).strip().upper()

            reasons = []
            if alert_status == "CLOSED":
                reasons.append("ROAD CLOSED")
            if alert_risk == "CRITICAL":
                reasons.append("CRITICAL RISK")

            st.error(
                f"🚨 {alert_sec['section_id']} — {alert_sec['name']} | "
                f"Status: {alert_status} | Risk: {alert_risk} | "
                f"Alert: {' + '.join(reasons)}"
            )

    st.markdown("---")


    # 3. Checkpoint Search and Filters
    st.markdown("### Corridor Checkpoint Status")

    search_text = st.text_input(
        "Search checkpoint",
        placeholder="Enter section ID or road name..."
    )

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        selected_status = st.selectbox(
            "Filter by Status",
            ["ALL", "OPEN", "UNDER OBSERVATION", "RESTRICTED", "CLOSED", "REOPENED"]
        )

    with filter_col2:
        selected_risk = st.selectbox(
            "Filter by Risk",
            ["ALL", "LOW", "MODERATE", "HIGH", "CRITICAL"]
        )

    filtered_sections = sections_df.copy()

    if search_text.strip():
        search_mask = (
            filtered_sections["section_id"].astype(str).str.contains(
                search_text.strip(), case=False, na=False
            )
            | filtered_sections["name"].astype(str).str.contains(
                search_text.strip(), case=False, na=False
            )
        )
        filtered_sections = filtered_sections[search_mask]

    if selected_status != "ALL":
        filtered_sections = filtered_sections[
            filtered_sections["status"].astype(str).str.upper()
            == selected_status
        ]

    if selected_risk != "ALL":
        filtered_sections = filtered_sections[
            filtered_sections["risk_level"].astype(str).str.upper()
            == selected_risk
        ]

    st.caption(
        f"Showing {len(filtered_sections)} of {len(sections_df)} checkpoints"
    )

    # Fetch alerts for checkpoint status correlation
    active_alerts_df = get_alerts(limit=50)

    for _, sec in filtered_sections.iterrows():
        sec_id = sec["section_id"]
        status = sec["status"]
        risk_lvl = sec["risk_level"]
        assoc_stn_id = str(sec["associated_station"])

        # Sensor readings from enriched stations
        stn_match = next((s for s in (enriched_stations or []) if str(s.get("id")) == assoc_stn_id), None)
        sensor_info_html = ""
        if stn_match:
            soil = stn_match.get("soil_moisture_pct", "N/A")
            tilt = stn_match.get("tilt", "N/A")
            rain = stn_match.get("rainfall_intensity_mmh", "N/A")
            vib = "DETECTED 🔴" if stn_match.get("vib") else "STABLE 🟢"
            sensor_info_html = f"""
            <div style='font-size: 11px; color: #94A3B8; margin-top: 6px; background: rgba(255,255,255,0.03); padding: 5px 8px; border-radius: 4px;'>
                <b>Node Telemetry:</b> Soil: <b style='color:#F8FAFC;'>{soil}% VWC</b> • 
                Tilt: <b style='color:#F8FAFC;'>{tilt}°</b> • 
                Rain: <b style='color:#F8FAFC;'>{rain} mm/h</b> • 
                Seismic: <b style='color:#F8FAFC;'>{vib}</b>
            </div>
            """

        # Correlated active incident alert
        active_alert_html = ""
        if not active_alerts_df.empty:
            stn_alerts = active_alerts_df[
                (active_alerts_df["station_id"].astype(str) == assoc_stn_id) &
                (~active_alerts_df["status"].isin(["RESOLVED", "FALSE ALARM"]))
            ]
            if not stn_alerts.empty:
                top_alert = stn_alerts.iloc[0]
                active_alert_html = f"""
                <div style='font-size: 11px; color: #EF4444; margin-top: 5px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.25); padding: 4px 8px; border-radius: 4px;'>
                    ⚠️ <b>Active Incident #{top_alert['alert_id']} ({top_alert['risk_level']}):</b> {top_alert['reason']}
                </div>
                """

        # Closure warning information
        closure_notice_html = ""
        if status == "CLOSED":
            closure_notice_html = """
            <div style='font-size: 11px; color: #EF4444; font-weight: 600; margin-top: 5px; background: rgba(239,68,68,0.15); padding: 4px 8px; border-radius: 4px;'>
                ⛔ CORRIDOR TRAFFIC HALTED — Authorized clearance & inspection required prior to reopening.
            </div>
            """
        
        status_color_map = {
            "OPEN": "#10B981",
            "UNDER OBSERVATION": "#F59E0B",
            "RESTRICTED": "#F97316",
            "CLOSED": "#EF4444",
            "REOPENED": "#38BDF8"
        }
        color = status_color_map.get(status, "#94A3B8")

        with st.container():
            render_html(f"""
            <div style='background: #111827; border-left: 4px solid {color}; border-top: 1px solid #1F2937; border-right: 1px solid #1F2937; border-bottom: 1px solid #1F2937; border-radius: 6px; padding: 14px 18px; margin-bottom: 10px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <div>
                        <span style='font-size: 15px; font-weight: 600; color: #F8FAFC;'>{sec_id}: {sec['name']}</span>
                        <span class='font-mono' style='margin-left: 10px; font-size: 11px; color: #38BDF8;'>[Node: {sec['associated_station']}]</span>
                    </div>
                    <div style='background: rgba(16, 185, 129, 0.1); color: {color}; border: 1px solid {color}55; padding: 3px 10px; border-radius: 4px; font-family: "JetBrains Mono", monospace; font-size: 11px; font-weight: 600;'>
                        ● {status}
                    </div>
                </div>
                <div style='font-size: 12px; color: #94A3B8; margin-top: 5px;'>
                    Corridor Segment: {sec['corridor']} • Sector Risk Rating: <b style='color:{color};'>{risk_lvl}</b>
                </div>
                {sensor_info_html}
                {active_alert_html}
                {closure_notice_html}
                <div style='font-size: 13px; color: #E2E8F0; margin-top: 6px;'>
                    <b>Field Inspector Directive:</b> {sec['condition_notes']}
                </div>
                <div class='font-mono' style='font-size: 11px; color: #64748B; margin-top: 6px;'>
                    Modified: {sec['last_updated']} by {sec['updated_by']}
                </div>
            </div>
            """)

    st.markdown("<hr style='border:0; border-top:1px solid #1F2937; margin: 16px 0;'>", unsafe_allow_html=True)

    # 4. Authorized Operator Road Status Update Console
    st.markdown("### Sector Transit Modification Console")
    with st.form("road_status_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_sec_id = st.selectbox("Target Highway Section", sections_df["section_id"].tolist())
        with col2:
            new_status = st.selectbox(
                "Update Transit Status",
                ["OPEN", "UNDER OBSERVATION", "RESTRICTED", "CLOSED", "REOPENED"]
            )
        with col3:
            new_risk = st.selectbox(
                "Designated Risk Rating",
                ["LOW", "MODERATE", "HIGH", "CRITICAL"]
            )

        notes_input = st.text_input("Transit Restriction / Field Advisory Notes", value="Single-lane pilot clearance in effect. Heavy commercial vehicles diverted.")
        officer_input = st.text_input("Authorizing Officer Name & Badge ID", value="Inspector BRO Highway Command")

        clearance_completed = st.checkbox(
            "I confirm that landslide debris clearance and repair work are completed."
        )

        inspection_completed = st.checkbox(
            "I confirm that the highway safety inspection has been completed."
        )

        reopening_approved = st.checkbox(
            "I authorize reopening this highway section."
        )

        submit = st.form_submit_button("Broadcast Corridor Advisory", type="primary", use_container_width=True)
        if submit:
            selected_section = sections_df[
                sections_df["section_id"] == selected_sec_id
            ].iloc[0]

            current_status = str(selected_section["status"]).upper()
            station_id = str(selected_section["associated_station"])
            live_risk = station_risk_map.get(station_id)

            # Validate road reopening
            if new_status in ["OPEN", "REOPENED"] and current_status != new_status:

                if not officer_input.strip():
                    st.error("Authorized Officer name is required.")

                elif live_risk is None:
                    st.error("Live sensor risk unavailable. Reopening cannot be approved.")

                elif live_risk == "CRITICAL":
                    st.error("Reopening blocked: CRITICAL risk is still detected.")

                elif not clearance_completed:
                    st.error("Confirm that landslide clearance and repair work are completed.")

                elif not inspection_completed:
                    st.error("Confirm that highway safety inspection is completed.")

                elif not reopening_approved:
                    st.error("Authorized officer approval is required.")

                else:
                    update_road_section(
                        selected_sec_id,
                        new_status,
                        new_risk,
                        notes_input,
                        updated_by=officer_input
                    )
                    st.success(
                        f"Sector {selected_sec_id} approved for reopening."
                    )
                    st.rerun()

            else:
                update_road_section(
                    selected_sec_id,
                    new_status,
                    new_risk,
                    notes_input,
                    updated_by=officer_input
                )
                st.success(
                    f"Sector {selected_sec_id} updated to {new_status}."
                )
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Alternative Route & Detour Guide
    st.markdown("### Emergency Highway Bypass & Traffic Diversion Advisory")
    render_html("""
    <div style='background: #111827; border: 1px solid #1F2937; border-radius: 8px; padding: 18px;'>
        <div class='hud-eyebrow'>PRIMARY BYPASS CORRIDOR • NH-707A CHIKHALIDHAR ARTERIAL</div>
        <div style='font-size: 13px; color: #E2E8F0; line-height: 1.6; margin-top: 6px;'>
            In the event of closure at <b>SEC-01 (Byasi Mountain Pass)</b> or <b>SEC-02 (Kaudiyala Gorge)</b>, 
            divert northbound passenger and emergency logistics traffic from Rishikesh via <b>NH-707A (Rishikesh - Chamba - New Tehri - Kirtinagar)</b>.<br>
            • Estimated transit delta: <b style='color:#38BDF8;'>+45 minutes</b><br>
            • Maximum Gross Vehicle Weight (GVW): <b style='color:#10B981;'>24 Metric Tonnes</b><br>
            • Highway Patrol Clearance: <b>Open with 24/7 Police Checkpoints</b>
        </div>
    </div>
    """)
