"""
=============================================================================
GEOGUARD AI — OFF-GRID HIGHWAY LANDSLIDE EARLY WARNING & INTERLOCK SYSTEM
Module: modules/interlock.py
Purpose: Highway Interlock Simulation State Machine & Automated Dispatch Logger
=============================================================================
Provides:
- Simulated physical actuator interlocks:
  * Highway Boom Barrier: OPEN / CLOSED / UNKNOWN
  * Upstream Traffic Signals: GREEN / YELLOW / RED / UNKNOWN
  * Emergency Early Warning: INACTIVE / ACTIVE
  * Sensor System Health: ONLINE / DEGRADED / OFFLINE
  * Dispatch Status: PENDING / LOGGED / ACKNOWLEDGED
- Automated Dispatch Incident Logging for:
  * NH-58 Traffic Police (Devprayag & Byasi Checkpoints)
  * District Emergency Control Room (Tehri Garhwal & Srinagar)
  * Highway Emergency Response Team (SDRF / NDRF / BRO Task Force)
- Hysteresis and Recovery Confirmation (prevents premature recovery on momentary dip)
- CSV Export of local dispatch incident logs
=============================================================================
IMPORTANT SAFETY NOTICE:
Actuator actions are strictly SIMULATED for demonstration and control-room testing.
No physical signals or barrier commands are sent to external machinery without
certified hardware interlocks, watchdogs, and authorized operator authorization.
=============================================================================
"""

import json
from datetime import datetime, timezone
import pandas as pd


class HighwayInterlockSystem:
    """
    Simulated Highway Interlock State Machine and Automated Incident Dispatch Logger.
    Maintains actuator state, alert hysteresis, and incident audit trails.
    """

    def __init__(self, hysteresis_ticks_required: int = 3):
        self.barrier_state = "OPEN"           # OPEN, CLOSED, UNKNOWN
        self.traffic_signal = "GREEN"         # GREEN, YELLOW, RED, UNKNOWN
        self.emergency_state = "INACTIVE"     # INACTIVE, ACTIVE
        self.sensor_system = "ONLINE"         # ONLINE, DEGRADED, OFFLINE
        self.dispatch_status = "PENDING"      # PENDING, LOGGED, ACKNOWLEDGED
        
        self.active_incident_id = None
        self.active_incident = None
        self.last_emergency_timestamp = None
        
        # Hysteresis counter: requires consecutive safe ticks before recovering from emergency
        self.hysteresis_ticks_required = hysteresis_ticks_required
        self.consecutive_safe_ticks = 0
        
        # In-memory structured incident dispatch history
        self.dispatch_history = []
        self._incident_counter = 100

    def evaluate(
        self,
        composite_risk: float,
        is_valid_telemetry: bool,
        sensor_readings: dict,
        risk_subscores: dict,
        station_id: str = "GG-001",
        station_location: str = "NH-58 km 42.5 (Byasi Gorge Pass)",
        data_source: str = "SIMULATION"
    ):
        """
        Evaluates composite landslide risk score and manages simulated actuators:
        - Critical (> 70.0): Interlock trips -> Barrier CLOSED, Signals RED, Dispatch LOGGED.
        - Moderate (40.0 - 70.0): Warning state -> Barrier OPEN, Signals YELLOW.
        - Low (< 40.0): Normal state -> Barrier OPEN, Signals GREEN.
        - Invalid/Faulted: Failsafe caution -> Barrier OPEN/CAUTION, Signals YELLOW, OFFLINE.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Case 1: Telemetry Fault or Disconnection
        if not is_valid_telemetry:
            self.sensor_system = "OFFLINE"
            # Do not classify as safe! If previously in emergency, maintain interlock
            if self.emergency_state == "ACTIVE":
                self.barrier_state = "CLOSED"
                self.traffic_signal = "RED"
            else:
                self.barrier_state = "OPEN"
                self.traffic_signal = "YELLOW"
            return self.get_status_summary()

        # Telemetry is valid
        self.sensor_system = "ONLINE"

        # Case 2: Critical Landslide Danger (Score > 70.0)
        if composite_risk > 70.0:
            self.consecutive_safe_ticks = 0
            self.emergency_state = "ACTIVE"
            self.barrier_state = "CLOSED"
            self.traffic_signal = "RED"
            self.last_emergency_timestamp = now_str

            # Create incident dispatch log if not already logged for this emergency
            if self.active_incident_id is None:
                self._incident_counter += 1
                incident_id = f"INC-NH58-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{self._incident_counter:04d}"
                self.active_incident_id = incident_id
                self.dispatch_status = "LOGGED"

                reason = (
                    f"Composite Landslide Index breached critical threshold ({composite_risk:.1f}/100). "
                    f"Sub-factors: Soil {risk_subscores.get('soil', 0.0):.1f}%, "
                    f"Temp {risk_subscores.get('temperature', 0.0):.1f}%, "
                    f"Slope {risk_subscores.get('slope', 0.0):.1f}%, "
                    f"Vibration {risk_subscores.get('vibration', 0.0):.1f}%."
                )

                record = {
                    "incident_id": incident_id,
                    "timestamp": now_str,
                    "highway_corridor": "NH-58 Himalayan Highway (Rishikesh–Badrinath)",
                    "station_id": station_id,
                    "station_location": station_location,
                    "composite_risk_score": round(composite_risk, 1),
                    "risk_classification": "CRITICAL DANGER",
                    "soil_moisture_vwc": sensor_readings.get("soil_moisture_pct", 0.0),
                    "soil_risk_subscore": risk_subscores.get("soil", 0.0),
                    "temperature_c": sensor_readings.get("temperature_c", 0.0),
                    "temp_risk_subscore": risk_subscores.get("temperature", 0.0),
                    "tilt_angle_deg": sensor_readings.get("tilt_degrees", 0.0),
                    "slope_risk_subscore": risk_subscores.get("slope", 0.0),
                    "vibration_pga_g": sensor_readings.get("vibration_pga", 0.0),
                    "vibration_risk_subscore": risk_subscores.get("vibration", 0.0),
                    "sensor_data_validity": "VALID",
                    "detected_emergency_condition": reason,
                    "simulated_barrier_state": "CLOSED",
                    "simulated_traffic_signal": "RED",
                    "intended_recipients": (
                        "1. NH-58 Traffic Police (Devprayag & Byasi Intercept Units) | "
                        "2. District Control Room (Disaster Management Center Tehri) | "
                        "3. Highway Emergency Response Team (SDRF / BRO Task Force)"
                    ),
                    "recommended_actions": (
                        "Immediate traffic halt at Upstream Checkpoint (km 38) and Downstream Checkpoint (km 46). "
                        "Activate VMS warning signs: 'LANDSLIDE DANGER - ROAD CLOSED'. "
                        "Dispatch geotechnical assessment and earthmoving clearance units."
                    ),
                    "dispatch_status": "LOGGED",
                    "acknowledgment_status": "PENDING OPERATOR REVIEW",
                    "data_source": data_source,
                    "legal_disclaimer": "Locally generated simulation dispatch record. Physical actuation disabled."
                }

                self.active_incident = record
                self.dispatch_history.insert(0, record)

        # Case 3: Non-Critical Condition (Score <= 70.0)
        else:
            # If system was in active emergency, apply hysteresis confirmation
            if self.emergency_state == "ACTIVE":
                self.consecutive_safe_ticks += 1
                # Require consecutive safe ticks before releasing the interlock
                if self.consecutive_safe_ticks >= self.hysteresis_ticks_required:
                    self.emergency_state = "INACTIVE"
                    self.barrier_state = "OPEN"
                    self.traffic_signal = "YELLOW" if composite_risk >= 40.0 else "GREEN"
                    self.active_incident_id = None
                else:
                    # Maintain protective closure during confirmation buffer
                    self.barrier_state = "CLOSED"
                    self.traffic_signal = "RED"
            else:
                self.consecutive_safe_ticks = 0
                self.emergency_state = "INACTIVE"
                self.barrier_state = "OPEN"
                self.traffic_signal = "YELLOW" if composite_risk >= 40.0 else "GREEN"

        return self.get_status_summary()

    def acknowledge_active_incident(self, operator_name: str = "Authorized Highway Controller"):
        """Marks active dispatch incident as ACKNOWLEDGED with operator audit log."""
        if self.active_incident:
            self.active_incident["acknowledgment_status"] = f"ACKNOWLEDGED by {operator_name}"
            self.active_incident["dispatch_status"] = "ACKNOWLEDGED"
            self.dispatch_status = "ACKNOWLEDGED"
            return True
        return False

    def reset_interlock(self):
        """Forces manual reset of the interlock state machine back to nominal baseline."""
        self.emergency_state = "INACTIVE"
        self.barrier_state = "OPEN"
        self.traffic_signal = "GREEN"
        self.dispatch_status = "PENDING"
        self.consecutive_safe_ticks = 0
        self.active_incident_id = None
        self.active_incident = None

    def get_status_summary(self) -> dict:
        """Returns current simulated actuator states for dashboard rendering."""
        return {
            "barrier_state": self.barrier_state,
            "traffic_signal": self.traffic_signal,
            "emergency_response": self.emergency_state,
            "sensor_system": self.sensor_system,
            "dispatch_status": self.dispatch_status,
            "active_incident_id": self.active_incident_id,
            "last_emergency_timestamp": self.last_emergency_timestamp
        }

    def get_dispatch_history_df(self) -> pd.DataFrame:
        """Returns the complete incident dispatch history as a Pandas DataFrame."""
        if not self.dispatch_history:
            return pd.DataFrame(columns=[
                "incident_id", "timestamp", "station_id", "composite_risk_score",
                "risk_classification", "simulated_barrier_state", "simulated_traffic_signal",
                "dispatch_status", "acknowledgment_status"
            ])
        return pd.DataFrame(self.dispatch_history)

    def export_csv(self) -> str:
        """Exports the dispatch log history to CSV format."""
        df = self.get_dispatch_history_df()
        return df.to_csv(index=False)
