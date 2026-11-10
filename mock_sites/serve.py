"""Роздає обидва статичні мок-сайти: Profesia на :8001, LinkedIn на :8002.

Запуск: uv run python -m mock_sites.serve   (Ctrl+C — зупинити)
"""

import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mock_sites.generate import MOCK_ROOT, SITES


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # без логу кожного запиту
        pass


def start_server(site_dir: Path, port: int) -> ThreadingHTTPServer:
    """Запускає сервер у фоновому потоці. port=0 — вільний порт (для тестів)."""
    handler = partial(QuietHandler, directory=str(site_dir))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    servers = []
    for site, cfg in SITES.items():
        site_dir = MOCK_ROOT / site / "site"
        if not site_dir.exists():
            raise SystemExit(f"Немає {site_dir}. Спершу: uv run python -m mock_sites.generate")
        servers.append(start_server(site_dir, cfg.port))
        print(f"{site}: http://localhost:{cfg.port}/")
    print("Ctrl+C — зупинити")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        for s in servers:
            s.shutdown()


if __name__ == "__main__":
    main()
