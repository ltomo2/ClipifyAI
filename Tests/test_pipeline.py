"""Real extraction/rendering and persistent resume, with explicitly mocked AI inference."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.core.jobs import Job
from app.core.pipeline import run_pipeline
from app.core.storage import DEFAULTS, Project
from app.services.media import tool


class PipelineTests(unittest.TestCase):
    def test_completed_project_reopens_without_duplicate_render(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source.mp4'
            Job().run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=15:duration=10',
                '-f', 'lavfi', '-i', 'sine=frequency=330:duration=10', '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', source])
            options = dict(DEFAULTS, min_duration=5, max_duration=8, count=1, exports=str(root / 'exports'))
            transcript = {'words': [{'start': i / 2, 'end': i / 2 + .3, 'word': ' sample'} for i in range(20)], 'duration': 10, 'coverage_end': 10}
            result = {'summary': 'Fixture summary', 'clips': [{'start': 1, 'end': 7, 'score': 80, 'hook': 'Fixture moment', 'reason': 'Explicit test data'}]}
            with patch('app.core.storage.ROOT', root), patch('app.core.pipeline.transcribe', return_value=transcript), patch('app.analysis.moments.Ollama.require'), patch('app.analysis.moments.Ollama.generate', return_value=result) as generator:
                path = run_pipeline(str(source), options, Job())
                first = Project(path)
                self.assertEqual(first.data['status'], 'complete')
                self.assertEqual(len(first.data['renders']), 1)
                self.assertTrue(Path(first.data['renders'][0]['path']).is_file())
                path2 = run_pipeline(str(source), options, Job())
                second = Project(path2)
                self.assertEqual(path, path2)
                self.assertEqual(len(second.data['renders']), 1)
                self.assertEqual(generator.call_count, 1)
                self.assertTrue((second.folder / 'transcript.json').exists())


if __name__ == '__main__':
    unittest.main()
