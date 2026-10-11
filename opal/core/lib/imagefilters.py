"""Render the designer's CSS filter stack into portable image pixels for office exports."""
import math

from PIL import Image, ImageFilter, ImageOps
from PySide6 import QtGui

from opal.core.lib.slidedesign import normalise_filters


def to_pillow(image):
    image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    return Image.frombytes('RGBA', (image.width(), image.height()), bytes(image.constBits()))


def to_qimage(image):
    image = image.convert('RGBA')
    return QtGui.QImage(image.tobytes(), image.width, image.height, image.width * 4,
                        QtGui.QImage.Format.Format_RGBA8888).copy()


def _matrix(key, value):
    """CSS shorthand matrices operate on unpremultiplied sRGB, with offsets in byte units.

    https://www.w3.org/TR/filter-effects-1/#ShorthandEquivalents
    """
    amount = value / 100
    if key in ('brightness', 'contrast', 'invert'):
        slope = 1 - 2 * amount if key == 'invert' else amount
        offset = 255 * (amount if key == 'invert' else (1 - amount) / 2 if key == 'contrast' else 0)
        return tuple(value for row in range(3) for value in
                     [*(slope if row == column else 0 for column in range(3)), offset])
    if key in ('grayscale', 'saturate'):
        weights = (.2126, .7152, .0722) if key == 'grayscale' else (.213, .715, .072)
        saturation = 1 - amount if key == 'grayscale' else amount
        matrix = [[weight * (1 - saturation) + (saturation if row == column else 0)
                   for column, weight in enumerate(weights)] for row in range(3)]
    elif key == 'sepia':
        sepia = ((.393, .769, .189), (.349, .686, .168), (.272, .534, .131))
        matrix = [[coefficient * amount + (1 - amount if row == column else 0)
                   for column, coefficient in enumerate(coefficients)] for row, coefficients in enumerate(sepia)]
    else:  # hue-rotate
        cosine, sine = math.cos(math.radians(value)), math.sin(math.radians(value))
        matrix = [
            [.213 + .787 * cosine - .213 * sine, .715 - .715 * cosine - .715 * sine,
             .072 - .072 * cosine + .928 * sine],
            [.213 - .213 * cosine + .143 * sine, .715 + .285 * cosine + .140 * sine,
             .072 - .072 * cosine - .283 * sine],
            [.213 - .213 * cosine - .787 * sine, .715 - .715 * cosine + .715 * sine,
             .072 + .928 * cosine + .072 * sine]]
    return tuple(value for row in matrix for value in [*row, 0])


def apply_filters(image, filters, scale=1, *, expand=False):
    """Return filtered QImage and symmetric padding; preserve alpha and the display's filter order."""
    filters = normalise_filters(filters)
    if not filters or image.isNull():
        return image, 0
    pixels = to_pillow(image)
    padding = math.ceil(filters.get('blur', 0) * scale * 3)
    if padding:
        pixels = ImageOps.expand(pixels, padding, fill=(0, 0, 0, 0))
    for key, value in filters.items():
        if key == 'blur':
            # Blur premultiplied pixels to prevent dark fringes around translucent artwork.
            pixels = pixels.convert('RGBa').filter(ImageFilter.GaussianBlur(value * scale)).convert('RGBA')
        else:
            alpha = pixels.getchannel('A')
            pixels = pixels.convert('RGB').convert('RGB', _matrix(key, value))
            pixels.putalpha(alpha)
    if padding and not expand:
        pixels = pixels.crop((padding, padding, pixels.width - padding, pixels.height - padding))
    return to_qimage(pixels), padding if expand else 0


def add_shadow(image, properties, scale):
    """Bake a CSS drop shadow after the colour filters, keeping the original centre unchanged."""
    if not properties.get('shadow') or image.isNull():
        return image, 0
    x, y = round(properties.get('shadow_x', 4) * scale), round(properties.get('shadow_y', 4) * scale)
    blur = properties.get('shadow_blur', 4) * scale
    padding = math.ceil(3 * blur + max(abs(x), abs(y)))
    pixels = to_pillow(image)
    size = (pixels.width + padding * 2, pixels.height + padding * 2)
    mask = Image.new('L', size)
    mask.paste(pixels.getchannel('A'), (padding + x, padding + y))
    shadow = Image.new('RGBA', size, properties.get('shadow_colour', '#000000'))
    shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(blur)))
    shadow.alpha_composite(pixels, (padding, padding))
    return to_qimage(shadow), padding
