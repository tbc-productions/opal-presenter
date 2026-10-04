"""Regression checks for formatting and minimum contrast on service sheets."""
from unittest.mock import patch

import pytest
from PySide6 import QtGui

from openlp.core.lib.formattingtags import FormattingTags
from openlp.core.lib.serviceprint import print_color, prepare_print_document, render_print_text, white_contrast


@pytest.mark.parametrize('source', [
    '#fff', '#ccc', '#ffff00', '#ffc0cb', '#ffa500', '#008000', '#0000ff', '#000000', 'transparent', '#80ffffff'
])
def test_print_colours_meet_contrast(source):
    original = QtGui.QColor(source)
    adjusted = print_color(original)
    assert adjusted.alpha() == 255
    assert white_contrast(adjusted) >= 4.0
    if original.alpha() == 255 and white_contrast(original) >= 4.0:
        assert adjusted == original


def test_css_inheritance_and_backgrounds_are_readable(qapp):
    document = QtGui.QTextDocument()
    prepare_print_document(document, '''<style>.pale { color: #ccc; background-color: #222; }</style>
        <div class="pale"><strong>Inherited</strong></div>
        <font color="#fff">White</font><span style="-webkit-text-fill-color:yellow">Yellow</span>
        <span style="color:rgba(255,255,255,0.5)">Alpha</span>
        <table bgcolor="#000"><tr><td bgcolor="#333">Table</td></tr></table>''')
    for word in ('Inherited', 'White', 'Yellow', 'Alpha', 'Table'):
        char_format = document.find(word).charFormat()
        assert white_contrast(char_format.foreground().color()) >= 4.0
        assert char_format.background().color().name() == '#ffffff'
    assert document.find('Inherited').charFormat().fontWeight() >= QtGui.QFont.Weight.Bold


def test_hidden_and_unknown_tags_do_not_leak(settings):
    tags = list(FormattingTags.get_html_tags()) + [
        {'start tag': '{hidden}', 'end tag': '{/hidden}', 'start html': '', 'end html': '', 'hidden': True}
    ]
    with patch.object(FormattingTags, 'get_html_tags', return_value=tags):
        output = render_print_text('{st}Bold{/st} {hidden}secret{/hidden} {unknown}visible{/unknown} {unpaired}')
    assert 'secret' not in output
    assert 'visible' in output and '<strong>Bold</strong>' in output
    assert '{' not in output and '}' not in output


def test_chords_keep_their_formatting(settings):
    output = render_print_text('{st}[C]Amazing{/st}{br}[G]Grace', render_chords=True)
    assert 'chordrow' in output and '<strong>' in output
    assert '{' not in output and '}' not in output
