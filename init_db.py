#!/usr/bin/env python3
"""Create the MySQL database, tables and the first admin account.

    python init_db.py              create schema + first admin (if none exists)
    python init_db.py --demo       also load a few sample products
    python init_db.py --add-admin  create an additional admin account
"""
import argparse
import getpass
import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()
HERE = Path(__file__).resolve().parent

DEMO_PRODUCTS = [
    # sku, barcode, name, category, price, cost, stock, reorder_level
    ("BEV-001", "4800000000011", "Bottled Water 500ml", "Beverages", "1.00", "0.40", 120, 24),
    ("BEV-002", "4800000000028", "Orange Juice 1L", "Beverages", "3.50", "2.10", 36, 10),
    ("BEV-003", "4800000000035", "Ground Coffee 250g", "Beverages", "7.90", "4.80", 18, 6),
    ("SNK-001", "4800000000042", "Potato Chips 150g", "Snacks", "2.25", "1.20", 60, 15),
    ("SNK-002", "4800000000059", "Chocolate Bar", "Snacks", "1.75", "0.90", 80, 20),
    ("GRO-001", "4800000000066", "White Rice 5kg", "Grocery", "9.80", "7.20", 25, 8),
    ("GRO-002", "4800000000073", "Cooking Oil 1L", "Grocery", "4.60", "3.30", 30, 10),
    ("GRO-003", "4800000000080", "Pasta 500g", "Grocery", "2.10", "1.30", 4, 10),
    ("HOM-001", "4800000000097", "Dish Soap 500ml", "Household", "3.20", "1.90", 22, 8),
    ("HOM-002", "4800000000103", "Paper Towels 2-pack", "Household", "4.40", "2.70", 15, 6),
    ("PER-001", "4800000000110", "Shampoo 350ml", "Personal Care", "5.90", "3.60", 12, 5),
    ("PER-002", "4800000000127", "Toothpaste 100g", "Personal Care", "2.80", "1.50", 0, 8),
]


def connect(database=None):
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=database,
        charset="utf8mb4",
        autocommit=True,
    )


def sql_statements(path):
    """Split schema.sql into statements (comment lines removed)."""
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def create_admin(cur, username=None, password=None):
    username = (username or input("Admin username: ")).strip()
    if not username or len(username) > 50:
        sys.exit("Username is required (max 50 characters).")
    cur.execute("SELECT id FROM admins WHERE username = %s", (username,))
    if cur.fetchone():
        sys.exit(f"An admin named '{username}' already exists.")
    if password is None:
        password = getpass.getpass("Password (min 8 characters): ")
        if password != getpass.getpass("Repeat password: "):
            sys.exit("Passwords do not match.")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    cur.execute(
        "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
        (username, generate_password_hash(password)),
    )
    print(f"Admin '{username}' created.")


def load_demo(cur):
    added = 0
    for sku, barcode, name, category, price, cost, stock, reorder in DEMO_PRODUCTS:
        cur.execute(
            "INSERT IGNORE INTO products (sku, barcode, name, category, price, cost, stock, reorder_level) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (sku, barcode, name, category, price, cost, stock, reorder),
        )
        if cur.rowcount == 1:
            added += 1
            if stock > 0:
                cur.execute(
                    "INSERT INTO stock_movements (product_id, change_qty, reason, note) "
                    "VALUES (%s, %s, 'opening', 'Demo opening stock')",
                    (cur.lastrowid, stock),
                )
    print(f"Demo products added: {added}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="load sample products")
    parser.add_argument("--add-admin", action="store_true", help="create an additional admin account")
    args = parser.parse_args()

    db_name = os.environ.get("DB_NAME", "retail_pos")
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        sys.exit("DB_NAME may only contain letters, digits and underscores.")

    try:
        conn = connect()
    except pymysql.MySQLError as exc:
        sys.exit(f"Could not connect to MySQL: {exc}")

    with conn:
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.execute(f"USE `{db_name}`")
        for stmt in sql_statements(HERE / "schema.sql"):
            cur.execute(stmt)
        print(f"Database '{db_name}' is ready.")

        cur.execute("SELECT COUNT(*) FROM admins")
        has_admin = cur.fetchone()[0] > 0
        if args.add_admin or not has_admin:
            create_admin(cur, os.environ.get("ADMIN_USERNAME") if not has_admin else None,
                         os.environ.get("ADMIN_PASSWORD") if not has_admin else None)
        else:
            print("An admin account already exists (use --add-admin to create another).")

        if args.demo:
            load_demo(cur)

    print("Done. Start the app with:  python app.py")


if __name__ == "__main__":
    main()
