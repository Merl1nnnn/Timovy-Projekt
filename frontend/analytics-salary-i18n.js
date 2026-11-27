'use strict';

const salaryMessages = {
  en: {
    convertedSalaryUnit: 'Display salary as',
    fxSource: 'ECB reference rates: {date} · Snapshot rates, not historical rates',
    fxUnavailable: 'Exchange rates unavailable. Same-currency conversion remains available.',
    conversionMethod: 'Annual = monthly × 12; 52 weeks/year; full-time 40 h/week, part-time 20 h/week. Hourly conversion requires a known employment type. No bonuses or taxes are estimated. Missing legacy periods are treated as monthly.',
    conversionCoverage: 'Comparable salary data: {n} of {total} postings; {excluded} excluded (missing salary, currency rate or hours).',
    fxRefresh: 'Refresh local ECB rates', salaryCoverageShort: 'n={n}/{total}',
    convertedOriginal: 'Original advertised amount', estimate: 'Converted estimate',
    salaryMethod: 'Median advertised lower bounds in the selected currency and pay period; P25–P75 is the middle 50%. Unconvertible amounts are excluded. Dated snapshot exchange rates apply to all observations, not historical rates.',
    payMethod: 'Median advertised lower bounds by company size, converted to the selected currency and pay period. The smallest group with comparable salary data is the reference. Hourly amounts use the stated working-hour assumptions.',
    comparisonMethod: 'Same dates, selected currency and pay period. Converted minima may include working-hour estimates. Differences describe these samples; they do not prove a skill causes higher pay.',
    firmOfferIntro: 'Enter requirements and a gross base salary. Advertised minima are converted to the selected currency and pay period; hourly figures may be estimates.',
    comparisonPaySample: '{n} comparable converted salary minima from {total} matching postings',
    offerPercentileMethod: 'Sample percentile: lower converted minima + half of equal minima. This compares advertised starting amounts in a common unit, not actual pay; currency and hourly conversions can be estimates.'
  },
  sk: {
    convertedSalaryUnit: 'Zobraziť mzdu ako',
    fxSource: 'Referenčné kurzy ECB: {date} · Kurzy zo snímky, nie historické kurzy',
    fxUnavailable: 'Výmenné kurzy nie sú dostupné. Prepočet v rovnakej mene zostáva dostupný.',
    conversionMethod: 'Ročná mzda = mesačná × 12; 52 týždňov/rok; plný úväzok 40 h/týždeň, čiastočný 20 h/týždeň. Hodinový prepočet vyžaduje známy typ úväzku. Bonusy ani dane sa neodhadujú. Staršie údaje bez obdobia sa považujú za mesačné.',
    conversionCoverage: 'Porovnateľné mzdové údaje: {n} z {total} ponúk; {excluded} vynechaných (chýba mzda, kurz alebo počet hodín).',
    fxRefresh: 'Obnoviť lokálne kurzy ECB', salaryCoverageShort: 'n={n}/{total}',
    convertedOriginal: 'Pôvodná ponúkaná suma', estimate: 'Prepočítaný odhad',
    salaryMethod: 'Medián ponúkaných dolných hraníc vo vybranej mene a období; P25–P75 je prostredných 50 %. Sumy, ktoré nemožno prepočítať, sa vynechávajú. Datované kurzy zo snímky platia pre všetky pozorovania, nejde o historické kurzy.',
    payMethod: 'Medián ponúkaných dolných hraníc podľa veľkosti firmy, prepočítaný na vybranú menu a obdobie. Referenciou je najmenšia skupina s porovnateľnými mzdovými údajmi. Hodinové sumy používajú uvedené predpoklady pracovného času.',
    comparisonMethod: 'Rovnaké dátumy, vybraná mena a obdobie mzdy. Prepočítané minimá môžu zahŕňať odhad pracovného času. Rozdiely opisujú vzorky; nedokazujú, že zručnosť spôsobuje vyššiu mzdu.',
    firmOfferIntro: 'Zadajte požiadavky a základnú hrubú mzdu. Ponúkané minimá sa prepočítajú na vybranú menu a obdobie; hodinové sumy môžu byť odhadom.',
    comparisonPaySample: '{n} porovnateľných prepočítaných mzdových miním z {total} zodpovedajúcich ponúk',
    offerPercentileMethod: 'Percentil vo vzorke: nižšie prepočítané minimá + polovica rovnakých. Porovnávajú sa ponúkané nástupné sumy v spoločnej jednotke, nie skutočné mzdy; menové a hodinové prepočty môžu byť odhadom.'
  },
  uk: {
    convertedSalaryUnit: 'Показувати зарплату в',
    fxSource: 'Довідкові курси ЄЦБ: {date} · Курси зі знімка, не історичні',
    fxUnavailable: 'Валютні курси недоступні. Перерахунок у тій самій валюті залишається доступним.',
    conversionMethod: 'Річна зарплата = місячна × 12; 52 тижні/рік; повна зайнятість 40 год/тиждень, часткова 20 год/тиждень. Погодинний перерахунок потребує відомого типу зайнятості. Бонуси й податки не оцінюються. У старих записах без періоду зарплата вважається місячною.',
    conversionCoverage: 'Порівнювані дані про зарплату: {n} із {total} вакансій; {excluded} виключено (немає зарплати, валютного курсу або годин).',
    fxRefresh: 'Оновити локальні курси ЄЦБ', salaryCoverageShort: 'n={n}/{total}',
    convertedOriginal: 'Початкова запропонована сума', estimate: 'Оцінка після перерахунку',
    salaryMethod: 'Медіана запропонованих нижніх меж у вибраній валюті й періоді; P25–P75 — середні 50 %. Суми, які неможливо перерахувати, виключено. Датовані курси зі знімка застосовуються до всіх спостережень, це не історичні курси.',
    payMethod: 'Медіана запропонованих нижніх меж за розміром компанії, перерахованих у вибрану валюту й період. База порівняння — найменша група з порівнюваними даними. Для погодинних сум діють зазначені припущення щодо робочого часу.',
    comparisonMethod: 'Ті самі дати, вибрана валюта й період виплати. Перераховані мінімуми можуть включати оцінку робочого часу. Відмінності описують вибірки; вони не доводять, що навичка спричиняє вищу зарплату.',
    firmOfferIntro: 'Введіть вимоги й базову зарплату до оподаткування. Запропоновані мінімуми перераховуються у вибрану валюту й період; погодинні суми можуть бути оцінками.',
    comparisonPaySample: '{n} порівнюваних перерахованих мінімумів зарплати з {total} відповідних вакансій',
    offerPercentileMethod: 'Перцентиль вибірки: нижчі перераховані мінімуми + половина однакових. Порівнюються запропоновані початкові суми в спільних одиницях, а не фактичні зарплати; валютні й погодинні перерахунки можуть бути оцінками.'
  },
  cs: {
    convertedSalaryUnit: 'Zobrazit mzdu jako',
    fxSource: 'Referenční kurzy ECB: {date} · Kurzy ze snímku, nikoli historické',
    fxUnavailable: 'Směnné kurzy nejsou dostupné. Přepočet ve stejné měně zůstává dostupný.',
    conversionMethod: 'Roční mzda = měsíční × 12; 52 týdnů/rok; plný úvazek 40 h/týden, částečný 20 h/týden. Hodinový přepočet vyžaduje známý typ úvazku. Bonusy ani daně se neodhadují. Starší údaje bez období se považují za měsíční.',
    conversionCoverage: 'Porovnatelná mzdová data: {n} z {total} nabídek; {excluded} vynecháno (chybí mzda, kurz nebo počet hodin).',
    fxRefresh: 'Obnovit místní kurzy ECB', salaryCoverageShort: 'n={n}/{total}',
    convertedOriginal: 'Původní nabízená částka', estimate: 'Přepočítaný odhad',
    salaryMethod: 'Medián nabízených dolních hranic ve vybrané měně a období; P25–P75 je prostředních 50 %. Částky, které nelze přepočítat, se vynechávají. Datované kurzy ze snímku platí pro všechna pozorování, nejde o historické kurzy.',
    payMethod: 'Medián nabízených dolních hranic podle velikosti firmy, přepočítaný na vybranou měnu a období. Referencí je nejmenší skupina s porovnatelnými mzdovými daty. Hodinové částky používají uvedené předpoklady pracovní doby.',
    comparisonMethod: 'Stejná data, vybraná měna a období mzdy. Přepočítaná minima mohou zahrnovat odhad pracovní doby. Rozdíly popisují vzorky; nedokazují, že dovednost způsobuje vyšší mzdu.',
    firmOfferIntro: 'Zadejte požadavky a základní hrubou mzdu. Nabízená minima se přepočítají na vybranou měnu a období; hodinové částky mohou být odhadem.',
    comparisonPaySample: '{n} porovnatelných přepočítaných mzdových minim z {total} odpovídajících nabídek',
    offerPercentileMethod: 'Percentil ve vzorku: nižší přepočítaná minima + polovina stejných. Porovnávají se nabízené nástupní částky ve společné jednotce, nikoli skutečné mzdy; měnové a hodinové přepočty mohou být odhadem.'
  },
  de: {
    convertedSalaryUnit: 'Gehalt anzeigen als',
    fxSource: 'EZB-Referenzkurse: {date} · Kurse des Datenstands, keine historischen Kurse',
    fxUnavailable: 'Wechselkurse nicht verfügbar. Umrechnung innerhalb derselben Währung bleibt verfügbar.',
    conversionMethod: 'Jahresgehalt = Monatsgehalt × 12; 52 Wochen/Jahr; Vollzeit 40 Std./Woche, Teilzeit 20 Std./Woche. Stundenumrechnung erfordert eine bekannte Beschäftigungsart. Boni und Steuern werden nicht geschätzt. Ältere Angaben ohne Zeitraum gelten als monatlich.',
    conversionCoverage: 'Vergleichbare Gehaltsdaten: {n} von {total} Stellen; {excluded} ausgeschlossen (Gehalt, Wechselkurs oder Stunden fehlen).',
    fxRefresh: 'Lokale EZB-Kurse aktualisieren', salaryCoverageShort: 'n={n}/{total}',
    convertedOriginal: 'Ursprünglich ausgeschriebener Betrag', estimate: 'Umgerechneter Schätzwert',
    salaryMethod: 'Median ausgeschriebener Untergrenzen in gewählter Währung und gewähltem Zeitraum; P25–P75 umfasst die mittleren 50 %. Nicht umrechenbare Beträge werden ausgeschlossen. Datierte Kurse des Datenstands gelten für alle Beobachtungen, keine historischen Kurse.',
    payMethod: 'Median ausgeschriebener Untergrenzen nach Unternehmensgröße, umgerechnet in gewählte Währung und gewählten Zeitraum. Referenz ist die kleinste Gruppe mit vergleichbaren Gehaltsdaten. Stundenbeträge verwenden die angegebenen Arbeitszeitannahmen.',
    comparisonMethod: 'Gleicher Zeitraum, gleiche gewählte Währung und Gehaltsperiode. Umgerechnete Untergrenzen können Arbeitszeitschätzungen enthalten. Unterschiede beschreiben die Stichproben; sie belegen keinen Gehaltseffekt einer Kompetenz.',
    firmOfferIntro: 'Geben Sie Anforderungen und ein Bruttogrundgehalt ein. Ausgeschriebene Untergrenzen werden in gewählte Währung und Gehaltsperiode umgerechnet; Stundenbeträge können Schätzwerte sein.',
    comparisonPaySample: '{n} vergleichbare umgerechnete Gehaltsuntergrenzen aus {total} passenden Stellen',
    offerPercentileMethod: 'Stichprobenperzentil: niedrigere umgerechnete Untergrenzen + die Hälfte gleicher Werte. Verglichen werden ausgeschriebene Einstiegsbeträge in gemeinsamer Einheit, keine tatsächlichen Gehälter; Währungs- und Stundenumrechnungen können Schätzwerte sein.'
  }
};

for (const [code, messages] of Object.entries(salaryMessages)) Object.assign(MESSAGES[code], messages);
