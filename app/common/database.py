import importlib

from sqlmodel import SQLModel, create_engine

from app.common.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

_MODELS = ("app.references.models",)


def create_db_and_tables() -> None:
    for module_name in _MODELS:
        importlib.import_module(module_name)
    SQLModel.metadata.create_all(engine)
