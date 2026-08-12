import re

from app.references.citation_key import _first_author_last_name
from app.references.models import Reference


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _first_author_last_name_lower(authors: list[str]) -> str:
    return _first_author_last_name(authors).lower()


class _DSU:
    def __init__(self, n: int) -> None:
        self._parent: list[int] = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


class DuplicateDetector:
    @staticmethod
    def find_groups(references: list[Reference]) -> list[list[Reference]]:
        if len(references) < 2:
            return []
        dsu = _DSU(len(references))
        by_key: dict[str, int] = {}
        for index, ref in enumerate(references):
            for key in DuplicateDetector._duplicate_keys(ref):
                existing = by_key.get(key)
                if existing is None:
                    by_key[key] = index
                else:
                    dsu.union(existing, index)
        clusters: dict[int, list[Reference]] = {}
        for index, ref in enumerate(references):
            clusters.setdefault(dsu.find(index), []).append(ref)
        groups: list[list[Reference]] = []
        for members in clusters.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: (r.title.lower(), str(r.id)))
            groups.append(members)
        groups.sort(key=lambda g: g[0].title.lower())
        return groups

    @staticmethod
    def _duplicate_keys(ref: Reference) -> list[str]:
        keys: list[str] = []
        if ref.doi:
            keys.append("doi:" + ref.doi.lower())
        norm_title = normalize_title(ref.title)
        if norm_title:
            if ref.year is not None:
                keys.append(f"ty:{norm_title}|{ref.year}")
            author = _first_author_last_name_lower(list(ref.authors))
            if author:
                keys.append(f"ta:{norm_title}|{author}")
        return keys
