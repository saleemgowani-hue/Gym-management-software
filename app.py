"""
SN Gym Management System
Developed by SN Softech Solutions

Entry point. Handles the session, the sign in / sign up screens, the
licence gate, the sidebar and page routing.

Run with:  streamlit run app.py
"""

import streamlit as st

import auth
import database as db
import demo_setup
import license_manager as lm
import theme
from modules import (attendance, dashboard, expenses, members, membership,
                     notifications, payments, products, reports_ui, settings,
                     trainers)

APP_NAME = "SN Gym Management System"
COMPANY = "SN Softech Solutions"
VERSION = "1.0.0"

st.set_page_config(page_title=APP_NAME, page_icon="\U0001F3CB", layout="wide",
                   initial_sidebar_state="auto")   # 'auto' keeps the sidebar
                                                   # collapsed on phones, open on desktop

db.init_db()
theme.inject()


@st.cache_resource(show_spinner=False)
def _bootstrap_demo():
    """Runs once per server start: builds the demo gym when DEMO_MODE is on."""
    if demo_setup.demo_mode():
        try:
            return demo_setup.ensure_demo()
        except Exception:
            return None
    return None


_bootstrap_demo()


# --------------------------------------------------------------------------
# Session helpers
# --------------------------------------------------------------------------
def boot_session():
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("page", "dashboard")
    st.session_state.setdefault("auth_view", "signin")
    st.session_state.setdefault("currency", "INR")
    st.session_state.setdefault("profile_member", None)
    if st.session_state.user and not st.session_state.get("gym"):
        load_gym()


def load_gym():
    gym = db.fetch_one("SELECT * FROM gyms WHERE id=?", (st.session_state.user["gym_id"],))
    st.session_state.gym = gym or {}
    st.session_state.currency = (gym or {}).get("currency", "INR")


def sign_out():
    user = st.session_state.get("user")
    if user:
        db.log_action(user["gym_id"], user, "LOGOUT", "Signed out")
    for key in ("user", "gym", "page", "profile_member"):
        st.session_state.pop(key, None)
    st.session_state.auth_view = "signin"
    st.rerun()


def brand_bar(right_html=""):
    st.markdown(
        f"""<div class="brand-bar">
              <div class="brand-left"><div class="brand-mark">\U0001F3CB</div>
                <div><h1>{APP_NAME}</h1><p>DEVELOPED BY {COMPANY.upper()}</p></div></div>
              <div>{right_html}</div>
            </div>""", unsafe_allow_html=True)


def footer():
    st.markdown(
        f"""<div class="app-foot">{APP_NAME} v{VERSION} &nbsp;|&nbsp; Developed by
        <strong>{COMPANY}</strong> &nbsp;|&nbsp; All rights reserved</div>""",
        unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Authentication screens
# --------------------------------------------------------------------------
def screen_auth():
    brand_bar('<span class="pill pill-live">LICENSED SOFTWARE</span>')
    left, right = st.columns([1.05, 1])

    with left:
        st.markdown(
            """<div class="auth-hero">
                 <h2>Run your gym, not your paperwork.</h2>
                 <p style="color:#CBDCF3;font-size:.92rem">
                   Members, plans, attendance, collections and business analytics in one place.</p>
                 <ul>
                   <li>Member records with photos, plans and expiry tracking</li>
                   <li>One-click renewals and printable receipts</li>
                   <li>Daily attendance and trainer allocation</li>
                   <li>Collections, dues, expenses and net profit</li>
                   <li>KPI dashboard built for gym owners</li>
                 </ul>
                 <p style="color:#8FA9CC;font-size:.8rem;margin-top:18px">
                   Licensed software from SN Softech Solutions. Register your gym,
                   then activate your licence key to begin.</p>
               </div>""", unsafe_allow_html=True)

    with right:
        view = st.session_state.auth_view
        if view == "signup":
            form_signup()
        elif view == "forgot":
            form_forgot()
        else:
            form_signin()
    footer()


def form_signin():
    st.subheader("Sign in")

    st.info(
        f"**Try the live demo** — username `{demo_setup.DEMO_USER}`, password "
        f"`{demo_setup.DEMO_PASSWORD}` (full Admin access). "
        f"A limited receptionist login is `{demo_setup.DEMO_STAFF_USER}` / "
        f"`{demo_setup.DEMO_STAFF_PASSWORD}`.")
    if st.button("Sign in to the demo gym", type="primary", use_container_width=True,
                 key="demo_login"):
        demo_setup.ensure_demo()
        user, _msg = auth.login(demo_setup.DEMO_USER, demo_setup.DEMO_PASSWORD)
        if user:
            st.session_state.user = user
            load_gym()
            st.rerun()
        else:
            st.error("The demo account could not be opened. Please try the form below.")
    st.caption("The demo is shared and resets from time to time, so please do not "
               "enter real member data.")
    with st.form("signin_form"):
        identifier = st.text_input("Username or email")
        password = st.text_input("Password", type="password")
        remember = st.checkbox("Keep me signed in on this device")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        if not identifier or not password:
            st.error("Enter your username and password to continue.")
        else:
            user, message = auth.login(identifier, password)
            if user:
                st.session_state.user = user
                st.session_state.remember = remember
                load_gym()
                st.rerun()
            else:
                st.error(message)

    col1, col2 = st.columns(2)
    if col1.button("Create a gym account", use_container_width=True):
        st.session_state.auth_view = "signup"
        st.rerun()
    if col2.button("Forgot password", use_container_width=True):
        st.session_state.auth_view = "forgot"
        st.rerun()


def form_signup():
    st.subheader("Create your gym account")
    st.caption("Register the gym first, then activate your licence key to unlock the software.")
    with st.form("signup_form"):
        c1, c2 = st.columns(2)
        gym_name = c1.text_input("Gym / business name *")
        owner = c2.text_input("Owner name *")
        mobile = c1.text_input("Mobile number *")
        email = c2.text_input("Email *")
        username = c1.text_input("Username *")
        question = c2.selectbox("Security question",
                                ["Your first trainer's name?", "Your city of birth?",
                                 "Your favourite exercise?", "Your pet's name?"])
        password = c1.text_input("Password *", type="password")
        confirm = c2.text_input("Confirm password *", type="password")
        answer = st.text_input("Answer to the security question *",
                               help="Used if you ever need to reset your password.")
        submitted = st.form_submit_button("Create account", type="primary",
                                          use_container_width=True)

    if submitted:
        import utils
        errors = utils.require({"Gym name": gym_name, "Owner name": owner, "Mobile": mobile,
                                "Email": email, "Username": username, "Password": password,
                                "Security answer": answer})
        if mobile and not utils.valid_mobile(mobile):
            errors.append("Enter a valid mobile number (7 to 15 digits).")
        if email and not utils.valid_email(email):
            errors.append("Enter a valid email address.")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("The two passwords do not match.")
        if errors:
            st.error("  \n".join(f"\u2022 {e}" for e in errors))
        else:
            ok, result = auth.register_gym(gym_name, owner, mobile, email, username,
                                           password, question, answer)
            if not ok:
                st.error(result)
            else:
                user, _ = auth.login(username, password)
                st.session_state.user = user
                load_gym()
                st.success("Account created. Enter your licence key on the next screen to start.")
                st.rerun()

    if st.button("Back to sign in", use_container_width=True):
        st.session_state.auth_view = "signin"
        st.rerun()


def form_forgot():
    st.subheader("Reset your password")
    st.caption("Answer your security question to set a new password.")
    identifier = st.text_input("Username or email", key="fp_id")
    user = None
    if identifier:
        user = db.fetch_one("SELECT security_question FROM users "
                            "WHERE lower(username)=lower(?) OR lower(email)=lower(?)",
                            (identifier.strip(), identifier.strip()))
        if user and user["security_question"]:
            st.info(f"Security question: **{user['security_question']}**")
    with st.form("forgot_form"):
        answer = st.text_input("Your answer")
        new_pw = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update password", type="primary",
                                          use_container_width=True)
    if submitted:
        if not identifier or not answer or not new_pw:
            st.error("Fill in every field to reset your password.")
        elif len(new_pw) < 6:
            st.error("Password must be at least 6 characters.")
        elif new_pw != confirm:
            st.error("The two passwords do not match.")
        else:
            ok, message = auth.reset_password(identifier, answer, new_pw)
            (st.success if ok else st.error)(message)
    if st.button("Back to sign in", key="fp_back", use_container_width=True):
        st.session_state.auth_view = "signin"
        st.rerun()


# --------------------------------------------------------------------------
# Licence gate
# --------------------------------------------------------------------------
def screen_locked(status):
    brand_bar('<span class="pill pill-warn">ACCESS LOCKED</span>')
    gym = st.session_state.gym
    headline = {
        "UNLICENSED": "Activate your licence to start using the software.",
        "LICENSE_EXPIRED": "Your Gym Management Software License has expired.",
        "TAMPERED": "The system clock was changed on this computer.",
        "NONE": "No licence record was found for this gym.",
    }.get(status["state"], "Your licence needs attention.")

    st.markdown(
        f"""<div class="lock-card">
              <h2 style="margin-top:0">{headline}</h2>
              <p style="color:#64748B">Your data is safe and untouched. Enter the licence
              key issued for this gym to unlock every module.</p>
              <p style="font-size:.9rem"><strong>Gym:</strong> {gym.get('gym_name','-')} &nbsp;
              <strong>Registered mobile:</strong> {gym.get('mobile','-')} &nbsp;
              <strong>Licence expiry:</strong> {status.get('expiry_date') or 'not activated yet'}</p>
              <p style="font-size:.85rem;color:#64748B">To buy a licence key, contact
              {lm.SUPPORT_CONTACT}</p>
            </div>""", unsafe_allow_html=True)

    st.markdown("#### Activate your licence")
    with st.form("activate_locked"):
        c1, c2 = st.columns(2)
        key = c1.text_input("License key", placeholder="SNGYM-XXXX-XXXX-XXXX-XXXX")
        gym_name = c2.text_input("Gym name", value=gym.get("gym_name", ""))
        mobile = c1.text_input("Registered mobile", value=gym.get("mobile", ""))
        c2.text_input("Activation date", value="Today", disabled=True)
        submitted = st.form_submit_button("Activate license", type="primary",
                                          use_container_width=True)
    if submitted:
        ok, message = lm.activate(gym["id"], key, gym_name, mobile)
        if ok:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    if st.button("Sign out"):
        sign_out()
    footer()


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
def sidebar(status):
    user = st.session_state.user
    gym = st.session_state.gym
    with st.sidebar:
        st.markdown(
            f"""<div class="side-head"><div class="t">{gym.get('gym_name', APP_NAME)}</div>
                <div class="s">SN Gym Management</div></div>""", unsafe_allow_html=True)
        st.markdown(
            f"""<div class="side-user"><b>{user.get('full_name') or user['username']}</b><br>
                <span>{user['role']} &middot; @{user['username']}</span></div>""",
            unsafe_allow_html=True)

        badge = "pill-live" if status["state"] == "LICENSED" else "pill-warn"
        text = (f"LICENSED - {status['days_left']} DAYS LEFT"
                if status["state"] == "LICENSED" else status["label"].upper())
        st.markdown(f"<div style='margin-bottom:10px'><span class='pill {badge}'>{text}</span></div>",
                    unsafe_allow_html=True)

        theme.nav_colour_css()
        for key, icon, label, _colour in theme.MENU:
            if not auth.can_access(user["role"], key):
                continue
            active = st.session_state.page == key
            if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.page = key
                st.session_state.profile_member = None
                st.rerun()

        if st.button("\U0001F6AA  Logout", key="nav_logout", use_container_width=True):
            sign_out()

        st.markdown(
            f"""<div class="side-foot">{APP_NAME} v{VERSION}<br>
                Developed by <strong>{COMPANY}</strong></div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------
ROUTES = {
    "dashboard": dashboard.page,
    "members": members.page,
    "plans": membership.page_plans,
    "sales": membership.page_sales,
    "renewals": membership.page_renewals,
    "attendance": attendance.page,
    "trainers": trainers.page_trainers,
    "pt": trainers.page_personal_training,
    "payments": payments.page,
    "products": products.page,
    "expenses": expenses.page,
    "reports": reports_ui.page_reports,
    "kpi": reports_ui.page_kpi,
    "notifications": notifications.page,
    "staff": settings.page_staff,
    "settings": settings.page_settings,
    "license": settings.page_license,
}


def main():
    boot_session()

    if not st.session_state.user:
        screen_auth()
        return

    gym_id = st.session_state.user["gym_id"]
    status = lm.get_status(gym_id)
    st.session_state.license_status = status

    # Admins can always reach the licence screen; everyone else is blocked.
    if status["locked"]:
        screen_locked(status)
        return

    sidebar(status)

    if status["state"] == "LICENSED":
        right = f'<span class="pill pill-live">LICENSED - {status["days_left"]} DAYS LEFT</span>'
    else:
        right = f'<span class="pill pill-warn">{status["label"]}</span>'
    brand_bar(right)

    if status["state"] == "LICENSED" and status["days_left"] <= 15:
        st.warning(f"Your licence expires in {status['days_left']} day(s). Renew it to avoid a lockout.")

    page_key = st.session_state.page
    if not auth.can_access(st.session_state.user["role"], page_key):
        st.error("Your role does not have access to this section. Pick another item from the menu.")
        page_key = "dashboard"
        st.session_state.page = "dashboard"

    try:
        ROUTES.get(page_key, dashboard.page)()
    except Exception as exc:                      # never show a raw traceback
        st.error("Something went wrong while loading this screen. "
                 "Nothing was saved, and your data is safe.")
        st.caption(f"Technical detail: {type(exc).__name__}: {exc}")
        db.log_action(gym_id, st.session_state.user, "ERROR", f"{page_key}: {exc}")

    footer()


if __name__ == "__main__":
    main()
