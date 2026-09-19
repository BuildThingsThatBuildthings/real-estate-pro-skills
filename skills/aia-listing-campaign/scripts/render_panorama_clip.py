#!/usr/bin/env python3
"""Author a rotating perspective viewport within an original 360 photograph.

This never translates the camera or reconstructs geometry. All commands and
intermediate media stay private; invoke through the AIA workflow runner.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import tempfile
from PIL import Image
from production_inputs import Inputs


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(config, image_size, run_id):
    c = config
    root = Path(c['root']).resolve()
    if c.get('run_id') != run_id or not run_id:
        raise ValueError('Matching active run ID required')
    source = (root / c['source']).resolve()
    if c.get('projection') != 'equirectangular' or c.get('geometry') != list(image_size):
        raise ValueError('Declare the actual equirectangular source dimensions')
    if image_size[0] != 2 * image_size[1]:
        raise ValueError('A complete mono 2:1 equirectangular panorama is required')
    if not c.get('room_identity') or not c.get('source_identity'):
        raise ValueError('Observed room and original source identities are required')
    if c.get('rights') not in ('authorized', 'licensed', 'original') or not c.get('rights_basis'):
        raise ValueError('Original panorama reuse authority is required')
    if c['rights'] == 'licensed' and not c.get('license_evidence'):
        raise ValueError('Licensed panorama needs license evidence')
    if not c.get('source_sha256') or len(c['source_sha256']) != 64:
        raise ValueError('Exact original panorama SHA-256 required')
    width, height = c['width'], c['height']
    if not all(isinstance(v, int) and not isinstance(v, bool) and 16 <= v <= 3840 and v % 2 == 0 for v in (width, height)):
        raise ValueError('Even viewport dimensions from 16 to 3840 required')
    if c['fps'] not in (24, 25, 30, 50, 60) or not number(c['seconds']) or not 0.1 <= c['seconds'] <= 30:
        raise ValueError('Supported frame rate and finite clip duration required')
    for endpoint in ('start', 'end'):
        view = c[endpoint]
        if not all(number(view.get(k)) for k in ('yaw', 'pitch', 'h_fov', 'v_fov')):
            raise ValueError('Author yaw, pitch and both fields of view at each endpoint')
        if not -180 <= view['yaw'] <= 180 or not -85 <= view['pitch'] <= 85:
            raise ValueError('Yaw or pitch exceeds supported authored range')
        if not all(10 <= view[k] <= 110 for k in ('h_fov', 'v_fov')):
            raise ValueError('Use restrained perspective fields of view from 10 to 110 degrees')
        aspect = math.tan(math.radians(view['h_fov'] / 2)) / math.tan(math.radians(view['v_fov'] / 2))
        if abs(aspect / (width / height) - 1) > 0.005:
            raise ValueError('Horizontal and vertical fields of view must preserve square-pixel geometry')
    if c['start'] == c['end']:
        raise ValueError('Author a purposeful viewport movement')
    output = (root / c['output']).resolve()
    working = (root / c['working']).resolve()
    if not output.is_relative_to(root / 'working') or output.suffix.lower() != '.mp4':
        raise ValueError('Intermediate panorama clips must be MP4 in private working storage')
    if not working.is_relative_to(root / 'working') or working == root / 'working':
        raise ValueError('Use a dedicated private working subdirectory')
    if output.exists() or output == source or (working.exists() and not working.is_dir()):
        raise ValueError('Fresh output and private working directory required')
    return root, source, output, working


def view_at(c, frame, frames):
    t = frame / max(1, frames - 1)
    eased = t * t * t * (t * (t * 6 - 15) + 10)
    start, end = c['start'], c['end']
    delta = (end['yaw'] - start['yaw'] + 180) % 360 - 180
    yaw = (start['yaw'] + delta * eased + 180) % 360 - 180
    pitch = start['pitch'] + (end['pitch'] - start['pitch']) * eased
    # Interpolate one field of view, then derive the other to avoid changing
    # the image's aspect ratio while zooming.
    hfov = start['h_fov'] + (end['h_fov'] - start['h_fov']) * eased
    vfov = math.degrees(2 * math.atan(math.tan(math.radians(hfov / 2)) * c['height'] / c['width']))
    return {'yaw': yaw, 'pitch': pitch, 'h_fov': hfov, 'v_fov': vfov}


def command_text(c, frames):
    previous = None
    lines = []
    for frame in range(frames):
        view = view_at(c, frame, frames)
        commands = [f'v360@view {key} {value:.9f}' for key, value in view.items()
                    if previous is None or abs(value - previous[key]) > 1e-10]
        if commands:
            lines.append(f'{frame / c["fps"]:.9f} ' + ', '.join(commands) + ';')
        previous = view
    return '\n'.join(lines) + '\n'


def render(c, inputs):
    source = (Path(c['root']).resolve() / c['source']).resolve()
    data = inputs.read(source)
    if hashlib.sha256(data).hexdigest() != c['source_sha256']:
        raise ValueError('Original panorama bytes changed')
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        geometry = image.size
    root, source, output, working = validate(c, geometry, inputs.run_id)
    working.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix='attempt-', dir=working))
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = max(2, round(c['seconds'] * c['fps']))
    (working / 'viewport-commands.txt').write_text(command_text(c, frames))
    view = view_at(c, 0, frames)
    viewport = ':'.join(f'{k}={v:.9f}' for k, v in view.items())
    filters = (f"loop=loop=-1:size=1:start=0,settb=expr=1/{c['fps']},setpts=N,sendcmd=f=viewport-commands.txt,v360@view=input=equirect:output=flat:"
               f"w={c['width']}:h={c['height']}:interp=cubic:reset_rot=1:{viewport},setsar=1,format=yuv420p")
    partial = output.with_name(output.stem + '.partial.mp4')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
               '-i', str(source),
               '-filter_threads', '1', '-vf', filters, '-frames:v', str(frames),
               '-an', '-r', str(c['fps']), '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '2',
               '-movflags', '+faststart', str(partial)]
    subprocess.run(command, cwd=working, check=True, timeout=600)
    if hashlib.sha256(source.read_bytes()).hexdigest() != c['source_sha256']:
        raise ValueError('Original panorama changed during render')
    partial.replace(output)
    inputs.finish()
    print(f'Rendered original panorama viewport: {c["room_identity"]} -> {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    args = parser.parse_args()
    inputs = Inputs()
    config = json.loads(inputs.read(Path(args.config).resolve()))
    render(config, inputs)
