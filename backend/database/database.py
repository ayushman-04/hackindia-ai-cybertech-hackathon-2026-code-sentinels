from typing import List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_sqlite_schema_migrations(target_engine: Optional[Engine] = None) -> List[str]:
    """
    Safe, non-destructive schema migration helper for SQLite.
    Creates any missing tables and adds any missing columns defined on SQLAlchemy
    models via ALTER TABLE ADD COLUMN while preserving all existing rows.
    """
    active_engine = target_engine or engine
    import backend.database.models  # noqa: F401

    Base.metadata.create_all(bind=active_engine)
    inspector = inspect(active_engine)
    existing_tables = set(inspector.get_table_names())
    added_columns: List[str] = []

    with active_engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            existing_col_names = {col["name"] for col in inspector.get_columns(table_name)}
            for column in table.columns:
                if column.name in existing_col_names:
                    continue
                col_type_sql = column.type.compile(dialect=active_engine.dialect)
                conn.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type_sql}')
                )
                if (
                    column.default is not None
                    and getattr(column.default, "is_scalar", False)
                    and isinstance(column.default.arg, (str, int, float, bool))
                ):
                    default_val = column.default.arg
                    conn.execute(
                        text(
                            f'UPDATE "{table_name}" SET "{column.name}" = :default_val '
                            f'WHERE "{column.name}" IS NULL'
                        ),
                        {"default_val": default_val},
                    )
                added_columns.append(f"{table_name}.{column.name}")

    return added_columns


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
