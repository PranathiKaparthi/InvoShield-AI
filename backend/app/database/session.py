import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
connect_args = {}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args)
else:
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        # Test connection
        with engine.connect() as conn:
            logger.info("Successfully connected to primary database.")
    except Exception as e:
        logger.warning(f"Failed to connect to primary database at {db_url}: {e}. Falling back to SQLite.")
        db_url = "sqlite:///./invoshield.db"
        connect_args = {"check_same_thread": False}
        engine = create_engine(db_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all database tables and seed initial admin/reviewer/user if not present."""
    from sqlalchemy import text
    from app.models.entities import User
    from app.core.security import get_password_hash
    Base.metadata.create_all(bind=engine)

    # Automatic schema migration for new columns
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(invoices)"))
            cols = [row[1] for row in res.fetchall()]
            if cols:
                if "sha256_checksum" not in cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN sha256_checksum VARCHAR(64)"))
                if "organization" not in cols:
                    conn.execute(text("ALTER TABLE invoices ADD COLUMN organization VARCHAR(120) DEFAULT 'General'"))
                conn.commit()
    except Exception as e:
        logger.debug(f"Schema migration note: {e}")
    
    # Check if admin exists; if not, seed default demo users
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.email == "admin@invoshield.ai").first()
        if not admin_user:
            demo_users = [
                User(
                    name="Security Administrator",
                    email="admin@invoshield.ai",
                    password_hash=get_password_hash("Admin@12345"),
                    role="admin",
                    organization="InvoShield Global Security"
                ),
                User(
                    name="Senior Financial Reviewer",
                    email="reviewer@invoshield.ai",
                    password_hash=get_password_hash("Reviewer@12345"),
                    role="reviewer",
                    organization="Apex FinTech Audits"
                ),
                User(
                    name="Standard User",
                    email="user@invoshield.ai",
                    password_hash=get_password_hash("User@12345"),
                    role="user",
                    organization="Acme Supply Co"
                ),
            ]
            db.add_all(demo_users)
            db.commit()
            logger.info("Seeded default users: admin@invoshield.ai, reviewer@invoshield.ai, user@invoshield.ai")
    except Exception as e:
        logger.error(f"Error seeding default users: {e}")
        db.rollback()
    finally:
        db.close()
