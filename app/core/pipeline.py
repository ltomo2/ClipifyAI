import hashlib
import json
import logging
from app.core.storage import Project, atomic_json, read_json
from app.core.jobs import Cancelled
from app.services.media import probe, extract_audio, free_space
from app.services.transcription import transcribe
from app.analysis.moments import analyse
from app.analysis.visual import enrich
from app.rendering.export import render


def run_pipeline(source, options, job):
    if not 5 <= options['min_duration'] <= options['max_duration'] <= 180:
        raise ValueError('Choose clip lengths between 5 and 180 seconds, with minimum no greater than maximum.')
    p = Project.create(source, options)
    p.verify_source()
    p.data['settings'] = dict(options)
    try:
        p.data.update(status='processing', error='')
        p.save()
        job.report('Reading video', 1, 'Checking source and saved work…')
        media = probe(source, job)
        if media['duration'] < options['min_duration']:
            raise RuntimeError('This video is shorter than the minimum clip length. Lower the minimum duration on Dashboard.')
        if not media['audio']:
            raise RuntimeError('This video has no audio track. The current speech-based analysis needs audio.')
        p.data['media'] = media
        p.save()
        free_space(p.folder, media['duration'] * 32000 + 200 * 1024**2)
        if not (p.folder / 'audio.wav').exists():
            job.report('Extracting audio', 5, 'Extracting the entire video audio, without changing the source.')
            extract_audio(source, p.folder / 'audio.wav', job)
        p.data['stage'] = 'Transcribing'
        p.save()
        transcript = transcribe(p, options, job)
        atomic_json(p.folder / 'transcript.json', transcript)
        p.data['stage'] = 'Analysing content'
        p.save()
        scenes = None
        if options.get('use_scenes'):
            from app.analysis.scenes import detect
            scenes = detect(p, job)
        candidates = analyse(p, transcript, options, job)
        if scenes:
            for candidate in candidates:
                candidate['scene_changes'] = sum(candidate['start'] < scene['start'] < candidate['end'] for scene in scenes['scenes'])
        # Save text results before optional visual enrichment, so missing vision models lose no analysis.
        p.data['candidates'] = candidates
        p.save()
        candidates = enrich(p, candidates, options, job)
        p.data['candidates'] = candidates
        p.data['stage'] = 'Creating clips'
        p.save()
        for index, c in enumerate(candidates[:options['count']]):
            job.check()
            signature = render_signature(c, options)
            old = [r for r in p.data['renders'] if r.get('signature') == signature]
            from pathlib import Path
            if any(Path(r['path']).is_file() for r in old):
                continue
            job.report('Creating clips', 78, f'Clip {index + 1}/{min(options["count"], len(candidates))}: {c["hook"]}')
            result = render(p, c, transcript, options, job)
            result['signature'] = signature
            p.data['renders'].append(result)
            p.save()
        p.data.update(status='complete', stage='Complete')
        p.save()
        job.report('Complete', 100, f'{len(p.data["renders"])} finished exports saved. Scores estimate potential; they do not guarantee virality.')
        return str(p.folder)
    except Exception as e:
        p.data.update(status='cancelled' if isinstance(e, Cancelled) else 'error', error=str(e))
        p.save()
        logging.exception('Project processing stopped: %s', p.folder)
        raise


def render_signature(candidate, options):
    keys = ['layout', 'font_size', 'highlight', 'caption_y', 'exports', 'encoder']
    return hashlib.sha256(json.dumps({'start': candidate['start'], 'end': candidate['end'], **{k: options[k] for k in keys}}, sort_keys=True).encode()).hexdigest()


def rerender(folder, candidate, options, job):
    p = Project(folder)
    p.verify_source()
    transcript = read_json(p.folder / 'transcript.json')
    result = render(p, candidate, transcript, options, job)
    result['signature'] = render_signature(candidate, options)
    p.data['renders'].append(result)
    p.save()
    job.report('Complete', 100, 'New export saved; previous versions preserved.')
    return str(p.folder)
