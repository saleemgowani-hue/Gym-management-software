"""
SN Gym Management System - visual theme
Developed by SN Softech Solutions

One place for the palette and CSS so every screen looks the same.
Premium corporate fitness look: deep navy rail, cool light workspace,
one accent colour per module used sparingly as a colour tab.
"""

import streamlit as st

# Menu key -> (icon, label, accent colour)
MENU = [
    ("dashboard",     "\U0001F3E0", "Dashboard",            "#3B5BFF"),
    ("members",       "\U0001F464", "Members",              "#0EA5A5"),
    ("plans",         "\U0001F4DD", "Membership Plans",     "#7C4DFF"),
    ("sales",         "\U0001F4B3", "Membership Sales",     "#2E9E5B"),
    ("renewals",      "\U0001F504", "Renewals",             "#E08A00"),
    ("attendance",    "\U0001F4C5", "Attendance",           "#0B87C4"),
    ("trainers",      "\U0001F3CB", "Trainers",             "#C2410C"),
    ("pt",            "\U0001F4AA", "Personal Training",    "#DB2777"),
    ("payments",      "\U0001F4B0", "Payments & Collections", "#16A34A"),
    ("products",      "\U0001F4E6", "Products / Supplements", "#0891B2"),
    ("expenses",      "\U0001F9FE", "Expenses",             "#B45309"),
    ("reports",       "\U0001F4CA", "Reports",              "#4F46E5"),
    ("kpi",           "\U0001F4C8", "KPI & Analytics",      "#9333EA"),
    ("notifications", "\U0001F4E2", "Notifications",        "#E11D48"),
    ("staff",         "\U0001F465", "Staff Management",     "#0F766E"),
    ("settings",      "\u2699",     "Settings",             "#475569"),
    ("license",       "\U0001F510", "License Management",   "#1D4ED8"),
]

MENU_LOOKUP = {key: (icon, label, colour) for key, icon, label, colour in MENU}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root{
  --ink:#0F2A4A; --navy:#0B1E36; --muted:#64748B; --line:#E3E8F0;
  --surface:#F4F7FC; --card:#FFFFFF;
}
html, body, [class*="css"], .stApp { font-family:'Inter',system-ui,sans-serif; }
.stApp { background:var(--surface); }
h1,h2,h3,h4 { font-family:'Manrope','Inter',sans-serif; color:var(--ink); letter-spacing:-.2px; }
#MainMenu, footer {visibility:hidden;}
.block-container{ padding-top:1.4rem; padding-bottom:3rem; max-width:1500px; }

/* ---------- Brand header ---------- */
.brand-bar{
  background:linear-gradient(100deg,#0B1E36 0%,#123A63 55%,#1D4ED8 130%);
  border-radius:16px; padding:16px 22px; margin-bottom:18px; color:#fff;
  display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;
}
.brand-bar h1{ color:#fff; font-size:1.32rem; margin:0; font-weight:800; }
.brand-bar p{ margin:2px 0 0; font-size:.8rem; color:#B9CBE6; letter-spacing:.4px; }
.brand-mark{ width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,.12);
  display:flex;align-items:center;justify-content:center;font-size:22px;margin-right:12px;}
.brand-left{display:flex;align-items:center;}
.pill{ padding:6px 14px;border-radius:999px;font-size:.78rem;font-weight:700; }
.pill-trial{ background:#FDE68A;color:#7C4A03; }
.pill-live{ background:#BBF7D0;color:#065F46; }
.pill-warn{ background:#FECACA;color:#7F1D1D; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"]{ background:var(--navy); width:288px !important; }
section[data-testid="stSidebar"] * { color:#DCE6F5; }
section[data-testid="stSidebar"] .stButton>button{
  width:100%; text-align:left; justify-content:flex-start;
  background:rgba(255,255,255,.045); color:#DCE6F5; border:1px solid rgba(255,255,255,.07);
  border-left:4px solid var(--nav,#3B5BFF); border-radius:10px;
  padding:.5rem .8rem; margin:.14rem 0; font-weight:600; font-size:.9rem;
  transition:background .15s ease, transform .15s ease;
}
section[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(255,255,255,.12); transform:translateX(3px); border-color:rgba(255,255,255,.18);
  border-left-color:var(--nav,#3B5BFF); color:#fff;
}
section[data-testid="stSidebar"] .stButton>button[kind="primary"]{
  background:var(--nav,#3B5BFF); border-color:var(--nav,#3B5BFF); color:#fff; box-shadow:0 6px 16px rgba(0,0,0,.28);
}
.side-head{ padding:6px 4px 12px; border-bottom:1px solid rgba(255,255,255,.1); margin-bottom:10px; }
.side-head .t{ font-family:'Manrope';font-weight:800;font-size:1.02rem;color:#fff; }
.side-head .s{ font-size:.72rem;color:#8FA9CC;letter-spacing:.6px;text-transform:uppercase; }
.side-user{ background:rgba(255,255,255,.06);border-radius:10px;padding:10px 12px;margin-bottom:12px; }
.side-user b{ color:#fff;font-size:.9rem; } .side-user span{ font-size:.74rem;color:#93A9C8; }
.side-foot{ margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,.1);
  font-size:.7rem;color:#7D95B8;line-height:1.5; }

/* ---------- KPI cards ---------- */
.kpi{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:14px 16px; display:flex; gap:12px; align-items:center; height:100%;
  box-shadow:0 1px 2px rgba(15,42,74,.05); border-top:3px solid var(--accent); }
.kpi-ico{ width:42px;height:42px;border-radius:11px;display:flex;align-items:center;
  justify-content:center;font-size:20px;background:color-mix(in srgb,var(--accent) 14%,white); }
.kpi-label{ font-size:.74rem;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;font-weight:600; }
.kpi-value{ font-family:'Manrope';font-size:1.42rem;font-weight:800;color:var(--ink);line-height:1.15; }
.kpi-sub{ font-size:.72rem;color:var(--muted); }

/* ---------- Page header ---------- */
.page-head{ display:flex;gap:12px;align-items:center;margin:2px 0 14px; }
.page-ico{ width:40px;height:40px;border-radius:11px;background:#E8EEFC;display:flex;
  align-items:center;justify-content:center;font-size:20px; }
.page-head h2{ margin:0;font-size:1.22rem; } .page-head p{ margin:0;color:var(--muted);font-size:.82rem; }

/* ---------- Panels, tables, forms ---------- */
.panel{ background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:14px; }
div[data-testid="stDataFrame"]{ border:1px solid var(--line);border-radius:12px;overflow:hidden; }
.stTabs [data-baseweb="tab-list"]{ gap:4px;border-bottom:1px solid var(--line); }
.stTabs [data-baseweb="tab"]{ border-radius:9px 9px 0 0;padding:6px 16px;font-weight:600;font-size:.88rem; }
.stTabs [aria-selected="true"]{ background:#E8EEFC;color:var(--ink); }
.stButton>button{ border-radius:9px;font-weight:600; }
div[data-testid="stForm"]{ border:1px solid var(--line);border-radius:14px;background:var(--card);padding:16px 18px; }
.empty{ border:1px dashed #C9D6EA;border-radius:14px;padding:34px;text-align:center;background:#FBFDFF; }
.empty-t{ font-family:'Manrope';font-weight:700;color:var(--ink);font-size:1rem; }
.empty-h{ color:var(--muted);font-size:.84rem;margin-top:4px; }
.lock-card{ background:var(--card);border:1px solid var(--line);border-top:5px solid #E11D48;
  border-radius:16px;padding:26px 28px;max-width:760px;margin:8px auto 18px; }
.app-foot{ text-align:center;color:var(--muted);font-size:.76rem;margin-top:26px;
  padding-top:14px;border-top:1px solid var(--line); }
.auth-hero{ background:linear-gradient(155deg,#0B1E36,#164B85);border-radius:18px;color:#fff;
  padding:30px 28px;height:100%; }
.auth-hero h2{ color:#fff;font-size:1.5rem;margin:0 0 8px; }
.auth-hero li{ margin:7px 0;font-size:.9rem;color:#CBDCF3; }
/* ---------- Tablet ---------- */
@media (max-width:1024px){
  .block-container{ padding-left:1.1rem; padding-right:1.1rem; }
  section[data-testid="stSidebar"]{ width:250px !important; }
  .kpi-value{ font-size:1.25rem; }
  .kpi-ico{ width:38px;height:38px;font-size:18px; }
}

/* ---------- Phone ---------- */
@media (max-width:640px){
  .block-container{ padding:0.7rem 0.7rem 2rem; }
  .brand-bar{ padding:12px 14px; border-radius:12px; }
  .brand-bar h1{ font-size:1.02rem; } .brand-bar p{ font-size:.68rem; }
  .brand-mark{ width:34px;height:34px;font-size:17px;margin-right:9px; }
  /* KPI cards stack, so make them short and wide instead of tall */
  .kpi{ padding:10px 12px; gap:10px; }
  .kpi-ico{ width:34px;height:34px;font-size:16px;border-radius:9px; }
  .kpi-value{ font-size:1.15rem; } .kpi-label{ font-size:.68rem; }
  .page-head h2{ font-size:1.05rem; } .page-ico{ width:34px;height:34px;font-size:17px; }
  .panel{ padding:12px 13px; }
  /* Wide report tables scroll sideways instead of squashing */
  div[data-testid="stDataFrame"]{ overflow-x:auto; }
  .stTabs [data-baseweb="tab-list"]{ overflow-x:auto; flex-wrap:nowrap; }
  .stTabs [data-baseweb="tab"]{ padding:6px 11px; font-size:.82rem; white-space:nowrap; }
  section[data-testid="stSidebar"]{ width:82vw !important; }
  section[data-testid="stSidebar"] .stButton>button{ padding:.62rem .8rem; font-size:.95rem; }
  /* Comfortable tap targets on glass */
  .stButton>button, div[data-testid="stDownloadButton"] button{ min-height:44px; }
  .empty{ padding:22px 14px; }
  .app-foot{ font-size:.7rem; }
}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def nav_colour_css():
    """Per-button accent colours, applied through Streamlit's st-key-* classes."""
    rules = "".join(
        f".st-key-nav_{key} button{{--nav:{colour};}}" for key, _i, _l, colour in MENU)
    rules += ".st-key-nav_logout button{--nav:#94A3B8;}"
    st.markdown(f"<style>{rules}</style>", unsafe_allow_html=True)
