'use strict';

const interfaceMessages = {
  sk: {
    overview: 'Prehľad', postings: 'Pracovné ponuky', analytics: 'Analytika', filters: 'Filtre',
    settings: 'Nastavenia', about: 'O nás', toggleMenu: 'Rozbaliť alebo zbaliť menu',
    resultsLabel: 'Výsledky', theme: 'Farebný motív', darkMode: 'Tmavý režim', allFilterValues: 'Všetky',
    rowsPerPage: 'Počet ponúk na stránku', defaultPeriod: 'Predvolené obdobie analýzy',
    account: 'Účet', accountDemo: 'Ukážkové tlačidlo bez funkcie.',
    aboutProject: 'SkillMiner je študentský tímový projekt na analýzu IT pracovných ponúk, zručností a miezd.'
  },
  en: {
    settings: 'Settings', about: 'About us', toggleMenu: 'Expand or collapse navigation',
    resultsLabel: 'Results', theme: 'Colour theme', darkMode: 'Dark mode', allFilterValues: 'Any',
    rowsPerPage: 'Job postings per page', defaultPeriod: 'Default analytics period',
    account: 'Account', accountDemo: 'Demo button. It has no action.',
    aboutProject: 'SkillMiner is a student team project for exploring IT vacancies, skills and advertised pay.'
  },
  uk: {
    settings: 'Налаштування', about: 'Про нас', toggleMenu: 'Розгорнути або згорнути меню',
    resultsLabel: 'Результати', theme: 'Колірна тема', darkMode: 'Темний режим', allFilterValues: 'Усі',
    rowsPerPage: 'Вакансій на сторінці', defaultPeriod: 'Типовий період аналітики',
    account: 'Обліковий запис', accountDemo: 'Демонстраційна кнопка без дії.',
    aboutProject: 'SkillMiner — студентський командний проєкт для аналізу IT-вакансій, навичок і зарплат.'
  },
  cs: {
    locale: 'cs-CZ', navigation: 'Hlavní navigace', overview: 'Přehled', postings: 'Pracovní nabídky',
    analytics: 'Analytika', filters: 'Filtry', settings: 'Nastavení', about: 'O nás',
    toggleMenu: 'Rozbalit nebo sbalit nabídku', language: 'Jazyk', theme: 'Barevný motiv',
    resultsLabel: 'Výsledky', darkMode: 'Tmavý režim', light: 'Světlý', dark: 'Tmavý', allFilterValues: 'Libovolné',
    rowsPerPage: 'Počet nabídek na stránku', defaultPeriod: 'Výchozí období analýzy',
    account: 'Účet', accountDemo: 'Ukázkové tlačítko bez funkce.',
    aboutProject: 'SkillMiner je studentský týmový projekt pro analýzu pracovních nabídek v IT, dovedností a mezd.',
    dashboardIntro: 'Pracovní nabídky, vývoj poptávky a zveřejněné mzdy.',
    loading: 'Načítají se data…', synthetic: 'Ukázková data', published: 'Zveřejněná data', updated: 'Aktualizováno:',
    syntheticNotice: 'Ukázková data · Nabídky, velikosti firem a ukázková historie jsou smyšlené.',
    realNotice: 'Zveřejněné výsledky automatické analýzy. Neověřené záznamy mohou obsahovat chyby.',
    checked: 'Kontrola dat {date}', refreshError: 'Nejnovější data nejsou dostupná. Zobrazujeme předchozí stav.',
    mockRunning: 'Kontrolujeme místní testovací zdroje…', mockFailed: 'Kontrola místních zdrojů se nezdařila.',
    metrics: 'Ukazatele', count: 'Nabídky ve výběru', skills: 'Unikátní technologie',
    review: 'Označeno ke kontrole', remote: 'Na dálku / hybridně',
    changes: 'Změny v nabídkách', noChanges: 'Zatím nebyly zaznamenány žádné změny.',
    search: 'Hledat', searchPlaceholder: 'Název, firma, dovednost…', specialization: 'Specializace',
    seniority: 'Úroveň', location: 'Město', site: 'Zdroj', allSpecializations: 'Všechny specializace',
    allLevels: 'Všechny úrovně', allLocations: 'Všechna města', allSources: 'Všechny zdroje',
    company_size: 'Velikost firmy', allSizes: 'Všechny velikosti', small: 'Malá · 1–49',
    medium: 'Střední · 50–249', large: 'Velká · 250+', unknown: 'Neznámá',
    doubtful: 'Pouze sporné záznamy', possibleDuplicates: 'Možné duplicity', reset: 'Zrušit filtry',
    export: 'Export CSV ↓', more: 'Zobrazit další', empty: 'Žádná nabídka neodpovídá těmto filtrům.',
    position: 'Pozice', company: 'Firma', salary: 'Mzda', company_headcount: 'Zaměstnanci',
    headcount: 'Zaměstnanci: {n}', copies: 'Propojené zdroje: {n}', needsReview: 'Vyžaduje kontrolu',
    sourceLink: 'Otevřít zdroj ↗', demoLink: 'Ukázkový odkaz ↗',
    salary_period: 'Období mzdy', month: 'měsíc', hour: 'hodina', year: 'rok',
    activity: 'Vývoj pracovních nabídek', activityNote: 'Unikátní aktivní, nové a změněné nabídky podle vybraných filtrů.',
    period: 'Období', last7: 'Posledních 7 dnů', last30: 'Posledních 30 dnů', last90: 'Posledních 90 dnů',
    active: 'Aktivní', added: 'Nové', updatedSeries: 'Změněné', date: 'Datum', chartValues: 'Zobrazit hodnoty grafu',
    showingPeriod: 'Období {period}', clearPeriod: 'Zrušit výběr období', queueEmpty: 'Pro tento výběr není dostupná historie.',
    distribution: 'Rozdělení nabídek', technologiesSample: 'Technologie ve výběru',
    salaryHistory: 'Historie mzdy', salaryMinimum: 'Zveřejněné minimum',
    historyNote: 'Minimální mzda při každé zaznamenané změně. Tabulka uvádí celé zveřejněné rozpětí.',
    noHistory: 'Tato nabídka zatím nemá srovnatelné změny mzdy.',
    payComparison: 'Mzdy podle velikosti firmy', payMethod: 'Medián zveřejněného minima. Základem je nejmenší skupina s údaji o mzdě. Měny a období jsou uvedeny samostatně.',
    baseline: 'Základ', difference: 'Rozdíl', sample: 'Nabídky', noSalaryData: 'Pro tyto filtry nejsou dostupné srovnatelné mzdy.',
    firstSeen: 'Poprvé zaznamenáno', lastSeen: 'Poslední kontrola', lastChanged: 'Poslední změna', publishedDate: 'Zveřejněno',
    employment_type: 'Typ úvazku', required_skills: 'Požadované dovednosti',
    nice_to_have_skills: 'Dovednosti výhodou', technologies: 'Technologie',
    salary_min: 'Minimální mzda', salary_max: 'Maximální mzda', salary_currency: 'Měna',
    yes: 'Ano', no: 'Ne', titleField: 'Název nabídky',
    quality: 'Kontrola kvality', confidence: 'Skóre pravidel: {score}. Jde o orientační hodnocení.',
    close: 'Zavřít', unavailable: 'Data nejsou dostupná', invalidData: 'Neplatný formát dat',
    loadError: 'Data se nepodařilo načíst: {error}. Zkuste obnovit stránku.'
  },
  de: {
    locale: 'de-DE', navigation: 'Hauptnavigation', overview: 'Übersicht', postings: 'Stellenangebote',
    analytics: 'Analysen', filters: 'Filter', settings: 'Einstellungen', about: 'Über uns',
    toggleMenu: 'Menü ein- oder ausklappen', language: 'Sprache', theme: 'Farbschema',
    resultsLabel: 'Ergebnisse', darkMode: 'Dunkelmodus', light: 'Hell', dark: 'Dunkel', allFilterValues: 'Alle',
    rowsPerPage: 'Stellenangebote pro Seite', defaultPeriod: 'Standardzeitraum der Analyse',
    account: 'Konto', accountDemo: 'Demo-Schaltfläche ohne Funktion.',
    aboutProject: 'SkillMiner ist ein studentisches Teamprojekt zur Analyse von IT-Stellenangeboten, Kompetenzen und Gehältern.',
    dashboardIntro: 'Stellenangebote, Entwicklung der Nachfrage und ausgeschriebene Gehälter.',
    loading: 'Daten werden geladen…', synthetic: 'Demodaten', published: 'Veröffentlichte Daten', updated: 'Aktualisiert:',
    syntheticNotice: 'Demodaten · Stellenangebote, Unternehmensgrößen und Beispielverläufe sind fiktiv.',
    realNotice: 'Veröffentlichte Ergebnisse der automatischen Analyse. Ungeprüfte Einträge können Fehler enthalten.',
    checked: 'Daten geprüft am {date}', refreshError: 'Die neuesten Daten konnten nicht geladen werden. Der vorherige Stand wird angezeigt.',
    mockRunning: 'Lokale Demoquellen werden geprüft…', mockFailed: 'Die Prüfung der lokalen Demoquellen ist fehlgeschlagen.',
    metrics: 'Kennzahlen', count: 'Stellen in der Auswahl', skills: 'Unterschiedliche Technologien',
    review: 'Zur Prüfung markiert', remote: 'Remote / hybrid',
    changes: 'Änderungen an Stellenangeboten', noChanges: 'Bisher wurden keine Änderungen erfasst.',
    search: 'Suche', searchPlaceholder: 'Titel, Firma, Kompetenz…', specialization: 'Fachgebiet',
    seniority: 'Erfahrungsstufe', location: 'Stadt', site: 'Quelle', allSpecializations: 'Alle Fachgebiete',
    allLevels: 'Alle Erfahrungsstufen', allLocations: 'Alle Städte', allSources: 'Alle Quellen',
    company_size: 'Unternehmensgröße', allSizes: 'Alle Größen', small: 'Klein · 1–49',
    medium: 'Mittel · 50–249', large: 'Groß · 250+', unknown: 'Unbekannt',
    doubtful: 'Nur markierte Einträge', possibleDuplicates: 'Mögliche Duplikate', reset: 'Filter zurücksetzen',
    export: 'CSV exportieren ↓', more: 'Mehr anzeigen', empty: 'Keine Stellenangebote passen zu diesen Filtern.',
    position: 'Stelle', company: 'Unternehmen', salary: 'Gehalt', company_headcount: 'Beschäftigte',
    headcount: '{n} Beschäftigte', copies: '{n} verknüpfte Quellen', needsReview: 'Prüfung erforderlich',
    sourceLink: 'Quelle öffnen ↗', demoLink: 'Demolink ↗',
    salary_period: 'Zahlungszeitraum', month: 'Monat', hour: 'Stunde', year: 'Jahr',
    activity: 'Stellenangebote im Zeitverlauf', activityNote: 'Eindeutige aktive, neue und geänderte Angebote für die gewählten Filter.',
    period: 'Zeitraum', last7: 'Letzte 7 Tage', last30: 'Letzte 30 Tage', last90: 'Letzte 90 Tage',
    active: 'Aktiv', added: 'Neu', updatedSeries: 'Geändert', date: 'Datum', chartValues: 'Diagrammdaten anzeigen',
    showingPeriod: 'Zeitraum {period}', clearPeriod: 'Zeitraum abwählen', queueEmpty: 'Für diese Auswahl ist kein Verlauf verfügbar.',
    distribution: 'Verteilung der Stellenangebote', technologiesSample: 'Technologien in der Auswahl',
    salaryHistory: 'Gehaltsverlauf', salaryMinimum: 'Ausgeschriebenes Mindestgehalt',
    historyNote: 'Mindestgehalt zum Zeitpunkt jeder erfassten Änderung. Die Tabelle zeigt die gesamte Gehaltsspanne.',
    noHistory: 'Für dieses Angebot liegen noch keine vergleichbaren Gehaltsänderungen vor.',
    payComparison: 'Gehalt nach Unternehmensgröße', payMethod: 'Median der ausgeschriebenen Mindestgehälter. Die kleinste Gruppe mit Gehaltsdaten dient als Vergleich. Währungen und Zeiträume werden separat ausgewiesen.',
    baseline: 'Vergleichsbasis', difference: 'Unterschied', sample: 'Stellen', noSalaryData: 'Für diese Filter liegen keine vergleichbaren Gehaltsdaten vor.',
    firstSeen: 'Zuerst erfasst', lastSeen: 'Zuletzt geprüft', lastChanged: 'Zuletzt geändert', publishedDate: 'Veröffentlicht',
    employment_type: 'Beschäftigungsart', required_skills: 'Erforderliche Kompetenzen',
    nice_to_have_skills: 'Wünschenswerte Kompetenzen', technologies: 'Technologien',
    salary_min: 'Mindestgehalt', salary_max: 'Höchstgehalt', salary_currency: 'Währung',
    yes: 'Ja', no: 'Nein', titleField: 'Stellentitel',
    quality: 'Qualitätsprüfung', confidence: 'Regelwert: {score}. Dieser Wert dient zur Orientierung.',
    close: 'Schließen', unavailable: 'Daten nicht verfügbar', invalidData: 'Ungültiges Datenformat',
    loadError: 'Daten konnten nicht geladen werden: {error}. Versuchen Sie, die Seite neu zu laden.'
  }
};

Object.assign(interfaceMessages.cs, {
  published: 'Skutečné nabídky · Profesia.sk', skills: 'Unikátní dovednosti', technologiesSample: 'Dovednosti ve výběru',
  realNotice: 'Skutečné nabídky z Profesia.sk zpracované automatickou analýzou. Neověřené záznamy mohou obsahovat chyby.',
  datasetSwitch: 'Sada dat', dataMock: 'Ukázková', dataReal: 'Skutečná', realMissingShort: 'Skutečná data nejsou zveřejněna',
  realMissing: 'Skutečné nabídky zatím nejsou zveřejněny. Tým je zveřejní ručně po kontrole a schválení použití dat.',
  rankRequired: 'Požadované', rankNice: 'Výhodou', rankMode: 'Typ dovedností', summary: 'Stručně o pozici',
  noSummary: 'Popis není k dispozici.', experience: 'Praxe', experienceYears: 'min. {n} r.', noExperience: 'bez praxe',
  education: 'Vzdělání', edu_secondary: 'středoškolské', edu_bachelor: 'VŠ bakalářské', edu_master: 'VŠ magisterské',
  edu_phd: 'doktorské (PhD)'
});
Object.assign(interfaceMessages.de, {
  published: 'Echte Stellen · Profesia.sk', skills: 'Unterschiedliche Kompetenzen', technologiesSample: 'Kompetenzen in der Auswahl',
  realNotice: 'Echte Stellenangebote von Profesia.sk, automatisch ausgewertet. Ungeprüfte Einträge können Fehler enthalten.',
  datasetSwitch: 'Datensatz', dataMock: 'Demo', dataReal: 'Echt', realMissingShort: 'Echte Daten nicht veröffentlicht',
  realMissing: 'Echte Stellenangebote sind noch nicht veröffentlicht. Das Team veröffentlicht sie manuell nach Prüfung und Freigabe.',
  rankRequired: 'Erforderlich', rankNice: 'Wünschenswert', rankMode: 'Art der Kompetenz', summary: 'Kurz zur Stelle',
  noSummary: 'Keine Beschreibung verfügbar.', experience: 'Berufserfahrung', experienceYears: 'mind. {n} J.',
  noExperience: 'keine erforderlich', education: 'Ausbildung', edu_secondary: 'Abitur / Matura', edu_bachelor: 'Bachelor',
  edu_master: 'Master', edu_phd: 'Promotion (PhD)'
});

for (const [code, messages] of Object.entries(interfaceMessages)) {
  MESSAGES[code] = {...MESSAGES[code], ...messages};
}

const savedLanguage = readPreference('skillminer-language');
let language = Object.hasOwn(MESSAGES, savedLanguage) ? savedLanguage : 'sk';
