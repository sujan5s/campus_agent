from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added to tables that already exist in older demo DBs. `create_all`
# only creates missing *tables*, never missing columns — so Phase 3 (F3 booking)
# needs this tiny additive shim. It only ever ADDs; it never drops or rewrites.
# Alembic takes over once the schema stabilizes (docs/04-ROADMAP Phase 0 note).
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "events": {
        "category": "VARCHAR(30) DEFAULT 'event'",
        "created_at": "DATETIME",
    },
    "bookings": {
        "requested_by": "INTEGER",
        "purpose": "TEXT DEFAULT ''",
        "rationale": "TEXT DEFAULT ''",
        "request_key": "VARCHAR(64)",
        "last_nag_at": "DATETIME",
    },
}


def _ensure_columns() -> None:
    """Idempotently add any missing columns listed in _ADDED_COLUMNS (SQLite)."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return  # other backends: use a real migration
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                continue  # table doesn't exist yet — create_all made it correctly
            existing = {r[1] for r in rows}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    """Create all tables (dev convenience; Alembic takes over once schema stabilizes)."""
    from app.db import models  # noqa: F401 — register models on Base

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
