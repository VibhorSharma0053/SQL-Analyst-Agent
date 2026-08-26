# file: app/database/schema_inspector.py

"""
Database Schema Inspector.

This module provides tools to inspect the active database structure
at runtime using SQLAlchemy's inspection engine.

It extracts:
- Table names
- Column names and data types
- Primary key constraints
- Foreign key relationships

It also formats this information into a compact string suitable
for inclusion in LLM prompts.
"""

from typing import Dict, List, Any
from sqlalchemy import inspect
from app.database.connection import engine


def get_table_names() -> List[str]:
    """
    Returns a list of all table names in the database.
    """
    inspector = inspect(engine)
    return inspector.get_table_names()


def get_table_details(table_name: str) -> Dict[str, Any]:
    """
    Extracts column details, primary keys, and foreign keys for a single table.

    Returns a dictionary structured as:
    {
        "table_name": "orders",
        "columns": [
            {"name": "order_id", "type": "INTEGER", "nullable": False},
            ...
        ],
        "primary_keys": ["order_id"],
        "foreign_keys": [
            {
                "constrained_columns": ["customer_id"],
                "referred_table": "customers",
                "referred_columns": ["customer_id"]
            }
        ]
    }
    """
    inspector = inspect(engine)
    
    # 1. Get column information
    columns_raw = inspector.get_columns(table_name)
    columns = [
        {
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col.get("nullable", True)
        }
        for col in columns_raw
    ]

    # 2. Get primary keys
    pk_constraint = inspector.get_pk_constraint(table_name)
    primary_keys = pk_constraint.get("constrained_columns", [])

    # 3. Get foreign keys
    fks_raw = inspector.get_foreign_keys(table_name)
    foreign_keys = [
        {
            "constrained_columns": fk.get("constrained_columns", []),
            "referred_table": fk.get("referred_table"),
            "referred_columns": fk.get("referred_columns", [])
        }
        for fk in fks_raw
    ]

    return {
        "table_name": table_name,
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys
    }


def get_full_schema() -> Dict[str, Any]:
    """
    Inspects all tables and returns a dictionary of the complete database schema.
    """
    tables = get_table_names()
    schema = {}
    for table in tables:
        schema[table] = get_table_details(table)
    return schema


def get_schema_for_prompt() -> str:
    """
    Formats the complete database schema into a clean, human-readable string
    designed specifically for LLM context prompts.

    Example output:
    Table: customers
      - customer_id (INTEGER) [PRIMARY KEY]
      - name (VARCHAR(100))
      - email (VARCHAR(150))
      - city (VARCHAR(100))
      - signup_date (DATE)

    Table: orders
      - order_id (INTEGER) [PRIMARY KEY]
      - customer_id (INTEGER) [FOREIGN KEY -> customers.customer_id]
      - order_date (DATE)
      - status (VARCHAR(20))
    """
    schema = get_full_schema()
    formatted_lines = []

    for table_name, details in schema.items():
        formatted_lines.append(f"Table: {table_name}")
        
        # Build quick lookup sets for constraints
        pk_set = set(details["primary_keys"])
        fk_map = {}
        for fk in details["foreign_keys"]:
            for col, ref_col in zip(fk["constrained_columns"], fk["referred_columns"]):
                fk_map[col] = f"{fk['referred_table']}.{ref_col}"

        for col in details["columns"]:
            col_name = col["name"]
            col_type = col["type"]
            flags = []

            if col_name in pk_set:
                flags.append("PRIMARY KEY")
            if col_name in fk_map:
                flags.append(f"FOREIGN KEY -> {fk_map[col_name]}")

            flag_str = f" [{', '.join(flags)}]" if flags else ""
            formatted_lines.append(f"  - {col_name} ({col_type}){flag_str}")
        
        formatted_lines.append("")  # Empty line between tables

    return "\n".join(formatted_lines).strip()