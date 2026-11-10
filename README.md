# SkillMiner

A student team project for analysing IT job postings and mapping skills to ESCO. Requirements: [English SRS](docs/SRS_SkillMiner_EN.docx) · [Slovak SRS](docs/SRS_SkillMiner_SK.docx).

## Public dashboard

**Live site: https://merl1nnnn.github.io/Timovy-Projekt/**

The static dashboard in `frontend/` supports search, filters, technology frequencies, job details, quality flags and CSV export. The interface is available in **Slovak, English and Ukrainian**, with **light and dark themes**. Preferences are saved in the browser. Job titles and extracted data remain in their original language.

The initial dataset contains **101 synthetic postings from local mock sites**. LLM results may contain errors. These are not statistics from the real labour market.

## How publishing works

Local NLP pipeline → public JSON in GitHub → GitHub Actions → GitHub Pages.

The laptop is needed only to process and upload new results. Published data stays available when the laptop is off. Each upload replaces the complete dataset snapshot; this is not a database or a realtime API.

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

Review `frontend/data/jobs.json`, then publish:

```sh
python3 scripts/publish_results.py --input '/absolute/path/to/data/parsed/jobs.jsonl'
```

The script updates only `frontend/data/jobs.json` on `main`. GitHub Actions then deploys the updated site. Earlier snapshots remain in Git history. A concurrent update causes a SHA conflict instead of silently overwriting someone else's changes; rerun the command after reviewing the latest data.

Datasets are marked as synthetic by default. Use `--kind real` only after checking publication permissions and removing personal data upstream.

Authentication uses GitHub CLI or `GITHUB_TOKEN` with **Contents: write** access. Never put tokens in frontend files or commit them. The export includes only explicitly allowed fields, excludes raw HTML and `.env`, and redacts email addresses and international phone numbers. This is not complete anonymisation: names and other personal information must be removed in the processing pipeline before export.

To prepare JSON without making network requests:

```sh
python3 scripts/export_results.py --input '/absolute/path/to/jobs.jsonl'
```

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The export tests cover the field allowlist, email and phone redaction, URL deduplication, and preservation of the previous published file when input is invalid. Browser checks cover language and theme switching, saved preferences, filters and job details.
