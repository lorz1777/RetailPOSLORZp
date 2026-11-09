# Retail POS (Flask + MySQL)

A web-based point-of-sale system for a retail store. One role: **admin**. Everything sits behind a login.

## Features

| Area | What it does |
|------|--------------|
| **Admin login** | Username/password, hashed passwords, CSRF protection, login throttling, 8-hour sessions, change-password page |
| **Product management** | Add / edit products (SKU, barcode, category, price, cost, reorder level). Products are deactivated, not deleted, so old receipts stay intact |
| **Inventory management** | Stock on hand, low / out-of-stock flags, stock value. Add stock, record damaged/lost items, or set a counted quantity. Every change is written to a stock history log |
| **Sales checkout** | Search or scan a barcode, build a cart, apply a discount, tax, pay by cash / card / e-wallet, change calculation, printable receipt |
| **Sales reports** | Date range or presets: revenue, gross profit, transactions, items sold, average sale, tax, discounts, daily sales, top products, payment methods. CSV download |
| **Void sale** | Cancels a sale and returns the items to stock (logged) |

## Setup

You need Python 3.9+ and MySQL 5.7+ / 8.x (MariaDB 10.3+ also works).

```bash
cd pos_system
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**1. Create a MySQL user** (skip if you will use root for setup):

```sql
CREATE USER 'pos_user'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL PRIVILEGES ON retail_pos.* TO 'pos_user'@'localhost';
```

**2. Configure.** Copy `.env.example` to `.env` and fill in `SECRET_KEY`, the `DB_*` values, `STORE_NAME`, `CURRENCY_SYMBOL` and `TAX_RATE` (for example `0.12` for 12%, or `0` for no tax).

**3. Create the tables and your admin account:**

```bash
python init_db.py            # asks for the admin username and password
python init_db.py --demo     # optional: also loads 12 sample products
```

**4. Run it:**

```bash
python app.py
```

Open http://127.0.0.1:5000 and sign in.

## Using it

1. **Products** → add your items (opening stock is entered here once).
2. **Inventory** → later stock changes: deliveries (*Add stock*), breakage (*Remove*), stocktake (*Set counted quantity*).
3. **Checkout** → type a name/SKU or scan a barcode and press Enter. Scanners that "type" the code work as-is. Enter cash received (or press *Exact*) and click *Complete sale*.
4. **Sales** → every receipt; open one to print or void it.
5. **Reports** → pick a date range; *Download CSV* exports the sales list.

## Project layout

```
app.py             Flask routes and business logic
init_db.py         creates the database, tables, first admin, optional demo data
schema.sql         MySQL tables
requirements.txt
.env.example
templates/         Jinja pages
static/            style.css, pos.js (checkout screen)
```

## How it keeps the numbers right

- Money is stored as `DECIMAL(10,2)` and calculated with Python `Decimal`, never floats.
- Checkout runs in **one database transaction** and locks the product rows (`SELECT ... FOR UPDATE`), so two cashiers cannot sell the last unit twice. If anything fails, nothing is saved.
- The server recalculates every total, tax and change figure itself; the browser's numbers are for display only.
- Each sale line stores the SKU, name, price and cost at the time of sale, so editing a product later never changes old receipts or past profit.
- Prices are entered **without tax**; tax (`TAX_RATE`) is added at checkout.
- Dates and times come from the MySQL server's clock and time zone.

## Putting it into real use

- Set a strong `SECRET_KEY` and keep `.env` private (never commit it).
- `python app.py` is the development server. For a shop, run behind a production server and HTTPS, for example `pip install gunicorn` then `gunicorn -w 2 -b 127.0.0.1:8000 app:app`, with nginx or Caddy in front. Once on HTTPS, set `SESSION_COOKIE_SECURE=1`.
- Back up the MySQL database regularly (`mysqldump retail_pos > backup.sql`).
- Failed-login throttling is kept in memory per process, so it resets on restart.
- Receipts print through the browser's print dialog. Direct thermal-printer or cash-drawer control is not included.

## Testing status

The checkout logic, every page, CSRF/login handling and the browser checkout screen were exercised with the MySQL driver replaced by an in-memory stand-in, because no MySQL server was available where this was built. Your first run against a real MySQL server is therefore the first end-to-end test: run `python init_db.py --demo`, sign in, and make a test sale.
