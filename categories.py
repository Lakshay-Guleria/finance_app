import sqlite3

from flask import Blueprint, render_template, session,request, redirect, url_for, flash
from db import get_db_connection
from auth import login_required

categories_bp = Blueprint("categories", __name__)

# ---------------------------
# Categories
# ---------------------------
@categories_bp.route("/categories")
@login_required
def categories():

    current_user_id = session["user_id"]

    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM categories WHERE user_id = ? AND is_active = 1", (current_user_id,)
        ).fetchall()
    finally:
        conn.close()

    categories = []

    for row in rows:
        categories.append(dict(row))

    return render_template("categories.html", categories=categories)

# ---------------------------
# Create Categories
# ---------------------------


@categories_bp.route("/create-category", methods=["GET", "POST"])
@login_required
def create_category():
    
    current_user_id = session["user_id"]

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        category_type = request.form.get("type")

        if not name:
            flash("Category name is required", "error")
            return redirect(url_for("categories.create_category"))

        # Backend Validation
        if category_type not in ("income", "expense"):
           flash("Invalid category type", "error")
           return redirect(url_for("categories.create_category"))

        conn = get_db_connection()
        try:
            existing_category = conn.execute(
                """
                SELECT is_active
                FROM categories
                WHERE user_id = ?
                  AND lower(trim(name)) = lower(trim(?))
                  AND type = ?
                LIMIT 1
                """,
                (current_user_id, name, category_type),
            ).fetchone()

            if existing_category:
                if existing_category["is_active"]:
                    flash("Category with this name and type already exists", "error")
                else:
                    flash("This category already exists in archived categories. Restore it instead.", "warning")
                return redirect(url_for("categories.create_category"))

            conn.execute(
                "INSERT INTO categories (user_id, name, type) VALUES (?, ?, ?)",
                (current_user_id, name, category_type),
            )
            conn.commit()
            flash("Category created successfully", "success")
        except sqlite3.IntegrityError:
            flash("Category with this name and type already exists", "error")
        finally:
            conn.close()

        return redirect(url_for("categories.categories"))
    return render_template("create_category.html")


# ---------------------------
# Delete Categories
# ---------------------------
@categories_bp.route("/delete-category/<int:category_id>", methods=["POST"])
@login_required
def delete_category(category_id):
    current_user_id = session["user_id"]

    conn = get_db_connection()

    try:
        # Check category ownership
        category = conn.execute(
            """
             SELECT id FROM categories
             WHERE id = ? AND user_id = ? AND is_active = 1
             """,
            (category_id, current_user_id),
        ).fetchone()

        if not category:
            flash("Category not found or already inactive", "error")
            return redirect(url_for("categories.categories"))
        
        #check if category is linked to any transactions
        linked = conn.execute(
            """
            SELECT 1 
            FROM transactions
            WHERE category_id = ?  
            LIMIT 1
            """,
            (category_id,),
        ).fetchone()

        if linked:
            flash("Warning: this category has previous transactions linked to it.", "warning")

        # Soft delete (archive) the category
        conn.execute(
            """
            UPDATE categories
            SET is_active = 0
            WHERE id = ?
            """,
            (category_id,),
        )
        conn.commit()
        flash("Category archived successfully", "success")

    finally:
        conn.close()

    return redirect(url_for("categories.categories"))


# ---------------------------
# Archive Categories (Soft Delete)
# ---------------------------
@categories_bp.route("/categories/archived")
@login_required
def archived_categories():
    current_user_id = session["user_id"]

    conn = get_db_connection()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM categories
            WHERE user_id = ? AND is_active = 0
            """,
            (current_user_id,),
        ).fetchall()
    finally:
        conn.close()

    categories = [dict(row) for row in rows]
    return render_template("archived_categories.html", categories=categories)

# ---------------------------
# Restore Categories
# ---------------------------
@categories_bp.route("/restore-category/<int:category_id>", methods=["POST"])
@login_required
def restore_category(category_id):
    current_user_id = session["user_id"]
    conn = get_db_connection()

    try:
        category = conn.execute(
            """
            SELECT id, name, type
            FROM categories
            WHERE id = ?
              AND user_id = ?
              AND is_active = 0
            """,
            (category_id, current_user_id),
        ).fetchone()

        if not category:
            flash("Category not found or already active", "error")
            return redirect(url_for("categories.archived_categories"))

        duplicate_active_category = conn.execute(
            """
            SELECT id
            FROM categories
            WHERE user_id = ?
              AND id != ?
              AND is_active = 1
              AND lower(trim(name)) = lower(trim(?))
              AND type = ?
            LIMIT 1
            """,
            (current_user_id, category_id, category["name"], category["type"]),
        ).fetchone()

        if duplicate_active_category:
            flash("An active category with the same name and type already exists", "error")
            return redirect(url_for("categories.archived_categories"))

        conn.execute(
            """
            UPDATE categories
            SET is_active = 1
            WHERE id = ?
            """,
            (category_id,),
        )

        conn.commit()
        flash("Category restored successfully", "success")

    finally:
        conn.close()

    return redirect(url_for("categories.archived_categories"))

# ---------------------------
# Permanently Delete Categories
# ---------------------------
@categories_bp.route("/permanent-delete-category/<int:category_id>", methods=["POST"])
@login_required
def permanent_delete_category(category_id):
    current_user_id = session["user_id"]
    conn = get_db_connection()

    try:
        # Ensure category belongs to user and is archived
        category = conn.execute(
            """
            SELECT id
            FROM categories
            WHERE id = ?
              AND user_id = ?
              AND is_active = 0
            """,
            (category_id, current_user_id),
        ).fetchone()

        if not category:
            flash("Category must be archived before permanent deletion", "error")
            return redirect(url_for("categories.archived_categories"))

        # Check if transactions exist
        linked = conn.execute(
            """
            SELECT 1
            FROM transactions
            WHERE category_id = ?
            LIMIT 1
            """,
            (category_id,),
        ).fetchone()

        if linked:
            flash("Cannot permanently delete category with existing transactions", "error")
            return redirect(url_for("categories.archived_categories"))

        # Delete budgets first (safe to cascade manually)
        conn.execute(
            """
            DELETE FROM budgets
            WHERE category_id = ?
            """,
            (category_id,),
        )

        # Delete category
        conn.execute(
            """
            DELETE FROM categories
            WHERE id = ?
            """,
            (category_id,),
        )

        conn.commit()
        flash("Category permanently deleted", "success")

    finally:
        conn.close()

    return redirect(url_for("categories.archived_categories"))
