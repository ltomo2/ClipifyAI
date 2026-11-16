from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from app.core.jobs import Job
from app.core.storage import DEFAULTS
from app.services.media import probe, tool
from app.rendering.export import render


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        cls.source = cls.folder / 'source.mp4'
        Job().run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=15:duration=4',
            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', cls.source])
        cls.project = SimpleNamespace(folder=cls.folder, data={'source': str(cls.source), 'id': 'test', 'media': probe(cls.source)})
        cls.candidate = {'id': 'test', 'start': .5, 'end': 3.5, 'score': 50, 'hook': 'Test clip', 'reason': 'Fixture'}
        cls.transcript = {'words': [{'start': 1, 'end': 2, 'word': 'Example'}]}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_tracked_crop_commands_and_nvenc_cpu_retry(self):
        options = dict(DEFAULTS, layout='auto', encoder='h264_nvenc', exports=str(self.folder / 'out'))
        tracking = {'width': 100, 'positions': [(0, 0), (1, 50), (2, 100)]}
        original = Job.run
        attempts = []
        def fake_nvenc(job, args, cwd=None):
            if 'h264_nvenc' in args:
                attempts.append('nvenc')
                raise RuntimeError('Simulated unavailable NVENC device')
            return original(job, args, cwd)
        with patch('app.rendering.export.track', return_value=(tracking, 'Controlled tracking fixture')), patch.object(Job, 'run', fake_nvenc):
            result = render(self.project, self.candidate, self.transcript, options, Job())
        self.assertEqual(attempts, ['nvenc'])
        self.assertEqual(result['layout'], 'tracked')
        self.assertEqual(result['settings']['encoder'], 'libx264')
        self.assertEqual(result['media']['width'], 1080)
        self.assertTrue(Path(result['thumbnail']).is_file())
        Job().run([tool('ffmpeg'), '-v', 'error', '-i', result['path'], '-f', 'null', '-'])

    def test_missing_cascade_backend_falls_back(self):
        from app.rendering.tracking import track
        with patch.dict('sys.modules', {'cv2': SimpleNamespace()}):
            result, reason = track(self.source, 0, 3, Job())
        self.assertIsNone(result)
        self.assertIn('blurred background', reason)

    def test_low_confidence_uses_blurred_background(self):
        options = dict(DEFAULTS, layout='auto', exports=str(self.folder / 'out'))
        with patch('app.rendering.export.track', return_value=(None, 'No confident face')):
            result = render(self.project, self.candidate, self.transcript, options, Job())
        self.assertEqual(result['layout'], 'blur')
        self.assertEqual(result['captions'], 'burned-in')
        self.assertAlmostEqual(result['media']['duration'], 3, delta=.1)


if __name__ == '__main__':
    unittest.main()
