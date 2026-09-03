"""
SN Gym Management System - Trainers & Personal Training
Developed by SN Softech Solutions
"""

from datetime import date

import streamlit as st

import database as db
import utils

STATUSES = ["Active", "Inactive"]
SPECIALIZATIONS = ["Strength & Conditioning", "Weight Loss", "Bodybuilding", "Yoga",
                   "CrossFit", "Cardio", "Rehabilitation", "General Fitness"]


# --------------------------------------------------------------------------
# Trainers
# --------------------------------------------------------------------------
def page_trainers():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Trainers", "Manage your training staff and their assignments.", "\U0001F3CB")

    tab_list, tab_add = st.tabs(["All Trainers", "Add / Edit Trainer"])

    with tab_list:
        rows = db.fetch_all(
            """SELECT t.*, (SELECT COUNT(*) FROM members m WHERE m.trainer_id=t.id) AS member_count
               FROM trainers t WHERE t.gym_id=? ORDER BY t.id DESC""", (gym_id,))
        if not rows:
            utils.empty_state("No trainers yet", "Add your first trainer in the next tab.")
        for t in rows:
            c = st.columns([3, 2, 2, 2, 2, 1])
            c[0].markdown(f"**{t['trainer_name']}**  \n<span style='color:#64748B;font-size:.8rem'>"
                         f"{t['specialization'] or ''}</span>", unsafe_allow_html=True)
            c[1].write(t["mobile"] or "-")
            c[2].write(f"{t['member_count']} member(s)")
            c[3].write(utils.money(t["salary"]))
            c[4].markdown(utils.status_badge(t["status"]) if t["status"] == "Active" else
                         f"<span style='color:#94A3B8'>{t['status']}</span>", unsafe_allow_html=True)
            if c[5].button("Edit", key=f"trainer_edit_{t['id']}"):
                st.session_state["editing_trainer"] = t["id"]
                st.rerun()

    with tab_add:
        editing_id = st.session_state.get("editing_trainer")
        trainer = db.fetch_one("SELECT * FROM trainers WHERE id=?", (editing_id,)) if editing_id else None
        if trainer:
            st.info(f"Editing **{trainer['trainer_name']}**")
            if st.button("Cancel edit / add new instead", key="cancel_trainer_edit"):
                st.session_state["editing_trainer"] = None
                st.rerun()
        with st.form("trainer_form", clear_on_submit=not trainer):
            c1, c2 = st.columns(2)
            name = c1.text_input("Trainer Name *", value=(trainer or {}).get("trainer_name", ""))
            mobile = c2.text_input("Mobile", value=(trainer or {}).get("mobile", ""))
            email = c1.text_input("Email", value=(trainer or {}).get("email", ""))
            spec = c2.selectbox("Specialization", SPECIALIZATIONS,
                                index=SPECIALIZATIONS.index(trainer["specialization"])
                                if trainer and trainer.get("specialization") in SPECIALIZATIONS else 0)
            joining = c1.date_input("Joining Date",
                                    value=utils.to_date(trainer.get("joining_date")) if trainer else date.today())
            salary = c2.number_input("Monthly Salary", min_value=0.0, step=500.0,
                                     value=float((trainer or {}).get("salary", 0)))
            commission = c1.number_input("PT Commission %", min_value=0.0, max_value=100.0,
                                         value=float((trainer or {}).get("commission", 0)))
            status = c2.selectbox("Status", STATUSES,
                                  index=STATUSES.index(trainer["status"]) if trainer and trainer.get("status") in STATUSES else 0)
            submitted = st.form_submit_button("Update Trainer" if trainer else "Save Trainer",
                                              type="primary", use_container_width=True)
        if submitted:
            errors = utils.require({"Trainer Name": name})
            if mobile and not utils.valid_mobile(mobile):
                errors.append("Enter a valid mobile number.")
            if errors:
                utils.toast_err("  \n".join(errors))
            elif trainer:
                db.execute(
                    """UPDATE trainers SET trainer_name=?, mobile=?, email=?, specialization=?,
                           joining_date=?, salary=?, commission=?, status=? WHERE id=?""",
                    (name.strip(), mobile, email, spec, joining.strftime("%Y-%m-%d"), salary,
                     commission, status, trainer["id"]))
                st.session_state["editing_trainer"] = None
                utils.toast_ok("Trainer updated.")
                st.rerun()
            else:
                db.execute(
                    """INSERT INTO trainers (gym_id, trainer_name, mobile, email, specialization,
                           joining_date, salary, commission) VALUES (?,?,?,?,?,?,?,?)""",
                    (gym_id, name.strip(), mobile, email, spec, joining.strftime("%Y-%m-%d"),
                     salary, commission))
                utils.toast_ok(f"Trainer {name} added.")
                st.rerun()


# --------------------------------------------------------------------------
# Personal Training
# --------------------------------------------------------------------------
def page_personal_training():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Personal Training", "Sell PT packages and log sessions.", "\U0001F4AA")

    tab_list, tab_add = st.tabs(["Active Packages", "Sell PT Package"])

    with tab_list:
        rows = db.fetch_all(
            """SELECT pt.*, m.full_name, m.member_code, t.trainer_name
               FROM personal_training pt
               JOIN members m ON m.id = pt.member_id
               LEFT JOIN trainers t ON t.id = pt.trainer_id
               WHERE pt.gym_id=? ORDER BY pt.id DESC""", (gym_id,))
        if not rows:
            utils.empty_state("No PT packages sold yet.")
        for p in rows:
            remaining = max(p["total_sessions"] - p["used_sessions"], 0)
            with st.expander(f"{p['full_name']} - {p['package_name']}  "
                             f"({p['used_sessions']}/{p['total_sessions']} used)  -  {p['status']}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"Trainer: **{p['trainer_name'] or 'Unassigned'}**")
                c2.write(f"Valid: {utils.fmt_date(p['start_date'])} to {utils.fmt_date(p['end_date'])}")
                c3.write(f"Due: {utils.money(p['due_amount'])}")
                if remaining > 0 and p["status"] == "Active":
                    if st.button("Log One Session", key=f"pt_session_{p['id']}"):
                        db.execute("INSERT INTO pt_sessions (gym_id, pt_id, session_date) VALUES (?,?,?)",
                                  (gym_id, p["id"], date.today().strftime("%Y-%m-%d")))
                        db.execute("UPDATE personal_training SET used_sessions=used_sessions+1 WHERE id=?",
                                  (p["id"],))
                        if remaining - 1 <= 0:
                            db.execute("UPDATE personal_training SET status='Completed' WHERE id=?", (p["id"],))
                        utils.toast_ok("Session logged.")
                        st.rerun()
                sessions = db.fetch_df(
                    "SELECT session_date AS Date, notes AS Notes FROM pt_sessions WHERE pt_id=? "
                    "ORDER BY id DESC", (p["id"],))
                if not sessions.empty:
                    st.dataframe(sessions, use_container_width=True, hide_index=True)

    with tab_add:
        member_map = utils.member_options(gym_id, active_only=True)
        trainer_map = utils.trainer_options(gym_id)
        if not member_map:
            utils.empty_state("No active members", "Add a member first.")
            return
        if not trainer_map:
            utils.empty_state("No active trainers", "Add a trainer first.")
            return
        with st.form("pt_form"):
            c1, c2 = st.columns(2)
            member_choice = c1.selectbox("Member *", list(member_map.keys()))
            trainer_choice = c2.selectbox("Trainer *", list(trainer_map.keys()))
            package_name = c1.text_input("Package Name", value="PT - 12 Sessions")
            total_sessions = c2.number_input("Total Sessions", min_value=1, step=1, value=12)
            start_date = c1.date_input("Start Date", value=date.today())
            end_date = c2.date_input("Expiry Date", value=utils.add_months(date.today(), 1))
            amount = c1.number_input("Package Amount", min_value=0.0, step=500.0, value=6000.0)
            paid_amount = c2.number_input("Paid Amount", min_value=0.0, value=amount)
            payment_mode = st.selectbox("Payment Mode", db.PAYMENT_MODES)
            submitted = st.form_submit_button("Sell Package", type="primary", use_container_width=True)

        if submitted:
            member_id = member_map[member_choice]
            trainer_id = trainer_map[trainer_choice]
            due_amount = round(amount - paid_amount, 2)
            invoice_no = utils.next_invoice(gym_id, "PT")
            pt_id = db.execute(
                """INSERT INTO personal_training (gym_id, member_id, trainer_id, package_name,
                       total_sessions, used_sessions, start_date, end_date, amount, paid_amount,
                       due_amount, invoice_no) VALUES (?,?,?,?,?,0,?,?,?,?,?,?)""",
                (gym_id, member_id, trainer_id, package_name, total_sessions,
                 start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), amount,
                 paid_amount, due_amount, invoice_no))
            db.execute(
                """INSERT INTO payments (gym_id, member_id, invoice_no, pay_date, category,
                       ref_table, ref_id, amount, paid_amount, due_amount, payment_mode, status,
                       created_by)
                   VALUES (?,?,?,?, 'Personal Training', 'personal_training', ?,?,?,?,?,?,?)""",
                (gym_id, member_id, invoice_no, start_date.strftime("%Y-%m-%d"), pt_id, amount,
                 paid_amount, due_amount, payment_mode, "Paid" if due_amount <= 0 else "Partial",
                 st.session_state.user["id"]))
            db.log_action(gym_id, st.session_state.user, "PT_SOLD",
                         f"{member_choice} -> {package_name} ({invoice_no})")
            utils.toast_ok(f"PT package sold. Invoice {invoice_no}.")
            st.rerun()
