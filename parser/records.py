"""Acceptance contract shared by the parser and standalone public exporter."""
SCHEMA_VERSION = 3


def is_accepted(record):
    return (record.get('schema_version') == SCHEMA_VERSION
            and record.get('validation_status') == 'validated'
            and record.get('review_required') is False and record.get('low_confidence') is False)
