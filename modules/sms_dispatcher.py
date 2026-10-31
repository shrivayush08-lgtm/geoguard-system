"""
=============================================================================
GEOGUARD AI — HIGHWAY LANDSLIDE EARLY WARNING & EMERGENCY DISPATCH
Module: modules/sms_dispatcher.py
Purpose: Multi-Channel SMS & Mobile Alert Dispatcher (Fast2SMS, Twilio, Webhook)
=============================================================================
"""

import requests
import json
import time
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional

# In-memory cooldown tracking: { recipient_number: last_dispatch_epoch }
_DISPATCH_COOLDOWN_MAP = {}
DEFAULT_COOLDOWN_SECONDS = 180  # 3 minutes cooldown between repeated SMS

def format_landslide_sms_message(station_id: str, tilt_deg: float, rain_mmh: float, soil_pct: float) -> str:
    """Formats an authentic Indian Government-style disaster alert text message (GSM 7-bit ASCII safe)."""
    return (
        f"[GOVT / NDMA / GEOGUARD EMERGENCY WARNING]\n"
        f"Critical Landslide Threat in Himalayan Corridor (Station {station_id}).\n"
        f"- Slope Tilt: {tilt_deg:.2f} deg (Shear Limit Exceeded)\n"
        f"- Rainfall: {rain_mmh:.1f} mm/h\n"
        f"- Soil Saturation: {soil_pct:.1f}%\n"
        f"DIRECTIVE: Halt uphill traffic immediately. Take emergency shelter."
    )

def send_fast2sms(api_key: str, mobile_number: str, message: str) -> Tuple[bool, str]:
    """
    Sends direct cellular SMS to an Indian mobile number via Fast2SMS gateway.
    Requires free API key from https://www.fast2sms.com
    """
    if not api_key or not mobile_number:
        return False, "Fast2SMS API key or mobile number is missing."
    
    clean_number = "".join(filter(str.isdigit, str(mobile_number)))
    if len(clean_number) > 10:
        clean_number = clean_number[-10:] # Extract last 10 digits
        
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        "authorization": api_key.strip(),
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "route": "q", # Quick SMS route
        "message": message[:160], # Standard 160-char SMS limit
        "language": "english",
        "flash": 0,
        "numbers": clean_number
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=8)
        data = response.json()
        if data.get("return") is True:
            return True, f"SMS successfully dispatched to +91 {clean_number} via Fast2SMS."
        else:
            err_msg = data.get("message", ["Unknown Fast2SMS error"])[0] if isinstance(data.get("message"), list) else str(data.get("message"))
            return False, f"Fast2SMS error: {err_msg}"
    except Exception as e:
        return False, f"SMS Gateway network error: {str(e)}"

def send_twilio_sms(account_sid: str, auth_token: str, from_number: str, to_number: str, message: str) -> Tuple[bool, str]:
    """Sends SMS via Twilio worldwide cellular gateway."""
    if not (account_sid and auth_token and from_number and to_number):
        return False, "Twilio configuration parameters missing."
        
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    auth = (account_sid.strip(), auth_token.strip())
    payload = {
        "From": from_number.strip(),
        "To": to_number.strip() if to_number.startswith("+") else f"+91{to_number.strip()}",
        "Body": message
    }
    
    try:
        response = requests.post(url, auth=auth, data=payload, timeout=8)
        if response.status_code in [200, 201]:
            return True, f"Twilio SMS dispatched to {payload['To']}."
        else:
            return False, f"Twilio HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"Twilio network error: {str(e)}"

def send_telegram_alert(bot_token: str, chat_id: str, message: str) -> Tuple[bool, str]:
    """Sends instant high-priority emergency message via Telegram Bot API."""
    if not (bot_token and chat_id):
        return False, "Telegram Bot Token or Chat ID missing."
        
    url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
    payload = {
        "chat_id": chat_id.strip(),
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload, timeout=8)
        if response.status_code == 200:
            return True, "Telegram emergency message sent successfully."
        else:
            return False, f"Telegram API error: {response.text}"
    except Exception as e:
        return False, f"Telegram network error: {str(e)}"

def check_and_dispatch_automatic_sms(
    sensor_dict: Dict[str, Any],
    mobile_number: str,
    fast2sms_key: str = "",
    telegram_token: str = "",
    telegram_chat_id: str = "",
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
) -> Tuple[bool, str]:
    """
    Evaluates sensor readings. If landslide or critical thresholds are breached,
    dispatches SMS/Alert if cooldown has elapsed.
    """
    if not sensor_dict:
        return False, "No live telemetry available."

    tilt = float(sensor_dict.get("tilt_degrees", 0.0))
    rain = float(sensor_dict.get("rain_intensity_mmh", sensor_dict.get("rain_intensity", 0.0)) or 0.0)
    soil = float(sensor_dict.get("soil_moisture_pct", 0.0))
    is_landslide = sensor_dict.get("landslide", False)

    # Physical Calibration: 60° mountain resting baseline
    # Acute shear failure occurs when tilt drops > 5° from 60° (tilt < 55.0°)
    is_tilt_slip = (tilt < 55.0)
    is_severe_tilt = (tilt < 50.0)
    is_water_saturated = (rain > 20.0 or soil > 55.0)

    is_critical = bool(is_landslide) or is_severe_tilt or (is_tilt_slip and is_water_saturated) or (rain > 35.0 and soil > 70.0)
    if not is_critical:
        return False, "Nominal conditions. No SMS trigger needed."

    now = time.time()
    last_sent = _DISPATCH_COOLDOWN_MAP.get(mobile_number, 0.0)
    if (now - last_sent) < cooldown_seconds:
        rem = int(cooldown_seconds - (now - last_sent))
        return False, f"Alert suppressed by cooldown ({rem}s remaining)."

    msg = format_landslide_sms_message(
        station_id=sensor_dict.get("station_id", "GG-001"),
        tilt_deg=tilt,
        rain_mmh=rain,
        soil_pct=soil
    )

    success = False
    details = []

    # Attempt Fast2SMS if key provided
    if fast2sms_key and mobile_number:
        ok, res = send_fast2sms(fast2sms_key, mobile_number, msg)
        details.append(res)
        if ok: success = True

    # Attempt Telegram if configured
    if telegram_token and telegram_chat_id:
        ok, res = send_telegram_alert(telegram_token, telegram_chat_id, msg)
        details.append(res)
        if ok: success = True

    if success:
        _DISPATCH_COOLDOWN_MAP[mobile_number] = now
        return True, " | ".join(details)
    else:
        return False, " | ".join(details) if details else "No active SMS provider configured."
