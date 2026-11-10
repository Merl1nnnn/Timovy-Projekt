"""Підготувати публічний JSON для фронтенду з локального jobs.jsonl."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

FIELDS = ('title', 'company', 'location', 'remote', 'employment_type', 'seniority',
          'specialization', 'required_skills', 'nice_to_have_skills', 'technologies',
          'salary_min', 'salary_max', 'salary_currency', 'language', 'source_url',
          'site', 'id', 'confidence', 'low_confidence', 'quality_issues', 'model', 'parsed_at')
EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
PHONE = re.compile(r'(?<!\w)(?:\+|00)\d[\d ()-]{7,}\d')


def redact(value):
    # Сирі HTML/тексти й довільні службові поля ніколи не експортуються.
    if isinstance(value, str):
        return PHONE.sub('[phone removed]', EMAIL.sub('[email removed]', value))
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def export(source: Path, output: Path, kind: str) -> dict:
    jobs = []
    seen = set()
    for number, line in enumerate(source.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or not isinstance(record.get('title'), str):
            raise ValueError(f'Рядок {number}: потрібен об’єкт із title')
        for key in ('technologies', 'required_skills', 'nice_to_have_skills', 'quality_issues'):
            if key in record and (not isinstance(record[key], list) or
                                  not all(isinstance(v, str) for v in record[key])):
                raise ValueError(f'Рядок {number}: {key} має бути списком рядків')
        key = record.get('source_url')
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        jobs.append({k: redact(record[k]) for k in FIELDS if k in record})
    if not jobs:
        raise ValueError('Порожній набір: попередня публікація не буде замінена')
    payload = {'schema_version': 1, 'dataset_kind': kind,
               'generated_at': datetime.now(timezone.utc).isoformat(), 'jobs': jobs}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(output)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('frontend/data/jobs.json'))
    parser.add_argument('--kind', choices=['synthetic', 'real'], default='synthetic')
    args = parser.parse_args()
    payload = export(args.input, args.output, args.kind)
    print(f"Підготовлено {len(payload['jobs'])} публічних записів: {args.output}")


if __name__ == '__main__':
    main()
