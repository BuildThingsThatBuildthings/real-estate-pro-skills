"""Validate the exact client handoff; production metadata never belongs in Drive."""
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

MEDIA = {'.mp4', '.png', '.jpg', '.jpeg'}
DOCUMENTS = {'.pdf', '.md', '.txt'}
TECHNICAL = {'.json', '.jsonl', '.csv', '.srt', '.vtt', '.log', '.py', '.js', '.mjs', '.ts', '.tsx', '.html', '.zip', '.yaml', '.yml', '.wav', '.mp3'}


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts or any(p.startswith('.') for p in path.parts):
        raise ValueError(f'Unsafe delivery path: {value}')
    return path


def check_media(path):
    if path.suffix.lower() != '.mp4':
        from PIL import Image
        with Image.open(path) as image:
            expected = 'PNG' if path.suffix.lower() == '.png' else 'JPEG'
            if image.format != expected:
                raise ValueError('image content does not match extension')
            image.verify()
        with Image.open(path) as image:
            image.load()
        return
    with path.open('rb') as stream:
        header = stream.read(32)
    if header[4:8] != b'ftyp' or header[8:12] == b'qt  ':
        raise ValueError('not an MP4 container')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=30)
    data = json.loads(probe.stdout)
    if float(data.get('format', {}).get('duration', 0)) <= 0 or not any(s.get('codec_type') == 'video' for s in data.get('streams', [])):
        raise ValueError('MP4 has no timed video stream')
    result = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0', '-map', '0:a?', '-f', 'null', '-'], capture_output=True, text=True, timeout=300)
    if result.returncode or result.stderr.strip():
        raise ValueError('MP4 failed complete decode')


def check_document(path):
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        with path.open('rb') as stream:
            if stream.read(5) != b'%PDF-':
                raise ValueError('document content does not match PDF extension')
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted or not len(reader.pages):
            raise ValueError('PDF must have readable pages')
        for page in reader.pages:
            page.extract_text()
    else:
        content = path.read_text(encoding='utf-8')
        if not content.strip() or '\x00' in content or content.lstrip().startswith(('{', '[', '<!DOCTYPE', '<html')):
            raise ValueError('not a useful text document; technical data cannot be renamed for delivery')


def validate_delivery(root, document_folders=(), documents=()):
    """Return validated files, or refuse the entire batch before any upload."""
    root = Path(root).resolve()
    folders = [relative(p) for p in document_folders]
    media_folder = re.compile(r'\b(video|videos|image|images|graphics|covers|reels|teasers|carousels|feed|stories|neighborhood media)\b', re.I)
    if any(media_folder.search(part) for folder in folders for part in folder.parts):
        raise ValueError('Media folders cannot be designated as document folders')
    approved = {relative(p).as_posix() for p in documents}
    errors, files, seen = [], [], set()
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append(f'{name}: symlinks cannot be delivered')
            continue
        if not path.is_file():
            continue
        seen.add(name)
        suffix = path.suffix.lower()
        parts = PurePosixPath(name).parts
        if any(p.startswith('.') for p in parts) or '.partial.' in path.name.lower():
            errors.append(f'{name}: hidden or unfinished production file')
            continue
        try:
            if suffix in TECHNICAL:
                raise ValueError('technical sidecars are never client deliverables')
            if suffix in MEDIA:
                check_media(path)
            elif suffix in DOCUMENTS:
                if any(media_folder.search(part) for part in parts[:-1]):
                    raise ValueError('media folders accept only finished MP4/PNG/JPG images and video')
                if name not in approved or not any(PurePosixPath(name).is_relative_to(folder) for folder in folders):
                    raise ValueError('useful documents require both an explicit document folder and an exact --document path')
                check_document(path)
            else:
                raise ValueError('unsupported client deliverable type')
            files.append(path)
        except (ValueError, OSError, ImportError, subprocess.SubprocessError) as error:
            errors.append(f'{name}: {error}')
        except Exception as error:
            errors.append(f'{name}: unreadable media or document ({type(error).__name__})')
    errors.extend(f'{name}: identified document is missing' for name in sorted(approved - seen))
    if not files and not errors:
        errors.append('no finished deliverables')
    if errors:
        raise ValueError('Delivery refused:\n' + '\n'.join(errors))
    return files
