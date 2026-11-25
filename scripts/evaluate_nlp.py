"""Inspection-file adapter; shared metrics live in scripts.nlp_metrics."""
import argparse
import json
from pathlib import Path

from scripts.nlp_metrics import evaluate_nlp, key, prf


def indexed(rows):
    result = {}
    for row in rows:
        url = row.get('source_url')
        if not isinstance(url, str) or not url:
            raise ValueError('Every inspection/gold row needs source_url')
        if url in result:
            raise ValueError(f'Duplicate source_url: {url}')
        result[url] = row
    return result


def evaluate(gold, predictions):
    expected, actual = indexed(gold), indexed(predictions)
    for url in expected.keys() & actual.keys():
        for field in ('text_hash', 'source_text_sha256', 'snapshot_id'):
            if expected[url].get(field) and actual[url].get(field) and expected[url][field] != actual[url][field]:
                raise ValueError(f'Source snapshot mismatch: {url}')
    result = evaluate_nlp(expected, actual)
    for field in ('required_skills', 'nice_to_have_skills'):
        tp = fp = fn = 0
        for url, g in expected.items():
            if field not in g: continue
            target = {key(v) for v in g[field]}
            found = {key(v) for v in actual.get(url, {}).get(field, [])}
            tp += len(target & found); fp += len(found-target); fn += len(target-found)
        result[field] = prf(tp, fp, fn)
    result['missing_predictions'] = sorted(expected.keys() - actual.keys())
    result['extra_predictions'] = sorted(actual.keys() - expected.keys())
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--gold', type=Path, required=True)
    ap.add_argument('--predictions', type=Path, required=True)
    ap.add_argument('--output', type=Path, default=Path('data/parsed/metrics.json'))
    args = ap.parse_args()
    gold = json.loads(args.gold.read_text(encoding='utf-8'))
    if isinstance(gold, dict): gold = gold['jobs']
    if args.predictions.is_dir():
        predictions = []
        for p in sorted(args.predictions.glob('*.json')):
            if p.resolve() in {args.output.resolve(), args.gold.resolve()}: continue
            row = json.loads(p.read_text(encoding='utf-8'))
            # Directories may contain reports as well as inspection records.
            if isinstance(row, dict) and 'source_url' in row: predictions.append(row)
    else:
        predictions = [json.loads(line) for line in args.predictions.read_text(encoding='utf-8').splitlines() if line.strip()]
    result = evaluate(gold, predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
