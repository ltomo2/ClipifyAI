"""Versioned local storage. Media and legacy projects are never deleted."""
from pathlib import Path
import hashlib
import json
import os
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 1
DEFAULTS = {
    'min_duration': 30, 'max_duration': 60, 'count': 5,
    'layout': 'blur', 'language': 'en', 'whisper_model': 'tiny.en',
    'transcriber': 'whisper', 'device': 'auto', 'faster_model_path': '',
    'visual': False, 'use_scenes': False, 'text_model': 'llama3.2:3b', 'vision_model': 'qwen3-vl:2b',
    'font_size': 72, 'highlight': '#B58AFF', 'caption_y': 1500,
    'exports': str(ROOT / 'Exports'), 'encoder': 'libx264',
}

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def settings():
    path = ROOT / 'settings.json'
    try:
        saved = read_json(path) if path.exists() else {}
        return DEFAULTS | ({k: v for k, v in saved.items() if k in DEFAULTS} if isinstance(saved, dict) else {})
    except (ValueError, OSError):
        import logging
        logging.warning('Unreadable settings preserved; using defaults: %s', path)
        return dict(DEFAULTS)


def fingerprint(source):
    p = Path(source).resolve()
    st = p.stat()
    # Sample both ends as well as path, length and modification time.
    h = hashlib.sha256(f'{p}|{st.st_size}|{st.st_mtime_ns}'.encode())
    with p.open('rb') as f:
        h.update(f.read(1024 * 1024))
        f.seek(max(0, st.st_size - 1024 * 1024))
        h.update(f.read(1024 * 1024))
    return h.hexdigest()


class Project:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / 'project.json'
        self.data = read_json(self.path)
        if self.data.get('schema') != SCHEMA:
            raise ValueError('This project uses another schema. It was preserved; open it with its original version.')

    @classmethod
    def create(cls, source, options):
        identity = fingerprint(source)
        folder = ROOT / 'Projects' / identity[:16]
        if (folder / 'project.json').exists():
            p = cls(folder)
            if p.data['fingerprint'] != identity:
                raise ValueError('Source identity conflict; existing project preserved.')
            return p
        folder.mkdir(parents=True, exist_ok=True)
        atomic_json(folder / 'project.json', {
            'schema': SCHEMA, 'id': identity[:16], 'fingerprint': identity,
            'name': Path(source).stem, 'source': str(Path(source).resolve()),
            'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'status': 'new',
            'stage': 'Waiting', 'settings': options, 'candidates': [], 'renders': [],
        })
        return cls(folder)

    def save(self):
        atomic_json(self.path, self.data)

    def verify_source(self):
        if fingerprint(self.data['source']) != self.data['fingerprint']:
            raise ValueError('The source changed. Import it again to create a separate project.')


def projects():
    result = []
    for path in (ROOT / 'Projects').glob('*/project.json'):
        try:
            result.append(Project(path.parent))
        except (ValueError, OSError, KeyError):
            continue  # Unknown/old data remains untouched.
    return sorted(result, key=lambda p: p.data['created'], reverse=True)
