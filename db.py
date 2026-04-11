import sqlite3

def get_db_connection():
    conn = sqlite3.connect("finance.db")
    conn.row_factory = (
        sqlite3.Row
    )  # create a row factory to return rows as dictionaries
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_user_name_type_unique
        ON categories(user_id, lower(trim(name)), type)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_user_otps (
            email TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            email TEXT PRIMARY KEY,
            otp_code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn
