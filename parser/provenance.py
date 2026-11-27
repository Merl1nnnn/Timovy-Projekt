"""Stable cache identity for NLP code, aliases and local model configuration."""
from hashlib import sha256
import json
from pathlib import Path

from parser.aliases import VERSION
from parser.extract import PROMPT_VERSION
from parser.validator import VALIDATOR_VERSION

from parser.records import SCHEMA_VERSION, is_accepted
ROOT = Path(__file__).resolve().parent
INPUTS = ('extract.py', 'schema.py', 'normalize.py', 'context.py', 'evidence.py',
          'validator.py', 'quality.py', 'html_text.py', 'llm.py', 'aliases.py',
          'resources/aliases.json', 'provenance.py', 'run.py', 'records.py')


def provenance(client):
    config = {key: getattr(client, key, None) for key in ('name', 'url', 'num_ctx', 'model_revision')}
    config['code'] = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in INPUTS}
    return {'schema_version': SCHEMA_VERSION, 'prompt_version': PROMPT_VERSION,
            'validator_version': VALIDATOR_VERSION, 'alias_version': VERSION,
            'model_revision': config['model_revision'],
            'pipeline_fingerprint': sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()}
