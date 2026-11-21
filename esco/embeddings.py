import hashlib
import sqlite3
from pathlib import Path

import httpx
import numpy as np

from esco.data import Catalog, digest, read_json, write_json

PROFILE = "embeddinggemma-retrieval-v1"


def unit_vectors(values, count=None):
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.ndim != 2 or not matrix.shape[1] or (count is not None and matrix.shape[0] != count):
        raise ValueError("Invalid embedding count or dimensions")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if not np.isfinite(matrix).all() or not np.isfinite(norms).all() or (norms <= 0).any():
        raise ValueError("Embeddings must be finite, non-zero vectors")
    return matrix / norms


def document_text(concept):
    titles, parts = [], []
    for lang, labels in sorted(concept.labels.items()):
        titles.append(labels.preferred)
        alternatives = "; ".join(labels.alternative[:12])[:700]
        parts.append(f"{lang}: {labels.preferred}. Alternatives: {alternatives}. {labels.description[:1000]}")
    return f"title: {' / '.join(titles)} | text: " + "\n".join(parts)[:3600]


def query_text(skill, context=""):
    return f"task: search result | query: {skill}" + (f". Context: {context[:1500]}" if context else "")


class OllamaEmbedder:
    def __init__(self, model="embeddinggemma:latest", url="http://localhost:11434", http=None):
        if model.split(":")[0] != "embeddinggemma":
            raise ValueError("This retrieval profile supports embeddinggemma only")
        self.model = model if ":" in model else model + ":latest"
        self.url = url.rstrip("/")
        self.http = http or httpx.Client(timeout=180)
        self.owned = http is None
        self.profile = PROFILE
        self.model_digest = self._digest()

    def _digest(self):
        response = self.http.get(self.url + "/api/tags")
        response.raise_for_status()
        for model in response.json()["models"]:
            if model["name"] == self.model:
                if model.get("remote_host") or model.get("remote_model"):
                    raise ValueError("Use a local embedding model")
                return model["digest"]
        raise ValueError(f"Model {self.model} is not installed. Run: ollama pull {self.model}")

    def verify(self):
        if self._digest() != self.model_digest:
            raise ValueError("Embedding model changed; rebuild the index")

    def embed(self, texts):
        response = self.http.post(self.url + "/api/embed", json={
            "model": self.model, "input": texts, "truncate": False, "keep_alive": "10m"})
        response.raise_for_status()
        return unit_vectors(response.json()["embeddings"], len(texts))

    def close(self):
        if self.owned:
            self.http.close()


class EmbeddingCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, dimensions INTEGER, vector BLOB)")

    def get_many(self, client, texts, batch_size=32, log=None):
        if batch_size < 1:
            raise ValueError("Batch size must be positive")
        keys = [digest([client.model_digest, client.profile, text]) for text in texts]
        vectors = {}
        for key in set(keys):
            row = self.db.execute("SELECT dimensions, vector FROM vectors WHERE key=?", (key,)).fetchone()
            if row:
                vector = np.frombuffer(row[1], dtype="<f4")
                if len(vector) != row[0]:
                    raise ValueError("Invalid cached vector")
                vectors[key] = vector
        missing = list(dict.fromkeys(key for key in keys if key not in vectors))
        by_key = dict(zip(keys, texts))
        for start in range(0, len(missing), batch_size):
            batch = missing[start:start + batch_size]
            values = unit_vectors(client.embed([by_key[key] for key in batch]), len(batch))
            with self.db:
                for key, value in zip(batch, values):
                    self.db.execute("INSERT OR REPLACE INTO vectors VALUES (?, ?, ?)",
                                    (key, len(value), value.astype("<f4").tobytes()))
                    vectors[key] = value
            if log:
                log(f"Embeddings: {min(start + len(batch), len(missing))}/{len(missing)} new texts")
        return unit_vectors([vectors[key] for key in keys], len(keys))

    def close(self):
        self.db.close()


def build_index(catalog: Catalog, out: Path, client, cache, batch_size=32, log=print):
    if out.exists():
        raise ValueError("Index directory exists; choose a new path")
    concepts = sorted(catalog.concepts, key=lambda c: c.uri)
    texts = [document_text(c) for c in concepts]
    vectors = cache.get_many(client, texts, batch_size, log)
    client.verify()
    out.mkdir(parents=True, exist_ok=False)
    np.save(out / "vectors.npy", vectors, allow_pickle=False)
    metadata = {"format_version": 1, "catalog_fingerprint": catalog.fingerprint,
                "esco_version": catalog.esco_version, "model": client.model,
                "model_digest": client.model_digest, "profile": client.profile,
                "dimensions": vectors.shape[1], "uris": [c.uri for c in concepts],
                "document_fingerprint": digest(texts),
                "vectors_sha256": hashlib.sha256((out / "vectors.npy").read_bytes()).hexdigest()}
    write_json(out / "manifest.json", metadata)
    return metadata


class SemanticIndex:
    def __init__(self, path: Path, catalog: Catalog, client, cache):
        self.meta = read_json(path / "manifest.json")
        expected = {"format_version": 1, "catalog_fingerprint": catalog.fingerprint,
                    "esco_version": catalog.esco_version, "model_digest": client.model_digest,
                    "profile": client.profile}
        for key, value in expected.items():
            if self.meta.get(key) != value:
                raise ValueError(f"Index mismatch: {key}; rebuild the index")
        concepts = sorted(catalog.concepts, key=lambda c: c.uri)
        if self.meta["uris"] != [c.uri for c in concepts] or self.meta["document_fingerprint"] != digest(
                [document_text(c) for c in concepts]):
            raise ValueError("Index concept order or document format mismatch")
        vector_path = path / "vectors.npy"
        if hashlib.sha256(vector_path.read_bytes()).hexdigest() != self.meta["vectors_sha256"]:
            raise ValueError("Index vector checksum mismatch")
        self.vectors = unit_vectors(np.load(vector_path, allow_pickle=False), len(concepts))
        if self.vectors.shape[1] != self.meta["dimensions"]:
            raise ValueError("Index dimension mismatch")
        self.client, self.cache, self.concepts = client, cache, concepts

    def search(self, skill, context="", k=3):
        vector = self.cache.get_many(self.client, [query_text(skill, context)])[0]
        if len(vector) != self.vectors.shape[1]:
            raise ValueError("Query/index dimension mismatch")
        scores = self.vectors @ vector
        order = np.argsort(-scores, kind="stable")[:k]
        return [(self.concepts[i], float(scores[i])) for i in order]
