import csv
import json
from pathlib import Path

import httpx
import pytest

from esco.data import Catalog, Concept, Labels, fetch_catalog, from_api, import_csv, load_catalog, write_json

URI1 = "http://data.europa.eu/esco/skill/00000000-0000-0000-0000-000000000001"
URI2 = "http://data.europa.eu/esco/skill/00000000-0000-0000-0000-000000000002"


def concept(uri=URI1, name="Python"):
    return Concept(uri=uri, labels={"en": Labels(preferred=name, alternative=["Python programming"], description="A language")})


def page(uri=URI1, offset=0, total=1):
    return {"offset": offset, "total": total, "count": 1, "concepts": [{"uri": uri}],
            "_embedded": {uri: {"uri": uri, "className": "Skill", "status": "released",
                                "preferredLabel": {"en": "Python", "sk": "Python", "de": "Python"},
                                "alternativeLabel": {"en": ["Python programming"]},
                                "description": {"en": {"literal": "A language"}},
                                "_links": {"hasSkillType": [{"uri": "knowledge"}]}}}}


def test_api_preserves_requested_labels_and_stable_uri():
    c = from_api(page(), ["en", "sk"])[0]
    assert c.uri == URI1
    assert set(c.labels) == {"en", "sk"}
    assert c.labels["en"].alternative == ["Python programming"]
    assert c.skill_type == "knowledge"


def test_catalog_fingerprint_is_order_independent():
    a, b = concept(), concept(URI2, "Java")
    first = Catalog(esco_version="test", concepts=[a, b])
    second = Catalog(esco_version="test", concepts=[b, a], provenance={"time": "later"})
    assert first.fingerprint == second.fingerprint
    second.esco_version = "other"
    assert first.fingerprint != second.fingerprint


def test_rejects_empty_catalog_duplicate_uri_and_invalid_uri():
    with pytest.raises(ValueError):
        Catalog(esco_version="test", concepts=[])
    with pytest.raises(ValueError, match="Duplicate"):
        Catalog(esco_version="test", concepts=[concept(), concept()])
    with pytest.raises(ValueError):
        concept("https://example.org/not-esco")


def test_download_paginates_by_page_number_and_resumes(tmp_path):
    calls = []
    def handler(request):
        offset = int(request.url.params["offset"])
        calls.append(offset)
        assert request.url.params["selectedVersion"] == "v1.2.0"
        return httpx.Response(200, json=page([URI1, URI2][offset], offset, 2))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = tmp_path / "catalog.json"
        catalog = fetch_catalog(out, page_size=1, http=client, log=lambda _: None)
        assert calls == [0, 1]
        assert len(catalog.concepts) == 2
        assert catalog.provenance["complete"]
        assert load_catalog(out).fingerprint == catalog.fingerprint
        with pytest.raises(ValueError, match="exists"):
            fetch_catalog(out, http=client)
        calls.clear()
        fetch_catalog(tmp_path / "second.json", page_size=1, http=client, log=lambda _: None)
        assert calls == []


def test_download_rejects_missing_embedded_resource(tmp_path):
    payload = page()
    payload["_embedded"] = {}
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
        with pytest.raises(KeyError):
            fetch_catalog(tmp_path / "catalog.json", http=client)
    assert not (tmp_path / "catalog.json").exists()


def test_download_does_not_publish_incomplete_catalog(tmp_path):
    def handler(request):
        offset = int(request.url.params["offset"])
        payload = page(URI1, 0, 2) if offset == 0 else {"offset": 1, "total": 2, "count": 0, "concepts": [], "_embedded": {}}
        return httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="pagination"):
            fetch_catalog(tmp_path / "catalog.json", page_size=1, http=client, log=lambda _: None)
    assert not (tmp_path / "catalog.json").exists()


def write_csv(path: Path, label):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["conceptUri", "preferredLabel", "altLabels", "description"])
        writer.writeheader()
        writer.writerow({"conceptUri": URI1, "preferredLabel": label,
                         "altLabels": "alias one\nalias two", "description": "Description"})


def test_csv_import_merges_languages_and_preserves_input(tmp_path):
    en, sk = tmp_path / "skills_en.csv", tmp_path / "skills_sk.csv"
    write_csv(en, "English label")
    write_csv(sk, "Slovak label")
    original = en.read_bytes()
    catalog = import_csv({"en": en, "sk": sk}, "v1.2.1", tmp_path / "catalog.json")
    assert len(catalog.concepts) == 1
    assert set(catalog.concepts[0].labels) == {"en", "sk"}
    assert catalog.concepts[0].labels["en"].alternative == ["alias one", "alias two"]
    assert en.read_bytes() == original


def test_json_outputs_never_overwrite_inputs(tmp_path):
    path = tmp_path / "source.json"
    write_json(path, {"original": True})
    with pytest.raises(FileExistsError):
        write_json(path, {})
    assert json.loads(path.read_text()) == {"original": True}


def test_accepts_official_isced_knowledge_concepts():
    c = concept("http://data.europa.eu/esco/isced-f/0613", "Software development")
    assert c.uri.endswith("/0613")
