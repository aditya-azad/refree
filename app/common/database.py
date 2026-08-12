import importlib

from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine

from app.common.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

_MODELS = ("app.references.models",)


def _add_missing_columns() -> None:
    inspector = inspect(engine)
    dialect = engine.dialect
    for table in SQLModel.metadata.sorted_tables:
        if table.name not in inspector.get_table_names():
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            if not column.nullable and column.server_default is None:
                msg = (
                    f"cannot add NOT NULL column {table.name}.{column.name} "
                    "without a default to an existing table"
                )
                raise RuntimeError(msg)
            col_type = column.type.compile(dialect=dialect)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f'ALTER TABLE "{table.name}" '
                        f'ADD COLUMN "{column.name}" {col_type}'
                    )
                )


def create_db_and_tables() -> None:
    for module_name in _MODELS:
        importlib.import_module(module_name)
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()
