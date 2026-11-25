"""Докази прив'язані до незміненого html_to_text: індекси Python Unicode, [start, end)."""
import re

from parser.aliases import ALIASES, TYPES
from parser.normalize import fold, normalize_skill
from parser.schema import CandidateMention, EvidenceSpan, RejectedItem, SkillMention

REQUIRED = re.compile(r'^(?:poziadav|pozadujeme|pozadav|dalsie znalosti|ostatne znalosti|pocitacove znalosti|jazykove znalosti|osobnostne predpoklady|other knowledge|requirements|must.have|what you bring|who we.re looking for|looking for|hladame|hledame|co.*ovladat)', re.I)
NICE = re.compile(r'vyhodou|vyhod|nice.to.have|bonus points|plusove body|a plus|\(bonus\)', re.I)
NICE_HEADING = re.compile(r'^(?:vyhodou|nice.to.have|bonus points|plusove body)', re.I)
OTHER = re.compile(r'^(?:napln prace|pracovna napln|responsibilities|duties|benefit|what you.ll do|what we offer|ponukame|nabizime|about us|o spolocnosti|podobne ponuky|people also viewed|kontakt)', re.I)
NEGATION = re.compile(r'\b(?:not required|not necessary|no need|do not require|nevyzadujeme|nepozadujeme|nie je potrebn|neni nutn|neni potreba|nie je podmienkou|without experience|bez znalosti)\w*', re.I)
ALTERNATIVE = re.compile(r'\b(?:or|alebo|nebo)\b', re.I)
INJECTION = re.compile(r'ignore (?:all |the )?(?:previous|system)|\bsystem\s*:|disregard.*instructions', re.I)


def sections(text):
    zone = 'unknown'
    at = 0
    for line in text.splitlines(keepends=True):
        folded = fold(line).strip()
        if OTHER.search(folded):
            zone = 'other'
        elif REQUIRED.search(folded):
            zone = 'required'
        elif NICE_HEADING.search(folded):
            # Inline "Výhodou je Kafka" applies to this line, not every following bullet.
            tail = NICE_HEADING.sub('', folded).strip(' :.-')
            if not tail or tail in {'je', 'su', 'skills'}:
                zone = 'nice_to_have'
        current = 'nice_to_have' if NICE.search(folded) and zone != 'other' else zone
        yield at, at + len(line), line.rstrip('\r\n'), current
        at += len(line)


def context_problem(surface, quote):
    clauses = re.split(r';|,|\b(?:but|however|ale|avsak)\b', fold(quote))
    related = [c for c in clauses if alias_pattern(fold(surface)).search(c)]
    if any(NEGATION.search(c) for c in related):
        return 'negated requirement needs expert review'
    if any(ALTERNATIVE.search(c) for c in related):
        return 'alternative requirements need expert review'
    return None


def alias_pattern(alias):
    return re.compile(r'(?<![\w+#])' + re.escape(alias) + r'(?![\w+#])', re.I)


def dictionary_candidates(text):
    """Швидкий словниковий NER. Усі кандидати ще потребують LLM-перевірки."""
    candidates = []
    for _, _, line, section in sections(text):
        if section in {'other', 'unknown'} or not line.strip():
            continue
        for canonical, aliases in ALIASES.items():
            match = next((m for alias in sorted([canonical, *aliases], key=len, reverse=True)
                          if (m := alias_pattern(alias).search(line))), None)
            if match:
                candidates.append(CandidateMention(surface=match.group(), canonical=canonical,
                    kind=TYPES[canonical], requirement='nice_to_have' if section == 'nice_to_have' else 'required',
                    evidence=line))
    return candidates


def ground(candidates, text):
    mentions, rejected, seen = [], [], set()
    lines = list(sections(text))
    def priority(candidate):
        zones = [zone for match in re.finditer(re.escape(candidate.evidence), text)
                 for start, end, _, zone in lines if start < match.end() and end > match.start()]
        return min(({'required': 0, 'nice_to_have': 1, 'unknown': 2, 'other': 3}[zone] for zone in zones), default=4)
    for candidate in sorted(candidates, key=priority):
        canonical = normalize_skill(candidate.canonical)
        surface_canonical = normalize_skill(candidate.surface)
        reason = None
        if candidate.implicit:
            reason = 'implicit skill: keep separate from explicit requirements'
        elif surface_canonical.casefold() != canonical.casefold():
            reason = 'surface does not map to the canonical name in the alias dictionary'
        elif not alias_pattern(candidate.surface).search(candidate.evidence):
            reason = 'surface absent from quote'
        occurrences = list(re.finditer(re.escape(candidate.evidence), text))
        eligible = []
        for match in occurrences:
            zones = [zone for start, end, _, zone in lines if start < match.end() and end > match.start()]
            if zones and all(zone in {'required', 'nice_to_have'} for zone in zones):
                eligible.append(match)
        if not eligible:
            reason = reason or 'quote missing or located outside requirements'
        reason = reason or context_problem(candidate.surface, candidate.evidence)
        if INJECTION.search(candidate.evidence):
            reason = 'instruction-like text is not evidence'
        if reason:
            rejected.append(RejectedItem(canonical=canonical, verdict='uncertain', reason=reason))
            continue
        match = eligible[0]
        kind = TYPES.get(canonical, candidate.kind)
        if canonical.casefold() in seen:
            continue
        seen.add(canonical.casefold())
        # Requirement heading wins over the model's label when it is explicit.
        zone = next((zone for start, end, _, zone in lines if start <= match.start() < end), 'unknown')
        requirement = zone if zone in {'required', 'nice_to_have'} else candidate.requirement
        mentions.append(SkillMention(id=f'm{len(mentions)}', surface=candidate.surface, canonical=canonical,
            kind=kind, requirement=requirement,
            evidence=EvidenceSpan(quote=candidate.evidence, start=match.start(), end=match.end())))
    return mentions, rejected


def attach_evidence(posting, extraction, text):
    mentions, rejected = ground([*extraction.mentions, *dictionary_candidates(text)], text)
    candidates = set(posting.required_skills + posting.nice_to_have_skills)
    grounded = {m.canonical for m in mentions}
    for missing in sorted(candidates - grounded):
        rejected.append(RejectedItem(canonical=missing, verdict='unsupported', reason='no literal evidence'))
    posting.skill_mentions = mentions
    posting.rejected_items = rejected
    posting.review_required = posting.review_required or bool(rejected) or bool(INJECTION.search(text))
    return posting
