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
"""Export the supplied OpalPresenter.png logo to app and installer assets.

OpalBackground.jpg is the separate projection background. Projection uses it
alone; the logo belongs on app icons, splash/About artwork and installers.
"""
import argparse
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
    font = (ImageFont.truetype(str(font_path), font_size) if font_path.exists()
            else ImageFont.load_default(size=font_size))
    draw.text((size[0] // 2, size[1] * 9 // 10), 'Opal Presenter', font=font, fill='white', anchor='mm',
              stroke_width=max(1, font_size // 20), stroke_fill='#001448')
    return image


def update_packaging(logo, package):
    """Keep installer artwork clear of native text and drag-and-drop icons."""
    from PySide6 import QtCore, QtGui, QtSvg
    from PIL.ImageQt import fromqimage

    renderer = QtSvg.QSvgRenderer(str(ROOT / 'resources/images/opal-presenter-icon.svg'))
    if not renderer.isValid():
        raise ValueError('The small Opal icon is not a valid SVG')
    image = QtGui.QImage(256, 256, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    renderer.render(painter)
    painter.end()
    icon = fromqimage(image)
    small_icons = [icon.resize((size, size), Image.Resampling.LANCZOS) for size in SIZES if size <= 128]
    logo.save(package / 'macos/OpalPresenter.icns', append_images=small_icons)
    windows = package / 'windows'
    portable = windows / 'OpalPresenterPortable'
    for path in (windows / 'OpalPresenter.ico', windows / 'service_file.ico',
                 portable / 'App/Appinfo/appicon.ico', portable / 'Other/Help/Images/Favicon.ico'):
        logo.resize((256, 256), Image.Resampling.LANCZOS).save(
            path, sizes=[(size, size) for size in SIZES if size <= 256], append_images=small_icons)
    for size in (16, 32):
        icon.resize((size, size), Image.Resampling.LANCZOS).save(portable / f'App/Appinfo/appicon_{size}.png')
    icon.save(windows / 'service_file.png')
    (portable / 'Other/Help/Images/OpalPresenterIcon.svg').write_bytes(
        (ROOT / 'resources/images/opal-presenter-icon.svg').read_bytes())

    background = Image.open(ROOT / 'branding/OpalBackground.jpg').convert('RGB')
    dmg = ImageOps.fit(background, (530, 360), method=Image.Resampling.LANCZOS)
    dmg.save(package / 'macos/OpalPresenter-Background.tiff')

    main = Image.new('RGB', (493, 312), 'white')
    main.paste(ImageOps.fit(background, (164, 312), method=Image.Resampling.LANCZOS), (0, 0))
    mark = logo.resize((128, 128), Image.Resampling.LANCZOS)
    main.paste(mark, (18, 80), mark)
    banner = Image.new('RGB', (493, 58), 'white')
    mark = icon.resize((44, 44), Image.Resampling.LANCZOS)
    banner.paste(mark, (439, 7), mark)
    for name, artwork in (('WizardMain', main), ('WizardBanner', banner)):
        for suffix in ('bmp', 'png'):
            artwork.save(windows / f'{name}.{suffix}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?', default=ROOT / 'branding/OpalPresenter.png')
    parser.add_argument('--packaging', type=Path)
    parser.add_argument('--remote', type=Path)
    args = parser.parse_args()
    source = args.source
    if not source.is_file():
        source = ROOT / 'resources/images' / source
    logo = Image.open(source).convert('RGBA').resize((1024, 1024), Image.Resampling.LANCZOS)
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
    display = ROOT / 'opal/core/display/html'
    for name in ('opal-presenter-background.png', 'opal-presenter-splash.png'):
        (display / name).write_bytes((images / name).read_bytes())
    if args.packaging:
        update_packaging(logo, args.packaging)
    if args.remote:
        logo.save(args.remote / 'src/assets/favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])
        logo.resize((256, 256), Image.Resampling.LANCZOS).save(args.remote / 'src/assets/opal-presenter.png')
        logo.resize((256, 256), Image.Resampling.LANCZOS).save(args.remote / 'src/assets/loading.png')


if __name__ == '__main__':
    main()
