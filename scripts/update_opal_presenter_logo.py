#!/usr/bin/env python3
# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""Export Opal's approved raster master to app and installer assets.

The SVG is canonical. Render its filters with Inkscape or a browser before
replacing the master PNG; Qt SVG does not support its clipping correctly.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)


def poster(logo, size):
    image = ImageOps.fit(Image.open(ROOT / 'branding/OpalBackground.jpg').convert('RGB'),
                         size, method=Image.Resampling.LANCZOS)
    edge = max(16, min(size[0] * 2 // 3, size[1] * 3 // 5))
    icon = logo.resize((edge, edge), Image.Resampling.LANCZOS)
    image.paste(icon, ((size[0] - edge) // 2, max(0, (size[1] - edge) // 2 - size[1] // 12)), icon)
    draw = ImageDraw.Draw(image)
    font_path = Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')
    font_size = max(10, min(40, size[0] // 12))
    font = ImageFont.truetype(str(font_path), font_size) if font_path.exists() else ImageFont.load_default(size=font_size)
    draw.text((size[0] // 2, size[1] * 9 // 10), 'Opal Presenter', font=font, fill='white', anchor='mm',
              stroke_width=max(1, font_size // 20), stroke_fill='#001448')
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?', default=ROOT / 'branding/Opal-Presenter.svg')
    parser.add_argument('--packaging', type=Path)
    parser.add_argument('--remote', type=Path)
    args = parser.parse_args()
    source = args.source
    if not source.is_file():
        source = ROOT / 'resources/images' / source
    if source.suffix.lower() == '.svg':
        master = ROOT / 'branding/Opal-Presenter-1024.png'
        inkscape = shutil.which('inkscape')
        if inkscape:
            subprocess.run([inkscape, str(source), '--export-type=png', f'--export-filename={master}',
                            '--export-width=1024', '--export-height=1024'], check=True)
        else:
            approved = json.loads((ROOT / 'branding/raster-master.json').read_text())
            if hashlib.sha256(source.read_bytes()).hexdigest() != approved['source_sha256']:
                parser.error('The SVG has changed. Install Inkscape to regenerate its raster master.')
        source = master
    logo = Image.open(source).convert('RGBA')
    assert logo.size == (1024, 1024), 'Render the canonical SVG at 1024px first.'
    images = ROOT / 'resources/images'
    for size in SIZES:
        logo.resize((size, size), Image.Resampling.LANCZOS).save(images / f'opal-presenter-logo-{size}x{size}.png')
    logo.save(images / 'OpalPresenter.ico', sizes=[(size, size) for size in SIZES if size <= 256])
    logo.save(images / 'OpalPresenter.icns')
    logo.resize((256, 256), Image.Resampling.LANCZOS).save(images / 'opal-presenter.png')
    Image.open(ROOT / 'branding/OpalBackground.jpg').convert('RGB').resize(
        (1920, 1080), Image.Resampling.LANCZOS).save(images / 'opal-presenter-background.png')
    poster(logo, (370, 370)).save(images / 'opal-presenter-splash.png')
    poster(logo, (200, 400)).save(images / 'opal-presenter-about.png')
    display = ROOT / 'openlp/core/display/html'
    for name in ('opal-presenter-background.png', 'opal-presenter-splash.png'):
        (display / name).write_bytes((images / name).read_bytes())
    if args.packaging:
        package = args.packaging
        (package / 'macos/OpalPresenter.icns').write_bytes((images / 'OpalPresenter.icns').read_bytes())
        poster(logo, (530, 360)).save(package / 'macos/OpalPresenter-Background.tiff')
        for path in (package / 'windows').rglob('*'):
            if path.suffix.lower() not in ('.ico', '.bmp', '.png'):
                continue
            if path.suffix.lower() == '.ico':
                logo.save(path, sizes=[(size, size) for size in SIZES if size <= 256])
            else:
                size = Image.open(path).size
                image = logo.resize(size, Image.Resampling.LANCZOS) if path.name.startswith('appicon') else poster(logo, size)
                image.save(path)
    if args.remote:
        logo.save(args.remote / 'src/assets/favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])
        logo.resize((256, 256), Image.Resampling.LANCZOS).save(args.remote / 'src/assets/opal-presenter.png')


if __name__ == '__main__':
    main()
