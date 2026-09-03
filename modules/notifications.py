"""
SN Gym Management System - Notifications
Developed by SN Softech Solutions
"""

import streamlit as st

import database as db
import reports
import utils

SEVERITY_COLOUR = {"bad": "#D93025", "warn": "#E08A00"}


def page():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Notifications", "Live alerts for expiries, dues and low stock.", "\U0001F4E2")

    tab_alerts, tab_log = st.tabs(["Live Alerts", "Notification Log"])

    with tab_alerts:
        _alerts(gym_id)
    with tab_log:
        _log(gym_id)


def _alerts(gym_id):
    gym = st.session_state.gym
    warn_days = int(gym.get("notify_expiry_days") or 7)
    alerts = reports.build_alerts(gym_id, warn_days)

    if not alerts:
        utils.empty_state("All clear", "No expiring memberships, dues or low stock right now.")
        return

    c1, c2 = st.columns([3, 1])
    c1.caption(f"{len(alerts)} alert(s) - expiry warning window is {warn_days} day(s)")
    if c2.button("Save all to log", use_container_width=True):
        saved = 0
        for a in alerts:
            exists = db.fetch_value(
                "SELECT COUNT(*) FROM notifications WHERE gym_id=? AND notif_type=? AND message=?",
                (gym_id, a["type"], a["message"]))
            if not exists:
                db.execute(
                    """INSERT INTO notifications (gym_id, notif_type, title, message, channel)
                       VALUES (?,?,?,?, 'In-App')""",
                    (gym_id, a["type"], a["type"], a["message"]))
                saved += 1
        utils.toast_ok(f"{saved} new alert(s) saved to the log." if saved else "Nothing new to save.")
        st.rerun()

    for a in alerts:
        colour = SEVERITY_COLOUR.get(a["severity"], "#64748B")
        contact = f" &middot; {a['contact']}" if a.get("contact") else ""
        st.markdown(
            f"<div class='panel' style='border-left:4px solid {colour};padding:12px 16px;margin-bottom:8px'>"
            f"<span style='color:{colour};font-weight:700'>{a['type']}</span><br>"
            f"{a['message']}<span style='color:#64748B;font-size:.8rem'>{contact}</span></div>",
            unsafe_allow_html=True)


def _log(gym_id):
    rows = db.fetch_all("SELECT * FROM notifications WHERE gym_id=? ORDER BY id DESC LIMIT 200",
                        (gym_id,))
    if not rows:
        utils.empty_state("No notifications logged yet.", "Save alerts from the Live Alerts tab.")
        return

    unread = sum(1 for r in rows if not r["is_read"])
    c1, c2 = st.columns([3, 1])
    c1.caption(f"{unread} unread of {len(rows)}")
    if unread and c2.button("Mark all read", use_container_width=True):
        db.execute("UPDATE notifications SET is_read=1 WHERE gym_id=?", (gym_id,))
        st.rerun()

    for n in rows:
        weight = "700" if not n["is_read"] else "500"
        c = st.columns([5, 2, 1])
        c[0].markdown(f"<span style='font-weight:{weight}'>{n['title']}</span> - {n['message']}",
                     unsafe_allow_html=True)
        c[1].caption(utils.fmt_date(n["created_at"]))
        if not n["is_read"]:
            if c[2].button("Read", key=f"read_{n['id']}", use_container_width=True):
                db.execute("UPDATE notifications SET is_read=1 WHERE id=?", (n["id"],))
                st.rerun()
