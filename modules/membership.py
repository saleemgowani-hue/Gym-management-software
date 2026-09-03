"""
SN Gym Management System - Membership plans, sales & renewals
Developed by SN Softech Solutions
"""

from datetime import date

import streamlit as st

import database as db
import utils

STATUSES = ["Active", "Inactive"]


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------
def page_plans():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Membership Plans", "Define the plans your gym sells.", "\U0001F4DD")

    tab_list, tab_add = st.tabs(["All Plans", "Add / Edit Plan"])

    with tab_list:
        df = db.fetch_all("SELECT * FROM membership_plans WHERE gym_id=? ORDER BY id DESC", (gym_id,))
        if not df:
            utils.empty_state("No plans yet", "Create your first plan in the 'Add / Edit Plan' tab.")
        for p in df:
            with st.container():
                c = st.columns([3, 2, 2, 2, 2, 1])
                c[0].markdown(f"**{p['plan_name']}**  \n<span style='color:#64748B;font-size:.8rem'>"
                             f"{p['description'] or ''}</span>", unsafe_allow_html=True)
                c[1].write(f"{p['duration_months']} month(s)")
                c[2].write(utils.money(p["price"]))
                c[3].write(f"{p['discount']}% off")
                c[4].markdown(utils.status_badge(p["status"]) if p["status"] == "Active" else
                              f"<span style='color:#94A3B8'>{p['status']}</span>", unsafe_allow_html=True)
                if c[5].button("Edit", key=f"plan_edit_{p['id']}"):
                    st.session_state["editing_plan"] = p["id"]
                    st.rerun()

    with tab_add:
        editing_id = st.session_state.get("editing_plan")
        plan = db.fetch_one("SELECT * FROM membership_plans WHERE id=?", (editing_id,)) if editing_id else None
        if plan:
            st.info(f"Editing **{plan['plan_name']}**")
            if st.button("Cancel edit / add new instead"):
                st.session_state["editing_plan"] = None
                st.rerun()
        with st.form("plan_form", clear_on_submit=not plan):
            c1, c2 = st.columns(2)
            name = c1.text_input("Plan Name *", value=(plan or {}).get("plan_name", ""))
            duration = c2.number_input("Duration (months) *", min_value=0.5, step=0.5,
                                       value=float((plan or {}).get("duration_months", 1)))
            price = c1.number_input("Price *", min_value=0.0, step=100.0,
                                    value=float((plan or {}).get("price", 0)))
            discount = c2.number_input("Discount %", min_value=0.0, max_value=100.0, step=1.0,
                                       value=float((plan or {}).get("discount", 0)))
            description = st.text_area("Description", value=(plan or {}).get("description", ""))
            status = st.selectbox("Status", STATUSES,
                                  index=STATUSES.index(plan["status"]) if plan and plan.get("status") in STATUSES else 0)
            submitted = st.form_submit_button("Update Plan" if plan else "Save Plan",
                                              type="primary", use_container_width=True)
        if submitted:
            errors = utils.require({"Plan Name": name})
            if not price and price != 0:
                errors.append("Enter a price.")
            if errors:
                utils.toast_err("  \n".join(errors))
            elif plan:
                db.execute(
                    """UPDATE membership_plans SET plan_name=?, duration_months=?, price=?,
                           discount=?, description=?, status=? WHERE id=?""",
                    (name.strip(), duration, price, discount, description, status, plan["id"]))
                st.session_state["editing_plan"] = None
                utils.toast_ok("Plan updated.")
                st.rerun()
            else:
                db.execute(
                    """INSERT INTO membership_plans (gym_id, plan_name, duration_months, price,
                           discount, description) VALUES (?,?,?,?,?,?)""",
                    (gym_id, name.strip(), duration, price, discount, description))
                utils.toast_ok(f"Plan '{name}' created.")
                st.rerun()


# --------------------------------------------------------------------------
# Sales
# --------------------------------------------------------------------------
def page_sales():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Membership Sales", "Sell a new membership plan to a member.", "\U0001F4B3")

    member_map = utils.member_options(gym_id)
    plans = db.fetch_all("SELECT * FROM membership_plans WHERE gym_id=? AND status='Active' "
                         "ORDER BY plan_name", (gym_id,))
    if not member_map:
        utils.empty_state("No members yet", "Add a member first from the Members page.")
        return
    if not plans:
        utils.empty_state("No active plans", "Create a plan first from Membership Plans.")
        return
    plan_map = {p["plan_name"]: p for p in plans}

    with st.form("sale_form"):
        c1, c2 = st.columns(2)
        member_choice = c1.selectbox("Member *", list(member_map.keys()))
        plan_choice = c2.selectbox("Plan *", list(plan_map.keys()))
        start_date = c1.date_input("Start Date", value=date.today())
        plan = plan_map[plan_choice]
        end_date = utils.add_months(start_date, plan["duration_months"])
        c2.date_input("Expiry Date (auto)", value=end_date, disabled=True)
        amount = c1.number_input("Amount", min_value=0.0, value=float(plan["price"]))
        discount = c2.number_input("Discount", min_value=0.0, value=round(
            float(plan["price"]) * float(plan["discount"] or 0) / 100, 2))
        net_amount = round(amount - discount, 2)
        st.markdown(f"**Net Payable: {utils.money(net_amount)}**")
        paid_amount = c1.number_input("Paid Amount", min_value=0.0, max_value=max(net_amount, 0.0),
                                      value=net_amount)
        payment_mode = c2.selectbox("Payment Mode", db.PAYMENT_MODES)
        notes = st.text_input("Notes")
        submitted = st.form_submit_button("Confirm Sale", type="primary", use_container_width=True)

    if not submitted:
        return

    due_amount = round(net_amount - paid_amount, 2)
    member_id = member_map[member_choice]
    invoice_no = utils.next_invoice(gym_id, "MEM")

    ms_id = db.execute(
        """INSERT INTO memberships (gym_id, member_id, plan_id, plan_name, sale_type, invoice_no,
               start_date, end_date, amount, discount, net_amount, paid_amount, due_amount,
               payment_mode, notes, created_by)
           VALUES (?,?,?,?,'New',?,?,?,?,?,?,?,?,?,?,?)""",
        (gym_id, member_id, plan["id"], plan["plan_name"], invoice_no,
         start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), amount, discount,
         net_amount, paid_amount, due_amount, payment_mode, notes, st.session_state.user["id"]))
    db.execute(
        """INSERT INTO payments (gym_id, member_id, invoice_no, pay_date, category, ref_table,
               ref_id, amount, paid_amount, due_amount, payment_mode, status, notes, created_by)
           VALUES (?,?,?,?, 'Membership', 'memberships', ?,?,?,?,?,?,?,?)""",
        (gym_id, member_id, invoice_no, start_date.strftime("%Y-%m-%d"), ms_id, net_amount,
         paid_amount, due_amount, payment_mode, "Paid" if due_amount <= 0 else "Partial", notes,
         st.session_state.user["id"]))
    db.execute("UPDATE members SET status='Active' WHERE id=?", (member_id,))
    db.log_action(gym_id, st.session_state.user, "MEMBERSHIP_SALE",
                 f"{member_choice} -> {plan_choice} ({invoice_no})")
    utils.toast_ok(f"Membership sold. Invoice {invoice_no}.")

    sale = db.fetch_one("SELECT * FROM memberships WHERE id=?", (ms_id,))
    member = db.fetch_one("SELECT * FROM members WHERE id=?", (member_id,))
    html = utils.receipt_html(st.session_state.gym, member, sale)
    utils.print_button(html, f"receipt_{invoice_no}", "Print / Save Receipt", key="sale_receipt")


# --------------------------------------------------------------------------
# Renewals
# --------------------------------------------------------------------------
def page_renewals():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Renewals", "Renew memberships that are expiring soon or already lapsed.",
                      "\U0001F504")

    df = db.fetch_df(
        """SELECT m.id AS member_id, m.full_name, m.mobile, ms.id AS ms_id, ms.plan_id,
                  ms.plan_name, ms.end_date, COALESCE(ms.due_amount,0) AS due
           FROM members m
           JOIN memberships ms ON ms.id = (
               SELECT id FROM memberships WHERE member_id=m.id ORDER BY date(end_date) DESC, id DESC LIMIT 1)
           WHERE m.gym_id=? ORDER BY date(ms.end_date)""", (gym_id,))
    if df.empty:
        utils.empty_state("No memberships to renew yet.")
        return

    df["Status"] = df.apply(lambda r: utils.membership_status(r["end_date"], r["due"]), axis=1)
    view = df[df["Status"].isin(["Expiring Soon", "Expired", "Payment Due"])]
    st.caption(f"{len(view)} member(s) need attention")
    if view.empty:
        utils.empty_state("Nothing due right now", "Every membership is active and paid up.")
        return

    plans = db.fetch_all("SELECT * FROM membership_plans WHERE gym_id=? AND status='Active' "
                         "ORDER BY plan_name", (gym_id,))
    plan_map = {p["plan_name"]: p for p in plans}

    for _, r in view.iterrows():
        with st.expander(f"{r['full_name']}  -  {r['plan_name'] or 'No plan'}  -  "
                         f"expiry {utils.fmt_date(r['end_date'])}  ({r['Status']})"):
            with st.form(f"renew_{r['ms_id']}"):
                c1, c2 = st.columns(2)
                default_plan = r["plan_name"] if r["plan_name"] in plan_map else (
                    list(plan_map.keys())[0] if plan_map else None)
                if not plan_map:
                    st.warning("No active plans available. Create one on Membership Plans.")
                    st.form_submit_button("Renew", disabled=True)
                    continue
                plan_choice = c1.selectbox("Plan", list(plan_map.keys()),
                                           index=list(plan_map.keys()).index(default_plan) if default_plan in plan_map else 0,
                                           key=f"plan_{r['ms_id']}")
                plan = plan_map[plan_choice]
                anchor = utils.to_date(r["end_date"], date.today())
                start_date = max(anchor, date.today()) if anchor < date.today() else anchor
                start_date = c2.date_input("Start Date", value=start_date, key=f"start_{r['ms_id']}")
                end_date = utils.add_months(start_date, plan["duration_months"])
                st.caption(f"New expiry: {utils.fmt_date(end_date)}")
                amount = c1.number_input("Amount", min_value=0.0, value=float(plan["price"]),
                                         key=f"amt_{r['ms_id']}")
                discount = c2.number_input("Discount", min_value=0.0, value=round(
                    float(plan["price"]) * float(plan["discount"] or 0) / 100, 2),
                    key=f"disc_{r['ms_id']}")
                net_amount = round(amount - discount, 2)
                st.markdown(f"**Net Payable: {utils.money(net_amount)}**")
                paid_amount = c1.number_input("Paid Amount", min_value=0.0,
                                              value=net_amount, key=f"paid_{r['ms_id']}")
                payment_mode = c2.selectbox("Payment Mode", db.PAYMENT_MODES, key=f"mode_{r['ms_id']}")
                submitted = st.form_submit_button("Renew Membership", type="primary",
                                                  use_container_width=True)
            if submitted:
                due_amount = round(net_amount - paid_amount, 2)
                invoice_no = utils.next_invoice(gym_id, "REN")
                ms_id = db.execute(
                    """INSERT INTO memberships (gym_id, member_id, plan_id, plan_name, sale_type,
                           invoice_no, start_date, end_date, amount, discount, net_amount,
                           paid_amount, due_amount, payment_mode, created_by)
                       VALUES (?,?,?,?,'Renewal',?,?,?,?,?,?,?,?,?,?)""",
                    (gym_id, int(r["member_id"]), plan["id"], plan["plan_name"], invoice_no,
                     start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), amount,
                     discount, net_amount, paid_amount, due_amount, payment_mode,
                     st.session_state.user["id"]))
                db.execute(
                    """INSERT INTO payments (gym_id, member_id, invoice_no, pay_date, category,
                           ref_table, ref_id, amount, paid_amount, due_amount, payment_mode,
                           status, created_by)
                       VALUES (?,?,?,?, 'Renewal', 'memberships', ?,?,?,?,?,?,?)""",
                    (gym_id, int(r["member_id"]), invoice_no, start_date.strftime("%Y-%m-%d"),
                     ms_id, net_amount, paid_amount, due_amount, payment_mode,
                     "Paid" if due_amount <= 0 else "Partial", st.session_state.user["id"]))
                db.execute("UPDATE members SET status='Active' WHERE id=?", (int(r["member_id"]),))
                db.log_action(gym_id, st.session_state.user, "MEMBERSHIP_RENEWED",
                             f"{r['full_name']} -> {plan_choice} ({invoice_no})")
                utils.toast_ok(f"Membership renewed for {r['full_name']}. Invoice {invoice_no}.")
                st.rerun()
