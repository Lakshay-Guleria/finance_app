from flask import Blueprint, render_template, session, request, redirect, url_for,flash
from db import get_db_connection
from auth import login_required
import sqlite3
from datetime import datetime

budgets_bp = Blueprint("budgets", __name__)

# ---------------------------
# Budgets
# ---------------------------


@budgets_bp.route("/budgets")
@login_required
def budgets():

    current_user_id = session["user_id"]

    # month = 2
    # year = 2026

    current_date = datetime.now()

    month = request.args.get("month", type=int) or current_date.month
    year = request.args.get("year", type=int) or current_date.year
    if month < 1 or month > 12:
        month = current_date.month

    conn = get_db_connection()

    try:
        rows = conn.execute(
            """
    SELECT 
        b.id,
        c.name AS category_name,
        b.month,
        b.year,
        b.limit_amount,
        COUNT(t.id) AS transaction_count,
        IFNULL(SUM(t.amount), 0) AS total_spent,
        (b.limit_amount - IFNULL(SUM(t.amount), 0)) AS remaining
    FROM budgets b
    JOIN categories c 
        ON b.category_id = c.id
    LEFT JOIN transactions t
        ON t.category_id = b.category_id
        AND t.user_id = ?
        AND strftime('%m', t.date) = printf('%02d', b.month)
        AND strftime('%Y', t.date) = CAST(b.year AS TEXT)
    WHERE b.user_id = ?
      AND b.month = ?
      AND b.year = ?
    GROUP BY b.id
    ORDER BY b.year DESC, b.month DESC;
            """,
            (current_user_id, current_user_id, month, year),
        ).fetchall()

        available_year_rows = conn.execute(
            """
            SELECT DISTINCT year
            FROM budgets
            WHERE user_id = ?
            ORDER BY year DESC
            """,
            (current_user_id,),
        ).fetchall()
    finally:
        conn.close()

    budgets = []
    for row in rows:
        budgets.append(dict(row))

    month_options = [
        (1, "January"),
        (2, "February"),
        (3, "March"),
        (4, "April"),
        (5, "May"),
        (6, "June"),
        (7, "July"),
        (8, "August"),
        (9, "September"),
        (10, "October"),
        (11, "November"),
        (12, "December"),
    ]

    available_years = [row["year"] for row in available_year_rows] or [year]

    return render_template(
        "budgets.html",
        budgets=budgets,
        selected_month=month,
        selected_year=year,
        month_options=month_options,
        available_years=available_years,
    )


# ---------------------------
# Create Budget
# ---------------------------


@budgets_bp.route("/create-budget", methods=["GET", "POST"])
@login_required
def create_budget():

    current_user_id = session["user_id"]
    current_date = datetime.now()

    conn = get_db_connection()

    if request.method == "POST":
        category_id = request.form["category_id"]
        month = request.form["month"]
        year = request.form["year"]
        limit_amount = request.form["limit_amount"]

        # Validate category
        rows = conn.execute(
            "SELECT type FROM categories WHERE id = ? AND user_id = ?",
            (category_id, current_user_id),
        ).fetchone()

        if not rows:
            conn.close()
            return "Invalid Category", 400

        if rows["type"] != "expense":
            conn.close()
            flash("Budget only allowed for expense categories", "error")
            return redirect(url_for("budgets.create_budget"))

        try:
            conn.execute(
                """
                INSERT INTO budgets
                (user_id, category_id, month, year, limit_amount, created_at)
                VALUES (?, ?, ?, ?, ?, date('now'))
                """,
                (current_user_id, category_id, month, year, limit_amount),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("Budget already exists for this month", "error")
            return redirect(url_for("budgets.create_budget"))

        conn.close()
        flash("Budget created successfully", "success")
        return redirect(url_for("budgets.budgets"))

    # GET logic
    rows = conn.execute(
        """
        SELECT id, name 
        FROM categories
        WHERE user_id = ?
        AND type = 'expense'
        """,
        (current_user_id,),
    ).fetchall()

    categories = [dict(row) for row in rows]

    conn.close()
    return render_template(
        "create_budgets.html",
        categories=categories,
        default_month=current_date.month,
        default_year=current_date.year,
    )


# ---------------------------
# Edit Budget
# ---------------------------
@budgets_bp.route("/edit-budget/<int:budget_id>", methods=["GET", "POST"])
@login_required
def edit_budget(budget_id):
    current_user_id = session["user_id"]
    conn = get_db_connection()

    try:
        budget = conn.execute(
            """
            SELECT *
            FROM budgets
            WHERE id = ?
              AND user_id = ?
            """,
            (budget_id, current_user_id),
        ).fetchone()

        if not budget:
            flash("Budget not found", "error")
            return redirect(url_for("budgets.budgets"))

        if request.method == "POST":
            category_id = request.form.get("category_id")
            month = request.form.get("month")
            year = request.form.get("year")
            limit_amount = request.form.get("limit_amount")

            if not category_id or not month or not year or not limit_amount:
                flash("All fields are required", "error")
                return redirect(url_for("budgets.edit_budget", budget_id=budget_id))

            try:
                month = int(month)
                year = int(year)
                limit_amount = float(limit_amount)

                if month < 1 or month > 12:
                    flash("Invalid month", "error")
                    return redirect(url_for("budgets.edit_budget", budget_id=budget_id))

                if limit_amount <= 0:
                    flash("Limit must be positive", "error")
                    return redirect(url_for("budgets.edit_budget", budget_id=budget_id))

            except ValueError:
                flash("Invalid input", "error")
                return redirect(url_for("budgets.edit_budget", budget_id=budget_id))

            # Validate category (must be expense + active)
            category_check = conn.execute(
                """
                SELECT id
                FROM categories
                WHERE id = ?
                  AND user_id = ?
                  AND type = 'expense'
                  AND is_active = 1
                """,
                (category_id, current_user_id),
            ).fetchone()

            if not category_check:
                flash("Invalid category", "error")
                return redirect(url_for("budgets.edit_budget", budget_id=budget_id))

            try:
                conn.execute(
                    """
                    UPDATE budgets
                    SET category_id = ?,
                        month = ?,
                        year = ?,
                        limit_amount = ?
                    WHERE id = ?
                      AND user_id = ?
                    """,
                    (category_id, month, year, limit_amount, budget_id, current_user_id),
                )
                conn.commit()
                flash("Budget updated successfully", "success")
                return redirect(url_for("budgets.budgets"))

            except sqlite3.IntegrityError:
                flash("Budget already exists for this month", "error")
                return redirect(url_for("budgets.edit_budget", budget_id=budget_id))

        categories = conn.execute(
            """
            SELECT id, name
            FROM categories
            WHERE user_id = ?
              AND type = 'expense'
              AND is_active = 1
            """,
            (current_user_id,),
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "edit_budget.html",
        budget=dict(budget),
        categories=[dict(row) for row in categories],
    )

#---------------------------
# Delete Budget
#---------------------------
@budgets_bp.route("/delete-budget/<int:budget_id>", methods=["POST"])
@login_required
def delete_budget(budget_id):
    current_user_id = session["user_id"]
    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            DELETE FROM budgets
            WHERE id = ?
              AND user_id = ?
            """,
            (budget_id, current_user_id),
        )

        if cursor.rowcount == 0:
            flash("Budget not found", "error")
        else:
            conn.commit()
            flash("Budget deleted successfully", "success")

    finally:
        conn.close()

    return redirect(url_for("budgets.budgets"))
