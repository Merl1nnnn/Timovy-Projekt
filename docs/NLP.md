# NLP A — feature/nlp

This branch starts at `main` commit `c3124bb6c9e6c668fe02ac5a750243c1a9a96022`. It extends the existing Ollama extractor; it is not a separate project. No frontend, published JSON or Pages workflow changes are needed for this work.

## Implemented path

1. Existing HTML-to-text and structured LLM extraction.
2. Fast dictionary NER plus LLM mention proposals, including explicit certifications and skill types.
3. Exact quotes grounded in the unchanged text. Python Unicode offsets use `[start, end)`, not UTF-8 byte offsets. The alias registry checks surface → canonical mappings. Quotes from recognised benefits/duties sections, negations and missing quotes go to review.
4. A separate LLM prompt validates every mention and non-null metadata field. Missing/duplicate IDs, an invalid response, a failed request, or confidence below 0.8 fails closed. The same configured local model is used in a second pass; this is not an independently trained model.
5. Only supported mentions populate the final skill lists. Metadata needs literal supporting quotes. Uncertain records and low-confidence heuristic reports go to `data/parsed/review.jsonl`; only accepted records go to `jobs.jsonl`.
6. SK/EN/CS language heuristics (with `und` for insufficient text), Slovak city-to-region mapping, explicit salary currency/period/gross/net. Yearly amounts have a separate monthly equivalent. Hourly pay is not multiplied by guessed working hours. Ambiguous currencies or missing period/basis require review. Currency is not converted and net is not converted to gross.

`source_text`, its SHA-256, `field_evidence`, `skill_mentions`, rejected items and model/alias versions are local audit data. Evidence is anchored to the exact stored `source_text`; changing the text invalidates offsets. The public exporter does not export full text or evidence quotes. The exporter accepts only validated schema-v2 records; legacy and review records are refused. At the next batch run, legacy local results move to review instead of silently being treated as validated.

`role_specializations` separates role tags (Backend, ML, etc.) from technologies; the existing legacy fields remain for compatibility. Role tags are derived from explicit title wording, not guessed from a technology alone.

## Local manual inspection

No model/server is started automatically. Install dependencies using `uv sync --locked`. Start Ollama yourself only when you want to run inference. Use an 8192-token context or larger. The conservative preflight may reject long pages instead of letting Ollama truncate them silently; chunking long postings is still a future improvement.

```sh
# From this checkout, after you choose to start Ollama:
.venv/bin/python -m parser.inspect --input samples/nlp/sk.txt \
  --source-url https://example.invalid/nlp/sk --output data/nlp-checks/sk.json
.venv/bin/python -m parser.inspect --input samples/nlp/en.txt --output data/nlp-checks/en.json
.venv/bin/python -m parser.inspect --input samples/nlp/cs.txt --output data/nlp-checks/cs.json
.venv/bin/python -m parser.inspect --input samples/nlp/adversarial.txt --output data/nlp-checks/adversarial.json
```

Use `--html` for a saved page. This command only reads a file and writes local JSON; it never publishes. See `samples/nlp/EXPECTED.md` for manual expectations. Source text can contain personal data: use redacted source pages and keep `data/` out of Git.

For the normal batch pipeline: `.venv/bin/python -m parser.run --no-publish`. Review files are candidates for the future expert UI, not an implemented expert decision workflow. Re-running the old batch runner may append repeated review attempts; use the inspection command for focused debugging.

## Test and measurement commands (prepared for the user, not executed during this change)

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_nlp_evidence.py -q
.venv/bin/python -m scripts.evaluate_nlp --gold samples/nlp/gold.example.json \
  --predictions data/nlp-checks --output data/nlp-checks/metrics.json
```

The tiny synthetic examples are not the required ≥300 manually annotated golden set. Annotation ownership remains shared with NLP B. No SRS metric is claimed as achieved: skill F1 ≥0.80, seniority/specialisation macro-F1 ≥0.75/0.70 and validator injected-error detection ≥85% still need measurement on the frozen human-labelled test split. Numeric confidence is a model judgement/heuristic, not a calibrated probability.

## Expert-maintained aliases

Edit `parser/resources/aliases.json`: canonical name, aliases, kind, and a new version string. Ambiguous aliases fail to load. Restart the parser after editing. This is a versioned file interface, not an expert web editor. The NER stage is dictionary matching, not a fine-tuned SlovakBERT model. Inflections/new aliases and domain vocabulary need manual review.

## Branch safety

`AUTO_PUBLISH=false`, `SKILLMINER_OFFLINE=true`, and `SKILLMINER_BRANCH=feature/nlp` are the defaults here. The publisher refuses actual uploads in offline mode. The hosted main frontend remains unchanged. Do not disable the guard until the team agrees on a reviewed integration.

Both other branches change `parser/run.py`. When merging later, preserve their changed-text hash logic / `--real` routing and this branch's validation gate. No integration with those branches was performed here.

## Known limitations to check

- Small local models can still be inaccurate; the validator may agree with an extractor error.
- Requirements-section and negation detection is conservative and language dependent; inspect false rejections.
- The alias dictionary and regional coverage are finite; foreign cities have no invented Slovak region.
- No legal source approval, real-site crawl, new training, expert UI or golden-set annotation is performed by this branch.
- Title/company/other rejected metadata is kept only in review records for diagnosis; accepted records require field evidence.
- The legacy frontend assumes monthly pay; it must use `salary_period`/`salary_monthly_*` before this output is integrated into main analytics.
