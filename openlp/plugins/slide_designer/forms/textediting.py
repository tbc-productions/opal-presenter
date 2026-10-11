"""Map edits in a rendered page back to its lyrics without losing source tags."""
import html
import re
from difflib import SequenceMatcher

from openlp.core.display.render import remove_chords
from openlp.core.lib.formattingtags import FormattingTags


def visible_text(source):
    """Return plain text and the source span belonging to each visible character."""
    hidden = [re.escape(tag['start tag']) + r'.*?' + re.escape(tag['end tag'])
              for tag in FormattingTags.get_html_tags() if tag.get('hidden')]
    pattern = '|'.join(hidden + [r'\n?\[---\]', r'\{/?[^{}\n]+\}', r'<[^>]+>',
                                 r'&(?:#\d+|#x[\da-fA-F]+|\w+);', r'\[[^\]\n]+\]', r'.'])
    text, spans = [], []
    for match in re.finditer(pattern, source, re.DOTALL):
        token = match.group()
        if token in ('{br}', '<br>', '<br/>', '<br />'):
            value = '\n'
        elif token.startswith(('{', '<')) or '[---]' in token or remove_chords(token) == '':
            continue
        else:
            value = html.unescape(token).replace('\xa0', ' ')
        text.extend(value)
        spans.extend([(match.start() + index, match.start() + index + 1) for index in range(len(value))]
                     if value == token else [(match.start(), match.end())] * len(value))
    return ''.join(text), spans


def replace_visible_text(source, spans, before, after):
    """Apply only changed characters, retaining formatting, chords and split markers."""
    edits = []
    for operation, first, last, new_first, new_last in SequenceMatcher(
            None, before, after, autojunk=False).get_opcodes():
        if operation == 'equal':
            continue
        position = spans[first][0] if first < len(spans) else spans[-1][1] if spans else 0
        for start, end in set(spans[first:last]):
            edits.append((start, end, ''))
        edits.append((position, position, html.escape(after[new_first:new_last], quote=False)))
    for start, end, value in sorted(edits, reverse=True):
        source = source[:start] + value + source[end:]
    return source
