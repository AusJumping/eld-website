"""One-off image optimiser: copies images out of the old WordPress backup,
resizes them for the web and writes assets/img/manifest.json (used by build.py
for width/height attributes).

Usage:  python3 tools/optimize_images.py "<path to old backup folder>"
Needs Pillow (pip install pillow). Only required when adding new photos.
"""
import json
import os
import sys

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'assets', 'img')
os.makedirs(OUT, exist_ok=True)

backup = sys.argv[1]
manifest_path = os.path.join(OUT, 'manifest.json')
manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}

for line in open(os.path.join(HERE, 'images.tsv')):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    name, src = line.split('\t')
    src_path = os.path.join(backup, src)
    if not os.path.exists(src_path):
        print('MISSING', src)
        continue
    im = Image.open(src_path)
    im = ImageOps.exif_transpose(im)
    is_logo = name.startswith(('client-', 'logo-', 'eld-logo'))
    if is_logo:
        im = im.convert('RGBA')
        im.thumbnail((900 if name == 'eld-logo' else 420, 420 if name != 'eld-logo' else 900))
        fn = name + '.png'
        im.save(os.path.join(OUT, fn), optimize=True)
        manifest[name] = {'file': fn, 'w': im.width, 'h': im.height}
        continue
    im = im.convert('RGB')
    big = im.copy()
    big.thumbnail((1600, 1600))
    fn = name + '.jpg'
    big.save(os.path.join(OUT, fn), quality=80, optimize=True, progressive=True)
    entry = {'file': fn, 'w': big.width, 'h': big.height}
    if im.width > 900:
        small = im.copy()
        small.thumbnail((800, 800))
        small.save(os.path.join(OUT, name + '-800.jpg'), quality=78, optimize=True, progressive=True)
        entry['thumb'] = name + '-800.jpg'
        entry['tw'] = small.width
    manifest[name] = entry

json.dump(manifest, open(manifest_path, 'w'), indent=1, sort_keys=True)
print('images:', len(manifest))
