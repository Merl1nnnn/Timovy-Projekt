"""Докази прив'язані до незміненого html_to_text: індекси Python Unicode, [start, end)."""
import re

from parser.aliases import ALIASES, TYPES
from parser.normalize import fold, normalize_skill
from parser.schema import CandidateMention, EvidenceSpan, RejectedItem, SkillMention

REQUIRED = re.compile(r'poziadav|pozadujeme|pozadav|requirements|must.have|what you bring|looking for|hladame|hledame|co.*ovladat', re.I)
NICE = re.compile(r'vyhodou|vyhod|nice.to.have|bonus points|plusove body', re.I)
OTHER = re.compile(r'napln prace|benefit|what you.ll do|what we offer|ponukame|nabizime|podobne ponuky|people also viewed|kontakt', re.I)
NEGATION = re.compile(r'\b(?:not required|not necessary|no need|do not require|nevyzadujeme|nepozadujeme|nie je potrebn|neni nutn|bez znalosti)\w*', re.I)
INJECTION = re.compile(r'ignore (?:all |the )?(?:previous|system)|\bsystem\s*:|disregard.*instructions', re.I)


def sections(text):
    zone = 'unknown'
    at = 0
    for line in text.splitlines(keepends=True):
        folded = fold(line)
        # A heading changes the section; a bullet with '(výhodou)' changes only that item.
        if OTHER.search(folded):
            zone = 'other'
        elif REQUIRED.search(folded):
            zone = 'required'
        elif NICE.search(folded) and not line.lstrip().startswith('-'):
            zone = 'nice_to_have'
        yield at, at + len(line), line.rstrip('\r\n'), ('nice_to_have' if NICE.search(folded) and zone != 'other' else zone)
        at += len(line)


def alias_pattern(alias):
    return re.compile(r'(?<![\w+#])' + re.escape(alias) + r'(?![\w+#])', re.I)


def dictionary_candidates(text):
    """Швидкий словниковий NER. Усі кандидати ще потребують LLM-перевірки."""
    candidates = []
    for _, _, line, section in sections(text):
        if section == 'other' or not line.strip():
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
        elif candidate.surface.casefold() not in candidate.evidence.casefold():
            reason = 'surface absent from quote'
        occurrences = list(re.finditer(re.escape(candidate.evidence), text))
        eligible = []
        for match in occurrences:
            zones = [zone for start, end, _, zone in lines if start < match.end() and end > match.start()]
            if 'other' not in zones:
                eligible.append(match)
        if not eligible:
            reason = reason or 'quote missing or located outside requirements'
        if NEGATION.search(fold(candidate.evidence)):
            reason = 'negated requirement needs expert review'
        if INJECTION.search(candidate.evidence):
            reason = 'instruction-like text is not evidence'
        if reason:
            rejected.append(RejectedItem(canonical=canonical, verdict='uncertain', reason=reason))
            continue
        match = eligible[0]
        kind = TYPES.get(canonical, candidate.kind)
        if canonical in seen:
            continue
        seen.add(canonical)
        # Requirement heading wins over the model's label when it is explicit.
        zone = next((zone for start, end, _, zone in lines if start <= match.start() < end), 'unknown')
        requirement = zone if zone in {'required', 'nice_to_have'} else candidate.requirement
        mentions.append(SkillMention(id=f'm{len(mentions)}', surface=candidate.surface, canonical=canonical,
            kind=kind, requirement=requirement,
            evidence=EvidenceSpan(quote=candidate.evidence, start=match.start(), end=match.end())))
    return mentions, rejected


def attach_evidence(posting, extraction, text):
    mentions, rejected = ground([*extraction.mentions, *dictionary_candidates(text)], text)
    candidates = set(posting.required_skills + posting.nice_to_have_skills + posting.technologies)
    grounded = {m.canonical for m in mentions}
    for missing in sorted(candidates - grounded):
        rejected.append(RejectedItem(canonical=missing, verdict='unsupported', reason='no literal evidence'))
    posting.skill_mentions = mentions
    posting.rejected_items = rejected
    posting.review_required = posting.review_required or bool(rejected) or bool(INJECTION.search(text))
    return posting
