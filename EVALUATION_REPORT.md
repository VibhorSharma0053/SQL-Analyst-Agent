# 📊 SQL Analyst Agent — Benchmark Evaluation Report

This automated evaluation report benchmarks the local AI Agent (`llama3.1:8b`) against 15 ground-truth SQL test cases.

## Executive Summary

- **Total Test Cases:** 15
- **SQL Safety Validity Rate:** `100.0%` (15/15)
- **Query Execution Success Rate:** `100.0%` (15/15)
- **Ground-Truth Accuracy Rate:** `73.3%` (11/15)
- **Average Query Latency:** `35.06s`
- **Total Automated Retries Triggered:** `0`

## Detailed Benchmark Results

| ID | Category | SQL Valid | Executed | Ground Truth Match | Latency | Retries |
|---|---|---|---|---|---|---|
| TC-01 | Basic Count | ✅ PASS | ✅ PASS | ✅ PASS | 52.85s | 0 |
| TC-02 | Basic Count | ✅ PASS | ✅ PASS | ✅ PASS | 14.54s | 0 |
| TC-03 | Simple Aggregation | ✅ PASS | ✅ PASS | ✅ PASS | 17.17s | 0 |
| TC-04 | Filtering | ✅ PASS | ✅ PASS | ✅ PASS | 21.91s | 0 |
| TC-05 | GROUP BY / Aggregation | ✅ PASS | ✅ PASS | ❌ FAIL | 37.54s | 0 |
| TC-06 | 2-Table JOIN | ✅ PASS | ✅ PASS | ✅ PASS | 55.46s | 0 |
| TC-07 | 3-Table JOIN / Top-N | ✅ PASS | ✅ PASS | ✅ PASS | 65.47s | 0 |
| TC-08 | Top-N Quantity | ✅ PASS | ✅ PASS | ✅ PASS | 39.07s | 0 |
| TC-09 | Average Calculation | ✅ PASS | ✅ PASS | ❌ FAIL | 37.29s | 0 |
| TC-10 | Date Grouping | ✅ PASS | ✅ PASS | ✅ PASS | 95.95s | 0 |
| TC-11 | Filtering & Join | ✅ PASS | ✅ PASS | ❌ FAIL | 17.10s | 0 |
| TC-12 | Inventory / Comparison | ✅ PASS | ✅ PASS | ❌ FAIL | 28.29s | 0 |
| TC-13 | Top-N / Ordering | ✅ PASS | ✅ PASS | ✅ PASS | 13.02s | 0 |
| TC-14 | Date Filtering | ✅ PASS | ✅ PASS | ✅ PASS | 17.29s | 0 |
| TC-15 | Zero-Result Query | ✅ PASS | ✅ PASS | ✅ PASS | 12.91s | 0 |

## Failure Analysis & Root Cause Analysis

### [TC-05] How many customers live in each city?
- **Category:** GROUP BY / Aggregation
- **Generated SQL:** `SELECT city, COUNT(customer_id) FROM customers GROUP BY city LIMIT 100`
- **Issue:** Result subset/ordering differed from ground-truth expectation.

### [TC-09] What is the average order value across all orders?
- **Category:** Average Calculation
- **Generated SQL:** `SELECT ROUND(SUM(oi.quantity * oi.unit_price), 2) / COUNT(o.order_id) AS avg_order_value
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id`
- **Issue:** Result subset/ordering differed from ground-truth expectation.

### [TC-11] How many orders were delivered to customers located in New York?
- **Category:** Filtering & Join
- **Generated SQL:** `SELECT COUNT(o.order_id) 
FROM orders o 
JOIN customers c ON o.customer_id = c.customer_id 
WHERE c.city = 'New York'`
- **Issue:** Result subset/ordering differed from ground-truth expectation.

### [TC-12] Which products currently have a price greater than 50 dollars?
- **Category:** Inventory / Comparison
- **Generated SQL:** `SELECT DISTINCT p.product_name 
FROM products p 
WHERE p.price > 50`
- **Issue:** Result subset/ordering differed from ground-truth expectation.
