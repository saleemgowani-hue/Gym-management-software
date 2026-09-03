"""
SN Gym Management System - Dashboard
Developed by SN Softech Solutions
"""

import plotly.express as px
import streamlit as st

import reports
import utils


def page():
    user = st.session_state.user
    gym_id = user["gym_id"]
    utils.page_header("Dashboard", f"Welcome back, {user.get('full_name') or user['username']}",
                      "\U0001F3E0")

    k = reports.kpi_summary(gym_id)

    row1 = st.columns(4)
    with row1[0]:
        utils.kpi_card("Total Members", k["total_members"], "\U0001F465", "#3B5BFF")
    with row1[1]:
        utils.kpi_card("Active Members", k["active_members"], "✅", "#0EA5A5")
    with row1[2]:
        utils.kpi_card("Expiring Soon", k["expiring_soon"], "⏳", "#E08A00")
    with row1[3]:
        utils.kpi_card("Expired", k["expired_members"], "⚠️", "#D93025")

    row2 = st.columns(4)
    with row2[0]:
        utils.kpi_card("This Month Revenue", utils.money(k["monthly_revenue"]),
                       "\U0001F4B0", "#16A34A")
    with row2[1]:
        utils.kpi_card("Today's Collection", utils.money(k["today_collection"]),
                       "\U0001F4B5", "#2E9E5B")
    with row2[2]:
        utils.kpi_card("Pending Dues", utils.money(k["pending_payments"]),
                       "\U0001F9FE", "#7C4DFF")
    with row2[3]:
        utils.kpi_card("Today's Attendance", k["today_attendance"], "\U0001F4C5", "#0B87C4")

    row3 = st.columns(4)
    with row3[0]:
        utils.kpi_card("New This Month", k["new_this_month"], "✨", "#DB2777")
    with row3[1]:
        utils.kpi_card("PT Members", k["pt_members"], "\U0001F4AA", "#C2410C")
    with row3[2]:
        utils.kpi_card("Trainers", k["total_trainers"], "\U0001F3CB", "#0891B2")
    with row3[3]:
        utils.kpi_card("This Month Expenses", utils.money(k["monthly_expenses"]),
                       "\U0001F4C9", "#B45309")

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("##### Revenue - last 12 months")
        df = reports.revenue_by_month(gym_id)
        if df.empty:
            utils.empty_state("No collections recorded yet.")
        else:
            fig = px.bar(df, x="month", y="revenue", color_discrete_sequence=["#3B5BFF"])
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300,
                              xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("##### Membership growth")
        df = reports.membership_growth(gym_id)
        if df.empty:
            utils.empty_state("No members yet.")
        else:
            fig = px.line(df, x="month", y="cumulative", markers=True,
                          color_discrete_sequence=["#0EA5A5"])
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300,
                              xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("##### Plan distribution")
        df = reports.plan_distribution(gym_id)
        if df.empty:
            utils.empty_state("No memberships sold yet.")
        else:
            fig = px.pie(df, names="plan", values="members", hole=.55)
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("##### Active vs expired")
        df = reports.active_vs_expired(gym_id)
        if df["members"].sum() == 0:
            utils.empty_state("No members yet.")
        else:
            fig = px.pie(df, names="status", values="members", hole=.55,
                        color="status",
                        color_discrete_map={"Active": "#16A34A", "Expired": "#D93025"})
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown("##### Live alerts")
    all_alerts = reports.build_alerts(gym_id)
    alerts = all_alerts[:6]
    if not alerts:
        utils.empty_state("All clear", "No expiring memberships, dues or low stock right now.")
    else:
        for a in alerts:
            colour = {"bad": "#D93025", "warn": "#E08A00"}.get(a["severity"], "#64748B")
            st.markdown(
                f"<div style='padding:8px 0;border-bottom:1px solid #E3E8F0'>"
                f"<span style='color:{colour};font-weight:700'>{a['type']}</span> - {a['message']}"
                f"</div>", unsafe_allow_html=True)
        if len(all_alerts) > 6:
            st.caption("See the Notifications page for the full list.")
    st.markdown("</div>", unsafe_allow_html=True)
