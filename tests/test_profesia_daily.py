"""Tests for the daily collector on a synthetic site (same structure as Profesia, no network)."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from scraper import profesia_daily as pd
from scraper import profesia_live as pl
from tests.test_profesia_live import detail_page, list_page


class Site:
    """A category list of `ids` split into pages of 3."""

    def __init__(self, ids: list[int], texts: dict[int, str] | None = None, gone: set[int] | None = None) -> None:
        self.ids = ids
        self.texts = texts or {}
        self.gone = gone or set()
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        if "/praca/informacne-technologie/" in url:
            num = int(url.rsplit("page_num=", 1)[1]) if "page_num=" in url else 1
            chunk = self.ids[(num - 1) * 3:num * 3]
            # Like the real site: every page links "next", even an empty one (back to page 2).
            return httpx.Response(200, text=list_page(chunk, next_num=num + 1 if chunk else 2))
        job = int(url.rsplit("/O", 1)[1])
        if job in self.gone:
            return httpx.Response(404)
        page = detail_page(job)
        if job in self.texts:
            page = page.replace("Python, Django.", self.texts[job])
        return httpx.Response(200, text=page)


def client(site: Site) -> pl.PoliteClient:
    return pl.PoliteClient(delay=0, http=httpx.Client(transport=httpx.MockTransport(site)), check_robots=False)


def run(site: Site, raw: Path, **kw: object) -> dict:
    return pd.collect(client(site), raw_dir=raw, log=lambda *_: None, **kw)  # type: ignore[arg-type]


def index(raw: Path) -> dict[str, dict]:
    return {e["id"]: e for e in json.loads((raw / "profesia" / "index.json").read_text(encoding="utf-8"))}


def age(raw: Path, days: float) -> None:
    """Pretend every posting was last checked `days` ago."""
    path = raw / "profesia" / "index.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    for e in entries:
        e["checked_at"] = old
    path.write_text(json.dumps(entries), encoding="utf-8")


def test_empty_page_past_the_end_stops_the_walk() -> None:
    site = Site([1, 2, 3, 4, 5, 6])  # two full pages: page 3 is empty but links to page 2
    seen, complete = pd.crawl_list(client(site), log=lambda *_: None)
    assert list(seen) == ["1", "2", "3", "4", "5", "6"] and complete
    assert sum("informacne-technologie" in u for u in site.requests) == 3


def test_first_run_downloads_everything_and_second_run_nothing(tmp_path: Path) -> None:
    stats = run(Site([1, 2, 3, 4]), tmp_path)
    assert stats["new"] == 4 and stats["list_complete"] and stats["active"] == 4
    assert (tmp_path / "profesia" / "4.html").exists()
    site = Site([1, 2, 3, 4])
    stats = run(site, tmp_path)
    assert stats.get("new", 0) == 0
    assert not any("/O" in u for u in site.requests)  # checked less than refresh_days ago
    lines = (tmp_path / "profesia" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_changed_posting_is_updated_and_old_version_kept(tmp_path: Path) -> None:
    run(Site([1, 2]), tmp_path)
    first = index(tmp_path)["1"]["scraped_at"]
    age(tmp_path, 8)
    stats = run(Site([1, 2], texts={1: "Python, FastAPI."}), tmp_path)
    assert stats["updated"] == 1 and stats["unchanged"] == 1
    entry = index(tmp_path)["1"]
    assert entry["versions"] == 2 and entry["updated_at"] and entry["first_seen"] == first
    assert "FastAPI" in (tmp_path / "profesia" / "1.html").read_text(encoding="utf-8")
    [old] = (tmp_path / "profesia" / "history" / "1").iterdir()
    assert "Django" in old.read_text(encoding="utf-8")
    assert index(tmp_path)["2"]["versions"] == 1


def test_posting_removed_after_two_missed_walks_and_can_return(tmp_path: Path) -> None:
    run(Site([1, 2]), tmp_path)
    run(Site([1]), tmp_path)
    assert index(tmp_path)["2"]["removed_at"] is None and index(tmp_path)["2"]["missed"] == 1
    stats = run(Site([1]), tmp_path)
    assert stats["removed"] == 1 and index(tmp_path)["2"]["removed_at"]
    stats = run(Site([1, 2]), tmp_path)
    assert stats["returned"] == 1 and index(tmp_path)["2"]["removed_at"] is None


def test_incomplete_walk_does_not_mark_postings_missing(tmp_path: Path) -> None:
    run(Site([1, 2, 3, 4]), tmp_path)
    for _ in range(3):
        stats = run(Site([1, 2, 3, 4]), tmp_path, max_pages=1)
        assert not stats["list_complete"]
    assert all(e["removed_at"] is None and e["missed"] == 0 for e in index(tmp_path).values())


def test_posting_answering_404_is_removed_and_file_kept(tmp_path: Path) -> None:
    run(Site([1]), tmp_path)
    age(tmp_path, 8)
    stats = run(Site([1], gone={1}), tmp_path)
    assert stats["removed"] == 1 and index(tmp_path)["1"]["removed_at"]
    assert "Python developer 1" in (tmp_path / "profesia" / "1.html").read_text(encoding="utf-8")


def test_entries_from_the_old_scraper_are_kept(tmp_path: Path) -> None:
    pl.scrape(client(Site([1, 2])), raw_dir=tmp_path, limit=2, log=lambda *_: None)
    before = index(tmp_path)["1"]
    stats = run(Site([1, 2, 3]), tmp_path)
    assert stats["new"] == 1
    entry = index(tmp_path)["1"]
    assert entry["first_seen"] == before["scraped_at"] and entry["file"] == before["file"]


@pytest.mark.parametrize("status", [403, 429])
def test_collect_stops_when_blocked(tmp_path: Path, status: int) -> None:
    blocked = pl.PoliteClient(delay=0, check_robots=False,
                              http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status))))
    with pytest.raises(pl.Blocked):
        pd.collect(blocked, raw_dir=tmp_path, log=lambda *_: None)
