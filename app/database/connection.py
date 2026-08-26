# file: app/database/connection.py

"""
Database connection setup.

This module creates the connection to our SQLite database.
Every other module that needs to talk to the database
imports the engine and SessionLocal from here.

What is an engine?
  The engine is SQLAlchemy's starting point. It knows how to
  connect to the database (which file, which server, etc.).
  Think of it as the "address" of the database.

What is a session factory?
  The session factory (SessionLocal) creates individual sessions.
  Each session is a temporary workspace for reading and writing data.
  Think of the engine as the building and sessions as the rooms inside.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# ── Create the Engine ─────────────────────────────────────────────
#
# The engine reads the database URL from our config.
# For SQLite, the URL looks like: sqlite:///./data/analytics.db
#
# connect_args={"check_same_thread": False} is required for SQLite
# when using it with FastAPI. Without it, SQLite raises an error
# because FastAPI handles requests on multiple threads.
#
# echo=True would print every SQL query to the terminal.
# We set it to True only in development so you can see what
# SQLAlchemy is doing behind the scenes. Turn it off in production.

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.is_development,
)

# ── Create the Session Factory ────────────────────────────────────
#
# sessionmaker creates a factory. Every time you call SessionLocal(),
# you get a new session (a new workspace).
#
# autocommit=False means you must explicitly call session.commit()
# to save changes. This is safer because accidental changes are
# not saved automatically.
#
# autoflush=False means SQLAlchemy does not automatically send
# pending changes to the database before every query. This gives
# you more control and avoids unexpected behavior.

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ── Create the Base Class ─────────────────────────────────────────
#
# All our table models will inherit from this Base class.
# Base keeps track of all the tables we define so that
# Base.metadata.create_all() can create them all at once.

Base = declarative_base()


# ── Helper Function ───────────────────────────────────────────────
#
# get_db() is a generator function that FastAPI uses to provide
# a database session to each request.
#
# How it works:
#   1. FastAPI calls get_db()
#   2. get_db() creates a new session
#   3. FastAPI uses the session to handle the request
#   4. When the request is done, the finally block closes the session
#
# This ensures every request gets its own clean session and
# sessions are always closed, even if an error occurs.

def get_db():
    """
    Provides a database session for a single request.

    Usage in FastAPI:
        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            result = db.execute(...)
            return result
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()