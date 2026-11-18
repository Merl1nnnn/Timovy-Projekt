import base64
import json
from pathlib import Path
import tempfile
import unittest
from scripts.publish_results import NotFound, PublishConflict, merge_snapshots, publish


def snapshot(jobs):
    return {'schema_version': 1, 'dataset_kind': 'synthetic', 'jobs': jobs}


def encoded(data, sha='head'):
    return {'encoding': 'base64', 'content': base64.b64encode(json.dumps(data).encode()).decode(), 'sha': sha}


class PublishingTests(unittest.TestCase):
    def test_merges_other_participants_and_keeps_newer_results(self):
        remote = snapshot([{'source_url': 'a', 'title': 'new', 'parsed_at': '2026-11-10T12:00:00Z'},
                           {'source_url': 'b', 'title': 'other participant'}])
        local = snapshot([{'source_url': 'a', 'title': 'old', 'parsed_at': '2026-11-09T12:00:00Z'},
                          {'source_url': 'c', 'title': 'local'}])
        jobs = merge_snapshots(remote, local)['jobs']
        self.assertEqual([j['source_url'] for j in jobs], ['a', 'b', 'c'])
        self.assertEqual(jobs[0]['title'], 'new')

    def test_conflict_refetches_and_preserves_concurrent_job(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'jobs.jsonl'
            source.write_text(json.dumps({'source_url': 'local', 'title': 'Local'}))
            requests = []
            def api(token, method, endpoint, body=None):
                requests.append((method, body))
                if method == 'GET':
                    return encoded(snapshot([] if len(requests) == 1 else [{'source_url': 'other', 'title': 'Other'}]), str(len(requests)))
                if len(requests) == 2:
                    raise PublishConflict()
                data = json.loads(base64.b64decode(body['content']))
                self.assertEqual({j['source_url'] for j in data['jobs']}, {'local', 'other'})
                self.assertEqual(body['sha'], '3')
                return {'commit': {'html_url': 'https://github.com/example/commit'}}
            result = publish(source, token='fake', request=api)
            self.assertTrue(result['changed'])
            self.assertEqual([m for m, _ in requests], ['GET', 'PUT', 'GET', 'PUT'])

    def test_unchanged_data_does_not_create_commit(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'jobs.jsonl'
            record = {'source_url': 'same', 'title': 'Same'}
            source.write_text(json.dumps(record))
            def api(token, method, endpoint, body=None):
                self.assertEqual(method, 'GET')
                return encoded(snapshot([record]))
            self.assertFalse(publish(source, token='fake', request=api)['changed'])

    def test_failure_keeps_local_file(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'jobs.jsonl'
            original = json.dumps({'source_url': 'a', 'title': 'A'})
            source.write_text(original)
            def unavailable(*args):
                raise RuntimeError('offline')
            with self.assertRaisesRegex(RuntimeError, 'offline'):
                publish(source, token='fake', request=unavailable)
            self.assertEqual(source.read_text(), original)

    def test_real_data_goes_to_its_own_file_and_creates_it(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'jobs.jsonl'
            source.write_text(json.dumps({'source_url': 'https://www.profesia.sk/O1', 'title': 'Real'}))
            calls = []
            def api(token, method, endpoint, body=None):
                calls.append((method, endpoint, body))
                if method == 'GET':
                    raise NotFound('missing')
                self.assertNotIn('sha', body)
                self.assertEqual(json.loads(base64.b64decode(body['content']))['dataset_kind'], 'real')
                return {'commit': {'html_url': 'https://github.com/example/commit'}}
            self.assertTrue(publish(source, kind='real', token='fake', request=api)['changed'])
            self.assertTrue(all(e.split('?')[0].endswith('/frontend/data/jobs_real.json') for _, e, _ in calls))

    def test_synthetic_data_keeps_the_original_file(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'jobs.jsonl'
            source.write_text(json.dumps({'source_url': 'a', 'title': 'A'}))
            endpoints = []
            def api(token, method, endpoint, body=None):
                endpoints.append(endpoint.split('?')[0])
                if method == 'GET':
                    return encoded(snapshot([]))
                return {'commit': {'html_url': 'https://github.com/example/commit'}}
            publish(source, token='fake', request=api)
            self.assertTrue(endpoints and all(e.endswith('/contents/frontend/data/jobs.json') for e in endpoints))

    def test_mixed_datasets_are_rejected(self):
        remote = snapshot([{'source_url': 'a', 'title': 'A'}])
        local = {**snapshot([]), 'dataset_kind': 'real'}
        with self.assertRaises(RuntimeError):
            merge_snapshots(remote, local)


if __name__ == '__main__':
    unittest.main()
