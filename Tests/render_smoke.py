"""Real FFmpeg integration check using synthetic picture, chirp audio and supplied word times.
This does NOT test Whisper accuracy, Ollama selection, or the user's unavailable source video.
"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from app.core.jobs import Job
from app.core.storage import ROOT, DEFAULTS, atomic_json
from app.services.media import tool, probe
from app.rendering.export import render


def main():
    job = Job(lambda s, n, m: print(s, m, flush=True))
    fixture = ROOT / 'Tests' / 'generated'
    fixture.mkdir(exist_ok=True)
    source = fixture / 'synthetic_source.mp4'
    job.run([tool('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=25:duration=35',
        '-f', 'lavfi', '-i', 'aevalsrc=0.2*sin(2*PI*(220*t+12*t*t)):s=48000:d=35',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', source])
    media = probe(source)
    project = SimpleNamespace(folder=fixture, data={'id': 'synthetic-test', 'source': str(source), 'media': media})
    words = [{'start': 2 + i * .5, 'end': 2.4 + i * .5, 'word': [' Synthetic', ' caption', ' timing', ' test.'][i % 4]} for i in range(60)]
    options = dict(DEFAULTS, exports=str(fixture / 'exports'))
    clip = {'id': 'demo', 'start': 2, 'end': 32, 'score': 0, 'hook': 'Synthetic rendering test', 'reason': 'Test fixture; no AI selection or speech recognition involved.'}
    result = render(project, clip, {'words': words}, options, job)
    job.run([tool('ffmpeg'), '-v', 'error', '-i', result['path'], '-f', 'null', '-'])
    # Extract captioned frames for inspection.
    for t in [.2, .7]:
        job.run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(t), '-i', result['path'], '-frames:v', '1', fixture / f'caption_{t}.png'])
    # Compare decoded audio at beginning and near end to the original, after the trim offset.
    import numpy as np
    errors = []
    for offset in [0.5, 28.0]:
        decoded = []
        for label, path, at in [('source', source, 2 + offset), ('output', result['path'], offset)]:
            pcm = fixture / f'{label}.pcm'
            job.run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(at), '-i', path, '-t', '0.25',
                '-vn', '-ac', '1', '-ar', '8000', '-f', 'f32le', pcm])
            decoded.append(np.fromfile(pcm, dtype=np.float32))
        a, b = decoded
        corr = np.correlate(a, b, mode='full')
        lag = (int(np.argmax(corr)) - (len(b) - 1)) / 8000
        errors.append(lag)
        assert abs(lag) < .025, f'Audio shift too large: {lag}'
    result['tested'] = {'full_decode': True, 'audio_alignment_errors_seconds': errors,
        'real_user_video': False, 'whisper': False, 'ollama': False}
    atomic_json(fixture / 'render_result.json', result)
    print(json.dumps(result['tested'], indent=2))
    print('Captioned test MP4:', result['path'])


if __name__ == '__main__':
    main()
