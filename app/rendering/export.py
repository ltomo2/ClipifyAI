import math
import uuid
from pathlib import Path
from app.services.media import tool, probe, free_space
from app.rendering.captions import write_ass
from app.rendering.tracking import track


def render(project, candidate, transcript, options, job):
    start, end = float(candidate['start']), float(candidate['end'])
    duration = project.data['media']['duration']
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration):
        raise ValueError('Start and end must be inside the original video, with end after start.')
    source = project.data['source']
    output = Path(options['exports']).expanduser().resolve() / project.data['id']
    free_space(output, max(250 * 1024**2, (end - start) * 2_000_000))
    token = uuid.uuid4().hex[:10]
    work = project.folder / 'render_work' / token
    work.mkdir(parents=True, exist_ok=True)
    ass = work / 'captions.ass'
    job.report('Generating captions', 80, candidate['hook'])
    events = write_ass(ass, transcript['words'], start, end, options)
    focus, layout_reason = None, 'Blurred background selected.'
    if options['layout'] == 'auto':
        focus, layout_reason = track(source, start, end, job)
    if focus:
        (work / 'crop.txt').write_text('\n'.join(f'{t:.3f} crop@focus x {x};' for t, x in focus['positions']), encoding='utf-8')
        layout = f"[0:v]setpts=PTS-STARTPTS,sendcmd=f=crop.txt,crop@focus=w={focus['width']}:h=ih:x={focus['positions'][0][1]}:y=0,scale=1080:1920,setsar=1[canvas];"
    else:
        layout = ('[0:v]setpts=PTS-STARTPTS,split=2[bg][fg];'
            '[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:2[back];'
            '[fg]scale=1080:1920:force_original_aspect_ratio=decrease[front];'
            '[back][front]overlay=(W-w)/2:(H-h)/2,setsar=1[canvas];')
    graph = layout + "[canvas]subtitles=filename=captions.ass,format=yuv420p[v];[0:a]asetpts=PTS-STARTPTS,aresample=async=1:first_pts=0[a]"
    (work / 'filter.txt').write_text(graph, encoding='utf-8')
    partial = output / f'{candidate["id"]}_{token}.partial.mp4'
    final = output / f'{candidate["id"]}_{token}.mp4'
    job.report('Rendering exports', 85, layout_reason + ' Encoding captioned MP4…')
    try:
        base = [tool('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-filter_complex_threads', '2',
            '-ss', str(start), '-i', source, '-t', str(end - start),
            '-filter_complex_script', 'filter.txt', '-map', '[v]', '-map', '[a]', '-r', '30']
        encoder = options.get('encoder', 'libx264')
        codec = ['-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '22'] if encoder == 'h264_nvenc' else ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-threads', '4']
        tail = ['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', partial]
        try:
            job.run(base + codec + tail, cwd=work)
        except RuntimeError:
            if encoder != 'h264_nvenc':
                raise
            job.report('Rendering exports', 85, 'NVENC failed; retrying with the CPU encoder.')
            job.run(base + ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-threads', '4'] + tail, cwd=work)
            encoder = 'libx264'
        info = probe(partial, job)
        if (info['width'], info['height']) != (1080, 1920) or not info['audio'] or info['video_codec'] != 'h264' or abs(info['duration'] - (end - start)) > .35:
            raise RuntimeError('The rendered video failed the size, duration, audio or codec check.')
        job.check()
        partial.replace(final)
        thumb = output / f'{candidate["id"]}_{token}.jpg'
        try:
            job.run([tool('ffmpeg'), '-v', 'error', '-y', '-ss', '0.5', '-i', final, '-frames:v', '1', '-vf', 'scale=270:480', thumb])
        except RuntimeError:
            thumb = None
        return {'id': token, 'candidate_id': candidate['id'], 'path': str(final), 'thumbnail': str(thumb) if thumb else '',
            'start': start, 'end': end, 'score': candidate['score'], 'hook': candidate['hook'], 'reason': candidate['reason'],
            'captions': 'burned-in', 'caption_events': events, 'layout': 'tracked' if focus else 'blur',
            'layout_reason': layout_reason, 'settings': dict(options, encoder=encoder), 'media': info}
    finally:
        partial.unlink(missing_ok=True)
