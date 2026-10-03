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
Package to test the openlp.plugins.songs.forms.editsongform package.
"""
import pytest
from unittest.mock import MagicMock, patch

from PySide6 import QtTest, QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import UiStrings
from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.plugins.songs.forms.editsongform import EditSongForm
from openlp.plugins.songs.lib.db import Author
from openlp.plugins.songs.lib.ui import SongStrings


@pytest.fixture()
def form(settings: Settings):
    main_window = QtWidgets.QMainWindow()
    Registry().register('main_window', main_window)
    Registry().register('theme_manager', MagicMock())
    frm = EditSongForm(MagicMock(), main_window, MagicMock())
    yield frm
    del frm
    del main_window


def test_ui_defaults(form: EditSongForm):
    """
    Test that the EditSongForm defaults are correct
    """
    assert form.verse_edit_button.isEnabled() is False, 'The verse edit button should not be enabled'
    assert form.verse_delete_button.isEnabled() is False, 'The verse delete button should not be enabled'
    assert form.author_remove_button.isEnabled() is False, 'The author remove button should not be enabled'
    assert form.topic_remove_button.isEnabled() is False, 'The topic remove button should not be enabled'


def test_song_editor_exec_opens_and_closes(form: EditSongForm):
    """The Song Editor should open through the Fluent dialog sizing lifecycle."""
    parent = form.parentWidget()
    parent.resize(1200, 900)
    parent.show()
    form.setAnimationEnabled(False)
    observed = []

    def dismiss():
        observed.append(form.isVisible() and form.isOpen())
        form.reject()

    QtCore.QTimer.singleShot(0, dismiss)
    try:
        assert form.exec() == QtWidgets.QDialog.DialogCode.Rejected
        assert observed == [True]
    finally:
        parent.close()


def test_verse_order_no_warning(form: EditSongForm):
    """
    Test if the verse order warning is not shown
    """
    # GIVEN: Mocked methods.
    given_verse_order = 'V1 V2'
    form.verse_list_widget.rowCount = MagicMock(return_value=2)
    # Mock out the verse.
    first_verse = MagicMock()
    first_verse.data.return_value = 'V1'
    second_verse = MagicMock()
    second_verse.data.return_value = 'V2'
    form.verse_list_widget.item = MagicMock(side_effect=[first_verse, second_verse])
    form._extract_verse_order = MagicMock(return_value=given_verse_order.split())

    # WHEN: Call the method.
    form.on_verse_order_text_changed(given_verse_order)

    # THEN: No text should be shown.
    assert form.warning_label.text() == '', 'There should be no warning.'


def test_verse_order_incomplete_warning(form: EditSongForm):
    """
    Test if the verse-order-incomple warning is shown
    """
    # GIVEN: Mocked methods.
    given_verse_order = 'V1'
    form.verse_list_widget.rowCount = MagicMock(return_value=2)
    # Mock out the verse.
    first_verse = MagicMock()
    first_verse.data.return_value = 'V1'
    second_verse = MagicMock()
    second_verse.data.return_value = 'V2'
    form.verse_list_widget.item = MagicMock(side_effect=[first_verse, second_verse])
    form._extract_verse_order = MagicMock(return_value=[given_verse_order])

    # WHEN: Call the method.
    form.on_verse_order_text_changed(given_verse_order)

    # THEN: The verse-order-incomplete text should be shown.
    assert form.warning_label.text() == form.not_all_verses_used_warning, \
        'The verse-order-incomplete warning should be shown.'


def test_bug_1170435(form: EditSongForm):
    """
    Regression test for bug 1170435 (test if "no verse order" message is shown)
    """
    # GIVEN: Mocked methods.
    given_verse_order = ''
    form.verse_list_widget.rowCount = MagicMock(return_value=1)
    # Mock out the verse. (We want a verse type to be returned).
    mocked_verse = MagicMock()
    mocked_verse.data.return_value = 'V1'
    form.verse_list_widget.item = MagicMock(return_value=mocked_verse)
    form._extract_verse_order = MagicMock(return_value=[])
    form.verse_order_edit.text = MagicMock(return_value=given_verse_order)
    # WHEN: Call the method.
    form.on_verse_order_text_changed(given_verse_order)

    # THEN: The no-verse-order message should be shown.
    assert form.warning_label.text() == form.no_verse_order_entered_warning,  \
        'The no-verse-order message should be shown.'


def test_bug_1404967(form: EditSongForm):
    """
    Test for CCLI label showing correct text
    """
    # GIVEN; Mocked methods
    # THEN: CCLI label should be CCLI song label
    assert form.ccli_label.text() is not UiStrings().CCLINumberLabel, \
        'CCLI label should not be "{}"'.format(UiStrings().CCLINumberLabel)
    assert form.ccli_label.text() == UiStrings().CCLISongNumberLabel, \
        'CCLI label text should be "{}"'.format(UiStrings().CCLISongNumberLabel)


def test_copyright_edit_is_fixed_three_lines_with_scrollbar(form: EditSongForm):
    """The copyright editor should be a fixed 3-line height with a scrollbar as needed."""
    line_spacing = QtGui.QFontMetrics(form.copyright_edit.font()).lineSpacing()
    margins = form.copyright_edit.contentsMargins()
    chrome = form.copyright_edit.frameWidth() * 2 + margins.top() + margins.bottom()
    expected_height = line_spacing * 3 + chrome

    assert isinstance(form.copyright_edit, QtWidgets.QTextEdit)
    assert form.copyright_edit.acceptRichText() is False
    assert form.copyright_edit.lineWrapMode() == QtWidgets.QTextEdit.LineWrapMode.WidgetWidth
    assert form.copyright_edit.height() == expected_height
    assert form.copyright_edit.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded


def test_on_copyright_insert_button_triggered_inserts_symbol_at_cursor(form: EditSongForm):
    """The copyright insert button should insert the symbol at the current cursor position."""
    form.copyright_edit.setPlainText('Hello World')
    cursor = form.copyright_edit.textCursor()
    cursor.setPosition(len('Hello '))
    form.copyright_edit.setTextCursor(cursor)

    form.on_copyright_insert_button_triggered()

    assert form.copyright_edit.toPlainText() == 'Hello ' + SongStrings().CopyrightSymbol + 'World'


def test_copyright_edit_replaces_newlines_with_spaces(form: EditSongForm):
    """Copyright input should wrap visually without storing newline characters."""
    form.copyright_edit.setPlainText('Line one\nLine two\r\nLine three')

    assert form.copyright_edit.toPlainText() == 'Line one Line two Line three'


def test_copyright_edit_ignores_return_key(form: EditSongForm):
    """Pressing return in the copyright editor should not insert a newline."""
    form.copyright_edit.setFocus()
    form.copyright_edit.setPlainText('Copyright')

    QtTest.QTest.keyClick(form.copyright_edit, QtCore.Qt.Key.Key_Return)

    assert form.copyright_edit.toPlainText() == 'Copyright'


def test_verse_order_lowercase(form: EditSongForm):
    """
    Test that entering a verse order in lowercase automatically converts to uppercase
    """
    # GIVEN; Mocked methods

    # WHEN: We enter a verse order in lowercase
    form.verse_order_edit.setText('v1 v2 c1 v3 c1 v4 c1')
    # Need to manually trigger this method as it is only triggered by manual input
    form.on_verse_order_text_changed(form.verse_order_edit.text())

    # THEN: The verse order should be converted to uppercase
    assert form.verse_order_edit.text() == 'V1 V2 C1 V3 C1 V4 C1'


def test_help(settings: Settings):
    """
    Test the help button
    """
    # GIVEN: An edit song form and a patched help function
    main_window = QtWidgets.QMainWindow()
    Registry().register('main_window', main_window)
    Registry().register('theme_manager', MagicMock())
    edit_song_form = EditSongForm(MagicMock(), main_window, MagicMock())

    # WHEN: The Help button is clicked
    with patch.object(edit_song_form, 'provide_help') as mocked_help:
        QtTest.QTest.mouseClick(edit_song_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Help),
                                QtCore.Qt.MouseButton.LeftButton)

    # THEN: The Help function should be called
    mocked_help.assert_called_once()


@patch('openlp.plugins.songs.forms.editsongform.QtWidgets.QMessageBox.question')
def test_on_author_add_button_clicked_adds_multiple_authors_from_delimited_text(mocked_question, form: EditSongForm):
    """Delimited author text should prompt once, create missing authors, and avoid duplicates."""
    existing_author = Author(first_name='John', last_name='Newton', display_name='John Newton')
    existing_author.id = 1
    authors = [existing_author]

    def save_object_side_effect(author):
        author.id = len(authors) + 1
        authors.append(author)
        return True

    form.manager.get_all_objects.side_effect = lambda cls: list(authors) if cls is Author else []
    form.manager.save_object.side_effect = save_object_side_effect
    mocked_question.return_value = QtWidgets.QMessageBox.StandardButton.Yes

    form.load_authors()
    form.authors_combo_box.setCurrentText(' John Newton ;  Jane Doe | John Newton ')

    form.on_author_add_button_clicked()

    assert mocked_question.call_count == 1
    message = mocked_question.call_args.args[2]
    assert 'John Newton' in message
    assert 'Jane Doe (New)' in message
    assert len(authors) == 2
    assert authors[1].display_name == 'Jane Doe'
    assert form.authors_list_view.count() == 2
    assert form.authors_list_view.item(0).text() == 'John Newton'
    assert form.authors_list_view.item(1).text() == 'Jane Doe'


@patch('openlp.plugins.songs.forms.editsongform.QtWidgets.QMessageBox.question')
def test_on_author_add_button_clicked_adds_multiple_authors_from_comma_delimited_text(mocked_question,
                                                                                      form: EditSongForm):
    """Comma-delimited author text should be handled by the multi-author add flow."""
    existing_author = Author(first_name='John', last_name='Newton', display_name='John Newton')
    existing_author.id = 1
    authors = [existing_author]

    def save_object_side_effect(author):
        author.id = len(authors) + 1
        authors.append(author)
        return True

    form.manager.get_all_objects.side_effect = lambda cls: list(authors) if cls is Author else []
    form.manager.save_object.side_effect = save_object_side_effect
    mocked_question.return_value = QtWidgets.QMessageBox.StandardButton.Yes

    form.load_authors()
    form.authors_combo_box.setCurrentText('John Newton, Jane Doe')

    form.on_author_add_button_clicked()

    assert mocked_question.call_count == 1
    assert len(authors) == 2
    assert authors[1].display_name == 'Jane Doe'
    assert form.authors_list_view.count() == 2


@patch('openlp.plugins.songs.forms.editsongform.QtWidgets.QMessageBox.question')
def test_on_author_add_button_clicked_declined_multiple_authors_does_not_add(mocked_question, form: EditSongForm):
    """Declining the multi-author prompt should fall back to adding the full text as one author."""
    existing_author = Author(first_name='John', last_name='Newton', display_name='John Newton')
    existing_author.id = 1
    form.manager.get_all_objects.side_effect = lambda cls: [existing_author] if cls is Author else []
    mocked_question.side_effect = [
        QtWidgets.QMessageBox.StandardButton.No,
        QtWidgets.QMessageBox.StandardButton.Yes,
    ]

    def save_object_side_effect(author):
        author.id = 2
        return True

    form.manager.save_object.side_effect = save_object_side_effect

    form.load_authors()
    form.authors_combo_box.setCurrentText('John Newton; Jane Doe')

    form.on_author_add_button_clicked()

    assert form.authors_list_view.count() == 1
    assert form.authors_list_view.item(0).text() == 'John Newton; Jane Doe'
    form.manager.save_object.assert_called_once()
