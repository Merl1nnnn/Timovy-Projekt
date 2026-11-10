import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.export_results import export


class ExportTests(unittest.TestCase):
    def test_allowlist_redaction_and_deduplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = {'title': 'Developer test@example.com +421 900 123 456',
                      'source_url': 'http://localhost/job/1', 'technologies': ['Python'],
                      'raw_html': 'private raw text', 'api_key': 'SECRET'}
            source = root / 'in.jsonl'
            source.write_text('\n'.join([json.dumps(record)] * 2))
            result = export(source, root / 'out.json', 'synthetic')
            self.assertEqual(len(result['jobs']), 1)
            self.assertEqual(result['jobs'][0]['title'], 'Developer [email removed] [phone removed]')
            self.assertNotIn('api_key', result['jobs'][0])
            self.assertNotIn('raw_html', result['jobs'][0])

    def test_invalid_input_preserves_published_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'out.json'
            output.write_text('previous')
            source = root / 'in.jsonl'
            for content in ['', '{"title":"job","technologies":"Python"}', 'invalid json']:
                source.write_text(content)
                with self.assertRaises(ValueError):
                    export(source, output, 'synthetic')
                self.assertEqual(output.read_text(), 'previous')


if __name__ == '__main__':
    unittest.main()
