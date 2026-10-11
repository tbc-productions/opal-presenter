"""Map edits in a rendered page back to its lyrics without losing source tags."""
import html
import re
from difflib import SequenceMatcher

from opal.core.display.render import remove_chords
from opal.core.lib.formattingtags import FormattingTags


def visible_text(source, literal=False):
    """Return plain text and the source span belonging to each visible character."""
    hidden = [re.escape(tag['start tag']) + r'.*?' + re.escape(tag['end tag'])
              for tag in FormattingTags.get_html_tags() if tag.get('hidden')]
    pattern = '|'.join(hidden + [r'\{/?[^{}\n]+\}'] +
                       ([] if literal else [r'\n?\[---\]', r'<[^>]+>',
                                            r'&(?:#\d+|#x[\da-fA-F]+|\w+);', r'\[[^\]\n]+\]']) + [r'.'])
    text, spans = [], []
    for match in re.finditer(pattern, source, re.DOTALL):
        token = match.group()
        if token == '{br}' or not literal and token in ('<br>', '<br/>', '<br />'):
            value = '\n'
        elif (token.startswith('{') or
              not literal and (token.startswith('<') or '[---]' in token or remove_chords(token) == '')):
            continue
        else:
            value = token if literal else html.unescape(token).replace('\xa0', ' ')
        text.extend(value)
        spans.extend([(match.start() + index, match.start() + index + 1) for index in range(len(value))]
                     if value == token else [(match.start(), match.end())] * len(value))
    return ''.join(text), spans


def replace_visible_text(source, spans, before, after, literal=False):
    """Apply only changed characters, retaining formatting, chords and split markers."""
    edits = []
    for operation, first, last, new_first, new_last in SequenceMatcher(
            None, before, after, autojunk=False).get_opcodes():
        if operation == 'equal':
            continue
        position = spans[first][0] if first < len(spans) else spans[-1][1] if spans else 0
        for start, end in set(spans[first:last]):
            edits.append((start, end, ''))
        value = after[new_first:new_last]
        edits.append((position, position, value if literal else html.escape(value, quote=False)))
    for start, end, value in sorted(edits, reverse=True):
        source = source[:start] + value + source[end:]
    return source


def source_selection(source, selection, literal=False):
    """Map Chromium's UTF-16 selection to source characters, excluding outer formatting tags."""
    text, spans = visible_text(source, literal=literal)
    offsets = [selection.get(key) for key in ('anchor', 'position')]
    encoded = text.encode('utf-16-le')
    if any(not isinstance(offset, int) or not 0 <= offset * 2 <= len(encoded) for offset in offsets):
        return None
    anchor, position = [len(encoded[:offset * 2].decode('utf-16-le', errors='ignore')) for offset in offsets]
    if anchor == position:
        point = spans[anchor][0] if anchor < len(spans) else spans[-1][1] if spans else 0
        return point, point
    start, end = spans[min(anchor, position)][0], spans[max(anchor, position) - 1][1]
    return (start, end) if anchor < position else (end, start)
