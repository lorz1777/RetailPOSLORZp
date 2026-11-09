-- phpMyAdmin SQL Dump
-- version 5.2.3
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Nov 08, 2026 at 03:58 PM
-- Server version: 10.11.16-MariaDB
-- PHP Version: 8.3.36

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `retail_pos`
--

-- --------------------------------------------------------

--
-- Table structure for table `admins`
--

CREATE TABLE `admins` (
  `id` int(10) UNSIGNED NOT NULL,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `admins`
--

INSERT INTO `admins` (`id`, `username`, `password_hash`, `created_at`) VALUES
(1, 'pete123', 'scrypt:32768:8:1$KcPJJAbefXE5qYKZ$f109de7638f3e0053408e51cff6b8bf8337327832ad7a9933d4628551a3e2945854719a2a8380eb248e13b3f08ce2f4227b56a0cc4f6b3c5793e69dc4d2653b8', '2026-11-08 12:18:19');

-- --------------------------------------------------------

--
-- Table structure for table `products`
--

CREATE TABLE `products` (
  `id` int(10) UNSIGNED NOT NULL,
  `sku` varchar(40) NOT NULL,
  `barcode` varchar(64) DEFAULT NULL,
  `name` varchar(150) NOT NULL,
  `category` varchar(80) DEFAULT NULL,
  `price` decimal(10,2) NOT NULL,
  `cost` decimal(10,2) NOT NULL DEFAULT 0.00,
  `stock` int(11) NOT NULL DEFAULT 0,
  `reorder_level` int(11) NOT NULL DEFAULT 5,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ;

--
-- Dumping data for table `products`
--

INSERT INTO `products` (`id`, `sku`, `barcode`, `name`, `category`, `price`, `cost`, `stock`, `reorder_level`, `is_active`, `created_at`, `updated_at`) VALUES
(1, 'BEV-001', '4800000000011', 'Bottled Water 500ml', 'Beverages', 1.00, 0.40, 120, 24, 1, '2026-11-08 12:18:19', '2026-11-08 12:37:20'),
(2, 'BEV-002', '4800000000028', 'Orange Juice 1L', 'Beverages', 3.50, 2.10, 36, 10, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(3, 'BEV-003', '4800000000035', 'Ground Coffee 250g', 'Beverages', 7.90, 4.80, 18, 6, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(4, 'SNK-001', '4800000000042', 'Potato Chips 150g', 'Snacks', 2.25, 1.20, 60, 15, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(5, 'SNK-002', '4800000000059', 'Chocolate Bar', 'Snacks', 1.75, 0.90, 80, 20, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(6, 'GRO-001', '4800000000066', 'White Rice 5kg', 'Grocery', 9.80, 7.20, 25, 8, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(7, 'GRO-002', '4800000000073', 'Cooking Oil 1L', 'Grocery', 4.60, 3.30, 30, 10, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(8, 'GRO-003', '4800000000080', 'Pasta 500g', 'Grocery', 2.10, 1.30, 4, 10, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(9, 'HOM-001', '4800000000097', 'Dish Soap 500ml', 'Household', 3.20, 1.90, 22, 8, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(10, 'HOM-002', '4800000000103', 'Paper Towels 2-pack', 'Household', 4.40, 2.70, 15, 6, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(11, 'PER-001', '4800000000110', 'Shampoo 350ml', 'Personal Care', 5.90, 3.60, 12, 5, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(12, 'PER-002', '4800000000127', 'Toothpaste 100g', 'Personal Care', 2.80, 1.50, 0, 8, 1, '2026-11-08 12:18:19', '2026-11-08 12:18:19'),
(13, 'shabu', NULL, 'bana ni leni', 'medicine', 500.00, 650.00, 1000, 50, 0, '2026-11-08 12:32:59', '2026-11-08 12:45:10');

-- --------------------------------------------------------

--
-- Table structure for table `sales`
--

CREATE TABLE `sales` (
  `id` int(10) UNSIGNED NOT NULL,
  `admin_id` int(10) UNSIGNED DEFAULT NULL,
  `subtotal` decimal(12,2) NOT NULL,
  `discount` decimal(12,2) NOT NULL DEFAULT 0.00,
  `tax` decimal(12,2) NOT NULL DEFAULT 0.00,
  `total` decimal(12,2) NOT NULL,
  `payment_method` enum('cash','card','ewallet') NOT NULL,
  `amount_paid` decimal(12,2) NOT NULL,
  `change_due` decimal(12,2) NOT NULL DEFAULT 0.00,
  `status` enum('completed','voided') NOT NULL DEFAULT 'completed',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `voided_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `sale_items`
--

CREATE TABLE `sale_items` (
  `id` int(10) UNSIGNED NOT NULL,
  `sale_id` int(10) UNSIGNED NOT NULL,
  `product_id` int(10) UNSIGNED NOT NULL,
  `sku` varchar(40) NOT NULL,
  `product_name` varchar(150) NOT NULL,
  `qty` int(11) NOT NULL,
  `unit_price` decimal(10,2) NOT NULL,
  `unit_cost` decimal(10,2) NOT NULL DEFAULT 0.00,
  `line_total` decimal(12,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `stock_movements`
--

CREATE TABLE `stock_movements` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `product_id` int(10) UNSIGNED NOT NULL,
  `change_qty` int(11) NOT NULL,
  `reason` enum('opening','restock','damage','count','sale','void') NOT NULL,
  `note` varchar(255) DEFAULT NULL,
  `sale_id` int(10) UNSIGNED DEFAULT NULL,
  `admin_id` int(10) UNSIGNED DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `stock_movements`
--

INSERT INTO `stock_movements` (`id`, `product_id`, `change_qty`, `reason`, `note`, `sale_id`, `admin_id`, `created_at`) VALUES
(1, 1, 120, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(2, 2, 36, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(3, 3, 18, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(4, 4, 60, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(5, 5, 80, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(6, 6, 25, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(7, 7, 30, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(8, 8, 4, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(9, 9, 22, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(10, 10, 15, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(11, 11, 12, 'opening', 'Demo opening stock', NULL, NULL, '2026-11-08 12:18:19'),
(12, 13, 1000, 'opening', 'Opening stock', NULL, 1, '2026-11-08 12:32:59');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `admins`
--
ALTER TABLE `admins`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `products`
--
ALTER TABLE `products`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `sku` (`sku`),
  ADD UNIQUE KEY `barcode` (`barcode`),
  ADD KEY `idx_products_name` (`name`),
  ADD KEY `idx_products_active` (`is_active`);

--
-- Indexes for table `sales`
--
ALTER TABLE `sales`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_sales_created` (`created_at`),
  ADD KEY `idx_sales_status_created` (`status`,`created_at`),
  ADD KEY `fk_sales_admin` (`admin_id`);

--
-- Indexes for table `sale_items`
--
ALTER TABLE `sale_items`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_items_sale` (`sale_id`),
  ADD KEY `idx_items_product` (`product_id`);

--
-- Indexes for table `stock_movements`
--
ALTER TABLE `stock_movements`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_movements_product` (`product_id`,`id`),
  ADD KEY `fk_movements_sale` (`sale_id`),
  ADD KEY `fk_movements_admin` (`admin_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `admins`
--
ALTER TABLE `admins`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `products`
--
ALTER TABLE `products`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `sales`
--
ALTER TABLE `sales`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `sale_items`
--
ALTER TABLE `sale_items`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `stock_movements`
--
ALTER TABLE `stock_movements`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=13;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `sales`
--
ALTER TABLE `sales`
  ADD CONSTRAINT `fk_sales_admin` FOREIGN KEY (`admin_id`) REFERENCES `admins` (`id`) ON DELETE SET NULL;

--
-- Constraints for table `sale_items`
--
ALTER TABLE `sale_items`
  ADD CONSTRAINT `fk_items_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
  ADD CONSTRAINT `fk_items_sale` FOREIGN KEY (`sale_id`) REFERENCES `sales` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `stock_movements`
--
ALTER TABLE `stock_movements`
  ADD CONSTRAINT `fk_movements_admin` FOREIGN KEY (`admin_id`) REFERENCES `admins` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `fk_movements_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`),
  ADD CONSTRAINT `fk_movements_sale` FOREIGN KEY (`sale_id`) REFERENCES `sales` (`id`) ON DELETE SET NULL;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
