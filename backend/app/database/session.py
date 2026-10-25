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

# Columns added after the first release. init_db() adds any that are missing so existing
# SQLite/PostgreSQL databases keep working without a separate migration tool.
_COLUMN_MIGRATIONS = {
    "invoices": [
        ("sha256_checksum", "VARCHAR(64)"),
        ("organization", "VARCHAR(120) DEFAULT 'General'"),
        ("payment_status", "VARCHAR(30) DEFAULT 'unpaid'"),
        ("source_channel", "VARCHAR(30) DEFAULT 'web'"),
        ("source_contact_id", "INTEGER"),
    ],
    "users": [
        ("must_change_password", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ],
}


def run_column_migrations(bind=None):
    """Add missing columns listed in _COLUMN_MIGRATIONS (idempotent)."""
    from sqlalchemy import inspect, text
    bind = bind or engine
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    with bind.begin() as conn:
        for table, columns in _COLUMN_MIGRATIONS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    logger.info(f"Migration: added column {table}.{name}")


def init_db():
    """Create tables, run column migrations, and seed accounts according to the environment."""
    import app.models  # noqa: F401  registers every model (incl. assistant tables) before create_all
    assert app.models
    from app.models.entities import User
    from app.core.security import get_password_hash
    from app.core.config import enforce_production_safety

    enforce_production_safety(settings)
    Base.metadata.create_all(bind=engine)
    try:
        run_column_migrations()
    except Exception as e:
        logger.warning(f"Schema migration note: {e}")

    db = SessionLocal()
    try:
        # Demo accounts: development only. They are documented publicly, so never in production.
        if settings.SEED_DEMO_USERS and not settings.is_production:
            admin_user = db.query(User).filter(User.email == "admin@invoshield.ai").first()
            if not admin_user:
                db.add_all([
                    User(name="Security Administrator", email="admin@invoshield.ai",
                         password_hash=get_password_hash("Admin@12345"), role="admin",
                         organization="InvoShield Global Security"),
                    User(name="Senior Financial Reviewer", email="reviewer@invoshield.ai",
                         password_hash=get_password_hash("Reviewer@12345"), role="reviewer",
                         organization="Apex FinTech Audits"),
                    User(name="Standard User", email="user@invoshield.ai",
                         password_hash=get_password_hash("User@12345"), role="user",
                         organization="Acme Supply Co"),
                ])
                db.commit()
                logger.info("Seeded DEVELOPMENT demo users: admin@invoshield.ai, reviewer@invoshield.ai, user@invoshield.ai")

        # Production bootstrap admin: created once from env, forced to change password on first login.
        if settings.BOOTSTRAP_ADMIN_EMAIL and settings.BOOTSTRAP_ADMIN_PASSWORD:
            email = settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower()
            if not db.query(User).filter(User.email == email).first():
                db.add(User(
                    name="Administrator", email=email,
                    password_hash=get_password_hash(settings.BOOTSTRAP_ADMIN_PASSWORD),
                    role="admin", organization=settings.BOOTSTRAP_ADMIN_ORGANIZATION,
                    must_change_password=True,
                ))
                db.commit()
                logger.info(f"Created bootstrap admin {email} (password change required on first login).")
    except Exception as e:
        logger.error(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()
