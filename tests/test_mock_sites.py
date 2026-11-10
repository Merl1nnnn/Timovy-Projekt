import json
from pathlib import Path

import httpx

from mock_sites import vocab
from mock_sites.generate import SITES, detail_path, generate, list_path
from mock_sites.serve import start_server


def _gen(tmp: Path, seed: int = 42) -> list[dict]:
    return generate(seed=seed, n_per_site=45, sites_root=tmp / "sites", gt_path=tmp / "gt.json")


def test_counts_and_files(tmp_path: Path) -> None:
    gt = _gen(tmp_path)
    for site in SITES:
        rows = [r for r in gt if r["site"] == site]
        assert len([r for r in rows if not r["edge_case"]]) == 45
        site_dir = tmp_path / "sites" / site / "site"
        for r in rows:
            assert (site_dir / detail_path(site, r["id"]).lstrip("/")).exists()
        for page in range(1, (len(rows) + 9) // 10 + 1):  # по 10 на сторінці
            assert (site_dir / list_path(site, page).lstrip("/")).exists()
    assert len({r["source_url"] for r in gt}) == len(gt)  # ID складних вакансій не перетинаються з основними


def test_edge_cases_are_appended_without_changing_main_jobs(tmp_path: Path) -> None:
    plain = generate(seed=42, sites_root=tmp_path / "a", gt_path=tmp_path / "a.json", edge_cases=False)
    full = _gen(tmp_path / "b")
    main = [{k: v for k, v in r.items() if k != "edge_case"} for r in full if not r["edge_case"]]
    assert main == [{k: v for k, v in r.items() if k != "edge_case"} for r in plain]
    edge = [r for r in full if r["edge_case"]]
    assert {r["site"] for r in edge} == {"profesia", "linkedin"}
    assert all(":" in r["edge_case"] for r in edge)  # "<назва>: <опис пастки>"
    broken = next(r for r in edge if r["edge_case"].startswith("broken_html"))
    html = (tmp_path / "b/sites/profesia/site" / detail_path("profesia", broken["id"]).lstrip("/")).read_text(encoding="utf-8")
    assert "<table>" in html and "</td>" not in html  # справді зламаний HTML, не шаблон


def test_deterministic(tmp_path: Path) -> None:
    _gen(tmp_path / "a")
    _gen(tmp_path / "b")
    assert (tmp_path / "a" / "gt.json").read_bytes() == (tmp_path / "b" / "gt.json").read_bytes()
    gt = json.loads((tmp_path / "a" / "gt.json").read_text(encoding="utf-8"))
    f = detail_path("profesia", gt[0]["id"]).lstrip("/")
    assert (tmp_path / "a/sites/profesia/site" / f).read_bytes() == (tmp_path / "b/sites/profesia/site" / f).read_bytes()


def test_data_is_varied_and_dirty(tmp_path: Path) -> None:
    gt = [r for r in _gen(tmp_path) if not r["edge_case"]]  # складні вакансії навмисно нетипові
    assert {r["language"] for r in gt} == {"sk", "en"}
    assert {r["seniority"] for r in gt} == {"junior", "medior", "senior", "lead"}
    assert {r["location"] for r in gt} == {"Bratislava", "Košice", "Žilina", None}
    assert any(r["salary_min"] is None for r in gt) and any(r["salary_min"] for r in gt)
    for r in gt:
        assert set(r["technologies"]) <= set(r["required_skills"]) | set(r["nice_to_have_skills"])

    # У сирих HTML мають траплятися аліаси, а не лише канонічні назви.
    html = " ".join(p.read_text(encoding="utf-8") for p in (tmp_path / "sites").rglob("*.html"))
    aliases = {a for names in vocab.ALIASES.values() for a in names}
    assert sum(1 for a in aliases if f">{a}<" in html or f" {a}," in html or f" {a} " in html) >= 10


def test_server_serves_pages(tmp_path: Path) -> None:
    gt = _gen(tmp_path)
    server = start_server(tmp_path / "sites" / "linkedin" / "site", port=0)
    try:
        port = server.server_address[1]
        r = httpx.get(f"http://127.0.0.1:{port}{list_path('linkedin', 2)}")
        assert r.status_code == 200 and "jobs-search__results-list" in r.text
        job = next(x for x in gt if x["site"] == "linkedin")
        r = httpx.get(f"http://127.0.0.1:{port}{detail_path('linkedin', job['id'])}")
        assert r.status_code == 200 and job["company"] in r.content.decode("utf-8")
    finally:
        server.shutdown()
