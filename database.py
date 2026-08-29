import sqlite3
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # Required for SQLite concurrency
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()

def init_db():
    """Create or upgrade database tables to ensure all models exist."""
    import models
    Base.metadata.create_all(bind=engine)
    
    # Auto-seed initial colonies if empty
    with SessionLocal() as db:
        from models import Colony
        if db.query(Colony).count() == 0:
            default_colonies = [
                Colony(name="Green Park Colony, Delhi", city="Delhi", pincode="110016", alert_level="SAFE"),
                Colony(name="Sector 62, Noida", city="Noida", pincode="201309", alert_level="SAFE"),
                Colony(name="Gomti Nagar, Lucknow", city="Lucknow", pincode="226010", alert_level="SAFE"),
                Colony(name="Indiranagar, Bangalore", city="Bangalore", pincode="560038", alert_level="SAFE"),
                Colony(name="Koregaon Park, Pune", city="Pune", pincode="411001", alert_level="SAFE")
            ]
            db.add_all(default_colonies)
            db.commit()
            print("[DATABASE] Seeded initial colonies.")

def get_db():
    """Dependency for FastAPI route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()