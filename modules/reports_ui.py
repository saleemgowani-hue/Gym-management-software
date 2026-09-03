"""
SN Gym Management System - Reports & KPI Analytics
Developed by SN Softech Solutions
"""

import plotly.express as px
import streamlit as st

import reports
import utils


def page_reports():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("Reports", "Every report your gym needs, exportable to Excel or print.",
                      "\U0001F4CA")

    tabs = st.tabs(["Members", "Collections", "Outstanding Dues", "Expenses", "Attendance",
                    "Plan Revenue", "Trainer Performance", "Profit & Loss"])

    with tabs[0]:
        kind = st.selectbox("Show", ["All Members", "Active Members", "Expired Members",
                                     "Expiring Members", "New Members"], key="rep_mem_kind")
        df = reports.members_report(gym_id, kind)
        _table(df, "members_report")

    with tabs[1]:
        start, end, _ = utils.date_range_picker("rep_coll", default="This Month")
        df = reports.collection_report(gym_id, start, end)
        _table(df, "collections", total_col="Paid")

    with tabs[2]:
        df = reports.outstanding_report(gym_id)
        _table(df, "outstanding_dues", total_col="Due")

    with tabs[3]:
        start, end, _ = utils.date_range_picker("rep_exp", default="This Month")
        df = reports.expense_report(gym_id, start, end)
        _table(df, "expense_report", total_col="Amount")

    with tabs[4]:
        start, end, _ = utils.date_range_picker("rep_att", default="This Month")
        df = reports.attendance_report(gym_id, start, end)
        _table(df, "attendance_report")

    with tabs[5]:
        df = reports.plan_revenue(gym_id)
        _table(df, "plan_revenue", total_col="Collected")

    with tabs[6]:
        df = reports.trainer_performance(gym_id)
        _table(df, "trainer_performance")

    with tabs[7]:
        start, end, _ = utils.date_range_picker("rep_pl", default="This Month")
        pl = reports.profit_and_loss(gym_id, start, end)
        c1, c2, c3 = st.columns(3)
        with c1:
            utils.kpi_card("Income", utils.money(pl["income"]), "\U0001F4B0", "#16A34A")
        with c2:
            utils.kpi_card("Expense", utils.money(pl["expense"]), "\U0001F9FE", "#D93025")
        with c3:
            utils.kpi_card("Net Profit", utils.money(pl["net"]), "\U0001F4C8",
                           "#16A34A" if pl["net"] >= 0 else "#D93025")


def _table(df, filename, total_col=None):
    if df is None or df.empty:
        utils.empty_state("No records found for this selection.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    if total_col and total_col in df.columns:
        st.markdown(f"**Total {total_col}: {utils.money(df[total_col].sum())}**")
    c1, c2 = st.columns(2)
    with c1:
        utils.excel_download(df, filename, key=f"export_{filename}")
    with c2:
        html = utils.html_report(filename.replace("_", " ").title(), "", utils.table_html(df, total_col),
                                 st.session_state.gym)
        utils.print_button(html, filename, key=f"print_{filename}")


def page_kpi():
    gym_id = st.session_state.user["gym_id"]
    utils.page_header("KPI & Analytics", "The health of your business, at a glance.", "\U0001F4C8")

    k = reports.business_kpis(gym_id)

    row1 = st.columns(4)
    with row1[0]:
        utils.kpi_card("Total Revenue", utils.money(k["total_revenue"]), "\U0001F4B0", "#16A34A")
    with row1[1]:
        utils.kpi_card("Total Expenses", utils.money(k["total_expenses"]), "\U0001F9FE", "#B45309")
    with row1[2]:
        utils.kpi_card("Net Profit", utils.money(k["net_profit"]), "\U0001F4C8",
                       "#16A34A" if k["net_profit"] >= 0 else "#D93025")
    with row1[3]:
        utils.kpi_card("Avg Revenue / Member", utils.money(k["arpm"]), "\U0001F4CA", "#7C4DFF")

    row2 = st.columns(4)
    with row2[0]:
        utils.kpi_card("Renewal Rate", f"{k['renewal_rate']:.1f}%", "\U0001F504", "#E08A00")
    with row2[1]:
        utils.kpi_card("Expiry Rate", f"{k['expiry_rate']:.1f}%", "⚠️", "#D93025")
    with row2[2]:
        utils.kpi_card("Growth This Month", f"{k['growth_pct']:.1f}%", "\U0001F331", "#0EA5A5")
    with row2[3]:
        utils.kpi_card("Avg Daily Attendance", f"{k['avg_daily_attendance']:.1f}", "\U0001F4C5",
                       "#0B87C4")

    row3 = st.columns(4)
    with row3[0]:
        utils.kpi_card("Attendance Rate", f"{k['attendance_pct']:.1f}%", "\U0001F3AF", "#DB2777")
    with row3[1]:
        utils.kpi_card("PT Revenue", utils.money(k["pt_revenue"]), "\U0001F4AA", "#C2410C")
    with row3[2]:
        utils.kpi_card("Active Members", k["active_members"], "✅", "#0EA5A5")
    with row3[3]:
        utils.kpi_card("Pending Dues", utils.money(k["pending_payments"]), "\U0001F4B8", "#7C4DFF")

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("##### Revenue vs Expense trend")
        rev = reports.revenue_by_month(gym_id)
        exp = reports.expense_by_month(gym_id)
        if rev.empty and exp.empty:
            utils.empty_state("Not enough data yet.")
        else:
            merged = rev.merge(exp, on="month", how="outer").fillna(0).sort_values("month")
            fig = px.line(merged, x="month", y=["revenue", "expense"], markers=True,
                         color_discrete_sequence=["#16A34A", "#D93025"])
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="",
                              yaxis_title="", legend_title="")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("##### New vs Renewal sales")
        df = reports.new_vs_renewal(gym_id)
        if df.empty:
            utils.empty_state("Not enough data yet.")
        else:
            cols = [c for c in df.columns if c != "month"]
            fig = px.bar(df, x="month", y=cols, barmode="stack")
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="",
                              yaxis_title="", legend_title="")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
