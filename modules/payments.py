"""
SN Gym Management System - Payments & Collections
Developed by SN Softech Solutions
"""

from datetime import date

import streamlit as st

import database as db
import reports
import utils


def page():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Payments & Collections", "Collect dues and review payment history.",
                      "\U0001F4B0")

    tab_dues, tab_history, tab_summary = st.tabs(["Collect Dues", "Payment History", "Collection Summary"])

    with tab_dues:
        _dues(gym_id)
    with tab_history:
        _history(gym_id)
    with tab_summary:
        _summary(gym_id)


def _dues(gym_id):
    df = reports.outstanding_report(gym_id)
    if df.empty:
        utils.empty_state("No outstanding dues", "Every invoice is fully paid. Nice work!")
        return

    st.caption(f"{len(df)} invoice(s) with a balance")
    total = df["Due"].sum()
    utils.kpi_card("Total Outstanding", utils.money(total), "\U0001F4B8", "#D93025")
    st.write("")

    for _, r in df.iterrows():
        pay_row = db.fetch_one("SELECT * FROM payments WHERE gym_id=? AND invoice_no=? "
                               "ORDER BY id DESC LIMIT 1", (gym_id, r["Invoice"]))
        if not pay_row:
            continue
        with st.expander(f"{r['Member']} ({r['Member ID']})  -  {r['Invoice']}  -  "
                         f"Due {utils.money(r['Due'])}"):
            with st.form(f"collect_{pay_row['id']}"):
                c1, c2 = st.columns(2)
                collect = c1.number_input("Amount to collect", min_value=0.0,
                                          max_value=float(pay_row["due_amount"]),
                                          value=float(pay_row["due_amount"]), key=f"amt_{pay_row['id']}")
                mode = c2.selectbox("Payment Mode", db.PAYMENT_MODES, key=f"mode_{pay_row['id']}")
                submitted = st.form_submit_button("Collect Payment", type="primary",
                                                  use_container_width=True)
            if submitted and collect > 0:
                new_paid = round(pay_row["paid_amount"] + collect, 2)
                new_due = round(pay_row["due_amount"] - collect, 2)
                status = "Paid" if new_due <= 0 else "Partial"
                db.execute("UPDATE payments SET paid_amount=?, due_amount=?, status=?, "
                          "payment_mode=? WHERE id=? AND gym_id=?",
                          (new_paid, new_due, status, mode, pay_row["id"], gym_id))
                if pay_row.get("ref_table") in ("memberships", "personal_training") and pay_row.get("ref_id"):
                    db.execute(f"UPDATE {pay_row['ref_table']} SET paid_amount=?, due_amount=? "
                              f"WHERE id=? AND gym_id=?",
                              (new_paid, new_due, pay_row["ref_id"], gym_id))
                db.log_action(gym_id, st.session_state.user, "PAYMENT_COLLECTED",
                             f"{r['Invoice']} - {utils.money(collect)}")
                utils.toast_ok(f"Collected {utils.money(collect)} for invoice {r['Invoice']}.")
                st.rerun()

    utils.excel_download(df, "outstanding_dues", key="dues_export")


def _history(gym_id):
    start, end, _label = utils.date_range_picker("pay_hist", default="This Month")
    df = reports.collection_report(gym_id, start, end)
    if df.empty:
        utils.empty_state("No payments recorded for this period.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown(f"**Total Collected: {utils.money(df['Paid'].sum())}**")
    utils.excel_download(df, "payment_history", key="pay_export")
    html = utils.html_report("Payment History", f"{start} to {end}", utils.table_html(df, "Paid"),
                             st.session_state.gym)
    utils.print_button(html, "payment_history", key="pay_print")


def _summary(gym_id):
    start, end, _label = utils.date_range_picker("pay_sum", default="This Month")
    df = reports.payment_mode_split(gym_id, start, end)
    if df.empty:
        utils.empty_state("No collections for this period.")
        return
    import plotly.express as px
    c1, c2 = st.columns([1, 1])
    with c1:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown(f"**Total: {utils.money(df['amount'].sum())}**")
    with c2:
        fig = px.pie(df, names="mode", values="amount", hole=.5)
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
