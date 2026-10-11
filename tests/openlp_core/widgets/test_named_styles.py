"""Named styles replace one another without changing neighbouring text or emphasis."""
import pytest
from PySide6 import QtGui

from opal.core.widgets.edits import SpellTextEdit


@pytest.fixture
def editor(mock_settings, monkeypatch):
    from opal.core.lib.formattingtags import FormattingTags
    tags = [{'desc': name, 'start tag': '{' + tag + '}', 'end tag': '{/' + tag + '}',
             'start html': '<span style="color:' + colour + '">'}
            for name, tag, colour in [('Red', 'r', 'red'), ('Blue', 'bl', 'blue')]]
    tags += [{'desc': 'Bold', 'start tag': '{st}', 'end tag': '{/st}', 'start html': '<strong>'}]
    monkeypatch.setattr(FormattingTags, 'get_html_tags', lambda: tags)
    yield SpellTextEdit()


def select(editor, text):
    cursor = editor.textCursor()
    start = editor.toPlainText().index(text)
    cursor.setPosition(start)
    cursor.setPosition(start + len(text), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


@pytest.mark.parametrize('source, selection, expected', [
    ('{r}Hello world{/r}', 'world', '{r}Hello {/r}{bl}world{/bl}'),
    ('{r}Hello{/r} plain {r}world{/r}', 'Hello{/r} plain {r}world', '{bl}Hello plain world{/bl}'),
    ('{r}{st}Hello{/st}{/r}', '{st}Hello{/st}', '{bl}{st}Hello{/st}{/bl}'),
    ('{r}{bl}Hello{/bl}{/r}', 'Hello', '{bl}Hello{/bl}'),
    ('{r}{st}Hello world{/st}{/r}', 'world', '{r}{st}Hello {/st}{/r}{st}{bl}world{/bl}{/st}'),
])
def test_replacement_is_exclusive_and_undoable(editor, source, selection, expected):
    editor.setPlainText(source)
    select(editor, selection)
    editor._custom_formatting_combo.activated.emit(2)
    assert editor.toPlainText() == expected
    editor.undo()
    assert editor.toPlainText() == source


def test_none_removes_only_the_named_style(editor):
    editor.setPlainText('{st}{r}Hello world{/r}{/st}')
    select(editor, 'world')
    editor._custom_formatting_combo.activated.emit(0)
    assert editor.toPlainText() == '{st}{r}Hello {/r}world{/st}'


def test_replacement_at_caret_keeps_the_rest_of_the_style_and_cursor(editor):
    editor.setPlainText('{r}Hello world{/r}')
    cursor = editor.textCursor()
    cursor.setPosition(len('{r}Hello wo'))
    editor.setTextCursor(cursor)
    editor._custom_formatting_combo.activated.emit(2)
    assert editor.toPlainText() == '{r}Hello {/r}{bl}world{/bl}'
    assert not editor.textCursor().hasSelection()
    assert editor.textCursor().position() == len('{r}Hello {/r}{bl}wo')


def test_mixed_selection_and_programmatic_sync_do_not_edit_text(editor):
    source = '{r}Hello{/r} {bl}world{/bl}'
    editor.setPlainText(source)
    editor.selectAll()
    editor._update_toolbar_state()
    assert editor._custom_formatting_combo.currentIndex() == -1
    assert editor._custom_formatting_combo.placeholderText() == 'Mixed'
    assert editor.toPlainText() == source
    editor._custom_formatting_combo.setCurrentIndex(1)
    assert editor.toPlainText() == source


def test_uniform_style_across_slides_is_not_mixed(editor):
    editor.setPlainText('{r}Hello{/r}\n[---]\n{r}world{/r}')
    editor.selectAll()
    editor._update_toolbar_state()
    assert editor._custom_formatting_combo.currentIndex() == 1
    editor._custom_formatting_combo.activated.emit(2)
    assert editor.toPlainText() == '{bl}Hello{/bl}\n[---]\n{bl}world{/bl}'


def test_context_menu_styles_also_replace_existing_styles(editor):
    editor.setPlainText('{r}Hello{/r}')
    editor.selectAll()
    editor.html_tag('Blue')
    assert editor.toPlainText() == '{bl}Hello{/bl}'
