# Daily Profesia.sk collector (scraper/collector_server.py). Build context: the repository root.
#   docker build -f deploy/collector.Dockerfile -t skillminer-collector .
# Only the collector's own files go in: no Playwright, Ollama, Streamlit or parser models.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY deploy/collector-requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY scraper/__init__.py scraper/profesia_live.py scraper/profesia_daily.py scraper/collector_server.py scraper/
COPY parser/__init__.py parser/html_text.py parser/

# The volume is mounted at /app/data/real; a new named volume takes this owner.
RUN useradd --create-home --uid 10001 collector && mkdir -p /app/data/real && chown -R collector /app/data
USER collector

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["python", "-m", "scraper.collector_server"]
