# file: app/database/models.py

"""
Database table definitions (models).

Each class represents one table in the database.
SQLAlchemy reads these classes and creates the actual SQL tables.

Naming convention:
  - Class name: singular, PascalCase (Customer, Product)
  - Table name: plural, snake_case (customers, products)
  - Column names: snake_case (customer_id, order_date)
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.database.connection import Base


# ── Customers Table ───────────────────────────────────────────────
#
# Stores information about each customer.
#
# Columns:
#   customer_id  — unique number for each customer (primary key)
#   name         — full name of the customer
#   email        — email address (must be unique, no duplicates)
#   city         — city where the customer lives
#   signup_date  — date the customer created their account

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    city = Column(String(100), nullable=False)
    signup_date = Column(Date, nullable=False)

    # ── Relationship ──────────────────────────────────────────────
    #
    # This does NOT create a column in the database.
    # It is a Python shortcut that lets you access a customer's
    # orders easily:
    #
    #   customer = db.query(Customer).first()
    #   print(customer.orders)  # list of all orders by this customer
    #
    # back_populates="customer" connects this to the Order model below.

    orders = relationship("Order", back_populates="customer")

    def __repr__(self):
        """
        Controls how the object looks when printed.
        Useful for debugging.
        """
        return f"<Customer(id={self.customer_id}, name='{self.name}')>"


# ── Products Table ────────────────────────────────────────────────
#
# Stores information about each product we sell.
#
# Columns:
#   product_id    — unique number for each product (primary key)
#   product_name  — name of the product
#   category      — product category (Electronics, Clothing, etc.)
#   price         — price per unit in dollars
#   stock         — how many units are currently in inventory

class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)

    # ── Relationship ──────────────────────────────────────────────
    # A product can appear in many order items.
    order_items = relationship("OrderItem", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.product_id}, name='{self.product_name}')>"


# ── Orders Table ──────────────────────────────────────────────────
#
# Stores each order placed by a customer.
#
# Columns:
#   order_id     — unique number for each order (primary key)
#   customer_id  — which customer placed this order (foreign key)
#   order_date   — date the order was placed
#   status       — current status: pending, shipped, delivered, cancelled

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)

    # ── Foreign Key ───────────────────────────────────────────────
    #
    # ForeignKey("customers.customer_id") tells the database:
    # "This column must contain a value that exists in the
    #  customer_id column of the customers table."
    #
    # If you try to create an order with customer_id=999 and
    # no customer with ID 999 exists, the database rejects it.
    # This is called referential integrity.

    customer_id = Column(
        Integer,
        ForeignKey("customers.customer_id"),
        nullable=False,
    )

    order_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="pending")

    # ── Relationships ─────────────────────────────────────────────
    customer = relationship("Customer", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")

    def __repr__(self):
        return f"<Order(id={self.order_id}, customer={self.customer_id})>"


# ── Order Items Table ─────────────────────────────────────────────
#
# The bridge table connecting orders and products.
# Each row represents one product line within one order.
#
# Example:
#   Order #101 contains 2x Mouse and 1x Cable
#   → Two rows in this table:
#     (item_id=1, order_id=101, product_id=1, quantity=2, unit_price=29.99)
#     (item_id=2, order_id=101, product_id=3, quantity=1, unit_price=9.99)
#
# Columns:
#   item_id     — unique number for each line item (primary key)
#   order_id    — which order this item belongs to (foreign key)
#   product_id  — which product was ordered (foreign key)
#   quantity    — how many units were ordered
#   unit_price  — price per unit at the time of purchase
#                 (stored separately from products.price because
#                  product prices can change over time, but the
#                  order should remember the price at purchase)

class OrderItem(Base):
    __tablename__ = "order_items"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(
        Integer,
        ForeignKey("orders.order_id"),
        nullable=False,
    )
    product_id = Column(
        Integer,
        ForeignKey("products.product_id"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    # ── Relationships ─────────────────────────────────────────────
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")

    def __repr__(self):
        return (
            f"<OrderItem(id={self.item_id}, "
            f"order={self.order_id}, "
            f"product={self.product_id}, "
            f"qty={self.quantity})>"
        )