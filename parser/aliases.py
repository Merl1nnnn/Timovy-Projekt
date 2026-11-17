"""Версійований словник назв, який можна доповнювати без зміни коду."""
import json
from pathlib import Path

PATH = Path(__file__).with_name('resources') / 'aliases.json'
KINDS = {'technology', 'tool', 'certification', 'language', 'methodology', 'soft_skill'}


def load_registry(path: Path = PATH):
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data.get('version'), str) or not isinstance(data.get('entries'), list):
        raise ValueError('Alias registry needs version and entries')
    owners = {}
    for entry in data['entries']:
        if entry['kind'] not in KINDS or not entry['canonical'].strip():
            raise ValueError('Invalid alias entry')
        for alias in [entry['canonical'], *entry['aliases']]:
            key = alias.casefold().strip()
            if not key or (key in owners and owners[key] != entry['canonical']):
                raise ValueError(f'Ambiguous alias: {alias}')
            owners[key] = entry['canonical']
    return data


REGISTRY = load_registry()
VERSION = REGISTRY['version']
ALIASES = {e['canonical']: e['aliases'] for e in REGISTRY['entries']}
TYPES = {e['canonical']: e['kind'] for e in REGISTRY['entries']}
