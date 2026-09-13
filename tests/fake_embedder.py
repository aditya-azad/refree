import hashlib
import math
from collections.abc import Sequence

from app.extraction.embedder import Embedder


class FakeEmbedder(Embedder):
    def __init__(self, dim: int = 32) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self._dim
            for word in text.lower().split():
                digest = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vec[digest % self._dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]