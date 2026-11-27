"""Daily collection from the REAL Profesia.sk, meant for a server (cron / systemd timer).

Collection only, no parsing: the pages are stored for `parser.run --real` to process later.
Uses the same polite client, contact removal and data directory as scraper.profesia_live,
which keeps working as before.

One run:
1. walks the whole category list and remembers which postings are still listed (last_seen);
2. downloads new postings;
3. re-downloads listed postings not checked for --refresh-days days; if the visible text changed,
   the previous file is moved to history/<id>/<scraped_at>.html and the new one takes its place;
4. a posting missing from two complete list walks in a row (or answering 404/410) gets removed_at;
5. appends a line with the run statistics to runs.jsonl.

Extra index.json fields: first_seen, last_seen, checked_at, updated_at, removed_at, missed, versions.
The parser ignores them; scraped_at still says when the current file was downloaded.

Usage:
    uv run python -m scraper.profesia_daily
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

from parser.html_text import html_to_text
from scraper.profesia_live import (BASE_URL, REAL_RAW_DIR, SITE, START_PATH, Blocked, PoliteClient,
                                   _load_index, _save_index, detail_links, extract_detail, job_id, next_page)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text_key(page: str) -> bytes:
    # Sorted lines: Profesia may list the same skills in a different order ("SQL - Pokročilý" moved by a line).
    lines = sorted(line.strip() for line in html_to_text(page).splitlines() if line.strip())
    return sha256("\n".join(lines).encode("utf-8")).digest()


def same_text(a: str, b: str) -> bool:
    """Markup-only changes and reordered lines do not count as an update. Both sides are hashed now,
    so a later change to html_to_text cannot turn every stored posting into a false update."""
    return _text_key(a) == _text_key(b)


def crawl_list(client: PoliteClient, max_pages: int = 200, log: Any = print) -> tuple[dict[str, str], bool]:
    """All postings of the category {id: url} in list order, and whether the end of the list was reached."""
    seen: dict[str, str] = {}
    url: str | None = BASE_URL + START_PATH
    pages = 0
    while url and pages < max_pages:
        pages += 1
        list_html = client.get(url)
        links = detail_links(list_html)
        if not links:  # past the end: the page is empty, but "next" still points to page 2
            url = None
            break
        for link in links:
            seen.setdefault(job_id(link), link)
        url = next_page(list_html)
    log(f"сторінок списку: {pages}, вакансій у списку: {len(seen)}")
    return seen, url is None


def _upgrade(entry: dict[str, Any]) -> None:
    """Entries written by scraper.profesia_live get the extra fields from scraped_at."""
    entry.setdefault("first_seen", entry["scraped_at"])
    entry.setdefault("last_seen", entry["scraped_at"])
    entry.setdefault("checked_at", entry["scraped_at"])
    entry.setdefault("updated_at", None)
    entry.setdefault("removed_at", None)
    entry.setdefault("missed", 0)
    entry.setdefault("versions", 1)


def collect(client: PoliteClient, raw_dir: Path = REAL_RAW_DIR, refresh_days: float = 7.0,
            max_new: int = 2000, max_refresh: int = 300, max_pages: int = 200,
            log: Any = print) -> dict[str, Any]:
    """One daily run. Returns the run statistics (also appended to runs.jsonl).

    The index is saved after every posting, so an interrupted run keeps what it already did.
    """
    out_dir = raw_dir / SITE
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.json"
    index = _load_index(index_path)
    skipped = _load_index(out_dir / "skipped.json")
    skipped_urls = {e["url"] for e in skipped}
    for entry in index:
        _upgrade(entry)
    by_id = {e["id"]: e for e in index}
    started = _now()
    stats: Counter[str] = Counter()

    def save() -> None:
        _save_index(index_path, index)

    seen, complete = crawl_list(client, max_pages=max_pages, log=log)
    stats["listed"] = len(seen)
    for jid, url in seen.items():
        entry = by_id.get(jid)
        if entry is None:
            continue
        entry.update(last_seen=started, missed=0, url=url)
        if entry["removed_at"]:
            entry["removed_at"] = None
            stats["returned"] += 1
    if complete:  # an interrupted walk proves nothing about missing postings
        for entry in index:
            if entry["id"] not in seen and entry["removed_at"] is None:
                entry["missed"] += 1
                if entry["missed"] >= 2:  # a posting bumped to the top during the walk can slip past it once
                    entry["removed_at"] = started
                    stats["removed"] += 1
    save()

    new = [(jid, url) for jid, url in seen.items() if jid not in by_id and url not in skipped_urls]
    for jid, url in new[:max_new]:
        content = extract_detail(client.get(url))
        if content is None:  # non-standard template: remember it so it is not downloaded again
            skipped.append({"url": url, "reason": "no <main id=detail>"})
            _save_index(out_dir / "skipped.json", skipped)
            stats["skipped"] += 1
            continue
        (out_dir / f"{jid}.html").write_text(content, encoding="utf-8")
        now = _now()
        entry = {"site": SITE, "id": jid, "url": url, "file": f"{SITE}/{jid}.html", "scraped_at": now,
                 "first_seen": now, "last_seen": started, "checked_at": now, "updated_at": None,
                 "removed_at": None, "missed": 0, "versions": 1}
        index.append(entry)
        by_id[jid] = entry
        save()
        stats["new"] += 1
        log(f"  нова [{stats['new']}] {url}")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=refresh_days)).isoformat(timespec="seconds")
    due = sorted((e for e in index if e["removed_at"] is None and e["id"] in seen and e["checked_at"] < cutoff),
                 key=lambda e: e["checked_at"])
    for entry in due[:max_refresh]:
        try:
            content = extract_detail(client.get(entry["url"]))
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in (404, 410):
                raise
            entry["removed_at"] = _now()
            save()
            stats["removed"] += 1
            continue
        now = _now()
        entry["checked_at"] = now
        path = out_dir / entry["file"].split("/", 1)[1]
        if content is None:  # the template changed: keep the old file
            pass
        elif path.exists() and same_text(path.read_text(encoding="utf-8"), content):
            stats["unchanged"] += 1
        else:
            if path.exists():
                history = out_dir / "history" / entry["id"]
                history.mkdir(parents=True, exist_ok=True)
                path.replace(history / f"{entry['scraped_at'].replace(':', '-')}.html")
            path.write_text(content, encoding="utf-8")
            entry.update(scraped_at=now, updated_at=now, versions=entry["versions"] + 1)
            stats["updated"] += 1
            log(f"  оновлена {entry['url']}")
        save()

    run = {"started": started, "finished": _now(), "list_complete": complete,
           "active": sum(e["removed_at"] is None for e in index), "total": len(index), **stats}
    with (out_dir / "runs.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(run, ensure_ascii=False) + "\n")
    return run


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description="Щоденний збір IT-вакансій з Profesia.sk у data/real/raw/ (без парсингу).")
    ap.add_argument("--refresh-days", type=float, default=7.0,
                    help="перевіряти відому вакансію на зміни не частіше, ніж раз на N днів (default 7)")
    ap.add_argument("--max-new", type=int, default=2000, help="максимум нових вакансій за запуск (default 2000)")
    ap.add_argument("--max-refresh", type=int, default=300, help="максимум перевірок старих за запуск (default 300)")
    ap.add_argument("--max-pages", type=int, default=200, help="максимум сторінок списку (default 200)")
    ap.add_argument("--delay", type=float, default=3.0, help="мінімальна пауза між запитами, с (не менше 1)")
    args = ap.parse_args()
    if args.delay < 1:
        raise SystemExit("--delay має бути не менше 1 секунди")
    try:
        run = collect(PoliteClient(delay=args.delay), refresh_days=args.refresh_days, max_new=args.max_new,
                      max_refresh=args.max_refresh, max_pages=args.max_pages)
    except (Blocked, PermissionError, httpx.HTTPError, ValueError) as e:
        raise SystemExit(f"Зупинено: {e}. Уже завантажене збережено в data/real/raw/.")
    print(json.dumps(run, ensure_ascii=False))


if __name__ == "__main__":
    main()
