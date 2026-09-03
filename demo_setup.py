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
import time
from datetime import datetime, timedelta

import auth
import database as db
import demo_data
import license_manager as lm

DEMO_GYM = "SN Demo Fitness Studio"
DEMO_MOBILE = "9000000000"
DEMO_USER = "demo"
DEMO_PASSWORD = "demo1234"
DEMO_MEMBERS = 20

# A second, restricted login so visitors can see what a receptionist sees.
DEMO_STAFF_USER = "reception"
DEMO_STAFF_PASSWORD = "demo1234"

# Tables a visitor can add rows to while exploring the demo. Anything they add here
# gets wiped back out an hour later so the shared demo always resets itself.
_RESETTABLE_TABLES = ["members", "trainers", "membership_plans", "memberships", "attendance",
                      "personal_training", "pt_sessions", "payments", "expenses", "products",
                      "product_sales", "stock_movements", "weight_history", "notifications"]
RESET_AFTER_MINUTES = 60
_PURGE_CHECK_SECONDS = 120          # rate-limit how often we bother scanning for stale rows
_last_purge_check = 0.0             # in-process only - fine, it just paces a housekeeping scan


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


def is_demo_gym(gym):
    """gym is the dict already sitting in st.session_state.gym - no extra query needed."""
    return bool(gym) and gym.get("gym_name") == DEMO_GYM and gym.get("mobile") == DEMO_MOBILE


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
    _record_seed_marks(gym_id)
    return gym_id


def reset_demo():
    """Wipe the demo gym and build it again - handy after visitors have played with it."""
    gym_id = demo_gym_id()
    if gym_id:
        db.execute("DELETE FROM gyms WHERE id=?", (gym_id,))
        db.execute("DELETE FROM users WHERE gym_id=?", (gym_id,))
    return ensure_demo()


# --------------------------------------------------------------------------
# Auto-reset: anything a visitor adds to the shared demo gym is wiped an hour later
# --------------------------------------------------------------------------
def _state_get(key):
    row = db.fetch_one("SELECT value FROM app_state WHERE key=?", (key,))
    return row["value"] if row else None


def _state_set(key, value):
    db.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES (?,?)", (key, str(value)))


def _record_seed_marks(gym_id):
    """Remember the highest row id in each table right after the demo gym was built.
    Anything inserted above that id afterwards is something a visitor added."""
    for table in _RESETTABLE_TABLES:
        max_id = db.fetch_value(f"SELECT COALESCE(MAX(id),0) FROM {table} WHERE gym_id=?", (gym_id,))
        _state_set(f"demo_seed:{table}:{gym_id}", int(max_id))


def _seed_id(table, gym_id):
    value = _state_get(f"demo_seed:{table}:{gym_id}")
    return int(value) if value is not None else None


def _delete_where_in(table, column, ids):
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    db.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", tuple(ids))


def purge_expired_demo_data():
    """If a visitor added their own data to the shared demo gym more than an hour ago,
    wipe it back to the clean sample dataset. Cheap to call on every page load - the
    actual database scan is rate-limited to once every couple of minutes."""
    global _last_purge_check
    now = time.time()
    if now - _last_purge_check < _PURGE_CHECK_SECONDS:
        return
    _last_purge_check = now

    gym_id = demo_gym_id()
    if not gym_id:
        return
    try:
        _purge_gym(gym_id)
    except Exception:
        pass                             # demo housekeeping must never break the app


def _purge_gym(gym_id):
    cutoff = (datetime.now() - timedelta(minutes=RESET_AFTER_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")

    def stale_ids(table, extra_where=""):
        seed = _seed_id(table, gym_id)
        if seed is None:
            return []
        sql = (f"SELECT id FROM {table} WHERE gym_id=? AND id>? "
               f"AND created_at IS NOT NULL AND created_at<?{extra_where}")
        return [r["id"] for r in db.fetch_all(sql, (gym_id, seed, cutoff))]

    # Brand-new members/trainers/expenses/products a visitor created themselves.
    new_members = stale_ids("members", " AND (medical_notes IS NULL OR medical_notes<>'DEMO')")
    if new_members:
        _delete_where_in("payments", "member_id", new_members)
        _delete_where_in("members", "id", new_members)  # cascades memberships/attendance/PT/weight

    new_trainers = stale_ids("trainers", " AND (email IS NULL OR email NOT LIKE '%@demo.gym')")
    _delete_where_in("trainers", "id", new_trainers)

    _delete_where_in("expenses", "id",
                     stale_ids("expenses", " AND (notes IS NULL OR notes<>'DEMO')"))

    new_products = stale_ids("products", " AND (supplier IS NULL OR supplier<>'DEMO Supplies')")
    if new_products:
        placeholders = ",".join("?" * len(new_products))
        sale_ids = [r["id"] for r in db.fetch_all(
            f"SELECT id FROM product_sales WHERE product_id IN ({placeholders})",
            tuple(new_products))]
        if sale_ids:
            sp = ",".join("?" * len(sale_ids))
            db.execute(f"DELETE FROM payments WHERE ref_table='product_sales' AND ref_id IN ({sp})",
                      tuple(sale_ids))
            _delete_where_in("product_sales", "id", sale_ids)
        _delete_where_in("stock_movements", "product_id", new_products)
        _delete_where_in("products", "id", new_products)

    # New sales/visits/plans a visitor recorded against an EXISTING demo member/product.
    new_sales = stale_ids("product_sales")
    if new_sales:
        for row in db.fetch_all(
                f"SELECT id, product_id, quantity FROM product_sales WHERE id IN "
                f"({','.join('?' * len(new_sales))})", tuple(new_sales)):
            if row["product_id"]:
                db.execute("UPDATE products SET stock = stock + ? WHERE id=?",
                          (row["quantity"], row["product_id"]))
        sp = ",".join("?" * len(new_sales))
        db.execute(f"DELETE FROM payments WHERE ref_table='product_sales' AND ref_id IN ({sp})",
                  tuple(new_sales))
        _delete_where_in("product_sales", "id", new_sales)

    _delete_where_in("memberships", "id", stale_ids("memberships"))
    _delete_where_in("personal_training", "id", stale_ids("personal_training"))
    _delete_where_in("attendance", "id", stale_ids("attendance"))
    _delete_where_in("payments", "id", stale_ids("payments"))
    _delete_where_in("notifications", "id", stale_ids("notifications"))
    _delete_where_in("membership_plans", "id", stale_ids("membership_plans"))
