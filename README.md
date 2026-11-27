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

#### Daily collection on a server

`scraper/profesia_daily.py` only collects pages and never runs the parser. It is meant to run once a day, so data builds up over a longer period:

```sh
uv run python -m scraper.profesia_daily
```

Each run:

- walks the whole category list (about 60 pages) and records which postings are still listed (`last_seen`);
- downloads new postings;
- re-checks listed postings once every 7 days (`--refresh-days`). If the text changed, the new version replaces `<id>.html` and the previous one moves to `history/<id>/`;
- sets `removed_at` on postings missing from two complete list walks in a row, or answering 404;
- appends its statistics to `runs.jsonl`.

It writes to the same `data/real/raw/profesia/` as `profesia_live`, with the same politeness rules. The extra index fields (`first_seen`, `last_seen`, `checked_at`, `updated_at`, `removed_at`, `versions`) are ignored by the parser, and `profesia_live` works as before. The first run downloads the whole category (about 1,100 postings, roughly 1.5 h). Later runs take about 15–20 minutes.

#### Collection service on TUKE Coolify

`scraper/collector_server.py` wraps the daily collection in a small HTTP service for a container. It runs the collection every day at `COLLECT_AT_UTC` (default 03:30 UTC). After a start or redeploy it also runs right away if the last run began more than 20 hours ago. Every endpoint except `/health` needs `Authorization: Bearer <COLLECTOR_TOKEN>`, because the repository is public and the collected postings must not be:

| Endpoint | What it does |
| --- | --- |
| `GET /health` | `ok`, for the container health check |
| `GET /status` | posting counts, next run, the last 10 runs (failed runs have `error`) |
| `GET /download` | the whole `data/real/raw/` as `.tar.gz` |
| `POST /collect` | starts a run now (`409` while one is running) |

The image (`deploy/collector.Dockerfile`) contains only the collector and `httpx`. Data lives in the named volume `collector-data`, mounted at `/app/data/real`.

1. Generate a token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. In Coolify, create a new resource: **Public Repository** `https://github.com/Merl1nnnn/Timovy-Projekt`, branch `feature/daily-collector` (or `main` once merged), build pack **Docker Compose**, Docker Compose Location `/deploy/compose.collector.yaml`.
3. In the resource's environment variables, set `COLLECTOR_TOKEN` (and optionally `COLLECT_AT_UTC`). Without a token of at least 16 characters, the service does not start.
4. Give the `collector` service a domain with port 8000, e.g. `https://skillminer-data.student.kpi.fei.tuke.sk:8000`, then deploy. The first collection starts immediately and is visible in the resource's logs.

Check progress and download the data (PowerShell, `curl.exe` is part of Windows):

```powershell
$h = "Authorization: Bearer <token>"
curl.exe -H $h https://skillminer-data.student.kpi.fei.tuke.sk/status
curl.exe -H $h https://skillminer-data.student.kpi.fei.tuke.sk/download -o server_raw.tar.gz
mkdir data/real/server_raw; tar xzf server_raw.tar.gz -C data/real/server_raw
```

Extract it next to the local data, not over `data/real/raw/`. The gold set's postings may have newer versions on the server. The volume is the only copy, so download a backup from time to time. Deleting the resource together with its volume deletes the data.

Without Coolify, `deploy/skillminer-collect.service` and `.timer` run `scraper.profesia_daily` once a day under systemd. Copy them to `/etc/systemd/system/` and run `systemctl enable --now skillminer-collect.timer`.

#### Evaluate against the gold set

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
