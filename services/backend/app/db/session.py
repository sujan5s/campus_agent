from sqlalchemy import create_engine, inspect, text
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


# Nullable columns added to existing tables after they shipped. create_all() only
# creates *missing tables*, so an existing campus.db would keep the old shape —
# these ALTERs bring it forward. Additive and nullable only; anything structural
# still warrants a real migration (Alembic, once the schema stabilizes).
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "timetable_entries": {
        "elective_group_id": "INTEGER REFERENCES elective_groups(id)",  # Phase 2.4
    },
    # Phase 3 (F3 booking): events/bookings shipped in Phase 0 as thin stubs.
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


def ensure_schema() -> list[str]:
    """Add any missing additive columns to already-created tables. Idempotent;
    returns the columns it added (empty on an up-to-date DB)."""
    added: list[str] = []
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all() just made it with the column already
            have = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    added.append(f"{table}.{name}")
    return added


def init_db() -> None:
    """Create all tables (dev convenience; Alembic takes over once schema stabilizes)."""
    from app.db import models  # noqa: F401 — register models on Base

    Base.metadata.create_all(bind=engine)
    ensure_schema()
