import json
import sys
from pathlib import Path
from unittest.mock import Mock
import pytest
import parser.run as runner


@pytest.mark.parametrize('args,enabled,expected', [([], 'true', True), (['--no-publish'], 'true', False), ([], 'false', False)])
def test_cli_publishes_after_parsing(tmp_path, monkeypatch, args, enabled, expected):
    source = tmp_path / 'jobs.jsonl'
    def fake_run(*args, **kwargs):
        source.write_text(json.dumps({'title': 'Job', 'source_url': 'url'}))
        return 1, 0
    send = Mock(return_value={'changed': True, 'url': 'https://github.com/commit'})
    monkeypatch.setattr(runner, 'PARSED_DIR', tmp_path)
    monkeypatch.setattr(runner, 'run', fake_run)
    monkeypatch.setattr(runner, 'make_client', lambda: object())
    monkeypatch.setattr(runner, 'publish', send)
    monkeypatch.setattr(sys.stdout, 'reconfigure', lambda **kw: None, raising=False)
    monkeypatch.setattr(sys, 'argv', ['parser.run', *args])
    monkeypatch.setenv('AUTO_PUBLISH', enabled)
    monkeypatch.setenv('DATASET_KIND', 'synthetic')
    runner.main()
    assert send.called is expected
    if expected:
        send.assert_called_once_with(source, kind='synthetic')
    assert source.exists()


def test_failed_auto_publish_preserves_result_and_reports_failure(tmp_path, monkeypatch):
    source = tmp_path / 'jobs.jsonl'
    source.write_text('{"title":"Saved","source_url":"url"}')
    monkeypatch.setattr(runner, 'PARSED_DIR', tmp_path)
    monkeypatch.setattr(runner, 'run', lambda *a, **kw: (0, 0))
    monkeypatch.setattr(runner, 'make_client', lambda: object())
    monkeypatch.setattr(runner, 'publish', Mock(side_effect=RuntimeError('offline')))
    monkeypatch.setattr(sys.stdout, 'reconfigure', lambda **kw: None, raising=False)
    monkeypatch.setattr(sys, 'argv', ['parser.run'])
    monkeypatch.setenv('AUTO_PUBLISH', 'true')
    with pytest.raises(SystemExit, match='offline'):
        runner.main()
    assert json.loads(source.read_text())['title'] == 'Saved'
