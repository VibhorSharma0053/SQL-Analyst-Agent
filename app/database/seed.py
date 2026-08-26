# file: app/database/seed.py

"""
Seed data script.

This script creates the database tables and fills them with
realistic sample data. Run it once to set up the database.

Usage:
    python -m app.database.seed

What does "seed" mean?
  Seeding a database means filling it with initial data.
  Think of planting seeds in a garden — you put the initial
  plants in the soil so the garden has something to grow from.

This script is safe to run multiple times. It checks whether
data already exists before inserting, so it will not create
duplicate records.
"""

from datetime import date
from app.database.connection import engine, SessionLocal, Base
from app.database.models import Customer, Product, Order, OrderItem


def create_tables():
    """
    Creates all database tables defined in models.py.

    Base.metadata.create_all() reads every class that inherits
    from Base and creates the corresponding SQL table if it
    does not already exist.

    If the table already exists, this does nothing.
    It will NOT delete existing data.
    """
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


def seed_customers(db):
    """
    Inserts 20 sample customers into the database.

    The data includes diverse names, cities, and signup dates
    so that queries about geography and time produce interesting results.
    """
    # Check if data already exists
    if db.query(Customer).count() > 0:
        print("Customers already exist. Skipping.")
        return

    customers = [
        Customer(name="Alice Johnson", email="alice@email.com", city="New York", signup_date=date(2023, 1, 15)),
        Customer(name="Bob Smith", email="bob@email.com", city="Chicago", signup_date=date(2023, 2, 20)),
        Customer(name="Carol White", email="carol@email.com", city="Houston", signup_date=date(2023, 3, 10)),
        Customer(name="David Brown", email="david@email.com", city="Phoenix", signup_date=date(2023, 3, 25)),
        Customer(name="Eva Martinez", email="eva@email.com", city="Los Angeles", signup_date=date(2023, 4, 5)),
        Customer(name="Frank Wilson", email="frank@email.com", city="New York", signup_date=date(2023, 4, 18)),
        Customer(name="Grace Lee", email="grace@email.com", city="Chicago", signup_date=date(2023, 5, 2)),
        Customer(name="Henry Taylor", email="henry@email.com", city="Houston", signup_date=date(2023, 5, 14)),
        Customer(name="Iris Anderson", email="iris@email.com", city="Phoenix", signup_date=date(2023, 6, 1)),
        Customer(name="Jack Thomas", email="jack@email.com", city="Los Angeles", signup_date=date(2023, 6, 20)),
        Customer(name="Karen Davis", email="karen@email.com", city="New York", signup_date=date(2023, 7, 8)),
        Customer(name="Leo Garcia", email="leo@email.com", city="Chicago", signup_date=date(2023, 7, 22)),
        Customer(name="Mia Robinson", email="mia@email.com", city="Houston", signup_date=date(2023, 8, 3)),
        Customer(name="Nathan Clark", email="nathan@email.com", city="Phoenix", signup_date=date(2023, 8, 15)),
        Customer(name="Olivia Lewis", email="olivia@email.com", city="Los Angeles", signup_date=date(2023, 9, 1)),
        Customer(name="Paul Walker", email="paul@email.com", city="New York", signup_date=date(2023, 9, 12)),
        Customer(name="Quinn Hall", email="quinn@email.com", city="Chicago", signup_date=date(2023, 10, 5)),
        Customer(name="Rachel Allen", email="rachel@email.com", city="Houston", signup_date=date(2023, 10, 18)),
        Customer(name="Sam Young", email="sam@email.com", city="Phoenix", signup_date=date(2023, 11, 2)),
        Customer(name="Tina King", email="tina@email.com", city="Los Angeles", signup_date=date(2023, 11, 20)),
    ]

    db.add_all(customers)
    db.commit()
    print(f"Inserted {len(customers)} customers.")


def seed_products(db):
    """
    Inserts 15 sample products across 4 categories.

    Categories: Electronics, Clothing, Home, Books
    Prices range from $5.99 to $299.99 to allow interesting
    revenue calculations.
    """
    if db.query(Product).count() > 0:
        print("Products already exist. Skipping.")
        return

    products = [
        # Electronics
        Product(product_name="Wireless Mouse", category="Electronics", price=29.99, stock=150),
        Product(product_name="Mechanical Keyboard", category="Electronics", price=89.99, stock=75),
        Product(product_name="USB-C Hub", category="Electronics", price=45.99, stock=100),
        Product(product_name="Webcam HD", category="Electronics", price=59.99, stock=60),
        # Clothing
        Product(product_name="Cotton T-Shirt", category="Clothing", price=19.99, stock=300),
        Product(product_name="Denim Jeans", category="Clothing", price=49.99, stock=120),
        Product(product_name="Running Shoes", category="Clothing", price=79.99, stock=80),
        Product(product_name="Winter Jacket", category="Clothing", price=129.99, stock=40),
        # Home
        Product(product_name="Desk Lamp", category="Home", price=34.99, stock=90),
        Product(product_name="Coffee Mug Set", category="Home", price=24.99, stock=200),
        Product(product_name="Throw Pillow", category="Home", price=15.99, stock=180),
        Product(product_name="Wall Clock", category="Home", price=22.99, stock=70),
        # Books
        Product(product_name="Python Programming", category="Books", price=39.99, stock=110),
        Product(product_name="Data Science Handbook", category="Books", price=44.99, stock=85),
        Product(product_name="AI and the Future", category="Books", price=29.99, stock=95),
    ]

    db.add_all(products)
    db.commit()
    print(f"Inserted {len(products)} products.")


def seed_orders_and_items(db):
    """
    Inserts 50 orders and approximately 120 order items.

    Each order belongs to a random customer and contains 1 to 4 products.
    Order dates span from January 2024 to December 2024 so that
    monthly and quarterly analysis queries produce meaningful results.

    The unit_price in each order item matches the product's current price.
    In a real application, this would be the price at the time of purchase.
    """
    if db.query(Order).count() > 0:
        print("Orders already exist. Skipping.")
        return

    # Fetch all products so we can reference their IDs and prices
    products = db.query(Product).all()

    # ── Define 50 orders manually ─────────────────────────────────
    #
    # Each tuple contains:
    #   (customer_id, order_date, status, [(product_index, quantity), ...])
    #
    # product_index is the position in the products list (0-based).
    # We use this to look up the product_id and price.

    order_data = [
        # January 2024
        (1, date(2024, 1, 5), "delivered", [(0, 2), (4, 1)]),
        (2, date(2024, 1, 10), "delivered", [(1, 1)]),
        (3, date(2024, 1, 15), "delivered", [(8, 1), (9, 2)]),
        (5, date(2024, 1, 20), "delivered", [(12, 1), (13, 1)]),
        # February 2024
        (1, date(2024, 2, 3), "delivered", [(2, 1), (3, 1)]),
        (4, date(2024, 2, 8), "delivered", [(5, 2)]),
        (6, date(2024, 2, 14), "delivered", [(6, 1), (4, 3)]),
        (7, date(2024, 2, 20), "delivered", [(14, 2)]),
        (2, date(2024, 2, 25), "delivered", [(0, 1), (10, 1)]),
        # March 2024
        (8, date(2024, 3, 2), "delivered", [(7, 1)]),
        (3, date(2024, 3, 8), "delivered", [(1, 1), (2, 1)]),
        (9, date(2024, 3, 12), "delivered", [(4, 2), (5, 1)]),
        (10, date(2024, 3, 18), "delivered", [(11, 1), (12, 1)]),
        (1, date(2024, 3, 25), "delivered", [(6, 1)]),
        # April 2024
        (5, date(2024, 4, 1), "delivered", [(3, 1), (8, 1)]),
        (11, date(2024, 4, 7), "delivered", [(0, 3)]),
        (6, date(2024, 4, 12), "delivered", [(13, 1), (14, 1)]),
        (12, date(2024, 4, 18), "delivered", [(7, 1), (9, 1)]),
        (2, date(2024, 4, 22), "delivered", [(1, 1)]),
        # May 2024
        (13, date(2024, 5, 3), "delivered", [(4, 1), (10, 2)]),
        (7, date(2024, 5, 8), "delivered", [(2, 2)]),
        (14, date(2024, 5, 14), "delivered", [(5, 1), (6, 1)]),
        (3, date(2024, 5, 20), "delivered", [(12, 2)]),
        (15, date(2024, 5, 28), "delivered", [(0, 1), (11, 1)]),
        # June 2024
        (1, date(2024, 6, 2), "delivered", [(7, 1), (8, 1)]),
        (16, date(2024, 6, 8), "delivered", [(1, 1), (3, 1)]),
        (4, date(2024, 6, 15), "delivered", [(9, 3)]),
        (8, date(2024, 6, 20), "delivered", [(13, 1)]),
        (17, date(2024, 6, 25), "delivered", [(4, 2), (14, 1)]),
        # July 2024
        (5, date(2024, 7, 3), "delivered", [(6, 1), (2, 1)]),
        (9, date(2024, 7, 10), "delivered", [(0, 2), (10, 1)]),
        (18, date(2024, 7, 15), "delivered", [(5, 1)]),
        (10, date(2024, 7, 22), "delivered", [(12, 1), (11, 2)]),
        (2, date(2024, 7, 28), "delivered", [(7, 1)]),
        # August 2024
        (11, date(2024, 8, 2), "delivered", [(1, 1), (4, 2)]),
        (19, date(2024, 8, 8), "delivered", [(3, 1), (8, 1)]),
        (6, date(2024, 8, 14), "delivered", [(13, 2)]),
        (12, date(2024, 8, 20), "delivered", [(0, 1), (9, 1)]),
        (20, date(2024, 8, 26), "delivered", [(6, 1), (14, 1)]),
        # September 2024
        (1, date(2024, 9, 3), "delivered", [(2, 1), (5, 1)]),
        (13, date(2024, 9, 10), "delivered", [(7, 1)]),
        (3, date(2024, 9, 15), "delivered", [(12, 1), (10, 1)]),
        (14, date(2024, 9, 22), "shipped", [(4, 3)]),
        # October 2024
        (7, date(2024, 10, 1), "shipped", [(1, 1), (11, 1)]),
        (15, date(2024, 10, 8), "shipped", [(8, 2)]),
        (16, date(2024, 10, 15), "shipped", [(0, 1), (3, 1)]),
        (4, date(2024, 10, 22), "pending", [(6, 1), (13, 1)]),
        # November 2024
        (17, date(2024, 11, 2), "pending", [(5, 2), (9, 1)]),
        (8, date(2024, 11, 10), "pending", [(14, 1)]),
        (20, date(2024, 11, 18), "pending", [(2, 1), (7, 1)]),
    ]

    total_items = 0

    for customer_id, order_date, status, items in order_data:
        # Create the order
        order = Order(
            customer_id=customer_id,
            order_date=order_date,
            status=status,
        )
        db.add(order)
        db.flush()  # flush assigns the order_id without committing

        # Create order items for this order
        for product_index, quantity in items:
            product = products[product_index]
            order_item = OrderItem(
                order_id=order.order_id,
                product_id=product.product_id,
                quantity=quantity,
                unit_price=product.price,
            )
            db.add(order_item)
            total_items += 1

    db.commit()
    print(f"Inserted {len(order_data)} orders with {total_items} order items.")


def main():
    """
    Main function that runs all seeding steps in order.

    The order matters:
    1. Create tables first (cannot insert into tables that don't exist)
    2. Insert customers first (orders reference customer_id)
    3. Insert products second (order_items reference product_id)
    4. Insert orders and items last (they reference both)
    """
    print("=" * 50)
    print("  SQL Analyst Agent — Database Seeder")
    print("=" * 50)
    print()

    # Step 1: Create all tables
    create_tables()
    print()

    # Step 2: Open a database session
    db = SessionLocal()

    try:
        # Step 3: Insert data in the correct order
        seed_customers(db)
        seed_products(db)
        seed_orders_and_items(db)

        print()
        print("=" * 50)
        print("  Database seeding complete!")
        print("=" * 50)

        # Step 4: Print a summary
        print()
        print("Database summary:")
        print(f"  Customers:   {db.query(Customer).count()}")
        print(f"  Products:    {db.query(Product).count()}")
        print(f"  Orders:      {db.query(Order).count()}")
        print(f"  Order Items: {db.query(OrderItem).count()}")
        print()

    finally:
        db.close()


# This block ensures the script only runs when executed directly,
# not when imported by another module.
if __name__ == "__main__":
    main()