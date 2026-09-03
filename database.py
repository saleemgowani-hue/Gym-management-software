"""
SN Gym Management System - Database layer
Developed by SN Softech Solutions

Works against TWO backends from the same code:

  * SQLite   - default, used by the local Windows install (data/gym_management.db)
  * Postgres - used when a connection URL is supplied, e.g. on Streamlit Cloud

Every other module writes SQLite-flavoured SQL with `?` placeholders.
`_translate()` converts that to Postgres on the fly, so nothing above this file
has to know which database it is talking to.

Choosing the backend
--------------------
Postgres is used when any of these is set (checked in this order):

    st.secrets["DATABASE_URL"]          (Streamlit Cloud -> Settings -> Secrets)
    st.secrets["postgres"]["url"]
    environment variable DATABASE_URL

Otherwise SQLite is used, at $SNGYM_DB or data/gym_management.db.
"""

import os
import re
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
ASSET_DIR = os.path.join(BASE_DIR, "assets", "logo")
DB_PATH = os.environ.get("SNGYM_DB", os.path.join(DATA_DIR, "gym_management.db"))

for _d in (DATA_DIR, PHOTO_DIR, BACKUP_DIR, ASSET_DIR):
    os.makedirs(_d, exist_ok=True)


# --------------------------------------------------------------------------
# Which backend?
# --------------------------------------------------------------------------
def _database_url():
    """Find a Postgres URL in Streamlit secrets or the environment."""
    try:
        import streamlit as st
        if "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"])
        if "postgres" in st.secrets and "url" in st.secrets["postgres"]:
            return str(st.secrets["postgres"]["url"])
    except Exception:
        pass                       # no Streamlit runtime, or no secrets file
    return os.environ.get("DATABASE_URL") or None


DATABASE_URL = _database_url()
DIALECT = "postgres" if DATABASE_URL else "sqlite"


def is_postgres():
    return DIALECT == "postgres"


def backend_label():
    if is_postgres():
        safe = re.sub(r"//[^@/]*@", "//", DATABASE_URL or "")
        host = re.sub(r"^\w+://", "", safe).split("?")[0]
        return f"PostgreSQL ({host or 'cloud'})"
    return f"SQLite ({DB_PATH})"


# --------------------------------------------------------------------------
# SQLite -> Postgres translation
# --------------------------------------------------------------------------
_ALIAS_RE = re.compile(r"\bAS\s+'([^']*)'", re.IGNORECASE)
_DATE_RE = re.compile(r"\bdate\(\s*([A-Za-z_][\w.]*)\s*\)", re.IGNORECASE)
_STRFTIME_RE = re.compile(r"strftime\(\s*'([^']+)'\s*,\s*([A-Za-z_][\w.]*)\s*\)", re.IGNORECASE)
_STRFTIME_MAP = {"%Y-%m": "YYYY-MM", "%Y": "YYYY", "%Y-%m-%d": "YYYY-MM-DD",
                 "%m": "MM", "%d": "DD"}


def _translate(sql, escape_percent=False):
    """Rewrite one SQLite statement so Postgres understands it.

    escape_percent must be True whenever parameters are supplied: psycopg then
    treats % as a placeholder marker, so literals such as LIKE '%@demo.gym'
    have to be doubled.
    """
    if not is_postgres():
        return sql

    # AS 'Member ID'  ->  AS "Member ID"
    sql = _ALIAS_RE.sub(r'AS "\1"', sql)

    # strftime('%Y-%m', pay_date) -> to_char((pay_date)::date,'YYYY-MM')
    def _sf(match):
        fmt = _STRFTIME_MAP.get(match.group(1), "YYYY-MM")
        return "to_char((%s)::date,'%s')" % (match.group(2), fmt)
    sql = _STRFTIME_RE.sub(_sf, sql)

    # datetime('now','localtime') -> now() ; date('now','localtime') -> CURRENT_DATE
    sql = re.sub(r"datetime\(\s*'now'\s*,\s*'localtime'\s*\)", "now()", sql, flags=re.I)
    sql = re.sub(r"date\(\s*'now'\s*,\s*'localtime'\s*\)", "CURRENT_DATE", sql, flags=re.I)

    # date(column) -> (column)::date   (dates are stored as TEXT in both backends)
    sql = _DATE_RE.sub(r"(\1)::date", sql)

    # INSERT OR IGNORE / OR REPLACE -> ON CONFLICT
    if re.search(r"INSERT\s+OR\s+IGNORE", sql, re.I):
        sql = re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", sql, flags=re.I)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    elif re.search(r"INSERT\s+OR\s+REPLACE", sql, re.I):
        sql = re.sub(r"INSERT\s+OR\s+REPLACE", "INSERT", sql, flags=re.I)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"

    if escape_percent:
        sql = sql.replace("%", "%%")
    return sql.replace("?", "%s")


# --------------------------------------------------------------------------
# Connections
# --------------------------------------------------------------------------
_PG_LOCK = threading.RLock()
_PG_CONN = None


def _pg_connection():
    """One shared Postgres connection, reopened if the server dropped it."""
    global _PG_CONN
    import psycopg
    from psycopg.rows import dict_row
    if _PG_CONN is None or _PG_CONN.closed:
        _PG_CONN = psycopg.connect(DATABASE_URL, row_factory=dict_row,
                                   autocommit=False, connect_timeout=15)
    return _PG_CONN


class _Conn:
    """Thin wrapper so callers use one API for both backends."""

    def __init__(self, raw, dialect):
        self.raw = raw
        self.dialect = dialect

    def execute(self, sql, params=()):
        params = tuple(params)
        return self.raw.execute(_translate(sql, bool(params)), params)

    def executemany(self, sql, seq):
        seq = [tuple(row) for row in seq]
        if self.dialect == "sqlite":
            return self.raw.executemany(_translate(sql), seq)
        cur = self.raw.cursor()
        cur.executemany(_translate(sql, True), seq)
        return cur


@contextmanager
def get_conn():
    """Yield a connection with dict-style rows. Commits on success, rolls back on error."""
    if is_postgres():
        with _PG_LOCK:
            raw = _pg_connection()
            try:
                yield _Conn(raw, "postgres")
                raw.commit()
            except Exception:
                try:
                    raw.rollback()
                except Exception:
                    pass
                raise
    else:
        raw = sqlite3.connect(DB_PATH, timeout=30)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        try:
            yield _Conn(raw, "sqlite")
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()


def _rows(cursor):
    return [dict(r) for r in cursor.fetchall()]


# --------------------------------------------------------------------------
# Query helpers - the API every other module uses
# --------------------------------------------------------------------------
def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE. Returns the new row id for inserts."""
    with get_conn() as conn:
        if is_postgres() and re.match(r"\s*INSERT\s", sql, re.I) and "RETURNING" not in sql.upper():
            params = tuple(params)
            translated = _translate(sql, bool(params)).rstrip().rstrip(";") + " RETURNING id"
            row = conn.raw.execute(translated, params).fetchone()
            return row["id"] if row else None
        cur = conn.execute(sql, params)
        return getattr(cur, "lastrowid", None)


def execute_many(sql, seq):
    with get_conn() as conn:
        conn.executemany(sql, seq)


def fetch_all(sql, params=()):
    with get_conn() as conn:
        return _rows(conn.execute(sql, params))


def fetch_one(sql, params=()):
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def fetch_value(sql, params=(), default=0):
    row = fetch_one(sql, params)
    if not row:
        return default
    val = list(row.values())[0]
    return default if val is None else val


def fetch_df(sql, params=()):
    """Return a DataFrame, with correct column names even when there are no rows."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        rows = _rows(cur)
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame(columns=[d[0] for d in (cur.description or [])])


# --------------------------------------------------------------------------
# Schema  ({ID} and {TS} differ between the two backends)
# --------------------------------------------------------------------------
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS gyms (
        id {ID},
        gym_name TEXT NOT NULL,
        owner_name TEXT,
        mobile TEXT,
        email TEXT,
        address TEXT,
        gst_number TEXT,
        logo_path TEXT,
        receipt_footer TEXT DEFAULT 'Thank you for training with us!',
        currency TEXT DEFAULT 'INR',
        date_format TEXT DEFAULT 'dd-MMM-yyyy',
        theme TEXT DEFAULT 'Corporate Blue',
        notify_expiry_days INTEGER DEFAULT 7,
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS users (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        full_name TEXT,
        username TEXT NOT NULL UNIQUE,
        email TEXT,
        mobile TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Admin',
        is_active INTEGER DEFAULT 1,
        security_question TEXT,
        security_answer_hash TEXT,
        last_login TEXT,
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS licenses (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        status TEXT NOT NULL DEFAULT 'UNLICENSED',
        license_key TEXT,
        gym_name TEXT,
        mobile TEXT,
        activation_date TEXT,
        expiry_date TEXT,
        tamper_flag INTEGER DEFAULT 0,
        last_seen_ts DOUBLE PRECISION,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS app_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS trainers (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        trainer_name TEXT NOT NULL,
        mobile TEXT,
        email TEXT,
        specialization TEXT,
        joining_date TEXT,
        salary DOUBLE PRECISION DEFAULT 0,
        commission DOUBLE PRECISION DEFAULT 0,
        status TEXT DEFAULT 'Active',
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS membership_plans (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        plan_name TEXT NOT NULL,
        duration_months DOUBLE PRECISION NOT NULL DEFAULT 1,
        price DOUBLE PRECISION NOT NULL DEFAULT 0,
        discount DOUBLE PRECISION DEFAULT 0,
        description TEXT,
        status TEXT DEFAULT 'Active',
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS members (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        member_code TEXT,
        full_name TEXT NOT NULL,
        gender TEXT,
        dob TEXT,
        mobile TEXT,
        whatsapp TEXT,
        email TEXT,
        address TEXT,
        emergency_contact TEXT,
        joining_date TEXT,
        photo_path TEXT,
        blood_group TEXT,
        height DOUBLE PRECISION,
        weight DOUBLE PRECISION,
        fitness_goal TEXT,
        medical_notes TEXT,
        trainer_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL,
        status TEXT DEFAULT 'Active',
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS memberships (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        plan_id INTEGER REFERENCES membership_plans(id) ON DELETE SET NULL,
        plan_name TEXT,
        sale_type TEXT DEFAULT 'New',
        invoice_no TEXT,
        start_date TEXT,
        end_date TEXT,
        amount DOUBLE PRECISION DEFAULT 0,
        discount DOUBLE PRECISION DEFAULT 0,
        net_amount DOUBLE PRECISION DEFAULT 0,
        paid_amount DOUBLE PRECISION DEFAULT 0,
        due_amount DOUBLE PRECISION DEFAULT 0,
        payment_mode TEXT,
        notes TEXT,
        created_by INTEGER,
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS attendance (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        att_date TEXT NOT NULL,
        check_in TEXT,
        check_out TEXT,
        status TEXT DEFAULT 'Present',
        source TEXT DEFAULT 'Manual',
        UNIQUE(gym_id, member_id, att_date)
    )""",
    """CREATE TABLE IF NOT EXISTS personal_training (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        trainer_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL,
        package_name TEXT,
        total_sessions INTEGER DEFAULT 0,
        used_sessions INTEGER DEFAULT 0,
        start_date TEXT,
        end_date TEXT,
        amount DOUBLE PRECISION DEFAULT 0,
        paid_amount DOUBLE PRECISION DEFAULT 0,
        due_amount DOUBLE PRECISION DEFAULT 0,
        invoice_no TEXT,
        status TEXT DEFAULT 'Active',
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS pt_sessions (
        id {ID},
        gym_id INTEGER NOT NULL,
        pt_id INTEGER NOT NULL REFERENCES personal_training(id) ON DELETE CASCADE,
        session_date TEXT,
        notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS payments (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        invoice_no TEXT,
        pay_date TEXT,
        category TEXT DEFAULT 'Membership',
        ref_table TEXT,
        ref_id INTEGER,
        amount DOUBLE PRECISION DEFAULT 0,
        paid_amount DOUBLE PRECISION DEFAULT 0,
        due_amount DOUBLE PRECISION DEFAULT 0,
        payment_mode TEXT,
        status TEXT DEFAULT 'Paid',
        notes TEXT,
        created_by INTEGER,
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS expenses (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        exp_date TEXT,
        category TEXT,
        description TEXT,
        amount DOUBLE PRECISION DEFAULT 0,
        payment_mode TEXT,
        notes TEXT,
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS products (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        product_name TEXT NOT NULL,
        category TEXT,
        barcode TEXT,
        purchase_price DOUBLE PRECISION DEFAULT 0,
        selling_price DOUBLE PRECISION DEFAULT 0,
        stock DOUBLE PRECISION DEFAULT 0,
        low_stock_limit DOUBLE PRECISION DEFAULT 5,
        supplier TEXT,
        status TEXT DEFAULT 'Active'
    )""",
    """CREATE TABLE IF NOT EXISTS product_sales (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        sale_date TEXT,
        quantity DOUBLE PRECISION DEFAULT 1,
        rate DOUBLE PRECISION DEFAULT 0,
        amount DOUBLE PRECISION DEFAULT 0,
        paid_amount DOUBLE PRECISION DEFAULT 0,
        due_amount DOUBLE PRECISION DEFAULT 0,
        payment_mode TEXT,
        invoice_no TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS stock_movements (
        id {ID},
        gym_id INTEGER NOT NULL,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        move_date TEXT,
        move_type TEXT,
        quantity DOUBLE PRECISION,
        notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS weight_history (
        id {ID},
        gym_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
        log_date TEXT,
        weight DOUBLE PRECISION
    )""",
    """CREATE TABLE IF NOT EXISTS notifications (
        id {ID},
        gym_id INTEGER NOT NULL REFERENCES gyms(id) ON DELETE CASCADE,
        notif_type TEXT,
        title TEXT,
        message TEXT,
        channel TEXT DEFAULT 'In-App',
        ref_table TEXT,
        ref_id INTEGER,
        is_read INTEGER DEFAULT 0,
        created_at {TS}
    )""",
    """CREATE TABLE IF NOT EXISTS audit_logs (
        id {ID},
        gym_id INTEGER,
        user_id INTEGER,
        username TEXT,
        action TEXT,
        details TEXT,
        created_at {TS}
    )""",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_members_gym ON members(gym_id)",
    "CREATE INDEX IF NOT EXISTS idx_memberships_member ON memberships(member_id)",
    "CREATE INDEX IF NOT EXISTS idx_att_date ON attendance(gym_id, att_date)",
    "CREATE INDEX IF NOT EXISTS idx_pay_date ON payments(gym_id, pay_date)",
    "CREATE INDEX IF NOT EXISTS idx_exp_date ON expenses(gym_id, exp_date)",
]

# Creation order matters for foreign keys on Postgres.
TABLES = ["gyms", "users", "licenses", "app_state", "trainers", "membership_plans", "members",
          "memberships", "attendance", "personal_training", "pt_sessions", "payments",
          "expenses", "products", "product_sales", "stock_movements", "weight_history",
          "notifications", "audit_logs"]

DEFAULT_PLANS = [
    ("1 Month", 1, 1500, 0, "Standard monthly gym access"),
    ("3 Months", 3, 4000, 5, "Quarterly membership"),
    ("6 Months", 6, 7000, 10, "Half yearly membership"),
    ("12 Months", 12, 12000, 15, "Annual membership - best value"),
    ("Student Plan", 1, 1000, 0, "Valid with student ID"),
    ("Couple Plan", 1, 2500, 10, "For two members"),
    ("Family Plan", 12, 20000, 20, "Up to 4 family members"),
    ("Personal Training", 1, 6000, 0, "12 PT sessions with a certified trainer"),
]

EXPENSE_CATEGORIES = ["Rent", "Electricity", "Salary", "Maintenance",
                      "Equipment", "Marketing", "Cleaning", "Other"]
PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer", "Other"]
ROLES = ["Admin", "Manager", "Receptionist", "Trainer"]


def init_db():
    """Create every table on first launch. Safe to call on every start."""
    if is_postgres():
        id_col = "SERIAL PRIMARY KEY"
        ts_col = "TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')"
    else:
        id_col = "INTEGER PRIMARY KEY AUTOINCREMENT"
        ts_col = "TEXT DEFAULT (datetime('now','localtime'))"

    with get_conn() as conn:
        for stmt in SCHEMA:
            conn.raw.execute(stmt.format(ID=id_col, TS=ts_col))
        for stmt in INDEXES:
            conn.raw.execute(stmt)
    return True


def drop_all(force=False):
    """Destructive: remove every table. Only used by the test suites and by
    tools/migrate_sqlite_to_postgres.py --fresh. Requires force=True."""
    if not force:
        raise RuntimeError("drop_all() must be called with force=True")
    with get_conn() as conn:
        for table in reversed(TABLES):
            suffix = " CASCADE" if is_postgres() else ""
            conn.raw.execute(f"DROP TABLE IF EXISTS {table}{suffix}")
    return True


def seed_plans(gym_id):
    """Give a brand new gym a usable set of membership plans."""
    if fetch_value("SELECT COUNT(*) FROM membership_plans WHERE gym_id=?", (gym_id,)):
        return
    execute_many(
        """INSERT INTO membership_plans
           (gym_id, plan_name, duration_months, price, discount, description)
           VALUES (?,?,?,?,?,?)""",
        [(gym_id,) + p for p in DEFAULT_PLANS],
    )


def log_action(gym_id, user, action, details=""):
    """Append to the audit trail. Never raises - logging must not break a flow."""
    try:
        execute(
            "INSERT INTO audit_logs (gym_id, user_id, username, action, details) VALUES (?,?,?,?,?)",
            (gym_id, (user or {}).get("id"), (user or {}).get("username", "system"),
             action, str(details)[:500]),
        )
    except Exception:
        pass


# --------------------------------------------------------------------------
# Backup / restore  (file copy on SQLite, workbook export on Postgres)
# --------------------------------------------------------------------------
def create_backup():
    """SQLite: a consistent .db copy. Postgres: an .xlsx workbook of every table."""
    init_db()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if is_postgres():
        target = os.path.join(BACKUP_DIR, f"gym_backup_{stamp}.xlsx")
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            for table in TABLES:
                try:
                    frame = fetch_df(f"SELECT * FROM {table}")
                except Exception:
                    continue
                if frame.empty:
                    frame = pd.DataFrame({"info": ["no rows"]})
                frame.to_excel(writer, sheet_name=table[:31], index=False)
        return target

    target = os.path.join(BACKUP_DIR, f"gym_backup_{stamp}.db")
    with get_conn() as conn:
        dest = sqlite3.connect(target)
        conn.raw.backup(dest)
        dest.close()
    return target


def list_backups():
    files = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if name.endswith((".db", ".xlsx")):
            path = os.path.join(BACKUP_DIR, name)
            files.append({
                "file": name,
                "path": path,
                "size_kb": round(os.path.getsize(path) / 1024, 1),
                "created": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d-%b-%Y %H:%M"),
            })
    return files


def restore_backup(uploaded_bytes):
    """Restore a SQLite backup. The current database is always saved first."""
    if is_postgres():
        raise RuntimeError(
            "Restore replaces a local database file and is not available on the cloud "
            "deployment. Use your Postgres provider's point-in-time restore instead.")
    safety = os.path.join(BACKUP_DIR,
                          "pre_restore_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, safety)
    tmp = DB_PATH + ".incoming"
    with open(tmp, "wb") as fh:
        fh.write(uploaded_bytes)
    test = sqlite3.connect(tmp)
    try:
        test.execute("SELECT COUNT(*) FROM users").fetchone()
    finally:
        test.close()
    shutil.move(tmp, DB_PATH)
    init_db()
    return safety
