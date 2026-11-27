"""Regression checks for public salary units and standalone publishing commands."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

import scripts.publish_results as publisher
from scripts.export_results import export
from tests.test_publishing import encoded, snapshot

ROOT = Path(__file__).resolve().parents[1]


def accepted(**fields):
    return {'schema_version': 3, 'validation_status': 'validated',
            'review_required': False, 'low_confidence': False,
            'title': 'Synthetic developer', 'source_url': 'https://example.invalid/1', **fields}


def test_export_pairs_monthly_amount_with_monthly_period_and_keeps_original(tmp_path):
    source = tmp_path / 'jobs.jsonl'
    source.write_text(json.dumps(accepted(salary_min=3500, salary_max=4000, salary_currency='EUR',
        salary_original_min=42000, salary_original_max=48000, salary_period='year', salary_basis='gross')))
    job = export(source, tmp_path / 'public.json', 'synthetic')['jobs'][0]
    assert (job['salary_min'], job['salary_max'], job['salary_period']) == (3500, 4000, 'month')
    assert (job['salary_original_min'], job['salary_original_max'], job['salary_original_period']) == (42000, 48000, 'year')


@pytest.mark.parametrize('script', ['export_results.py', 'publish_results.py'])
def test_documented_direct_command_works_outside_repository(tmp_path, script):
    source = tmp_path / 'jobs.jsonl'
    source.write_text(json.dumps(accepted()))
    target = tmp_path / 'public.json'
    command = [sys.executable, str(ROOT / 'scripts' / script), '--input', str(source), '--output', str(target)]
    if script == 'publish_results.py': command.append('--dry-run')
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(target.read_text())['jobs'][0]['title'] == 'Synthetic developer'


def isolated_config(tmp_path, monkeypatch, text):
    env = tmp_path / '.env'
    env.write_text(text)
    monkeypatch.setattr(publisher, 'ENV_FILE', env)
    for key in ('SKILLMINER_OFFLINE', 'SKILLMINER_BRANCH', 'SKILLMINER_REPOSITORY'):
        monkeypatch.delenv(key, raising=False)
    # Register loaded dotenv values with monkeypatch so they are restored after each test.
    monkeypatch.setenv('SKILLMINER_OFFLINE', '')
    monkeypatch.delenv('SKILLMINER_OFFLINE')
    monkeypatch.setenv('SKILLMINER_BRANCH', '')
    monkeypatch.delenv('SKILLMINER_BRANCH')
    monkeypatch.setenv('SKILLMINER_REPOSITORY', '')
    monkeypatch.delenv('SKILLMINER_REPOSITORY')


@pytest.mark.parametrize('config', ['', 'SKILLMINER_OFFLINE=true\n', 'SKILLMINER_OFFLINE=unexpected\n'])
def test_missing_disabled_or_invalid_publication_config_stops_before_auth_and_network(tmp_path, monkeypatch, config):
    isolated_config(tmp_path, monkeypatch, config)
    auth, api = Mock(), Mock()
    monkeypatch.setattr(publisher, 'auth_token', auth)
    monkeypatch.setattr(publisher, 'api', api)
    with pytest.raises(RuntimeError, match='Publication is disabled'):
        publisher.publish(tmp_path / 'not-needed.jsonl')
    auth.assert_not_called()
    api.assert_not_called()


def test_enabled_publication_requires_explicit_target_branch(tmp_path, monkeypatch):
    isolated_config(tmp_path, monkeypatch, 'SKILLMINER_OFFLINE=false\n')
    auth, api = Mock(), Mock()
    monkeypatch.setattr(publisher, 'auth_token', auth)
    monkeypatch.setattr(publisher, 'api', api)
    with pytest.raises(RuntimeError, match='branch explicitly'):
        publisher.publish(tmp_path / 'not-needed.jsonl')
    auth.assert_not_called()
    api.assert_not_called()


@pytest.mark.parametrize('target', [None, 'explicit-branch'])
def test_publisher_reads_dotenv_from_repository_independently_of_cwd(tmp_path, monkeypatch, target):
    isolated_config(tmp_path, monkeypatch, 'SKILLMINER_OFFLINE=false\nSKILLMINER_BRANCH=configured-branch\nSKILLMINER_REPOSITORY=example/test\n')
    monkeypatch.chdir(tmp_path)
    source = tmp_path / 'jobs.jsonl'
    source.write_text(json.dumps(accepted()))
    api = Mock(side_effect=[encoded(snapshot([])), {'commit': {'html_url': 'https://example.invalid/commit'}}])
    monkeypatch.setattr(publisher, 'api', api)
    result = publisher.publish(source, token='test-only', branch=target)
    assert result['changed']
    branch = target or 'configured-branch'
    assert api.call_args_list[0].args[2].startswith('/repos/example/test/')
    assert api.call_args_list[0].args[2].endswith('?ref=' + branch)
    assert api.call_args_list[1].args[3]['branch'] == branch


def test_process_environment_overrides_dotenv(tmp_path, monkeypatch):
    isolated_config(tmp_path, monkeypatch, 'SKILLMINER_OFFLINE=false\nSKILLMINER_BRANCH=from-file\n')
    monkeypatch.setenv('SKILLMINER_OFFLINE', 'true')
    with pytest.raises(RuntimeError, match='Publication is disabled'):
        publisher.publish(tmp_path / 'not-needed.jsonl', token='test-only')
    assert os.environ['SKILLMINER_OFFLINE'] == 'true'
