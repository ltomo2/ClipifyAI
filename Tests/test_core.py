import json
import math
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app.analysis.moments import validate, deduplicate, windows, analyse
from app.core.jobs import Job, Cancelled
from app.core.storage import atomic_json, Project
from app.rendering.captions import write_ass
from app.services.ollama import local_tag


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.words = [{'start': i, 'end': i + .7, 'word': f' word{i}'} for i in range(900)]
        self.clip = dict(start=10, end=50, score=85, hook='An unexpected answer', reason='The question establishes the expectation and the answer reverses it.')

    def test_invalid_times_and_scores_rejected(self):
        for change in [{'start': -1}, {'end': 9999}, {'end': 4}, {'score': math.nan}, {'start': math.inf}, {'score': 101}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(self.clip | change, self.words, 900, 30, 60)

    def test_word_edges_and_duration(self):
        clip = validate(self.clip, self.words, 900, 30, 60)
        self.assertEqual(clip['start'], 9.88)
        self.assertEqual(clip['end'], 49.9)
        with self.assertRaises(ValueError):
            validate(self.clip | {'end': 15}, self.words, 900, 30, 60)

    def test_windows_cover_hours_and_overlap(self):
        duration = 7200
        words = [{'start': i, 'end': i + .5, 'word': ' data'} for i in range(duration)]
        ws = list(windows(words, duration))
        covered = {int(w['start']) for _, _, _, group in ws for w in group}
        self.assertEqual(covered, set(range(duration)))
        self.assertEqual(ws[-1][2], duration)
        for a, b in zip(ws, ws[1:]):
            self.assertEqual(a[2] - b[1], 45)

    def test_dedup_keeps_stronger(self):
        clips = [self.clip, self.clip | {'start': 12, 'end': 52, 'score': 90}, self.clip | {'start': 100, 'end': 140}]
        result = deduplicate(clips)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['score'], 90)

    def test_subtitle_offsets_and_injection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.ass'
            words = [{'start': 100.1, 'end': 100.5, 'word': '{\\pos(1,1)}Hello'}, {'start': 100.6, 'end': 101.0, 'word': ' world'}]
            write_ass(path, words, 100, 102, {'font_size': 72, 'highlight': '#B58AFF', 'caption_y': 1500})
            text = path.read_text(encoding='utf-8-sig')
            self.assertIn('0:00:00.10,0:00:00.50', text)
            self.assertIn('\\c&HFF8AB5&', text)
            self.assertNotIn('{\\pos(1,1)}', text)
            self.assertEqual(text.count('Dialogue:'), 2)

    def test_atomic_save_and_unknown_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'project.json'
            atomic_json(path, {'schema': 999, 'private': 'preserved'})
            with self.assertRaises(ValueError):
                Project(folder)
            self.assertEqual(json.loads(path.read_text())['private'], 'preserved')
            self.assertEqual(len(list(Path(folder).glob('*.tmp'))), 0)

    def test_only_local_model_tags(self):
        for name in ['qwen3-vl:2b-cloud', 'https://host/model', 'someone/model:3b', 'llama3.2']:
            with self.assertRaises(ValueError):
                local_tag(name)
        self.assertEqual(local_tag('llama3.2:3b'), 'llama3.2:3b')

    def test_cancel_kills_subprocess(self):
        import sys
        job = Job()
        timer = threading.Timer(.3, job.stop.set)
        timer.start()
        begin = time.monotonic()
        with self.assertRaises(Cancelled):
            job.run([sys.executable, '-c', 'import time; time.sleep(30)'])
        timer.join()
        self.assertLess(time.monotonic() - begin, 3)

    def test_analysis_resumes_all_windows_without_requery(self):
        from app.core.storage import DEFAULTS
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            p = SimpleNamespace(folder=Path(folder))
            opts = dict(DEFAULTS)
            transcript = {'words': self.words, 'duration': 900}
            calls = []
            def generate(tag, prompt, job):
                calls.append(prompt)
                import re
                start = float(re.search(r'\[([\d.]+)–', prompt).group(1))
                return {'summary': 'Context preserved', 'clips': [dict(self.clip, start=start + 10, end=start + 50)]}
            with patch('app.analysis.moments.Ollama.require'), patch('app.analysis.moments.Ollama.generate', side_effect=generate):
                first = analyse(p, transcript, opts, Job())
                count = len(calls)
                second = analyse(p, transcript, opts, Job())
                self.assertEqual(first, second)
                self.assertEqual(len(calls), count)
                self.assertGreater(count, 5)
                self.assertIn('word899', calls[-1])

    def test_backup_preserves_old_code_and_media(self):
        from install_into_existing import install
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'old'
            target.mkdir()
            (target / 'clipify.py').write_text('old source')
            (target / 'important.mp4').write_bytes(b'preserve me')
            (target / 'Projects').mkdir()
            (target / 'Projects' / 'old.json').write_text('legacy results')
            backup = install(target)
            import zipfile
            with zipfile.ZipFile(backup / 'previous_source.zip') as archive:
                self.assertEqual(archive.read('clipify.py'), b'old source')
            self.assertEqual((target / 'important.mp4').read_bytes(), b'preserve me')
            self.assertEqual((target / 'Projects' / 'old.json').read_text(), 'legacy results')
            self.assertNotEqual((target / 'clipify.py').read_text(), 'old source')


if __name__ == '__main__':
    unittest.main()
