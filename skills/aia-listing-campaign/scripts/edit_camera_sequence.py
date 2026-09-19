#!/usr/bin/env python3
"""Footage-first independently authored film timelines; creative review remains required."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from panorama_sequence import panorama_inputs, validate_coverage
from font_text import prepare_text

FILMS = {'flagship', 'launch', 'neighborhood'}
RANGES = {'flagship': (75, 90), 'launch': (45, 60), 'neighborhood': (75, 100),
          'reel': (20, 45), 'teaser': (8, 12)}
PHOTO_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp'}

def photo_windows(shot, width, height):
    from PIL import Image
    with Image.open(shot['path']) as source:sw, sh = source.size
    motion = shot.get('motion', {})
    windows = []
    for key in ('start', 'end'):
        box = motion.get(key)
        if not isinstance(box, dict) or any(k not in box for k in ('x', 'y', 'width', 'height')):
            raise ValueError('Each original photo needs authored start/end framing windows')
        x, y, w, h = [box[k] for k in ('x', 'y', 'width', 'height')]
        if not all(finite(v) for v in (x,y,w,h)) or min(x,y)<0 or min(w,h)<=0 or x+w>sw+.01 or y+h>sh+.01:
            raise ValueError('Photo framing exceeds original source boundaries')
        if abs(w/h-width/height)>.003:raise ValueError('Photo framing must match the output aspect ratio')
        windows.append((x,y,w,h))
    if windows[0] == windows[1]:raise ValueError('Author a purposeful movement, not a static held photograph')
    return sw,sh,windows

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
        '-show_format', '-of', 'json', str(path)]))

def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def validate(c, inspect=probe):
    if os.environ.get('AIA_RUN_ID') and os.environ['AIA_RUN_ID'] != c.get('run_id'):
        raise ValueError('Runner and composition run IDs differ')
    if not c.get('run_id') or not c.get('composition_id') or c.get('kind') not in RANGES:
        raise ValueError('Fresh run, independent composition ID and supported kind required')
    if Path(c['composition_id']).name != c['composition_id'] or c['composition_id'] in ('.', '..'):
        raise ValueError('Composition ID must be a plain filename component')
    out, work = Path(c['output']).resolve(), Path(c['working']).resolve()
    if out.suffix.lower() != '.mp4' or work == out.parent or out.parent in work.parents:
        raise ValueError('MP4 output and internal working directory outside delivery required')
    if out.exists():
        raise ValueError('Output already exists; use a fresh render destination')
    w, h = c['width'], c['height']
    if not all(isinstance(v, int) and v > 0 and v % 2 == 0 for v in (w, h)):
        raise ValueError('Even positive export dimensions required')
    if c.get('fps', 30) not in (24, 25, 30, 50, 60):
        raise ValueError('Unsupported frame rate')
    if not c.get('shots'):
        raise ValueError('No source-camera coverage')
    total, intervals, photo_frames = 0, {}, {}
    for shot in c['shots']:
        path = Path(shot['path'])
        photo = path.suffix.lower() in PHOTO_SUFFIXES
        if photo and c.get('mode') not in ('basic_photo_edit', 'panorama_photo_edit'):raise ValueError('Photo editing must be explicitly requested; never silently substitute it for camera footage')
        if not photo and path.suffix.lower() not in ('.mp4', '.mov', '.m4v', '.webm', '.mkv'):
            raise ValueError('Unsupported picture source')
        if shot.get('status') != 'reviewed' or shot.get('origin') not in ('original', 'generated'):
            raise ValueError('Reviewed original or generated camera footage required')
        if shot['origin'] == 'generated' and shot.get('origin_run_id', shot.get('run_id')) != c['run_id']:
            raise ValueError('Prior generated footage prohibited in fresh run')
        if not shot.get('source_sha256') or digest(path) != shot['source_sha256']:
            raise ValueError('Source bytes do not match reviewed footage')
        if photo:
            if shot['origin']!='original':raise ValueError('Basic photo edit uses authorized originals, not prior generated images')
            if not finite(shot['seconds']) or not 1 <= shot['seconds'] <= 5:raise ValueError('Author short picture cuts between1and5seconds')
            _,_,windows=photo_windows(shot,w,h)
            used=photo_frames.setdefault(shot['source_sha256'],[])
            if windows in used or len(used)>=2:raise ValueError('Do not repeat identical photo moves or pad with one photograph')
            used.append(windows);total+=shot['seconds'];continue
        meta = inspect(path)
        video = next((s for s in meta['streams'] if s['codec_type'] == 'video'), None)
        if not video:
            raise ValueError('Missing camera video stream')
        start, seconds = shot['in'], shot['seconds']
        if not all(finite(v) for v in (start, seconds)) or start < 0 or seconds <= 0 or start + seconds > float(meta['format']['duration']) + .02:
            raise ValueError('Invalid segment or duration padding')
        if shot.get('speed', 1) != 1 or shot.get('loop'):
            raise ValueError('Speed stretching and loop padding are prohibited')
        prior = intervals.setdefault(shot['source_sha256'], [])
        if any(start < end - .01 and start + seconds > begin + .01 for begin, end in prior):
            raise ValueError('Repeated footage cannot pad the film')
        prior.append((start, start + seconds))
        crop = shot.get('crop')
        if crop:
            x, y, cw, ch = (crop[k] for k in ('x', 'y', 'width', 'height'))
            if not all(isinstance(v, int) for v in (x, y, cw, ch)) or min(x, y) < 0 or min(cw, ch) <= 0 or x + cw > video['width'] or y + ch > video['height']:
                raise ValueError('Invalid explicit source crop')
        else:
            cw, ch = video['width'], video['height']
        if abs(cw / ch - w / h) > .003:
            raise ValueError('Composition requires explicit matching crop; no implicit letterboxing')
        total += seconds
    lo, hi = RANGES[c['kind']]
    if c.get('mode')=='basic_photo_edit' and c['kind']=='flagship' and len(photo_frames)<28:
        raise ValueError('Complete basic flagship requires at least28distinct original photographs')
    validate_coverage(c, photo_frames, total)
    lo, hi = max(lo, c.get('duration_min', lo)), min(hi, c.get('duration_max', hi))
    if not lo <= total <= hi:
        raise ValueError('Actual footage duration does not fulfill film specification')
    if c['kind'] in FILMS and (not c.get('narration') or not c.get('captions')):
        raise ValueError('Full story films require narration and embedded captions')
    if not c.get('music'):
        raise ValueError('Reviewed music required')
    for role, audio in [('music', c['music']), ('narration', c.get('narration'))] + [('sfx', a) for a in c.get('sfx', [])]:
        if not audio:
            continue
        if not audio.get('rights_basis') or (role == 'music' and not audio.get('attribution')):
            raise ValueError('Document approved sound rights')
        meta = inspect(audio['path'])
        if not any(s['codec_type'] == 'audio' for s in meta['streams']):
            raise ValueError('Missing sound stream')
        duration = float(meta['format']['duration'])
        if role == 'narration' and audio.get('segments'):
            prior_source = prior_timeline = 0
            for segment in audio['segments']:
                begin, seconds, at = (segment[k] for k in ('in','seconds','at'))
                if not all(finite(v) for v in (begin,seconds,at)) or seconds <= 0 or begin < prior_source-.01 or at < prior_timeline-.01 or begin+seconds > duration+.02 or at+seconds > total+.02:
                    raise ValueError('Narration edit exceeds source/timeline or overlaps speech')
                prior_source, prior_timeline = begin+seconds, at+seconds
        if role == 'narration' and duration > total + .02:
            raise ValueError('Narration would be truncated')
        if role == 'music' and duration < audio.get('in', 0) + total - .02:
            raise ValueError('Music does not cover timeline; author a complete sound bed')
        if role == 'sfx' and (audio.get('at', 0) < 0 or audio.get('seconds', duration) > duration or audio.get('at', 0) + audio.get('seconds', duration) > total):
            raise ValueError('SFX exceeds timeline or source duration')
    for caption in c.get('captions', []):
        if not 0 <= caption['start'] < caption['end'] <= total or not caption.get('text'):
            raise ValueError('Invalid embedded caption interval')
    return total

def escape(value):
    return str(value).replace('\\', '\\\\').replace("'", "'\\''").replace(':', '\\:')

def render(c):
    c = prepare_text(c)
    duration = validate(c)
    root = Path(c['working']).resolve() / c['composition_id']
    root.mkdir(parents=True, exist_ok=True)
    out = Path(c['output']).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    clips = []
    for n, shot in enumerate(c['shots']):
        filters = []
        photo=Path(shot['path']).suffix.lower() in PHOTO_SUFFIXES
        if photo:
            sw,sh,windows=photo_windows(shot,c['width'],c['height']);frames=round(shot['seconds']*c.get('fps',30))
            filters=['setsar=1']
        elif shot.get('crop'):
            q = shot['crop']; filters.append(f"crop={q['width']}:{q['height']}:{q['x']}:{q['y']}")
        if not photo:filters += [f"scale={c['width']}:{c['height']}", 'setsar=1', f"fps={c.get('fps', 30)}"]
        for j, text in enumerate(shot.get('text', []) + c.get('brand_text', [])):
            file = root / f'text-{n}-{j}.txt'; file.write_text(text['text'])
            filters.append(f"drawtext=fontfile='{escape(c['font'])}':textfile='{escape(file)}':expansion=none:fontcolor=white:fontsize={text['size']}:x={text['x']}:y={text['y']}:borderw=2:bordercolor=black@0.55:shadowcolor=black@0.6:shadowx=2:shadowy=2")
        clip = root / f'clip-{n:03}.mp4'
        command=['ffmpeg','-v','error','-y']
        if photo:command+=['-f','rawvideo','-pix_fmt','rgb24','-s',f"{c['width']}x{c['height']}",'-framerate',str(c.get('fps',30)),'-i','pipe:0']
        else:command+=['-ss',str(shot['in']),'-i',shot['path']]
        command+=['-t',str(shot['seconds']),'-an','-vf',','.join(filters),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(clip)]
        if photo:
            # FFmpeg zoompan derives BOTH crop dimensions from input aspect, which
            # stretches landscape stills into portrait. Rasterize the authored
            # source-pixel rectangle explicitly so its width AND height are honored.
            from PIL import Image
            with Image.open(shot['path']) as original:
                picture=original.convert('RGB')
                with (root/f'clip-{n:03}-encode.log').open('wb') as log:
                    process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
                    try:
                        for frame in range(frames):
                            progress=frame/max(1,frames-1);eased=progress*progress*(3-2*progress)
                            x,y,cw,ch=[a+(b-a)*eased for a,b in zip(windows[0],windows[1])]
                            raster=picture.transform((c['width'],c['height']),Image.Transform.EXTENT,(x,y,x+cw,y+ch),resample=Image.Resampling.BICUBIC)
                            process.stdin.write(raster.tobytes())
                    finally:
                        process.stdin.close();code=process.wait()
                    if code:raise subprocess.CalledProcessError(code,command)
        else:subprocess.run(command,check=True)
        clips.append(clip)
    concat = root / 'concat.txt'
    concat.write_text('\n'.join("file '" + str(p).replace("'", "'\\''") + "'" for p in clips))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat)]
    filters, audio_labels = [], []
    sounds = [('music', c['music'])] + ([('narration', c['narration'])] if c.get('narration') else []) + [('sfx', s) for s in c.get('sfx', [])]
    for idx, (role, sound) in enumerate(sounds, 1):
        cmd += ['-i', sound['path']]
        if role == 'narration' and sound.get('segments'):
            segments=sound['segments'];labels=''.join(f'[voice{idx}_{n}]' for n in range(len(segments)))
            filters.append(f'[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-18:TP=-2:LRA=9,asplit={len(segments)}'+labels)
            parts=[]
            for n,segment in enumerate(segments):
                label=f'paced{idx}_{n}';parts.append(f'[{label}]')
                filters.append(f"[voice{idx}_{n}]atrim=start={segment['in']}:duration={segment['seconds']},asetpts=PTS-STARTPTS,adelay={round(segment['at']*1000)}:all=1[{label}]")
            label=f'a{idx}';filters.append(''.join(parts)+f'amix=inputs={len(parts)}:normalize=0:duration=longest[{label}]');audio_labels.append(f'[{label}]');continue
        start = sound.get('in', 0); seconds = sound.get('seconds', duration)
        level = -28 if role == 'music' and c.get('narration') else -18
        chain = f'[{idx}:a]atrim=start={start}:duration={seconds},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo'
        if role == 'sfx':
            chain += f",volume={sound.get('gain', .3)},adelay={round(sound.get('at', 0)*1000)}:all=1"
        else:
            chain += f',loudnorm=I={level}:TP=-2:LRA=9'
        if role == 'music':
            chain += f',afade=t=in:d=0.3,afade=t=out:st={max(0, duration-1.5)}:d=1.5'
        label = f'a{idx}'; filters.append(chain + f'[{label}]'); audio_labels.append(f'[{label}]')
    filters.append(''.join(audio_labels) + f'amix=inputs={len(sounds)}:normalize=0:duration=longest,alimiter=limit=0.89:level=false,atrim=duration={duration}[mix]')
    video_filters = []
    for i, cap in enumerate(c.get('captions', [])):
        file = root / f'caption-{i:03}.txt'; file.write_text(cap['text'])
        video_filters.append(f"drawtext=fontfile='{escape(c['font'])}':textfile='{escape(file)}':expansion=none:fontcolor=white:fontsize={c.get('caption_size', round(c['width']*.037))}:x=(w-text_w)/2:y=h*0.82:box=1:boxcolor=black@0.55:boxborderw=10:enable='between(t,{cap['start']},{cap['end']})'")
    if video_filters:
        filters.append('[0:v]' + ','.join(video_filters) + '[video]')
    temp = root / 'master.mp4'
    cmd += ['-filter_complex', ';'.join(filters), '-map', '[video]' if video_filters else '0:v', '-map', '[mix]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-t', str(duration), '-metadata', 'comment='+c['music']['attribution'], '-movflags', '+faststart', str(temp)]
    subprocess.run(cmd, check=True)
    import shutil
    shutil.copyfile(temp, out)
    declared = {str(Path(p['path']).resolve()): p for p in c.get('input_provenance', [])}
    declared.update({str(Path(p['path']).resolve()): p for p in json.loads(os.environ.get('AIA_TASK_INPUTS_JSON', '[]'))})
    consumed = {}
    external = c['shots'] + [sound for _, sound in sounds]
    for shot in c['shots']:
        if shot.get('panorama_config'):
            parent, original, _ = panorama_inputs(shot, c['run_id'])
            external.extend([{'path': str(parent)}, {'path': str(original)}])
    if c.get('font') and (c.get('captions') or c.get('brand_text') or any(s.get('text') for s in c['shots'])):
        external.append({'path': c['font']})
    if c.get('_config_path'):
        external.append({'path': c['_config_path']})
    for entry in external:
        path = str(Path(entry['path']).resolve()); identity = {**declared.get(path, {}), **entry}
        record = {'path': path, 'sha256': digest(path)}
        for field in ('origin', 'source_id', 'producer_task'):
            if identity.get(field): record[field] = identity[field]
        if identity.get('origin_run_id', identity.get('run_id')):
            record['run_id'] = identity.get('origin_run_id', identity.get('run_id'))
        consumed[path] = record
    receipt = {'run_id': c['run_id'], 'composition_id': c['composition_id'], 'mode': c.get('mode','camera_footage'), 'output': str(out), 'sha256': digest(out), 'duration': duration, 'consumed': list(consumed.values()), 'consumed_sources': [{'path': s['path'], 'sha256': s['source_sha256'], 'origin': s['origin'], 'origin_run_id': s.get('origin_run_id', s.get('run_id')), 'in': s.get('in',0), 'seconds': s['seconds']} for s in c['shots']], 'status': 'rendered_awaiting_full_playback', 'full_sound': False, 'full_muted': False}
    (root / 'render-receipt.json').write_text(json.dumps(receipt, indent=2))
    if os.environ.get('AIA_PRODUCTION_RECEIPT'):
        destination = Path(os.environ['AIA_PRODUCTION_RECEIPT']).resolve()
        if destination == out or destination.parent == out.parent or out.parent in destination.parents:
            raise ValueError('Production receipt must remain outside media delivery')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(receipt, indent=2))
    return out

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('config'); args = parser.parse_args()
    config = json.loads(Path(args.config).read_text()); config['_config_path'] = str(Path(args.config).resolve())
    print(render(config))
