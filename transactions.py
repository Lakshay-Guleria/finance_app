import csv
import io
from datetime import date, datetime

from flask import Blueprint, Response, render_template, session, request, redirect, url_for, flash
from db import get_db_connection
from auth import login_required

transactions_bp = Blueprint("transactions", __name__)


def _is_future_transaction_date(transaction_date):
    try:
        parsed_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    return parsed_date > date.today()


def _build_pagination_pages(current_page, total_pages, window_size=3):
    if total_pages <= 2:
        return []

    start_page = current_page if current_page > 1 else 2
    end_page = min(total_pages - 1, start_page + window_size - 1)

    if end_page - start_page + 1 < window_size:
        start_page = max(2, end_page - window_size + 1)

    return list(range(start_page, end_page + 1))


def _get_filtered_transactions_data(current_user_id):
    per_page = 10
    page = request.args.get("page", type=int) or 1
    if page < 1:
        page = 1

    selected_category_id = request.args.get("category_id", type=int)
    selected_type = (request.args.get("type") or "").strip().lower()
    search_query = (request.args.get("q") or "").strip()
    start_date = (request.args.get("start_date") or "").strip()
    end_date = (request.args.get("end_date") or "").strip()
    min_amount_raw = (request.args.get("min_amount") or "").strip()
    max_amount_raw = (request.args.get("max_amount") or "").strip()

    min_amount = None
    max_amount = None

    try:
        if min_amount_raw:
            min_amount = float(min_amount_raw)
    except ValueError:
        min_amount_raw = ""

    try:
        if max_amount_raw:
            max_amount = float(max_amount_raw)
    except ValueError:
        max_amount_raw = ""

    conn = get_db_connection()
    try:
        category_rows = conn.execute(
            """
            SELECT id, name, type
            FROM categories
            WHERE user_id = ?
              AND is_active = 1
            ORDER BY name ASC
            """,
            (current_user_id,),
        ).fetchall()

        categories = [dict(row) for row in category_rows]

        query = """
            SELECT 
                transactions.id,
                categories.name AS category_name,
                categories.type,
                transactions.amount,
                transactions.description,
                transactions.date
            FROM transactions
            JOIN categories 
                ON transactions.category_id = categories.id
            WHERE transactions.user_id = ?
        """
        params = [current_user_id]

        if selected_category_id:
            valid_category = conn.execute(
                """
                SELECT id
                FROM categories
                WHERE id = ?
                  AND user_id = ?
                  AND is_active = 1
                """,
                (selected_category_id, current_user_id),
            ).fetchone()

            if valid_category:
                query += " AND transactions.category_id = ?"
                params.append(selected_category_id)
            else:
                selected_category_id = None

        if selected_type in ("income", "expense"):
            query += " AND categories.type = ?"
            params.append(selected_type)
        else:
            selected_type = ""

        if search_query:
            query += """
                AND (
                    lower(IFNULL(transactions.description, '')) LIKE lower(?)
                    OR lower(categories.name) LIKE lower(?)
                )
            """
            search_term = f"%{search_query}%"
            params.extend([search_term, search_term])

        if start_date:
            query += " AND transactions.date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND transactions.date <= ?"
            params.append(end_date)

        if min_amount is not None:
            query += " AND transactions.amount >= ?"
            params.append(min_amount)

        if max_amount is not None:
            query += " AND transactions.amount <= ?"
            params.append(max_amount)

        query += " ORDER BY transactions.date DESC"

        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    all_transactions = [dict(row) for row in rows]
    total_transactions = len(all_transactions)
    total_pages = max(1, (total_transactions + per_page - 1) // per_page)

    if page > total_pages:
        page = total_pages

    pagination_pages = _build_pagination_pages(page, total_pages)

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    transactions_list = all_transactions[start_index:end_index]

    active_filters = []
    if search_query:
        active_filters.append(f"Search: {search_query}")
    if selected_category_id:
        selected_category = next(
            (category for category in categories if category["id"] == selected_category_id),
            None,
        )
        if selected_category:
            active_filters.append(f"Category: {selected_category['name']}")
    if selected_type:
        active_filters.append(f"Type: {selected_type.title()}")
    if start_date:
        active_filters.append(f"From: {start_date}")
    if end_date:
        active_filters.append(f"To: {end_date}")
    if min_amount_raw:
        active_filters.append(f"Min Amount: {min_amount_raw}")
    if max_amount_raw:
        active_filters.append(f"Max Amount: {max_amount_raw}")

    return {
        "transactions": transactions_list,
        "page": page,
        "per_page": per_page,
        "total_transactions": total_transactions,
        "total_pages": total_pages,
        "pagination_pages": pagination_pages,
        "has_previous_page": page > 1,
        "has_next_page": page < total_pages,
        "row_number_start": start_index + 1,
        "categories": categories,
        "selected_category_id": selected_category_id,
        "selected_type": selected_type,
        "search_query": search_query,
        "start_date": start_date,
        "end_date": end_date,
        "min_amount": min_amount_raw,
        "max_amount": max_amount_raw,
        "has_active_filters": bool(active_filters),
        "active_filters": active_filters,
    }


# ---------------------------
# transactions
# ---------------------------


@transactions_bp.route("/transactions")
@login_required
def transactions():

    current_user_id = session["user_id"]
    transaction_data = _get_filtered_transactions_data(current_user_id)

    return render_template(
        "transactions.html",
        transactions=transaction_data["transactions"],
        page=transaction_data["page"],
        per_page=transaction_data["per_page"],
        total_transactions=transaction_data["total_transactions"],
        total_pages=transaction_data["total_pages"],
        pagination_pages=transaction_data["pagination_pages"],
        has_previous_page=transaction_data["has_previous_page"],
        has_next_page=transaction_data["has_next_page"],
        row_number_start=transaction_data["row_number_start"],
        categories=transaction_data["categories"],
        selected_category_id=transaction_data["selected_category_id"],
        selected_type=transaction_data["selected_type"],
        search_query=transaction_data["search_query"],
        start_date=transaction_data["start_date"],
        end_date=transaction_data["end_date"],
        min_amount=transaction_data["min_amount"],
        max_amount=transaction_data["max_amount"],
        has_active_filters=transaction_data["has_active_filters"],
        active_filters=transaction_data["active_filters"],
    )


@transactions_bp.route("/transactions/export")
@login_required
def export_transactions():
    current_user_id = session["user_id"]
    transaction_data = _get_filtered_transactions_data(current_user_id)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["ID", "Category", "Type", "Amount", "Description", "Date"])

    for row in transaction_data["transactions"]:
        writer.writerow(
            [
                row["id"],
                row["category_name"],
                row["type"],
                row["amount"],
                row["description"] or "",
                row["date"],
            ]
        )

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions_export.csv"},
    )


# ---------------------------
# Create Transactiosn
# ---------------------------


@transactions_bp.route("/create-transaction", methods=["GET", "POST"])
@login_required
def create_transaction():
    current_user_id = session["user_id"]

    conn = get_db_connection()

    # Fetch categories first
    category_rows = conn.execute(
        """
        SELECT id, name, type
        FROM categories
        WHERE user_id = ?
        AND is_active = 1
        """,
        (current_user_id,),
    ).fetchall()

    categories = [dict(row) for row in category_rows]

    if request.method == "POST":
        category_id = request.form.get("category_id")
        amount = request.form.get("amount")
        description = request.form.get("description")
        date = request.form.get("date")

        if not category_id or not amount or not date:
            conn.close()
            flash("Missing required fields", "error")
            return redirect(url_for("transactions.create_transaction"))

        try:
            amount = float(amount)
            if amount <= 0:
                conn.close()
                flash("Amount must be positive", "error")
                return redirect(url_for("transactions.create_transaction"))
        except ValueError:
            conn.close()
            flash("Invalid amount", "error")
            return redirect(url_for("transactions.create_transaction"))

        is_future_date = _is_future_transaction_date(date)
        if is_future_date is None:
            conn.close()
            flash("Invalid transaction date", "error")
            return redirect(url_for("transactions.create_transaction"))
        if is_future_date:
            conn.close()
            flash("Future dates are not allowed for transactions", "error")
            return redirect(url_for("transactions.create_transaction"))

        category_check = conn.execute(
            """
            SELECT id FROM categories
            WHERE id = ? AND user_id = ?
            AND is_active = 1
            """,
            (category_id, current_user_id),
        ).fetchone()

        if category_check is None:
            conn.close()
            flash("Invalid category", "error")
            return redirect(url_for("transactions.create_transaction"))

        conn.execute(
            """
            INSERT INTO transactions
            (user_id, category_id, amount, description, date, created_at)
            VALUES (?, ?, ?, ?, ?, date('now'))
            """,
            (current_user_id, category_id, amount, description, date),
        )

        conn.commit()
        conn.close()

        flash("Transaction created successfully", "success")
        return redirect(url_for("transactions.transactions"))
    conn.close()

    if not categories:
        return render_template("create_transaction.html", categories=None)

    return render_template("create_transaction.html", categories=categories)


#---------------------------
# Edit Transaction
#---------------------------
@transactions_bp.route("/edit-transaction/<int:transaction_id>", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    current_user_id = session["user_id"]
    conn = get_db_connection()

    try:
        # Fetch transaction (ownership check)
        transaction = conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE id = ?
              AND user_id = ?
            """,
            (transaction_id, current_user_id),
        ).fetchone()

        if not transaction:
            flash("Transaction not found", "error")
            return redirect(url_for("transactions.transactions"))

        if request.method == "POST":
            category_id = request.form.get("category_id")
            amount = request.form.get("amount")
            description = request.form.get("description")
            date = request.form.get("date")

            if not category_id or not amount or not date:
                flash("Missing required fields", "error")
                return redirect(url_for("transactions.edit_transaction", transaction_id=transaction_id))

            try:
                amount = float(amount)
                if amount <= 0:
                    flash("Amount must be positive", "error")
                    return redirect(url_for("transactions.edit_transaction", transaction_id=transaction_id))
            except ValueError:
                flash("Invalid amount", "error")
                return redirect(url_for("transactions.edit_transaction", transaction_id=transaction_id))

            is_future_date = _is_future_transaction_date(date)
            if is_future_date is None:
                flash("Invalid transaction date", "error")
                return redirect(url_for("transactions.edit_transaction", transaction_id=transaction_id))
            if is_future_date:
                flash("Future dates are not allowed for transactions", "error")
                return redirect(url_for("transactions.edit_transaction", transaction_id=transaction_id))

            # Validate category ownership + active
            category_check = conn.execute(
                """
                SELECT id
                FROM categories
                WHERE id = ?
                  AND user_id = ?
                  AND is_active = 1
                """,
                (category_id, current_user_id),
            ).fetchone()

            if not category_check:
                flash("Invalid category", "error")
                return redirect(url_for("transactions.edit_transaction", transaction_id=transaction_id))

            conn.execute(
                """
                UPDATE transactions
                SET category_id = ?,
                    amount = ?,
                    description = ?,
                    date = ?
                WHERE id = ?
                  AND user_id = ?
                """,
                (category_id, amount, description, date, transaction_id, current_user_id),
            )

            conn.commit()
            flash("Transaction updated successfully", "success")
            return redirect(url_for("transactions.transactions"))

        # GET case — load categories
        categories = conn.execute(
            """
            SELECT id, name, type
            FROM categories
            WHERE user_id = ?
              AND is_active = 1
            """,
            (current_user_id,),
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "edit_transaction.html",
        transaction=dict(transaction),
        categories=[dict(row) for row in categories],
    )


#---------------------------
# Delete Transaction
#---------------------------
@transactions_bp.route("/delete-transaction/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    current_user_id = session["user_id"]
    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            DELETE FROM transactions
            WHERE id = ?
              AND user_id = ?
            """,
            (transaction_id, current_user_id),
        )

        if cursor.rowcount == 0:
            flash("Transaction not found", "error")
        else:
            conn.commit()
            flash("Transaction deleted successfully", "success")

    finally:
        conn.close()

    return redirect(url_for("transactions.transactions"))
