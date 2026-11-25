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
    'Trenčiansky kraj': ['Trenčín', 'Prievidza', 'Považská Bystrica', 'Nové Mesto nad Váhom', 'Partizánske', 'Púchov', 'Dubnica nad Váhom'],
    'Nitriansky kraj': ['Nitra', 'Nové Zámky', 'Levice', 'Komárno', 'Šaľa', 'Topoľčany'],
    'Žilinský kraj': ['Žilina', 'Martin', 'Ružomberok', 'Liptovský Mikuláš', 'Čadca', 'Dolný Kubín'],
    'Banskobystrický kraj': ['Banská Bystrica', 'Zvolen', 'Lučenec', 'Brezno', 'Žiar nad Hronom', 'Detva', 'Revúca', 'Rimavská Sobota'],
    'Prešovský kraj': ['Prešov', 'Poprad', 'Bardejov', 'Humenné', 'Vranov nad Topľou', 'Stará Ľubovňa'],
    'Košický kraj': ['Košice', 'Michalovce', 'Spišská Nová Ves', 'Rožňava', 'Trebišov']
}


def region_for(city):
    if city:
        for region, cities in REGIONS.items():
            if fold(city) in {fold(c) for c in cities}:
                return region
    return None


AMOUNT = r'(?:\d{1,3}(?:[ \u00a0.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)'
CURRENCY = r'(?:€|EUR\b|CZK\b|Kč\b|USD\b|\$)'
UNIT = r'(?:/\s*(?:month|year|hour|mesiac|mesic|hodina|h)\b)?'
MONEY = re.compile(
    rf'(?<![\w.,])(?P<pre>{CURRENCY})?\s*(?P<low>{AMOUNT})\s*(?P<after_low>{CURRENCY})?{UNIT}'
    rf'(?:\s*[–—-]\s*(?P<before_high>{CURRENCY})?\s*(?P<high>{AMOUNT})\s*(?P<post>{CURRENCY})?{UNIT})?(?![\w.,])', re.I)
PERIODS = {
    'hour': r'/\s*h\b|\bhours?\b|hodin',
    'year': r'rocn|\byears?\b|annual|per annum|/\s*rok\b',
    'month': r'mesiac|mesac|mesic|\bmonths?\b',
}
BENEFIT_MONEY = re.compile(r'meal|stravn|stravov|referral|sign.on|naborov|prispevok|allowance|voucher', re.I)
PAY_LABEL = re.compile(r'salary|wage|mzda|mzdy|mzdov|plat(?:ove|ovy|u|\b)|odmena|remuneration', re.I)


def amount(value):
    raw = value.replace(' ', '').replace('\u00a0', '')
    if re.search(r'[.,]\d{1,2}$', raw):
        sep = max(raw.rfind('.'), raw.rfind(','))
        raw = re.sub('[.,]', '', raw[:sep]) + '.' + raw[sep+1:]
    else:
        raw = re.sub('[.,]', '', raw)
    return float(raw)


def salary_info(text):
    """Only one unambiguous monetary offer; units and basis must be explicit."""
    found, ambiguous = [], False
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        folded_line = fold(line)
        if BENEFIT_MONEY.search(folded_line) and not PAY_LABEL.search(folded_line):
            continue
        for match in MONEY.finditer(line):
            currencies = { {'€': 'EUR', '$': 'USD', 'kč': 'CZK'}.get(c.lower(), c.upper())
                          for c in [match['pre'], match['after_low'], match['before_high'], match['post']] if c }
            if not currencies:
                continue
            if len(currencies) != 1:
                ambiguous = True
                continue
            # Adjacent labels can establish units/basis, but unrelated earlier amounts cannot.
            start = index
            while start > max(0, index - 2):
                previous = lines[start - 1]
                if re.search(r'\d', previous) or not re.search(r'brutto|gross|hrub|netto|salary|mzda|mzdy|mzdov|plat|mesac|month|rocne|annual|hodin', fold(previous)):
                    break
                start -= 1
            end = index + 1
            if end < len(lines) and re.fullmatch(r'\s*(?:brutto|gross|netto|net|hrubeho|mesacne|monthly|per month|per year|rocne|hourly)[\s/(),.]*', fold(lines[end])):
                end += 1
            quote = ''.join(lines[start:end]).rstrip('\r\n')
            folded = fold(quote)
            periods = [key for key, pattern in PERIODS.items() if re.search(pattern, folded)]
            basis_tags = []
            if re.search(r'\bnet(?:to)?\b|v cistom|cisteho', folded): basis_tags.append('net')
            if re.search(r'brutto|gross|hrub', folded): basis_tags.append('gross')
            low, high = amount(match['low']), amount(match['high']) if match['high'] else None
            if high is not None and low > high:
                ambiguous = True
                continue
            # "up to" is an upper bound, not a guaranteed minimum.
            upper_only = high is None and re.search(r'\bup to\s*$|\bdo\s*$', fold(line[:match.start()]))
            if upper_only: low, high = None, low
            found.append({'low': low, 'high': high, 'currency': next(iter(currencies)),
                          'period': periods[0] if len(periods) == 1 else None,
                          'basis': basis_tags[0] if len(basis_tags) == 1 else 'unknown', 'quote': quote})
    unique = {(m['low'], m['high'], m['currency'], m['period'], m['basis']) for m in found}
    return found[0] if not ambiguous and len(unique) == 1 else None


def enrich(posting, text):
    posting.salary_monthly_min = posting.salary_monthly_max = None
    posting.salary_original_min = posting.salary_original_max = None
    posting.salary_min = posting.salary_max = None
    posting.salary_currency = None
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
        posting.salary_original_min, posting.salary_original_max = info['low'], info['high']
        posting.salary_currency = info['currency']
        posting.salary_period, posting.salary_basis = info['period'], info['basis']
        if info['period'] in {'month', 'year'} and info['basis'] == 'gross':
            divisor = 12 if info['period'] == 'year' else 1
            posting.salary_min = posting.salary_monthly_min = round(info['low'] / divisor, 2) if info['low'] is not None else None
            posting.salary_max = posting.salary_monthly_max = round(info['high'] / divisor, 2) if info['high'] is not None else None
        elif info['period'] == 'hour':
            posting.normalization_issues.append('hourly salary: monthly conversion requires a work-hours assumption')
        if info['period'] is None or info['basis'] == 'unknown':
            posting.normalization_issues.append('salary period or gross/net basis is not explicit')
            posting.review_required = True
    elif re.search(CURRENCY, text, re.I) and any(MONEY.finditer(text)):
        posting.normalization_issues.append('salary could not be grounded unambiguously in the source')
        posting.review_required = True
    if posting.language == 'und':
        posting.review_required = True
    return posting
