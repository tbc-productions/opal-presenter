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
This module contains tests for the openlp.core.widgets.edits module
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch, call
from typing import Any

from PySide6 import QtCore, QtGui, QtTest
import fluentqt
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.path import path_to_str
from openlp.core.common.platform import is_win
from openlp.core.common.registry import Registry
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.edits import PathEdit, HistoryComboBox, SearchEdit, SpellTextEdit, Highlighter, FormattingTagDelegate
from openlp.core.widgets.enums import PathEditType


class SearchTypes(object):
    """
    Types of search
    """
    First = 0
    Second = 1


SECOND_PLACEHOLDER_TEXT = "Second Placeholder Text"
SEARCH_TYPES = [(SearchTypes.First, QtGui.QIcon(), "First", "First Placeholder Text"),
                (SearchTypes.Second, QtGui.QIcon(), "Second", SECOND_PLACEHOLDER_TEXT)]


if is_win():
    p_prefix = 'C:\\'
else:
    p_prefix = ''


@pytest.fixture()
@patch('openlp.core.ui.icons.is_ui_theme_dark')
def search_edit(mock_is_dark: MagicMock, mock_settings: MagicMock) -> SearchEdit:
    main_window = QtWidgets.QMainWindow()
    Registry().register('main_window', main_window)
    Registry().remove('settings')
    Registry().register('settings', MagicMock(**{'value.return_value': SearchTypes.First}))

    s_edit = SearchEdit(main_window, 'settings_section')
    # To complete set up we have to set the search types.
    s_edit.set_search_types(SEARCH_TYPES)
    return s_edit


@pytest.fixture()
def history_combo(mock_settings: MagicMock) -> HistoryComboBox:
    main_window = QtWidgets.QMainWindow()
    Registry().register('main_window', main_window)
    s_combo = HistoryComboBox(main_window)
    return s_combo


@pytest.fixture()
def path_edit(mock_settings: MagicMock) -> PathEdit:
    with patch('openlp.core.widgets.edits.PathEdit._setup'):
        return PathEdit()


def test_path_getter(path_edit: PathEdit):
    """
    Test the `path` property getter.
    """
    # GIVEN: An instance of PathEdit with the `_path` instance variable set
    path_edit._path = Path('getter', 'test', 'pat.h')

    # WHEN: Reading the `path` property
    # THEN: The value that we set should be returned
    assert path_edit.path == Path('getter', 'test', 'pat.h')


@pytest.mark.parametrize('prop, expected', [
    (Path(p_prefix, 'setter', 'test', 'pat.h'), (p_prefix, 'setter', 'test', 'pat.h')),
    (p_prefix + 'setter/str/test/pat.h', (p_prefix, 'setter', 'str', 'test', 'pat.h')),
    (None, None)
])
def test_path_setter(prop: Any, expected: Any, path_edit: PathEdit):
    """
    Test the `path` property setter.
    """
    # GIVEN: An instance of the PathEdit object and a mocked `line_edit`
    path_edit.line_edit = MagicMock()

    # WHEN: Writing to the `path` property
    path_edit.path = prop

    # THEN: The `_path` instance variable should be set with the test data. The `line_edit` text and tooltip
    #       should have also been set.
    if expected is not None:
        assert path_edit._path == Path(*expected)
        os_normalised_str = path_to_str(Path(*expected))
        path_edit.line_edit.setToolTip.assert_called_once_with(os_normalised_str)
        path_edit.line_edit.setText.assert_called_once_with(os_normalised_str)
    else:
        assert path_edit._path is None


def test_path_type_getter(path_edit: PathEdit):
    """
    Test the `path_type` property getter.
    """
    # GIVEN: An instance of PathEdit
    # WHEN: Reading the `path` property
    # THEN: The default value should be returned
    assert path_edit.path_type == PathEditType.Files


def test_path_type_setter(path_edit: PathEdit):
    """
    Test the `path_type` property setter.
    """
    # GIVEN: An instance of the PathEdit object and a mocked `update_button_tool_tips` method.
    with patch.object(path_edit, 'update_button_tool_tips') as mocked_update_button_tool_tips:

        # WHEN: Writing to a different value than default to the `path_type` property
        path_edit.path_type = PathEditType.Directories

        # THEN: The `_path_type` instance variable should be set with the test data and not the default. The
        #       update_button_tool_tips should have been called.
        assert path_edit._path_type == PathEditType.Directories
        mocked_update_button_tool_tips.assert_called_once_with()


def test_update_button_tool_tips_directories(path_edit: PathEdit):
    """
    Test the `update_button_tool_tips` method.
    """
    # GIVEN: An instance of PathEdit with the `path_type` set to `Directories`
    path_edit.browse_button = MagicMock()
    path_edit.revert_button = MagicMock()
    path_edit._path_type = PathEditType.Directories

    # WHEN: Calling update_button_tool_tips
    path_edit.update_button_tool_tips()

    path_edit.browse_button.setToolTip.assert_called_once_with('Browse for directory.')
    path_edit.revert_button.setToolTip.assert_called_once_with('Revert to default directory.')


def test_update_button_tool_tips_files(path_edit: PathEdit):
    """
    Test the `update_button_tool_tips` method.
    """
    # GIVEN: An instance of PathEdit with the `path_type` set to `Files`
    path_edit.browse_button = MagicMock()
    path_edit.revert_button = MagicMock()
    path_edit._path_type = PathEditType.Files

    # WHEN: Calling update_button_tool_tips
    path_edit.update_button_tool_tips()

    path_edit.browse_button.setToolTip.assert_called_once_with('Browse for file.')
    path_edit.revert_button.setToolTip.assert_called_once_with('Revert to default file.')


@patch('openlp.core.widgets.edits.FileDialog.getExistingDirectory', return_value=None)
@patch('openlp.core.widgets.edits.FileDialog.getOpenFileName')
def test_on_browse_button_clicked_directory(mocked_get_open_file_name: MagicMock,
                                            mocked_get_existing_directory: MagicMock, path_edit: PathEdit):
    """
    Test the `browse_button` `clicked` handler on_browse_button_clicked when the `path_type` is set to Directories.
    """
    # GIVEN: An instance of PathEdit with the `path_type` set to `Directories` and a mocked
    #        QFileDialog.getExistingDirectory
    path_edit._path_type = PathEditType.Directories
    path_edit._path = Path('test', 'path')

    # WHEN: Calling on_browse_button_clicked
    path_edit.on_browse_button_clicked()

    # THEN: The FileDialog.getExistingDirectory should have been called with the default caption
    mocked_get_existing_directory.assert_called_once_with(path_edit, 'Select Directory',
                                                          Path('test', 'path'),
                                                          FileDialog.Option.ShowDirsOnly)
    assert mocked_get_open_file_name.called is False


def test_on_browse_button_clicked_directory_custom_caption(path_edit: PathEdit):
    """
    Test the `browse_button` `clicked` handler on_browse_button_clicked when the `path_type` is set to Directories,
    and `dialog_caption` is set.
    """
    # GIVEN: An instance of PathEdit with the `path_type` set to `Directories` and a mocked
    #        QFileDialog.getExistingDirectory with `default_caption` set.
    with patch('openlp.core.widgets.edits.FileDialog.getExistingDirectory', return_value=None) as \
            mocked_get_existing_directory, \
            patch('openlp.core.widgets.edits.FileDialog.getOpenFileName') as mocked_get_open_file_name:
        path_edit._path_type = PathEditType.Directories
        path_edit._path = Path('test', 'path')
        path_edit.dialog_caption = 'Directory Caption'

        # WHEN: Calling on_browse_button_clicked
        path_edit.on_browse_button_clicked()

        # THEN: The FileDialog.getExistingDirectory should have been called with the custom caption
        mocked_get_existing_directory.assert_called_once_with(path_edit, 'Directory Caption',
                                                              Path('test', 'path'),
                                                              FileDialog.Option.ShowDirsOnly)
        assert mocked_get_open_file_name.called is False


def test_on_browse_button_clicked_file(path_edit: PathEdit):
    """
    Test the `browse_button` `clicked` handler on_browse_button_clicked when the `path_type` is set to Files.
    """
    # GIVEN: An instance of PathEdit with the `path_type` set to `Files` and a mocked QFileDialog.getOpenFileName
    with patch('openlp.core.widgets.edits.FileDialog.getExistingDirectory') as mocked_get_existing_directory, \
            patch('openlp.core.widgets.edits.FileDialog.getOpenFileName', return_value=(None, '')) as \
            mocked_get_open_file_name:
        path_edit._path_type = PathEditType.Files
        path_edit._path = Path('test', 'pat.h')

        # WHEN: Calling on_browse_button_clicked
        path_edit.on_browse_button_clicked()

        # THEN: The FileDialog.getOpenFileName should have been called with the default caption
        mocked_get_open_file_name.assert_called_once_with(path_edit, 'Select File', Path('test', 'pat.h'),
                                                          path_edit.filters)
        assert mocked_get_existing_directory.called is False


def test_on_browse_button_clicked_file_custom_caption(path_edit: PathEdit):
    """
    Test the `browse_button` `clicked` handler on_browse_button_clicked when the `path_type` is set to Files and
    `dialog_caption` is set.
    """
    # GIVEN: An instance of PathEdit with the `path_type` set to `Files` and a mocked QFileDialog.getOpenFileName
    #        with `default_caption` set.
    with patch('openlp.core.widgets.edits.FileDialog.getExistingDirectory') as mocked_get_existing_directory, \
            patch('openlp.core.widgets.edits.FileDialog.getOpenFileName', return_value=(None, '')) as \
            mocked_get_open_file_name:
        path_edit._path_type = PathEditType.Files
        path_edit._path = Path('test', 'pat.h')
        path_edit.dialog_caption = 'File Caption'

        # WHEN: Calling on_browse_button_clicked
        path_edit.on_browse_button_clicked()

        # THEN: The FileDialog.getOpenFileName should have been called with the custom caption
        mocked_get_open_file_name.assert_called_once_with(path_edit, 'File Caption', Path('test', 'pat.h'),
                                                          path_edit.filters)
        assert mocked_get_existing_directory.called is False


def test_on_browse_button_clicked_user_cancels(path_edit: PathEdit):
    """
    Test the `browse_button` `clicked` handler on_browse_button_clicked when the user cancels the FileDialog (an
    empty str is returned)
    """
    # GIVEN: An instance of PathEdit with a mocked QFileDialog.getOpenFileName which returns an empty str for the
    #        file path.
    with patch('openlp.core.widgets.edits.FileDialog.getOpenFileName', return_value=(None, '')) as \
            mocked_get_open_file_name:

        # WHEN: Calling on_browse_button_clicked
        path_edit.on_browse_button_clicked()

        # THEN: normpath should not have been called
        assert mocked_get_open_file_name.called is True


def test_on_browse_button_clicked_user_accepts(path_edit: PathEdit):
    """
    Test the `browse_button` `clicked` handler on_browse_button_clicked when the user accepts the FileDialog (a path
    is returned)
    """
    # GIVEN: An instance of PathEdit with a mocked QFileDialog.getOpenFileName which returns a str for the file
    #        path.
    with patch('openlp.core.widgets.edits.FileDialog.getOpenFileName',
               return_value=(Path('test', 'pat.h'), '')) as mocked_get_open_file_name, \
            patch.object(path_edit, 'on_new_path'):

        # WHEN: Calling on_browse_button_clicked
        path_edit.on_browse_button_clicked()

        # THEN: normpath and `on_new_path` should have been called
        assert mocked_get_open_file_name.called is True
        assert path_edit.on_new_path.called is True


def test_on_revert_button_clicked(path_edit: PathEdit):
    """
    Test that the default path is set as the path when the `revert_button.clicked` handler is called.
    """
    # GIVEN: An instance of PathEdit with a mocked `on_new_path`, and the `default_path` set.
    with patch.object(path_edit, 'on_new_path') as mocked_on_new_path:
        path_edit.default_path = Path('default', 'pat.h')

        # WHEN: Calling `on_revert_button_clicked`
        path_edit.on_revert_button_clicked()

        # THEN: on_new_path should have been called with the default path
        mocked_on_new_path.assert_called_once_with(Path('default', 'pat.h'))


def test_on_line_edit_editing_finished(path_edit: PathEdit):
    """
    Test that the new path is set as the path when the `line_edit.editingFinished` handler is called.
    """
    # GIVEN: An instance of PathEdit with a mocked `line_edit` and `on_new_path`.
    with patch.object(path_edit, 'on_new_path') as mocked_on_new_path:
        path_edit.line_edit = MagicMock(**{'text.return_value': 'test/pat.h'})

        # WHEN: Calling `on_line_edit_editing_finished`
        path_edit.on_line_edit_editing_finished()

        # THEN: on_new_path should have been called with the path enetered in `line_edit`
        mocked_on_new_path.assert_called_once_with(Path('test', 'pat.h'))


def test_on_new_path_no_change(path_edit: PathEdit):
    """
    Test `on_new_path` when called with a path that is the same as the existing path.
    """
    # GIVEN: An instance of PathEdit with a test path and mocked `pathChanged` signal
    with patch('openlp.core.widgets.edits.PathEdit.path', new_callable=PropertyMock):
        path_edit._path = Path('/old', 'test', 'pat.h')
        path_edit.pathChanged = MagicMock()

        # WHEN: Calling `on_new_path` with the same path as the existing path
        path_edit.on_new_path(Path('/old', 'test', 'pat.h'))

        # THEN: The `pathChanged` signal should not be emitted
        assert path_edit.pathChanged.emit.called is False


def test_on_new_path_change(path_edit: PathEdit):
    """
    Test `on_new_path` when called with a path that is the different to the existing path.
    """
    # GIVEN: An instance of PathEdit with a test path and mocked `pathChanged` signal
    with patch('openlp.core.widgets.edits.PathEdit.path', new_callable=PropertyMock):
        path_edit._path = Path('/old', 'test', 'pat.h')
        path_edit.pathChanged = MagicMock()

        # WHEN: Calling `on_new_path` with the a new path
        path_edit.on_new_path(Path('/new', 'test', 'pat.h'))

        # THEN: The `pathChanged` signal should be emitted
        path_edit.pathChanged.emit.assert_called_once_with(Path('/new', 'test', 'pat.h'))


def test_on_new_path_none(path_edit: PathEdit):
    """
    Test `on_new_path` when called with a path that is None
    """
    # GIVEN: An instance of PathEdit with a test path and mocked `pathChanged` signal
    with patch('openlp.core.widgets.edits.PathEdit.path', new_callable=PropertyMock):
        path_edit._path = Path('/old', 'test', 'pat.h')
        path_edit.pathChanged = MagicMock()

        # WHEN: Calling `on_new_path` with the same path as the existing path
        path_edit.on_new_path(None)

        # THEN: The `pathChanged` signal should not be emitted
        assert path_edit.pathChanged.emit.called is False


def test_set_search_types(search_edit: SearchEdit):
    """
    Test setting the search types of the search edit.
    """
    # GIVEN: The search edit with the search types set. NOTE: The set_search_types(types) is called in the setUp()
    # method!

    # WHEN:

    # THEN: The first search type should be the first one in the list. The selected type should be saved in the
    #       settings
    assert search_edit.current_search_type() == SearchTypes.First, \
        "The first search type should be selected."
    Registry().get('settings').setValue.assert_called_once_with('settings_section/last used search type', 0)


def test_set_current_search_type(search_edit: SearchEdit):
    """
    Test if changing the search type works.
    """
    # GIVEN:
    # WHEN: Change the search type
    result = search_edit.set_current_search_type(SearchTypes.Second)

    # THEN:
    assert result is True, "The call should return success (True)."
    assert search_edit.current_search_type() == SearchTypes.Second, \
        "The search type should be SearchTypes.Second"
    assert search_edit.placeholderText() == SECOND_PLACEHOLDER_TEXT, \
        "The correct placeholder text should be 'Second Placeholder Text'."
    Registry().get('settings').setValue.assert_has_calls(
        [call('settings_section/last used search type', 0), call('settings_section/last used search type', 1)])


def test_clear_button_visibility(search_edit: SearchEdit):
    """
    Test if the clear button is hidden/shown correctly.
    """
    # GIVEN: A visible search field with no text.
    Registry().get('main_window').show()
    search_edit.show()
    QtWidgets.QApplication.processEvents()
    clear_button = search_edit.findChild(QtWidgets.QWidget, 'fluentLineEditClearButton')
    assert search_edit.isClearButtonEnabled()
    assert clear_button.isHidden(), "Pre condition not met. Button should be hidden."

    # WHEN: Type something in the search edit.
    QtTest.QTest.keyPress(search_edit, QtCore.Qt.Key.Key_A)
    QtTest.QTest.keyRelease(search_edit, QtCore.Qt.Key.Key_A)

    # THEN: The clear button should not be hidden any more.
    assert not clear_button.isHidden(), "The clear button should be visible."


def test_press_clear_button(search_edit: SearchEdit):
    """
    Check if the search edit behaves correctly when pressing the clear button.
    """
    # GIVEN: A visible search edit with text.
    Registry().get('main_window').show()
    search_edit.show()
    QtWidgets.QApplication.processEvents()
    QtTest.QTest.keyPress(search_edit, QtCore.Qt.Key.Key_A)
    QtTest.QTest.keyRelease(search_edit, QtCore.Qt.Key.Key_A)

    # WHEN: Press the clear button.
    clear_button = search_edit.findChild(QtWidgets.QWidget, 'fluentLineEditClearButton')
    QtTest.QTest.mouseClick(clear_button, QtCore.Qt.MouseButton.LeftButton)

    # THEN: The search edit text should be cleared and the button be hidden.
    assert not search_edit.text(), "The search edit should not have any text."
    assert clear_button.isHidden(), "The clear button should be hidden."


def test_search_selector_does_not_overlap_native_clear_button(search_edit: SearchEdit):
    """Resizing keeps the selector, input text and native clear control apart."""
    Registry().get('main_window').show()
    search_edit.show()
    search_edit.setText('Search text')
    for direction in (QtCore.Qt.LayoutDirection.LeftToRight, QtCore.Qt.LayoutDirection.RightToLeft):
        search_edit.setLayoutDirection(direction)
        search_edit.resize(320, 40)
        QtWidgets.QApplication.processEvents()
        clear_button = search_edit.findChild(QtWidgets.QWidget, 'fluentLineEditClearButton')
        assert not search_edit.menu_button.geometry().intersects(clear_button.geometry())
        assert search_edit.contentMargins().left() > search_edit.menu_button.geometry().right()


def test_history_combo_get_items(history_combo: HistoryComboBox):
    """
    Test the getItems() method
    """
    # GIVEN: The history_combo.

    # WHEN: Add two items.
    history_combo.addItem('test1')
    history_combo.addItem('test2')

    # THEN: The list of items should contain both strings.
    assert history_combo.getItems() == ['test1', 'test2']


@pytest.mark.parametrize('line, expected', [
    ('[---]', QtCore.Qt.PenStyle.DotLine),
    (' [---] ', QtCore.Qt.PenStyle.DotLine),
    ('[--}{--]', QtCore.Qt.PenStyle.SolidLine),
    ('[===]', QtCore.Qt.PenStyle.SolidLine),
    (' [--}{--] ', QtCore.Qt.PenStyle.SolidLine),
    ('plain text', None)
])
def test_spell_text_edit_split_marker_style_for_text(line, expected):
    """Test split marker line style detection used by the visual split renderer."""
    assert SpellTextEdit.split_marker_style_for_text(line) == expected


@pytest.mark.parametrize('line, expected', [
    ('[===]', 2.5),
    (' [===] ', 2.5),
    ('[---]', 1.0),
    ('[--}{--]', 1.0),
    ('plain text', 1.0)
])
def test_spell_text_edit_split_marker_width_for_text(line, expected):
    """Test split marker line width detection used by the visual split renderer."""
    assert SpellTextEdit.split_marker_width_for_text(line) == expected


def test_highlighter_format_from_start_html_maps_css(mock_settings):
    """Test conversion of HTML/CSS from formatting tags into QTextCharFormat settings."""
    document = QtGui.QTextDocument()
    highlighter = Highlighter(document)

    text_format = highlighter._format_from_start_html(
        '<span style="-webkit-text-fill-color:red; font-size:80%; font-weight:700; opacity:0.5;">')

    assert text_format.fontWeight() == QtGui.QFont.Weight.Bold
    assert text_format.fontPointSize() > 0
    assert text_format.foreground().color().isValid() is True
    assert text_format.foreground().color().alphaF() == pytest.approx(0.5, rel=0.05)


@pytest.mark.parametrize('text, expected', [
    ("{tt}The Lord's Prayer{/tt}", "The Lord's Prayer"),
    ('{tt}{st}Title & <lyrics>{/st}{/tt}', 'Title & <lyrics>'),
    ('{tt}Unclosed tag', 'Unclosed tag'),
    ('Closing tag{/tt}', 'Closing tag'),
])
def test_read_only_formatting_preview_hides_unregistered_tags(settings, text, expected):
    """Read-only previews hide unknown markers while retaining text and known styles."""
    document = FormattingTagDelegate._build_text_document(QtGui.QFont(), text, 500)
    assert document.toPlainText() == expected
    if '{st}' in text:
        cursor = QtGui.QTextCursor(document)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.NextCharacter)
        assert cursor.charFormat().fontWeight() == QtGui.QFont.Weight.Bold


def test_highlighter_unknown_tag_opacity(mock_settings):
    """Unknown formatting tags should be rendered in red."""
    text_format = Highlighter._unknown_token_format()
    color = text_format.foreground().color()
    assert color.red() > 200
    assert color.green() < 100
    assert color.blue() < 100


def test_highlighter_hidden_token_format(mock_settings):
    """Hidden tokens in rich mode should be transparent, near-zero size, and zero-width."""
    text_format = Highlighter._hidden_token_format()
    assert text_format.foreground().color().alpha() == 0
    assert text_format.fontPointSize() == pytest.approx(0.001, rel=0.05)
    assert text_format.fontStretch() == 1
    assert text_format.fontLetterSpacingType() == QtGui.QFont.SpacingType.AbsoluteSpacing
    assert text_format.fontLetterSpacing() == pytest.approx(0.0, abs=0.01)


def test_highlighter_iter_tag_regions_separates_tokens_from_content(mock_settings):
    """Known tag parsing should isolate the token ranges from the inner content range."""
    regions = list(Highlighter._iter_tag_regions(
        '{st}Hello{/st}',
        [{'start tag': '{st}', 'end tag': '{/st}', 'start html': '<strong>'}]
    ))

    assert regions == [{
        'html': {'start tag': '{st}', 'end tag': '{/st}', 'start html': '<strong>'},
        'start_token_start': 0,
        'start_token_length': 4,
        'content_start': 4,
        'content_length': 5,
        'end_token_start': 9,
        'end_token_length': 5
    }]


def test_highlighter_find_closing_tag_depth_aware_simple(mock_settings):
    """Depth-aware close finder should return the first close when there is no nesting."""
    pos = Highlighter._find_closing_tag_depth_aware('{st}Hello{/st}', '{st}', '{/st}',
                                                    start_pos=4, start_depth=1)
    assert pos == 9


def test_highlighter_find_closing_tag_depth_aware_nested(mock_settings):
    """Depth-aware close finder should skip nested same-tag pairs and find the outer close."""
    # Outer open at 0, inner open at 9 and close at 15, outer close at 22.
    text = '{st}a{st}b{/st}c{/st}'
    pos = Highlighter._find_closing_tag_depth_aware(text, '{st}', '{/st}',
                                                    start_pos=4, start_depth=1)
    # The outer close is at position 16.
    assert pos == text.rfind('{/st}')


def test_highlighter_find_closing_tag_depth_aware_returns_minus_one_when_unclosed(mock_settings):
    """Depth-aware close finder should return -1 when no balanced close exists."""
    pos = Highlighter._find_closing_tag_depth_aware('{st}a{st}b{/st}c', '{st}', '{/st}',
                                                    start_pos=4, start_depth=1)
    assert pos == -1


def test_highlighter_nested_same_tag_does_not_close_outer_span_prematurely(mock_settings):
    """An inner {st}...{/st} must not terminate the outer continuation span."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    # Outer {st} opens on line 0 and closes on line 1 AFTER an inner {st}...{/st}.
    editor.setPlainText('{st}Line one\nFor the {st}kingdom{/st} power Amen.{/st}')

    doc = editor.document()
    block0 = doc.findBlockByNumber(0)
    block1 = doc.findBlockByNumber(1)
    assert block0.isValid() and block1.isValid()

    # Block 0: outer {st} is unclosed so userState > 0.
    assert block0.userState() > 0

    # Block 1: outer {st} closes (after the inner pair) so ends clean.
    assert block1.userState() == 0

    # Document text must be unchanged.
    assert editor.toPlainText() == '{st}Line one\nFor the {st}kingdom{/st} power Amen.{/st}'


def test_highlighter_multi_line_block_state_continues_span(mock_settings):
    """A tag that opens in one block and closes in the next should not corrupt document text."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    # Two-line text: tag opens on line 1 and closes on line 2.
    editor.setPlainText('{st}Line one\nLine two{/st}')

    doc = editor.document()

    # Both blocks must exist with correct raw text.
    block0 = doc.findBlockByNumber(0)
    block1 = doc.findBlockByNumber(1)
    assert block0.isValid()
    assert block1.isValid()
    assert block0.text() == '{st}Line one'
    assert block1.text() == 'Line two{/st}'

    # The full document text must be unchanged (highlighter must not mutate it).
    assert editor.toPlainText() == '{st}Line one\nLine two{/st}'

    # Block 0 should have been highlighted with a continuation state (> 0) because
    # the open tag has no matching close on the same line.  We read it via the
    # block's stored user-state which Qt copies from setCurrentBlockState.
    assert block0.userState() > 0

    # Block 1 ends clean — the span closes within it.
    assert block1.userState() == 0


def test_highlighter_span_continues_across_split_marker(mock_settings):
    """A formatting tag that straddles a split marker should propagate its state through it."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    # Bold tag open on line 0, split marker on line 1, closing tag on line 2.
    editor.setPlainText('{st}Before split\n[---]\nAfter split{/st}')

    doc = editor.document()
    block0 = doc.findBlockByNumber(0)  # '{st}Before split'
    block1 = doc.findBlockByNumber(1)  # '[---]'
    block2 = doc.findBlockByNumber(2)  # 'After split{/st}'

    assert block0.isValid() and block1.isValid() and block2.isValid()

    # Block 0: unclosed tag → state > 0.
    assert block0.userState() > 0

    # Block 1: split marker must PROPAGATE the incoming state (not reset to 0)
    # so block 2 can resume the span correctly.
    assert block1.userState() == block0.userState()

    # Block 2: span closes here → ends clean.
    assert block2.userState() == 0

    # Document text must be unchanged.
    assert editor.toPlainText() == '{st}Before split\n[---]\nAfter split{/st}'


def test_highlighter_combines_nested_tag_styles(mock_settings):
    """Nested tags should combine visual styles (for example bold + italic)."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}{it}Hello{/it}{/st}')

    block = editor.document().firstBlock()
    assert block.isValid()
    index_in_block = len('{st}{it}')

    content_format = None
    for format_range in block.layout().formats():
        start = format_range.start
        end = format_range.start + format_range.length
        if start <= index_in_block < end:
            content_format = format_range.format
            break

    assert content_format is not None
    assert content_format.fontWeight() == QtGui.QFont.Weight.Bold
    assert content_format.fontItalic() is True


def test_highlighter_combines_three_nested_tag_styles(mock_settings):
    """Nested tags should render all active styles, including underline."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}{it}{u}Hello{/u}{/it}{/st}')

    block = editor.document().firstBlock()
    assert block.isValid()
    index_in_block = len('{st}{it}{u}')

    content_format = None
    for format_range in block.layout().formats():
        start = format_range.start
        end = format_range.start + format_range.length
        if start <= index_in_block < end:
            content_format = format_range.format
            break

    assert content_format is not None
    assert content_format.fontWeight() == QtGui.QFont.Weight.Bold
    assert content_format.fontItalic() is True
    assert content_format.fontUnderline() is True


def test_highlighter_applies_uppercase_tag_visual_style(mock_settings):
    """The uppercase tag should apply uppercase visual capitalization."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{uc}Abide with me{/uc}')

    block = editor.document().firstBlock()
    assert block.isValid()
    index_in_block = len('{uc}') + 2

    content_format = None
    for format_range in block.layout().formats():
        start = format_range.start
        end = format_range.start + format_range.length
        if start <= index_in_block < end:
            content_format = format_range.format
            break

    assert content_format is not None
    assert content_format.fontCapitalization() == QtGui.QFont.Capitalization.AllUppercase


def test_highlighter_combines_three_styles_across_multiline_continuation(mock_settings):
    """Styles active across blocks should keep all active attributes, including underline."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}{it}\n{u}Hello\n{/u}{/it}{/st}')

    block = editor.document().findBlockByNumber(1)
    assert block.isValid()

    content_format = None
    for format_range in block.layout().formats():
        start = format_range.start
        end = format_range.start + format_range.length
        if start <= 4 < end:  # inside "Hello"
            content_format = format_range.format
            break

    assert content_format is not None
    assert content_format.fontWeight() == QtGui.QFont.Weight.Bold
    assert content_format.fontItalic() is True
    assert content_format.fontUnderline() is True


def test_spell_text_edit_does_not_add_tags_on_split_marker_line(mock_settings):
    """Formatting actions should not insert tokens on section split lines."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('[---]')

    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == '[---]'


def test_spell_text_edit_apply_formatting_selection_skips_split_lines(mock_settings):
    """Formatting across a selection containing a split line must skip the split marker line."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('foo\n[---]\nbar')

    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len('foo\n[---]\nbar'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == '{st}foo{/st}\n[---]\n{st}bar{/st}'


def test_spell_text_edit_apply_formatting_selection_skips_song_section_headers(mock_settings):
    """Formatting across song section headers should format each section independently."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('foo\n---[Verse:2]---\nbar')

    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len('foo\n---[Verse:2]---\nbar'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == '{st}foo{/st}\n---[Verse:2]---\n{st}bar{/st}'


def test_spell_text_edit_apply_formatting_across_sections_preserves_selection(mock_settings):
    """Applying formatting across sections should preserve selection over both formatted sections."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('foo\n---[Verse:2]---\nbar')

    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len('foo\n---[Verse:2]---\nbar'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('u')

    result_cursor = editor.textCursor()
    assert editor.toPlainText() == '{u}foo{/u}\n---[Verse:2]---\n{u}bar{/u}'
    assert result_cursor.hasSelection() is True
    assert result_cursor.selectionStart() == 3  # just after '{u}'
    assert result_cursor.selectionEnd() == len('{u}foo{/u}\n---[Verse:2]---\n{u}bar')


def test_spell_text_edit_does_not_add_tags_on_song_section_header_line(mock_settings):
    """Formatting actions should not insert tokens on song section header lines."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('---[Verse:2]---')

    cursor = editor.textCursor()
    cursor.setPosition(4)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == '---[Verse:2]---'


def test_spell_text_edit_toggle_rich_mode(mock_settings):
    """Rich/plain mode toggle should update both editor and highlighter state."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.set_rich_text_mode(False)
    assert editor.rich_text_mode is False
    assert editor.highlighter.rich_text_mode is False
    editor.set_rich_text_mode(True)
    assert editor.rich_text_mode is True
    assert editor.highlighter.rich_text_mode is True


def test_spell_text_edit_source_button_mapping(mock_settings):
    """Source button checked state should map to plain mode (unchecked means rich mode)."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)

    assert editor.rich_text_mode is True
    assert editor._mode_switch.isOn() is False
    assert isinstance(editor._mode_switch, fluentqt.ToggleSwitch)
    assert editor._mode_switch.onContent() == 'Source'
    assert editor._mode_switch.offContent() == 'Source'

    editor._mode_switch.setIsOn(True)
    assert editor.rich_text_mode is False
    assert editor.highlighter.rich_text_mode is False

    editor._mode_switch.setIsOn(False)
    assert editor.rich_text_mode is True
    assert editor.highlighter.rich_text_mode is True


@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_spell_text_edit_color_menu_population(mock_get_html_tags: MagicMock, mock_settings):
    """Color dropdown should include formatting tags that define text colors."""
    mock_get_html_tags.return_value = [
        {'desc': 'Red', 'start tag': '{r}', 'end tag': '{/r}',
         'start html': '<span style="-webkit-text-fill-color:red">'},
        {'desc': 'Bold', 'start tag': '{st}', 'end tag': '{/st}', 'start html': '<strong>'}
    ]

    editor = SpellTextEdit(None, formatting_tags_allowed=True)

    # Only the color tag should appear in the dropdown.
    assert editor._color_tags == ['{r}']
    assert isinstance(editor._custom_formatting_combo, QtWidgets.MultiSelectComboBox)
    assert editor._custom_formatting_combo.placeholderText() == 'Custom formatting'


@patch('openlp.core.widgets.edits.FormattingTagForm')
@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_spell_text_edit_edit_color_button_opens_dialog_and_refreshes(mock_get_html_tags: MagicMock,
                                                                      mock_formatting_tag_form: MagicMock,
                                                                      mock_settings):
    """The edit button should open the formatting tag dialog and refresh the dropdown when accepted."""
    mock_get_html_tags.side_effect = [
        [
            {'desc': 'Red', 'start tag': '{r}', 'end tag': '{/r}',
             'start html': '<span style="-webkit-text-fill-color:red">'}
        ],
        [
            {'desc': 'Blue', 'start tag': '{bl}', 'end tag': '{/bl}',
             'start html': '<span style="-webkit-text-fill-color:blue">'}
        ]
    ]
    mock_formatting_tag_form.return_value.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted

    editor = SpellTextEdit(None, formatting_tags_allowed=True)

    assert editor._color_tags == ['{r}']

    editor._edit_tags_action.trigger()

    mock_formatting_tag_form.assert_called_once()
    mock_formatting_tag_form.return_value.exec.assert_called_once_with()
    assert editor._color_tags == ['{bl}']


@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_spell_text_edit_custom_formatting_multiple_selection(mock_get_html_tags, mock_settings):
    """Selecting multiple options preserves each format and existing bold text."""
    mock_get_html_tags.return_value = [
        {'desc': 'Red', 'start tag': '{r}', 'end tag': '{/r}',
         'start html': '<span style="color:red">'},
        {'desc': 'Blue', 'start tag': '{bl}', 'end tag': '{/bl}',
         'start html': '<span style="color:blue">'}
    ]
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Hello world{/st}')
    cursor = editor.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(15, QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    combo = editor._custom_formatting_combo
    combo.setSelectedRows([0, 1])
    assert editor.toPlainText() == '{st}{r}{bl}Hello world{/bl}{/r}{/st}'
    assert combo.selectedRows() == [0, 1]
    combo.setSelectedRows([1])
    assert editor.toPlainText() == '{st}{bl}Hello world{/bl}{/st}'
    assert combo.selectedRows() == [1]
    editor.undo()
    assert editor.toPlainText() == '{st}{r}{bl}Hello world{/bl}{/r}{/st}'


@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_custom_formatting_preserves_slide_markers(mock_get_html_tags, mock_settings):
    mock_get_html_tags.return_value = [
        {'desc': 'Red', 'start tag': '{r}', 'end tag': '{/r}', 'start html': '<span style="color:red">'}
    ]
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('First slide\n[---]\nSecond slide')
    editor.selectAll()
    editor._custom_formatting_combo.setSelectedRows([0])
    assert editor.toPlainText() == '{r}First slide{/r}\n[---]\n{r}Second slide{/r}'
    editor._custom_formatting_combo.setSelectedRows([])
    assert editor.toPlainText() == 'First slide\n[---]\nSecond slide'


@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_spell_text_edit_custom_formatting_model_labels(mock_get_html_tags, mock_settings):
    """Native combo rows carry readable names, colour and tag metadata."""
    mock_get_html_tags.return_value = [
        {'desc': 'Red', 'start tag': '{r}', 'end tag': '{/r}',
         'start html': '<span style="-webkit-text-fill-color:red">'}
    ]
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    item = editor._color_model.item(0)
    assert item.text() == 'Red {r}'
    assert item.data(QtCore.Qt.ItemDataRole.UserRole) == '{r}'
    assert item.foreground().color() == QtGui.QColor('red')


@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_spell_text_edit_color_menu_toggle_applies_and_removes(mock_get_html_tags: MagicMock, mock_settings):
    """Clicking a color option should apply the tag when inactive and remove it when active."""
    mock_get_html_tags.return_value = [
        {'desc': 'Red', 'start tag': '{r}', 'end tag': '{/r}',
         'start html': '<span style="-webkit-text-fill-color:red">'}
    ]

    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('Hello')
    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)

    # First click — not active: wraps word.
    editor._toggle_color_tag('{r}', '{/r}')
    assert editor.toPlainText() == '{r}Hello{/r}'

    # Move cursor inside the tagged region.
    cursor = editor.textCursor()
    cursor.setPosition(len('{r}Hel'))
    editor.setTextCursor(cursor)

    # Second click — active: removes tag tokens.
    editor._toggle_color_tag('{r}', '{/r}')
    assert editor.toPlainText() == 'Hello'


@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_spell_text_edit_update_toolbar_state_checks_color_action(mock_get_html_tags: MagicMock, mock_settings):
    """The color dropdown action should become checked when the cursor is inside that color region."""
    mock_get_html_tags.return_value = [
        {'desc': 'Red', 'start tag': '{r}', 'end tag': '{/r}',
         'start html': '<span style="-webkit-text-fill-color:red">'}
    ]

    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{r}Hello{/r} world')

    cursor = editor.textCursor()
    cursor.setPosition(len('{r}He'))
    editor.setTextCursor(cursor)

    editor._update_toolbar_state()

    assert editor._custom_formatting_combo.selectedRows() == [0]

    # Move outside: should uncheck.
    cursor = editor.textCursor()
    cursor.setPosition(len('{r}Hello{/r} wo'))
    editor.setTextCursor(cursor)
    editor._update_toolbar_state()

    assert editor._custom_formatting_combo.selectedRows() == []


def test_spell_text_edit_apply_formatting_wrap_selection(mock_settings):
    """Applying formatting with selected text should wrap it with tags."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('Hello')
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == '{st}Hello{/st}'
    # Selection should be placed over the content region (not the tokens).
    result_cursor = editor.textCursor()
    assert result_cursor.selectionStart() == len('{st}')
    assert result_cursor.selectionEnd() == len('{st}Hello')


def test_spell_text_edit_apply_formatting_wrap_word_without_selection(mock_settings):
    """Applying formatting without selection should wrap the current word under cursor."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('Hello world')
    cursor = editor.textCursor()
    cursor.setPosition(1)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('it')

    assert editor.toPlainText() == '{it}Hello{/it} world'
    # Cursor should be at the same relative offset within the word content.
    # Original offset = 1, start_tag = '{it}' (length 4) → new pos = 0 + 4 + 1 = 5.
    assert editor.textCursor().position() == len('{it}H')


def test_spell_text_edit_apply_formatting_insert_without_selection_no_word(mock_settings):
    """Applying formatting without selection should insert paired tags when cursor is not on a word."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('   ')
    cursor = editor.textCursor()
    cursor.setPosition(1)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('it')

    assert editor.toPlainText() == ' {it}{/it}  '
    assert editor.textCursor().position() == len(' {it}')


def test_spell_text_edit_remove_unused_tags(mock_settings):
    """Unknown tags should be removed while known tags remain."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Known{/st} {unknown}X{/unknown}')

    editor.remove_unused_tags()

    assert editor.toPlainText() == '{st}Known{/st} X'


def test_spell_text_edit_remove_formatting_strips_tags_from_selection(mock_settings):
    """Remove formatting should strip all known formatting tags from the selected range."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Bold text{/st} and {it}italic{/it}')

    # Select the first tagged segment content only.
    cursor = editor.textCursor()
    cursor.setPosition(len('{st}'))
    cursor.setPosition(len('{st}Bold text'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor.remove_formatting()

    assert editor.toPlainText() == 'Bold text and {it}italic{/it}'


def test_spell_text_edit_remove_formatting_uses_word_when_no_selection(mock_settings):
    """Remove formatting without a selection should expand to strip adjacent tag tokens too."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Hello{/st}')

    # Place cursor inside the content word — WordUnderCursor selects 'Hello'
    cursor = editor.textCursor()
    cursor.setPosition(len('{st}Hel'))
    editor.setTextCursor(cursor)

    editor.remove_formatting()

    # Both the surrounding {st}/{/st} tokens and the word are now tag-free
    assert editor.toPlainText() == 'Hello'


def test_spell_text_edit_undo_redo_actions_track_state(mock_settings):
    """Undo and redo toolbar buttons should reflect whether edits are available."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)

    assert editor._undo_action.isEnabled() is False
    assert editor._redo_action.isEnabled() is False

    QtTest.QTest.keyClicks(editor, 'Hello')
    QtWidgets.QApplication.processEvents()

    assert editor._undo_action.isEnabled() is True
    assert editor._redo_action.isEnabled() is False

    editor.undo()
    QtWidgets.QApplication.processEvents()

    assert editor._undo_action.isEnabled() is False
    assert editor._redo_action.isEnabled() is True


def test_spell_text_edit_undo_action_reverts_text(mock_settings):
    """Clicking undo should revert the last user edit."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)

    QtTest.QTest.keyClicks(editor, 'Hello')
    QtWidgets.QApplication.processEvents()

    assert editor.toPlainText() == 'Hello'
    editor._undo_action.trigger()
    QtWidgets.QApplication.processEvents()
    assert editor.toPlainText() == ''


def test_spell_text_edit_toggle_off_formatting_preserves_content(mock_settings):
    """Toggling off formatting should remove only tokens, never the wrapped text."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Bold{/st}')

    cursor = editor.textCursor()
    cursor.setPosition(len('{st}Bo'))
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == 'Bold'


def test_spell_text_edit_toggle_off_formatting_keeps_surrounding_text(mock_settings):
    """Toggling off formatting must not remove text before or after the formatted span."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('pre {st}Bold{/st} post')

    cursor = editor.textCursor()
    cursor.setPosition(len('pre {st}Bo'))
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == 'pre Bold post'


def test_spell_text_edit_apply_formatting_across_split_marker_applies_each_section(mock_settings):
    """Applying formatting across a split marker should format each slide section independently."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('foo bar\n[---]\nbaz qux')

    cursor = editor.textCursor()
    cursor.setPosition(len('foo '))
    cursor.setPosition(len('foo bar\n[---]\nbaz'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == 'foo {st}bar{/st}\n[---]\n{st}baz{/st} qux'


def test_spell_text_edit_apply_formatting_merges_adjacent_same_tags(mock_settings):
    """Applying formatting between two identical tagged spans should merge them."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}this is a{/st} test {st}case{/st}')

    cursor = editor.textCursor()
    cursor.setPosition(len('{st}this is a{/st}'))
    cursor.setPosition(len('{st}this is a{/st} test '), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == '{st}this is a test case{/st}'


def test_spell_text_edit_clear_formatting_across_split_marker_applies_to_each_section(mock_settings):
    """Clear formatting across a split marker should only affect the selected slide sections."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('foo {st}bar{/st}\n[---]\n{st}baz{/st} qux')

    cursor = editor.textCursor()
    cursor.setPosition(len('foo '))
    cursor.setPosition(len('foo {st}bar{/st}\n[---]\n{st}baz'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor.remove_formatting()

    assert editor.toPlainText() == 'foo bar\n[---]\nbaz qux'


def test_spell_text_edit_remove_formatting_preserves_surrounding_formatting(mock_settings):
    """Clear formatting should only affect the highlighted part of a formatted span."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('pre {st}Bold text{/st} post')

    cursor = editor.textCursor()
    cursor.setPosition(len('pre {st}'))
    cursor.setPosition(len('pre {st}Bold'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor.remove_formatting()

    assert editor.toPlainText() == 'pre Bold{st} text{/st} post'


def test_spell_text_edit_remove_formatting_preserves_selection_range(mock_settings):
    """Removing formatting from a selection should keep the selection on the same text."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('aa {st}hello{/st} bb')

    cursor = editor.textCursor()
    cursor.setPosition(len('aa {st}'))
    cursor.setPosition(len('aa {st}hello'), QtGui.QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    editor.remove_formatting()

    result_cursor = editor.textCursor()
    assert editor.toPlainText() == 'aa hello bb'
    assert result_cursor.selectedText() == 'hello'
    assert result_cursor.selectionStart() == len('aa ')
    assert result_cursor.selectionEnd() == len('aa hello')


def test_spell_text_edit_remove_formatting_strips_leftover_malformed_tokens_across_sections(mock_settings):
    """Clear formatting on a cross-section selection should remove all known tokens, even malformed leftovers."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText(
        '---[Verse:1]---\n'
        '{st}Abide with me, fast{uc} falls t{it}{u}{/st}{/it}{/u}{st}he eventide;\n'
        '{r}Help of the helpless, O abide with me.{/r}{/uc}{/st}\n'
        '---[Verse:2]---\n'
        '{st}{u}{it}{u}{it}{uc}Swift to its close ebbs out life\'s little day;\n'
        'Change and decay in all {/st}{/u}{/it}{/st}{/u}{/it}around I see;\n'
        'O Thou who changest not, abide with me.{/uc}\n'
    )

    cursor = editor.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)

    editor.remove_formatting()

    result = editor.toPlainText()
    for token in editor._known_tag_tokens():
        assert token not in result
    assert '---[Verse:1]---' in result
    assert '---[Verse:2]---' in result


def test_spell_text_edit_toolbar_buttons_are_checkable(mock_settings):
    """Every toolbar formatting button should be a checkable action."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)

    for tag_token, action in editor._tag_actions.items():
        assert action.isCheckable(), f'Action for {tag_token!r} should be checkable'


def test_spell_text_edit_update_toolbar_state_checks_button_when_cursor_in_tag(mock_settings):
    """The toolbar button for a tag should become checked when the cursor is inside that tag."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Bold{/st} normal')

    # Move cursor inside the bold region
    cursor = editor.textCursor()
    cursor.setPosition(len('{st}Bo'))
    editor.setTextCursor(cursor)

    editor._update_toolbar_state()

    assert editor._tag_actions['st'].isChecked() is True
    assert editor._tag_actions['it'].isChecked() is False


def test_spell_text_edit_update_toolbar_state_unchecks_outside_tag(mock_settings):
    """The toolbar button should be unchecked when the cursor is outside any tagged region."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Bold{/st} normal')

    # Move cursor into the plain text area
    cursor = editor.textCursor()
    cursor.setPosition(len('{st}Bold{/st} nor'))
    editor.setTextCursor(cursor)

    editor._update_toolbar_state()

    assert editor._tag_actions['st'].isChecked() is False


def test_spell_text_edit_apply_formatting_by_tag_toggles_off_when_active(mock_settings):
    """Clicking a toolbar button while inside a tagged region should remove those tag tokens."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('{st}Hello{/st}')

    # Position cursor inside the bold region
    cursor = editor.textCursor()
    cursor.setPosition(len('{st}Hel'))
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == 'Hello'


def test_spell_text_edit_apply_formatting_by_tag_applies_when_not_active(mock_settings):
    """Clicking a toolbar button outside any tagged region should wrap the word in that tag."""
    editor = SpellTextEdit(None, formatting_tags_allowed=True)
    editor.setPlainText('Hello')

    # Position cursor inside the plain word
    cursor = editor.textCursor()
    cursor.setPosition(2)
    editor.setTextCursor(cursor)

    editor._apply_formatting_by_tag('st')

    assert editor.toPlainText() == '{st}Hello{/st}'


@patch('openlp.core.widgets.edits.FormattingTags.get_html_tags')
def test_custom_format_preview_and_single_command_bar(mock_tags, mock_settings, qtbot):
    """Custom styles are previewed and remain selectable beside a single overflow menu."""
    mock_tags.return_value = [
        {'desc': 'Emphasis', 'start tag': '{em}', 'end tag': '{/em}',
         'start html': '<strong><em><span style="color:blue">', 'protected': False}]
    window = QtWidgets.QMainWindow()
    editor = SpellTextEdit(window)
    window.setCentralWidget(editor)
    window.resize(1000, 600)
    editor.setPlainText('Lyrics to format')
    window.show()
    editor._custom_formatting_combo.setIsOpen(True)
    qtbot.waitUntil(lambda: any(
        view.itemDelegate().metaObject().className() == 'FormattingStyleDelegate'
        for view in window.findChildren(QtWidgets.QAbstractItemView)))
    try:
        assert len(editor._toolbar.findChildren(fluentqt.CommandBar)) == 1
        item = editor._color_model.item(0)
        assert item.text() == 'Emphasis {em}'
        assert item.font().bold() and item.font().italic()
        assert item.foreground().color() == QtGui.QColor('blue')
        view = window.findChild(QtWidgets.QAbstractItemView, 'MultiSelectComboBox.ListView')
        qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                         pos=view.visualRect(view.model().index(0, 0)).center())
        assert editor._custom_formatting_combo.selectedRows() == [0]
        assert '{em}' in editor.toPlainText()
        # Focus and selection must preserve the blue style preview.
        option = QtWidgets.QStyleOptionViewItem()
        option.rect = QtCore.QRect(0, 0, 300, 40)
        option.widget = view
        option.palette = view.palette()
        option.state = (QtWidgets.QStyle.StateFlag.State_Enabled | QtWidgets.QStyle.StateFlag.State_Selected |
                        QtWidgets.QStyle.StateFlag.State_HasFocus)
        preview = QtGui.QPixmap(300, 40)
        preview.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(preview)
        view.itemDelegate().paint(painter, option, view.model().index(0, 0))
        painter.end()
        image = preview.toImage()
        assert any(image.pixelColor(x, y).blue() > 220 and image.pixelColor(x, y).red() < 60
                   for x in range(44, 200) for y in range(40))
        editor._mode_switch.setIsOn(True)
        assert editor.rich_text_mode is False
        assert '{em}' in editor.toPlainText()
        editor._custom_formatting_combo.setIsOpen(False)
        editor._mode_switch.setIsOn(False)
    finally:
        window.close()


@pytest.mark.parametrize('width', [650, 1000])
def test_formatting_header_spans_row_above_scrollbar(mock_settings, qtbot, width):
    """The full header has a continuous surface, trailing padding and no scrollbar beside it."""
    window = QtWidgets.QMainWindow()
    editor = SpellTextEdit(window)
    window.setCentralWidget(editor)
    window.resize(width, 500)
    editor.setPlainText('\n'.join(f'Line {row}' for row in range(100)))
    window.show()
    qtbot.waitUntil(lambda: editor.verticalScrollBar().isVisible())
    try:
        header = editor._toolbar
        scrollbar_top = editor.verticalScrollBar().mapTo(editor, QtCore.QPoint()).y()
        assert header.geometry().right() == editor.contentsRect().right()
        assert scrollbar_top > header.geometry().bottom()
        switch_left = editor._mode_switch.mapTo(header, QtCore.QPoint()).x()
        switch_right = switch_left + editor._mode_switch.width()
        assert switch_right <= header.width() - 12
        assert switch_left - editor._custom_formatting_combo.geometry().right() >= 12
        window.resize(width - 100, 400)
        QtWidgets.QApplication.processEvents()
        assert header.geometry().right() == editor.contentsRect().right()
        assert editor.verticalScrollBar().mapTo(editor, QtCore.QPoint()).y() > header.geometry().bottom()
    finally:
        window.close()
