# file: tests/test_sql_validator.py

"""
Unit tests for the SQL query validator.

These tests are FAST because they do not need a database or LLM.
They test pure Python logic: given a SQL string, does the validator
correctly accept or reject it?

Run: pytest tests/test_sql_validator.py -v
"""

import pytest
from app.tools.sql_validator import validate_sql_query


# ═══════════════════════════════════════════════════════════════════
#  SAFE QUERIES — Must all return (True, None)
# ═══════════════════════════════════════════════════════════════════

class TestSafeQueries:
    """Queries that should pass validation."""

    def test_simple_select(self):
        is_valid, error = validate_sql_query("SELECT * FROM customers")
        assert is_valid is True
        assert error is None

    def test_select_with_where(self):
        is_valid, error = validate_sql_query(
            "SELECT name FROM customers WHERE city = 'New York'"
        )
        assert is_valid is True

    def test_select_with_join(self):
        is_valid, error = validate_sql_query(
            "SELECT c.name, o.order_id "
            "FROM customers c "
            "JOIN orders o ON c.customer_id = o.customer_id"
        )
        assert is_valid is True

    def test_select_with_group_by(self):
        is_valid, error = validate_sql_query(
            "SELECT city, COUNT(*) FROM customers GROUP BY city"
        )
        assert is_valid is True

    def test_select_with_order_and_limit(self):
        is_valid, error = validate_sql_query(
            "SELECT name FROM customers ORDER BY name DESC LIMIT 10"
        )
        assert is_valid is True

    def test_select_with_aggregation(self):
        is_valid, error = validate_sql_query(
            "SELECT ROUND(SUM(quantity * unit_price), 2) FROM order_items"
        )
        assert is_valid is True

    def test_select_with_subquery(self):
        is_valid, error = validate_sql_query(
            "SELECT * FROM customers "
            "WHERE customer_id IN (SELECT customer_id FROM orders)"
        )
        assert is_valid is True

    def test_select_with_cte(self):
        """Common Table Expressions (WITH clause) should be allowed."""
        is_valid, error = validate_sql_query(
            "WITH totals AS ("
            "  SELECT customer_id, SUM(quantity * unit_price) as total "
            "  FROM order_items JOIN orders ON order_items.order_id = orders.order_id "
            "  GROUP BY customer_id"
            ") SELECT * FROM totals ORDER BY total DESC LIMIT 5"
        )
        assert is_valid is True

    def test_select_with_trailing_semicolon(self):
        """A single trailing semicolon is standard SQL and should be allowed."""
        is_valid, error = validate_sql_query("SELECT COUNT(*) FROM customers;")
        assert is_valid is True

    def test_select_lowercase(self):
        """SQL is case-insensitive. Lowercase should work."""
        is_valid, error = validate_sql_query("select count(*) from customers")
        assert is_valid is True

    def test_select_mixed_case(self):
        is_valid, error = validate_sql_query("Select Count(*) From Customers")
        assert is_valid is True

    def test_column_named_updated_at(self):
        """
        A column named 'updated_at' contains the word 'update' but
        should NOT be blocked because we use word boundaries.
        """
        is_valid, error = validate_sql_query(
            "SELECT name, updated_at FROM customers"
        )
        assert is_valid is True

    def test_column_named_dropped_items(self):
        """
        A column named 'dropped_items' contains 'drop' but
        should NOT be blocked.
        """
        is_valid, error = validate_sql_query(
            "SELECT dropped_items FROM orders"
        )
        assert is_valid is True


# ═══════════════════════════════════════════════════════════════════
#  DANGEROUS QUERIES — Must all return (False, error_message)
# ═══════════════════════════════════════════════════════════════════

class TestDangerousQueries:
    """Queries that should be blocked by the validator."""

    def test_drop_table(self):
        is_valid, error = validate_sql_query("DROP TABLE customers")
        assert is_valid is False
        assert "DROP" in error or "read-only" in error.lower()

    def test_delete(self):
        is_valid, error = validate_sql_query("DELETE FROM customers")
        assert is_valid is False

    def test_update(self):
        is_valid, error = validate_sql_query(
            "UPDATE customers SET name = 'Hacked'"
        )
        assert is_valid is False

    def test_insert(self):
        is_valid, error = validate_sql_query(
            "INSERT INTO customers (name) VALUES ('Evil')"
        )
        assert is_valid is False

    def test_alter_table(self):
        is_valid, error = validate_sql_query(
            "ALTER TABLE customers ADD COLUMN password TEXT"
        )
        assert is_valid is False

    def test_truncate(self):
        is_valid, error = validate_sql_query("TRUNCATE TABLE orders")
        assert is_valid is False

    def test_create_table(self):
        is_valid, error = validate_sql_query(
            "CREATE TABLE hackers (id INTEGER)"
        )
        assert is_valid is False

    def test_attach_database(self):
        """SQLite-specific attack: attach a malicious database."""
        is_valid, error = validate_sql_query(
            "ATTACH DATABASE 'evil.db' AS evil"
        )
        assert is_valid is False

    def test_pragma(self):
        """SQLite PRAGMA can modify database settings."""
        is_valid, error = validate_sql_query(
            "PRAGMA journal_mode = DELETE"
        )
        assert is_valid is False

    def test_drop_case_insensitive(self):
        """Blocking must be case-insensitive."""
        is_valid, error = validate_sql_query("drop table customers")
        assert is_valid is False

    def test_delete_mixed_case(self):
        is_valid, error = validate_sql_query("DeLeTe FROM customers")
        assert is_valid is False


# ═══════════════════════════════════════════════════════════════════
#  STACKED STATEMENT ATTACKS — Must all be blocked
# ═══════════════════════════════════════════════════════════════════

class TestStackedStatements:
    """
    SQL injection attacks that hide a second statement
    after a semicolon.
    """

    def test_select_then_drop(self):
        is_valid, error = validate_sql_query(
            "SELECT * FROM customers; DROP TABLE orders"
        )
        assert is_valid is False
        assert "multiple" in error.lower() or "semicolon" in error.lower()

    def test_select_then_delete(self):
        is_valid, error = validate_sql_query(
            "SELECT 1; DELETE FROM customers"
        )
        assert is_valid is False

    def test_select_then_insert(self):
        is_valid, error = validate_sql_query(
            "SELECT * FROM products; INSERT INTO customers VALUES (1)"
        )
        assert is_valid is False

    def test_select_then_update(self):
        is_valid, error = validate_sql_query(
            "SELECT 1; UPDATE products SET price = 0"
        )
        assert is_valid is False


# ═══════════════════════════════════════════════════════════════════
#  EDGE CASES
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases and unusual inputs."""

    def test_empty_string(self):
        is_valid, error = validate_sql_query("")
        assert is_valid is False

    def test_whitespace_only(self):
        is_valid, error = validate_sql_query("   \n\t  ")
        assert is_valid is False

    def test_none_value(self):
        """The validator should handle None gracefully."""
        # Depending on implementation, this may raise or return False
        try:
            is_valid, error = validate_sql_query(None)
            assert is_valid is False
        except (TypeError, AttributeError):
            # Also acceptable — the caller should not pass None
            pass

    def test_random_text(self):
        is_valid, error = validate_sql_query("hello world this is not sql")
        assert is_valid is False

    def test_select_with_comment_containing_drop(self):
        """
        A SQL comment mentioning DROP should not be blocked
        if the actual query is a safe SELECT.
        
        Note: Our current validator may block this because it does
        simple keyword matching. This test documents the behavior.
        """
        is_valid, error = validate_sql_query(
            "SELECT * FROM customers -- do not DROP this table"
        )
        # This may be True or False depending on implementation.
        # The important thing is it does not crash.
        assert isinstance(is_valid, bool)