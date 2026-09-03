"""
SN Gym Management System - Expenses
Developed by SN Softech Solutions
"""

from datetime import date

import streamlit as st

import database as db
import reports
import utils


def page():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Expenses", "Track rent, salaries, maintenance and other running costs.",
                      "\U0001F9FE")

    tab_list, tab_add = st.tabs(["Expense History", "Add Expense"])

    with tab_add:
        with st.form("expense_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            exp_date = c1.date_input("Date *", value=date.today())
            category = c2.selectbox("Category *", db.EXPENSE_CATEGORIES)
            description = c1.text_input("Description")
            amount = c2.number_input("Amount *", min_value=0.0, step=100.0)
            payment_mode = c1.selectbox("Payment Mode", db.PAYMENT_MODES)
            notes = st.text_area("Notes", height=60)
            submitted = st.form_submit_button("Save Expense", type="primary", use_container_width=True)
        if submitted:
            if amount <= 0:
                utils.toast_err("Enter an amount greater than zero.")
            else:
                db.execute(
                    """INSERT INTO expenses (gym_id, exp_date, category, description, amount,
                           payment_mode, notes) VALUES (?,?,?,?,?,?,?)""",
                    (gym_id, exp_date.strftime("%Y-%m-%d"), category, description, amount,
                     payment_mode, notes))
                db.log_action(gym_id, st.session_state.user, "EXPENSE_ADDED",
                             f"{category} - {utils.money(amount)}")
                utils.toast_ok("Expense recorded.")
                st.rerun()

    with tab_list:
        start, end, _label = utils.date_range_picker("exp_hist", default="This Month")
        df = reports.expense_report(gym_id, start, end)
        if df.empty:
            utils.empty_state("No expenses recorded for this period.")
        else:
            utils.kpi_card("Total Expenses", utils.money(df["Amount"].sum()), "\U0001F9FE", "#B45309")
            st.write("")
            st.dataframe(df, use_container_width=True, hide_index=True)
            utils.excel_download(df, "expenses", key="exp_export")
            html = utils.html_report("Expense Report", f"{start} to {end}",
                                     utils.table_html(df, "Amount"), st.session_state.gym)
            utils.print_button(html, "expense_report", key="exp_print")
