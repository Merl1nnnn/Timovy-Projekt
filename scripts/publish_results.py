"""Публікація локальних результатів на спільному сайті GitHub Pages."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

if __package__:
    from .export_results import export
else:
    from export_results import export

REPOSITORY = 'Merl1nnnn/Timovy-Projekt'
PATH = 'frontend/data/jobs.json'


class PublishConflict(RuntimeError):
    pass


def api(token, method, endpoint, body=None):
    req = urllib.request.Request('https://api.github.com' + endpoint,
        data=json.dumps(body).encode() if body is not None else None,
        method=method, headers={'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'SkillMiner-local-publisher'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (409, 422):
            raise PublishConflict('Конфлікт публікації; дані на сайті змінилися') from None
        messages = {401: 'Потрібна чинна авторизація (gh auth login)',
                    403: 'Недостатньо прав Contents: write або перевищено ліміт',
                    404: 'Репозиторій, гілку або файл даних не знайдено'}
        raise RuntimeError(messages.get(error.code, f'GitHub HTTP {error.code}')) from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError('GitHub недоступний; локальні результати збережено') from error


def auth_token():
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    gh = shutil.which('gh')
    local_gh = Path.home() / '.local/opt/gh/bin/gh'
    if not gh and local_gh.is_file():
        gh = str(local_gh)
    if not token and gh:
        try:
            auth = subprocess.run([gh, 'auth', 'token', '--hostname', 'github.com'],
                                  capture_output=True, text=True, timeout=15)
        except subprocess.TimeoutExpired:
            raise RuntimeError('Авторизація GitHub не відповідає; виконайте gh auth login') from None
        if auth.returncode == 0:
            token = auth.stdout.strip()
    if not token:
        raise RuntimeError('Виконайте gh auth login; потрібне право запису в спільний репозиторій')
    return token


def merge_snapshots(previous, local):
    if previous.get('schema_version') != 1 or not isinstance(previous.get('jobs'), list):
        raise RuntimeError('Невідома схема опублікованих даних; запис зупинено')
    if previous['jobs'] and previous.get('dataset_kind') != local['dataset_kind']:
        raise RuntimeError('Не можна змішувати синтетичні та реальні дані в одному наборі')
    # Зберігаємо вакансії інших учасників. Для однакового URL перемагає новіший parsed_at.
    by_url = {}
    for job in previous['jobs'] + local['jobs']:
        url = job.get('source_url')
        if not isinstance(url, str) or not url:
            raise RuntimeError('Кожна опублікована вакансія повинна мати source_url')
        existing = by_url.get(url)
        def stamp(item):
            try:
                dt = datetime.fromisoformat(item.get('parsed_at', '').replace('Z', '+00:00'))
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            except (ValueError, TypeError, AttributeError):
                return datetime.min.replace(tzinfo=timezone.utc)
        if existing is None or stamp(job) >= stamp(existing):
            by_url[url] = job
    return {**local, 'jobs': list(by_url.values())}


def publish(source, *, output=None, kind='synthetic', repository=None, branch=None, token=None, request=None):
    output = output or source.parent / 'public_jobs.json'
    local = export(source, output, kind)
    token = token or auth_token()
    repository = repository or os.getenv('SKILLMINER_REPOSITORY', REPOSITORY)
    branch = branch or os.getenv('SKILLMINER_BRANCH', 'main')
    request = request or api
    endpoint = f'/repos/{repository}/contents/{PATH}'
    for attempt in range(3):
        previous = request(token, 'GET', endpoint + '?ref=' + urllib.parse.quote(branch, safe=''))
        if previous.get('encoding') != 'base64':
            raise RuntimeError('Непідтримуваний формат GitHub Contents; запис зупинено')
        remote = json.loads(base64.b64decode(previous['content']))
        merged = merge_snapshots(remote, local)
        if remote['jobs'] == merged['jobs'] and remote.get('dataset_kind') == kind:
            return {'changed': False, 'count': len(merged['jobs']), 'url': None}
        try:
            result = request(token, 'PUT', endpoint, {'message': 'Update shared NLP results',
                'branch': branch, 'sha': previous['sha'],
                'content': base64.b64encode(json.dumps(merged, ensure_ascii=False, indent=2).encode()).decode()})
        except PublishConflict:
            if attempt == 2:
                raise
            continue
        return {'changed': True, 'count': len(merged['jobs']), 'url': result['commit']['html_url']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--kind', choices=['synthetic', 'real'], default='synthetic')
    ap.add_argument('--repository', default=None)
    ap.add_argument('--branch', default=None)
    ap.add_argument('--output', type=Path, default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    output = args.output or args.input.parent / 'public_jobs.json'
    if args.dry_run:
        payload = export(args.input, output, args.kind)
        print(f"Підготовлено {len(payload['jobs'])} публічних записів: {output}")
        return
    result = publish(args.input, output=output, kind=args.kind,
                     repository=args.repository, branch=args.branch)
    print('Опубліковано: ' + result['url'] if result['changed'] else 'На сайті вже актуальні результати; новий коміт не потрібен')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        raise SystemExit(str(error))
