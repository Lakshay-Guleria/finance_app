import os

from flask import Flask, render_template, request, redirect, url_for, session, flash

from db import get_db_connection
from auth import auth, login_required
from categories import categories_bp
from transactions import transactions_bp
from budgets import budgets_bp
from dashboard import dashboard_bp


def _load_local_env(env_path=".env"):
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")

            if key and key not in os.environ:
                os.environ[key] = value


_load_local_env()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY is not set. Add it to your .env file or environment variables."
    )

app.register_blueprint(auth)
app.register_blueprint(categories_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(budgets_bp)
app.register_blueprint(dashboard_bp)

# ---------------------------
# User Detail Route
# ---------------------------
@app.route("/user/<int:user_id>")
@login_required
def get_user(user_id):
    if user_id != session["user_id"]:
        flash("Unauthorized access", "error")
        return redirect(url_for("dashboard.dashboard"))
    
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()

    if row is None:
        return "User not found", 404

    user = dict(row)

    return render_template("user.html", user=user)


# ---------------------------
# Run App - should be at the end of the file
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True,port=9000,host="0.0.0.0")
