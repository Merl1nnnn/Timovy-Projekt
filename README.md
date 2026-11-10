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

The static dashboard in `frontend/` supports search, filters, technology frequencies, job details, quality flags and CSV export. The interface is available in **Slovak, English and Ukrainian**, with **light and dark themes**. Preferences are saved in the browser. Job titles and extracted data remain in their original language.

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

The script merges results into `frontend/data/jobs.json` on `main`, preserving jobs from other participants. GitHub Actions then deploys the updated site. Earlier snapshots remain in Git history. Concurrent updates are retried; if all retries fail, local results remain available for a later upload.

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

The 62 automated tests cover extraction, normalisation, quality checks, mock sites, the Chromium scraper, export redaction, shared-result merging, upload conflicts, automatic publishing, opt-out and local-data preservation on failure. Unit tests use fake LLM responses and do not require Ollama. Browser checks cover language and theme switching, saved preferences, filters and job details. These checks do not establish the SRS quality metrics on real annotated postings.
