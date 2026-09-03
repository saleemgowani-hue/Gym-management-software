"""
SN Gym Management System - Attendance
Developed by SN Softech Solutions
"""

from datetime import date, datetime

import streamlit as st

import database as db
import reports
import utils


def page():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Attendance", "Check members in and out, and review attendance history.",
                      "\U0001F4C5")

    tab_checkin, tab_today, tab_history = st.tabs(["Check-In", "Today's Attendance", "History"])

    with tab_checkin:
        _checkin(gym_id)
    with tab_today:
        _today(gym_id)
    with tab_history:
        _history(gym_id)


def _checkin(gym_id):
    member_map = utils.member_options(gym_id, active_only=True)
    if not member_map:
        utils.empty_state("No active members", "Add and activate members first.")
        return

    with st.form("checkin_form", clear_on_submit=True):
        member_choice = st.selectbox("Member *", list(member_map.keys()))
        check_in_time = st.time_input("Check-in time", value=datetime.now().time())
        submitted = st.form_submit_button("Mark Present", type="primary", use_container_width=True)

    if submitted:
        member_id = member_map[member_choice]
        today = date.today().strftime("%Y-%m-%d")
        existing = db.fetch_one("SELECT id FROM attendance WHERE gym_id=? AND member_id=? AND att_date=?",
                                (gym_id, member_id, today))
        if existing:
            utils.toast_err(f"{member_choice} is already marked present today.")
        else:
            db.execute(
                """INSERT INTO attendance (gym_id, member_id, att_date, check_in, status, source)
                   VALUES (?,?,?,?, 'Present', 'Manual')""",
                (gym_id, member_id, today, check_in_time.strftime("%H:%M")))
            utils.toast_ok(f"{member_choice} checked in.")
            st.rerun()


def _today(gym_id):
    today = date.today().strftime("%Y-%m-%d")
    df = db.fetch_all(
        """SELECT a.id, m.full_name, m.member_code, a.check_in, a.check_out
           FROM attendance a JOIN members m ON m.id = a.member_id
           WHERE a.gym_id=? AND a.att_date=? ORDER BY a.check_in DESC""", (gym_id, today))
    total = db.fetch_value("SELECT COUNT(*) FROM members WHERE gym_id=? AND status='Active'", (gym_id,))
    utils.kpi_card("Checked In Today", len(df), "\U0001F4C5", "#0B87C4",
                   sub=f"out of {total} active members")
    st.write("")
    if not df:
        utils.empty_state("No check-ins yet today.")
        return
    for r in df:
        c = st.columns([3, 2, 2, 2])
        c[0].write(f"**{r['full_name']}** ({r['member_code']})")
        c[1].write(f"In: {r['check_in'] or '-'}")
        c[2].write(f"Out: {r['check_out'] or '-'}")
        if not r["check_out"]:
            if c[3].button("Check Out", key=f"co_{r['id']}", use_container_width=True):
                db.execute("UPDATE attendance SET check_out=? WHERE id=?",
                          (datetime.now().strftime("%H:%M"), r["id"]))
                st.rerun()
        else:
            c[3].markdown("<span style='color:#16A34A'>Completed</span>", unsafe_allow_html=True)


def _history(gym_id):
    start, end, _label = utils.date_range_picker("att_hist", default="This Month")
    df = reports.attendance_report(gym_id, start, end)
    if df.empty:
        utils.empty_state("No attendance records for this period.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    utils.excel_download(df, "attendance_report", key="att_export")

    st.markdown("##### Member-wise summary")
    summary = reports.memberwise_attendance(gym_id, start, end)
    if not summary.empty:
        st.dataframe(summary, use_container_width=True, hide_index=True)
