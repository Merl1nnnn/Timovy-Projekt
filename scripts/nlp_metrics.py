"""Offline NLP diagnostics shared by the team evaluator and inspection CLI."""
from parser.normalize import normalize_skill
from parser.provenance import is_accepted


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {'precision': p, 'recall': r, 'f1': 2*p*r/(p+r) if p+r else 0.0,
            'tp': tp, 'fp': fp, 'fn': fn}


def macro_f1(rows):
    labels = sorted({v for a, b in rows for v in (a, b) if v is not None})
    scores = {label: prf(sum(a == b == label for a, b in rows),
                         sum(a != label and b == label for a, b in rows),
                         sum(a == label and b != label for a, b in rows))['f1'] for label in labels}
    return {'macro_f1': sum(scores.values())/len(scores) if scores else None,
            'per_class_f1': scores, 'examples': len(rows)}


def key(value):
    return normalize_skill(value).casefold()


def evaluate_nlp(gold, pred):
    result = {'gold_jobs': len(gold), 'prediction_coverage': len(set(gold) & set(pred))/len(gold) if gold else 0}
    for field in ('seniority', 'specialization', 'language'):
        rows = [(g[field], pred.get(jid, {}).get(field)) for jid, g in gold.items() if field in g]
        result[field] = macro_f1(rows)
    for field in ('certificates', 'role_specializations'):
        tp = fp = fn = count = 0
        for jid, g in gold.items():
            if field not in g: continue
            count += 1
            target = {key(v) for v in g[field]}
            found = {key(v) for v in pred.get(jid, {}).get(field, [])}
            tp += len(target & found); fp += len(found - target); fn += len(target - found)
        result[field] = {**prf(tp, fp, fn), 'annotated_jobs': count} if count else None
    mentions = valid = accepted_skills = covered = missing_text = 0
    injected = detected = false_rejections = supported_controls = 0
    accepted_jobs = 0
    for jid, g in gold.items():
        record = pred.get(jid, {})
        accepted_jobs += is_accepted(record)
        text = record.get('source_text')
        supported = set()
        for mention in record.get('skill_mentions', []):
            mentions += 1
            span = mention.get('evidence', {})
            start, end, quote = span.get('start'), span.get('end'), span.get('quote')
            literal = (isinstance(text, str) and type(start) is int and type(end) is int
                       and isinstance(quote, str) and 0 <= start < end <= len(text) and text[start:end] == quote)
            if literal and mention.get('verdict') == 'supported':
                valid += 1
                supported.add(key(mention['canonical']))
        names = {key(v) for f in ('required_skills', 'nice_to_have_skills') for v in record.get(f, [])}
        accepted_skills += len(names)
        covered += len(names & supported)
        if record and not isinstance(text, str): missing_text += 1
        rejected = {key(r['canonical']) for r in record.get('rejected_items', [])}
        for name in g.get('injected_errors', []):
            injected += 1
            # Rejecting and simultaneously accepting the same skill is not successful detection.
            detected += key(name) in rejected and key(name) not in names
        for name in g.get('supported_controls', []):
            supported_controls += 1
            false_rejections += key(name) not in names
    result['evidence'] = {'mentions': mentions, 'valid_supported_spans': valid,
                          'invalid_or_unconfirmed_spans': mentions-valid, 'jobs_without_source_text': missing_text,
                          'skills': accepted_skills, 'skills_with_valid_evidence': covered,
                          'coverage': covered/accepted_skills if accepted_skills else None,
                          'note': 'Literal spans measure traceability, not semantic correctness.'}
    result['validator'] = {'injected_errors': injected, 'detected_errors': detected,
                           'error_detection_rate': detected/injected if injected else None,
                           'supported_controls': supported_controls, 'false_rejections': false_rejections,
                           'false_rejection_rate': false_rejections/supported_controls if supported_controls else None}
    result['accepted_jobs'] = accepted_jobs
    result['accepted_coverage'] = accepted_jobs/len(gold) if gold else 0
    return result
