"""YAML helpers (PyYAML, with a JSON fallback so pixelterm still starts
without it)."""
from __future__ import annotations

import json
import os

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

EXTS = ('.yaml', '.yml', '.json')


def load(path):
    with open(path, 'r', encoding='utf-8') as fh:
        text = fh.read()
    if path.endswith('.json') or yaml is None:
        return json.loads(text) if text.strip() else {}
    return yaml.safe_load(text) or {}


def dump(data, path, header=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        if header:
            for ln in header.splitlines():
                fh.write('# %s\n' % ln)
        if yaml is None or path.endswith('.json'):
            json.dump(data, fh, indent=2)
        else:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, default_flow_style=None, width=100)


def find(base_no_ext):
    for e in EXTS:
        if os.path.exists(base_no_ext + e):
            return base_no_ext + e
    return None
