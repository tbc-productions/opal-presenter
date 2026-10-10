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
"""
Update OpenLP logo raster assets from a supplied source image.

This script regenerates:
- openlp-logo-16x16.png
- openlp-logo-32x32.png
- openlp-logo-48x48.png
- openlp-logo-64x64.png
- openlp-logo-128x128.png
- openlp-logo-256x256.png
- openlp-splash-screen.png
- OpenLP.ico
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


SIZES = (16, 32, 48, 64, 128, 256)
SPLASH_TARGETS = {
    'openlp-splash-screen.png': 1110,
}


def run_command(command: list[str]) -> None:
    """Run one external command."""
    print(' '.join(command))
    subprocess.run(command, check=True)


def build_pngs(source_image: Path, images_dir: Path) -> None:
    """Render all required PNG sizes from the source image using Inkscape."""
    inkscape = shutil.which('inkscape')
    if not inkscape:
        raise RuntimeError('inkscape was not found in PATH. Please install Inkscape first.')

    for size in SIZES:
        png_path = images_dir / f'openlp-logo-{size}x{size}.png'
        command = [
            inkscape,
            str(source_image),
            '--export-type=png',
            f'--export-filename={png_path}',
            f'--export-width={size}',
            f'--export-height={size}',
        ]
        run_command(command)


def build_splash_images(source_image: Path, images_dir: Path) -> None:
    """Render splash-screen assets from the source image using Inkscape."""
    inkscape = shutil.which('inkscape')
    if not inkscape:
        raise RuntimeError('inkscape was not found in PATH. Please install Inkscape first.')

    for file_name, size in SPLASH_TARGETS.items():
        splash_path = images_dir / file_name
        command = [
            inkscape,
            str(source_image),
            '--export-type=png',
            f'--export-filename={splash_path}',
            f'--export-width={size}',
            f'--export-height={size}',
        ]
        run_command(command)


def build_ico(images_dir: Path) -> None:
    """Create OpenLP.ico from generated PNGs using icotool."""
    icotool = shutil.which('icotool')
    ico_path = images_dir / 'OpenLP.ico'
    png_paths = [str(images_dir / f'openlp-logo-{size}x{size}.png') for size in SIZES]
    if icotool:
        command = [icotool, '-c', '-o', str(ico_path), *png_paths]
        run_command(command)
        return

    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            'icotool was not found in PATH and Pillow is not installed. '
            'Install icoutils or Pillow to create OpenLP.ico.'
        ) from error

    largest_png = images_dir / 'openlp-logo-256x256.png'
    with Image.open(largest_png) as image:
        image.save(
            ico_path,
            format='ICO',
            sizes=[(size, size) for size in SIZES],
        )


def parse_source_image_name(argv: list[str]) -> str:
    """Parse the single required source image argument."""
    if len(argv) != 2:
        script_name = Path(argv[0]).name if argv else 'update_openlp_logo.py'
        print(f'Usage: {script_name} <source-image-name>', file=sys.stderr)
        raise SystemExit(2)
    return argv[1]


def main() -> int:
    """Script entry point."""
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    images_dir = (repo_root / 'resources' / 'images').resolve()
    source_image_name = parse_source_image_name(sys.argv)
    source_image = (images_dir / source_image_name).resolve()

    if not source_image.is_file():
        print(f'ERROR: source image does not exist: {source_image}', file=sys.stderr)
        return 1
    if not images_dir.is_dir():
        print(f'ERROR: images directory does not exist: {images_dir}', file=sys.stderr)
        return 1

    try:
        build_pngs(source_image=source_image, images_dir=images_dir)
        build_splash_images(source_image=source_image, images_dir=images_dir)
        build_ico(images_dir=images_dir)
    except RuntimeError as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(f'ERROR: command failed with exit code {error.returncode}', file=sys.stderr)
        return error.returncode or 1

    print('Logo and splash assets successfully updated.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
