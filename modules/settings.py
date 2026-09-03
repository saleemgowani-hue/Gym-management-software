"""
SN Gym Management System - Staff, Settings & License Management
Developed by SN Softech Solutions
"""

import streamlit as st

import auth
import database as db
import demo_data
import license_manager as lm
import utils

CURRENCIES = list(utils.CURRENCY_SYMBOLS.keys())


# --------------------------------------------------------------------------
# Staff management (Admin only)
# --------------------------------------------------------------------------
def page_staff():
    user = st.session_state.user
    gym_id = user["gym_id"]
    utils.page_header("Staff Management", "Create logins for your team and control access.",
                      "\U0001F465")

    if user["role"] != "Admin":
        st.error("Only Admins can manage staff accounts.")
        return

    tab_list, tab_add = st.tabs(["All Staff", "Add Staff"])

    with tab_list:
        rows = db.fetch_all("SELECT id, full_name, username, email, mobile, role, is_active, "
                            "last_login FROM users WHERE gym_id=? ORDER BY id", (gym_id,))
        for r in rows:
            c = st.columns([3, 2, 2, 2, 1])
            c[0].markdown(f"**{r['full_name'] or r['username']}**  \n<span style='color:#64748B;"
                         f"font-size:.8rem'>@{r['username']}</span>", unsafe_allow_html=True)
            c[1].write(r["role"])
            c[2].write(r["mobile"] or r["email"] or "-")
            c[3].write(f"Last login: {utils.fmt_date(r['last_login']) if r['last_login'] else 'Never'}")
            if r["id"] == user["id"]:
                c[4].caption("You")
                continue
            label = "Deactivate" if r["is_active"] else "Activate"
            if c[4].button(label, key=f"staff_toggle_{r['id']}", use_container_width=True):
                db.execute("UPDATE users SET is_active=? WHERE id=?",
                          (0 if r["is_active"] else 1, r["id"]))
                st.rerun()

    with tab_add:
        with st.form("staff_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            full_name = c1.text_input("Full Name *")
            username = c2.text_input("Username *")
            email = c1.text_input("Email")
            mobile = c2.text_input("Mobile")
            role = c1.selectbox("Role *", [r for r in db.ROLES if r != "Admin"])
            password = c2.text_input("Password *", type="password")
            submitted = st.form_submit_button("Create Login", type="primary", use_container_width=True)
        if submitted:
            errors = utils.require({"Full Name": full_name, "Username": username, "Password": password})
            if password and len(password) < 6:
                errors.append("Password must be at least 6 characters.")
            if errors:
                utils.toast_err("  \n".join(errors))
            else:
                ok, message = auth.create_user(gym_id, full_name, username, email, mobile,
                                               password, role)
                if ok:
                    db.log_action(gym_id, user, "STAFF_CREATED", f"{username} ({role})")
                    utils.toast_ok(f"Login created for {username}.")
                    st.rerun()
                else:
                    utils.toast_err(message)


# --------------------------------------------------------------------------
# Gym settings
# --------------------------------------------------------------------------
def page_settings():
    user = st.session_state.user
    gym_id = user["gym_id"]
    utils.page_header("Settings", "Gym profile, preferences, backups and demo data.", "⚙")

    tabs = st.tabs(["Gym Profile", "My Account", "Backup & Restore", "Demo Data"])

    with tabs[0]:
        _profile(gym_id)
    with tabs[1]:
        _account(user)
    with tabs[2]:
        _backup(gym_id, user)
    with tabs[3]:
        _demo(gym_id, user)


def _profile(gym_id):
    gym = db.fetch_one("SELECT * FROM gyms WHERE id=?", (gym_id,))
    with st.form("gym_profile_form"):
        c1, c2 = st.columns(2)
        gym_name = c1.text_input("Gym Name *", value=gym.get("gym_name", ""))
        owner_name = c2.text_input("Owner Name", value=gym.get("owner_name", ""))
        mobile = c1.text_input("Mobile", value=gym.get("mobile", ""))
        email = c2.text_input("Email", value=gym.get("email", ""))
        address = st.text_area("Address", value=gym.get("address", ""), height=70)
        gst_number = c1.text_input("GST Number", value=gym.get("gst_number", ""))
        currency = c2.selectbox("Currency", CURRENCIES,
                                index=CURRENCIES.index(gym.get("currency", "INR"))
                                if gym.get("currency") in CURRENCIES else 0)
        notify_days = c1.number_input("Notify before expiry (days)", min_value=1, max_value=60,
                                      value=int(gym.get("notify_expiry_days") or 7))
        receipt_footer = st.text_input("Receipt Footer", value=gym.get("receipt_footer", ""))
        logo = st.file_uploader("Gym Logo", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("Save Changes", type="primary", use_container_width=True)

    if not submitted:
        return
    errors = utils.require({"Gym Name": gym_name})
    if email and not utils.valid_email(email):
        errors.append("Enter a valid email address.")
    if errors:
        utils.toast_err("  \n".join(errors))
        return
    logo_path = gym.get("logo_path")
    if logo:
        import os
        ext = os.path.splitext(logo.name)[1].lower() or ".png"
        logo_path = os.path.join(db.ASSET_DIR, f"gym_{gym_id}{ext}")
        with open(logo_path, "wb") as fh:
            fh.write(logo.getbuffer())
    db.execute(
        """UPDATE gyms SET gym_name=?, owner_name=?, mobile=?, email=?, address=?, gst_number=?,
               currency=?, notify_expiry_days=?, receipt_footer=?, logo_path=? WHERE id=?""",
        (gym_name.strip(), owner_name, mobile, email, address, gst_number, currency,
         notify_days, receipt_footer, logo_path, gym_id))
    st.session_state.gym = db.fetch_one("SELECT * FROM gyms WHERE id=?", (gym_id,))
    st.session_state.currency = currency
    utils.toast_ok("Gym profile updated.")
    st.rerun()


def _account(user):
    st.markdown(f"**Username:** @{user['username']}  |  **Role:** {user['role']}")
    with st.form("change_password_form", clear_on_submit=True):
        old_password = st.text_input("Current Password", type="password")
        c1, c2 = st.columns(2)
        new_password = c1.text_input("New Password", type="password")
        confirm = c2.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password", type="primary", use_container_width=True)
    if submitted:
        if not old_password or not new_password:
            utils.toast_err("Fill in every field.")
        elif len(new_password) < 6:
            utils.toast_err("New password must be at least 6 characters.")
        elif new_password != confirm:
            utils.toast_err("The two passwords do not match.")
        else:
            ok, message = auth.change_password(user["id"], old_password, new_password)
            (utils.toast_ok if ok else utils.toast_err)(message)


def _backup(gym_id, user):
    st.markdown(f"**Active database:** {db.backend_label()}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create Database Backup", type="primary", use_container_width=True):
            path = db.create_backup()
            db.log_action(gym_id, user, "BACKUP_CREATED", path)
            utils.toast_ok(f"Backup saved: {path}")
            st.rerun()
    with c2:
        if not db.is_postgres():
            uploaded = st.file_uploader("Restore from a .db backup file", type=["db"])
            if uploaded is not None and utils.confirm("restore_confirm",
                                                       "Yes, replace the current database"):
                if st.button("Restore Now", type="primary"):
                    try:
                        safety = db.restore_backup(uploaded.getbuffer().tobytes())
                        db.log_action(gym_id, user, "BACKUP_RESTORED", safety)
                        utils.toast_ok("Database restored. The previous copy was saved as a safety backup.")
                        st.rerun()
                    except Exception as exc:
                        utils.toast_err(f"Restore failed: {exc}")

    st.markdown("##### Recent backups")
    backups = db.list_backups()
    if not backups:
        utils.empty_state("No backups yet.")
        return
    for b in backups[:15]:
        c = st.columns([3, 2, 2, 1])
        c[0].write(b["file"])
        c[1].write(f"{b['size_kb']} KB")
        c[2].write(b["created"])
        with open(b["path"], "rb") as fh:
            c[3].download_button("Download", data=fh.read(), file_name=b["file"],
                                 key=f"dl_{b['file']}", use_container_width=True)


def _demo(gym_id, user):
    st.caption("Load a sample gym (members, trainers, attendance, sales, expenses, products) to "
              "explore the software, or clear it again. Only rows tagged as demo data are ever "
              "added or removed - your real data is never touched.")
    loaded = demo_data.already_loaded(gym_id)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load Demo Data", disabled=loaded, use_container_width=True, type="primary"):
            summary = demo_data.load(gym_id)
            db.log_action(gym_id, user, "DEMO_DATA_LOADED", summary)
            utils.toast_ok(summary)
            st.rerun()
    with c2:
        if st.button("Clear Demo Data", disabled=not loaded, use_container_width=True):
            count = demo_data.clear_demo(gym_id)
            db.log_action(gym_id, user, "DEMO_DATA_CLEARED", f"{count} demo members removed")
            utils.toast_ok(f"Removed {count} demo member(s) and related demo records.")
            st.rerun()
    if loaded:
        st.info("Demo data is currently loaded for this gym.")


# --------------------------------------------------------------------------
# License management
# --------------------------------------------------------------------------
def page_license():
    user = st.session_state.user
    gym_id = user["gym_id"]
    gym = st.session_state.gym
    utils.page_header("License Management", "View and renew your software licence.", "\U0001F510")

    status = lm.get_status(gym_id)
    c1, c2, c3 = st.columns(3)
    with c1:
        utils.kpi_card("Status", status["label"], "\U0001F510",
                       "#16A34A" if status["state"] == "LICENSED" else "#D93025")
    with c2:
        utils.kpi_card("Days Left", status.get("days_left", 0), "⏳", "#E08A00")
    with c3:
        utils.kpi_card("Expiry Date", utils.fmt_date(status.get("expiry_date")), "\U0001F4C5", "#1D4ED8")

    if status.get("tamper"):
        st.warning("A backward clock change was detected on this computer. Licence days cannot "
                  "be recovered by changing the system clock.")

    st.markdown("##### Activate / Renew Licence")
    with st.form("license_form"):
        c1, c2 = st.columns(2)
        key = c1.text_input("Licence Key", placeholder="SNGYM-XXXX-XXXX-XXXX-XXXX")
        gym_name = c2.text_input("Gym Name", value=gym.get("gym_name", ""))
        mobile = c1.text_input("Registered Mobile", value=gym.get("mobile", ""))
        submitted = st.form_submit_button("Activate Licence", type="primary", use_container_width=True)
    if submitted:
        ok, message = lm.activate(gym_id, key, gym_name, mobile)
        (utils.toast_ok if ok else utils.toast_err)(message)
        if ok:
            st.rerun()

    st.caption(f"To purchase or renew a licence key, contact {lm.SUPPORT_CONTACT}")
