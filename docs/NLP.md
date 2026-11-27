# NLP A — feature/nlp

This branch incorporates main `00ff59c` (25 November 2026), including the live Profesia
scraper, dashboard, extraction fields and team evaluator. The deployed main site is unchanged.

## Pipeline and compatibility

1. Structured extraction preserves main's required/nice-to-have lists, experience,
   education and English summary. `technologies` is removed, matching main.
2. Dictionary NER and LLM proposals produce skills, tools and certificates with exact
   Unicode `[start, end)` spans in the saved source text. Requirements headings and
   item-level nice markers determine the requirement type. Company descriptions,
   benefits, duties, negations and alternative requirements cannot silently become
   mandatory skills. Unknown section layouts go to review rather than being guessed.
3. A separate prompt checks every mention and non-null metadata field. Missing,
   duplicate or unknown IDs, invalid output, failed requests, or confidence below 0.8
   prevent automatic acceptance. The same local model is used twice; its errors may
   be correlated. Confidence is not a calibrated probability.
4. Only supported mentions populate the final lists. A job needing review is kept out
   of `jobs.jsonl` and refused by the public exporter. This conservative gate must be
   assessed for false rejections as well as missed errors.

`skill_mentions` stores canonical name, type, requirement, quote, positions and verdict.
`certificates` is a separate list. `role_specializations` contains explicit title-based
roles such as Backend or ML, independently of Python/Java skill tags. An ambiguous
"Python developer" does not automatically imply either role. The legacy
`specialization` field remains for current consumers. The extraction prompt no longer
infers a lead role from seven years of experience alone. Taxonomy and inference rules
still need agreement with the mentor.

## Salary, language and aliases

- Language detection supports SK/EN/CS, with `und` for insufficient evidence.
- Known Slovak cities map to regions; foreign cities do not receive invented regions.
- `salary_original_min/max`, `salary_currency`, `salary_period` and `salary_basis`
  preserve the source offer, including cents and upper-only bounds.
- Legacy `salary_min/max` and `salary_monthly_min/max` contain **monthly gross** amounts
  in the original currency. Explicit annual gross amounts are divided by 12. Hourly,
  net or ambiguous amounts leave these fields null. No working hours, currency rate,
  or net-to-gross conversion is guessed. Missing units/basis require review.
- Public JSON uses `salary_period=month` with the legacy monthly amounts and preserves
  the source unit separately as `salary_original_period`. Internal results retain the
  source period in `salary_period` for validation and inspection.
- Conflicting salary offers are not resolved by taking the first EUR line. Clear meal
  vouchers/allowances are excluded. Ambiguous combinations still require inspection.
- Experts edit `parser/resources/aliases.json` and its version. Ambiguous aliases fail
  to load; dictionary content changes also invalidate cached results.

## Local checking

No service is started automatically. Use `uv sync --locked`, then start Ollama yourself.
The example configuration uses `qwen2.5:7b` and an 8192-token context. A 1.5B model can
be used for smoke checks, but neither model has a proven quality score for this branch.
Long pages exceeding the conservative context preflight fail rather than being silently
truncated; automatic chunking is not implemented.

```sh
.venv/bin/python -m parser.inspect --input samples/nlp/sk.txt --source-url https://example.invalid/nlp/sk --output data/nlp-checks/sk.json
.venv/bin/python -m parser.inspect --input samples/nlp/en.txt --output data/nlp-checks/en.json
.venv/bin/python -m parser.inspect --input samples/nlp/cs.txt --output data/nlp-checks/cs.json
.venv/bin/python -m parser.inspect --input samples/nlp/adversarial.txt --output data/nlp-checks/adversarial.json
.venv/bin/python -m parser.run --real --no-publish --limit 5
```

`--html` accepts a saved HTML page. Both inspection and batch processing are local.
The frontend receives compatible legacy fields plus optional role/certificate/salary
metadata. Full text and evidence quotes remain local and are not publicly exported.

## Reprocessing and review

Cache identity includes source-text SHA-256, extraction/validation prompts, NLP code,
schema, alias content/version, model name, context and `OLLAMA_MODEL_REVISION`.
Set the revision when replacing weights under the same model tag: tag names alone do
not identify the weights. Review results are cached too, avoiding endless retries.
`--force` reprocesses only the selected records; it does not delete unrelated results.
Legacy outputs are reprocessed, never assigned a new text hash without inference.

- `jobs.jsonl`: current accepted schema-v3 results for export.
- `review.jsonl`: latest uncertain/stale result per source URL; no duplicate attempts.
- `results.jsonl`: current-fingerprint successful attempts, including review, for NLP
  diagnostics. Stale migration records are excluded.
- `errors.jsonl`: failed extraction attempts.

If refreshing fails, the previous accepted record moves to review and is not exported
as current. The files are individually replaced atomically, not a database transaction.
Expert decisions and an expert UI are outside this implementation.

## Measurement

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.evaluate --gold data/real/gold --pred data/real/parsed/jobs.jsonl --ids data/real/splits/dev.json --run-name accepted-dev --out-dir data/real/eval/accepted-dev
.venv/bin/python -m scripts.evaluate --gold data/real/gold --pred data/real/parsed/results.jsonl --ids data/real/splits/dev.json --run-name diagnostics-dev --out-dir data/real/eval/diagnostics-dev
.venv/bin/python -m scripts.evaluate_nlp --gold samples/nlp/gold.example.json --predictions data/nlp-checks --output data/nlp-checks/metrics.json
```

The first report measures accepted output, counting review/missing jobs as missing.
The second diagnoses all current attempts and reports accepted coverage separately.
Never compare these as equivalent cohorts of accepted predictions. Preserve snapshots
and previous outputs before reprocessing; keep development and frozen test sets separate.

Shared evaluation includes seniority/specialization/language macro-F1, optional
certificate/role metrics, literal span and skill evidence coverage, injected-error
recognition and supported-control false rejections. Gold may add `certificates`,
`role_specializations`, `injected_errors` and `supported_controls` lists. Missing optional
annotations are unscored. An injected error counts as detected only when rejected and
absent from the output lists. Literal spans establish traceability, not semantic truth.

The sample gold is synthetic and tiny. No SRS quality target is claimed: skill F1 ≥0.80,
seniority/specialization macro-F1 ≥0.75/0.70, validator error detection ≥85%, and ≥300
human-annotated jobs still require team measurement and a frozen test set.

## Publication safety

Defaults remain `AUTO_PUBLISH=false`, `SKILLMINER_OFFLINE=true` and
an empty `SKILLMINER_BRANCH`. The publisher loads the repository `.env`, respects
existing process variables, and requires an explicitly selected branch when publication
is enabled. Missing/unknown offline configuration blocks publication. Dry runs stay local.
Real processing never auto-publishes. No deployment,
real-site crawl or LLM inference is needed for the offline test suite.
