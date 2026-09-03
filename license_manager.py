"""
SN Gym Management System - Trial & license engine
Developed by SN Softech Solutions

Rules
-----
* There is NO free trial. A newly registered gym is UNLICENSED and every module
  stays locked until a valid licence key is activated.
* A valid key unlocks the software for 1 year from the activation date.
* Licence keys are derived from the gym name + registered mobile with an HMAC,
  so a key issued for one gym will not validate on another.
* Clock tampering: the app stores a monotonic "last seen" timestamp. Winding the
  computer clock backwards raises a tamper flag; winding it forward only brings
  the expiry closer, never pushes it out.
* verify_online() is the single hook to swap in a hosted licence server later -
  the rest of the app does not change.
"""

import hashlib
import hmac
import re
import time
from datetime import datetime, date, timedelta

import database as db

# Vendor secret. Change this before shipping to customers and keep it private -
# it is what makes keys unforgeable. Use tools/keygen.py with the same secret.
VENDOR_SECRET = b"SN-SOFTECH-SOLUTIONS-GYM-2026-MASTER-SECRET"

LICENSE_YEARS = 1
CLOCK_TOLERANCE_SECONDS = 6 * 3600      # allow small corrections / DST shifts
SUPPORT_CONTACT = "SN Softech Solutions  |  support@snsoftech.com  |  +91 00000 00000"

DATE_FMT = "%Y-%m-%d"


# --------------------------------------------------------------------------
# Key generation & verification
# --------------------------------------------------------------------------
def _normalise(gym_name, mobile):
    name = re.sub(r"[^a-z0-9]", "", (gym_name or "").lower())
    digits = re.sub(r"\D", "", (mobile or ""))[-10:]
    return f"{name}|{digits}".encode()


def generate_key(gym_name, mobile):
    """Vendor side: produce the licence key for a customer."""
    digest = hmac.new(VENDOR_SECRET, _normalise(gym_name, mobile), hashlib.sha256).hexdigest().upper()
    body = digest[:16]
    return "SNGYM-" + "-".join(body[i:i + 4] for i in range(0, 16, 4))


def verify_key(key, gym_name, mobile):
    if not key:
        return False
    clean = key.strip().upper().replace(" ", "")
    return hmac.compare_digest(clean, generate_key(gym_name, mobile))


def verify_online(key, gym_name, mobile):
    """
    Placeholder for hosted activation. Return:
        None  -> server not configured / unreachable, fall back to offline check
        dict  -> {"valid": bool, "expiry": "YYYY-MM-DD", "message": str}
    Implement with a requests.post() to the SN Softech licence API when ready.
    """
    return None


# --------------------------------------------------------------------------
# Licence record
# --------------------------------------------------------------------------
def create_license_record(gym_id, gym_name, mobile):
    """Called at sign up. The gym starts UNLICENSED - locked until a key is entered."""
    db.execute(
        """INSERT INTO licenses (gym_id, status, gym_name, mobile,
                                 tamper_flag, last_seen_ts, updated_at)
           VALUES (?,'UNLICENSED',?,?,0,?,?)""",
        (gym_id, gym_name, mobile, time.time(),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )


def get_license(gym_id):
    return db.fetch_one("SELECT * FROM licenses WHERE gym_id=? ORDER BY id DESC LIMIT 1", (gym_id,))


# --------------------------------------------------------------------------
# Clock guard
# --------------------------------------------------------------------------
def heartbeat(gym_id):
    """
    Called on every page load. Detects a backwards clock jump and keeps an
    always-forward reference time so licence time cannot be won back.
    Returns the effective 'today' the licence engine should trust.
    """
    lic = get_license(gym_id)
    now = time.time()
    if not lic:
        return date.today()

    last = lic.get("last_seen_ts") or now
    tamper = lic.get("tamper_flag") or 0

    if now < last - CLOCK_TOLERANCE_SECONDS:
        tamper = 1                      # clock was moved backwards
    reference = max(now, last)          # never let time walk backwards

    db.execute("UPDATE licenses SET last_seen_ts=?, tamper_flag=?, updated_at=? WHERE id=?",
               (reference, tamper, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), lic["id"]))
    return datetime.fromtimestamp(reference).date()


def _parse(value):
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except Exception:
        return None


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------
def get_status(gym_id):
    """
    Returns a dict describing exactly where this gym stands:
        state        UNLICENSED | LICENSED | LICENSE_EXPIRED | TAMPERED | NONE
        locked       True when the modules must be blocked
        days_left    remaining licence days
    """
    if not get_license(gym_id):
        return {"state": "NONE", "locked": True, "days_left": 0, "label": "No licence record",
                "activation_date": None, "expiry_date": None, "license_key": None}

    # Run the clock guard first, then re-read so the fresh tamper flag is used.
    today = heartbeat(gym_id)
    lic = get_license(gym_id)
    info = {
        "license_key": lic.get("license_key"),
        "gym_name": lic.get("gym_name"),
        "mobile": lic.get("mobile"),
        "activation_date": _parse(lic.get("activation_date") or ""),
        "expiry_date": _parse(lic.get("expiry_date") or ""),
        "today": today,
    }

    if lic.get("status") == "LICENSED":
        expiry = info["expiry_date"]
        days = (expiry - today).days if expiry else 0
        if lic.get("tamper_flag"):
            # A licensed copy still runs, but we surface the warning.
            info.update({"state": "LICENSED", "locked": days < 0, "days_left": max(days, 0),
                         "label": "Licensed (clock change detected)", "tamper": True})
            return info
        if days < 0:
            info.update({"state": "LICENSE_EXPIRED", "locked": True, "days_left": 0,
                         "label": "Licence expired"})
        else:
            info.update({"state": "LICENSED", "locked": False, "days_left": days,
                         "label": "Licensed"})
        return info

    # Never activated on this installation
    info.update({"state": "UNLICENSED", "locked": True, "days_left": 0,
                 "label": "Not activated - licence key required",
                 "tamper": bool(lic.get("tamper_flag"))})
    return info


# --------------------------------------------------------------------------
# Activation
# --------------------------------------------------------------------------
def activate(gym_id, key, gym_name, mobile, activation_date=None):
    """Validate a key and switch the gym to a 1 year licence."""
    lic = get_license(gym_id)
    if not lic:
        return False, "No licence record found for this gym."

    online = verify_online(key, gym_name, mobile)
    if online is not None and not online.get("valid"):
        return False, online.get("message", "The licence server rejected this key.")

    if online is None and not verify_key(key, gym_name, mobile):
        return False, ("This key is not valid for this gym name and mobile number. "
                       "Check both entries exactly as registered, then try again.")

    start = activation_date or date.today()
    expiry = date(start.year + LICENSE_YEARS, start.month, start.day) - timedelta(days=1)
    if online and online.get("expiry"):
        expiry = _parse(online["expiry"]) or expiry

    db.execute(
        """UPDATE licenses SET status='LICENSED', license_key=?, gym_name=?, mobile=?,
                               activation_date=?, expiry_date=?, tamper_flag=0,
                               last_seen_ts=?, updated_at=? WHERE id=?""",
        (key.strip().upper(), gym_name, mobile, start.strftime(DATE_FMT),
         expiry.strftime(DATE_FMT), time.time(),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), lic["id"]),
    )
    db.log_action(gym_id, {"username": "system"}, "LICENSE_ACTIVATED",
                  f"Valid until {expiry.strftime('%d-%b-%Y')}")
    return True, f"Licence activated. Valid until {expiry.strftime('%d-%b-%Y')}."
