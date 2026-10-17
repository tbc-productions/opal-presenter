"""Projection and installer artwork keep their intended branding."""
from io import BytesIO

from PIL import Image, ImageOps
from PySide6 import QtCore

from scripts.update_opal_presenter_logo import ROOT, update_packaging


def test_projection_artwork_is_plain_wallpaper():
    """Both display copies and the compiled Qt resource must contain no logo."""
    wallpaper = Image.open(ROOT / 'branding/OpalBackground.jpg').convert('RGB')
    expected = wallpaper.resize((1920, 1080), Image.Resampling.LANCZOS)
    resource = QtCore.QFile(':/graphics/opal-presenter-background.png')
    assert resource.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    copies = [bytes(resource.readAll())]
    resource.close()
    copies.extend((ROOT / directory / 'opal-presenter-background.png').read_bytes()
                  for directory in ('resources/images', 'opal/core/display/html'))
    for data in copies:
        with Image.open(BytesIO(data)) as artwork:
            assert artwork.size == expected.size
            assert artwork.convert('RGB').tobytes() == expected.tobytes()


def test_packaging_branding(tmp_path):
    portable = tmp_path / 'windows/OpalPresenterPortable'
    (tmp_path / 'macos').mkdir()
    (portable / 'App/Appinfo').mkdir(parents=True)
    help_images = portable / 'Other/Help/Images'
    help_images.mkdir(parents=True)
    donation = help_images / 'Donation_Button.png'
    donation.write_bytes(b'Unrelated portable artwork')

    update_packaging(Image.new('RGBA', (1024, 1024), 'red'), tmp_path)

    assert donation.read_bytes() == b'Unrelated portable artwork'
    with Image.open(tmp_path / 'macos/OpalPresenter-Background.tiff') as artwork:
        wallpaper = Image.open(ROOT / 'branding/OpalBackground.jpg').convert('RGB')
        expected = ImageOps.fit(wallpaper, (530, 360), method=Image.Resampling.LANCZOS)
        assert artwork.tobytes() == expected.tobytes()
    with Image.open(tmp_path / 'windows/WizardMain.bmp') as artwork:
        assert artwork.size == (493, 312)
        assert artwork.crop((164, 0, 493, 312)).getextrema() == ((255, 255),) * 3
    with Image.open(tmp_path / 'windows/WizardBanner.bmp') as artwork:
        assert artwork.size == (493, 58)
        assert artwork.crop((0, 0, 439, 58)).getextrema() == ((255, 255),) * 3
    with Image.open(tmp_path / 'windows/OpalPresenter.ico') as icon:
        assert icon.ico.sizes() == {(size, size) for size in (16, 32, 48, 64, 128, 256)}
        colours = icon.ico.getimage((32, 32)).getcolors(1024)
        assert max((count, pixel) for count, pixel in colours if pixel[3] == 255)[1] == (77, 121, 185, 255)
        assert icon.ico.getimage((256, 256)).getpixel((128, 128)) == (255, 0, 0, 255)
    with Image.open(tmp_path / 'macos/OpalPresenter.icns') as icon:
        small = icon.icns.getimage((16, 16, 2))
        colours = small.getcolors(1024)
        assert max((count, pixel) for count, pixel in colours if pixel[3] == 255)[1] == (77, 121, 185, 255)
