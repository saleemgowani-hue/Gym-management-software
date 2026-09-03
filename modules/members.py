"""
SN Gym Management System - Members
Developed by SN Softech Solutions
"""

from datetime import date

import pandas as pd
import streamlit as st

import database as db
import reports
import utils

GENDERS = ["Male", "Female", "Other"]
BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
GOALS = ["Weight Loss", "Muscle Gain", "General Fitness", "Strength", "Endurance", "Rehabilitation"]
STATUSES = ["Active", "Inactive"]


def page():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Members", "Add, search and manage every member of your gym.", "\U0001F464")

    if st.session_state.get("profile_member"):
        _profile(gym_id, st.session_state.profile_member)
        return

    tab_list, tab_add = st.tabs(["Member Directory", "Add New Member"])
    with tab_list:
        _directory(gym_id)
    with tab_add:
        _form(gym_id)


def _directory(gym_id):
    df = db.fetch_df(
        """SELECT m.id, m.member_code, m.full_name, m.mobile, m.gender, m.status,
                  t.trainer_name, ms.plan_name, ms.end_date, COALESCE(ms.due_amount,0) AS due
           FROM members m
           LEFT JOIN trainers t ON t.id = m.trainer_id
           LEFT JOIN memberships ms ON ms.id = (
               SELECT id FROM memberships WHERE member_id=m.id ORDER BY date(end_date) DESC, id DESC LIMIT 1)
           WHERE m.gym_id=? ORDER BY m.id DESC""", (gym_id,))

    if df.empty:
        utils.empty_state("No members yet", "Use the 'Add New Member' tab to register your first member.")
        return

    search = st.text_input("Search by name, mobile or member ID", key="mem_search")
    c1, c2 = st.columns(2)
    status_filter = c1.selectbox("Membership status", ["All", "Active", "Expiring Soon",
                                                        "Expired", "No Membership", "Payment Due"],
                                 key="mem_status_filter")
    trainer_filter = c2.selectbox("Trainer", ["All"] + sorted(df["trainer_name"].dropna().unique().tolist()),
                                  key="mem_trainer_filter")

    view = df.copy()
    view["Membership Status"] = view.apply(lambda r: utils.membership_status(r["end_date"], r["due"]), axis=1)
    if search:
        s = search.lower()
        view = view[view.apply(lambda r: s in str(r["full_name"]).lower()
                               or s in str(r["mobile"]).lower()
                               or s in str(r["member_code"]).lower(), axis=1)]
    if status_filter != "All":
        view = view[view["Membership Status"] == status_filter]
    if trainer_filter != "All":
        view = view[view["trainer_name"] == trainer_filter]

    st.caption(f"{len(view)} of {len(df)} members")
    for _, r in view.iterrows():
        c = st.columns([2, 2, 2, 2, 2, 1])
        c[0].markdown(f"**{r['full_name']}**  \n<span style='color:#64748B'>{r['member_code']}</span>",
                      unsafe_allow_html=True)
        c[1].write(r["mobile"] or "-")
        c[2].write(r["plan_name"] or "No plan")
        c[3].write(utils.fmt_date(r["end_date"]))
        c[4].markdown(utils.status_badge(r["Membership Status"]), unsafe_allow_html=True)
        if c[5].button("View", key=f"view_mem_{r['id']}", use_container_width=True):
            st.session_state.profile_member = int(r["id"])
            st.rerun()

    export_df = view.drop(columns=["id"], errors="ignore")
    utils.excel_download(export_df, "members", key="mem_export")


def _form(gym_id, member=None):
    editing = member is not None
    prefix = f"edit_{member['id']}" if editing else "new"

    with st.form(f"member_form_{prefix}"):
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Full Name *", value=(member or {}).get("full_name", ""))
        gender = c2.selectbox("Gender", GENDERS,
                              index=GENDERS.index(member["gender"]) if editing and member.get("gender") in GENDERS else 0)
        mobile = c1.text_input("Mobile *", value=(member or {}).get("mobile", ""))
        whatsapp = c2.text_input("WhatsApp", value=(member or {}).get("whatsapp", ""))
        email = c1.text_input("Email", value=(member or {}).get("email", ""))
        dob = c2.date_input("Date of Birth", value=utils.to_date(member.get("dob")) if editing and member.get("dob") else date(1995, 1, 1),
                            min_value=date(1930, 1, 1), max_value=date.today())
        address = st.text_area("Address", value=(member or {}).get("address", ""), height=70)
        emergency = c1.text_input("Emergency Contact", value=(member or {}).get("emergency_contact", ""))
        joining_date = c2.date_input("Joining Date", value=utils.to_date(member.get("joining_date")) if editing else date.today())

        c3, c4, c5 = st.columns(3)
        blood_group = c3.selectbox("Blood Group", BLOOD_GROUPS,
                                   index=BLOOD_GROUPS.index(member["blood_group"]) if editing and member.get("blood_group") in BLOOD_GROUPS else 0)
        height = c4.number_input("Height (cm)", min_value=0.0, max_value=250.0,
                                 value=float((member or {}).get("height") or 0))
        weight = c5.number_input("Weight (kg)", min_value=0.0, max_value=300.0,
                                 value=float((member or {}).get("weight") or 0))
        fitness_goal = c1.selectbox("Fitness Goal", GOALS,
                                    index=GOALS.index(member["fitness_goal"]) if editing and member.get("fitness_goal") in GOALS else 0)
        trainer_map = utils.trainer_options(gym_id)
        trainer_names = ["Unassigned"] + list(trainer_map.keys())
        current_trainer = None
        if editing and member.get("trainer_id"):
            current_trainer = next((n for n, i in trainer_map.items() if i == member["trainer_id"]), None)
        trainer_choice = c2.selectbox("Assign Trainer", trainer_names,
                                      index=trainer_names.index(current_trainer) if current_trainer else 0)
        medical_notes = st.text_area("Medical Notes", value=(member or {}).get("medical_notes", ""), height=60)
        photo = st.file_uploader("Photo", type=["png", "jpg", "jpeg"])
        status = st.selectbox("Status", STATUSES,
                              index=STATUSES.index(member["status"]) if editing and member.get("status") in STATUSES else 0) if editing else "Active"

        submitted = st.form_submit_button("Update Member" if editing else "Save Member",
                                          type="primary", use_container_width=True)

    if not submitted:
        return

    errors = utils.require({"Full Name": full_name, "Mobile": mobile})
    if mobile and not utils.valid_mobile(mobile):
        errors.append("Enter a valid mobile number.")
    if email and not utils.valid_email(email):
        errors.append("Enter a valid email address.")
    if errors:
        utils.toast_err("  \n".join(errors))
        return

    trainer_id = trainer_map.get(trainer_choice) if trainer_choice != "Unassigned" else None
    code = member["member_code"] if editing else utils.next_member_code(gym_id)
    photo_path = utils.save_photo(photo, code) if photo else (member or {}).get("photo_path")

    if editing:
        db.execute(
            """UPDATE members SET full_name=?, gender=?, dob=?, mobile=?, whatsapp=?, email=?,
                   address=?, emergency_contact=?, joining_date=?, photo_path=?, blood_group=?,
                   height=?, weight=?, fitness_goal=?, medical_notes=?, trainer_id=?, status=?
               WHERE id=? AND gym_id=?""",
            (full_name.strip(), gender, dob.strftime("%Y-%m-%d"), mobile.strip(), whatsapp,
             email.strip(), address, emergency, joining_date.strftime("%Y-%m-%d"), photo_path,
             blood_group, height, weight, fitness_goal, medical_notes, trainer_id, status,
             member["id"], gym_id))
        db.log_action(gym_id, st.session_state.user, "MEMBER_UPDATED", full_name)
        utils.toast_ok("Member updated.")
    else:
        member_id = db.execute(
            """INSERT INTO members (gym_id, member_code, full_name, gender, dob, mobile, whatsapp,
                   email, address, emergency_contact, joining_date, photo_path, blood_group,
                   height, weight, fitness_goal, medical_notes, trainer_id, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'Active')""",
            (gym_id, code, full_name.strip(), gender, dob.strftime("%Y-%m-%d"), mobile.strip(),
             whatsapp, email.strip(), address, emergency, joining_date.strftime("%Y-%m-%d"),
             photo_path, blood_group, height, weight, fitness_goal, medical_notes, trainer_id))
        if weight:
            db.execute("INSERT INTO weight_history (gym_id, member_id, log_date, weight) VALUES (?,?,?,?)",
                       (gym_id, member_id, date.today().strftime("%Y-%m-%d"), weight))
        db.log_action(gym_id, st.session_state.user, "MEMBER_ADDED", f"{full_name} ({code})")
        utils.toast_ok(f"Member {full_name} added with ID {code}.")
    utils.member_options.clear()
    st.rerun()


def _profile(gym_id, member_id):
    member = db.fetch_one("SELECT * FROM members WHERE id=? AND gym_id=?", (member_id, gym_id))
    if not member:
        st.session_state.profile_member = None
        utils.toast_err("That member could not be found.")
        return

    if st.button("← Back to member list"):
        st.session_state.profile_member = None
        st.rerun()

    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown(utils.photo_or_placeholder(member.get("photo_path")), unsafe_allow_html=True)
    with c2:
        st.markdown(f"### {member['full_name']}  <span style='color:#64748B;font-size:.9rem'>"
                    f"{member['member_code']}</span>", unsafe_allow_html=True)
        st.write(f"\U0001F4F1 {member['mobile'] or '-'}   |   ✉️ {member['email'] or '-'}")
        trainer = db.fetch_one("SELECT trainer_name FROM trainers WHERE id=? AND gym_id=?",
                               (member.get("trainer_id"), gym_id)) if member.get("trainer_id") else None
        st.write(f"Trainer: **{trainer['trainer_name'] if trainer else 'Unassigned'}**  |  "
                f"Joined: **{utils.fmt_date(member['joining_date'])}**  |  Status: **{member['status']}**")

    tabs = st.tabs(["Overview", "Membership History", "Attendance", "Payments", "Personal Training",
                    "Weight Tracker", "Edit / Delete"])

    with tabs[0]:
        latest = db.fetch_one(
            """SELECT * FROM memberships WHERE member_id=? ORDER BY date(end_date) DESC, id DESC LIMIT 1""",
            (member_id,))
        due = db.fetch_value("SELECT COALESCE(SUM(due_amount),0) FROM payments WHERE member_id=?", (member_id,))
        c1, c2, c3 = st.columns(3)
        with c1:
            utils.kpi_card("Current Plan", latest["plan_name"] if latest else "None", "\U0001F4DD", "#7C4DFF")
        with c2:
            status = utils.membership_status(latest["end_date"] if latest else None, due)
            utils.kpi_card("Membership Status", status, "✅", "#0EA5A5")
        with c3:
            utils.kpi_card("Total Due", utils.money(due), "\U0001F4B0", "#D93025")
        st.write("**Address:**", member.get("address") or "-")
        st.write("**Emergency Contact:**", member.get("emergency_contact") or "-")
        st.write("**Blood Group:**", member.get("blood_group") or "-", "  |  **Fitness Goal:**",
                 member.get("fitness_goal") or "-")
        st.write("**Medical Notes:**", member.get("medical_notes") or "-")

    with tabs[1]:
        df = db.fetch_df(
            """SELECT invoice_no AS Invoice, plan_name AS Plan, sale_type AS Type,
                      start_date AS Start, end_date AS Expiry, net_amount AS Net,
                      paid_amount AS Paid, due_amount AS Due
               FROM memberships WHERE member_id=? ORDER BY id DESC""", (member_id,))
        if df.empty:
            utils.empty_state("No membership sold yet.", "Go to Membership Sales to sell a plan.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[2]:
        df = db.fetch_df(
            """SELECT att_date AS Date, check_in AS 'Check In', check_out AS 'Check Out', status AS Status
               FROM attendance WHERE member_id=? ORDER BY att_date DESC LIMIT 60""", (member_id,))
        if df.empty:
            utils.empty_state("No attendance recorded yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[3]:
        df = db.fetch_df(
            """SELECT pay_date AS Date, invoice_no AS Invoice, category AS Category,
                      amount AS Amount, paid_amount AS Paid, due_amount AS Due,
                      payment_mode AS Mode, status AS Status
               FROM payments WHERE member_id=? ORDER BY id DESC""", (member_id,))
        if df.empty:
            utils.empty_state("No payments recorded yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[4]:
        df = db.fetch_df(
            """SELECT package_name AS Package, total_sessions AS Total, used_sessions AS Used,
                      start_date AS Start, end_date AS Expiry, status AS Status
               FROM personal_training WHERE member_id=? ORDER BY id DESC""", (member_id,))
        if df.empty:
            utils.empty_state("No personal training package yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[5]:
        df = db.fetch_df("SELECT log_date AS Date, weight AS 'Weight (kg)' FROM weight_history "
                         "WHERE member_id=? ORDER BY date(log_date)", (member_id,))
        with st.form("weight_log"):
            c1, c2 = st.columns(2)
            log_date = c1.date_input("Date", value=date.today())
            new_weight = c2.number_input("Weight (kg)", min_value=0.0, max_value=300.0, step=0.5)
            if st.form_submit_button("Log Weight", type="primary"):
                db.execute("INSERT INTO weight_history (gym_id, member_id, log_date, weight) VALUES (?,?,?,?)",
                          (gym_id, member_id, log_date.strftime("%Y-%m-%d"), new_weight))
                db.execute("UPDATE members SET weight=? WHERE id=?", (new_weight, member_id))
                utils.toast_ok("Weight logged.")
                st.rerun()
        if not df.empty:
            import plotly.express as px
            fig = px.line(df, x="Date", y="Weight (kg)", markers=True)
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with tabs[6]:
        st.markdown("##### Edit member details")
        _form(gym_id, member)
        st.divider()
        st.markdown("##### Danger zone")
        if utils.confirm("del_confirm", "Yes, permanently delete this member and all related records"):
            if st.button("Delete Member", type="primary"):
                db.execute("DELETE FROM members WHERE id=?", (member_id,))
                db.log_action(gym_id, st.session_state.user, "MEMBER_DELETED", member["full_name"])
                utils.member_options.clear()
                st.session_state.profile_member = None
                utils.toast_ok("Member deleted.")
                st.rerun()
