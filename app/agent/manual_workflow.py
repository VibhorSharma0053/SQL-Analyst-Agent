# file: app/agent/manual_workflow.py

"""
Manual SQL Analyst Workflow.

This module implements a deterministic (non-AI) version of the SQL analyst.
It processes natural language questions and returns answers by:

1. Inspecting the database schema
2. Mapping the question to a SQL query using simple rules
3. Validating the SQL for safety
4. Executing the query against the database
5. Formatting the result into a human-readable answer

This is the foundation for the AI-powered agent.
Once this works perfectly, we replace the manual SQL generation
with LLM-based generation in the next steps.
"""

from typing import Dict, Any, Optional
from app.database.schema_inspector import get_schema_for_prompt
from app.tools.sql_validator import validate_sql_query
from app.tools.database_tools import execute_readonly_query


class ManualSQLAnalyst:
    """
    A deterministic SQL analyst that answers questions using simple rules.

    Attributes:
        schema_text: The formatted schema string used for reference.
    """

    def __init__(self):
        """
        Initialize the manual analyst.
        Loads the database schema on startup.
        """
        self.schema_text = get_schema_for_prompt()
        print("Manual SQL Analyst initialized. Schema loaded.")

    def _generate_sql(self, question: str) -> str:
        """
        Generates SQL based on the question using simple keyword matching.

        This is the part that will later be replaced by the LLM.
        For now, we use hardcoded rules to demonstrate the workflow.

        Args:
            question: The natural language question.

        Returns:
            A SQL query string.
        """
        question_lower = question.lower()

        # ── Basic Count Questions ──────────────────────────────────
        if "how many customers" in question_lower:
            return "SELECT COUNT(*) as count FROM customers"

        if "how many products" in question_lower:
            return "SELECT COUNT(*) as count FROM products"

        if "how many orders" in question_lower:
            return "SELECT COUNT(*) as count FROM orders"

        if "how many order items" in question_lower or "how many items" in question_lower:
            return "SELECT COUNT(*) as count FROM order_items"

        # ── Revenue Questions ─────────────────────────────────────
        if "total revenue" in question_lower:
            return """
                SELECT ROUND(SUM(quantity * unit_price), 2) as total_revenue
                FROM order_items
            """

        if "revenue by category" in question_lower:
            return """
                SELECT
                    p.category,
                    ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
                FROM products p
                JOIN order_items oi ON p.product_id = oi.product_id
                GROUP BY p.category
                ORDER BY revenue DESC
            """

        if "revenue by month" in question_lower:
            return """
                SELECT
                    strftime('%Y-%m', o.order_date) as month,
                    ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                GROUP BY month
                ORDER BY month
            """

        # ── Top X Questions ───────────────────────────────────────
        if "top 5 customers by spending" in question_lower or "top five customers" in question_lower:
            return """
                SELECT
                    c.name,
                    ROUND(SUM(oi.quantity * oi.unit_price), 2) as total_spent
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                JOIN order_items oi ON o.order_id = oi.order_id
                GROUP BY c.customer_id, c.name
                ORDER BY total_spent DESC
                LIMIT 5
            """

        if "top 5 products by revenue" in question_lower or "top five products" in question_lower:
            return """
                SELECT
                    p.product_name,
                    ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
                FROM products p
                JOIN order_items oi ON p.product_id = oi.product_id
                GROUP BY p.product_id, p.product_name
                ORDER BY revenue DESC
                LIMIT 5
            """

        if "top selling product" in question_lower or "which product sold the most" in question_lower:
            return """
                SELECT
                    p.product_name,
                    SUM(oi.quantity) as total_quantity
                FROM products p
                JOIN order_items oi ON p.product_id = oi.product_id
                GROUP BY p.product_id, p.product_name
                ORDER BY total_quantity DESC
                LIMIT 1
            """

        # ── Average Questions ──────────────────────────────────────
        if "average order value" in question_lower:
            return """
                SELECT
                    ROUND(AVG(total_amount), 2) as avg_order_value
                FROM (
                    SELECT
                        o.order_id,
                        SUM(oi.quantity * oi.unit_price) as total_amount
                    FROM orders o
                    JOIN order_items oi ON o.order_id = oi.order_id
                    GROUP BY o.order_id
                )
            """

        # ── City Questions ─────────────────────────────────────────
        if "which city has the most customers" in question_lower:
            return """
                SELECT
                    city,
                    COUNT(*) as customer_count
                FROM customers
                GROUP BY city
                ORDER BY customer_count DESC
                LIMIT 1
            """

        if "customers by city" in question_lower:
            return """
                SELECT
                    city,
                    COUNT(*) as customer_count
                FROM customers
                GROUP BY city
                ORDER BY customer_count DESC
            """

        # ── Default: Return a simple query if no match ─────────────
        # This prevents the workflow from breaking on unexpected questions.
        # In the AI version, the LLM will handle arbitrary questions.
        return "SELECT 1 as dummy"

    def _format_answer(
        self,
        question: str,
        sql: str,
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formats the raw database result into a human-readable answer.

        Args:
            question: The original question.
            sql: The SQL query that was executed.
            execution_result: The result from execute_readonly_query.

        Returns:
            A dictionary containing the formatted answer, SQL, and metadata.
        """
        if not execution_result["success"]:
            return {
                "question": question,
                "answer": "I could not answer your question due to a database error.",
                "error": execution_result["error"],
                "sql": sql,
                "rows": [],
                "columns": [],
                "row_count": 0,
            }

        rows = execution_result["rows"]
        columns = execution_result["columns"]
        row_count = execution_result["row_count"]
        truncated = execution_result["truncated"]

        # If there are no rows, return a simple answer
        if row_count == 0:
            return {
                "question": question,
                "answer": "No data found for this query.",
                "sql": sql,
                "rows": [],
                "columns": columns,
                "row_count": 0,
            }

        # ── Single Value Answers ────────────────────────────────────
        # If the result has exactly one row and one column, treat it as a scalar answer.
        if row_count == 1 and len(columns) == 1:
            value = rows[0][columns[0]]
            return {
                "question": question,
                "answer": f"{value}",
                "sql": sql,
                "rows": rows,
                "columns": columns,
                "row_count": row_count,
            }

        # ── Single Row, Multiple Columns ────────────────────────────
        # If the result has exactly one row, describe it as a single record.
        if row_count == 1:
            description_parts = [f"{col}: {rows[0][col]}" for col in columns]
            description = ", ".join(description_parts)
            return {
                "question": question,
                "answer": f"Result: {description}",
                "sql": sql,
                "rows": rows,
                "columns": columns,
                "row_count": row_count,
            }

        # ── Multiple Rows: Format as a Table ─────────────────────────
        # For multiple rows, create a simple text table representation.
        if row_count > 1:
            # Create a header
            header = " | ".join(columns)
            separator = "-" * len(header)

            # Create rows
            table_rows = [header, separator]
            for row in rows:
                row_values = [str(row.get(col, "")) for col in columns]
                table_rows.append(" | ".join(row_values))

            table = "\n".join(table_rows)

            # Add a note if results were truncated
            truncation_note = ""
            if truncated:
                truncation_note = (
                    f"\n\n[Note: Only {row_count} of more than {row_count} rows shown. "
                    f"Maximum row limit is {execution_result.get('limit', 'N/A')}.]"
                )

            return {
                "question": question,
                "answer": f"Query results:\n\n{table}{truncation_note}",
                "sql": sql,
                "rows": rows,
                "columns": columns,
                "row_count": row_count,
                "truncated": truncated,
            }

        # Fallback (should not reach here)
        return {
            "question": question,
            "answer": "I found data but could not format it properly.",
            "sql": sql,
            "rows": rows,
            "columns": columns,
            "row_count": row_count,
        }

    def analyze(self, question: str) -> Dict[str, Any]:
        """
        Processes a natural language question and returns an answer.

        This is the main entry point for the manual workflow.
        It implements the complete pipeline:

        1. Generate SQL from the question
        2. Validate the SQL
        3. Execute the query
        4. Format the answer

        Args:
            question: The natural language question to answer.

        Returns:
            A dictionary containing:
            - question: The original question
            - answer: The human-readable answer
            - sql: The SQL query that was executed
            - rows: The raw result rows
            - columns: The column names
            - row_count: Number of rows returned
            - error: Any error message (None if successful)
        """
        # ── Step 1: Generate SQL ─────────────────────────────────────
        sql = self._generate_sql(question)

        # ── Step 2: Validate SQL ─────────────────────────────────────
        is_valid, validation_error = validate_sql_query(sql)
        if not is_valid:
            return {
                "question": question,
                "answer": f"Invalid SQL query: {validation_error}",
                "sql": sql,
                "rows": [],
                "columns": [],
                "row_count": 0,
                "error": validation_error,
            }

        # ── Step 3: Execute Query ─────────────────────────────────────
        execution_result = execute_readonly_query(sql)

        # ── Step 4: Format Answer ─────────────────────────────────────
        answer = self._format_answer(question, sql, execution_result)

        return answer