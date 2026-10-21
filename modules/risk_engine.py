"""
=============================================================================
GEOGUARD AI — SATELLITE-POWERED TERRAIN RISK & EARLY WARNING PLATFORM
Module: modules/risk_engine.py
Purpose: 4-Factor Geotechnical Landslide Risk Calculation & Classification Engine
=============================================================================
COMPETITION: Smart India Hackathon (SIH)
CORRIDOR: NH-58 Himalayan Highway (Rishikesh–Devprayag–Joshimath)

THE 4 SENSORS EVALUATED:
1. Soil Moisture Sensor: Volumetric Water Content (% VWC) & saturation detection
2. Temperature Sensor: Ambient/soil temperature (°C) & freeze-thaw phase transition
3. Slope/Tilt Sensor: Angular displacement (°) & shear failure rate
4. Seismic Vibration Sensor: Peak Ground Acceleration (g) & micro-seismic shock

EXACT COMPOSITE FORMULA:
Overall Risk Score = (Soil Risk × 0.25)
                   + (Temperature Risk × 0.25)
                   + (Slope Risk × 0.25)
                   + (Vibration Risk × 0.25)

EXACT CLASSIFICATION RULES & BOUNDARIES:
- LOW RISK: Overall score < 40.0
  Display: "Low Risk - Conditions appear normal"
  Color: GREEN (#10B981)
- MODERATE RISK: Overall score >= 40.0 and <= 70.0
  Display: "Moderate Risk - Warning state active"
  Color: YELLOW (#F59E0B)
- CRITICAL RISK: Overall score > 70.0
  Display: "Critical Danger - Emergency response required"
  Color: RED (#EF4444)

EXACT BOUNDARY VERIFICATION:
  39.9 -> LOW
  40.0 -> MODERATE
  70.0 -> MODERATE
  70.1 -> CRITICAL

FAULT/STALE DATA POLICY:
If sensor readings are stale, invalid, or unavailable, display "UNKNOWN DATA"
or "SENSOR FAULT" instead of assigning LOW RISK. Communications failure must
NEVER be treated as proof of highway safety.
=============================================================================
"""

import plotly.graph_objects as go
from typing import Optional, Dict, Any, Tuple


# =============================================================================
# SECTION 1: Configurable Geotechnical Calibration Parameters
# =============================================================================
# Default demonstration thresholds (clearly labeled as unvalidated engineering defaults):
DEFAULT_CONFIG = {
    # Soil Moisture (% VWC)
    "soil_dry_max": 30.0,         # Normal baseline below 30% VWC
    "soil_elevated_max": 50.0,    # Elevated pore pressure (30-50% VWC)
    "soil_saturation_max": 70.0,  # High saturation (50-70% VWC)
    "soil_critical_min": 70.0,    # Critical liquefaction (>70% VWC)
    "soil_adc_dry": 1100,         # 12-bit ADC dry calibration baseline
    "soil_adc_wet": 3700,         # 12-bit ADC water saturated baseline

    # Temperature (°C)
    "temp_freeze_thaw_low": -4.0, # Lower bound of peak freeze-thaw danger
    "temp_freeze_thaw_high": 4.0, # Upper bound of peak freeze-thaw danger
    "temp_optimal_low": 12.0,     # Normal baseline minimum
    "temp_optimal_high": 24.0,    # Normal baseline maximum
    "temp_rapid_melt": 28.0,      # Glacial/snowpack rapid melt threshold

    # Slope Inclinometer Displacement (Degrees from calibrated baseline)
    "tilt_baseline_max": 0.8,     # Normal micro-creep
    "tilt_warning_max": 2.0,      # Moderate shear deformation
    "tilt_critical_min": 3.0,     # Structural slip plane failure

    # Ground Vibration / Acceleration (Peak Ground Acceleration in g)
    "vib_background_max": 0.05,   # Normal ambient seismic rumble
    "vib_elevated_max": 0.18,     # Heavy traffic / minor tremors
    "vib_shock_min": 0.35,        # Major shock / rockfall impact

    # Sensor Weights (25% each by default)
    "weight_soil": 0.25,
    "weight_temp": 0.25,
    "weight_slope": 0.25,
    "weight_vib": 0.25,

    # Classification Boundaries
    "threshold_low_max": 39.999,
    "threshold_moderate_min": 40.0,
    "threshold_moderate_max": 70.0,
    "threshold_critical_min": 70.001
}


# =============================================================================
# SECTION 2: Piecewise Normalization Functions (0 to 100 Scale)
# =============================================================================

def normalize_soil_moisture_risk(
    soil_vwc: Optional[float],
    raw_adc: Optional[int] = None,
    cfg: Optional[Dict[str, Any]] = None
) -> Optional[float]:
    """
    Normalizes soil moisture into a 0–100 risk sub-score.
    Piecewise calibration:
    - 0% to 30% VWC (Normal): 0 to 35 points
    - 30% to 50% VWC (Elevated dampness): 35 to 55 points
    - 50% to 70% VWC (High saturation): 55 to 75 points
    - > 70% VWC (Critical saturation / liquefaction): 75 to 100 points
    """
    c = cfg or DEFAULT_CONFIG

    # Optional hardware conversion layer: if ADC is provided instead of % VWC
    if soil_vwc is None and raw_adc is not None:
        adc_dry = c["soil_adc_dry"]
        adc_wet = c["soil_adc_wet"]
        span = max(1.0, float(adc_wet - adc_dry))
        soil_vwc = max(0.0, min(100.0, ((float(raw_adc) - adc_dry) / span) * 100.0))

    if soil_vwc is None:
        return None

    val = max(0.0, min(100.0, float(soil_vwc)))

    dry_max = c["soil_dry_max"]
    elev_max = c["soil_elevated_max"]
    sat_max = c["soil_saturation_max"]

    if val <= dry_max:
        score = (val / dry_max) * 35.0
    elif val <= elev_max:
        score = 35.0 + ((val - dry_max) / (elev_max - dry_max)) * 20.0
    elif val <= sat_max:
        score = 55.0 + ((val - elev_max) / (sat_max - elev_max)) * 20.0
    else:
        score = 75.0 + ((val - sat_max) / (100.0 - sat_max)) * 25.0

    return round(max(0.0, min(100.0, score)), 1)


def normalize_temperature_risk(
    temp_c: Optional[float],
    prev_temp_c: Optional[float] = None,
    cfg: Optional[Dict[str, Any]] = None
) -> Optional[float]:
    """
    Normalizes temperature into a 0–100 risk sub-score.
    Himalayan geotechnical engineering basis:
    - Peak hazard: Freeze-thaw cycling (-4°C to +4°C). Ice expands ~9% in bedrock
      fissures, creating catastrophic wedge forces that trigger rock avalanches.
    - Stable mild temperatures (12°C to 24°C): Minimal risk (5 to 25 points).
    - Rapid heating (> 28°C): Glacial snowpack runoff hazard (45 to 70 points).
    - Thermal gradients: Sharp drop or rise increases instability.
    """
    c = cfg or DEFAULT_CONFIG
    if temp_c is None:
        return None

    val = float(temp_c)
    ft_low = c["temp_freeze_thaw_low"]
    ft_high = c["temp_freeze_thaw_high"]
    opt_low = c["temp_optimal_low"]
    opt_high = c["temp_optimal_high"]

    # 1. Base thermal risk
    if ft_low <= val <= ft_high:
        # Distance from 0°C: closer to 0°C = highest ice/water phase transition stress
        proximity_to_zero = 4.0 - abs(val)
        score = 65.0 + (proximity_to_zero / 4.0) * 20.0  # 65 to 85 pts
    elif val < ft_low:
        # Deep continuous frost wedging
        score = min(75.0, 50.0 + abs(val - ft_low) * 2.5)
    elif val > c["temp_rapid_melt"]:
        # Rapid snowpack/permafrost melt runoff
        score = min(75.0, 45.0 + (val - c["temp_rapid_melt"]) * 3.5)
    elif opt_low <= val <= opt_high:
        # Optimal stable ambient range
        score = 5.0 + (abs(val - 18.0) / 6.0) * 15.0
    else:
        # Intermediate transitional temps (4°C to 12°C or 24°C to 28°C)
        if val < opt_low:
            score = 30.0 + ((opt_low - val) / (opt_low - ft_high)) * 25.0
        else:
            score = 25.0 + ((val - opt_high) / (c["temp_rapid_melt"] - opt_high)) * 20.0

    # 2. Thermal gradient acceleration (rapid temperature shift)
    if prev_temp_c is not None:
        delta = abs(val - float(prev_temp_c))
        if delta > 3.0:
            score += min(15.0, delta * 2.5)

    return round(max(0.0, min(100.0, score)), 1)


def normalize_slope_tilt_risk(
    tilt_deg: Optional[float],
    tilt_rate_deg_h: float = 0.0,
    cfg: Optional[Dict[str, Any]] = None
) -> Optional[float]:
    """
    Normalizes slope inclinometer angular displacement into a 0–100 risk sub-score.
    Measures deviation from baseline slope angle:
    - < 0.8° (Normal micro-creep): 0 to 35 points
    - 0.8° to 2.0° (Moderate shear strain): 35 to 65 points
    - 2.0° to 3.0° (Elevated slip displacement): 65 to 80 points
    - > 3.0° (Acute structural shear plane failure): 80 to 100 points
    - Rate of angular displacement adds dynamic acceleration penalty.
    """
    c = cfg or DEFAULT_CONFIG
    if tilt_deg is None:
        return None

    disp = abs(float(tilt_deg))
    base_max = c["tilt_baseline_max"]
    warn_max = c["tilt_warning_max"]
    crit_min = c["tilt_critical_min"]

    if disp <= base_max:
        base = (disp / base_max) * 35.0
    elif disp <= warn_max:
        base = 35.0 + ((disp - base_max) / (warn_max - base_max)) * 30.0
    elif disp <= crit_min:
        base = 65.0 + ((disp - warn_max) / (crit_min - warn_max)) * 15.0
    else:
        base = 80.0 + ((min(6.0, disp) - crit_min) / (6.0 - crit_min)) * 20.0

    # Dynamic displacement rate factor
    rate = abs(float(tilt_rate_deg_h)) if tilt_rate_deg_h else 0.0
    rate_boost = min(20.0, rate * 30.0)

    return round(max(0.0, min(100.0, base + rate_boost)), 1)


def normalize_vibration_risk(
    vib_pga: Optional[float],
    vib_detected: bool = False,
    cfg: Optional[Dict[str, Any]] = None
) -> Optional[float]:
    """
    Normalizes seismic vibration / Peak Ground Acceleration (PGA in g) into 0–100.
    - < 0.05g (Normal background microseisms): 0 to 20 points
    - 0.05g to 0.18g (Elevated road traffic / low tremor): 20 to 50 points
    - 0.18g to 0.35g (Strong ground motion / active rockfall): 50 to 70 points
    - > 0.35g (Acute seismic shock / severe ground rupture): 70 to 100 points
    """
    c = cfg or DEFAULT_CONFIG
    pga = abs(float(vib_pga)) if vib_pga is not None else 0.0

    bg_max = c["vib_background_max"]
    elev_max = c["vib_elevated_max"]
    shock_min = c["vib_shock_min"]

    if pga <= bg_max and not vib_detected:
        base = (pga / bg_max) * 20.0
    elif pga <= elev_max:
        base = 20.0 + ((pga - bg_max) / (elev_max - bg_max)) * 30.0
    elif pga <= shock_min:
        base = 50.0 + ((pga - elev_max) / (shock_min - elev_max)) * 20.0
    else:
        base = 70.0 + ((min(2.0, pga) - shock_min) / (2.0 - shock_min)) * 30.0

    if vib_detected and base < 40.0:
        base = 40.0

    return round(max(0.0, min(100.0, base)), 1)


# =============================================================================
# SECTION 3: 4-Factor Composite Landslide Risk Calculation
# =============================================================================

def calculate_four_sensor_risk(
    soil_moisture_pct: Optional[float] = None,
    temperature_c: Optional[float] = None,
    tilt_degrees: Optional[float] = None,
    vibration_pga: Optional[float] = None,
    vibration_detected: bool = False,
    tilt_rate_deg_h: float = 0.0,
    prev_temperature_c: Optional[float] = None,
    soil_raw_adc: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes the Composite Landslide Risk Index using the four normalized scores.
    
    EXACT FORMULA:
    Overall Risk Score = (Soil Risk × 0.25)
                       + (Temperature Risk × 0.25)
                       + (Slope Risk × 0.25)
                       + (Vibration Risk × 0.25)

    EXACT RISK CLASSIFICATION:
    - LOW: Overall score < 40.0 ("Low Risk - Conditions appear normal", GREEN #10B981)
    - MODERATE: Overall score >= 40.0 and <= 70.0 ("Moderate Risk - Warning state active", YELLOW #F59E0B)
    - CRITICAL: Overall score > 70.0 ("Critical Danger - Emergency response required", RED #EF4444)
    """
    cfg = config or DEFAULT_CONFIG

    # Configurable sensor weights (equal 25% distribution by default)
    w_soil = weights.get("soil", 0.25) if weights else 0.25
    w_temp = weights.get("temperature", 0.25) if weights else 0.25
    w_slope = weights.get("slope", 0.25) if weights else 0.25
    w_vib = weights.get("vibration", 0.25) if weights else 0.25

    # 1. Compute Individual Normalized Scores (0-100)
    soil_score = normalize_soil_moisture_risk(soil_moisture_pct, raw_adc=soil_raw_adc, cfg=cfg)
    temp_score = normalize_temperature_risk(temperature_c, prev_temp_c=prev_temperature_c, cfg=cfg)
    slope_score = normalize_slope_tilt_risk(tilt_degrees, tilt_rate_deg_h=tilt_rate_deg_h, cfg=cfg)
    vib_score = normalize_vibration_risk(vibration_pga, vib_detected=vibration_detected, cfg=cfg)

    subscores = {
        "soil": soil_score,
        "temperature": temp_score,
        "slope": slope_score,
        "vibration": vib_score
    }

    # 2. Check Data Completeness & Telemetry Integrity
    missing_sensors = [name for name, score in subscores.items() if score is None]
    is_valid = (len(missing_sensors) == 0)

    # 3. Critical Safety Policy: Missing / Invalid Telemetry
    if not is_valid:
        data_quality = "FAULT" if len(missing_sensors) >= 3 else "DEGRADED"
        msg = f"Sensor Disconnection / Fault: Missing {', '.join(missing_sensors)}. Safety cannot be certified."
        clean_scores = {k: (v if v is not None else 0.0) for k, v in subscores.items()}
        return {
            "overall_risk_score": 0.0,
            "risk_score": 0.0,
            "risk_level": "UNKNOWN DATA",
            "status_color": "#94A3B8",
            "status_message": msg,
            "recommended_action": msg,
            "is_valid": False,
            "is_complete": False,
            "data_quality": data_quality,
            "sensor_scores": clean_scores,
            "breakdown": clean_scores,
            "factors": [f"Missing {', '.join(missing_sensors)} readings"],
            "missing_sensors": missing_sensors,
            "immediate_warning": False,
            "immediate_triggers": []
        }

    # 4. Composite Formula: Weighted Sum of Sub-scores
    overall_score = round(
        (soil_score * w_soil) +
        (temp_score * w_temp) +
        (slope_score * w_slope) +
        (vib_score * w_vib),
        1
    )
    overall_score = max(0.0, min(100.0, overall_score))

    # 5. Exact Classification Rule
    # 39.9 -> LOW
    # 40.0 -> MODERATE
    # 70.0 -> MODERATE
    # 70.1 -> CRITICAL
    if overall_score < 40.0:
        risk_level = "LOW"
        status_color = "#10B981"  # GREEN
        status_message = "Low Risk - Conditions appear normal"
    elif 40.0 <= overall_score <= 70.0:
        risk_level = "MODERATE"
        status_color = "#F59E0B"  # YELLOW
        status_message = "Moderate Risk - Warning state active"
    else:  # overall_score > 70.0
        risk_level = "CRITICAL"
        status_color = "#EF4444"  # RED
        status_message = "Critical Danger - Emergency response required"

    # 6. Immediate Warnings (acute single-sensor hazard triggers)
    immediate_warning = False
    immediate_triggers = []

    if tilt_degrees is not None and abs(float(tilt_degrees)) >= 2.5:
        immediate_warning = True
        immediate_triggers.append(f"Acute slope displacement ({float(tilt_degrees):.2f}°)")
    if tilt_rate_deg_h is not None and abs(float(tilt_rate_deg_h)) >= 0.30:
        immediate_warning = True
        immediate_triggers.append(f"Accelerated slope creep rate (+{float(tilt_rate_deg_h):.2f}°/h)")
    if vibration_detected or (vibration_pga is not None and float(vibration_pga) >= 0.35):
        immediate_warning = True
        immediate_triggers.append(f"Abnormal seismic ground shock ({float(vibration_pga or 0.0):.2f}g PGA)")

    clean_scores = {
        "soil": soil_score,
        "temperature": temp_score,
        "slope": slope_score,
        "vibration": vib_score
    }
    factors_list = list(immediate_triggers)
    if not factors_list:
        if risk_level == "CRITICAL":
            factors_list.append("Multiple sub-sensors exhibiting critical landslide deformation")
        elif risk_level == "MODERATE":
            factors_list.append("Elevated sensor measurements in warning state")
        else:
            factors_list.append("All 4 geotechnical sensors nominal")

    return {
        "overall_risk_score": overall_score,
        "risk_score": overall_score,
        "risk_level": risk_level,
        "status_color": status_color,
        "status_message": status_message,
        "recommended_action": status_message,
        "is_valid": True,
        "is_complete": True,
        "data_quality": "OPTIMAL",
        "sensor_scores": clean_scores,
        "breakdown": clean_scores,
        "factors": factors_list,
        "weights": {
            "soil": w_soil,
            "temperature": w_temp,
            "slope": w_slope,
            "vibration": w_vib
        },
        "missing_sensors": [],
        "immediate_warning": immediate_warning,
        "immediate_triggers": immediate_triggers
    }


# =============================================================================
# SECTION 4: Plotly Circular Gauge Indicator
# =============================================================================

def build_four_sensor_risk_gauge(
    risk_score: float,
    risk_level: str,
    status_color: str,
    height: int = 270
) -> go.Figure:
    """
    Renders an animated, calibrated circular gauge showing the Composite Landslide Risk Index.
    Configured with the exact 3 domain bands:
    - 0 to 40%: LOW RISK (Green)
    - 40 to 70%: MODERATE RISK (Yellow)
    - 70 to 100%: CRITICAL RISK (Red)
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=risk_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={
            'text': (
                f"<b>COMPOSITE LANDSLIDE RISK</b><br>"
                f"<span style='font-size:12px; font-weight:600; color:{status_color};'>● {risk_level}</span>"
            ),
            'font': {'size': 13, 'family': 'Inter, sans-serif', 'color': '#F1F5F9'}
        },
        number={'suffix': "%", 'font': {'size': 36, 'family': 'JetBrains Mono, monospace', 'color': status_color}},
        gauge={
            'axis': {
                'range': [0, 100],
                'tickwidth': 1,
                'tickcolor': "#334155",
                'tickfont': {'color': '#94A3B8', 'size': 10},
                'tickvals': [0, 20, 40, 60, 70, 80, 100]
            },
            'bar': {'color': status_color, 'thickness': 0.28},
            'bgcolor': "rgba(15, 23, 42, 0.9)",
            'borderwidth': 1,
            'bordercolor': "#334155",
            'steps': [
                {'range': [0, 40], 'color': 'rgba(16, 185, 129, 0.18)'},   # Low (Green)
                {'range': [40, 70], 'color': 'rgba(245, 158, 11, 0.18)'},  # Moderate (Yellow)
                {'range': [70, 100], 'color': 'rgba(239, 68, 68, 0.24)'}  # Critical (Red)
            ],
            'threshold': {
                'line': {'color': "#EF4444", 'width': 3},
                'thickness': 0.85,
                'value': 70.0
            }
        }
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=18, r=18, t=45, b=10),
        height=height
    )
    return fig


# Backward compatibility alias
calculate_risk = calculate_four_sensor_risk
build_risk_gauge = build_four_sensor_risk_gauge
