import json

import pytest

from parser.context import enrich, salary_info
from parser.evidence import dictionary_candidates, ground
from parser.normalize import normalize
from parser.provenance import provenance
from parser.run import run
from parser.schema import CandidateMention, JobExtraction
from scripts.evaluate_nlp import evaluate
from scripts.export_results import export
from scripts.nlp_metrics import evaluate_nlp
from tests.test_parser import FakeClient, GOOD, PAGE_TEXT


@pytest.mark.parametrize('text', [
    'About us:\nWe use Python in our internal projects.',
    'Benefits:\n- Python workshops.',
    'Requirements:\n- Java is not required.',
    'Requirements:\n- Python or Java.',
])
def test_context_is_not_accepted_as_mandatory_skill(text):
    mentions, _ = ground(dictionary_candidates(text), text)
    assert not mentions


def test_java_is_not_evidence_for_javascript_or_the_reverse():
    candidate = CandidateMention(surface='Java', canonical='Java', kind='technology',
                                 requirement='required', evidence='JavaScript is required.')
    mentions, rejected = ground([candidate], 'Requirements:\nJavaScript is required.')
    assert not mentions and rejected


def test_inline_nice_marker_does_not_change_following_items():
    text = 'Requirements:\n- Python (výhodou)\n- SQL\nVýhodou je Kafka\n- Java'
    mentions, _ = ground(dictionary_candidates(text), text)
    assert {m.canonical: m.requirement for m in mentions} == {
        'Python': 'nice_to_have', 'SQL': 'required', 'Kafka': 'nice_to_have', 'Java': 'required'}


@pytest.mark.parametrize('text,original,monthly,period,basis', [
    ('Salary: 42 000 – 48 000 EUR ročne brutto', 42000, 3500, 'year', 'gross'),
    ('Salary: €18.50/hour gross', 18.5, None, 'hour', 'gross'),
    ('Salary: EUR 2,000 net/month', 2000, None, 'month', 'net'),
    ('Salary: 2 000 EUR', 2000, None, None, 'unknown'),
])
def test_legacy_salary_never_receives_hourly_annual_or_net_raw_amount(text, original, monthly, period, basis):
    posting = normalize(JobExtraction(**GOOD), 'u', PAGE_TEXT)
    result = enrich(posting, text + '\nWe are looking for a developer with experience.')
    assert result.salary_original_min == original
    assert result.salary_min == result.salary_monthly_min == monthly
    assert (result.salary_period, result.salary_basis) == (period, basis)


def test_salary_does_not_pick_first_of_conflicting_offers_or_benefits():
    assert salary_info('Salary: 2000 EUR gross/month\nSalary: 4000 EUR gross/month') is None
    assert salary_info('Meal vouchers 500 EUR monthly') is None
    assert salary_info('Salary: 2000 EUR - 3000 USD gross/month') is None


def test_role_tags_are_independent_of_programming_language():
    plain = normalize(JobExtraction(**(GOOD | {'title': 'Python developer', 'specialization': 'Python'})), 'u', PAGE_TEXT)
    backend = normalize(JobExtraction(**(GOOD | {'title': 'Python Backend developer', 'specialization': 'Python'})), 'u', PAGE_TEXT)
    assert plain.role_specializations == []
    assert backend.role_specializations == ['Backend']


def raw_fixture(tmp_path):
    raw = tmp_path / 'raw'
    (raw / 'profesia').mkdir(parents=True)
    (raw / 'profesia/1.html').write_text(f'<p>{PAGE_TEXT}</p>')
    (raw / 'profesia/index.json').write_text(json.dumps([
        {'site': 'profesia', 'id': '1', 'url': 'u', 'file': 'profesia/1.html'}]))
    return raw, tmp_path / 'out'


def test_cache_changes_on_model_revision_and_review_is_replaced(tmp_path):
    raw, out = raw_fixture(tmp_path)
    client = FakeClient([json.dumps(GOOD)])
    assert run(client, raw, out) == (1, 0)
    assert run(FakeClient([]), raw, out) == (0, 0)
    revised = FakeClient([json.dumps(GOOD)])
    revised.model_revision = 'new-weights'
    assert provenance(client)['pipeline_fingerprint'] != provenance(revised)['pipeline_fingerprint']
    assert run(revised, raw, out) == (1, 0)
    # A failed refresh invalidates old accepted output and preserves diagnostics.
    assert run(FakeClient(['invalid'] * 3), raw, out, force=True) == (0, 1)
    assert (out / 'jobs.jsonl').read_text() == ''
    assert len((out / 'review.jsonl').read_text().splitlines()) == 1
    assert run(FakeClient([json.dumps(GOOD)]), raw, out) == (1, 0)
    assert (out / 'review.jsonl').read_text() == ''
    assert json.loads((out / 'results.jsonl').read_text())['validation_status'] == 'validated'
    assert run(FakeClient(['invalid'] * 3), raw, out, force=True) == (0, 1)
    assert (out / 'results.jsonl').read_text() == ''
    assert run(FakeClient([json.dumps(GOOD)]), raw, out) == (1, 0)


def test_uncertain_result_is_not_retried_or_duplicated_until_forced(tmp_path):
    raw, out = raw_fixture(tmp_path)
    bad = GOOD | {'required_skills': [*GOOD['required_skills'], 'Rust']}
    assert run(FakeClient([json.dumps(bad)]), raw, out) == (1, 0)
    assert (out / 'jobs.jsonl').read_text() == ''
    assert run(FakeClient([]), raw, out) == (0, 0)
    assert len((out / 'review.jsonl').read_text().splitlines()) == 1
    assert json.loads((out / 'results.jsonl').read_text())['validation_status'] == 'review'


def test_export_refuses_review_and_never_exports_source_or_quotes(tmp_path):
    record = {'title': 'Developer', 'schema_version': 3, 'validation_status': 'validated',
              'review_required': False, 'low_confidence': False, 'source_text': 'secret',
              'skill_mentions': ['private quote'], 'role_specializations': ['Backend']}
    source, target = tmp_path / 'in.jsonl', tmp_path / 'out.json'
    source.write_text(json.dumps(record))
    job = export(source, target, 'real')['jobs'][0]
    assert job['role_specializations'] == ['Backend']
    assert 'source_text' not in job and 'skill_mentions' not in job
    previous = target.read_bytes()
    source.write_text(json.dumps(record | {'review_required': True}))
    with pytest.raises(ValueError): export(source, target, 'real')
    assert target.read_bytes() == previous


def test_metrics_penalize_missing_and_unexpected_labels_and_false_rejections():
    gold = {'1': {'seniority': 'senior', 'injected_errors': ['Rust'], 'supported_controls': ['Python']},
            '2': {'seniority': 'junior'}}
    pred = {'1': {'seniority': 'lead', 'required_skills': ['Rust'], 'rejected_items': [{'canonical': 'Rust'}]}}
    metrics = evaluate_nlp(gold, pred)
    assert metrics['seniority']['macro_f1'] == 0
    assert set(metrics['seniority']['per_class_f1']) == {'senior', 'junior', 'lead'}
    assert metrics['validator']['error_detection_rate'] == 0  # still accepted despite rejection
    assert metrics['validator']['false_rejection_rate'] == 1
    assert metrics['prediction_coverage'] == .5


def test_inspection_evaluation_rejects_duplicate_inputs_and_bad_spans():
    row = {'source_url': 'u', 'required_skills': ['Python'], 'seniority': 'senior'}
    with pytest.raises(ValueError, match='Duplicate'): evaluate([row], [row, row])
    result = evaluate([row], [row | {'source_text': 'Python', 'skill_mentions': [{
        'canonical': 'Python', 'verdict': 'supported', 'evidence': {'start': -1, 'end': 6, 'quote': 'Python'}}]}])
    assert result['evidence']['invalid_or_unconfirmed_spans'] == 1
