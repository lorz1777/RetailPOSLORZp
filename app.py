"""Retail POS - Flask + MySQL, single admin role.

Pages: login, dashboard, products, inventory, checkout (POS), sales, reports.
"""
import csv
import io
import os
import secrets
import time
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import wraps

import pymysql
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from pymysql.cursors import DictCursor
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

CENT = Decimal("0.01")
MAX_PRICE = Decimal("99999999.99")
MAX_SALE = Decimal("9999999999.99")
STORE_NAME = os.environ.get("STORE_NAME", "My Retail Store")
CURRENCY = os.environ.get("CURRENCY_SYMBOL", "$")
try:
    TAX_RATE = Decimal(os.environ.get("TAX_RATE", "0"))
    if not (Decimal("0") <= TAX_RATE < Decimal("1")):
        TAX_RATE = Decimal("0")
except InvalidOperation:
    TAX_RATE = Decimal("0")
PAYMENT_METHODS = ("cash", "card", "ewallet")
PAGE_SIZE = 50

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=1024 * 1024,
)
if not os.environ.get("SECRET_KEY"):
    app.logger.warning("SECRET_KEY is not set: sessions will reset every time the app restarts.")


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "retail_pos"),
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            if exc is not None:
                db.rollback()
        finally:
            db.close()


def query(sql, args=(), one=False):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone() if one else cur.fetchall()


def execute(sql, args=()):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, args)
        last_id = cur.lastrowid
    db.commit()
    return last_id


def is_duplicate(exc):
    return isinstance(exc, pymysql.err.IntegrityError) and exc.args and exc.args[0] == 1062


def db_today():
    return query("SELECT CURDATE() AS d", one=True)["d"]


def escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# --------------------------------------------------------------------------
# Money / parsing helpers
# --------------------------------------------------------------------------
def money(value, default=None):
    """Parse a money string into a 2-decimal Decimal, or return default."""
    if value is None or str(value).strip() == "":
        return default
    try:
        d = Decimal(str(value).strip().replace(",", ""))
    except InvalidOperation:
        return default
    if not d.is_finite():
        return default
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def to_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_range(default_days=30):
    today = db_today()

    def parse(value, fallback):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            return fallback

    end = parse(request.args.get("end"), today)
    start = parse(request.args.get("start"), end - timedelta(days=default_days - 1))
    if start > end:
        start, end = end, start
    return start, end


RANGE_SQL = "s.created_at >= %s AND s.created_at < DATE_ADD(%s, INTERVAL 1 DAY)"


# --------------------------------------------------------------------------
# Template helpers
# --------------------------------------------------------------------------
@app.template_filter("money")
def money_filter(value):
    return f"{CURRENCY}{Decimal(value or 0):,.2f}"


@app.template_filter("receipt_no")
def receipt_no_filter(sale_id):
    return f"R{int(sale_id):06d}"


@app.context_processor
def inject_globals():
    return {
        "store_name": STORE_NAME,
        "currency": CURRENCY,
        "tax_rate": float(TAX_RATE),
        "tax_percent": format((TAX_RATE * 100).normalize(), "f"),
        "payment_methods": PAYMENT_METHODS,
    }


# --------------------------------------------------------------------------
# Security: CSRF, login, headers
# --------------------------------------------------------------------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
            abort(400, "Your session expired or the form was invalid. Please go back, reload and try again.")


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    if "admin_id" in session:
        resp.headers["Cache-Control"] = "no-store"
    return resp


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify(error="Please sign in again."), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.errorhandler(HTTPException)
def http_error(err):
    if request.path.startswith("/api/"):
        return jsonify(error=err.description), err.code
    return render_template("error.html", code=err.code, message=err.description), err.code


_failed_logins = {}  # ip -> [timestamps]; per-process, resets on restart


def too_many_attempts(ip):
    now = time.time()
    recent = [t for t in _failed_logins.get(ip, []) if now - t < 300]
    _failed_logins[ip] = recent
    return len(recent) >= 5


@app.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if too_many_attempts(ip):
            flash("Too many failed attempts. Please wait a few minutes and try again.", "error")
            return render_template("login.html"), 429
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = query("SELECT id, username, password_hash FROM admins WHERE username = %s", (username,), one=True)
        if admin and check_password_hash(admin["password_hash"], password):
            _failed_logins.pop(ip, None)
            session.clear()
            session.permanent = True
            session["admin_id"] = admin["id"]
            session["username"] = admin["username"]
            nxt = request.args.get("next", "")
            if not nxt.startswith("/") or nxt.startswith("//") or "\\" in nxt:
                nxt = url_for("dashboard")
            return redirect(nxt)
        _failed_logins.setdefault(ip, []).append(time.time())
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "ok")
    return redirect(url_for("login"))


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")
        admin = query("SELECT password_hash FROM admins WHERE id = %s", (session["admin_id"],), one=True)
        if not admin or not check_password_hash(admin["password_hash"], current):
            flash("Your current password is incorrect.", "error")
        elif len(new) < 8:
            flash("The new password must be at least 8 characters.", "error")
        elif new != confirm:
            flash("The new passwords do not match.", "error")
        else:
            execute("UPDATE admins SET password_hash = %s WHERE id = %s",
                    (generate_password_hash(new), session["admin_id"]))
            flash("Password updated.", "ok")
            return redirect(url_for("dashboard"))
    return render_template("password.html")


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    today = query(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total), 0) AS revenue FROM sales "
        "WHERE status = 'completed' AND created_at >= CURDATE()", one=True)
    stock = query(
        "SELECT COUNT(*) AS products, COALESCE(SUM(stock <= reorder_level), 0) AS low "
        "FROM products WHERE is_active = 1", one=True)
    low_items = query(
        "SELECT id, sku, name, stock, reorder_level FROM products "
        "WHERE is_active = 1 AND stock <= reorder_level ORDER BY stock, name LIMIT 8")
    recent = query("SELECT id, total, payment_method, status, created_at FROM sales ORDER BY id DESC LIMIT 8")
    return render_template("dashboard.html", today=today, stock=stock, low_items=low_items, recent=recent)


# --------------------------------------------------------------------------
# Product management
# --------------------------------------------------------------------------
def parse_product_form(form, creating):
    errors = []
    sku = form.get("sku", "").strip()
    name = form.get("name", "").strip()
    barcode = form.get("barcode", "").strip() or None
    category = form.get("category", "").strip() or None
    price = money(form.get("price"))
    cost = money(form.get("cost"), Decimal("0.00"))
    reorder = to_int(form.get("reorder_level") or "0")
    opening = to_int(form.get("stock") or "0") if creating else 0

    if not sku or len(sku) > 40:
        errors.append("SKU is required (max 40 characters).")
    if not name or len(name) > 150:
        errors.append("Name is required (max 150 characters).")
    if barcode and len(barcode) > 64:
        errors.append("Barcode is too long (max 64 characters).")
    if category and len(category) > 80:
        errors.append("Category is too long (max 80 characters).")
    if price is None or price < 0 or price > MAX_PRICE:
        errors.append("Enter a valid selling price.")
    if cost is None or cost < 0 or cost > MAX_PRICE:
        errors.append("Enter a valid cost (or leave it blank).")
    if reorder is None or not (0 <= reorder <= 1_000_000):
        errors.append("Reorder level must be a whole number of 0 or more.")
    if opening is None or not (0 <= opening <= 1_000_000):
        errors.append("Opening stock must be a whole number of 0 or more.")

    data = {"sku": sku, "barcode": barcode, "name": name, "category": category,
            "price": price, "cost": cost, "reorder_level": reorder, "stock": opening}
    return data, errors


@app.route("/products")
@login_required
def products():
    q = request.args.get("q", "").strip()
    show_inactive = request.args.get("inactive") == "1"
    sql = "SELECT * FROM products WHERE 1 = 1"
    args = []
    if q:
        like = f"%{escape_like(q)}%"
        sql += " AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s OR category LIKE %s)"
        args += [like] * 4
    if not show_inactive:
        sql += " AND is_active = 1"
    sql += " ORDER BY name LIMIT 500"
    return render_template("products.html", products=query(sql, args), q=q, show_inactive=show_inactive)


@app.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    form = {"reorder_level": "5", "stock": "0"}
    if request.method == "POST":
        form = request.form.to_dict()
        data, errors = parse_product_form(request.form, creating=True)
        if not errors:
            db = get_db()
            try:
                with db.cursor() as cur:
                    cur.execute(
                        "INSERT INTO products (sku, barcode, name, category, price, cost, stock, reorder_level) "
                        "VALUES (%(sku)s, %(barcode)s, %(name)s, %(category)s, %(price)s, %(cost)s, %(stock)s, %(reorder_level)s)",
                        data)
                    if data["stock"] > 0:
                        cur.execute(
                            "INSERT INTO stock_movements (product_id, change_qty, reason, note, admin_id) "
                            "VALUES (%s, %s, 'opening', 'Opening stock', %s)",
                            (cur.lastrowid, data["stock"], session["admin_id"]))
                db.commit()
                flash(f"Added {data['name']}.", "ok")
                return redirect(url_for("products"))
            except pymysql.err.IntegrityError as exc:
                db.rollback()
                if not is_duplicate(exc):
                    raise
                errors.append("That SKU or barcode is already used by another product.")
        for e in errors:
            flash(e, "error")
    return render_template("product_form.html", form=form, product=None)


@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def product_edit(pid):
    product = query("SELECT * FROM products WHERE id = %s", (pid,), one=True)
    if not product:
        abort(404, "Product not found.")
    form = {k: ("" if v is None else str(v)) for k, v in product.items()}
    if request.method == "POST":
        form = request.form.to_dict()
        data, errors = parse_product_form(request.form, creating=False)
        if not errors:
            data["id"] = pid
            try:
                execute(
                    "UPDATE products SET sku=%(sku)s, barcode=%(barcode)s, name=%(name)s, category=%(category)s, "
                    "price=%(price)s, cost=%(cost)s, reorder_level=%(reorder_level)s WHERE id=%(id)s", data)
                flash(f"Saved {data['name']}.", "ok")
                return redirect(url_for("products"))
            except pymysql.err.IntegrityError as exc:
                get_db().rollback()
                if not is_duplicate(exc):
                    raise
                errors.append("That SKU or barcode is already used by another product.")
        for e in errors:
            flash(e, "error")
    return render_template("product_form.html", form=form, product=product)


@app.post("/products/<int:pid>/toggle")
@login_required
def product_toggle(pid):
    product = query("SELECT id, name, is_active FROM products WHERE id = %s", (pid,), one=True)
    if not product:
        abort(404, "Product not found.")
    execute("UPDATE products SET is_active = 1 - is_active WHERE id = %s", (pid,))
    flash(f"{product['name']} is now {'inactive' if product['is_active'] else 'active'}.", "ok")
    return redirect(request.form.get("back") if (request.form.get("back") or "").startswith("/products") else url_for("products"))


# --------------------------------------------------------------------------
# Inventory management
# --------------------------------------------------------------------------
@app.route("/inventory")
@login_required
def inventory():
    q = request.args.get("q", "").strip()
    low_only = request.args.get("low") == "1"
    sql = ("SELECT id, sku, name, category, stock, reorder_level, cost, price "
           "FROM products WHERE is_active = 1")
    args = []
    if q:
        like = f"%{escape_like(q)}%"
        sql += " AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s OR category LIKE %s)"
        args += [like] * 4
    if low_only:
        sql += " AND stock <= reorder_level"
    sql += " ORDER BY (stock <= reorder_level) DESC, name LIMIT 500"
    summary = query(
        "SELECT COUNT(*) AS products, COALESCE(SUM(stock), 0) AS units, "
        "COALESCE(SUM(stock * cost), 0) AS cost_value, COALESCE(SUM(stock * price), 0) AS retail_value, "
        "COALESCE(SUM(stock <= reorder_level), 0) AS low FROM products WHERE is_active = 1", one=True)
    return render_template("inventory.html", items=query(sql, args), summary=summary, q=q, low_only=low_only)


@app.post("/inventory/<int:pid>/adjust")
@login_required
def inventory_adjust(pid):
    action = request.form.get("action", "")
    qty = to_int(request.form.get("quantity"))
    note = request.form.get("note", "").strip()[:255] or None
    back = url_for("inventory", _anchor=f"p{pid}")

    if action not in ("restock", "damage", "count") or qty is None or not (0 <= qty <= 1_000_000) \
            or (action != "count" and qty < 1):
        flash("Enter a valid quantity.", "error")
        return redirect(back)

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id, name, stock FROM products WHERE id = %s FOR UPDATE", (pid,))
        product = cur.fetchone()
        if not product:
            abort(404, "Product not found.")
        if action == "restock":
            delta = qty
        elif action == "damage":
            delta = -qty
        else:
            delta = qty - product["stock"]
        new_stock = product["stock"] + delta
        if new_stock < 0:
            db.rollback()
            flash(f"Cannot remove {qty}: only {product['stock']} in stock.", "error")
            return redirect(back)
        if delta == 0:
            db.rollback()
            flash("Stock already matches that count. No change made.", "ok")
            return redirect(back)
        cur.execute("UPDATE products SET stock = %s WHERE id = %s", (new_stock, pid))
        cur.execute(
            "INSERT INTO stock_movements (product_id, change_qty, reason, note, admin_id) "
            "VALUES (%s, %s, %s, %s, %s)", (pid, delta, action, note, session["admin_id"]))
    db.commit()
    flash(f"{product['name']}: stock {product['stock']} → {new_stock}.", "ok")
    return redirect(back)


@app.route("/inventory/movements")
@login_required
def stock_movements():
    pid = request.args.get("product_id", type=int)
    sql = ("SELECT m.id, m.change_qty, m.reason, m.note, m.sale_id, m.created_at, "
           "p.id AS product_id, p.name, p.sku, a.username "
           "FROM stock_movements m JOIN products p ON p.id = m.product_id "
           "LEFT JOIN admins a ON a.id = m.admin_id")
    args = []
    if pid:
        sql += " WHERE m.product_id = %s"
        args.append(pid)
    sql += " ORDER BY m.id DESC LIMIT 200"
    return render_template("movements.html", movements=query(sql, args), pid=pid)


# --------------------------------------------------------------------------
# Checkout (POS)
# --------------------------------------------------------------------------
@app.route("/pos")
@login_required
def pos():
    return render_template("pos.html")


@app.get("/api/products/search")
@login_required
def api_product_search():
    q = request.args.get("q", "").strip()[:100]
    sql = "SELECT id, sku, barcode, name, price, stock FROM products WHERE is_active = 1"
    args = []
    order = "ORDER BY name"
    if q:
        like = f"%{escape_like(q)}%"
        sql += " AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s)"
        args += [like] * 3
        order = "ORDER BY (barcode = %s OR sku = %s) DESC, name"
        args += [q, q]
    rows = query(f"{sql} {order} LIMIT 30", args)
    return jsonify([{**r, "price": str(r["price"])} for r in rows])


class CheckoutError(Exception):
    pass


@app.post("/api/checkout")
@login_required
def api_checkout():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request."), 400
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return jsonify(error="The cart is empty."), 400

    wanted = {}
    for item in items:
        try:
            pid, qty = int(item["product_id"]), int(item["qty"])
        except (KeyError, TypeError, ValueError):
            return jsonify(error="Invalid cart item."), 400
        if qty < 1 or qty > 100000:
            return jsonify(error="Invalid quantity."), 400
        wanted[pid] = wanted.get(pid, 0) + qty

    method = data.get("payment_method")
    if method not in PAYMENT_METHODS:
        return jsonify(error="Choose a payment method."), 400

    raw_discount = data.get("discount")
    discount = Decimal("0.00") if raw_discount in (None, "") else money(raw_discount)
    if discount is None or discount < 0:
        return jsonify(error="Invalid discount."), 400

    db = get_db()
    try:
        with db.cursor() as cur:
            ids = sorted(wanted)
            marks = ",".join(["%s"] * len(ids))
            # Lock the rows so two checkouts cannot sell the same last unit.
            cur.execute(
                f"SELECT id, sku, name, price, cost, stock, is_active FROM products "
                f"WHERE id IN ({marks}) ORDER BY id FOR UPDATE", ids)
            found = {row["id"]: row for row in cur.fetchall()}

            subtotal = Decimal("0.00")
            lines = []
            for pid in ids:
                product, qty = found.get(pid), wanted[pid]
                if product is None or not product["is_active"]:
                    raise CheckoutError("A product in the cart is no longer available.")
                if product["stock"] < qty:
                    raise CheckoutError(f"Only {product['stock']} of {product['name']} left in stock.")
                line_total = (product["price"] * qty).quantize(CENT)
                subtotal += line_total
                lines.append((product, qty, line_total))
            if subtotal > MAX_SALE:
                raise CheckoutError("This sale is too large to process.")
            if discount > subtotal:
                raise CheckoutError("The discount cannot be more than the subtotal.")

            taxable = subtotal - discount
            tax = (taxable * TAX_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
            total = taxable + tax
            if method == "cash":
                paid = money(data.get("amount_paid"))
                if paid is None or paid < total:
                    raise CheckoutError("The cash received is less than the total.")
                if paid > MAX_SALE:
                    raise CheckoutError("Invalid cash amount.")
            else:
                paid = total
            change = paid - total

            cur.execute(
                "INSERT INTO sales (admin_id, subtotal, discount, tax, total, payment_method, amount_paid, change_due) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (session["admin_id"], subtotal, discount, tax, total, method, paid, change))
            sale_id = cur.lastrowid
            for product, qty, line_total in lines:
                cur.execute(
                    "INSERT INTO sale_items (sale_id, product_id, sku, product_name, qty, unit_price, unit_cost, line_total) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (sale_id, product["id"], product["sku"], product["name"], qty,
                     product["price"], product["cost"], line_total))
                cur.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (qty, product["id"]))
                cur.execute(
                    "INSERT INTO stock_movements (product_id, change_qty, reason, sale_id, admin_id) "
                    "VALUES (%s, %s, 'sale', %s, %s)", (product["id"], -qty, sale_id, session["admin_id"]))
        db.commit()
    except CheckoutError as exc:
        db.rollback()
        return jsonify(error=str(exc)), 409
    except Exception:
        db.rollback()
        app.logger.exception("Checkout failed")
        return jsonify(error="Checkout failed and nothing was saved. Please try again."), 500

    return jsonify(sale_id=sale_id, receipt_no=receipt_no_filter(sale_id), total=str(total),
                   change=str(change), receipt_url=url_for("sale_detail", sale_id=sale_id))


# --------------------------------------------------------------------------
# Sales history and receipts
# --------------------------------------------------------------------------
@app.route("/sales")
@login_required
def sales():
    start, end = parse_range(30)
    page = max(request.args.get("page", 1, type=int), 1)
    count = query(f"SELECT COUNT(*) AS n FROM sales s WHERE {RANGE_SQL}", (start, end), one=True)["n"]
    rows = query(
        f"SELECT s.id, s.subtotal, s.discount, s.tax, s.total, s.payment_method, s.status, s.created_at, a.username "
        f"FROM sales s LEFT JOIN admins a ON a.id = s.admin_id WHERE {RANGE_SQL} "
        f"ORDER BY s.id DESC LIMIT %s OFFSET %s", (start, end, PAGE_SIZE, (page - 1) * PAGE_SIZE))
    pages = max((count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    return render_template("sales.html", sales=rows, start=start, end=end, page=page, pages=pages, count=count)


@app.route("/sales/<int:sale_id>")
@login_required
def sale_detail(sale_id):
    sale = query("SELECT s.*, a.username FROM sales s LEFT JOIN admins a ON a.id = s.admin_id "
                 "WHERE s.id = %s", (sale_id,), one=True)
    if not sale:
        abort(404, "Sale not found.")
    lines = query("SELECT * FROM sale_items WHERE sale_id = %s ORDER BY id", (sale_id,))
    return render_template("sale_detail.html", sale=sale, lines=lines)


@app.post("/sales/<int:sale_id>/void")
@login_required
def sale_void(sale_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id, status FROM sales WHERE id = %s FOR UPDATE", (sale_id,))
        sale = cur.fetchone()
        if not sale:
            abort(404, "Sale not found.")
        if sale["status"] == "voided":
            db.rollback()
            flash("This sale is already voided.", "error")
            return redirect(url_for("sale_detail", sale_id=sale_id))
        cur.execute("SELECT product_id, qty FROM sale_items WHERE sale_id = %s ORDER BY product_id", (sale_id,))
        for line in cur.fetchall():
            cur.execute("UPDATE products SET stock = stock + %s WHERE id = %s", (line["qty"], line["product_id"]))
            cur.execute(
                "INSERT INTO stock_movements (product_id, change_qty, reason, note, sale_id, admin_id) "
                "VALUES (%s, %s, 'void', %s, %s, %s)",
                (line["product_id"], line["qty"], f"Voided sale {receipt_no_filter(sale_id)}", sale_id, session["admin_id"]))
        cur.execute("UPDATE sales SET status = 'voided', voided_at = NOW() WHERE id = %s", (sale_id,))
    db.commit()
    flash(f"Sale {receipt_no_filter(sale_id)} voided and stock returned to inventory.", "ok")
    return redirect(url_for("sale_detail", sale_id=sale_id))


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------
@app.route("/reports")
@login_required
def reports():
    start, end = parse_range(30)
    args = (start, end)
    done = f"s.status = 'completed' AND {RANGE_SQL}"

    summary = query(
        f"SELECT COUNT(*) AS transactions, COALESCE(SUM(s.total), 0) AS revenue, "
        f"COALESCE(SUM(s.tax), 0) AS tax, COALESCE(SUM(s.discount), 0) AS discounts "
        f"FROM sales s WHERE {done}", args, one=True)
    lines = query(
        f"SELECT COALESCE(SUM(si.qty), 0) AS items, COALESCE(SUM(si.line_total - si.unit_cost * si.qty), 0) AS margin "
        f"FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE {done}", args, one=True)
    voided = query(
        f"SELECT COUNT(*) AS n, COALESCE(SUM(s.total), 0) AS amount FROM sales s "
        f"WHERE s.status = 'voided' AND {RANGE_SQL}", args, one=True)
    daily = query(
        f"SELECT DATE(s.created_at) AS day, COUNT(*) AS transactions, SUM(s.total) AS revenue "
        f"FROM sales s WHERE {done} GROUP BY DATE(s.created_at) ORDER BY day", args)
    top = query(
        f"SELECT si.sku, si.product_name, SUM(si.qty) AS qty, SUM(si.line_total) AS revenue "
        f"FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE {done} "
        f"GROUP BY si.product_id, si.sku, si.product_name ORDER BY qty DESC, revenue DESC LIMIT 10", args)
    methods = query(
        f"SELECT s.payment_method, COUNT(*) AS transactions, SUM(s.total) AS revenue "
        f"FROM sales s WHERE {done} GROUP BY s.payment_method ORDER BY revenue DESC", args)

    peak = max((d["revenue"] for d in daily), default=Decimal("0"))
    for d in daily:
        d["pct"] = float(d["revenue"] / peak * 100) if peak else 0

    today = db_today()
    presets = [
        ("Today", today, today),
        ("Last 7 days", today - timedelta(days=6), today),
        ("Last 30 days", today - timedelta(days=29), today),
        ("This month", today.replace(day=1), today),
    ]
    avg_sale = summary["revenue"] / summary["transactions"] if summary["transactions"] else Decimal("0")
    return render_template(
        "reports.html", start=start, end=end, summary=summary, items=lines["items"],
        gross_profit=lines["margin"] - summary["discounts"], voided=voided, daily=daily,
        top=top, methods=methods, presets=presets, avg_sale=avg_sale)


@app.route("/reports/export.csv")
@login_required
def reports_export():
    start, end = parse_range(30)
    rows = query(
        f"SELECT s.id, s.created_at, s.status, s.payment_method, s.subtotal, s.discount, s.tax, s.total, a.username "
        f"FROM sales s LEFT JOIN admins a ON a.id = s.admin_id WHERE {RANGE_SQL} ORDER BY s.id", (start, end))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["receipt", "date_time", "status", "payment_method", "subtotal", "discount", "tax", "total", "cashier"])
    for r in rows:
        writer.writerow([receipt_no_filter(r["id"]), r["created_at"].strftime("%Y-%m-%d %H:%M:%S"), r["status"],
                         r["payment_method"], r["subtotal"], r["discount"], r["tax"], r["total"], r["username"] or ""])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=sales_{start}_{end}.csv"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("FLASK_DEBUG") == "1")
