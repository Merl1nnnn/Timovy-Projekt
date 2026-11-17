"""Оцінка локальних JSON-витягів на ручній розмітці; жодних мережевих запитів."""
import argparse
import json
from pathlib import Path


def f1(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    return {'precision': precision, 'recall': recall,
            'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0}


def evaluate(gold, predictions):
    results = {'examples': len(gold), 'missing_predictions': 0, 'invalid_evidence_spans': 0}
    by_url = {item['source_url']: item for item in predictions}
    for row in gold:
        if row['source_url'] not in by_url:
            results['missing_predictions'] += 1
    for field in ['required_skills', 'nice_to_have_skills', 'technologies', 'certificates']:
        tp = fp = fn = 0
        for expected in gold:
            if field not in expected: continue
            actual = by_url.get(expected['source_url'], {})
            target = {s.casefold() for s in expected[field]}
            found = {s.casefold() for s in actual.get(field, [])}
            tp += len(target & found); fp += len(found - target); fn += len(target - found)
        results[field] = f1(tp, fp, fn)
    for field in ['seniority', 'specialization', 'language']:
        rows = [(g[field], by_url.get(g['source_url'], {}).get(field)) for g in gold if field in g]
        labels = {target for target, _ in rows if target is not None}
        per_class = [f1(sum(a == label and b == label for a,b in rows),
                        sum(a != label and b == label for a,b in rows),
                        sum(a == label and b != label for a,b in rows))['f1'] for label in labels]
        results[field + '_macro_f1'] = sum(per_class) / len(per_class) if per_class else None
    injected = detected = 0
    for expected in gold:
        actual = by_url.get(expected['source_url'], {})
        for name in expected.get('injected_errors', []):
            injected += 1
            if any(r['canonical'].casefold() == name.casefold() for r in actual.get('rejected_items', [])):
                detected += 1
        text = actual.get('source_text', '')
        for mention in actual.get('skill_mentions', []):
            span = mention['evidence']
            if text[span['start']:span['end']] != span['quote']:
                results['invalid_evidence_spans'] += 1
    results['injected_error_detection'] = detected / injected if injected else None
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--gold', type=Path, required=True)
    ap.add_argument('--predictions', type=Path, required=True, help='directory with inspect JSON files or a JSONL file')
    ap.add_argument('--output', type=Path, default=Path('data/parsed/metrics.json'))
    args = ap.parse_args()
    gold = json.loads(args.gold.read_text())
    if args.predictions.is_dir():
        predictions = [json.loads(p.read_text()) for p in args.predictions.glob('*.json')]
    else:
        predictions = [json.loads(line) for line in args.predictions.read_text().splitlines() if line.strip()]
    result = evaluate(gold, predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
