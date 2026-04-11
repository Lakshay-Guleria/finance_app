from flask import Blueprint, render_template, session
from db import get_db_connection
from auth import login_required
from datetime import datetime

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def dashboard():
    current_user_id = session["user_id"]
    conn = get_db_connection()

    try:
        # ---------------------------
        # All-Time Totals
        # ---------------------------
        totals = conn.execute(
            """
            SELECT 
                IFNULL(SUM(CASE WHEN c.type = 'income' THEN t.amount END), 0) AS total_income,
                IFNULL(SUM(CASE WHEN c.type = 'expense' THEN t.amount END), 0) AS total_expense
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = ?
            """,
            (current_user_id,),
        ).fetchone()

        # ---------------------------
        # Current Month
        # ---------------------------
        now = datetime.now()
        start_date = now.replace(day=1).strftime("%Y-%m-%d")

        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)

        end_date = next_month.strftime("%Y-%m-%d")

        monthly = conn.execute(
            """
            SELECT 
                IFNULL(SUM(CASE WHEN c.type = 'income' THEN t.amount END), 0) AS month_income,
                IFNULL(SUM(CASE WHEN c.type = 'expense' THEN t.amount END), 0) AS month_expense
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = ?
              AND t.date >= ?
              AND t.date < ?
            """,
            (current_user_id, start_date, end_date),
        ).fetchone()

        # ---------------------------
        # Last 6 Months Chart Data
        # ---------------------------
        # Build list of (year, month) for last 6 months including current
        months = []
        y, m = now.year, now.month
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        months.reverse()  # oldest first

        chart_labels = []
        chart_income = []
        chart_expense = []

        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        for (yr, mo) in months:
            # First day of month
            s = f"{yr}-{mo:02d}-01"
            # First day of next month
            if mo == 12:
                e = f"{yr + 1}-01-01"
            else:
                e = f"{yr}-{mo + 1:02d}-01"

            row = conn.execute(
                """
                SELECT
                    IFNULL(SUM(CASE WHEN c.type = 'income'  THEN t.amount END), 0) AS inc,
                    IFNULL(SUM(CASE WHEN c.type = 'expense' THEN t.amount END), 0) AS exp
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.user_id = ?
                  AND t.date >= ?
                  AND t.date < ?
                """,
                (current_user_id, s, e),
            ).fetchone()

            chart_labels.append(f"{month_names[mo - 1]} {yr}")
            chart_income.append(round(row["inc"], 2))
            chart_expense.append(round(row["exp"], 2))

        # ---------------------------
        # Expense Breakdown by Category (current month)
        # ---------------------------
        category_rows = conn.execute(
            """
            SELECT c.name, IFNULL(SUM(t.amount), 0) AS total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.user_id = ?
              AND c.type = 'expense'
              AND t.date >= ?
              AND t.date < ?
            GROUP BY c.id
            ORDER BY total DESC
            LIMIT 6
            """,
            (current_user_id, start_date, end_date),
        ).fetchall()

        pie_labels = [r["name"] for r in category_rows]
        pie_data   = [round(r["total"], 2) for r in category_rows]

        # ---------------------------
        # Budget Alerts (current month)
        # ---------------------------
        budget_alert_rows = conn.execute(
            """
            SELECT
                c.name AS category_name,
                b.limit_amount,
                IFNULL(SUM(t.amount), 0) AS total_spent
            FROM budgets b
            JOIN categories c
                ON b.category_id = c.id
            LEFT JOIN transactions t
                ON t.category_id = b.category_id
                AND t.user_id = b.user_id
                AND t.date >= ?
                AND t.date < ?
            WHERE b.user_id = ?
              AND b.month = ?
              AND b.year = ?
              AND b.is_active = 1
            GROUP BY b.id
            HAVING total_spent > b.limit_amount
            ORDER BY (total_spent - b.limit_amount) DESC
            """,
            (start_date, end_date, current_user_id, now.month, now.year),
        ).fetchall()

        budget_alerts = []
        for row in budget_alert_rows:
            budget_alerts.append(
                {
                    "category_name": row["category_name"],
                    "limit_amount": round(row["limit_amount"], 2),
                    "total_spent": round(row["total_spent"], 2),
                    "over_by": round(row["total_spent"] - row["limit_amount"], 2),
                }
            )

    finally:
        conn.close()

    total_income  = totals["total_income"]
    total_expense = totals["total_expense"]
    net_balance   = total_income - total_expense
    month_income  = monthly["month_income"]
    month_expense = monthly["month_expense"]

    return render_template(
        "home.html",
        total_income=total_income,
        total_expense=total_expense,
        net_balance=net_balance,
        month_income=month_income,
        month_expense=month_expense,
        # Chart data
        chart_labels=chart_labels,
        chart_income=chart_income,
        chart_expense=chart_expense,
        pie_labels=pie_labels,
        pie_data=pie_data,
        budget_alerts=budget_alerts,
    )
