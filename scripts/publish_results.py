"""Експортувати локальні результати та оновити тільки frontend/data/jobs.json у GitHub."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from export_results import export

REPOSITORY = 'Merl1nnnn/Timovy-Projekt'
PATH = 'frontend/data/jobs.json'


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
        if error.code == 401:
            raise RuntimeError('GitHub: потрібна чинна авторизація (gh auth login)') from None
        if error.code == 403:
            raise RuntimeError('GitHub: недостатньо прав на запис Contents або перевищено ліміт') from None
        raise RuntimeError(f'GitHub HTTP {error.code}; зміни не підтверджено') from None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--kind', choices=['synthetic', 'real'], default='synthetic')
    ap.add_argument('--branch', default='main')
    ap.add_argument('--output', type=Path, default=Path('frontend/data/jobs.json'))
    ap.add_argument('--dry-run', action='store_true', help='Підготувати JSON без публікації')
    args = ap.parse_args()
    payload = export(args.input, args.output, args.kind)
    print(f"Підготовлено {len(payload['jobs'])} публічних записів: {args.output}")
    if args.dry_run:
        return
    token = os.environ.get('GITHUB_TOKEN')
    gh = shutil.which('gh')
    local_gh = Path.home() / '.local/opt/gh/bin/gh'
    if not gh and local_gh.is_file():
        gh = str(local_gh)
    if not token and gh:
        auth = subprocess.run([gh, 'auth', 'token', '--hostname', 'github.com'],
                              capture_output=True, text=True)
        if auth.returncode == 0:
            token = auth.stdout.strip()
    if not token:
        ap.error('Виконайте gh auth login або задайте GITHUB_TOKEN із правом Contents: write')
    endpoint = f'/repos/{REPOSITORY}/contents/{PATH}'
    # SHA забезпечує захист від паралельного перезапису. Конфлікт потребує повторного запуску.
    previous = api(token, 'GET', endpoint + '?ref=' + urllib.parse.quote(args.branch, safe=''))
    result = api(token, 'PUT', endpoint, {'message': 'Update published NLP results',
        'branch': args.branch, 'sha': previous['sha'],
        'content': base64.b64encode(args.output.read_bytes()).decode('ascii')})
    print('Опубліковано коміт: ' + result['commit']['html_url'])
    print('Оновлення сайту запустить GitHub Actions. Перевірте статус workflow.')


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error))
