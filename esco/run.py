import argparse
import csv
import hashlib
import json
from pathlib import Path

import httpx

from esco.data import digest, fetch_catalog, import_csv, load_catalog, read_json, write_json
from esco.embeddings import EmbeddingCache, OllamaEmbedder, SemanticIndex, build_index
from esco.evaluate import compare_reports, evaluate_mapping, import_review, report_markdown, review_template, validate_run
from esco.search import Matcher, Query, make_queries


def new_directory(path):
    path.mkdir(parents=True, exist_ok=False)


def csv_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def export_mapping(run, out):
    new_directory(out)
    write_json(out / "mapping.json", run)
    write_json(out / "review.json", review_template(run))
    fields = ["query_id", "skill", "context", "occurrences", "candidate_1", "candidate_2", "candidate_3",
              "decision", "acceptable_uris", "split", "reviewer", "note"]
    with (out / "review.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in run["results"]:
            entry = {"query_id": row["id"], "skill": row["skill"], "context": row["context"],
                     "occurrences": len(row["occurrences"]), "decision": "unreviewed", "split": "unassigned",
                     "acceptable_uris": "", "reviewer": "", "note": ""}
            for i in range(3):
                c = row["candidates"][i] if i < len(row["candidates"]) else None
                entry[f"candidate_{i + 1}"] = f"{c['labels'].get('en', next(iter(c['labels'].values())))} | {c['uri']} | {c['score']}" if c else ""
            writer.writerow({k: csv_cell(v) for k, v in entry.items()})


def main():
    parser = argparse.ArgumentParser(description="Prepare and evaluate ESCO skill mapping locally")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("download")
    fetch.add_argument("--version", default="v1.2.0")
    fetch.add_argument("--languages", nargs="+", default=["en", "sk"])
    fetch.add_argument("--page-size", type=int, default=200)
    fetch.add_argument("--out", type=Path, required=True)
    imp = commands.add_parser("import-csv")
    imp.add_argument("--csv", action="append", required=True, metavar="LANG=PATH")
    imp.add_argument("--version", required=True)
    imp.add_argument("--out", type=Path, required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--pred", type=Path, required=True)
    collect.add_argument("--out", type=Path, required=True)
    index = commands.add_parser("index")
    index.add_argument("--catalog", type=Path, required=True)
    index.add_argument("--out-dir", type=Path, required=True)
    index.add_argument("--batch-size", type=int, default=32)
    mapping = commands.add_parser("map")
    mapping.add_argument("--catalog", type=Path, required=True)
    mapping.add_argument("--queries", type=Path, required=True)
    mapping.add_argument("--method", choices=["lexical", "embedding", "hybrid"], default="lexical")
    mapping.add_argument("--index", type=Path)
    mapping.add_argument("--k", type=int, default=3)
    mapping.add_argument("--out-dir", type=Path, required=True)
    for command in (index, mapping):
        command.add_argument("--model", default="embeddinggemma:latest")
        command.add_argument("--ollama-url", default="http://localhost:11434")
        command.add_argument("--cache", type=Path, default=Path("data/esco/embeddings.sqlite3"))
    review = commands.add_parser("import-review")
    review.add_argument("--catalog", type=Path, required=True)
    review.add_argument("--run", type=Path, required=True)
    review.add_argument("--csv", type=Path, required=True)
    review.add_argument("--out", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--catalog", type=Path, required=True)
    evaluate.add_argument("--run", type=Path, required=True)
    evaluate.add_argument("--gold", type=Path, required=True)
    evaluate.add_argument("--split", choices=["dev", "test"], required=True)
    evaluate.add_argument("--baseline", type=Path)
    evaluate.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    client = cache = None
    try:
        out = getattr(args, "out", None) or getattr(args, "out_dir", None)
        if out and out.exists():
            raise ValueError("Output already exists; choose a new path")
        if args.command == "download":
            catalog = fetch_catalog(args.out, args.version, args.languages, args.page_size)
            print(f"Saved {len(catalog.concepts)} concepts")
        elif args.command == "import-csv":
            files = {}
            for item in args.csv:
                lang, path = item.split("=", 1)
                if lang in files or not lang:
                    raise ValueError("Use distinct language codes")
                files[lang] = Path(path)
            catalog = import_csv(files, args.version, args.out)
            print(f"Imported {len(catalog.concepts)} concepts")
        elif args.command == "collect":
            if args.pred.suffix == ".jsonl":
                jobs = [json.loads(line) for line in args.pred.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            else:
                payload = read_json(args.pred)
                jobs = payload["jobs"] if isinstance(payload, dict) else payload
            queries = make_queries(jobs)
            write_json(args.out, {"format_version": 1, "source_sha256": hashlib.sha256(args.pred.read_bytes()).hexdigest(),
                                  "queries": [q.model_dump() for q in queries]})
            print(f"Collected {len(queries)} distinct skill queries")
        else:
            catalog = load_catalog(args.catalog)
            if args.command == "index" or (args.command == "map" and args.method != "lexical"):
                client = OllamaEmbedder(args.model, args.ollama_url)
                cache = EmbeddingCache(args.cache)
            if args.command == "index":
                meta = build_index(catalog, args.out_dir, client, cache, args.batch_size)
                print(f"Indexed {len(meta['uris'])} skills; {meta['dimensions']} dimensions")
            elif args.command == "map":
                queries = [Query.model_validate(q) for q in read_json(args.queries)["queries"]]
                if not queries or len({q.id for q in queries}) != len(queries):
                    raise ValueError("Expected non-empty queries with unique IDs")
                if args.method != "lexical" and args.index is None:
                    raise ValueError("Supply --index for embedding/hybrid search")
                semantic = SemanticIndex(args.index, catalog, client, cache) if client else None
                matcher = Matcher(catalog, semantic)
                results = []
                for i, query in enumerate(queries, 1):
                    results.append(matcher.search(query, args.method, args.k))
                    print(f"Mapped {i}/{len(queries)}: {query.skill}")
                if client:
                    client.verify()
                rows = [q.model_dump() for q in queries]
                run = {"format_version": 1, "esco_version": catalog.esco_version,
                       "catalog_fingerprint": catalog.fingerprint, "queries_fingerprint": digest(rows),
                       "method": args.method, "k": args.k, "queries": rows, "results": results,
                       "embedding": {"model": client.model, "digest": client.model_digest,
                                     "profile": client.profile} if client else None,
                       "note": "Candidates require human review. Scores are not probabilities; no automatic assignments."}
                export_mapping(run, args.out_dir)
            elif args.command == "import-review":
                run = validate_run(read_json(args.run), catalog)
                import_review(args.csv, run, catalog, args.out)
                print("Saved human review")
            elif args.command == "evaluate":
                report = evaluate_mapping(read_json(args.gold), read_json(args.run), catalog, args.split)
                if args.baseline:
                    report["comparison"] = compare_reports(read_json(args.baseline), report)
                new_directory(args.out_dir)
                write_json(args.out_dir / "report.json", report)
                with (args.out_dir / "report.md").open("x", encoding="utf-8") as stream:
                    stream.write(report_markdown(report))
                print(report_markdown(report))
    except (ValueError, OSError, KeyError, TypeError, httpx.HTTPError) as exc:
        parser.exit(2, f"ESCO operation stopped: {exc}\n")
    finally:
        if cache:
            cache.close()
        if client:
            client.close()


if __name__ == "__main__":
    main()
