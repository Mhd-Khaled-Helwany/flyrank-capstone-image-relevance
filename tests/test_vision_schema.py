import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from vision.schema import TagSchema, validate_tag_payload

def test_valid_payload_passes():
    payload = {
        'subject': 'red fox',
        'category': 'animal',
        'attributes': ['orange fur', 'wild', 'forest'],
        'caption': 'A red fox standing in a forest',
        'confidence': 0.94,
    }

    tag, errors = validate_tag_payload(payload)
    assert errors is None
    assert isinstance(tag, TagSchema)
    assert tag.subject == 'red fox'
    assert tag.category == 'animal'


def test_invalid_payload_fails_cleanly():
    payload = {
        'subject': 'red fox',
        'category': 'electronics',
        'attributes': ['orange fur'],
        'caption': 'A red fox standing in a forest',
        'confidence': 1.5,
    }

    tag, errors = validate_tag_payload(payload)
    assert tag is None
    assert isinstance(errors, list)
    assert len(errors) >= 2