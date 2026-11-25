"""Локальний перегляд NLP без скрапера та без публікації."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from parser.extract import extract
from parser.html_text import html_to_text
from parser.llm import make_client
from parser.quality import check
from parser.provenance import provenance
from parser.validator import validate_posting


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--html', action='store_true')
    ap.add_argument('--source-url', default='https://example.invalid/local-nlp-check')
    ap.add_argument('--output', type=Path, default=Path('data/parsed/inspection.json'))
    args = ap.parse_args()
    source = args.input.read_text(encoding='utf-8')
    text = html_to_text(source) if args.html else source
    client = make_client()
    try:
        posting, attempts = extract(client, text, args.source_url)
        posting = validate_posting(client, posting, text)
        report = check(posting, text)
        if report.low_confidence:
            posting.review_required = True
            posting.validation_status = 'review'
        output = {**posting.model_dump(), **provenance(client), 'source_text': text,
                  'quality': report.model_dump(), 'model': client.name, 'attempts': attempts,
                  'parsed_at': datetime.now(timezone.utc).isoformat()}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{posting.validation_status}: {args.output}')
    finally:
        http = getattr(client, 'http', None)
        if http is not None: http.close()


if __name__ == '__main__':
    main()
