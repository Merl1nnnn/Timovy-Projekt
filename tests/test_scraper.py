import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, sync_playwright

from mock_sites.generate import generate
from mock_sites.serve import start_server
from scraper.linkedin import LinkedInAdapter
from scraper.profesia import ProfesiaAdapter
from scraper.run import scrape_site


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict]]:
    tmp = tmp_path_factory.mktemp("mock")
    # 23 звичайні + складні вакансії (у т. ч. зламаний HTML) = 3 сторінки, остання неповна
    gt = generate(seed=7, n_per_site=23, sites_root=tmp, gt_path=tmp / "gt.json")
    return tmp, gt


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.mark.parametrize("adapter_cls", [ProfesiaAdapter, LinkedInAdapter])
def test_scrapes_all_details(adapter_cls, generated, browser: Browser, tmp_path: Path) -> None:
    sites_root, gt = generated
    name = adapter_cls().name
    server = start_server(sites_root / name / "site", port=0)
    try:
        adapter = adapter_cls(base_url=f"http://127.0.0.1:{server.server_address[1]}")
        index = scrape_site(browser, adapter, raw_dir=tmp_path)
    finally:
        server.shutdown()

    expected_ids = {r["id"] for r in gt if r["site"] == name}
    assert {r["id"] for r in index} == expected_ids  # усі вакансії з усіх сторінок, без дублів
    assert len(index) == len(expected_ids) > 23

    saved = json.loads((tmp_path / name / "index.json").read_text(encoding="utf-8"))
    assert saved == index
    first = next(r for r in gt if r["site"] == name)
    html = (tmp_path / name / f"{first['id']}.html").read_text(encoding="utf-8")
    assert first["company"] in html


def test_failed_scrape_keeps_previous_data(browser: Browser, tmp_path: Path) -> None:
    old = tmp_path / "profesia"
    old.mkdir()
    (old / "index.json").write_text("[]", encoding="utf-8")
    server = start_server(tmp_path / "empty", port=0)  # неіснуюча тека -> 404 на все
    port = server.server_address[1]
    server.shutdown()
    server.server_close()  # порт закрито: з'єднання буде відхилено
    with pytest.raises(Exception):
        scrape_site(browser, ProfesiaAdapter(base_url=f"http://127.0.0.1:{port}"), raw_dir=tmp_path)
    assert (old / "index.json").read_text(encoding="utf-8") == "[]"
    assert not (tmp_path / "profesia.tmp").exists()
