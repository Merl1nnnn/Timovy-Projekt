# SkillMiner

Командний проєкт аналізу IT-вакансій. Специфікація: `docs/SRS_SkillMiner_EN.docx` і `docs/SRS_SkillMiner_SK.docx`.

## Публічний фронтенд

`frontend/` — статичний сайт без збірки: пошук, фільтри, частоти технологій, деталі вакансій, позначки якості та CSV. Початковий набір — 101 **синтетична** вакансія з мок-сайтів; результати LLM можуть містити помилки. Це не статистика реального попиту.

Схема: локальний NLP-пайплайн → публічний JSON у GitHub → GitHub Actions → GitHub Pages. Ноутбук не потрібен для перегляду вже опублікованих даних. Публікація оновлює весь знімок; це не база даних і не realtime API.

### Перша публікація

У GitHub відкрийте **Settings → Pages → Build and deployment → Source: GitHub Actions**. Workflow `.github/workflows/pages.yml` публікує тільки `frontend/` після змін у `main`. Сайт: `https://merl1nnnn.github.io/Timovy-Projekt/` (доступний після успішного deployment).

### Локальний перегляд

```sh
python3 -m http.server 8765 --directory frontend
```

Відкрийте `http://localhost:8765`. Запуск через `file://` не підтримується через fetch JSON.

### Локальне оновлення результатів

Потрібні Python 3.11+ і GitHub CLI (`gh`), авторизована з правом запису в цей репозиторій:

```sh
gh auth login
python3 scripts/publish_results.py --input '/absolute/path/to/data/parsed/jobs.jsonl' --dry-run
# Після перевірки сформованого frontend/data/jobs.json:
python3 scripts/publish_results.py --input '/absolute/path/to/data/parsed/jobs.jsonl'
```

За замовчуванням набір позначається як синтетичний. Для перевірених реальних даних використовуйте `--kind real` після перевірки дозволу на публікацію та персональних даних. Скрипт передає тільки явно дозволені поля, не передає HTML або .env, прибирає email та міжнародні номери телефонів. Це не повна анонімізація: імена та інші персональні дані потрібно прибрати в пайплайні до експорту.

`GITHUB_TOKEN` із правом Contents: write може замінити gh-авторизацію. Токен ніколи не додавайте у frontend чи git. Оновлення змінює тільки `frontend/data/jobs.json`; інші файли не перезаписуються. Попередній знімок лишається в Git-історії. Якщо інший учасник одночасно оновив JSON, SHA-конфлікт зупиняє запис — запустіть повторно.

Лише підготовка без мережевих запитів:

```sh
python3 scripts/export_results.py --input '/absolute/path/to/jobs.jsonl'
python3 -m unittest discover -s tests -v
```

Тести перевіряють whitelist, видалення email/телефону, дедуплікацію й збереження попередньої публікації при некоректному вході.
