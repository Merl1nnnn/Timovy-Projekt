"""Serve SkillMiner with the bundled demo or the localhost mock sites."""

import argparse
import errno
import json
import logging
import os
import sys
import webbrowser
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
CACHE = ROOT / "data" / "db" / "dashboard"
DEMO_CACHE = ROOT / "data" / "db" / "dashboard-demo"
DEMO_IDENTITY = b'{"app":"SkillMiner","mode":"demo"}'


def collect(cache: Path) -> None:
    from dotenv import load_dotenv
    from playwright.sync_api import sync_playwright
    from parser.llm import OllamaClient
    from parser.run import read_jsonl, run, save_jobs
    from scraper.linkedin import LinkedInAdapter
    from scraper.profesia import ProfesiaAdapter
    from scraper.run import scrape_site
    from scripts.export_results import export

    raw = cache / "raw"
    parsed = cache / "parsed"
    urls: set[str] = set()
    with sync_playwright() as playwright:
        browser_path = os.getenv("SKILLMINER_BROWSER_PATH")
        browser = playwright.chromium.launch(executable_path=browser_path)
        try:
            for adapter in (ProfesiaAdapter(), LinkedInAdapter()):
                entries = scrape_site(browser, adapter, raw)
                if not entries:
                    raise RuntimeError(f"The local {adapter.name} mock returned no vacancy links")
                urls.update(entry["url"] for entry in entries)
        finally:
            browser.close()

    load_dotenv()
    client = OllamaClient("http://127.0.0.1:11434", os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b"))
    try:
        run(client, raw_dir=raw, out_dir=parsed)
    finally:
        client.http.close()

    current_file = cache / "jobs.json"
    previous_file = current_file if current_file.is_file() else FRONTEND / "data" / "jobs.json"
    published = json.loads(previous_file.read_text(encoding="utf-8"))
    previous = published["jobs"] if published["dataset_kind"] == "synthetic" else []
    candidates = [*previous, *read_jsonl(parsed / "jobs.jsonl")]
    active = {job["source_url"]: job for job in candidates if job.get("source_url") in urls}
    if not active:
        raise RuntimeError("No mock vacancies could be parsed")

    source = cache / "active.jsonl"
    save_jobs(source, active)
    update_file = cache / "next.json"
    updated = export(source, update_file, "synthetic")
    if updated["jobs"] == previous:
        update_file.unlink()
        return
    archive_previous(updated, published)
    update_file.write_text(json.dumps(updated, ensure_ascii=False), encoding="utf-8")
    update_file.replace(current_file)


def archive_previous(updated: dict, previous: dict) -> None:
    if previous["dataset_kind"] == "synthetic" and previous["jobs"]:
        updated["snapshot_history"] = [
            *previous.get("snapshot_history", []),
            {"generated_at": previous["generated_at"], "jobs": previous["jobs"]},
        ]


class Demo:
    def __init__(self, source: Path, cache: Path):
        self.source = source
        self.cache = cache
        self.lock = Lock()

    def snapshot(self) -> dict:
        with self.lock:
            previous = json.loads(self.cache.read_text(encoding="utf-8")) if self.cache.is_file() else None
            try:
                source = json.loads(self.source.read_text(encoding="utf-8"))
                if source.get("dataset_kind") != "synthetic" or not isinstance(source.get("jobs"), list):
                    raise ValueError("Expected a synthetic job snapshot")
            except (OSError, ValueError, AttributeError):
                if previous is None:
                    raise
                return previous

            if previous is not None:
                if source["jobs"] == previous["jobs"]:
                    return previous
                source["generated_at"] = datetime.now(timezone.utc).isoformat()
                archive_previous(source, previous)
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache.with_suffix(".tmp")
            temporary.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.cache)
            return source


class Refresh:
    def __init__(self, cache: Path, interval: int):
        self.cache = cache
        self.interval = interval
        self.lock = Lock()
        self.running = False
        self.last_finished: float | None = None
        self.result = "idle"

    def status(self) -> str:
        with self.lock:
            return "running" if self.running else self.result

    def request(self) -> str:
        with self.lock:
            if self.running:
                return "running"
            if self.last_finished is not None and monotonic() - self.last_finished < self.interval:
                return self.result
            self.running = True
            Thread(target=self._work, daemon=True).start()
            return "running"

    def _work(self) -> None:
        result = "ready"
        try:
            collect(self.cache)
        except Exception:
            logging.exception("Mock source refresh failed")
            result = "failed"
        finally:
            with self.lock:
                self.result = result
                self.last_finished = monotonic()
                self.running = False


def serve(port: int, refresh_after: int, *, demo: bool = False, open_browser: bool = False) -> None:
    refresh = Refresh(CACHE, refresh_after)
    demo_source = Demo(FRONTEND / "data" / "jobs.json", DEMO_CACHE / "jobs.json") if demo else None

    class DashboardServer(ThreadingHTTPServer):
        # Windows can let two sockets using SO_REUSEADDR bind to the same address.
        allow_reuse_address = sys.platform != "win32"

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(FRONTEND), **kwargs)

        def end_headers(self) -> None:
            if urlsplit(self.path).path == "/data/jobs.json":
                if not demo_source:
                    self.send_header("X-SkillMiner-Refresh", "mock")
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_json(self, payload: bytes) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def send_status(self, status: str) -> None:
            self.send_json(json.dumps({"status": status}).encode("utf-8"))

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/launcher" and demo_source:
                self.send_json(DEMO_IDENTITY)
                return
            if path == "/api/refresh":
                self.send_status(refresh.status())
                return
            snapshot = CACHE / "jobs.json"
            if path == "/data/jobs.json":
                if demo_source:
                    try:
                        data = demo_source.snapshot()
                    except (OSError, ValueError, AttributeError):
                        self.send_error(503, "A synthetic snapshot is required")
                        return
                    self.send_json(json.dumps(data, ensure_ascii=False).encode("utf-8"))
                    return
                source = snapshot if snapshot.is_file() else FRONTEND / "data" / "jobs.json"
                data = json.loads(source.read_text(encoding="utf-8"))
                if data["dataset_kind"] == "synthetic":
                    self.send_json(json.dumps(data, ensure_ascii=False).encode("utf-8"))
                    return
                self.send_error(503, "A synthetic snapshot is required")
                return
            super().do_GET()

        def do_POST(self) -> None:
            if demo_source or urlsplit(self.path).path != "/api/refresh":
                self.send_error(404)
                return
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host or self.headers.get("Origin") != f"http://{host}":
                self.send_error(403)
                return
            self.send_status(refresh.request())

    candidates = (port, port + 1, 0) if open_browser and 0 < port < 65535 else (port,)
    for candidate in candidates:
        if demo and open_browser and candidate:
            url = f"http://127.0.0.1:{candidate}/"
            try:
                with urlopen(url + "api/launcher", timeout=0.5) as response:
                    existing_demo = response.read(len(DEMO_IDENTITY) + 1) == DEMO_IDENTITY
            except OSError:
                existing_demo = False
            if existing_demo:
                webbrowser.open(url)
                return
        try:
            server = DashboardServer(("127.0.0.1", candidate), Handler)
            break
        except OSError as error:
            if candidate == candidates[-1] or error.errno not in (errno.EADDRINUSE, 10048):
                raise
    with server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"SkillMiner: {url}", flush=True)
        if open_browser:
            Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--refresh-after", type=int, default=300, help="Seconds between mock refreshes")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--mock-sites", action="store_true",
                         help="Collect from the local mock sites using the parser instead of the bundled demo")
    sources.add_argument("--demo", dest="mock_sites", action="store_false", help=argparse.SUPPRESS)
    parser.set_defaults(mock_sites=False)
    parser.add_argument("--open", action=argparse.BooleanOptionalAction, default=True,
                        help="Open the dashboard in the default browser")
    args = parser.parse_args()
    serve(args.port, args.refresh_after, demo=not args.mock_sites, open_browser=args.open)
