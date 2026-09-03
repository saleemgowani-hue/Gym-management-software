"""
SN Gym Management System - Authentication & access control
Developed by SN Softech Solutions

Passwords are stored as PBKDF2-HMAC-SHA256 digests with a per-user random salt.
Plain text passwords are never written to the database.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime

import database as db

ITERATIONS = 200_000

# Which sidebar pages each role may open.
ROLE_PAGES = {
    "Admin": "ALL",
    "Manager": ["dashboard", "members", "plans", "sales", "renewals", "attendance",
                "trainers", "pt", "payments", "expenses", "products", "reports",
                "kpi", "notifications", "settings"],
    "Receptionist": ["dashboard", "members", "sales", "renewals", "attendance",
                     "payments", "products", "notifications"],
    "Trainer": ["dashboard", "members", "attendance", "pt", "notifications"],
}


# --------------------------------------------------------------------------
# Hashing
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iters, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False


# --------------------------------------------------------------------------
# Registration & login
# --------------------------------------------------------------------------
def username_exists(username: str) -> bool:
    return bool(db.fetch_one("SELECT id FROM users WHERE lower(username)=lower(?)", (username,)))


def email_exists(email: str) -> bool:
    if not email:
        return False
    return bool(db.fetch_one("SELECT id FROM users WHERE lower(email)=lower(?)", (email,)))


def register_gym(gym_name, owner_name, mobile, email, username, password,
                 security_question="", security_answer=""):
    """Create the gym, its Admin user and default plans. The gym starts UNLICENSED."""
    import license_manager as lm

    if username_exists(username):
        return False, "That username is already taken. Please choose another."
    if email_exists(email):
        return False, "An account already exists for this email address."

    gym_id = db.execute(
        """INSERT INTO gyms (gym_name, owner_name, mobile, email)
           VALUES (?,?,?,?)""",
        (gym_name.strip(), owner_name.strip(), mobile.strip(), email.strip()),
    )
    db.execute(
        """INSERT INTO users (gym_id, full_name, username, email, mobile,
                              password_hash, role, security_question, security_answer_hash)
           VALUES (?,?,?,?,?,?,'Admin',?,?)""",
        (gym_id, owner_name.strip(), username.strip(), email.strip(), mobile.strip(),
         hash_password(password), security_question,
         hash_password(security_answer.lower().strip()) if security_answer else None),
    )
    db.seed_plans(gym_id)
    lm.create_license_record(gym_id, gym_name, mobile)
    db.log_action(gym_id, {"username": username}, "SIGNUP", f"Gym '{gym_name}' registered")
    return True, gym_id


def login(identifier, password):
    """Accepts username or email. Returns (user_dict|None, message)."""
    user = db.fetch_one(
        """SELECT * FROM users
           WHERE lower(username)=lower(?) OR lower(email)=lower(?)""",
        (identifier.strip(), identifier.strip()),
    )
    if not user:
        return None, "No account found for that username or email."
    if not user["is_active"]:
        return None, "This account is deactivated. Ask your gym admin to enable it."
    if not verify_password(password, user["password_hash"]):
        return None, "Incorrect password. Please try again."
    db.execute("UPDATE users SET last_login=? WHERE id=?",
               (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["id"]))
    user.pop("password_hash", None)
    user.pop("security_answer_hash", None)
    db.log_action(user["gym_id"], user, "LOGIN", "Signed in")
    return user, "Signed in"


def reset_password(identifier, answer, new_password):
    """Password reset using the security question captured at sign up."""
    user = db.fetch_one(
        "SELECT * FROM users WHERE lower(username)=lower(?) OR lower(email)=lower(?)",
        (identifier.strip(), identifier.strip()),
    )
    if not user:
        return False, "No account found for that username or email."
    if not user["security_answer_hash"]:
        return False, "No security answer is set for this account. Ask your gym admin to reset it."
    if not verify_password(answer.lower().strip(), user["security_answer_hash"]):
        return False, "That answer does not match our records."
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (hash_password(new_password), user["id"]))
    db.log_action(user["gym_id"], user, "PASSWORD_RESET", "Password reset via security question")
    return True, "Password updated. You can sign in now."


def change_password(user_id, old_password, new_password):
    user = db.fetch_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not user or not verify_password(old_password, user["password_hash"]):
        return False, "Current password is incorrect."
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), user_id))
    return True, "Password changed."


def create_user(gym_id, full_name, username, email, mobile, password, role):
    if username_exists(username):
        return False, "That username is already taken."
    db.execute(
        """INSERT INTO users (gym_id, full_name, username, email, mobile, password_hash, role)
           VALUES (?,?,?,?,?,?,?)""",
        (gym_id, full_name, username.strip(), email, mobile, hash_password(password), role),
    )
    return True, "User created."


def can_access(role, page_key) -> bool:
    allowed = ROLE_PAGES.get(role, [])
    return allowed == "ALL" or page_key in allowed


# --------------------------------------------------------------------------
# "Remember me" token (stored in the browser via st.context.cookies fallback)
# --------------------------------------------------------------------------
def make_remember_token(user_id):
    token = secrets.token_urlsafe(24)
    db.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES (?,?)",
               (f"remember:{token}", str(user_id)))
    return token


def user_from_token(token):
    if not token:
        return None
    row = db.fetch_one("SELECT value FROM app_state WHERE key=?", (f"remember:{token}",))
    if not row:
        return None
    user = db.fetch_one("SELECT * FROM users WHERE id=?", (int(row["value"]),))
    if user:
        user.pop("password_hash", None)
        user.pop("security_answer_hash", None)
    return user


def clear_token(token):
    if token:
        db.execute("DELETE FROM app_state WHERE key=?", (f"remember:{token}",))
