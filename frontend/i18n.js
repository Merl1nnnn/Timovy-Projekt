'use strict';
const MESSAGES = {
  sk: {
    locale: 'sk-SK', title: 'SkillMiner — prehľad pracovných ponúk', language: 'Jazyk', theme: 'Téma', light: 'Svetlá', dark: 'Tmavá',
    eyebrow: 'ANALÝZA TRHU · SLOVENSKO', hero: 'Zručnosti, ktoré formujú IT trh.', intro: 'Prehľad pracovných ponúk a výsledkov lokálnej NLP analýzy.', loading: 'Načítavajú sa údaje…', synthetic: 'Syntetický súbor', published: 'Skutočné ponuky · Profesia.sk', updated: 'Aktualizované:',
    syntheticNotice: 'Demonštračné údaje: syntetické ponuky z lokálnych testovacích webov. Nejde o štatistiku skutočného trhu práce.', realNotice: 'Skutočné ponuky z Profesia.sk spracované automatickou analýzou. Neoverené záznamy môžu obsahovať chyby.', datasetSwitch: 'Súbor údajov', dataMock: 'Testovacie', dataReal: 'Skutočné', realMissingShort: 'Skutočné údaje nie sú zverejnené', realMissing: 'Skutočné ponuky zatiaľ nie sú zverejnené. Tím ich zverejní ručne po kontrole a schválení použitia údajov.',
    metrics: 'Ukazovatele', count: 'Ponuky vo výbere', skills: 'Unikátne zručnosti', review: 'Označené na kontrolu', remote: 'Na diaľku / hybridne',
    filters: 'Filtre', search: 'Vyhľadávanie', searchPlaceholder: 'Názov, spoločnosť, zručnosť…', specialization: 'Špecializácia', seniority: 'Úroveň', site: 'Zdroj', allSpecializations: 'Všetky špecializácie', allLevels: 'Všetky úrovne', allSources: 'Všetky zdroje', doubtful: 'Iba sporné záznamy', reset: 'Zrušiť filtre', asideNote: 'Výsledky sa spracúvajú lokálne. Web zobrazuje posledný zverejnený súbor.',
    rankRequired: 'Požadované', rankNice: 'Výhodou', rankMode: 'Typ zručností', summary: 'Stručne o pozícii', facts: 'Požiadavky', experience: 'Prax', experienceYears: 'min. {n} r.', noExperience: 'bez praxe', education: 'Vzdelanie', edu_secondary: 'stredoškolské', edu_bachelor: 'VŠ I. stupňa', edu_master: 'VŠ II. stupňa', edu_phd: 'VŠ III. stupňa (PhD)', noSummary: 'Popis nie je k dispozícii.', technologiesSample: 'Zručnosti vo výbere', jobCount: 'Počet ponúk', postings: 'Pracovné ponuky', export: 'Export CSV ↓', more: 'Zobraziť ďalšie', footer: 'SkillMiner · Študentský tímový projekt', pipeline: 'Lokálne spracovanie → verejné výsledky', close: 'Zavrieť',
    results: 'Výsledky: {n}', empty: 'Žiadne ponuky nezodpovedajú týmto filtrom.', unspecified: 'Neuvedené', untitled: 'Bez názvu', noLocation: 'Mesto neuvedené', noLevel: 'Úroveň neuvedená', needsReview: 'Vyžaduje kontrolu', salaryNote: 'Brutto / mesiac · výstup modelu', details: 'Podrobnosti ↗',
    required: 'Požadované zručnosti', nice: 'Výhodou', technologies: 'Technológie', quality: 'Kontrola kvality', confidence: 'Skóre pravidiel: {score}. Ide o heuristiku, nie o pravdepodobnosť správnosti.', model: 'Model:', sourceLink: 'Otvoriť zdroj ↗', localSource: 'Zdroj je lokálny testovací web; z internetu nie je dostupný.', evidence: 'Aktuálna schéma parsera zatiaľ nepodporuje dôkazové citácie.', unavailable: 'Údaje nie sú dostupné', invalidData: 'Neplatný formát údajov', loadError: 'Údaje sa nepodarilo načítať: {error}. Skúste obnoviť stránku.'
  },
  en: {
    locale: 'en-GB', title: 'SkillMiner — job overview', language: 'Language', theme: 'Theme', light: 'Light', dark: 'Dark',
    eyebrow: 'MARKET ANALYSIS · SLOVAKIA', hero: 'Skills shaping the IT market.', intro: 'Explore job postings and results from local NLP analysis.', loading: 'Loading data…', synthetic: 'Synthetic dataset', published: 'Real postings · Profesia.sk', updated: 'Updated:',
    syntheticNotice: 'Demo data: synthetic jobs from local mock sites. These are not statistics from the real labour market.', realNotice: 'Real postings from Profesia.sk processed by automated analysis. Unverified records may contain errors.', datasetSwitch: 'Dataset', dataMock: 'Mock', dataReal: 'Real', realMissingShort: 'Real data not published', realMissing: 'Real postings have not been published yet. The team publishes them manually after review and approval to use the data.',
    metrics: 'Metrics', count: 'Jobs in selection', skills: 'Unique skills', review: 'Flagged for review', remote: 'Remote / hybrid',
    filters: 'Filters', search: 'Search', searchPlaceholder: 'Title, company, skill…', specialization: 'Specialisation', seniority: 'Seniority', site: 'Source', allSpecializations: 'All specialisations', allLevels: 'All levels', allSources: 'All sources', doubtful: 'Flagged records only', reset: 'Reset filters', asideNote: 'Results are processed locally. This site shows the latest published dataset.',
    rankRequired: 'Required', rankNice: 'Nice to have', rankMode: 'Skill type', summary: 'About the role', facts: 'Requirements', experience: 'Experience', experienceYears: '{n}+ yrs', noExperience: 'none required', education: 'Education', edu_secondary: 'secondary', edu_bachelor: 'bachelor', edu_master: 'master', edu_phd: 'PhD', noSummary: 'No description available.', technologiesSample: 'Skills in selection', jobCount: 'Number of jobs', postings: 'Job postings', export: 'Export CSV ↓', more: 'Show more', footer: 'SkillMiner · Student team project', pipeline: 'Local processing → public results', close: 'Close',
    results: 'Results: {n}', empty: 'No jobs match these filters.', unspecified: 'Not specified', untitled: 'Untitled', noLocation: 'City not specified', noLevel: 'Level not specified', needsReview: 'Needs review', salaryNote: 'Gross / month · model output', details: 'Details ↗',
    required: 'Required skills', nice: 'Nice-to-have skills', technologies: 'Technologies', quality: 'Quality check', confidence: 'Rule score: {score}. This is a heuristic, not a probability of correctness.', model: 'Model:', sourceLink: 'Open source ↗', localSource: 'The source is a local mock site and is not accessible online.', evidence: 'The current parser schema does not support evidence quotes yet.', unavailable: 'Data unavailable', invalidData: 'Invalid data format', loadError: 'Could not load data: {error}. Try refreshing the page.'
  },
  uk: {
    locale: 'uk-UA', title: 'SkillMiner — огляд вакансій', language: 'Мова', theme: 'Тема', light: 'Світла', dark: 'Темна',
    eyebrow: 'АНАЛІЗ РИНКУ · СЛОВАЧЧИНА', hero: 'Навички, що формують ринок IT.', intro: 'Огляд вакансій і результатів локального NLP-аналізу.', loading: 'Завантаження даних…', synthetic: 'Синтетичний набір', published: 'Реальні вакансії · Profesia.sk', updated: 'Оновлено:',
    syntheticNotice: 'Демонстраційні дані: синтетичні вакансії з локальних мок-сайтів. Це не статистика реального ринку праці.', realNotice: 'Реальні вакансії з Profesia.sk, оброблені автоматичним аналізом. Неперевірені записи можуть містити помилки.', datasetSwitch: 'Набір даних', dataMock: 'Мокові', dataReal: 'Реальні', realMissingShort: 'Реальні дані не опубліковані', realMissing: 'Реальні вакансії ще не опубліковані. Команда публікує їх вручну після перевірки й дозволу на використання даних.',
    metrics: 'Показники', count: 'Вакансії у вибірці', skills: 'Унікальні навички', review: 'Позначено для перевірки', remote: 'Дистанційно / гібрид',
    filters: 'Фільтри', search: 'Пошук', searchPlaceholder: 'Назва, компанія, навичка…', specialization: 'Спеціалізація', seniority: 'Рівень', site: 'Джерело', allSpecializations: 'Усі спеціалізації', allLevels: 'Усі рівні', allSources: 'Усі джерела', doubtful: 'Лише сумнівні', reset: 'Скинути фільтри', asideNote: 'Результати обробляються локально. На сайті показано останній опублікований набір.',
    rankRequired: 'Обов’язкові', rankNice: 'Бажані', rankMode: 'Тип навичок', summary: 'Коротко про вакансію', facts: 'Вимоги', experience: 'Досвід', experienceYears: 'від {n} р.', noExperience: 'без досвіду', education: 'Освіта', edu_secondary: 'середня', edu_bachelor: 'бакалавр', edu_master: 'магістр', edu_phd: 'PhD', noSummary: 'Опису немає.', technologiesSample: 'Навички у вибірці', jobCount: 'Кількість вакансій', postings: 'Вакансії', export: 'Експорт CSV ↓', more: 'Показати ще', footer: 'SkillMiner · Навчальний командний проєкт', pipeline: 'Локальна обробка → публічні результати', close: 'Закрити',
    results: 'Результатів: {n}', empty: 'За цими фільтрами вакансій немає.', unspecified: 'Не вказано', untitled: 'Без назви', noLocation: 'Місто не вказано', noLevel: 'Рівень не вказано', needsReview: 'Потребує перевірки', salaryNote: 'Брутто / місяць · результат моделі', details: 'Деталі ↗',
    required: 'Обов’язкові навички', nice: 'Бажані навички', technologies: 'Технології', quality: 'Перевірка якості', confidence: 'Оцінка правил: {score}. Це евристика, а не ймовірність правильності.', model: 'Модель:', sourceLink: 'Відкрити джерело ↗', localSource: 'Джерело — локальний мок-сайт; з інтернету недоступне.', evidence: 'Цитати-докази поки не підтримуються поточною схемою парсера.', unavailable: 'Дані недоступні', invalidData: 'Неправильний формат даних', loadError: 'Не вдалося завантажити дані: {error}. Спробуйте оновити сторінку.'
  }
};
function readPreference(key) { try { return localStorage.getItem(key); } catch { return null; } }
function savePreference(key, value) { try { localStorage.setItem(key, value); } catch { /* Private browsing may disable storage. */ } }
function t(key, values = {}) {
  return (MESSAGES[language][key] ?? MESSAGES.en[key] ?? key)
    .replace(/\{(\w+)\}/g, (_, name) => values[name] ?? '');
}

const DASHBOARD_MESSAGES = {
  en: {
    navigation: 'Dashboard navigation', overview: 'Overview', analytics: 'Analytics',
    dashboardTitle: 'IT jobs dashboard', dashboardIntro: 'Explore vacancies, hiring activity and advertised pay.',
    syntheticNotice: 'Demo dataset · Vacancies, company sizes and example histories are synthetic.',
    checked: 'Snapshot checked {date}', refreshError: 'The latest snapshot could not be loaded. Showing the previous snapshot.',
    mockRunning: 'Checking the local demo sources…', mockFailed: 'The local demo check failed.',
    changes: 'Changes in vacancies', noChanges: 'No vacancy changes have been recorded.',
    position: 'Position', company: 'Company', location: 'City', allLocations: 'All cities', salary: 'Salary',
    company_size: 'Company size', company_headcount: 'Employees', headcount: '{n} employees',
    allSizes: 'All sizes', small: 'Small · 1–49', medium: 'Medium · 50–249', large: 'Large · 250+', unknown: 'Unknown',
    possibleDuplicates: 'Possible duplicates', copies: '{n} linked sources', demoLink: 'Demo link ↗',
    salary_period: 'Pay period', month: 'month', hour: 'hour', year: 'year',
    activity: 'Vacancies over time', activityNote: 'Unique active vacancies, new listings and updates for the selected filters.',
    period: 'Time range', last7: 'Last 7 days', last30: 'Last 30 days', last90: 'Last 90 days',
    active: 'Active', added: 'New', updatedSeries: 'Changed', date: 'Date', chartValues: 'View chart data',
    distribution: 'Vacancy distribution', salaryHistory: 'Salary history', salaryMinimum: 'Advertised minimum',
    historyNote: 'Minimum salary at each recorded change. The table shows the full advertised range.',
    noHistory: 'There are no comparable salary changes for this vacancy yet.',
    payComparison: 'Pay by company size', payMethod: 'Median advertised minimum by size. The smallest group with salary data is the reference. Each currency and pay period is shown separately.',
    baseline: 'Reference', difference: 'Difference', sample: 'Vacancies', noSalaryData: 'No comparable salaries for these filters.',
    firstSeen: 'First seen', lastSeen: 'Last checked', lastChanged: 'Last updated', publishedDate: 'Published',
    employment_type: 'Employment type', required_skills: 'Required skills', nice_to_have_skills: 'Nice-to-have skills',
    salary_min: 'Minimum salary', salary_max: 'Maximum salary', salary_currency: 'Currency',
    yes: 'Yes', no: 'No', titleField: 'Job title', showingPeriod: 'Showing period {period}', clearPeriod: 'Clear period',
    queueEmpty: 'No history available for this selection.'
  },
  sk: {
    navigation: 'Navigácia prehľadu', overview: 'Prehľad', analytics: 'Analytika',
    dashboardTitle: 'Prehľad IT ponúk', dashboardIntro: 'Pracovné ponuky, vývoj dopytu a zverejnené mzdy.',
    syntheticNotice: 'Demo údaje · Ponuky, veľkosti firiem a ukážková história sú syntetické.',
    checked: 'Snímka skontrolovaná {date}', refreshError: 'Najnovšiu snímku sa nepodarilo načítať. Zobrazuje sa predchádzajúca snímka.',
    mockRunning: 'Kontrolujú sa lokálne demo zdroje…', mockFailed: 'Kontrola lokálnych demo zdrojov zlyhala.',
    changes: 'Zmeny v ponukách', noChanges: 'Zatiaľ neboli zaznamenané žiadne zmeny ponúk.',
    position: 'Pozícia', company: 'Spoločnosť', location: 'Mesto', allLocations: 'Všetky mestá', salary: 'Mzda',
    company_size: 'Veľkosť firmy', company_headcount: 'Zamestnanci', headcount: 'Počet zamestnancov: {n}',
    allSizes: 'Všetky veľkosti', small: 'Malá · 1–49', medium: 'Stredná · 50–249', large: 'Veľká · 250+', unknown: 'Neznáma',
    possibleDuplicates: 'Možné duplikáty', copies: 'Priradené zdroje: {n}', demoLink: 'Demo odkaz ↗',
    salary_period: 'Obdobie mzdy', month: 'mesiac', hour: 'hodina', year: 'rok',
    activity: 'Vývoj pracovných ponúk', activityNote: 'Unikátne aktívne, nové a zmenené ponuky podľa zvolených filtrov.',
    period: 'Obdobie', last7: 'Posledných 7 dní', last30: 'Posledných 30 dní', last90: 'Posledných 90 dní',
    active: 'Aktívne', added: 'Nové', updatedSeries: 'Zmenené', date: 'Dátum', chartValues: 'Zobraziť hodnoty grafu',
    distribution: 'Rozdelenie ponúk', salaryHistory: 'História mzdy', salaryMinimum: 'Zverejnené minimum',
    historyNote: 'Minimálna mzda pri každej zaznamenanej zmene. Tabuľka uvádza celé zverejnené rozpätie.',
    noHistory: 'Táto ponuka zatiaľ nemá porovnateľné zmeny mzdy.',
    payComparison: 'Mzdy podľa veľkosti firmy', payMethod: 'Medián zverejneného minima. Referenciou je najmenšia skupina s údajmi o mzde. Meny a obdobia mzdy sú uvedené samostatne.',
    baseline: 'Referencia', difference: 'Rozdiel', sample: 'Ponuky', noSalaryData: 'Pre tieto filtre nie sú dostupné porovnateľné mzdy.',
    firstSeen: 'Prvý záznam', lastSeen: 'Posledná kontrola', lastChanged: 'Posledná zmena', publishedDate: 'Zverejnené',
    employment_type: 'Typ úväzku', required_skills: 'Požadované zručnosti', nice_to_have_skills: 'Zručnosti výhodou',
    salary_min: 'Minimálna mzda', salary_max: 'Maximálna mzda', salary_currency: 'Mena',
    yes: 'Áno', no: 'Nie', titleField: 'Názov pozície', showingPeriod: 'Obdobie {period}', clearPeriod: 'Zrušiť výber obdobia',
    queueEmpty: 'Pre tento výber nie je dostupná história.'
  },
  uk: {
    navigation: 'Навігація дашбордом', overview: 'Огляд', analytics: 'Аналітика',
    dashboardTitle: 'Дашборд IT-вакансій', dashboardIntro: 'Вакансії, динаміка найму й оголошені зарплати.',
    syntheticNotice: 'Демодані · Вакансії, розміри компаній та приклади історії вигадані.',
    checked: 'Знімок перевірено {date}', refreshError: 'Останній знімок недоступний. Показуємо попередній знімок.',
    mockRunning: 'Перевіряємо локальні демоджерела…', mockFailed: 'Не вдалося перевірити локальні демоджерела.',
    changes: 'Зміни у вакансіях', noChanges: 'Змін у вакансіях ще не зафіксовано.',
    position: 'Посада', company: 'Компанія', location: 'Місто', allLocations: 'Усі міста', salary: 'Зарплата',
    company_size: 'Розмір компанії', company_headcount: 'Працівники', headcount: 'Працівників: {n}',
    allSizes: 'Усі розміри', small: 'Мала · 1–49', medium: 'Середня · 50–249', large: 'Велика · 250+', unknown: 'Невідомо',
    possibleDuplicates: 'Можливі дублікати', copies: 'Пов’язані джерела: {n}', demoLink: 'Демопосилання ↗',
    salary_period: 'Період оплати', month: 'місяць', hour: 'година', year: 'рік',
    activity: 'Динаміка вакансій', activityNote: 'Унікальні активні, нові та змінені вакансії за вибраними фільтрами.',
    period: 'Період', last7: 'Останні 7 днів', last30: 'Останні 30 днів', last90: 'Останні 90 днів',
    active: 'Активні', added: 'Нові', updatedSeries: 'Змінені', date: 'Дата', chartValues: 'Показати дані графіка',
    distribution: 'Розподіл вакансій', salaryHistory: 'Історія зарплати', salaryMinimum: 'Оголошений мінімум',
    historyNote: 'Мінімальна зарплата на дату кожної зміни. У таблиці наведено повний оголошений діапазон.',
    noHistory: 'Для цієї вакансії ще немає порівнюваних змін зарплати.',
    payComparison: 'Зарплати за розміром компанії', payMethod: 'Медіана оголошеної нижньої межі. База порівняння — найменша група з даними про зарплати. Валюти й періоди оплати показано окремо.',
    baseline: 'База', difference: 'Різниця', sample: 'Вакансії', noSalaryData: 'За цими фільтрами немає порівнюваних зарплат.',
    firstSeen: 'Уперше помічено', lastSeen: 'Остання перевірка', lastChanged: 'Остання зміна', publishedDate: 'Опубліковано',
    employment_type: 'Тип зайнятості', required_skills: 'Обов’язкові навички', nice_to_have_skills: 'Бажані навички',
    salary_min: 'Мінімальна зарплата', salary_max: 'Максимальна зарплата', salary_currency: 'Валюта',
    yes: 'Так', no: 'Ні', titleField: 'Назва вакансії', showingPeriod: 'Період {period}', clearPeriod: 'Скинути період',
    queueEmpty: 'Для цієї вибірки немає історії.'
  }
};
for (const [code, messages] of Object.entries(DASHBOARD_MESSAGES)) Object.assign(MESSAGES[code], messages);
