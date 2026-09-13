from uuid import uuid4

import pytest
from sqlalchemy.pool import StaticPool

from app.extraction.vector_store import VectorStore, build_vector_engine
from tests.fake_embedder import FakeEmbedder


@pytest.fixture()
def vector_store() -> VectorStore:
    engine = build_vector_engine("sqlite://", in_memory=True)
    store = VectorStore(FakeEmbedder(dim=16), engine=engine)
    yield store
    engine.dispose()


def test_upsert_and_search_returns_inserted_id(
    vector_store: VectorStore,
) -> None:
    rid = uuid4()
    vector_store.upsert(rid, FakeEmbedder(dim=16).embed_one("alpha beta"))
    hits = vector_store.search(
        FakeEmbedder(dim=16).embed_one("alpha beta"), limit=5
    )
    assert hits
    assert hits[0][0] == rid


def test_upsert_replaces_existing(vector_store: VectorStore) -> None:
    rid = uuid4()
    embedder = FakeEmbedder(dim=16)
    vector_store.upsert(rid, embedder.embed_one("alpha"))
    vector_store.upsert(rid, embedder.embed_one("completely different words"))
    assert vector_store.count() == 1


def test_delete_removes_vector(vector_store: VectorStore) -> None:
    rid = uuid4()
    embedder = FakeEmbedder(dim=16)
    vector_store.upsert(rid, embedder.embed_one("alpha"))
    assert vector_store.count() == 1
    vector_store.delete(rid)
    assert vector_store.count() == 0


def test_search_orders_by_similarity(vector_store: VectorStore) -> None:
    embedder = FakeEmbedder(dim=16)
    close = uuid4()
    far = uuid4()
    vector_store.upsert(close, embedder.embed_one("deep learning networks"))
    vector_store.upsert(far, embedder.embed_one("cooking soup recipes"))
    hits = vector_store.search(embedder.embed_one("deep networks"), limit=2)
    assert hits[0][0] == close