'use strict';
const MESSAGES = {
  sk: {
    locale: 'sk-SK', title: 'SkillMiner — prehľad pracovných ponúk', language: 'Jazyk', theme: 'Téma', light: 'Svetlá', dark: 'Tmavá',
    eyebrow: 'ANALÝZA TRHU · SLOVENSKO', hero: 'Zručnosti, ktoré formujú IT trh.', intro: 'Prehľad pracovných ponúk a výsledkov lokálnej NLP analýzy.', loading: 'Načítavajú sa údaje…', synthetic: 'Syntetický súbor', published: 'Zverejnený súbor', updated: 'Aktualizované:',
    syntheticNotice: 'Demonštračné údaje: syntetické ponuky z lokálnych testovacích webov. Nejde o štatistiku skutočného trhu práce.', realNotice: 'Zverejnené výsledky automatickej analýzy. Neoverené záznamy môžu obsahovať chyby.',
    metrics: 'Ukazovatele', count: 'Ponuky vo výbere', skills: 'Unikátne technológie', review: 'Označené na kontrolu', remote: 'Na diaľku / hybridne',
    filters: 'Filtre', search: 'Vyhľadávanie', searchPlaceholder: 'Názov, spoločnosť, zručnosť…', specialization: 'Špecializácia', seniority: 'Úroveň', site: 'Zdroj', allSpecializations: 'Všetky špecializácie', allLevels: 'Všetky úrovne', allSources: 'Všetky zdroje', doubtful: 'Iba sporné záznamy', reset: 'Zrušiť filtre', asideNote: 'Výsledky sa spracúvajú lokálne. Web zobrazuje posledný zverejnený súbor.',
    technologiesSample: 'Technológie vo výbere', jobCount: 'Počet ponúk', postings: 'Pracovné ponuky', export: 'Export CSV ↓', more: 'Zobraziť ďalšie', footer: 'SkillMiner · Študentský tímový projekt', pipeline: 'Lokálne spracovanie → verejné výsledky', close: 'Zavrieť',
    results: 'Výsledky: {n}', empty: 'Žiadne ponuky nezodpovedajú týmto filtrom.', unspecified: 'Neuvedené', untitled: 'Bez názvu', noLocation: 'Mesto neuvedené', noLevel: 'Úroveň neuvedená', needsReview: 'Vyžaduje kontrolu', salaryNote: 'Brutto / mesiac · výstup modelu', details: 'Podrobnosti ↗',
    required: 'Požadované zručnosti', nice: 'Výhodou', technologies: 'Technológie', quality: 'Kontrola kvality', confidence: 'Skóre pravidiel: {score}. Ide o heuristiku, nie o pravdepodobnosť správnosti.', model: 'Model:', sourceLink: 'Otvoriť zdroj ↗', localSource: 'Zdroj je lokálny testovací web; z internetu nie je dostupný.', evidence: 'Aktuálna schéma parsera zatiaľ nepodporuje dôkazové citácie.', unavailable: 'Údaje nie sú dostupné', invalidData: 'Neplatný formát údajov', loadError: 'Údaje sa nepodarilo načítať: {error}. Skúste obnoviť stránku.'
  },
  en: {
    locale: 'en-GB', title: 'SkillMiner — job overview', language: 'Language', theme: 'Theme', light: 'Light', dark: 'Dark',
    eyebrow: 'MARKET ANALYSIS · SLOVAKIA', hero: 'Skills shaping the IT market.', intro: 'Explore job postings and results from local NLP analysis.', loading: 'Loading data…', synthetic: 'Synthetic dataset', published: 'Published dataset', updated: 'Updated:',
    syntheticNotice: 'Demo data: synthetic jobs from local mock sites. These are not statistics from the real labour market.', realNotice: 'Published results of automated analysis. Unverified records may contain errors.',
    metrics: 'Metrics', count: 'Jobs in selection', skills: 'Unique technologies', review: 'Flagged for review', remote: 'Remote / hybrid',
    filters: 'Filters', search: 'Search', searchPlaceholder: 'Title, company, skill…', specialization: 'Specialisation', seniority: 'Seniority', site: 'Source', allSpecializations: 'All specialisations', allLevels: 'All levels', allSources: 'All sources', doubtful: 'Flagged records only', reset: 'Reset filters', asideNote: 'Results are processed locally. This site shows the latest published dataset.',
    technologiesSample: 'Technologies in selection', jobCount: 'Number of jobs', postings: 'Job postings', export: 'Export CSV ↓', more: 'Show more', footer: 'SkillMiner · Student team project', pipeline: 'Local processing → public results', close: 'Close',
    results: 'Results: {n}', empty: 'No jobs match these filters.', unspecified: 'Not specified', untitled: 'Untitled', noLocation: 'City not specified', noLevel: 'Level not specified', needsReview: 'Needs review', salaryNote: 'Gross / month · model output', details: 'Details ↗',
    required: 'Required skills', nice: 'Nice-to-have skills', technologies: 'Technologies', quality: 'Quality check', confidence: 'Rule score: {score}. This is a heuristic, not a probability of correctness.', model: 'Model:', sourceLink: 'Open source ↗', localSource: 'The source is a local mock site and is not accessible online.', evidence: 'The current parser schema does not support evidence quotes yet.', unavailable: 'Data unavailable', invalidData: 'Invalid data format', loadError: 'Could not load data: {error}. Try refreshing the page.'
  },
  uk: {
    locale: 'uk-UA', title: 'SkillMiner — огляд вакансій', language: 'Мова', theme: 'Тема', light: 'Світла', dark: 'Темна',
    eyebrow: 'АНАЛІЗ РИНКУ · СЛОВАЧЧИНА', hero: 'Навички, що формують ринок IT.', intro: 'Огляд вакансій і результатів локального NLP-аналізу.', loading: 'Завантаження даних…', synthetic: 'Синтетичний набір', published: 'Опублікований набір', updated: 'Оновлено:',
    syntheticNotice: 'Демонстраційні дані: синтетичні вакансії з локальних мок-сайтів. Це не статистика реального ринку праці.', realNotice: 'Опубліковані результати автоматичного аналізу. Неперевірені записи можуть містити помилки.',
    metrics: 'Показники', count: 'Вакансії у вибірці', skills: 'Унікальні технології', review: 'Позначено для перевірки', remote: 'Дистанційно / гібрид',
    filters: 'Фільтри', search: 'Пошук', searchPlaceholder: 'Назва, компанія, навичка…', specialization: 'Спеціалізація', seniority: 'Рівень', site: 'Джерело', allSpecializations: 'Усі спеціалізації', allLevels: 'Усі рівні', allSources: 'Усі джерела', doubtful: 'Лише сумнівні', reset: 'Скинути фільтри', asideNote: 'Результати обробляються локально. На сайті показано останній опублікований набір.',
    technologiesSample: 'Технології у вибірці', jobCount: 'Кількість вакансій', postings: 'Вакансії', export: 'Експорт CSV ↓', more: 'Показати ще', footer: 'SkillMiner · Навчальний командний проєкт', pipeline: 'Локальна обробка → публічні результати', close: 'Закрити',
    results: 'Результатів: {n}', empty: 'За цими фільтрами вакансій немає.', unspecified: 'Не вказано', untitled: 'Без назви', noLocation: 'Місто не вказано', noLevel: 'Рівень не вказано', needsReview: 'Потребує перевірки', salaryNote: 'Брутто / місяць · результат моделі', details: 'Деталі ↗',
    required: 'Обов’язкові навички', nice: 'Бажані навички', technologies: 'Технології', quality: 'Перевірка якості', confidence: 'Оцінка правил: {score}. Це евристика, а не ймовірність правильності.', model: 'Модель:', sourceLink: 'Відкрити джерело ↗', localSource: 'Джерело — локальний мок-сайт; з інтернету недоступне.', evidence: 'Цитати-докази поки не підтримуються поточною схемою парсера.', unavailable: 'Дані недоступні', invalidData: 'Неправильний формат даних', loadError: 'Не вдалося завантажити дані: {error}. Спробуйте оновити сторінку.'
  }
};
function readPreference(key) { try { return localStorage.getItem(key); } catch { return null; } }
function savePreference(key, value) { try { localStorage.setItem(key, value); } catch { /* Private browsing may disable storage. */ } }
const savedLanguage = readPreference('skillminer-language');
const browserLanguage = navigator.language.split('-')[0];
let language = Object.hasOwn(MESSAGES, savedLanguage) ? savedLanguage : (Object.hasOwn(MESSAGES, browserLanguage) ? browserLanguage : 'sk');
function t(key, values = {}) { return MESSAGES[language][key].replace(/\{(\w+)\}/g, (_, name) => values[name] ?? ''); }
