# SkillMiner

A student team project for analysing IT job postings and mapping skills to ESCO. Requirements: [English SRS](docs/SRS_SkillMiner_EN.docx) · [Slovak SRS](docs/SRS_SkillMiner_SK.docx).

## Download and run the backend

Download the repository with **Code → Download ZIP**, or clone it:

```sh
git clone https://github.com/Merl1nnnn/Timovy-Projekt.git
cd Timovy-Projekt
```

Requirements: [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com/), and [GitHub CLI](https://cli.github.com/) for publishing. Python 3.11 is selected by the project configuration. A GPU is optional; the default small model runs on CPU, but its extraction quality is limited.

Install dependencies and prepare configuration:

```sh
uv sync --locked
uv run playwright install chromium
cp .env.example .env
```

On Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp` if needed. On Linux, missing browser system libraries can be installed with `uv run playwright install --with-deps chromium`.

Start Ollama if it is not already running, and download the model:

```sh
ollama serve
# In another terminal:
ollama pull qwen2.5:1.5b
```

Create the local demonstration sites and start their server:

```sh
uv run python -m mock_sites.generate
uv run python -m mock_sites.serve
```

Keep that server running. In another terminal, collect the mock pages, sign in to GitHub once, and run the parser:

```sh
uv run python -m scraper.run
gh auth login
uv run python -m parser.run
```

**When parsing finishes, results are automatically sent to the shared repository and GitHub Pages is updated.** Each participant must have write access to `Merl1nnnn/Timovy-Projekt`. Downloading the code alone does not grant permission to update the shared site. GitHub credentials remain on the participant's own computer.

The prototype collects from **local mock sites only**, not real Profesia or LinkedIn. Raw HTML is stored in `data/raw/`; extraction results in `data/parsed/jobs.jsonl`. The code includes the parser, normalisation, heuristic quality checks, mock-site generator and scraper. It does not yet implement the complete API, database, ESCO mapping or LLM validator described in the SRS; `app/` and `storage/` are placeholders.

### Real postings from Profesia.sk (experimental)

`scraper/profesia_live.py` downloads IT postings from the real Profesia.sk category *Informačné technológie* over plain HTTP:

```sh
uv run python -m scraper.profesia_live --limit 20
uv run python -m parser.run --real
```

- It checks `robots.txt`, waits at least 3 s (default) between requests, sends an identifying User-Agent and stops on HTTP 403/429.
- It is incremental. Already downloaded postings are skipped, and `--limit` caps new postings per run.
- Only the `<main id="detail">` block is stored. The contact section, contact person names, e-mail addresses and phone numbers are removed before saving.
- Real data lives in `data/real/` (git-ignored), separate from mock data. `parser.run --real` **never publishes automatically**. Publish manually with `scripts/publish_results.py --kind real` only after the team has confirmed permission to use the data.
- LinkedIn is intentionally not scraped: its terms prohibit automated access without permission.
- Real pages are longer than mock pages. With Ollama, set `OLLAMA_NUM_CTX=8192`.

#### Evaluate against the gold set

For gold validation, immutable JSON/Markdown/CSV reports, fixed dev/test cohorts and comparison of two saved runs, see [Evaluation guide](docs/EVALUATION.md). A synthetic demo runs locally without Ollama or real vacancy data.

The team hand-annotated 50 real postings (`data/real/gold/`, git-ignored). `scripts/evaluate.py` compares `data/real/parsed/jobs.jsonl` with them: accuracy per field, micro precision / recall / F1 for skills, and whether `low_confidence` really marks worse records.

```sh
uv run python -m parser.run --real
uv run python -m scripts.evaluate --json data/real/eval/report.json
```

`specialization` is not scored yet, because the gold set uses `other` for postings outside the parser's six specialisations.

### Automatic publishing settings

Defaults in `.env.example`:

```dotenv
AUTO_PUBLISH=true
SKILLMINER_REPOSITORY=Merl1nnnn/Timovy-Projekt
SKILLMINER_BRANCH=main
DATASET_KIND=synthetic
```

For local processing without uploading:

```sh
uv run python -m parser.run --no-publish
```

Alternatively set `AUTO_PUBLISH=false` in `.env`. `--limit N` processes at most N new postings; `--force` rebuilds local extraction output. A normal rerun skips already parsed URLs.

Published jobs are merged by `source_url`, preserving results submitted by other participants. For the same URL, the newer `parsed_at` wins. Concurrent updates are re-read and retried up to three times. Unchanged data creates no commit. Synthetic and real datasets cannot be mixed. Publishing is additive: rebuilding local output does not delete records already published by others.

If uploading fails, the command reports an error and keeps local results. Run the parser again to retry uploading without reprocessing existing URLs. A successful upload means the GitHub commit was accepted; the website updates after its deployment workflow completes.

## Public dashboard

**Live site: https://merl1nnnn.github.io/Timovy-Projekt/**

The static dashboard in `frontend/` supports search, filters, frequencies of required and nice-to-have skills, job details (short English summary, minimum experience and education), quality flags and CSV export. The interface is available in **Slovak, English and Ukrainian**, with **light and dark themes**. Preferences are saved in the browser. Job titles and extracted data remain in their original language.

A **Mock / Real** switch at the top selects the dataset. Mock data (lavender notice) comes from `frontend/data/jobs.json`; real Profesia.sk postings (green notice) come from `frontend/data/jobs_real.json`. Until real data is published, the Real view says so instead of showing anything. The choice is remembered and can be linked with `?data=real` or `?data=mock`.

The initial dataset contains **101 synthetic postings from local mock sites**. LLM results may contain errors. These are not statistics from the real labour market.

## How publishing works

Local NLP pipeline → public JSON in GitHub → GitHub Actions → GitHub Pages.

The laptop is needed only to process and upload new results. Published data stays available when the laptop is off. Each upload publishes a merged JSON snapshot; this is not a database or a realtime API.

The workflow in `.github/workflows/pages.yml` publishes only `frontend/` when that directory changes on `main`. GitHub Pages is configured to use GitHub Actions. To set this up in another repository, select **Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Local preview

No frontend build step or JavaScript dependencies are required. Use Python 3.11 or newer:

```sh
python3 -m http.server 8765 --directory frontend
```

Open http://localhost:8765. Opening `index.html` through `file://` is not supported because the dashboard loads its JSON with `fetch`.

To see your local real postings in the Real view, export them first. `frontend/data/jobs_real.json` is git-ignored, so it cannot be committed by accident:

```sh
python3 scripts/export_results.py --input data/real/parsed/jobs.jsonl --kind real
```

## Publish local NLP results

Install [GitHub CLI](https://cli.github.com/) and sign in with write access to this repository:

```sh
gh auth login
python3 scripts/publish_results.py --input '/absolute/path/to/data/parsed/jobs.jsonl' --dry-run
```

Review `data/parsed/public_jobs.json` next to your input file, then publish:

```sh
python3 scripts/publish_results.py --input '/absolute/path/to/data/parsed/jobs.jsonl'
```

The script merges results into `frontend/data/jobs.json` (synthetic) or `frontend/data/jobs_real.json` (`--kind real`) on `main`, preserving jobs from other participants. The real file is created on its first publication. GitHub Actions then deploys the updated site. Earlier snapshots remain in Git history. Concurrent updates are retried; if all retries fail, local results remain available for a later upload.

Datasets are marked as synthetic by default. Use `--kind real` only after checking publication permissions and removing personal data upstream.

Authentication uses GitHub CLI or `GITHUB_TOKEN` with **Contents: write** access. Never put tokens in frontend files or commit them. The export includes only explicitly allowed fields, excludes raw HTML and `.env`, and redacts email addresses and international phone numbers. This is not complete anonymisation: names and other personal information must be removed in the processing pipeline before export.

To prepare JSON without making network requests:

```sh
python3 scripts/export_results.py --input '/absolute/path/to/jobs.jsonl'
```

## Tests

```sh
uv run pytest -q
```

The 92 automated tests cover extraction, normalisation, rule-based salary fallback, quality checks, mock sites, the Chromium scraper, the real Profesia scraper (offline, on synthetic HTML), export redaction, shared-result merging, upload conflicts, automatic publishing, opt-out and local-data preservation on failure. Unit tests use fake LLM responses and do not require Ollama. Browser checks cover language and theme switching, saved preferences, filters and job details. Unit tests do not measure quality on real postings; use `scripts/evaluate.py` with the gold set for that.

## Local skill analytics prototype

Run `python3 -m http.server 8773 --bind 127.0.0.1 --directory frontend`, then open
`http://127.0.0.1:8773/?data=real#/analytics`. This local prototype reads the same
published snapshots as Job postings; it does not scrape, run an LLM or publish results.

Analytics uses deduplicated postings without a review flag, not human verification.
Select any number of required/nice-to-have skill tags: every selected skill must occur
in the same posting. Real and synthetic selections are kept separately. Date filters,
median advertised minima, quartiles, salary distributions and matching postings update
without reloading. Salary observations are converted into the chosen currency and period before aggregation. Missing dates/pay
are excluded from the corresponding chart; processing dates are labelled as such.

The skill funnel shows the remaining postings and losses after each added tag.
Company-offer comparison accepts independent skills, role, seniority, city and gross
base salary, then reports the median gap, percentile and comparable sample size.
Two independent profiles can be compared by counts, companies, remote share and
salary quartiles, with their overlap shown explicitly. All comparison forms share
the selected dataset and dates; their requirements are independent of the main tags.
Settings stay in this browser, separately for real and synthetic data. Salary
comparisons use converted advertised minima, exclude explicitly net amounts,
and do not imply a causal pay premium. Roles require an
explicit role label or title wording; a programming language alone does not imply a role.

Currency conversion uses the dated local ECB snapshot in `frontend/data/exchange-rates.json`.
The same snapshot rates apply to all observations; this is not historical FX analysis.
Refresh it locally with `python3 scripts/update_exchange_rates.py`, then reload the page.
The browser reads only the local file and makes no external rate requests.
Annual salary = monthly × 12; hourly estimates use 52 weeks/year and 40 h/week for
`full_time` or 20 h/week for `part_time`. Unknown employment types cannot be converted
between hourly and monthly/yearly pay. Missing legacy pay periods remain monthly.
Bonuses and taxes are not estimated. Charts show salary sample coverage and exclude
amounts with missing currency rates or required working hours. Posting rows retain
the original advertised amount alongside the converted estimate.

Run the frontend checks with `node --test tests/test_jobs_model.cjs tests/test_analytics_model.cjs tests/test_frontend_assets.cjs`.
These checks also run in GitHub Actions on this feature branch and pull requests to `main`.
GitHub Pages continues to publish only from `main`; after merging, the existing workflow
uploads the complete `frontend` directory, including analytics modules and the local
exchange-rate snapshot. Analytics needs no backend service, API keys or local `.env`.
