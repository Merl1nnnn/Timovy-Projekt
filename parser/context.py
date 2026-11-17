"""Нормалізація контексту: SK/EN/CS, регіони та явні суми без вигаданої конвертації."""
import re
import unicodedata


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).lower()


SK_WORDS = set('a v na s so je pre sa z za do od aj alebo ktory ktora budes ako len cez sme ste pri po k vo uz mas tvoj nas nasich hladame poziadavky ponukame skusenosti pracovny mesacne rocne'.split())
EN_WORDS = set('the and of to with for in you we our is are will your an at from who what or as requirements experience looking salary'.split())
CS_WORDS = set('hledame nabizime zkusenosti pracovnich pracovni mesicne rocni cestina cesky tymu pozadavky vyvojar hledate muzete budete'.split())
SK_DISTINCT = set('hladame ponukame skusenosti poziadavky mesacne rocne slovencina slovensky budete'.split())


def language_info(text):
    words = re.findall('[a-z]+', fold(text))
    en = sum(w in EN_WORDS for w in words)
    sk = sum(w in SK_WORDS for w in words)
    cs = sum(w in CS_WORDS for w in words)
    distinct_sk = sum(w in SK_DISTINCT for w in words)
    if cs >= 2 and cs > distinct_sk or re.search('[řůěŘŮĚ]', text):
        return 'cs', min(0.98, 0.6 + cs * 0.07)
    if en and en / max(1, en + sk + cs) >= 0.35:
        return 'en', min(0.98, 0.55 + en * 0.025)
    if sk >= 2 or distinct_sk:
        return 'sk', min(0.98, 0.55 + sk * 0.025)
    return 'und', 0.0


REGIONS = {
    'Bratislavský kraj': ['Bratislava', 'Malacky', 'Pezinok', 'Senec'],
    'Trnavský kraj': ['Trnava', 'Piešťany', 'Hlohovec', 'Dunajská Streda', 'Galanta', 'Senica', 'Skalica'],
    'Trenčiansky kraj': ['Trenčín', 'Prievidza', 'Považská Bystrica', 'Nové Mesto nad Váhom', 'Partizánske', 'Púchov'],
    'Nitriansky kraj': ['Nitra', 'Nové Zámky', 'Levice', 'Komárno', 'Šaľa', 'Topoľčany'],
    'Žilinský kraj': ['Žilina', 'Martin', 'Ružomberok', 'Liptovský Mikuláš', 'Čadca', 'Dolný Kubín'],
    'Banskobystrický kraj': ['Banská Bystrica', 'Zvolen', 'Lučenec', 'Brezno', 'Žiar nad Hronom', 'Detva'],
    'Prešovský kraj': ['Prešov', 'Poprad', 'Bardejov', 'Humenné', 'Vranov nad Topľou', 'Stará Ľubovňa'],
    'Košický kraj': ['Košice', 'Michalovce', 'Spišská Nová Ves', 'Rožňava', 'Trebišov']
}


def region_for(city):
    if city:
        for region, cities in REGIONS.items():
            if fold(city) in {fold(c) for c in cities}:
                return region
    return None


AMOUNT = r'\d{1,3}(?:[ \u00a0.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?'
# Currency before or after the amount; a range may repeat the currency.
MONEY = re.compile(rf'(?:(?P<pre>€|EUR|CZK|Kč|USD|\$)\s*)?(?P<low>{AMOUNT})(?:\s*(?:€|EUR|CZK|Kč|USD|\$)?\s*[–—-]\s*(?:€|EUR|CZK|Kč|USD|\$)?\s*(?P<high>{AMOUNT}))?\s*(?P<post>€|EUR|CZK|Kč|USD|\$)?', re.I)


def amount(value):
    raw = value.replace(' ', '').replace('\u00a0', '')
    if re.search(r'[.,]\d{1,2}$', raw):
        sep = max(raw.rfind('.'), raw.rfind(','))
        raw = re.sub('[.,]', '', raw[:sep]) + '.' + raw[sep+1:]
    else:
        raw = re.sub('[.,]', '', raw)
    return float(raw)


def salary_info(text):
    found = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        for match in MONEY.finditer(line):
            currency = match['pre'] or match['post']
            if not currency:
                continue
            folded = fold(" ".join(lines[max(0,index-2):index+1]))
            period = ('hour' if re.search(r'/\s*h\b|hour|hodin', folded) else
                      'year' if re.search(r'rocne|rocni|rocna|year|annual|per annum', folded) else
                      'month' if re.search(r'mesiac|mesac|mesic|mesicn|month', folded) else None)
            currency = {'€': 'EUR', '$': 'USD', 'kč': 'CZK'}.get(currency.lower(), currency.upper())
            basis = 'net' if re.search(r'\bnet(?:to)?\b|v cistom|cisteho', folded) else 'gross' if re.search(r'brutto|gross|hrub', folded) else 'unknown'
            low, high = amount(match['low']), amount(match['high']) if match['high'] else None
            if high is not None and low > high:
                continue
            found.append({'low': low, 'high': high, 'currency': currency, 'period': period, 'basis': basis, 'quote': line.strip()})
    unique = {(m['low'], m['high'], m['currency'], m['period'], m['basis']) for m in found}
    return found[0] if len(unique) == 1 else None


def enrich(posting, text):
    posting.salary_monthly_min = posting.salary_monthly_max = None
    posting.salary_period = None
    posting.salary_basis = 'unknown'
    posting.normalization_issues = []
    posting.role_specializations = []
    posting.language, posting.language_confidence = language_info(text)
    posting.region = region_for(posting.location)
    lower = fold(posting.title)
    for label, pattern in [('Backend', r'back[ -]?end'), ('Frontend', r'front[ -]?end|\bui\b'),
                           ('ML', r'machine learning|\bml\b|strojov'), ('DevOps', r'devops|\bsre\b'),
                           ('Data', r'data engineer|datov|data scientist'), ('QA', r'\bqa\b|test engineer'),
                           ('Security', r'security|bezpecnost'), ('Mobile', r'android|ios|mobile'),
                           ('Fullstack', r'full[ -]?stack')]:
        if re.search(pattern, lower):
            posting.role_specializations.append(label)
    info = salary_info(text)
    if info:
        posting.salary_min = info['low']
        posting.salary_max = info['high']
        posting.salary_currency = info['currency']
        posting.salary_period, posting.salary_basis = info['period'], info['basis']
        if info['period'] in {'month', 'year'}:
            divisor = 12 if info['period'] == 'year' else 1
            posting.salary_monthly_min = round(info['low'] / divisor, 2)
            posting.salary_monthly_max = round(info['high'] / divisor, 2) if info['high'] is not None else None
        elif info['period'] == 'hour':
            posting.normalization_issues.append('hourly salary: monthly conversion requires a work-hours assumption')
        else:
            posting.normalization_issues.append('salary period is not explicit; monthly equivalent is unavailable')
    elif posting.salary_min is not None:
        posting.salary_min = posting.salary_max = None
        posting.salary_currency = None
        posting.normalization_issues.append('salary could not be grounded unambiguously in the source')
    if posting.salary_basis == 'unknown' and posting.salary_min is not None:
        posting.normalization_issues.append('gross/net basis is not explicit')
    if posting.language == 'und':
        posting.review_required = True
    if posting.salary_min is not None and (posting.salary_period is None or posting.salary_basis == 'unknown'):
        posting.review_required = True
    if any('unambiguously' in issue for issue in posting.normalization_issues):
        posting.review_required = True
    return posting
