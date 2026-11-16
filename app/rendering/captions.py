import math
import re


def ass_time(t):
    cs = round(max(0, t) * 100)
    return f'{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}'


def escape(text):
    # Remove subtitle control characters so transcript cannot inject ASS tags.
    return text.replace('\\', '').replace('{', '').replace('}', '').replace('\n', ' ').strip()


def colour(hexcolour):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', hexcolour):
        raise ValueError('Caption highlight must be a colour such as #B58AFF.')
    return '&H' + hexcolour[5:7] + hexcolour[3:5] + hexcolour[1:3] + '&'


def write_ass(path, words, start, end, options):
    if not (math.isfinite(start) and math.isfinite(end) and start < end):
        raise ValueError('Invalid caption interval')
    font = max(28, min(110, int(options['font_size'])))
    y = max(250, min(1580, int(options['caption_y'])))
    highlight = colour(options['highlight'])
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,{font},&H00FFFFFF,&H00FFFFFF,&H00141414,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,5,100,100,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    selected = [w for w in words if w['end'] > start and w['start'] < end and escape(w['word'])]
    groups, group = [], []
    for word in selected:
        # Keep short phrases inside safe horizontal margins, with pauses as breaks.
        if group and (len(group) >= 4 or sum(len(escape(w['word'])) + 1 for w in group) + len(escape(word['word'])) > max(12, int(900 / (font * .65))) or word['start'] - group[-1]['end'] > .55):
            groups.append(group)
            group = []
        group.append(word)
        if escape(word['word']).endswith(('.', '?', '!')):
            groups.append(group)
            group = []
    if group:
        groups.append(group)
    events = []
    for group in groups:
        for i, w in enumerate(group):
            a, b = max(start, w['start']), min(end, w['end'])
            if b - a < .01:
                continue
            parts = []
            for j, other in enumerate(group):
                tag = f'{{\\c{highlight}\\fscx108\\fscy108}}' if i == j else '{\\c&HFFFFFF&\\fscx100\\fscy100}'
                parts.append(tag + escape(other['word']))
            text = f'{{\\an5\\pos(540,{y})\\fad(25,25)}}' + ' '.join(parts)
            events.append(f'Dialogue: 0,{ass_time(a - start)},{ass_time(b - start)},Caption,,0,0,0,,{text}')
    if not events:
        raise RuntimeError('No actual word timestamps overlap this clip. Captions cannot be generated.')
    path.write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')
    return len(events)
