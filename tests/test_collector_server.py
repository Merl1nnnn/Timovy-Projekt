"""Tests for the collector HTTP service: schedule, single run at a time, token, download (no network)."""

import io
import json
import tarfile
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import datetime, time, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from scraper import collector_server as cs

TOKEN = "t" * 32


def test_next_run_is_today_or_tomorrow() -> None:
    at = time(3, 30)
    assert cs.next_run(datetime(2026, 11, 27, 1, 0, tzinfo=timezone.utc), at) == \
        datetime(2026, 11, 27, 3, 30, tzinfo=timezone.utc)
    assert cs.next_run(datetime(2026, 11, 27, 3, 30, tzinfo=timezone.utc), at) == \
        datetime(2026, 11, 28, 3, 30, tzinfo=timezone.utc)


def test_overdue_after_20_hours_or_without_runs() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    assert cs.overdue([], now)
    assert not cs.overdue([{"started": (now - timedelta(hours=19)).isoformat()}], now)
    assert cs.overdue([{"started": (now - timedelta(hours=21)).isoformat()}], now)


def test_only_one_run_at_a_time_and_failure_is_recorded(tmp_path: Path) -> None:
    release = threading.Event()

    def slow() -> dict:
        release.wait(5)
        raise RuntimeError("HTTP 429")

    c = cs.Collector(tmp_path, run=slow, log=lambda *_: None)
    assert c.start() and c.running_since
    assert not c.start()  # still running
    release.set()
    assert c.thread is not None
    c.thread.join(5)
    assert c.running_since is None
    [run] = c.runs()
    assert run["error"] == "RuntimeError: HTTP 429" and run["started"]
    assert c.start()  # the lock is free again


def test_schedule_catches_up_a_missed_day(tmp_path: Path) -> None:
    started = threading.Event()
    c = cs.Collector(tmp_path, run=started.set, log=lambda *_: None)
    stop = threading.Event()
    t = threading.Thread(target=cs.schedule, args=(c, time(3, 30), stop), daemon=True)
    t.start()
    assert started.wait(5)  # no runs yet -> runs right away
    stop.set()
    t.join(5)
    assert not t.is_alive()


def test_schedule_does_not_rerun_after_a_recent_run(tmp_path: Path) -> None:
    (tmp_path / "profesia").mkdir()
    (tmp_path / "profesia" / "runs.jsonl").write_text(
        json.dumps({"started": datetime.now(timezone.utc).isoformat()}) + "\n", encoding="utf-8")
    calls: list[int] = []
    c = cs.Collector(tmp_path, run=lambda: calls.append(1), log=lambda *_: None)
    stop = threading.Event()
    stop.set()
    cs.schedule(c, time(3, 30), stop)
    assert calls == []


@pytest.fixture
def service(tmp_path: Path) -> Iterator[tuple[str, cs.Collector, threading.Event]]:
    raw = tmp_path / "raw"
    (raw / "profesia" / "history" / "1").mkdir(parents=True)
    (raw / "profesia" / "index.json").write_text(json.dumps([
        {"id": "1", "file": "profesia/1.html", "scraped_at": "x", "versions": 2, "removed_at": None},
        {"id": "2", "file": "profesia/2.html", "scraped_at": "x", "removed_at": "2026-11-20T00:00:00+00:00"},
    ]), encoding="utf-8")
    (raw / "profesia" / "1.html").write_text("<main>Python</main>", encoding="utf-8")
    (raw / "profesia" / "history" / "1" / "old.html").write_text("<main>Java</main>", encoding="utf-8")
    (raw / "profesia" / "index.json.tmp").write_text("half", encoding="utf-8")
    release = threading.Event()
    c = cs.Collector(raw, run=lambda: release.wait(5), log=lambda *_: None)
    server = ThreadingHTTPServer(("127.0.0.1", 0), cs.make_handler(c, TOKEN, time(3, 30)))
    server.RequestHandlerClass.log_message = lambda *a, **k: None  # type: ignore[method-assign]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", c, release
    release.set()
    server.shutdown()
    server.server_close()


def call(url: str, token: str | None = TOKEN, method: str = "GET") -> tuple[int, bytes]:
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_health_needs_no_token(service: tuple[str, cs.Collector, threading.Event]) -> None:
    base, _, _ = service
    assert call(base + "/health", token=None) == (200, b"ok\n")


@pytest.mark.parametrize("path,method", [("/status", "GET"), ("/download", "GET"), ("/collect", "POST")])
def test_data_needs_the_token(service: tuple[str, cs.Collector, threading.Event], path: str, method: str) -> None:
    base, c, _ = service
    assert call(base + path, token=None, method=method)[0] == 401
    assert call(base + path, token="wrong", method=method)[0] == 401
    assert c.running_since is None  # the refused POST did not start anything


def test_status_counts_postings(service: tuple[str, cs.Collector, threading.Event]) -> None:
    base, _, _ = service
    code, body = call(base + "/status")
    status = json.loads(body)
    assert code == 200
    assert (status["postings"], status["active"], status["removed"], status["with_old_versions"]) == (2, 1, 1, 1)
    assert status["next_run"].endswith("03:30:00+00:00") and status["running_since"] is None


def test_download_is_a_tar_of_raw_without_temp_files(service: tuple[str, cs.Collector, threading.Event]) -> None:
    base, _, _ = service
    code, body = call(base + "/download")
    assert code == 200
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
        names = set(tar.getnames())
        assert {"raw/profesia/index.json", "raw/profesia/1.html", "raw/profesia/history/1/old.html"} <= names
        assert "raw/profesia/index.json.tmp" not in names
        assert tar.extractfile("raw/profesia/1.html").read() == b"<main>Python</main>"  # type: ignore[union-attr]


def test_collect_starts_once(service: tuple[str, cs.Collector, threading.Event]) -> None:
    base, c, release = service
    assert call(base + "/collect", method="POST")[0] == 202
    assert call(base + "/collect", method="POST")[0] == 409
    assert json.loads(call(base + "/status")[1])["running_since"]
    release.set()


def test_unknown_path_is_404(service: tuple[str, cs.Collector, threading.Event]) -> None:
    base, _, _ = service
    assert call(base + "/index.json")[0] == 404


@pytest.mark.parametrize("env", [{}, {"COLLECTOR_TOKEN": "short"},
                                 {"COLLECTOR_TOKEN": TOKEN, "COLLECT_AT_UTC": "3h"},
                                 {"COLLECTOR_TOKEN": TOKEN, "COLLECT_DELAY": "0.5"}])
def test_refuses_to_start_with_bad_settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key in ("COLLECTOR_TOKEN", "COLLECT_AT_UTC", "COLLECT_DELAY"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(SystemExit):
        cs.main()
