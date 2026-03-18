import json
from datetime import date, timedelta, datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from supabase_client import get_supabase
import config

user_bp = Blueprint("user", __name__, url_prefix="/",
                    template_folder="../templates/user")


def user_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_user"):
            return redirect(url_for("user.login"))
        return f(*args, **kwargs)
    return decorated


def invoice_role_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_user"):
            return redirect(url_for("user.login"))
        if (session.get("user_role") or "").lower() != "invoice":
            flash("You do not have invoice access.", "warning")
            return redirect(url_for("user.home"))
        return f(*args, **kwargs)
    return decorated


def _pick_first_value(row, keys):
    for key in keys:
        if key in row and row.get(key) is not None:
            return row.get(key)
    return None


def _format_query_error(exc):
    raw = str(exc)
    try:
        args = getattr(exc, "args", None)
        if args and len(args) > 0:
            raw = str(args[0])
    except Exception:
        pass
    return raw


def _get_user_record(sb, username):
    configured = getattr(config, "USER_AUTH_TABLE", "user_accounts")
    candidate_tables = [configured, "user_accounts"]

    seen = set()
    username = (username or "").strip()
    esc_username = username.replace("'", "''")
    last_sql = ""
    for table_name in candidate_tables:
        if not table_name or table_name in seen:
            continue
        seen.add(table_name)
        sql_exact = f"SELECT username, password, role FROM {table_name} WHERE username = '{esc_username}' LIMIT 1;"
        try:
            last_sql = sql_exact
            rows = sb.table(table_name).select("username, password, role").eq("username", username).limit(1).execute().data
            if rows:
                raw = rows[0]
                normalized = {
                    "username": _pick_first_value(raw, ["username"]),
                    "password": _pick_first_value(raw, ["password"]),
                    "role": _pick_first_value(raw, ["role"]),
                }
                return normalized, None, last_sql
        except Exception as exc:
            err = str(exc).lower()
            if "permission" in err or "rls" in err or "policy" in err:
                return None, f"Cannot read user table. Add SELECT policy for user login table. ({_format_query_error(exc)})", last_sql
            return None, _format_query_error(exc), last_sql

    return None, None, last_sql


@user_bp.route("/user/login", methods=["GET", "POST"])
def login():
    if session.get("is_user"):
        return redirect(url_for("user.home"))

    login_error = session.pop("user_login_error", None)
    login_debug = session.get("user_login_debug", "")
    login_sql = session.get("user_login_sql", "")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            login_error = "Please enter username and password."
            session["user_login_error"] = login_error
            session["user_login_debug"] = "Validation: missing username/password before Supabase query."
            flash(login_error, "danger")
            return render_template("user/login.html", login_error=login_error, login_debug=session.get("user_login_debug", ""), login_sql=session.get("user_login_sql", ""))

        sb = get_supabase()
        user_row, lookup_error, sql_text = _get_user_record(sb, username)
        session["user_login_sql"] = sql_text
        if lookup_error:
            login_error = f"Login query error: {lookup_error}"
            session["user_login_error"] = login_error
            session["user_login_debug"] = f"Supabase query failed: {lookup_error}"
            flash(login_error, "danger")
            return render_template("user/login.html", login_error=login_error, login_debug=session.get("user_login_debug", ""), login_sql=session.get("user_login_sql", ""))

        if not user_row:
            login_error = "Invalid username or password."
            session["user_login_error"] = login_error
            session["user_login_debug"] = "Supabase query succeeded. No matching username found."
            flash(login_error, "danger")
            return render_template("user/login.html", login_error=login_error, login_debug=session.get("user_login_debug", ""), login_sql=session.get("user_login_sql", ""))

        stored_password = str(user_row.get("password") or "").strip()
        role = str(user_row.get("role") or "").strip().lower()
        if stored_password != password:
            login_error = "Invalid username or password."
            session["user_login_error"] = login_error
            session["user_login_debug"] = "Supabase query succeeded. Username matched, password mismatch."
            flash(login_error, "danger")
            return render_template("user/login.html", login_error=login_error, login_debug=session.get("user_login_debug", ""), login_sql=session.get("user_login_sql", ""))

        if role not in {"invoice", "order"}:
            login_error = "User role is not allowed."
            session["user_login_error"] = login_error
            session["user_login_debug"] = f"Supabase query succeeded. Unsupported role value: {role}"
            flash(login_error, "danger")
            return render_template("user/login.html", login_error=login_error, login_debug=session.get("user_login_debug", ""), login_sql=session.get("user_login_sql", ""))

        session["is_user"] = True
        session["user_username"] = username
        session["user_role"] = role
        session.pop("user_login_error", None)
        session.pop("user_login_debug", None)
        session.pop("user_login_sql", None)
        flash("Logged in successfully.", "success")
        if role == "invoice":
            return redirect(url_for("user.home"))
        return redirect(url_for("user.order_home"))

    return render_template("user/login.html", login_error=login_error, login_debug=login_debug, login_sql=login_sql)


@user_bp.route("/user/logout")
def logout():
    session.pop("is_user", None)
    session.pop("user_username", None)
    session.pop("user_role", None)
    flash("Logged out.", "info")
    return redirect(url_for("user.login"))


@user_bp.route("/user/change-password", methods=["GET", "POST"])
@user_login_required
def change_password():
    username = (session.get("user_username") or "").strip()
    if not username:
        flash("Session expired. Please login again.", "warning")
        return redirect(url_for("user.logout"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not current_password or not new_password or not confirm_password:
            flash("Please fill all password fields.", "danger")
            return render_template("user/change_password.html")

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "danger")
            return render_template("user/change_password.html")

        if len(new_password) < 4:
            flash("New password must be at least 4 characters.", "danger")
            return render_template("user/change_password.html")

        sb = get_supabase()
        user_row, lookup_error, _ = _get_user_record(sb, username)
        if lookup_error:
            flash(f"Password check failed: {lookup_error}", "danger")
            return render_template("user/change_password.html")

        if not user_row:
            flash("User record not found.", "danger")
            return render_template("user/change_password.html")

        stored_password = str(user_row.get("password") or "").strip()
        if stored_password != current_password:
            flash("Current password is incorrect.", "danger")
            return render_template("user/change_password.html")

        table_name = getattr(config, "USER_AUTH_TABLE", "user_accounts")
        try:
            sb.table(table_name).update({"password": new_password}).eq("username", username).execute()
        except Exception as exc:
            flash(f"Could not update password: {exc}", "danger")
            return render_template("user/change_password.html")

        flash("Password updated successfully.", "success")
        return redirect(url_for("user.change_password"))

    return render_template("user/change_password.html")


def _generate_invoice_number(sb):
    """Generate next invoice number like INV-00001 based on count."""
    result = sb.table("invoices").select("id", count="exact").execute()
    next_num = (result.count or 0) + 1
    return f"INV-{next_num:05d}"


@user_bp.route("/")
@user_login_required
def home():
    role = (session.get("user_role") or "").lower()
    if role == "order":
        return redirect(url_for("user.order_home"))

    if role != "invoice":
        flash("You do not have access to this section.", "warning")
        return redirect(url_for("user.logout"))

    sb = get_supabase()
    parties = sb.table("parties").select("*").order("name").execute().data
    addas = sb.table("addas").select("*").order("name").execute().data

    # Date options: today and 3 days back
    today = date.today()
    date_options = [(today - timedelta(days=i)).isoformat() for i in range(4)]

    # User's recent invoices (with line items)
    invoices = sb.table("invoices").select(
        "*, parties(name), addas(name, number), invoice_items(*, items(item_code, name, box_qty))"
    ).order("created_at", desc=True).limit(30).execute().data

    return render_template("user/home.html",
                           parties=parties, addas=addas,
                           date_options=date_options,
                           invoices=invoices)


@user_bp.route("/orders")
@user_login_required
def order_home():
    role = (session.get("user_role") or "").lower()
    if role != "order":
        flash("You do not have order access.", "warning")
        return redirect(url_for("user.home"))
    return render_template("user/order_home.html")


# --- API: search items by code or name (autocomplete) ---
@user_bp.route("/api/items/search")
@invoice_role_required
def api_items_search():
    q = request.args.get("q", "").strip()
    if len(q) < 1:
        return jsonify([])
    sb = get_supabase()
    results = sb.table("items").select("id, item_code, name").or_(
        f"item_code.ilike.%{q}%,name.ilike.%{q}%"
    ).limit(15).execute().data

    # Fetch total stock across all warehouses for each matched item
    if results:
        item_ids = [r["id"] for r in results]
        stock_rows = sb.table("warehouse_stock").select(
            "item_id, stock"
        ).in_("item_id", item_ids).execute().data

        stock_map = {}
        for sr in stock_rows:
            stock_map[sr["item_id"]] = stock_map.get(sr["item_id"], 0) + sr["stock"]

        for r in results:
            r["total_stock"] = stock_map.get(r["id"], 0)

    return jsonify(results)


# --- API: search addas by name (autocomplete) ---
@user_bp.route("/api/addas/search")
@invoice_role_required
def api_addas_search():
    q = request.args.get("q", "").strip()
    if len(q) < 1:
        return jsonify([])
    sb = get_supabase()
    rows = sb.table("addas").select("name").ilike(
        "name", f"%{q}%"
    ).order("name").limit(100).execute().data

    seen = set()
    results = []
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({"name": name})
        if len(results) >= 15:
            break

    return jsonify(results)


def _resolve_adda_id(sb, form):
    """Return adda_id from form.
    """
    adda_id = form.get("adda_id", "").strip()
    adda_name = form.get("adda_name", "").strip()
    adda_number = form.get("adda_number", "").strip()

    if adda_id:
        return int(adda_id)

    if adda_name and adda_number:
        existing = sb.table("addas").select("id").ilike("name", adda_name).eq("number", adda_number).limit(1).execute().data
        if existing:
            return existing[0]["id"]

        try:
            result = sb.table("addas").insert({"name": adda_name, "number": adda_number}).execute()
            return result.data[0]["id"]
        except Exception:
            # Backward-compat fallback for old DBs that still have UNIQUE(name)
            # (constraint: addas_name_key). Reuse the existing row for this name.
            by_name = sb.table("addas").select("id").ilike("name", adda_name).limit(1).execute().data
            if by_name:
                row_id = by_name[0]["id"]
                sb.table("addas").update({"number": adda_number}).eq("id", row_id).execute()
                return row_id
            raise

    if adda_name:
        # Legacy rows may have empty number.
        existing = sb.table("addas").select("id").ilike("name", adda_name).eq("number", "").limit(1).execute().data
        if existing:
            return existing[0]["id"]
        return None
    return None


def _get_item_discount_map(sb, item_ids):
    """Return {item_id: discount} from items table for selected item ids."""
    if not item_ids:
        return {}
    rows = sb.table("items").select("id, discount").in_("id", item_ids).execute().data
    return {int(r["id"]): float(r.get("discount") or 0) for r in rows}


# --- Submit new invoice (with multiple items) ---
@user_bp.route("/invoice/add", methods=["POST"])
@invoice_role_required
def add_invoice():
    party_id = request.form.get("party_id")
    delivery_paid = request.form.get("delivery_paid") == "yes"
    delivery_amount = request.form.get("delivery_amount", "0").strip() or "0"
    invoice_date = request.form.get("invoice_date", "")
    items_json = request.form.get("items_json", "[]")

    # Parse items list
    try:
        items_list = json.loads(items_json)
    except (json.JSONDecodeError, TypeError):
        items_list = []

    sb = get_supabase()
    adda_id = _resolve_adda_id(sb, request.form)

    if not adda_id:
        flash("Please select an existing adda, or enter adda name and adda number.", "danger")
        return redirect(url_for("user.home"))

    if not all([party_id, invoice_date]) or not items_list:
        flash("Please fill all fields and add at least one item.", "danger")
        return redirect(url_for("user.home"))

    # Validate each item entry
    for entry in items_list:
        if not entry.get("item_id") or not entry.get("quantity"):
            flash("Each item must have a valid ID and quantity.", "danger")
            return redirect(url_for("user.home"))

    # Validate date is within allowed range (today to 3 days ago)
    today = date.today()
    try:
        inv_date = date.fromisoformat(invoice_date)
    except ValueError:
        flash("Invalid date.", "danger")
        return redirect(url_for("user.home"))

    earliest = today - timedelta(days=3)
    if inv_date < earliest or inv_date > today:
        flash("Invoice date must be within the last 3 days.", "danger")
        return redirect(url_for("user.home"))

    item_ids = [int(entry["item_id"]) for entry in items_list]
    item_discount_map = _get_item_discount_map(sb, item_ids)

    # Generate invoice number
    inv_number = _generate_invoice_number(sb)

    # Create invoice header
    inv_result = sb.table("invoices").insert({
        "invoice_number": inv_number,
        "party_id": int(party_id),
        "adda_id": int(adda_id),
        "delivery_paid": delivery_paid,
        "delivery_amount": float(delivery_amount) if not delivery_paid else 0,
        "invoice_date": invoice_date,
        "status": "pending",
    }).execute()

    invoice_id = inv_result.data[0]["id"]

    # Insert line items
    line_items = [
        {
            "invoice_id": invoice_id,
            "item_id": int(entry["item_id"]),
            "quantity": int(entry["quantity"]),
            "discount": item_discount_map.get(int(entry["item_id"]), 0.0),
        }
        for entry in items_list
    ]
    sb.table("invoice_items").insert(line_items).execute()

    flash("Invoice " + inv_number + " submitted!", "success")
    return redirect(url_for("user.view_invoice", inv_id=invoice_id))


# --- View full invoice ---
@user_bp.route("/invoice/<int:inv_id>")
@invoice_role_required
def view_invoice(inv_id):
    sb = get_supabase()
    rows = sb.table("invoices").select(
        "*, parties(name), addas(name, number), invoice_items(*, items(item_code, name, box_qty))"
    ).eq("id", inv_id).execute().data
    if not rows:
        flash("Invoice not found.", "danger")
        return redirect(url_for("user.home"))
    return render_template("user/invoice_view.html", inv=rows[0])


# --- Edit invoice (only pending) ---
@user_bp.route("/invoice/<int:inv_id>/edit", methods=["GET", "POST"])
@invoice_role_required
def edit_invoice(inv_id):
    sb = get_supabase()

    # Fetch invoice
    rows = sb.table("invoices").select(
        "*, parties(name), addas(name, number), invoice_items(*, items(item_code, name, box_qty))"
    ).eq("id", inv_id).execute().data
    if not rows:
        flash("Invoice not found.", "danger")
        return redirect(url_for("user.home"))

    inv = rows[0]
    if inv["status"] != "pending":
        flash("Only pending invoices can be edited.", "warning")
        return redirect(url_for("user.view_invoice", inv_id=inv_id))

    if request.method == "GET":
        parties = sb.table("parties").select("*").order("name").execute().data
        addas = sb.table("addas").select("*").order("name").execute().data
        today = date.today()
        date_options = [(today - timedelta(days=i)).isoformat() for i in range(4)]
        initial_adda_name = inv.get("addas", {}).get("name", "") if inv.get("addas") else ""
        initial_adda_number = inv.get("addas", {}).get("number", "") if inv.get("addas") else ""
        return render_template("user/invoice_edit.html", inv=inv,
                               parties=parties, addas=addas,
                               date_options=date_options,
                               initial_adda_name=initial_adda_name,
                               initial_adda_number=initial_adda_number)

    # POST — update the invoice
    party_id = request.form.get("party_id")
    delivery_paid = request.form.get("delivery_paid") == "yes"
    delivery_amount = request.form.get("delivery_amount", "0").strip() or "0"
    invoice_date = request.form.get("invoice_date", "")
    items_json = request.form.get("items_json", "[]")

    try:
        items_list = json.loads(items_json)
    except (json.JSONDecodeError, TypeError):
        items_list = []

    adda_id = _resolve_adda_id(sb, request.form)

    if not adda_id:
        flash("Please select an existing adda, or enter adda name and adda number.", "danger")
        return redirect(url_for("user.edit_invoice", inv_id=inv_id))

    if not all([party_id, invoice_date]) or not items_list:
        flash("Please fill all fields and add at least one item.", "danger")
        return redirect(url_for("user.edit_invoice", inv_id=inv_id))

    today = date.today()
    try:
        inv_date = date.fromisoformat(invoice_date)
    except ValueError:
        flash("Invalid date.", "danger")
        return redirect(url_for("user.edit_invoice", inv_id=inv_id))

    earliest = today - timedelta(days=3)
    if inv_date < earliest or inv_date > today:
        flash("Invoice date must be within the last 3 days.", "danger")
        return redirect(url_for("user.edit_invoice", inv_id=inv_id))

    item_ids = [int(entry["item_id"]) for entry in items_list]
    item_discount_map = _get_item_discount_map(sb, item_ids)

    # Update invoice header
    sb.table("invoices").update({
        "party_id": int(party_id),
        "adda_id": int(adda_id),
        "delivery_paid": delivery_paid,
        "delivery_amount": float(delivery_amount) if not delivery_paid else 0,
        "invoice_date": invoice_date,
    }).eq("id", inv_id).execute()

    # Delete old line items and re-insert
    sb.table("invoice_items").delete().eq("invoice_id", inv_id).execute()
    line_items = [
        {
            "invoice_id": inv_id,
            "item_id": int(entry["item_id"]),
            "quantity": int(entry["quantity"]),
            "discount": item_discount_map.get(int(entry["item_id"]), 0.0),
        }
        for entry in items_list
    ]
    sb.table("invoice_items").insert(line_items).execute()

    flash("Invoice updated!", "success")
    return redirect(url_for("user.view_invoice", inv_id=inv_id))
