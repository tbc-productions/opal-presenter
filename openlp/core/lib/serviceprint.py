"""Readable rich text for service sheets printed on white paper."""
import re

from PySide6 import QtCore, QtGui

from openlp.core.display.render import remove_unknown_tags, render_tags
from openlp.core.lib.formattingtags import FormattingTags


MIN_PRINT_CONTRAST = 4.0


def render_print_text(text, render_chords=False):
    """Expand OpenLP markup without exposing unknown or unpaired tag markers."""
    for tag in FormattingTags.get_html_tags():
        if tag.get('hidden') and tag['end tag']:
            text = re.sub(re.escape(tag['start tag']) + '.*?' + re.escape(tag['end tag']), '', text, flags=re.DOTALL)
    rendered = render_tags(text, can_render_chords=render_chords, is_printing=True)
    return re.sub(r'\{/?[a-zA-Z][\w-]*\}', '', remove_unknown_tags(rendered))


def white_contrast(color):
    """Relative luminance contrast against white using the sRGB transfer function."""
    # https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
    channels = [channel / 255 for channel in color.getRgb()[:3]]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
              for channel in channels]
    luminance = sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return 1.05 / (luminance + 0.05)


def print_color(color):
    """Keep readable colours; darken pale colours while retaining their hue."""
    alpha = color.alphaF()
    rgb = [round(channel * alpha + 255 * (1 - alpha)) for channel in color.getRgb()[:3]]
    opaque = QtGui.QColor(*rgb)
    if white_contrast(opaque) >= MIN_PRINT_CONTRAST:
        return opaque
    low, high = 0.0, 1.0
    for _ in range(24):
        scale = (low + high) / 2
        candidate = QtGui.QColor(*(int(channel * scale) for channel in rgb))
        if white_contrast(candidate) >= MIN_PRINT_CONTRAST:
            low = scale
        else:
            high = scale
    return QtGui.QColor(*(int(channel * low) for channel in rgb))


def prepare_print_document(document, html_source):
    """Resolve inherited CSS through Qt, then enforce contrast on the actual text runs."""
    # Projection colours use a WebKit property that QTextDocument does not support.
    html_source = re.sub(r'-webkit-text-fill-color\s*:', 'color:', html_source, flags=re.IGNORECASE)
    document.setHtml(html_source)
    runs = []
    block = document.begin()
    while block.isValid():
        cursor = QtGui.QTextCursor(block)
        block_format = block.blockFormat()
        block_format.setBackground(QtGui.QColor('white'))
        cursor.setBlockFormat(block_format)
        fragments = block.begin()
        while not fragments.atEnd():
            fragment = fragments.fragment()
            if fragment.isValid():
                runs.append((fragment.position(), fragment.length(), fragment.charFormat()))
            fragments += 1
        block = block.next()
    for position, length, char_format in runs:
        color = char_format.foreground().color()
        if char_format.foreground().style() == QtCore.Qt.BrushStyle.NoBrush:
            color = QtGui.QColor('black')
        char_format.setForeground(print_color(color))
        char_format.setBackground(QtGui.QColor('white'))
        cursor = QtGui.QTextCursor(document)
        cursor.setPosition(position)
        cursor.setPosition(position + length, QtGui.QTextCursor.MoveMode.KeepAnchor)
        cursor.setCharFormat(char_format)
    frames = [document.rootFrame()]
    for frame in frames:
        frame_format = frame.frameFormat()
        frame_format.setBackground(QtGui.QColor('white'))
        frame.setFrameFormat(frame_format)
        if isinstance(frame, QtGui.QTextTable):
            for row in range(frame.rows()):
                for column in range(frame.columns()):
                    cell = frame.cellAt(row, column)
                    cell_format = cell.format()
                    cell_format.setBackground(QtGui.QColor('white'))
                    cell.setFormat(cell_format)
        frames.extend(frame.childFrames())


def plain_print_text(document):
    """Retain the service sheet hierarchy when copying to unformatted text."""
    plain_document = document.clone()
    children = []
    block = plain_document.begin()
    while block.isValid():
        cursor = QtGui.QTextCursor(block)
        indented = block.blockFormat().leftMargin() >= 16 or block.textList() is not None
        frame = cursor.currentFrame()
        while frame is not None:
            indented |= frame.frameFormat().leftMargin() >= 16
            frame = frame.parentFrame()
        if indented and block.text():
            children.append((block.position(), block.text()))
        block = block.next()
    for position, text in reversed(children):
        cursor = QtGui.QTextCursor(plain_document)
        cursor.setPosition(position)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock, QtGui.QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText('  ' + text.replace('\u2028', '\u2028  '))
    cursor = QtGui.QTextCursor(plain_document)
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    return cursor.selectedText()
