import json

import httpx
import numpy as np
import pytest

from esco.data import Catalog, Concept, Labels
from esco.embeddings import EmbeddingCache, OllamaEmbedder, PROFILE, SemanticIndex, build_index, unit_vectors


def catalog():
    return Catalog(esco_version="synthetic-test", concepts=[
        Concept(uri=f"http://data.europa.eu/esco/skill/00000000-0000-0000-0000-{i:012}",
                labels={"en": Labels(preferred=name, description=name)})
        for i, name in [(1, "Python"), (2, "Java")]])


class FakeEmbedder:
    model = "fake"
    model_digest = "digest-v1"
    profile = PROFILE

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(texts)
        return np.array([[1., 0., 0.] if "Python" in text else [0., 1., 0.] for text in texts])

    def verify(self):
        pass


def test_cache_reuses_texts_and_separates_model_versions(tmp_path):
    cache = EmbeddingCache(tmp_path / "cache.sqlite3")
    client = FakeEmbedder()
    first = cache.get_many(client, ["Python", "Python", "Java"])
    assert len(client.calls) == 1 and len(client.calls[0]) == 2
    np.testing.assert_allclose(first, cache.get_many(client, ["Python", "Python", "Java"]))
    assert len(client.calls) == 1
    client.model_digest = "digest-v2"
    cache.get_many(client, ["Python"])
    assert len(client.calls) == 2
    cache.close()


def test_semantic_index_ranks_query_and_never_overwrites(tmp_path):
    data, client = catalog(), FakeEmbedder()
    cache = EmbeddingCache(tmp_path / "cache.sqlite3")
    out = tmp_path / "index"
    meta = build_index(data, out, client, cache, batch_size=1, log=lambda _: None)
    assert meta["dimensions"] == 3
    index = SemanticIndex(out, data, client, cache)
    results = index.search("Python", k=2)
    assert results[0][0].labels["en"].preferred == "Python"
    assert results[0][1] == pytest.approx(1)
    with pytest.raises(ValueError, match="exists"):
        build_index(data, out, client, cache)
    cache.close()


@pytest.mark.parametrize("field", ["model_digest", "profile"])
def test_index_rejects_incompatible_embedder(tmp_path, field):
    data, client = catalog(), FakeEmbedder()
    cache = EmbeddingCache(tmp_path / "cache.sqlite3")
    build_index(data, tmp_path / "index", client, cache, log=lambda _: None)
    setattr(client, field, "changed")
    with pytest.raises(ValueError, match=field):
        SemanticIndex(tmp_path / "index", data, client, cache)
    cache.close()


def test_index_rejects_changed_catalog_or_corrupt_vectors(tmp_path):
    data, client = catalog(), FakeEmbedder()
    cache = EmbeddingCache(tmp_path / "cache.sqlite3")
    out = tmp_path / "index"
    build_index(data, out, client, cache, log=lambda _: None)
    changed = data.model_copy(deep=True)
    changed.concepts[0].labels["en"].description = "changed"
    with pytest.raises(ValueError, match="catalog_fingerprint"):
        SemanticIndex(out, changed, client, cache)
    with (out / "vectors.npy").open("ab") as stream:
        stream.write(b"bad")
    with pytest.raises(ValueError, match="checksum"):
        SemanticIndex(out, data, client, cache)
    cache.close()


@pytest.mark.parametrize("values", [[[0, 0]], [[float("nan"), 1]], [[float("inf"), 1]], [1, 2], [[]]])
def test_rejects_invalid_vectors(values):
    with pytest.raises(ValueError):
        unit_vectors(values)


def test_ollama_records_digest_and_disables_silent_truncation():
    calls = []
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "embeddinggemma:latest", "digest": "abc"}]})
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"embeddings": [[3, 4]]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = OllamaEmbedder(http=http)
        vectors = client.embed(["text"])
        assert client.model_digest == "abc"
        assert calls[0]["truncate"] is False
        np.testing.assert_allclose(vectors, [[0.6, 0.8]])


def test_ollama_rejects_missing_and_changing_models():
    responses = [{"models": []}, {"models": [{"name": "embeddinggemma:latest", "digest": "v1"}]},
                 {"models": [{"name": "embeddinggemma:latest", "digest": "v2"}]}]
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=responses.pop(0)))) as http:
        with pytest.raises(ValueError, match="not installed"):
            OllamaEmbedder(http=http)
        client = OllamaEmbedder(http=http)
        with pytest.raises(ValueError, match="changed"):
            client.verify()
