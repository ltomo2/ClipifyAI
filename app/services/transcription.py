"""Chunked, resumable transcription. Existing weights only; never auto-download."""
import gc
import math
from pathlib import Path
from app.core.storage import atomic_json, read_json
from app.services.media import tool


def _transcribe_impl(project, options, job):
    folder = project.folder / 'speech'
    folder.mkdir(exist_ok=True)
    duration = project.data['media']['duration']
    engine = options['transcriber']
    language = options['language'].strip() or None
    key = {'engine': engine, 'model': options['whisper_model'] if engine == 'whisper' else options['faster_model_path'], 'language': language, 'version': 1}
    config = folder / 'config.json'
    # Different settings use a new cache directory, preserving older results.
    import hashlib, json
    folder = folder / hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:12]
    folder.mkdir(exist_ok=True)
    atomic_json(folder / 'config.json', key)
    chunks = math.ceil(duration / 300)
    if all((folder / f'{i:05}.json').exists() for i in range(chunks)):
        return combine(folder, chunks, duration)
    model = None
    device = 'cpu'
    try:
        if engine == 'whisper':
            import torch
            import whisper
            name = options['whisper_model']
            if name.endswith('.en') and language not in (None, 'en'):
                raise ValueError('tiny.en supports English only. Select an existing multilingual Whisper model for other languages.')
            cache = Path.home() / '.cache' / 'whisper' / f'{name}.pt'
            if not cache.is_file():
                raise RuntimeError(f'Existing Whisper weights not found at {cache}. No download was started.')
            device = 'cuda' if options['device'] != 'cpu' and torch.cuda.is_available() else 'cpu'
            try:
                model = whisper.load_model(str(cache), device=device)
            except RuntimeError:
                if device == 'cpu':
                    raise
                device = 'cpu'
                torch.cuda.empty_cache()
                model = whisper.load_model(str(cache), device=device)
        else:
            from faster_whisper import WhisperModel
            path = Path(options['faster_model_path'])
            if not path.is_dir() or not (path / 'model.bin').exists():
                raise RuntimeError('Choose an existing local faster-whisper model directory. OpenAI .pt weights are not CTranslate2 models.')
            # CPU/int8 is intentionally the conservative baseline; Torch CUDA is unrelated.
            model = WhisperModel(str(path), device='cpu', compute_type='int8', local_files_only=True)
        for i in range(chunks):
            job.check()
            cached = folder / f'{i:05}.json'
            if cached.exists():
                continue
            left = max(0, i * 300 - 2)
            right = min(duration, (i + 1) * 300 + 2)
            wav = folder / 'current.wav'
            job.report('Transcribing', int(10 + 40 * i / chunks), f'Full video: section {i + 1} of {chunks} ({device})')
            try:
                job.run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', str(left), '-i', project.folder / 'audio.wav',
                    '-t', str(right - left), '-c:a', 'pcm_s16le', wav])
                if engine == 'whisper':
                    try:
                        result = model.transcribe(str(wav), language=language, word_timestamps=True,
                            fp16=device == 'cuda', verbose=None)
                    except RuntimeError:
                        if device == 'cpu':
                            raise
                        job.report('Transcribing', 15, 'GPU transcription failed; retrying this section on CPU.')
                        model = model.cpu()
                        torch.cuda.empty_cache()
                        device = 'cpu'
                        result = model.transcribe(str(wav), language=language, word_timestamps=True, fp16=False, verbose=None)
                    segments = result['segments']
                else:
                    output, _ = model.transcribe(str(wav), language=language, word_timestamps=True, vad_filter=True)
                    segments = [{'start': s.start, 'end': s.end, 'text': s.text,
                        'words': [{'start': w.start, 'end': w.end, 'word': w.word} for w in (s.words or [])]} for s in output]
                words = []
                for s in segments:
                    for w in s.get('words', []):
                        a, b = float(w['start']) + left, float(w['end']) + left
                        if i * 300 <= (a + b) / 2 < min(duration, (i + 1) * 300) and 0 <= a < b <= duration + .1:
                            words.append({'start': max(0, a), 'end': min(duration, b), 'word': w['word']})
                job.check()
                atomic_json(cached, {'words': words})
            finally:
                wav.unlink(missing_ok=True)
        return combine(folder, chunks, duration)
    finally:
        del model
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


def combine(folder, chunks, duration):
    words = [w for i in range(chunks) for w in read_json(folder / f'{i:05}.json')['words']]
    words.sort(key=lambda w: w['start'])
    clean = []
    for w in words:
        if clean and w['start'] < clean[-1]['end']:
            w = dict(w, start=clean[-1]['end'])
        if w['start'] < w['end']:
            clean.append(w)
    if not clean:
        raise RuntimeError('No timestamped speech was detected. Clipify will not fabricate captions or random clips.')
    return {'words': clean, 'duration': duration, 'coverage_end': duration}


def _speech_process(folder, options, stop, messages):
    from app.core.storage import Project
    from app.core.jobs import Job
    job = Job(lambda s, n, m: messages.put(('progress', s, n, m)))
    job.stop = stop
    try:
        project = Project(folder)
        result = _transcribe_impl(project, options, job)
        atomic_json(project.folder / 'transcript_pending.json', result)
        messages.put(('done',))
    except Exception as e:
        messages.put(('error', str(e)))


def transcribe(project, options, job):
    # A spawned process lets cancellation stop native model inference and release GPU RAM.
    import multiprocessing
    import queue
    import time
    from app.core.jobs import Cancelled
    context = multiprocessing.get_context('spawn')
    stop, messages = context.Event(), context.Queue()
    process = context.Process(target=_speech_process, args=(str(project.folder), options, stop, messages))
    process.start()
    completed = False
    try:
        while True:
            if job.stop.is_set():
                stop.set()
                process.join(timeout=2)
                if process.is_alive():
                    process.terminate()
                raise Cancelled('Transcription cancelled. Completed audio sections are saved.')
            try:
                item = messages.get(timeout=.15)
            except queue.Empty:
                if not process.is_alive():
                    raise RuntimeError('Transcription process stopped unexpectedly. Saved sections can be resumed.')
                continue
            if item[0] == 'progress':
                job.report(*item[1:])
            elif item[0] == 'error':
                raise RuntimeError(item[1])
            elif item[0] == 'done':
                completed = True
                return read_json(project.folder / 'transcript_pending.json')
    finally:
        stop.set()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=3)
        messages.close()
