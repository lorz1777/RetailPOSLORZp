-- Retail POS schema (MySQL 5.7+ / 8.x, MariaDB 10.3+)
-- init_db.py creates the database and runs this file.
-- To run it by hand: mysql -u USER -p retail_pos < schema.sql

CREATE TABLE IF NOT EXISTS admins (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(50)  NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS products (
  id            INT UNSIGNED  NOT NULL AUTO_INCREMENT PRIMARY KEY,
  sku           VARCHAR(40)   NOT NULL UNIQUE,
  barcode       VARCHAR(64)   NULL UNIQUE,
  name          VARCHAR(150)  NOT NULL,
  category      VARCHAR(80)   NULL,
  price         DECIMAL(10,2) NOT NULL,
  cost          DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  stock         INT           NOT NULL DEFAULT 0,
  reorder_level INT           NOT NULL DEFAULT 5,
  is_active     TINYINT(1)    NOT NULL DEFAULT 1,
  created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_products_name (name),
  KEY idx_products_active (is_active),
  CONSTRAINT chk_products_stock CHECK (stock >= 0),
  CONSTRAINT chk_products_money CHECK (price >= 0 AND cost >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sales (
  id             INT UNSIGNED  NOT NULL AUTO_INCREMENT PRIMARY KEY,
  admin_id       INT UNSIGNED  NULL,
  subtotal       DECIMAL(12,2) NOT NULL,
  discount       DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  tax            DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  total          DECIMAL(12,2) NOT NULL,
  payment_method ENUM('cash','card','ewallet') NOT NULL,
  amount_paid    DECIMAL(12,2) NOT NULL,
  change_due     DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  status         ENUM('completed','voided') NOT NULL DEFAULT 'completed',
  created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  voided_at      DATETIME      NULL,
  KEY idx_sales_created (created_at),
  KEY idx_sales_status_created (status, created_at),
  CONSTRAINT fk_sales_admin FOREIGN KEY (admin_id) REFERENCES admins (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Each line keeps a copy of the SKU, name, price and cost at the time of sale,
-- so reports stay correct even if the product is edited later.
CREATE TABLE IF NOT EXISTS sale_items (
  id           INT UNSIGNED  NOT NULL AUTO_INCREMENT PRIMARY KEY,
  sale_id      INT UNSIGNED  NOT NULL,
  product_id   INT UNSIGNED  NOT NULL,
  sku          VARCHAR(40)   NOT NULL,
  product_name VARCHAR(150)  NOT NULL,
  qty          INT           NOT NULL,
  unit_price   DECIMAL(10,2) NOT NULL,
  unit_cost    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  line_total   DECIMAL(12,2) NOT NULL,
  KEY idx_items_sale (sale_id),
  KEY idx_items_product (product_id),
  CONSTRAINT fk_items_sale    FOREIGN KEY (sale_id)    REFERENCES sales (id) ON DELETE CASCADE,
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Every change to stock is logged here (audit trail for the inventory screen).
CREATE TABLE IF NOT EXISTS stock_movements (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  product_id INT UNSIGNED    NOT NULL,
  change_qty INT             NOT NULL,
  reason     ENUM('opening','restock','damage','count','sale','void') NOT NULL,
  note       VARCHAR(255)    NULL,
  sale_id    INT UNSIGNED    NULL,
  admin_id   INT UNSIGNED    NULL,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_movements_product (product_id, id),
  CONSTRAINT fk_movements_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_movements_sale    FOREIGN KEY (sale_id)    REFERENCES sales (id) ON DELETE SET NULL,
  CONSTRAINT fk_movements_admin   FOREIGN KEY (admin_id)   REFERENCES admins (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
