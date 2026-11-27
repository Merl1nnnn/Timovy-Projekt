"""HTTP service around the daily collector, meant for a container (TUKE Coolify).

- Runs scraper.profesia_daily.collect once a day at COLLECT_AT_UTC (default 03:30 UTC) in a background thread,
  and right after start when the last run began more than 20 h ago, so a redeploy or a stopped
  container does not skip a day. A failed run is written to runs.jsonl with "error" and also counts.
- GET  /health             -> "ok", no token (container health check)
- GET  /status   (token)   -> JSON: posting counts, next run, the last runs
- GET  /download (token)   -> data/real/raw as .tar.gz
- POST /collect  (token)   -> starts a run now (409 while one is running)

The token is COLLECTOR_TOKEN, sent as "Authorization: Bearer <token>". Without it the service does not start:
the repository is public, the collected postings must not be.
Other settings: COLLECT_ENABLED (default 1; 0 = no daily schedule, POST /collect still works),
COLLECT_DELAY (default 3 s), PORT (default 8000).

Usage:
    COLLECTOR_TOKEN=... uv run python -m scraper.collector_server
"""

import hmac
import json
import os
import sys
import tarfile
import threading
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from scraper import profesia_daily
from scraper.profesia_live import REAL_RAW_DIR, SITE, PoliteClient, _load_index

OVERDUE = timedelta(hours=20)
LAST_RUNS = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_run(now: datetime, at: time) -> datetime:
    """The next moment `at` (UTC) strictly after `now`."""
    candidate = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(days=1)


def overdue(runs: list[dict[str, Any]], now: datetime) -> bool:
    if not runs:
        return True
    return now - datetime.fromisoformat(runs[-1]["started"]) > OVERDUE


class Collector:
    """At most one collection at a time, in a background thread."""

    def __init__(self, raw_dir: Path = REAL_RAW_DIR, delay: float = 3.0,
                 run: Callable[[], Any] | None = None, log: Any = print) -> None:
        self.raw_dir = raw_dir
        self.log = log
        self._run = run or (lambda: profesia_daily.collect(PoliteClient(delay=delay), raw_dir=raw_dir, log=log))
        self._lock = threading.Lock()
        self.running_since: str | None = None
        self.thread: threading.Thread | None = None

    @property
    def runs_path(self) -> Path:
        return self.raw_dir / SITE / "runs.jsonl"

    def runs(self) -> list[dict[str, Any]]:
        if not self.runs_path.exists():
            return []
        out = []
        for line in self.runs_path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:  # a line cut off by a killed container
                continue
        return out

    def start(self) -> bool:
        """Starts a run; False if one is already running."""
        if not self._lock.acquire(blocking=False):
            return False
        self.running_since = _now()
        self.thread = threading.Thread(target=self._work, name="collect", daemon=True)
        self.thread.start()
        return True

    def _work(self) -> None:
        started = self.running_since or _now()
        self.log(f"збір почався {started}")
        try:
            run = self._run()
            self.log(f"збір завершено: {json.dumps(run, ensure_ascii=False)}")
        except Exception as e:  # noqa: BLE001 - a failed day must not stop the service
            error = f"{type(e).__name__}: {e}"
            self.log(f"збір зупинено: {error}")
            self.runs_path.parent.mkdir(parents=True, exist_ok=True)
            with self.runs_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"started": started, "finished": _now(), "error": error}, ensure_ascii=False) + "\n")
        finally:
            self.running_since = None
            self._lock.release()

    def status(self) -> dict[str, Any]:
        index = _load_index(self.raw_dir / SITE / "index.json")
        return {"running_since": self.running_since,
                "postings": len(index),
                "active": sum(e.get("removed_at") is None for e in index),
                "removed": sum(e.get("removed_at") is not None for e in index),
                "with_old_versions": sum(e.get("versions", 1) > 1 for e in index),
                "last_runs": self.runs()[-LAST_RUNS:]}


def schedule(collector: Collector, at: time, stop: threading.Event) -> None:
    """Catch up a missed day right away, then run every day at `at`."""
    if overdue(collector.runs(), datetime.now(timezone.utc)):
        collector.start()
    while not stop.is_set():
        now = datetime.now(timezone.utc)
        if stop.wait((next_run(now, at) - now).total_seconds()):
            return
        if not collector.start():
            collector.log("попередній збір ще триває, пропускаємо")


def make_handler(collector: Collector, token: str, at: time | None) -> type[BaseHTTPRequestHandler]:
    expected = f"Bearer {token}".encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "SkillMinerCollector/0.1"

        def _authorized(self) -> bool:
            if hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected):
                return True
            self._json(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
            return False

        def _json(self, code: int, body: Any, headers: dict[str, str] | None = None) -> None:
            data = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            path = self.path.split("?", 1)[0]
            if path == "/health":
                data = b"ok\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif path == "/status":
                if self._authorized():
                    body = collector.status()
                    body["next_run"] = next_run(datetime.now(timezone.utc), at).isoformat() if at else None
                    self._json(200, body)
            elif path == "/download":
                if self._authorized():
                    self._download()
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            if self.path.split("?", 1)[0] != "/collect":
                self._json(404, {"error": "not found"})
            elif self._authorized():
                if collector.start():
                    self._json(202, {"started": collector.running_since})
                else:
                    self._json(409, {"error": "a collection is already running",
                                     "running_since": collector.running_since})

        def _download(self) -> None:
            if not collector.raw_dir.exists():
                self._json(404, {"error": "nothing collected yet"})
                return
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
            self.send_response(200)
            self.send_header("Content-Type", "application/gzip")
            self.send_header("Content-Disposition", f'attachment; filename="skillminer-raw-{stamp}.tar.gz"')
            self.end_headers()  # no Content-Length: the archive is streamed, the connection closes at the end
            with tarfile.open(fileobj=self.wfile, mode="w|gz") as tar:
                tar.add(collector.raw_dir, arcname="raw",
                        filter=lambda info: None if info.name.endswith(".tmp") else info)

    return Handler


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    token = os.environ.get("COLLECTOR_TOKEN", "")
    if len(token) < 16:
        raise SystemExit("COLLECTOR_TOKEN не задано або коротший за 16 символів: дані не можна віддавати без токена")
    try:
        hour, minute = map(int, os.environ.get("COLLECT_AT_UTC", "03:30").split(":"))
        at = time(hour, minute)
    except ValueError:
        raise SystemExit("COLLECT_AT_UTC має бути у форматі ГГ:ХХ, наприклад 03:30")
    delay = float(os.environ.get("COLLECT_DELAY", "3"))
    if delay < 1:
        raise SystemExit("COLLECT_DELAY має бути не менше 1 секунди")
    enabled = os.environ.get("COLLECT_ENABLED", "1") not in ("0", "false", "no")
    port = int(os.environ.get("PORT", "8000"))

    collector = Collector(REAL_RAW_DIR, delay=delay)
    if enabled:
        threading.Thread(target=schedule, args=(collector, at, threading.Event()), name="schedule",
                         daemon=True).start()
    print(f"SkillMiner collector: порт {port}, збір {'щодня о ' + at.strftime('%H:%M') + ' UTC' if enabled else 'вимкнено'}",
          flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), make_handler(collector, token, at if enabled else None)).serve_forever()


if __name__ == "__main__":
    main()
