"""PowerPoint picture corrections, with a rendered PNG and an editable JPEG XR original."""
from hashlib import sha256
import struct

from lxml import etree
from pptx.opc.package import Part
from pptx.oxml.ns import qn

from openlp.core.lib.slidedesign import normalise_filters


NAMESPACE = 'http://schemas.microsoft.com/office/drawing/2010/main'
PHOTO_REL = 'http://schemas.microsoft.com/office/2007/relationships/hdphoto'
PHOTO_EXT = '{BEBA8EAE-BF5A-486C-A8C5-ECC9F3942E4B}'
RGBA_FORMAT = bytes.fromhex('2dadc7f58d6add43a7a8a29935261ae9')
BGRA_FORMAT = bytes.fromhex('24c3dd6f034efe4bb1853d77768dc90f')


def _office_jpegxr(pixels):
    """Encode lossless JPEG XR using the BGRA output format understood by Office.

    imagecodecs writes the newer 32bppRGBA GUID. PowerPoint for Mac reads the effect
    controls but cannot use that original, silently treating the cached (already
    filtered) PNG as the source instead. Office's own originals use 32bppBGRA.
    The GUID specifies decoded pixel packing; the compressed colour/alpha streams
    are independent of RGB/BGR byte order, so no pixel re-encoding is necessary.
    Locate the PixelFormat IFD entry rather than assuming a fixed GUID offset.
    """
    import numpy
    from imagecodecs import jpegxr_encode

    data = bytearray(jpegxr_encode(numpy.asarray(pixels), level=1))
    if data[:4] != b'II\xbc\x01':
        raise ValueError('Unexpected JPEG XR container')
    directory, = struct.unpack_from('<I', data, 4)
    entries, = struct.unpack_from('<H', data, directory)
    for index in range(entries):
        tag, kind, count, offset = struct.unpack_from('<HHII', data, directory + 2 + index * 12)
        if tag == 0xbc01:
            if kind != 1 or count != 16 or data[offset:offset + 16] != RGBA_FORMAT:
                raise ValueError('Unexpected JPEG XR pixel format')
            data[offset:offset + 16] = BGRA_FORMAT
            return bytes(data)
    raise ValueError('Missing JPEG XR pixel format')


def native_filter_effects(filters, scale=1):
    """Map a complete stack to PowerPoint controls, or return no mapping for a baked fallback.

    CSS and Office use different correction curves. Keep the exact CSS-rendered PNG as
    the initial appearance; Office's curves take over when the user edits the effects.
    Never move an unsupported filter before/after a supported one just to keep a slider.
    """
    filters = normalise_filters(filters)
    if not filters or set(filters) - {'blur', 'brightness', 'contrast', 'grayscale', 'saturate'}:
        return []
    radius = filters.get('blur', 0) * scale
    if radius > 100:
        return []  # PowerPoint's artistic blur radius is limited to 100 image pixels.
    effects = []
    if radius:
        effects.append(('artisticBlur', {'radius': max(1, round(radius))}))
    if 'brightness' in filters or 'contrast' in filters:
        effects.append(('brightnessContrast', {
            'bright': round((filters.get('brightness', 100) - 100) * 1000),
            'contrast': round((filters.get('contrast', 100) - 100) * 1000)}))
    if 'grayscale' in filters or 'saturate' in filters:
        saturation = (1 - filters.get('grayscale', 0) / 100) * filters.get('saturate', 100)
        effects.append(('saturation', {'sat': round(saturation * 1000)}))
    return effects


def apply_native_filters(shape, original, effects, originals):
    """Attach Office's editable effect chain; ``shape`` already contains the rendered preview.

    imgLayer requires a JPEG XR source and an hdphoto relationship (a PNG/image
    relationship is discarded by PowerPoint). Cache originals across repeated slides.
    https://learn.microsoft.com/en-us/openspecs/office_standards/ms-odrawxml/
    f10da8b6-40f3-4527-9c3d-9f5c2e9cff45
    """
    from openlp.core.lib.imagefilters import to_pillow

    pixels = to_pillow(original)
    key = (pixels.size, sha256(pixels.tobytes()).digest())
    package = shape.part.package
    if key not in originals:
        data = _office_jpegxr(pixels)
        originals[key] = Part(package.next_partname('/ppt/media/hdphoto%d.wdp'),
                              'image/vnd.ms-photo', package, data)
    relationship = shape.part.relate_to(originals[key], PHOTO_REL)
    blip = shape._element.blipFill.blip
    extensions = blip.find(qn('a:extLst'))
    if extensions is None:
        extensions = etree.SubElement(blip, qn('a:extLst'))
    extension = etree.SubElement(extensions, qn('a:ext'), uri=PHOTO_EXT)
    photo = etree.SubElement(extension, f'{{{NAMESPACE}}}imgProps', nsmap={'a14': NAMESPACE})
    layer = etree.SubElement(photo, f'{{{NAMESPACE}}}imgLayer', {qn('r:embed'): relationship})
    for tag, attributes in effects:
        effect = etree.SubElement(layer, f'{{{NAMESPACE}}}imgEffect')
        etree.SubElement(effect, f'{{{NAMESPACE}}}{tag}', {key: str(value) for key, value in attributes.items()})
