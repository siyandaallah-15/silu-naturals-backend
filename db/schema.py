"""
SiLu Naturals — SQLite schema initialiser
Run once (automatically on server start) to create all tables.
"""
import sqlite3, os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "silu.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── Distributors ──────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS distributors (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        code          TEXT    UNIQUE NOT NULL,
        fname         TEXT    NOT NULL,
        lname         TEXT    NOT NULL,
        email         TEXT    UNIQUE NOT NULL,
        phone         TEXT    NOT NULL,
        id_number     TEXT    NOT NULL,
        city          TEXT    NOT NULL,
        pack          TEXT    NOT NULL,          -- Silver|Gold|Platinum
        sponsor_code  TEXT,                       -- referral code of recruiter
        password_hash TEXT    NOT NULL,
        status        TEXT    NOT NULL DEFAULT 'pending',  -- pending|active|grace|suspended
        status_override TEXT,                     -- NULL|active|suspended  (admin manual)
        join_date     TEXT    NOT NULL,
        rank_name     TEXT    NOT NULL DEFAULT 'Member',
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )""")

    # ── Recruits (who recruited whom) ────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS recruits (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        sponsor_code  TEXT NOT NULL,
        recruit_code  TEXT NOT NULL,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(sponsor_code, recruit_code)
    )""")

    # ── Maintenance payments ──────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS maintenance_payments (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        dist_code     TEXT NOT NULL,
        amount        INTEGER NOT NULL,
        period_label  TEXT,
        method        TEXT NOT NULL DEFAULT 'card',
        status        TEXT NOT NULL DEFAULT 'pending',  -- pending|confirmed|rejected
        order_ref     TEXT,
        paid_at       TEXT,
        confirmed_at  TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    # ── Product orders (public + distributor) ────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no      TEXT    UNIQUE NOT NULL,
        customer_name TEXT    NOT NULL,
        customer_phone TEXT   NOT NULL,
        customer_email TEXT   NOT NULL,
        pep_store     TEXT    NOT NULL,
        product       TEXT    NOT NULL,
        qty           INTEGER NOT NULL DEFAULT 1,
        unit_price    INTEGER NOT NULL DEFAULT 200,
        subtotal      INTEGER NOT NULL,
        shipping      INTEGER NOT NULL DEFAULT 60,
        total         INTEGER NOT NULL,
        referral_code TEXT,
        payment_method TEXT  NOT NULL DEFAULT 'card',
        payment_status TEXT  NOT NULL DEFAULT 'pending',  -- pending|paid|failed
        order_type    TEXT  NOT NULL DEFAULT 'product',   -- product|registration|maintenance
        dist_code     TEXT,                               -- if placed by distributor
        notes         TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        paid_at       TEXT
    )""")

    # ── Sales (distributor personal sales log) ────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        dist_code     TEXT    NOT NULL,
        order_no      TEXT,
        product       TEXT    NOT NULL,
        qty           INTEGER NOT NULL DEFAULT 1,
        amount        INTEGER NOT NULL,
        sale_date     TEXT    NOT NULL DEFAULT (datetime('now'))
    )""")

    # ── Commission ledger ────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS commissions (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        beneficiary   TEXT    NOT NULL,   -- distributor who earns
        source_code   TEXT    NOT NULL,   -- distributor whose sale triggered it
        level         INTEGER NOT NULL,   -- 1, 2, 3, or 4
        rate          REAL    NOT NULL,
        sale_amount   INTEGER NOT NULL,
        commission    INTEGER NOT NULL,
        status        TEXT    NOT NULL DEFAULT 'pending',  -- pending|available|paid
        order_no      TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )""")

    # ── Payout requests ──────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS payouts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        dist_code     TEXT    NOT NULL,
        amount        INTEGER NOT NULL,
        bank_name     TEXT,
        account_name  TEXT,
        account_no    TEXT,
        branch_code   TEXT,
        status        TEXT    NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
        requested_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        processed_at  TEXT,
        notes         TEXT
    )""")

    # ── Admin users ──────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    UNIQUE NOT NULL,
        password_hash TEXT    NOT NULL,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )""")

    # ── Sessions / tokens blacklist ──────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS token_blacklist (
        token_jti     TEXT    PRIMARY KEY,
        expires_at    TEXT    NOT NULL
    )""")

    conn.commit()
    conn.close()
    print("[DB] Schema initialised ✓")
