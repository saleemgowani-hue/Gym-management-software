"""
SN Gym Management System - shared helpers
Developed by SN Softech Solutions
"""

import base64
import io
import os
import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import database as db

CURRENCY_SYMBOLS = {"INR": "\u20b9", "USD": "$", "EUR": "\u20ac", "GBP": "\u00a3", "AED": "AED "}


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def valid_mobile(value):
    digits = re.sub(r"\D", "", value or "")
    return 7 <= len(digits) <= 15


def valid_email(value):
    if not value:
        return True                      # email is optional in most forms
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$", value.strip()))


def require(fields: dict):
    """fields = {'Full Name': value, ...} -> list of friendly error messages."""
    errors = []
    for label, value in fields.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{label} is required.")
    return errors


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------
def currency_symbol():
    return CURRENCY_SYMBOLS.get(st.session_state.get("currency", "INR"), "\u20b9")


def money(value):
    try:
        return f"{currency_symbol()}{float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return f"{currency_symbol()}0"


def fmt_date(value):
    if not value:
        return "-"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d-%b-%Y")
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
    except Exception:
        return str(value)


def to_date(value, default=None):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return default


def add_months(start: date, months: float):
    """End date = start + duration. Handles half-month plans and month overflow."""
    whole = int(months)
    extra_days = int(round((months - whole) * 30))
    year = start.year + (start.month - 1 + whole) // 12
    month = (start.month - 1 + whole) % 12 + 1
    day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                          31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day) + timedelta(days=extra_days - 1)


def date_range_picker(key_prefix, default="This Month"):
    """Shared Today / Week / Month / Year / Custom filter. Returns (start, end, label)."""
    options = ["Today", "This Week", "This Month", "This Year", "Custom Range", "All Time"]
    choice = st.selectbox("Period", options, index=options.index(default),
                          key=f"{key_prefix}_period")
    today = date.today()
    if choice == "Today":
        start = end = today
    elif choice == "This Week":
        start, end = today - timedelta(days=today.weekday()), today
    elif choice == "This Month":
        start, end = today.replace(day=1), today
    elif choice == "This Year":
        start, end = today.replace(month=1, day=1), today
    elif choice == "All Time":
        start, end = date(2000, 1, 1), date(2999, 12, 31)
    else:
        col1, col2 = st.columns(2)
        start = col1.date_input("From", today.replace(day=1), key=f"{key_prefix}_from")
        end = col2.date_input("To", today, key=f"{key_prefix}_to")
    return start, end, choice


# --------------------------------------------------------------------------
# Membership status
# --------------------------------------------------------------------------
def membership_status(end_date, due=0, warn_days=7):
    end = to_date(end_date)
    if due and float(due) > 0:
        base = "Payment Due"
    else:
        base = None
    if not end:
        return base or "No Membership"
    today = date.today()
    if end < today:
        return "Expired"
    if (end - today).days <= warn_days:
        return "Expiring Soon"
    return base or "Active"


STATUS_COLORS = {
    "Active": "#0f9d58", "Expiring Soon": "#f4a112", "Expired": "#d93025",
    "Payment Due": "#7e3ff2", "No Membership": "#6b7280",
}


def status_badge(status):
    color = STATUS_COLORS.get(status, "#6b7280")
    return (f"<span style='background:{color}1a;color:{color};padding:3px 10px;"
            f"border-radius:999px;font-size:.78rem;font-weight:700;'>{status}</span>")


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
def df_to_excel(dfs: dict):
    """dfs = {'Sheet name': dataframe}. Returns xlsx bytes."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet, frame in dfs.items():
            (frame if not frame.empty else pd.DataFrame({"Info": ["No records"]})) \
                .to_excel(writer, sheet_name=str(sheet)[:31], index=False)
    return buffer.getvalue()


def excel_download(df, filename, label="Export to Excel", key=None):
    st.download_button(label, data=df_to_excel({"Data": df}),
                       file_name=f"{filename}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=key, use_container_width=True)


def html_report(title, subtitle, body_html, gym=None):
    """Wrap content in a clean print-friendly page."""
    gym = gym or {}
    footer = gym.get("receipt_footer") or "Thank you for training with us!"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
 body{{font-family:'Segoe UI',Arial,sans-serif;color:#1f2937;margin:28px;}}
 h1{{font-size:20px;margin:0;color:#0f2a4a}} h2{{font-size:14px;font-weight:500;color:#64748b;margin:4px 0 18px}}
 .hd{{border-bottom:3px solid #0f2a4a;padding-bottom:10px;margin-bottom:18px;
     display:flex;justify-content:space-between;align-items:flex-end}}
 table{{width:100%;border-collapse:collapse;font-size:12.5px}}
 th{{background:#0f2a4a;color:#fff;text-align:left;padding:8px}}
 td{{border-bottom:1px solid #e5e7eb;padding:7px 8px}}
 tr:nth-child(even) td{{background:#f8fafc}}
 .tot{{margin-top:16px;font-size:14px;font-weight:700;text-align:right}}
 .ft{{margin-top:30px;border-top:1px solid #e5e7eb;padding-top:10px;font-size:11px;color:#6b7280;
     display:flex;justify-content:space-between}}
 @media print{{.noprint{{display:none}}}}
</style></head><body>
<div class="hd"><div><h1>{gym.get('gym_name','SN Gym Management System')}</h1>
<div style="font-size:12px;color:#64748b">{gym.get('address','')} {('| ' + gym.get('mobile','')) if gym.get('mobile') else ''}</div></div>
<div style="text-align:right"><strong>{title}</strong><br><span style="font-size:12px;color:#64748b">{subtitle}</span></div></div>
{body_html}
<div class="ft"><span>{footer}</span><span>SN Gym Management System &middot; SN Softech Solutions</span></div>
<button class="noprint" onclick="window.print()"
 style="margin-top:18px;padding:9px 20px;border:0;border-radius:8px;background:#0f2a4a;color:#fff;cursor:pointer">
 Print this page</button>
</body></html>"""


def print_button(html, filename, label="Open print view", key=None):
    """Downloads a self-contained HTML page the user can print from the browser."""
    st.download_button(label, data=html.encode("utf-8"), file_name=f"{filename}.html",
                       mime="text/html", key=key, use_container_width=True)


def receipt_html(gym, member, sale, kind="Membership Receipt"):
    rows = [
        ("Receipt No", sale.get("invoice_no", "-")),
        ("Date", fmt_date(sale.get("created_at") or date.today())),
        ("Member", f"{member.get('full_name','-')} ({member.get('member_code','-')})"),
        ("Mobile", member.get("mobile", "-")),
        ("Plan / Package", sale.get("plan_name", "-")),
        ("Period", f"{fmt_date(sale.get('start_date'))} to {fmt_date(sale.get('end_date'))}"),
        ("Amount", money(sale.get("amount"))),
        ("Discount", money(sale.get("discount"))),
        ("Net Payable", money(sale.get("net_amount"))),
        ("Paid", money(sale.get("paid_amount"))),
        ("Balance Due", money(sale.get("due_amount"))),
        ("Payment Mode", sale.get("payment_mode", "-")),
    ]
    body = "<table>" + "".join(
        f"<tr><td style='width:40%;color:#64748b'>{k}</td><td><strong>{v}</strong></td></tr>"
        for k, v in rows) + "</table>"
    if gym.get("gst_number"):
        body += f"<p style='font-size:12px;color:#64748b'>GSTIN: {gym['gst_number']}</p>"
    return html_report(kind, sale.get("invoice_no", ""), body, gym)


def table_html(df: pd.DataFrame, total_col=None):
    if df is None or df.empty:
        return "<p>No records found for this selection.</p>"
    head = "".join(f"<th>{c}</th>" for c in df.columns)
    body = "".join("<tr>" + "".join(f"<td>{'' if pd.isna(v) else v}</td>" for v in row) + "</tr>"
                   for row in df.itertuples(index=False))
    html = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    if total_col and total_col in df.columns:
        html += f"<div class='tot'>Total {total_col}: {money(pd.to_numeric(df[total_col], errors='coerce').sum())}</div>"
    return html


# --------------------------------------------------------------------------
# Invoice numbers
# --------------------------------------------------------------------------
def next_invoice(gym_id, prefix="INV"):
    count = db.fetch_value(
        "SELECT COUNT(*) FROM payments WHERE gym_id=? AND invoice_no LIKE ?",
        (gym_id, f"{prefix}%"))
    return f"{prefix}-{datetime.now().strftime('%y%m')}-{int(count) + 1:04d}"


def next_member_code(gym_id):
    count = db.fetch_value("SELECT COUNT(*) FROM members WHERE gym_id=?", (gym_id,))
    return f"M{int(count) + 1:04d}"


# --------------------------------------------------------------------------
# Small UI helpers
# --------------------------------------------------------------------------
def kpi_card(label, value, icon="", accent="#2563eb", sub=""):
    st.markdown(
        f"""<div class="kpi" style="--accent:{accent}">
              <div class="kpi-ico">{icon}</div>
              <div class="kpi-body">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{sub}</div>
              </div>
            </div>""", unsafe_allow_html=True)


def page_header(title, subtitle="", icon=""):
    st.markdown(
        f"""<div class="page-head"><div class="page-ico">{icon}</div>
            <div><h2>{title}</h2><p>{subtitle}</p></div></div>""",
        unsafe_allow_html=True)


def empty_state(message, hint=""):
    st.markdown(
        f"""<div class="empty"><div class="empty-t">{message}</div>
            <div class="empty-h">{hint}</div></div>""", unsafe_allow_html=True)


def save_photo(uploaded, member_code):
    if not uploaded:
        return None
    ext = os.path.splitext(uploaded.name)[1].lower() or ".png"
    path = os.path.join(db.PHOTO_DIR, f"{member_code}{ext}")
    with open(path, "wb") as fh:
        fh.write(uploaded.getbuffer())
    return path


def photo_or_placeholder(path, size=140):
    if path and os.path.exists(path):
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        return (f"<img src='data:image/png;base64,{b64}' style='width:{size}px;height:{size}px;"
                f"object-fit:cover;border-radius:14px;border:3px solid #e2e8f0'>")
    return (f"<div style='width:{size}px;height:{size}px;border-radius:14px;background:#e8eefc;"
            f"display:flex;align-items:center;justify-content:center;font-size:{size//3}px'>&#128100;</div>")


def toast_ok(message):
    """Success feedback. The toast survives the st.rerun() that follows a save,
    so the user always sees confirmation."""
    st.success(message, icon="\u2705")
    try:
        st.toast(message, icon="\u2705")
    except Exception:
        pass


def toast_err(message):
    st.error(message, icon="\u26a0\ufe0f")
    try:
        st.toast(message, icon="\u26a0\ufe0f")
    except Exception:
        pass


def confirm(key, label="Yes, I am sure"):
    """Simple inline confirmation checkbox used before destructive actions."""
    return st.checkbox(label, key=key)


def member_options(gym_id, active_only=False):
    sql = "SELECT id, member_code, full_name, mobile FROM members WHERE gym_id=?"
    if active_only:
        sql += " AND status='Active'"
    rows = db.fetch_all(sql + " ORDER BY full_name", (gym_id,))
    return {f"{r['full_name']} ({r['member_code']}) - {r['mobile'] or 'no mobile'}": r["id"]
            for r in rows}


def trainer_options(gym_id):
    rows = db.fetch_all("SELECT id, trainer_name FROM trainers WHERE gym_id=? AND status='Active' "
                        "ORDER BY trainer_name", (gym_id,))
    return {r["trainer_name"]: r["id"] for r in rows}
