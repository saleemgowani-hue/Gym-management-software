"""
SN Gym Management System - analytics layer
Developed by SN Softech Solutions

Pure data functions. They return numbers and DataFrames; the UI modules decide
how to draw them. Keeping the SQL here means the dashboard, the reports hub and
the KPI page always agree on the same definitions.
"""

from datetime import date, timedelta

import pandas as pd

import database as db

D = "%Y-%m-%d"


def _s(d):
    return d.strftime(D) if hasattr(d, "strftime") else str(d)


# --------------------------------------------------------------------------
# Headline KPIs
# --------------------------------------------------------------------------
def kpi_summary(gym_id, warn_days=7):
    today = date.today()
    soon = today + timedelta(days=warn_days)
    month_start = today.replace(day=1)
    v = db.fetch_value

    latest = """
        SELECT m.id, ms.end_date, ms.due_amount FROM members m
        LEFT JOIN memberships ms ON ms.id = (
            SELECT id FROM memberships WHERE member_id = m.id ORDER BY date(end_date) DESC, id DESC LIMIT 1)
        WHERE m.gym_id = ?"""
    df = db.fetch_df(latest, (gym_id,))

    total = len(df)
    if total:
        ends = pd.to_datetime(df["end_date"], errors="coerce").dt.date
        active = int(((ends >= today) & ends.notna()).sum())
        expired = int(((ends < today) & ends.notna()).sum()) + int(ends.isna().sum())
        expiring = int(((ends >= today) & (ends <= soon)).sum())
    else:
        active = expired = expiring = 0

    return {
        "total_members": total,
        "active_members": active,
        "expired_members": expired,
        "expiring_soon": expiring,
        "new_this_month": v("SELECT COUNT(*) FROM members WHERE gym_id=? AND date(joining_date)>=?",
                            (gym_id, _s(month_start))),
        "today_attendance": v("SELECT COUNT(*) FROM attendance WHERE gym_id=? AND att_date=?",
                              (gym_id, _s(today))),
        "monthly_revenue": v("SELECT COALESCE(SUM(paid_amount),0) FROM payments "
                             "WHERE gym_id=? AND date(pay_date)>=?", (gym_id, _s(month_start))),
        "today_collection": v("SELECT COALESCE(SUM(paid_amount),0) FROM payments "
                              "WHERE gym_id=? AND date(pay_date)=?", (gym_id, _s(today))),
        "pending_payments": v("SELECT COALESCE(SUM(due_amount),0) FROM payments WHERE gym_id=?",
                              (gym_id,)),
        "pt_members": v("SELECT COUNT(DISTINCT member_id) FROM personal_training "
                        "WHERE gym_id=? AND status='Active'", (gym_id,)),
        "total_trainers": v("SELECT COUNT(*) FROM trainers WHERE gym_id=? AND status='Active'",
                            (gym_id,)),
        "total_staff": v("SELECT COUNT(*) FROM users WHERE gym_id=? AND is_active=1", (gym_id,)),
        "monthly_expenses": v("SELECT COALESCE(SUM(amount),0) FROM expenses "
                              "WHERE gym_id=? AND date(exp_date)>=?", (gym_id, _s(month_start))),
    }


# --------------------------------------------------------------------------
# Chart data
# --------------------------------------------------------------------------
def revenue_by_month(gym_id, months=12):
    df = db.fetch_df(
        """SELECT strftime('%Y-%m', pay_date) AS month,
                  COALESCE(SUM(paid_amount),0) AS revenue
           FROM payments WHERE gym_id=? GROUP BY month ORDER BY month""", (gym_id,))
    return df.tail(months)


def expense_by_month(gym_id, months=12):
    df = db.fetch_df(
        """SELECT strftime('%Y-%m', exp_date) AS month, COALESCE(SUM(amount),0) AS expense
           FROM expenses WHERE gym_id=? GROUP BY month ORDER BY month""", (gym_id,))
    return df.tail(months)


def membership_growth(gym_id, months=12):
    df = db.fetch_df(
        """SELECT strftime('%Y-%m', joining_date) AS month, COUNT(*) AS members
           FROM members WHERE gym_id=? GROUP BY month ORDER BY month""", (gym_id,))
    if not df.empty:
        df["cumulative"] = df["members"].cumsum()
    return df.tail(months)


def daily_attendance(gym_id, start, end):
    return db.fetch_df(
        """SELECT att_date AS day, COUNT(*) AS visits FROM attendance
           WHERE gym_id=? AND att_date BETWEEN ? AND ?
           GROUP BY att_date ORDER BY att_date""", (gym_id, _s(start), _s(end)))


def plan_distribution(gym_id):
    return db.fetch_df(
        """SELECT COALESCE(plan_name,'Unassigned') AS plan, COUNT(*) AS members
           FROM memberships WHERE gym_id=? GROUP BY plan ORDER BY members DESC""", (gym_id,))


def new_vs_renewal(gym_id, months=12):
    df = db.fetch_df(
        """SELECT strftime('%Y-%m', created_at) AS month, sale_type, COUNT(*) AS count
           FROM memberships WHERE gym_id=? GROUP BY month, sale_type ORDER BY month""", (gym_id,))
    if df.empty:
        return df
    return df.pivot(index="month", columns="sale_type", values="count").fillna(0).tail(months).reset_index()


def payment_mode_split(gym_id, start=None, end=None):
    sql = ("SELECT COALESCE(payment_mode,'Other') AS mode, COALESCE(SUM(paid_amount),0) AS amount "
           "FROM payments WHERE gym_id=?")
    params = [gym_id]
    if start and end:
        sql += " AND date(pay_date) BETWEEN ? AND ?"
        params += [_s(start), _s(end)]
    return db.fetch_df(sql + " GROUP BY mode ORDER BY amount DESC", tuple(params))


def active_vs_expired(gym_id):
    k = kpi_summary(gym_id)
    return pd.DataFrame({"status": ["Active", "Expired"],
                         "members": [k["active_members"], k["expired_members"]]})


# --------------------------------------------------------------------------
# Tabular reports
# --------------------------------------------------------------------------
def members_report(gym_id, kind="All Members", warn_days=7):
    df = db.fetch_df(
        """SELECT m.member_code AS 'Member ID', m.full_name AS 'Name', m.gender AS 'Gender',
                  m.mobile AS 'Mobile', m.joining_date AS 'Joined',
                  ms.plan_name AS 'Plan', ms.start_date AS 'Start', ms.end_date AS 'Expiry',
                  COALESCE(ms.due_amount,0) AS 'Due', t.trainer_name AS 'Trainer'
           FROM members m
           LEFT JOIN memberships ms ON ms.id = (
               SELECT id FROM memberships WHERE member_id=m.id ORDER BY date(end_date) DESC, id DESC LIMIT 1)
           LEFT JOIN trainers t ON t.id = m.trainer_id
           WHERE m.gym_id=? ORDER BY m.full_name""", (gym_id,))
    if df.empty:
        return df
    today = pd.Timestamp(date.today())
    exp = pd.to_datetime(df["Expiry"], errors="coerce")
    if kind == "Active Members":
        df = df[exp >= today]
    elif kind == "Expired Members":
        df = df[(exp < today) | exp.isna()]
    elif kind == "Expiring Members":
        df = df[(exp >= today) & (exp <= today + pd.Timedelta(days=warn_days))]
    elif kind == "New Members":
        df = df[pd.to_datetime(df["Joined"], errors="coerce") >= today.replace(day=1)]
    return df.reset_index(drop=True)


def collection_report(gym_id, start, end):
    return db.fetch_df(
        """SELECT p.pay_date AS 'Date', p.invoice_no AS 'Invoice',
                  COALESCE(m.full_name,'-') AS 'Member', p.category AS 'Category',
                  p.amount AS 'Amount', p.paid_amount AS 'Paid', p.due_amount AS 'Due',
                  p.payment_mode AS 'Mode', p.status AS 'Status'
           FROM payments p LEFT JOIN members m ON m.id=p.member_id
           WHERE p.gym_id=? AND date(p.pay_date) BETWEEN ? AND ?
           ORDER BY date(p.pay_date) DESC, p.id DESC""", (gym_id, _s(start), _s(end)))


def outstanding_report(gym_id):
    return db.fetch_df(
        """SELECT m.member_code AS 'Member ID', m.full_name AS 'Member', m.mobile AS 'Mobile',
                  p.invoice_no AS 'Invoice', p.pay_date AS 'Date', p.category AS 'Category',
                  p.due_amount AS 'Due'
           FROM payments p JOIN members m ON m.id=p.member_id
           WHERE p.gym_id=? AND p.due_amount > 0 ORDER BY p.due_amount DESC""", (gym_id,))


def expense_report(gym_id, start, end):
    return db.fetch_df(
        """SELECT exp_date AS 'Date', category AS 'Category', description AS 'Description',
                  amount AS 'Amount', payment_mode AS 'Mode', notes AS 'Notes'
           FROM expenses WHERE gym_id=? AND date(exp_date) BETWEEN ? AND ?
           ORDER BY date(exp_date) DESC""", (gym_id, _s(start), _s(end)))


def attendance_report(gym_id, start, end):
    return db.fetch_df(
        """SELECT a.att_date AS 'Date', m.member_code AS 'Member ID', m.full_name AS 'Member',
                  a.check_in AS 'Check In', a.check_out AS 'Check Out', a.status AS 'Status'
           FROM attendance a JOIN members m ON m.id=a.member_id
           WHERE a.gym_id=? AND a.att_date BETWEEN ? AND ?
           ORDER BY a.att_date DESC, m.full_name""", (gym_id, _s(start), _s(end)))


def memberwise_attendance(gym_id, start, end):
    days = max((end - start).days + 1, 1)
    df = db.fetch_df(
        """SELECT m.member_code AS 'Member ID', m.full_name AS 'Member',
                  COUNT(a.id) AS 'Visits'
           FROM members m LEFT JOIN attendance a
                ON a.member_id=m.id AND a.att_date BETWEEN ? AND ?
           WHERE m.gym_id=? GROUP BY m.id, m.member_code, m.full_name""",
        (_s(start), _s(end), gym_id))
    if not df.empty:
        df["Visits"] = pd.to_numeric(df["Visits"], errors="coerce").fillna(0).astype(int)
        df["Attendance %"] = (df["Visits"] / days * 100).round(1)
        df = df.sort_values("Visits", ascending=False).reset_index(drop=True)
    return df


def plan_revenue(gym_id):
    return db.fetch_df(
        """SELECT COALESCE(plan_name,'-') AS 'Plan', COUNT(*) AS 'Memberships',
                  COALESCE(SUM(net_amount),0) AS 'Billed',
                  COALESCE(SUM(paid_amount),0) AS 'Collected',
                  COALESCE(SUM(due_amount),0) AS 'Outstanding'
           FROM memberships WHERE gym_id=? GROUP BY plan_name
           ORDER BY COALESCE(SUM(paid_amount),0) DESC""",
        (gym_id,))


def trainer_performance(gym_id):
    return db.fetch_df(
        """SELECT t.trainer_name AS 'Trainer', t.specialization AS 'Specialization',
                  (SELECT COUNT(*) FROM members m WHERE m.trainer_id=t.id) AS 'Members',
                  (SELECT COUNT(*) FROM personal_training pt WHERE pt.trainer_id=t.id) AS 'PT Packages',
                  (SELECT COALESCE(SUM(paid_amount),0) FROM personal_training pt
                     WHERE pt.trainer_id=t.id) AS 'PT Revenue'
           FROM trainers t WHERE t.gym_id=? ORDER BY t.trainer_name""", (gym_id,))


def profit_and_loss(gym_id, start, end):
    income = db.fetch_value("SELECT COALESCE(SUM(paid_amount),0) FROM payments "
                            "WHERE gym_id=? AND date(pay_date) BETWEEN ? AND ?",
                            (gym_id, _s(start), _s(end)))
    expense = db.fetch_value("SELECT COALESCE(SUM(amount),0) FROM expenses "
                             "WHERE gym_id=? AND date(exp_date) BETWEEN ? AND ?",
                             (gym_id, _s(start), _s(end)))
    return {"income": income, "expense": expense, "net": income - expense}


# --------------------------------------------------------------------------
# KPI page helpers
# --------------------------------------------------------------------------
def business_kpis(gym_id, warn_days=7):
    k = kpi_summary(gym_id, warn_days)
    total_revenue = db.fetch_value("SELECT COALESCE(SUM(paid_amount),0) FROM payments WHERE gym_id=?",
                                   (gym_id,))
    total_expense = db.fetch_value("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE gym_id=?",
                                   (gym_id,))
    renewals = db.fetch_value("SELECT COUNT(*) FROM memberships WHERE gym_id=? AND sale_type='Renewal'",
                              (gym_id,))
    sales = db.fetch_value("SELECT COUNT(*) FROM memberships WHERE gym_id=?", (gym_id,))
    last_month = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
    prev_members = db.fetch_value(
        "SELECT COUNT(*) FROM members WHERE gym_id=? AND date(joining_date) < ?",
        (gym_id, _s(date.today().replace(day=1))))
    growth = ((k["new_this_month"] / prev_members) * 100) if prev_members else 0

    att_days = db.fetch_value("SELECT COUNT(DISTINCT att_date) FROM attendance WHERE gym_id=?",
                              (gym_id,)) or 1
    att_total = db.fetch_value("SELECT COUNT(*) FROM attendance WHERE gym_id=?", (gym_id,))

    k.update({
        "total_revenue": total_revenue,
        "total_expenses": total_expense,
        "net_profit": total_revenue - total_expense,
        "arpm": (total_revenue / k["total_members"]) if k["total_members"] else 0,
        "renewal_rate": (renewals / sales * 100) if sales else 0,
        "expiry_rate": (k["expired_members"] / k["total_members"] * 100) if k["total_members"] else 0,
        "growth_pct": growth,
        "avg_daily_attendance": att_total / att_days,
        "attendance_pct": (att_total / (att_days * k["total_members"]) * 100)
                          if k["total_members"] else 0,
        "pt_revenue": db.fetch_value("SELECT COALESCE(SUM(paid_amount),0) FROM personal_training "
                                     "WHERE gym_id=?", (gym_id,)),
        "prev_month_start": last_month,
    })
    return k


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
def build_alerts(gym_id, warn_days=7):
    """Recompute live alerts. Returns a list of dicts, newest concern first."""
    today = date.today()
    alerts = []

    expiring = db.fetch_all(
        """SELECT m.full_name, m.mobile, ms.end_date FROM members m
           JOIN memberships ms ON ms.id=(SELECT id FROM memberships WHERE member_id=m.id
                                         ORDER BY date(end_date) DESC, id DESC LIMIT 1)
           WHERE m.gym_id=? AND date(ms.end_date) BETWEEN ? AND ?""",
        (gym_id, _s(today), _s(today + timedelta(days=warn_days))))
    for r in expiring:
        alerts.append({"type": "Membership Expiring", "severity": "warn",
                       "message": f"{r['full_name']} expires on {r['end_date']}",
                       "contact": r["mobile"]})

    expired = db.fetch_all(
        """SELECT m.full_name, m.mobile, ms.end_date FROM members m
           JOIN memberships ms ON ms.id=(SELECT id FROM memberships WHERE member_id=m.id
                                         ORDER BY date(end_date) DESC, id DESC LIMIT 1)
           WHERE m.gym_id=? AND date(ms.end_date) < ?""", (gym_id, _s(today)))
    for r in expired:
        alerts.append({"type": "Membership Expired", "severity": "bad",
                       "message": f"{r['full_name']} expired on {r['end_date']}",
                       "contact": r["mobile"]})

    dues = db.fetch_all(
        """SELECT m.full_name, m.mobile, SUM(p.due_amount) AS due FROM payments p
           JOIN members m ON m.id=p.member_id
           WHERE p.gym_id=? AND p.due_amount>0 GROUP BY m.id""", (gym_id,))
    for r in dues:
        alerts.append({"type": "Payment Due", "severity": "warn",
                       "message": f"{r['full_name']} has an outstanding balance of {r['due']:.0f}",
                       "contact": r["mobile"]})

    low = db.fetch_all("SELECT product_name, stock, low_stock_limit FROM products "
                       "WHERE gym_id=? AND stock <= low_stock_limit AND status='Active'", (gym_id,))
    for r in low:
        alerts.append({"type": "Low Stock", "severity": "warn",
                       "message": f"{r['product_name']} is down to {r['stock']:.0f} units",
                       "contact": ""})
    return alerts
