"""Парсить усі сирі сторінки з data/raw/ через LLM -> data/parsed/jobs.jsonl.

Повторний запуск пропускає незмінений текст; --force повторно обробляє вибірку.
Запуск: uv run python -m parser.run [--site profesia|linkedin] [--limit N] [--force]
"""

import argparse
from hashlib import sha256
import json
import os
import sys
from tempfile import NamedTemporaryFile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from parser.extract import ExtractionError, extract
from parser.html_text import html_to_text
from parser.llm import LLMClient, LLMError, make_client
from parser.quality import check
from scripts.publish_results import publish

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PARSED_DIR = ROOT / "data" / "parsed"


def load_index(raw_dir: Path, site: str | None = None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index_file in sorted(raw_dir.glob("*/index.json")):
        if site and index_file.parent.name != site:
            continue
        entries += json.loads(index_file.read_text(encoding="utf-8"))
    return entries


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_entry(client: LLMClient, entry: dict[str, Any], text: str) -> dict[str, Any]:
    started = time.perf_counter()
    posting, attempts = extract(client, text, source_url=entry["url"])
    report = check(posting, text)
    return {
        "site": entry["site"],
        "id": entry["id"],
        **posting.model_dump(),
        "confidence": report.confidence,
        "low_confidence": report.low_confidence,
        "quality_issues": report.issues,
        "attempts": attempts,
        "model": client.name,
        "elapsed_s": round(time.perf_counter() - started, 1),
        "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def save_jobs(path: Path, records: dict[str, dict[str, Any]]) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            for record in records.values():
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(client: LLMClient, raw_dir: Path = RAW_DIR, out_dir: Path = PARSED_DIR, site: str | None = None,
        limit: int | None = None, force: bool = False) -> tuple[int, int]:
    """Повертає (успішно, помилок) за цей запуск."""
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs_path, errors_path = out_dir / "jobs.jsonl", out_dir / "errors.jsonl"
    records = {r["source_url"]: r for r in read_jsonl(jobs_path)}
    entries = load_index(raw_dir, site)
    print(f"{client.name}: перевіряємо {len(entries)} сторінок (уже є {len(records)})")
    ok = failed = 0
    for i, entry in enumerate(entries, start=1):
        if limit is not None and ok + failed >= limit:
            break
        content = html_to_text((raw_dir / entry["file"]).read_text(encoding="utf-8"))
        digest = sha256(content.encode("utf-8")).hexdigest()
        existing = records.get(entry["url"])
        if not force and existing and existing.get("text_hash") == digest:
            continue
        try:
            record = parse_entry(client, entry, content)
        except (ExtractionError, LLMError) as e:
            failed += 1
            with errors_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"url": entry["url"], "error": str(e)[:2000],
                                    "last_output": getattr(e, "last_output", "")[:2000]}, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(entries)}] ПОМИЛКА {entry['url']}: {str(e)[:150]}")
            continue
        ok += 1
        record["text_hash"] = digest
        record["scraped_at"] = entry.get("scraped_at")
        records[entry["url"]] = record
        save_jobs(jobs_path, records)
        flag = " LOW" if record["low_confidence"] else ""
        print(f"[{i}/{len(entries)}] {record['elapsed_s']:>5}s conf={record['confidence']:.2f}{flag}  {record['title']}")
    return ok, failed


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description="LLM-парсер сирих сторінок вакансій.")
    ap.add_argument("--site", choices=["profesia", "linkedin"])
    ap.add_argument("--limit", type=int, help="обробити не більше N сторінок")
    ap.add_argument("--force", action="store_true", help="повторно розпарсити вибрані сторінки")
    ap.add_argument("--no-publish", action="store_true", help="лише локальна обробка без публікації")
    args = ap.parse_args()
    try:
        ok, failed = run(make_client(), site=args.site, limit=args.limit, force=args.force)
    except httpx.ConnectError as e:
        raise SystemExit(f"LLM недоступна ({e}). Чи запущено Ollama (ollama serve)?")
    print(f"Готово: {ok} успішно, {failed} з помилками -> data/parsed/")
    enabled = os.getenv("AUTO_PUBLISH", "true").lower() not in {"0", "false", "no"}
    if not args.no_publish and enabled and (PARSED_DIR / "jobs.jsonl").exists():
        try:
            result = publish(PARSED_DIR / "jobs.jsonl", kind=os.getenv("DATASET_KIND", "synthetic"))
        except (RuntimeError, OSError, ValueError) as error:
            raise SystemExit(f"Публікація не вдалася: {error}. Локальні дані збережено; повторіть запуск.") from None
        if result["changed"]:
            print(f"Результати відправлено: {result['url']}. GitHub Pages оновиться після deployment.")
        else:
            print("На сайті вже актуальні результати; повторна публікація не потрібна.")


if __name__ == "__main__":
    main()
