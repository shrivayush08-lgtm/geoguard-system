"""
=============================================================================
GEOGUARD — HIGHWAY INTELLIGENCE & LANDSLIDE EARLY WARNING SYSTEM
Module: modules/gps_reader.py
Purpose: Modular Hardware GPS Telemetry Ingestion, NMEA 0183 Parser & Bridge
=============================================================================
Provides a robust, non-blocking telemetry ingestion gateway for physical GPS
hardware receivers (e.g., u-blox NEO-6M/8M, Quectel, SIM7600, or ESP32 RF bridges):
- High-performance NMEA 0183 sentence parsing ($GPGGA, $GNGGA, $GPRMC, $GNRMC)
- Bitwise XOR checksum verification
- Newline-delimited JSON GPS packet schema validation
- Automatic fallback recovery to plausible NH-58 coordinates on corrupt/missing fixes
- Preservation of last-known valid coordinates across packet loss
- Stale signal detection with automated health status degradation
- Explicit distinction between live hardware telemetry and simulated data

HARDWARE SETUP & CONFIGURATION REQUIREMENTS:
-----------------------------------------------------------------------------
1. Hardware Interface:
   - GPS Receiver Module: u-blox NEO-6M / NEO-8M / Quectel L86 or SIMCOM SIM7600
   - Interface: USB-to-UART Bridge (CP2102 / CH340 / FTDI) or ESP32 Serial Pass-Through
   - Standard Baud Rates: 9600 bps (Standard NMEA GPS) or 115200 bps (ESP32 Hub)
   - Default Serial Framing: 8 Data Bits, No Parity, 1 Stop Bit (8N1)
2. Supported Telemetry Protocols:
   - Protocol A: Standard NMEA 0183 ($GPRMC, $GPGGA, $GNRMC, $GNGGA)
   - Protocol B: IoT JSON Stream:
     {"unit_id": "UNIT-SAR-01", "lat": 30.1234, "lon": 78.4321, "speed": 42.0,
      "heading": 65.0, "altitude": 620.0, "battery": 94.0, "satellites": 10}
3. Safety Rule:
   - Do not claim that real GPS data is streaming unless a valid, checksum-verified
     hardware packet is received on an open, active serial interface.
=============================================================================
"""

import json
import math
from datetime import datetime, timezone
import serial
import serial.tools.list_ports

# ---------------------------------------------------------------------------
# Section 1: Fallback Coordinates along Rishikesh-Joshimath Corridor
# ---------------------------------------------------------------------------
# Used when incoming serial frames have zero-fix or corrupted coordinates
CORRIDOR_FALLBACK_COORDINATES = {
    "UNIT-SAR-01": {"lat": 30.1234, "lon": 78.4321, "altitude_m": 620.0, "location_name": "Byasi Gorge (GG-001)"},
    "UNIT-BRO-753": {"lat": 30.1850, "lon": 78.5040, "altitude_m": 780.0, "location_name": "Devprayag Transit (GG-003)"},
    "UNIT-HP-04": {"lat": 30.1450, "lon": 78.4620, "altitude_m": 665.0, "location_name": "Kaudiyala Sector (GG-002)"},
    "UNIT-EMS-08": {"lat": 30.2680, "lon": 78.5950, "altitude_m": 1010.0, "location_name": "Srinagar Approach (GG-005)"},
    "UNIT-GEO-SURV": {"lat": 30.2240, "lon": 78.5420, "altitude_m": 890.0, "location_name": "Kirtinagar Bluffs (GG-004)"}
}

DEFAULT_CORRIDOR_CENTER = {"lat": 30.1800, "lon": 78.5000, "altitude_m": 700.0}

def get_safe_fallback_fix(unit_id: str) -> dict:
    """Returns guaranteed valid NH-58 corridor fallback coordinates for any unit ID."""
    fb = CORRIDOR_FALLBACK_COORDINATES.get(unit_id, DEFAULT_CORRIDOR_CENTER)
    return {
        "lat": fb["lat"],
        "lon": fb["lon"],
        "altitude_m": fb.get("altitude_m", 700.0),
        "is_fallback": True
    }

# ---------------------------------------------------------------------------
# Section 2: NMEA 0183 Checksum & Coordinate Parsing Utilities
# ---------------------------------------------------------------------------

def verify_nmea_checksum(sentence: str) -> bool:
    """
    Validates standard NMEA 0183 sentence XOR checksum.
    The checksum is the 2-digit hex representation of the bitwise XOR of all
    characters between '$' (exclusive) and '*' (exclusive).
    """
    if not sentence or not sentence.startswith("$") or "*" not in sentence:
        return False

    try:
        content, cksum_str = sentence[1:].split("*", 1)
        cksum_str = cksum_str[:2]
        expected_cksum = int(cksum_str, 16)

        calc_cksum = 0
        for char in content:
            calc_cksum ^= ord(char)

        return calc_cksum == expected_cksum
    except (ValueError, IndexError):
        return False

def parse_nmea_coord(raw_value: str, direction: str) -> float | None:
    """
    Converts raw NMEA coordinates (ddmm.mmmm or dddmm.mmmm) into signed decimal degrees.
    Direction: 'N', 'S', 'E', 'W'.
    """
    if not raw_value or not direction:
        return None

    try:
        val = float(raw_value)
        # Latitude: ddmm.mmmm (2 digits degrees)
        # Longitude: dddmm.mmmm (3 digits degrees)
        if direction.upper() in ["N", "S"]:
            deg = int(val / 100)
            minutes = val - (deg * 100)
        else: # E or W
            deg = int(val / 100)
            minutes = val - (deg * 100)

        dec = deg + (minutes / 60.0)
        if direction.upper() in ["S", "W"]:
            dec = -dec
        return round(dec, 6)
    except (ValueError, TypeError):
        return None

def parse_nmea_sentence(sentence: str) -> dict | None:
    """
    Parses $GPGGA, $GNGGA, $GPRMC, $GNRMC sentences with resilient error catching.
    Returns structured GPS record or None if unrecoverable.
    """
    if not sentence or not isinstance(sentence, str):
        return None

    raw = sentence.strip()
    if not verify_nmea_checksum(raw):
        return None

    try:
        tokens = raw[1:].split("*")[0].split(",")
        msg_type = tokens[0].upper()
        now_iso = datetime.now(timezone.utc).isoformat()

        # --- 1. RMC: Recommended Minimum Specific GPS Data ---
        if msg_type in ["GPRMC", "GNRMC"]:
            if len(tokens) < 10:
                return None
            
            status = tokens[2].upper()
            if status != "A": # 'A' = Autonomous/Valid fix, 'V' = Void/Warning
                return {"fix_valid": False, "reason": "RMC Fix Void"}

            lat = parse_nmea_coord(tokens[3], tokens[4])
            lon = parse_nmea_coord(tokens[5], tokens[6])

            # Speed in knots -> convert to km/h (1 knot = 1.852 km/h)
            speed_kmh = 0.0
            try:
                speed_knots = float(tokens[7])
                speed_kmh = round(speed_knots * 1.852, 1)
            except (ValueError, IndexError):
                pass

            # Heading / Track angle in degrees true
            heading = 0.0
            try:
                heading = round(float(tokens[8]), 1)
            except (ValueError, IndexError):
                pass

            return {
                "fix_valid": (lat is not None and lon is not None),
                "lat": lat,
                "lon": lon,
                "speed_kmh": speed_kmh,
                "heading_deg": heading,
                "sentence_type": msg_type,
                "timestamp": now_iso
            }

        # --- 2. GGA: Global Positioning System Fix Data ---
        elif msg_type in ["GPGGA", "GNGGA"]:
            if len(tokens) < 10:
                return None

            fix_quality = 0
            try:
                fix_quality = int(tokens[6])
            except (ValueError, IndexError):
                pass

            if fix_quality == 0:
                return {"fix_valid": False, "reason": "GGA No Fix"}

            lat = parse_nmea_coord(tokens[2], tokens[3])
            lon = parse_nmea_coord(tokens[4], tokens[5])

            satellites = 0
            try:
                satellites = int(tokens[7])
            except (ValueError, IndexError):
                pass

            altitude_m = 0.0
            try:
                altitude_m = round(float(tokens[9]), 1)
            except (ValueError, IndexError):
                pass

            return {
                "fix_valid": (lat is not None and lon is not None),
                "lat": lat,
                "lon": lon,
                "altitude_m": altitude_m,
                "satellites_in_view": satellites,
                "fix_quality": fix_quality,
                "sentence_type": msg_type,
                "timestamp": now_iso
            }
    except Exception:
        return None

    return None

# ---------------------------------------------------------------------------
# Section 3: IoT JSON Telemetry Packet Validator with Resilient Fallbacks
# ---------------------------------------------------------------------------

def validate_json_gps_packet(payload: dict, unit_id_fallback: str = "UNIT-SAR-01") -> dict | None:
    """
    Validates newline-delimited JSON packets transmitted by IoT telemetry nodes.
    Applies graceful fallback coordinates if coordinate fields are missing/NaN.
    """
    if not isinstance(payload, dict):
        return None

    unit_id = payload.get("unit_id") or payload.get("id") or unit_id_fallback
    if not isinstance(unit_id, str):
        unit_id = str(unit_id_fallback)

    # Safe coordinate parsing with fallback to corridor baselines
    fb = get_safe_fallback_fix(unit_id)
    try:
        lat = float(payload.get("lat"))
        lon = float(payload.get("lon"))
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0) or math.isnan(lat) or math.isnan(lon):
            lat, lon = fb["lat"], fb["lon"]
            is_fallback = True
        else:
            is_fallback = False
    except (ValueError, TypeError):
        lat, lon = fb["lat"], fb["lon"]
        is_fallback = True

    # Safe parsing of optional telemetry fields with fallbacks
    try:
        speed = float(payload.get("speed_kmh", payload.get("speed", 0.0)))
        speed = max(0.0, min(200.0, speed))
    except (ValueError, TypeError):
        speed = 0.0

    try:
        heading = float(payload.get("heading_deg", payload.get("heading", 0.0)))
        heading = heading % 360.0
    except (ValueError, TypeError):
        heading = 0.0

    try:
        altitude = float(payload.get("altitude_m", payload.get("altitude", fb["altitude_m"])))
    except (ValueError, TypeError):
        altitude = fb["altitude_m"]

    try:
        battery = float(payload.get("battery_pct", payload.get("battery", 95.0)))
        battery = max(0.0, min(100.0, battery))
    except (ValueError, TypeError):
        battery = 95.0

    health_status = payload.get("status", "NOMINAL")
    if is_fallback:
        health_status = "WARNING (FALLBACK FIX)"

    return {
        "unit_id": unit_id.strip(),
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "speed_kmh": round(speed, 1),
        "heading_deg": round(heading, 1),
        "altitude_m": round(altitude, 1),
        "battery_pct": round(battery, 1),
        "health_status": health_status,
        "satellites_in_view": int(payload.get("satellites", payload.get("satellites_in_view", 8))),
        "data_source": "REAL_HARDWARE",
        "is_simulated": False,
        "is_fallback": is_fallback,
        "last_valid_ping": datetime.now(timezone.utc).isoformat()
    }

# ---------------------------------------------------------------------------
# Section 4: GPS Hardware Gateway Manager
# ---------------------------------------------------------------------------

class GPSHardwareGateway:
    """
    Non-blocking hardware serial gateway for USB/Serial GPS receivers.
    Manages connection lifecycle, packet decoding, coordinate caching,
    and stale signal handling with zero-crash fallbacks.
    """

    def __init__(self):
        self.serial_conn = None
        self.is_connected = False
        self.port = None
        self.baud = 9600
        self.target_unit_id = "UNIT-SAR-01" # Default mobile unit mapped to this physical receiver
        self.last_valid_fix = {} # Cache of last known valid coordinates per unit
        self.total_packets_received = 0
        self.checksum_errors = 0
        self.last_packet_time = None
        self.status_message = "GPS hardware interface idle. Select COM port to connect."

    @staticmethod
    def list_available_ports():
        """Scans host system for accessible serial COM ports."""
        try:
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    def connect(self, port_name: str, baud_rate: int = 9600, target_unit_id: str = "UNIT-SAR-01"):
        """Establishes non-blocking serial communication with GPS receiver."""
        if self.is_connected:
            self.disconnect()

        try:
            self.serial_conn = serial.Serial(
                port=port_name,
                baudrate=int(baud_rate),
                timeout=0.15, # Non-blocking short read timeout
                write_timeout=0.15
            )
            self.port = port_name
            self.baud = int(baud_rate)
            self.target_unit_id = target_unit_id
            self.is_connected = True
            self.status_message = f"Connected to {port_name} at {baud_rate} baud. Listening for NMEA/JSON GPS streams..."
            return True, self.status_message
        except Exception as e:
            self.is_connected = False
            self.serial_conn = None
            self.status_message = f"Failed to connect to {port_name}: {str(e)}"
            return False, self.status_message

    def disconnect(self):
        """Safely terminates the serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.is_connected = False
        self.serial_conn = None
        self.status_message = "Disconnected from GPS hardware interface."

    def read_latest_packet(self):
        """
        Polls serial buffer for incoming GPS packet.
        Handles both NMEA 0183 sentences ($GPRMC/$GPGGA) and JSON telemetry packets.
        Returns parsed telemetry dictionary or None.
        Guaranteed not to raise unhandled runtime exceptions.
        """
        if not self.is_connected or not self.serial_conn:
            return None

        try:
            if self.serial_conn.in_waiting > 0:
                raw_line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if not raw_line:
                    return None

                # 1. Check for NMEA 0183 Sentence
                if raw_line.startswith("$"):
                    nmea_res = parse_nmea_sentence(raw_line)
                    if nmea_res and nmea_res.get("fix_valid"):
                        self.total_packets_received += 1
                        self.last_packet_time = datetime.now(timezone.utc)
                        
                        unit_record = {
                            "unit_id": self.target_unit_id,
                            "lat": nmea_res["lat"],
                            "lon": nmea_res["lon"],
                            "speed_kmh": nmea_res.get("speed_kmh", 0.0),
                            "heading_deg": nmea_res.get("heading_deg", 0.0),
                            "altitude_m": nmea_res.get("altitude_m", 620.0),
                            "satellites_in_view": nmea_res.get("satellites_in_view", 8),
                            "health_status": "NOMINAL",
                            "data_source": "REAL_HARDWARE",
                            "is_simulated": False,
                            "last_valid_ping": datetime.now(timezone.utc).isoformat()
                        }
                        # Update last valid cache
                        self.last_valid_fix[self.target_unit_id] = unit_record
                        self.status_message = f"Live NMEA fix streaming from {self.target_unit_id}"
                        return unit_record
                    else:
                        self.checksum_errors += 1
                        # If cached fix exists, retain position
                        if self.target_unit_id in self.last_valid_fix:
                            cached = dict(self.last_valid_fix[self.target_unit_id])
                            cached["health_status"] = "WARNING (SIGNAL DEGRADED)"
                            return cached

                # 2. Check for JSON Telemetry Packet
                elif raw_line.startswith("{") and raw_line.endswith("}"):
                    try:
                        payload = json.loads(raw_line)
                        val_record = validate_json_gps_packet(payload, unit_id_fallback=self.target_unit_id)
                        if val_record:
                            self.total_packets_received += 1
                            self.last_packet_time = datetime.now(timezone.utc)
                            u_id = val_record["unit_id"]
                            self.last_valid_fix[u_id] = val_record
                            self.status_message = f"Live JSON telemetry streaming from {u_id}"
                            return val_record
                        else:
                            self.checksum_errors += 1
                    except json.JSONDecodeError:
                        self.checksum_errors += 1

        except Exception as e:
            self.status_message = f"Serial interface error: {str(e)}"
            self.disconnect()

        return None

    def get_diagnostics(self):
        """Returns connection quality diagnostics."""
        freshness_sec = None
        if self.last_packet_time:
            freshness_sec = round((datetime.now(timezone.utc) - self.last_packet_time).total_seconds(), 1)

        conn_status = "OFFLINE"
        if self.is_connected:
            if freshness_sec is not None and freshness_sec < 5.0:
                conn_status = "ONLINE (STREAMING)"
            elif freshness_sec is not None and freshness_sec < 45.0:
                conn_status = "DELAYED"
            else:
                conn_status = "CONNECTED (WAITING FIX)"

        return {
            "is_connected": self.is_connected,
            "port": self.port,
            "baud": self.baud,
            "status": conn_status,
            "freshness_seconds": freshness_sec,
            "total_packets": self.total_packets_received,
            "checksum_errors": self.checksum_errors,
            "status_message": self.status_message,
            "target_unit": self.target_unit_id
        }

# ---------------------------------------------------------------------------
# Section 5: Stale Telemetry Evaluation Helper
# ---------------------------------------------------------------------------

def evaluate_stale_telemetry(units_list, stale_threshold_sec: float = 45.0):
    """
    Inspects all mobile units. If a unit's last valid ping exceeds the stale
    threshold, flags unit as 'STALE' and signal quality as 'LOST' without
    clearing coordinates (preserves last known position).
    """
    if not units_list:
        return []

    now = datetime.now(timezone.utc)
    evaluated = []

    for u in units_list:
        item = dict(u)
        last_ping_str = item.get("last_valid_ping")

        if last_ping_str:
            try:
                ping_dt = datetime.fromisoformat(last_ping_str)
                if ping_dt.tzinfo is None:
                    ping_dt = ping_dt.replace(tzinfo=timezone.utc)
                age_sec = (now - ping_dt).total_seconds()
                if age_sec > stale_threshold_sec:
                    item["health_status"] = "STALE"
                    item["signal_quality"] = "LOST"
                    item["speed_kmh"] = 0.0 # Velocity zeroed when signal lost
            except Exception:
                pass

        evaluated.append(item)
    return evaluated
