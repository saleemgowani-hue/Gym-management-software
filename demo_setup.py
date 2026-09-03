"""
SN Gym Management System - demo account bootstrap
Developed by SN Softech Solutions

Used by the public cloud deployment. When DEMO_MODE is on, the app makes sure a
ready-to-explore gym exists on first boot: a licensed account, sample members,
attendance, sales, expenses and stock.

Turn it on with either of these:

    Streamlit Cloud -> Settings -> Secrets:   DEMO_MODE = true
    environment variable:                     DEMO_MODE=1

The demo login is intentionally public. Nothing here runs when DEMO_MODE is off,
so a real customer install never gets a demo account.
"""

import os

import auth
import database as db
import demo_data
import license_manager as lm

DEMO_GYM = "SN Demo Fitness Studio"
DEMO_MOBILE = "9000000000"
DEMO_USER = "demo"
DEMO_PASSWORD = "demo1234"
DEMO_MEMBERS = 28

# A second, restricted login so visitors can see what a receptionist sees.
DEMO_STAFF_USER = "reception"
DEMO_STAFF_PASSWORD = "demo1234"


def demo_mode():
    """Is this deployment running as a public demo?"""
    value = None
    try:
        import streamlit as st
        if "DEMO_MODE" in st.secrets:
            value = st.secrets["DEMO_MODE"]
    except Exception:
        pass
    if value is None:
        value = os.environ.get("DEMO_MODE", "")
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def demo_gym_id():
    row = db.fetch_one("SELECT gym_id FROM users WHERE lower(username)=lower(?)", (DEMO_USER,))
    return row["gym_id"] if row else None


def ensure_demo():
    """Create the demo gym if it is not there yet. Safe to call on every page load."""
    db.init_db()
    existing = demo_gym_id()
    if existing:
        return existing

    ok, gym_id = auth.register_gym(
        DEMO_GYM, "Demo Owner", DEMO_MOBILE, "demo@snsoftech.com",
        DEMO_USER, DEMO_PASSWORD, "Your pet's name?", "demo")
    if not ok:
        return None

    db.execute("""UPDATE gyms SET address='123 Fitness Street, Indore, MP',
                  receipt_footer='Thank you for training with us!' WHERE id=?""", (gym_id,))

    # The demo must be usable, so activate a genuine key for it.
    lm.activate(gym_id, lm.generate_key(DEMO_GYM, DEMO_MOBILE), DEMO_GYM, DEMO_MOBILE)

    demo_data.load(gym_id, DEMO_MEMBERS)
    auth.create_user(gym_id, "Demo Receptionist", DEMO_STAFF_USER, "", "",
                     DEMO_STAFF_PASSWORD, "Receptionist")
    db.log_action(gym_id, {"username": "system"}, "DEMO_BOOTSTRAP",
                  f"Demo gym created with {DEMO_MEMBERS} members")
    return gym_id


def reset_demo():
    """Wipe the demo gym and build it again - handy after visitors have played with it."""
    gym_id = demo_gym_id()
    if gym_id:
        db.execute("DELETE FROM gyms WHERE id=?", (gym_id,))
        db.execute("DELETE FROM users WHERE gym_id=?", (gym_id,))
    return ensure_demo()
