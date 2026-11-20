# Extraction evaluation — Rostyslav's module

This module validates the human-annotated gold set, scores saved parser outputs,
exports metrics and errors, and compares two runs. It reads input files without
modifying them. It does not call an LLM, scrape jobs, train a model, or publish data.

## Quick demo

Install dependencies with `uv sync --locked`. Run commands from the repository root.
The files in `examples/evaluation/` contain three fictional jobs and manually
prepared predictions. They demonstrate the evaluator, not a real model's quality.

```sh
uv run python -m scripts.evaluate --gold examples/evaluation/gold --validate-only

uv run python -m scripts.evaluate --gold examples/evaluation/gold --pred examples/evaluation/baseline.jsonl --run-name demo-baseline --out-dir data/real/eval/demo-baseline

uv run python -m scripts.evaluate --gold examples/evaluation/gold --pred examples/evaluation/candidate.jsonl --run-name demo-candidate --baseline data/real/eval/demo-baseline/report.json --out-dir data/real/eval/demo-candidate
```

Expected results: the baseline processes 2/3 jobs; the candidate processes 3/3.
The candidate finds all skills but gets the experience field wrong in demo-2.
The report shows both improvements and regressions. Use a new output directory
when repeating a run.

## Real data

1. Freeze copies of the texts used for human annotation and the corresponding
   parser outputs. The current page at the same URL may have changed.
2. Put the participants' `gold_*.json` files in one directory and validate them:

```sh
uv run python -m scripts.evaluate --gold data/real/gold --validate-only
```

3. Have the annotators resolve any conflicts. The evaluator does not choose a winner.
4. Freeze separate dev/test ID lists. `--ids` accepts a JSON array such as
   `["O123", "O456"]`, using actual IDs from your annotations. Keep duplicates and
   versions of the same job in the same split. The evaluator does not create random
   splits or automatically identify similar jobs.
5. Evaluate the saved predictions:

```sh
uv run python -m scripts.evaluate --gold data/real/gold --pred data/real/parsed/jobs.jsonl --ids data/real/splits/dev.json --run-name baseline-dev --prompt-version prompt-v1 --schema-version extraction-v1 --out-dir data/real/eval/baseline-dev
```

`--prompt-version` and `--schema-version` identify the versions actually used to
produce the predictions. The evaluator cannot recover them from an older JSONL
file. Omitted versions are recorded as unknown.

For the next experiment, first save its predictions in a **different** JSONL file.
Then add `--baseline data/real/eval/baseline-dev/report.json` and a new `--out-dir`.
The parser itself keeps only the latest result; this module does not change that
behavior. A normal parser run may skip unchanged texts even after a model or prompt
change. Plan reprocessing separately and preserve the previous predictions first.

If all existing examples have already informed parser improvements, treat them as
development data. Annotate new examples for independent testing. Do not tune the
prompt against test errors. Newly collected jobs do not change the frozen test set.

## Input format and validation

Gold files: `gold_*.json`, each containing `{"dataset_id": "...", "jobs": [...]}`.
`dataset_id` is optional; supplied values within one directory must agree.
Predictions: JSONL with one job object per line. Each `id` must be a non-empty string.

Both formats require: `title`, `company`, `location`, `remote`, `employment_type`,
`seniority`, `min_experience_years`, `education`, `salary_min`, `salary_max`,
`language`, `required_skills`, and `nice_to_have_skills`.

In gold annotations, `null` means the information was checked and is absent;
a missing key makes the record invalid. Skills must be lists of non-empty strings,
`remote` must be a boolean, and years/salary must be non-negative integers or null.
Categories follow the current parser schema.

Agreeing control annotations are merged; skill order does not matter. Conflicts
in scored fields, specialization, or known source identity stop evaluation and
produce a list of issues. Duplicate prediction IDs are rejected: select the outputs
of one run first. Invalid records are not silently discarded. IDs must be unique
within the dataset in this version.

When both records provide `site`, `source_url`/`url`, `snapshot_id`, or `text_hash`,
a mismatch stops evaluation. Missing hashes are allowed for older data, but the
report states how many jobs have matching hashes. Compute hashes from the same
text supplied to the model. Matching IDs alone do not verify matching source text.
Saving source snapshots and computing their hashes are separate steps.

## Reading the metrics

- **Precision = TP / (TP + FP):** the fraction of extracted skills that are correct.
- **Recall = TP / (TP + FN):** the fraction of gold skills that were found.
- **F1 = 2PR / (P + R):** the harmonic mean of precision and recall.
- **Micro:** sum TP/FP/FN across jobs before calculating the metrics.
- **Required / nice / all:** the two skill lists and their union. A skill assigned
  to the wrong list can be correct in `all` but wrong in required/nice.
- **Coverage:** gold jobs with a prediction divided by the selected gold set size.
- **Matched:** quality only on jobs with predictions.
- **Full cohort / end-to-end:** missing predictions count as empty skill lists.
  For field accuracy, a missing prediction is incorrect even if the gold value is null.
- **Present-only accuracy:** field accuracy on matched jobs whose gold value is
  not null. The report includes the sample count; this does not cover all gold jobs.

Empty-set convention: precision or recall with a zero denominator is 1; when both
skill sets are empty, F1 is 1. Always read F1 alongside coverage and TP/FP/FN.
Matched metrics are N/A when no jobs have predictions. An empty predictions file
can represent a complete processing failure. A non-empty file with no matching IDs
is treated as an incorrectly selected dataset. Extra IDs are listed but not scored.

Skills are compared after the parser's current normalization of aliases, case,
diacritics, and punctuation. This is not semantic ESCO evaluation. Job titles are
compared after collapsing whitespace. Company names use the existing rule that
removes legal forms and accepts equal names or substring matches. Other fields use
exact equality. These rules have limitations; normalization changes can affect scores.

`specialization` is not scored yet because the gold and parser categories differ.
`summary` and `salary_currency` are also unscored. The existing heuristic confidence
checks and frequent-error lists remain in JSON. Confidence is not a calibrated
probability of correctness.

## Reports and comparison

A new `--out-dir` contains:

- `report.json`: metrics, individual errors, per-job results, and run metadata.
- `report.md`: a readable summary for the team.
- `errors.csv`: incorrect fields, extra/missing skills, and missing predictions.

The CSV uses normalized skill keys. Inspect the source text to determine why an
error occurred; the evaluator identifies discrepancies, not their causes. CSV text
cells are escaped against spreadsheet formula interpretation. Reports can contain
job data; the default `data/real/eval/` directory is already excluded from Git.

`--json` remains available for a standalone JSON report. Existing output files and
directories are never overwritten. Invalid inputs or incompatible comparisons return
CLI exit code 2; successful runs return 0.

Comparison requires identical gold IDs, a matching gold fingerprint, and a matching
scoring-rules fingerprint. Metadata also records the predictions file's SHA-256,
model names, and evaluation time. If scoring rules change, evaluate **both saved
prediction sets** again under the new rules. Regenerate older reports without metadata.

Main metric deltas use the full frozen gold cohort, so missing predictions cannot
silently improve the score. Reports also include newly processed jobs, lost
predictions, and changes on jobs processed in both runs. A delta describes a
difference; it does not establish statistical significance. Conclusions from small
datasets are preliminary, and there is no universal threshold for a good F1 score.

## Tests

```sh
uv run pytest tests/test_evaluate.py -q
```

Tests cover manually verified metrics, missing predictions, null fields, annotation
conflicts, incompatible snapshots/reports, input preservation, and the CLI.
