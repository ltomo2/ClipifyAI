import json
import shutil
from pathlib import Path
from app.core.jobs import Job


def tool(name):
    found = shutil.which(name)
    if found:
        return found
    for p in [Path('C:/ffmpeg/bin') / (name + '.exe'), Path('C:/ffmpeg') / (name + '.exe')]:
        if p.is_file():
            return str(p)
    raise RuntimeError(f'{name} is missing. Check your existing C:\\ffmpeg installation and PATH.')


def probe(source, job=None):
    info = json.loads((job or Job()).run([tool('ffprobe'), '-v', 'error',
        '-show_format', '-show_streams', '-of', 'json', str(source)]))
    videos = [s for s in info['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if not videos:
        raise ValueError('This file has no playable video stream.')
    v = videos[0]
    duration = float(info['format'].get('duration') or v.get('duration') or 0)
    if not 0 < duration < 60 * 60 * 100:
        raise ValueError('The video duration could not be read reliably.')
    return {'duration': duration, 'width': v['width'], 'height': v['height'],
        'fps': v.get('avg_frame_rate'), 'video_codec': v['codec_name'],
        'audio': any(s['codec_type'] == 'audio' for s in info['streams']),
        'streams': info['streams']}


def extract_audio(source, target, job):
    tmp = Path(target).with_suffix('.partial.wav')
    try:
        job.run([tool('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-i', source,
            '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', tmp])
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)


def free_space(folder, required):
    Path(folder).mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(folder).free < required:
        raise RuntimeError(f'Not enough free disk space in {folder}. Need approximately {required / 1024**3:.1f} GB.')
