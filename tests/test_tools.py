# file: tests/test_tools.py

"""
Integration tests for the database execution tool.

These tests need the SQLite database to exist.
Run the seed script first if tests fail with "no such table":
    python -m app.database.seed

Run: pytest tests/test_tools.py -v
"""

import pytest
from app.tools.database_tools import execute_readonly_query


class TestSafeExecution:
    """Test that safe queries execute correctly."""

    def test_count_customers(self):
        result = execute_readonly_query("SELECT COUNT(*) as count FROM customers")
        assert result["success"] is True
        assert result["row_count"] == 1
        assert result["rows"][0]["count"] == 20

    def test_count_products(self):
        result = execute_readonly_query("SELECT COUNT(*) as count FROM products")
        assert result["success"] is True
        assert result["rows"][0]["count"] == 15

    def test_select_with_limit(self):
        result = execute_readonly_query("SELECT * FROM customers LIMIT 5")
        assert result["success"] is True
        assert result["row_count"] == 5

    def test_select_with_join(self):
        result = execute_readonly_query(
            "SELECT c.name, o.order_id "
            "FROM customers c "
            "JOIN orders o ON c.customer_id = o.customer_id "
            "LIMIT 10"
        )
        assert result["success"] is True
        assert result["row_count"] <= 10
        assert "name" in result["columns"]
        assert "order_id" in result["columns"]

    def test_aggregation_query(self):
        result = execute_readonly_query(
            "SELECT ROUND(SUM(quantity * unit_price), 2) as total "
            "FROM order_items"
        )
        assert result["success"] is True
        assert result["rows"][0]["total"] > 0

    def test_columns_are_returned(self):
        result = execute_readonly_query(
            "SELECT name, email, city FROM customers LIMIT 1"
        )
        assert result["columns"] == ["name", "email", "city"]


class TestBlockedExecution:
    """Test that dangerous queries are blocked at the execution layer."""

    def test_drop_blocked(self):
        result = execute_readonly_query("DROP TABLE customers")
        assert result["success"] is False
        assert "error" in result
        assert result["row_count"] == 0

    def test_delete_blocked(self):
        result = execute_readonly_query("DELETE FROM orders")
        assert result["success"] is False

    def test_insert_blocked(self):
        result = execute_readonly_query(
            "INSERT INTO customers (name, email, city, signup_date) "
            "VALUES ('Hacker', 'h@h.com', 'Evil', '2024-01-01')"
        )
        assert result["success"] is False

    def test_update_blocked(self):
        result = execute_readonly_query(
            "UPDATE products SET price = 0.01"
        )
        assert result["success"] is False

    def test_stacked_statement_blocked(self):
        result = execute_readonly_query(
            "SELECT 1; DROP TABLE customers"
        )
        assert result["success"] is False


class TestErrorHandling:
    """Test that the tool handles errors gracefully."""

    def test_nonexistent_table(self):
        result = execute_readonly_query("SELECT * FROM nonexistent_table")
        assert result["success"] is False
        assert "no such table" in result["error"].lower()

    def test_nonexistent_column(self):
        result = execute_readonly_query(
            "SELECT fake_column FROM customers"
        )
        assert result["success"] is False
        assert "no such column" in result["error"].lower()

    def test_invalid_sql_syntax(self):
        result = execute_readonly_query("SELEC broken query")
        assert result["success"] is False


class TestRowLimit:
    """Test that the row limit is enforced."""

    def test_row_limit_enforced(self):
        """
        Query all order_items (118 rows) with a limit of 10.
        The result should be truncated to 10 rows.
        """
        result = execute_readonly_query(
            "SELECT * FROM order_items",
            max_rows=10,
        )
        assert result["success"] is True
        assert result["row_count"] == 10
        assert result["truncated"] is True

    def test_no_truncation_under_limit(self):
        """
        Query 20 customers with a limit of 100.
        Should not be truncated.
        """
        result = execute_readonly_query(
            "SELECT * FROM customers",
            max_rows=100,
        )
        assert result["success"] is True
        assert result["row_count"] == 20
        assert result["truncated"] is False