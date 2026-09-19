#!/usr/bin/env python3
"""Private original-panorama intake sheet; source IDs are not room guesses."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from production_inputs import Inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inventory')
    parser.add_argument('output')
    args = parser.parse_args()
    inputs = Inputs()
    inventory = Path(args.inventory).resolve()
    spec = json.loads(inputs.read(inventory))
    if spec.get('run_id') != inputs.run_id:
        raise ValueError('Matching active run ID required')
    items = spec['images']
    output = Path(args.output).resolve()
    root = Path(spec['root']).resolve()
    if not output.is_relative_to(root / 'working') or output.suffix.lower() != '.png' or output.exists():
        raise ValueError('Fresh private PNG contact sheet required')
    columns, tile_width, tile_height, label_height = 3, 512, 256, 46
    image = Image.new('RGB', (columns * tile_width, math.ceil(len(items) / columns) * (tile_height + label_height)), '#171717')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=17)
    for n, item in enumerate(items):
        source = Path(item['path']).resolve()
        data = inputs.read(source)
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Panorama source changed')
        with Image.open(io.BytesIO(data)) as panorama:
            panorama.load()
            if panorama.width != 2 * panorama.height:
                raise ValueError('Original image is not a full 2:1 panorama')
            tile = panorama.convert('RGB').resize((tile_width, tile_height), Image.Resampling.LANCZOS)
            dimensions = f'{panorama.width} x {panorama.height}'
        x, y = n % columns * tile_width, n // columns * (tile_height + label_height)
        image.paste(tile, (x, y))
        draw.text((x + 10, y + tile_height + 4), str(item['id']) + ' | ' + dimensions, fill='white', font=font)
        draw.text((x + 10, y + tile_height + 24), 'Pending room identification', fill='#CCCCCC', font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    inputs.finish()
    print(f'Inspected {len(items)} original panoramas; room identification remains pending: {output}')


if __name__ == '__main__':
    main()
