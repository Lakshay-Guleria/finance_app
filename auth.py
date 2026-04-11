import os
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from db import get_db_connection

auth = Blueprint("auth", __name__)


OTP_EXPIRY_MINUTES = 5


def _generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_otp_email(recipient_email, otp_code, subject, purpose_label):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SMTP_FROM_EMAIL") or smtp_username

    if not all([smtp_host, smtp_username, smtp_password, sender_email]):
        print(f"[OTP DEBUG] {purpose_label} OTP for {recipient_email}: {otp_code}")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email
    message.set_content(
        f"Your Budget Manager OTP is {otp_code}. It expires in {OTP_EXPIRY_MINUTES} minutes."
    )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(message)

    return True


def _send_signup_otp_email(recipient_email, otp_code):
    return _send_otp_email(
        recipient_email,
        otp_code,
        "Your Budget Manager verification code",
        "Signup",
    )


def _send_password_reset_otp_email(recipient_email, otp_code):
    return _send_otp_email(
        recipient_email,
        otp_code,
        "Your Budget Manager password reset code",
        "Password reset",
    )


def _store_pending_signup(conn, name, email, password_hash, otp_code):
    expires_at = (datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(
        timespec="seconds"
    )
    created_at = datetime.now().isoformat(timespec="seconds")

    conn.execute(
        """
        INSERT INTO pending_user_otps (email, name, password_hash, otp_code, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            name = excluded.name,
            password_hash = excluded.password_hash,
            otp_code = excluded.otp_code,
            expires_at = excluded.expires_at,
            created_at = excluded.created_at
        """,
        (email, name, password_hash, otp_code, expires_at, created_at),
    )


def _cleanup_expired_otps(conn):
    conn.execute(
        """
        DELETE FROM pending_user_otps
        WHERE expires_at < ?
        """,
        (datetime.now().isoformat(timespec="seconds"),),
    )
    conn.execute(
        """
        DELETE FROM password_reset_otps
        WHERE expires_at < ?
        """,
        (datetime.now().isoformat(timespec="seconds"),),
    )


def _store_password_reset_otp(conn, email, otp_code):
    expires_at = (datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(
        timespec="seconds"
    )
    created_at = datetime.now().isoformat(timespec="seconds")

    conn.execute(
        """
        INSERT INTO password_reset_otps (email, otp_code, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            otp_code = excluded.otp_code,
            expires_at = excluded.expires_at,
            created_at = excluded.created_at
        """,
        (email, otp_code, expires_at, created_at),
    )


def _start_signup_verification(name, email, password_hash):
    conn = get_db_connection()
    try:
        _cleanup_expired_otps(conn)

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if existing_user:
            flash("Email already registered", "error")
            return False

        otp_code = _generate_otp()
        _store_pending_signup(conn, name, email, password_hash, otp_code)
        conn.commit()
    finally:
        conn.close()

    email_sent = _send_signup_otp_email(email, otp_code)
    session["pending_signup_email"] = email

    if email_sent:
        flash("OTP sent to your email. Please verify to complete signup.", "success")
    else:
        flash(
            "OTP generated. Email is not configured yet, so check the server terminal for the code.",
            "warning",
        )

    return True


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard.dashboard"))
        else:
            flash("Invalid email or password", "error")
            return redirect(url_for("auth.login"))

    return render_template("login.html")


# ---------------------------
# Logout Route
# ---------------------------


@auth.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


# ---------------------------
# Check login
# ---------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


# ---------------------------
# Create User Route
# ---------------------------


@auth.route("/create-user", methods=["GET", "POST"])
def create_user():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password")

        if not name or not email or not password:
            flash("All fields are required", "error")
            return redirect(url_for("auth.create_user"))

        password_hash = generate_password_hash(password)
        signup_started = _start_signup_verification(name, email, password_hash)
        if not signup_started:
            return redirect(url_for("auth.create_user"))

        return redirect(url_for("auth.verify_signup_otp"))

    return render_template("create_user.html")


@auth.route("/verify-signup-otp", methods=["GET", "POST"])
def verify_signup_otp():
    pending_email = session.get("pending_signup_email")

    if not pending_email:
        flash("Start signup first before verifying OTP", "warning")
        return redirect(url_for("auth.create_user"))

    if request.method == "POST":
        otp_code = (request.form.get("otp_code") or "").strip()

        if not otp_code:
            flash("OTP is required", "error")
            return redirect(url_for("auth.verify_signup_otp"))

        conn = get_db_connection()
        try:
            _cleanup_expired_otps(conn)

            pending_signup = conn.execute(
                """
                SELECT *
                FROM pending_user_otps
                WHERE email = ?
                """,
                (pending_email,),
            ).fetchone()

            if not pending_signup:
                flash(
                    "OTP expired or signup not found. Please register again.", "error"
                )
                session.pop("pending_signup_email", None)
                return redirect(url_for("auth.create_user"))

            if pending_signup["otp_code"] != otp_code:
                flash("Invalid OTP", "error")
                return redirect(url_for("auth.verify_signup_otp"))

            cursor = conn.execute(
                """
                INSERT INTO users(name, email, password_hash, created_at)
                VALUES (?, ?, ?, date('now'))
                """,
                (
                    pending_signup["name"],
                    pending_signup["email"],
                    pending_signup["password_hash"],
                ),
            )

            conn.execute(
                """
                DELETE FROM pending_user_otps
                WHERE email = ?
                """,
                (pending_email,),
            )
            conn.commit()

            session.pop("pending_signup_email", None)
            session["user_id"] = cursor.lastrowid
            flash("Account verified successfully", "success")
            return redirect(url_for("dashboard.dashboard"))

        except sqlite3.IntegrityError:
            flash("Email already registered", "error")
            session.pop("pending_signup_email", None)
            return redirect(url_for("auth.login"))
        finally:
            conn.close()

    return render_template("verify_signup_otp.html", pending_email=pending_email)


@auth.route("/resend-signup-otp", methods=["POST"])
def resend_signup_otp():
    pending_email = session.get("pending_signup_email")

    if not pending_email:
        flash("Start signup first before requesting another OTP", "warning")
        return redirect(url_for("auth.create_user"))

    conn = get_db_connection()
    try:
        _cleanup_expired_otps(conn)
        pending_signup = conn.execute(
            """
            SELECT name, email, password_hash
            FROM pending_user_otps
            WHERE email = ?
            """,
            (pending_email,),
        ).fetchone()
    finally:
        conn.close()

    if not pending_signup:
        session.pop("pending_signup_email", None)
        flash("OTP expired. Please register again.", "error")
        return redirect(url_for("auth.create_user"))

    signup_started = _start_signup_verification(
        pending_signup["name"],
        pending_signup["email"],
        pending_signup["password_hash"],
    )
    if not signup_started:
        session.pop("pending_signup_email", None)
        return redirect(url_for("auth.create_user"))

    return redirect(url_for("auth.verify_signup_otp"))


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not email:
            flash("Email is required", "error")
            return redirect(url_for("auth.forgot_password"))

        conn = get_db_connection()
        try:
            _cleanup_expired_otps(conn)
            user = conn.execute(
                """
                SELECT id
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

            if not user:
                flash("No account found with that email", "error")
                return redirect(url_for("auth.forgot_password"))

            otp_code = _generate_otp()
            _store_password_reset_otp(conn, email, otp_code)
            conn.commit()
        finally:
            conn.close()

        email_sent = _send_password_reset_otp_email(email, otp_code)
        session["pending_reset_email"] = email

        if email_sent:
            flash("Password reset OTP sent to your email", "success")
        else:
            flash(
                "Password reset OTP generated. Email is not configured yet, so check the server terminal for the code.",
                "warning",
            )

        return redirect(url_for("auth.reset_password"))

    return render_template("forgot_password.html")


@auth.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    pending_email = session.get("pending_reset_email")

    if not pending_email:
        flash("Start the forgot password process first", "warning")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        otp_code = (request.form.get("otp_code") or "").strip()
        new_password = request.form.get("new_password") or ""

        if not otp_code or not new_password:
            flash("OTP and new password are required", "error")
            return redirect(url_for("auth.reset_password"))

        conn = get_db_connection()
        try:
            _cleanup_expired_otps(conn)
            reset_row = conn.execute(
                """
                SELECT *
                FROM password_reset_otps
                WHERE email = ?
                """,
                (pending_email,),
            ).fetchone()

            if not reset_row:
                flash("Reset OTP expired. Request a new one.", "error")
                session.pop("pending_reset_email", None)
                return redirect(url_for("auth.forgot_password"))

            if reset_row["otp_code"] != otp_code:
                flash("Invalid OTP", "error")
                return redirect(url_for("auth.reset_password"))

            conn.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE email = ?
                """,
                (generate_password_hash(new_password), pending_email),
            )
            conn.execute(
                """
                DELETE FROM password_reset_otps
                WHERE email = ?
                """,
                (pending_email,),
            )
            conn.commit()
        finally:
            conn.close()

        session.pop("pending_reset_email", None)
        flash("Password reset successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", pending_email=pending_email)


@auth.route("/resend-reset-otp", methods=["POST"])
def resend_reset_otp():
    pending_email = session.get("pending_reset_email")

    if not pending_email:
        flash("Start the forgot password process first", "warning")
        return redirect(url_for("auth.forgot_password"))

    conn = get_db_connection()
    try:
        user = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (pending_email,),
        ).fetchone()

        if not user:
            session.pop("pending_reset_email", None)
            flash("Account not found", "error")
            return redirect(url_for("auth.forgot_password"))

        otp_code = _generate_otp()
        _store_password_reset_otp(conn, pending_email, otp_code)
        conn.commit()
    finally:
        conn.close()

    email_sent = _send_password_reset_otp_email(pending_email, otp_code)
    if email_sent:
        flash("A new password reset OTP has been sent", "success")
    else:
        flash(
            "A new password reset OTP was generated. Email is not configured yet, so check the server terminal for the code.",
            "warning",
        )

    return redirect(url_for("auth.reset_password"))
