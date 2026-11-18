"""Parses all raw pages from data/raw/ with the LLM -> data/parsed/jobs.jsonl.

A rerun skips already parsed URLs (an Ollama run is slow); --force starts from scratch.
Usage: uv run python -m parser.run [--site profesia|linkedin] [--limit N] [--force]
       uv run python -m parser.run --real   # real postings: data/real/raw -> data/real/parsed, no publishing
"""

import argparse
import json
import os
import sys
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
REAL_RAW_DIR = ROOT / "data" / "real" / "raw"
REAL_PARSED_DIR = ROOT / "data" / "real" / "parsed"


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


def parse_entry(client: LLMClient, entry: dict[str, Any], raw_dir: Path) -> dict[str, Any]:
    html = (raw_dir / entry["file"]).read_text(encoding="utf-8")
    text = html_to_text(html)
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


def run(client: LLMClient, raw_dir: Path = RAW_DIR, out_dir: Path = PARSED_DIR, site: str | None = None,
        limit: int | None = None, force: bool = False) -> tuple[int, int]:
    """Returns (succeeded, failed) for this run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs_path, errors_path = out_dir / "jobs.jsonl", out_dir / "errors.jsonl"
    if force:
        jobs_path.unlink(missing_ok=True)
        errors_path.unlink(missing_ok=True)
    done = {r["source_url"] for r in read_jsonl(jobs_path)}
    todo = [e for e in load_index(raw_dir, site) if e["url"] not in done]
    if limit is not None:
        todo = todo[:limit]
    print(f"{client.name}: до обробки {len(todo)} (уже є {len(done)})")

    ok = failed = 0
    for i, entry in enumerate(todo, start=1):
        try:
            record = parse_entry(client, entry, raw_dir)
        except (ExtractionError, LLMError) as e:
            failed += 1
            with errors_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"url": entry["url"], "error": str(e)[:2000],
                                    "last_output": getattr(e, "last_output", "")[:2000]}, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(todo)}] ПОМИЛКА {entry['url']}: {str(e)[:150]}")
            continue
        ok += 1
        with jobs_path.open("a", encoding="utf-8") as f:  # append immediately so an interrupted run keeps its work
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        flag = " LOW" if record["low_confidence"] else ""
        print(f"[{i}/{len(todo)}] {record['elapsed_s']:>5}s conf={record['confidence']:.2f}{flag}  {record['title']}")
    return ok, failed


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description="LLM-парсер сирих сторінок вакансій.")
    ap.add_argument("--site", choices=["profesia", "linkedin"])
    ap.add_argument("--limit", type=int, help="обробити не більше N сторінок")
    ap.add_argument("--force", action="store_true", help="видалити попередні результати й парсити все заново")
    ap.add_argument("--no-publish", action="store_true", help="лише локальна обробка без публікації")
    ap.add_argument("--real", action="store_true",
                    help="реальні вакансії (data/real/); результати НЕ публікуються автоматично")
    args = ap.parse_args()
    raw_dir, parsed_dir = (REAL_RAW_DIR, REAL_PARSED_DIR) if args.real else (RAW_DIR, PARSED_DIR)
    try:
        ok, failed = run(make_client(), raw_dir=raw_dir, out_dir=parsed_dir, site=args.site,
                         limit=args.limit, force=args.force)
    except httpx.ConnectError as e:
        raise SystemExit(f"LLM недоступна ({e}). Чи запущено Ollama (ollama serve)?")
    print(f"Готово: {ok} успішно, {failed} з помилками -> {parsed_dir}")
    if args.real:
        # Real data is never mixed with synthetic data or published without a manual review
        # (site permission, personal data). Publish manually: scripts/publish_results.py --kind real.
        print("Реальні дані не публікуються автоматично.")
        return
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
