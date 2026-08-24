import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = "finance.db"

DEMO_EMAIL = "demo@demo.com"
DEMO_PASSWORD = "demo"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create database tables and seed demo data if needed."""

    conn = get_db_connection()
    cursor = conn.cursor()

    # ---------------------------
    # USERS
    # ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

    # ---------------------------
    # CATEGORIES
    # ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income','expense')),
            is_active INTEGER DEFAULT 1,

            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_categories_user_name_type_unique
        ON categories(user_id, lower(trim(name)), type)
    """)

    # ---------------------------
    # TRANSACTIONS
    # ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            description TEXT,
            date TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    # ---------------------------
    # BUDGETS
    # ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            year INTEGER NOT NULL,
            limit_amount REAL NOT NULL CHECK(limit_amount > 0),
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,

            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(id),

            UNIQUE(user_id, category_id, month, year)
        )
    """)

    # ---------------------------
    # SIGNUP OTPs
    # ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_user_otps (
            email TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # ---------------------------
    # PASSWORD RESET OTPs
    # ---------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            email TEXT PRIMARY KEY,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # ---------------------------
    # CHECK FOR DEMO USER
    # ---------------------------
    cursor.execute(
        "SELECT id FROM users WHERE email = ?",
        (DEMO_EMAIL,)
    )

    demo_user = cursor.fetchone()

    # ---------------------------
    # SEED DEMO DATA
    # ---------------------------
    if demo_user is None:

        password_hash = generate_password_hash(DEMO_PASSWORD)

        cursor.execute("""
            INSERT INTO users
            (name, email, password_hash, created_at, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Demo Account",
            DEMO_EMAIL,
            password_hash,
            "2026-08-01",
            1
        ))

        user_id = cursor.lastrowid

        # Categories
        cursor.execute("""
            INSERT INTO categories
            (user_id, name, type, is_active)
            VALUES (?, ?, ?, ?)
        """, (user_id, "Salary", "income", 1))

        salary_category_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO categories
            (user_id, name, type, is_active)
            VALUES (?, ?, ?, ?)
        """, (user_id, "Groceries", "expense", 1))

        groceries_category_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO categories
            (user_id, name, type, is_active)
            VALUES (?, ?, ?, ?)
        """, (user_id, "Rent", "expense", 1))

        rent_category_id = cursor.lastrowid

        # Transactions
        cursor.execute("""
            INSERT INTO transactions
            (user_id, category_id, amount, description, date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            salary_category_id,
            4000.00,
            "Monthly Salary",
            "2026-08-01",
            "2026-08-01"
        ))

        cursor.execute("""
            INSERT INTO transactions
            (user_id, category_id, amount, description, date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            groceries_category_id,
            120.50,
            "Supermarket shopping",
            "2026-08-05",
            "2026-08-05"
        ))

        cursor.execute("""
            INSERT INTO transactions
            (user_id, category_id, amount, description, date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            rent_category_id,
            1200.00,
            "Monthly Rent",
            "2026-08-01",
            "2026-08-01"
        ))

        # Budget
        cursor.execute("""
            INSERT INTO budgets
            (user_id, category_id, month, year,
             limit_amount, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            groceries_category_id,
            8,
            2026,
            500.00,
            "2026-08-01",
            1
        ))

    conn.commit()
    conn.close()