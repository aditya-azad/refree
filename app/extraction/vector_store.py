import sqlite3
from collections.abc import Sequence
from uuid import UUID

import sqlite_vec
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app.common.config import settings
from app.extraction.embedder import Embedder

_EMBEDDING_TABLE = "refree_embeddings"


def build_vector_engine(
    database_url: str, *, in_memory: bool = False
) -> Engine:
    connect_args: dict[str, object] = {"check_same_thread": False}
    kwargs: dict[str, object] = {}
    if in_memory:
        connect_args["check_same_thread"] = False
        kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, connect_args=connect_args, **kwargs)

    @event.listens_for(engine, "connect")
    def _load_sqlite_vec(
        dbapi_connection: sqlite3.Connection, _record: object
    ) -> None:
        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)

    return engine


vector_engine = build_vector_engine(settings.database_url)


class VectorStore:
    def __init__(self, embedder: Embedder, engine: Engine) -> None:
        self._embedder = embedder
        self._dimension = embedder.dimension
        self._engine = engine
        self._ensure_table()

    def _ensure_table(self) -> None:
        table = _EMBEDDING_TABLE
        dimension = self._dimension
        ddl = (
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} "
            "USING vec0("
            "reference_id TEXT PRIMARY KEY, "
            f"embedding FLOAT[{dimension}] distance_metric=cosine)"
        )
        with self._engine.begin() as conn:
            conn.execute(text(ddl))

    def upsert(self, reference_id: UUID, embedding: Sequence[float]) -> None:
        packed = sqlite_vec.serialize_float32(list(embedding))
        key = str(reference_id)
        with self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM refree_embeddings WHERE reference_id = :k"),
                {"k": key},
            )
            conn.execute(
                text(
                    "INSERT INTO refree_embeddings "
                    "(reference_id, embedding) VALUES (:k, :e)"
                ),
                {"k": key, "e": packed},
            )

    def delete(self, reference_id: UUID) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM refree_embeddings WHERE reference_id = :k"),
                {"k": str(reference_id)},
            )

    def search(
        self, query: Sequence[float], limit: int
    ) -> list[tuple[UUID, float]]:
        packed = sqlite_vec.serialize_float32(list(query))
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT reference_id, distance FROM refree_embeddings "
                    "WHERE embedding MATCH :q ORDER BY distance LIMIT :limit"
                ),
                {"q": packed, "limit": limit},
            ).all()
        return [(UUID(str(row[0])), float(row[1])) for row in rows]

    def count(self) -> int:
        with self._engine.connect() as conn:
            return int(
                conn.execute(
                    text("SELECT COUNT(*) FROM refree_embeddings")
                ).scalar_one()
            )
