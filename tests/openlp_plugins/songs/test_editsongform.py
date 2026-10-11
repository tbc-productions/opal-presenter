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
This module contains tests for the lib submodule of the Songs plugin.
"""
import logging
import pytest
from unittest.mock import MagicMock, patch
from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.plugins.songs.forms.editsongform import EditSongForm
from openlp.plugins.songs.lib import VerseType
from openlp.plugins.songs.lib.db import Author
from openlp.plugins.songs.lib.sectioncolors import DEFAULT_SECTION_COLORS


@pytest.fixture
def edit_song_form(settings: Settings):
    Registry().register("service_list", MagicMock())
    with patch('openlp.plugins.songs.forms.editsongform.EditSongForm.__init__', return_value=None):
        return EditSongForm(None, MagicMock(), MagicMock())


@pytest.fixture
def edit_song_form_with_ui(settings: Settings) -> EditSongForm:
    main_window = QtWidgets.QMainWindow()
    Registry().register('service_list', MagicMock())
    Registry().register('main_window', main_window)
    Registry().register('theme_manager', MagicMock())
    form = EditSongForm(None, main_window, MagicMock())
    yield form
    del form
    del main_window


def test_validate_matching_tags(edit_song_form):
    # Given a set of tags
    tags = ['{r}', '{/r}', '{bl}', '{/bl}', '{su}', '{/su}']

    # WHEN we validate them
    valid = edit_song_form._validate_tags(tags)

    # THEN they should be valid
    assert valid is True, "The tags list should be valid"


def test_validate_nonmatching_tags(edit_song_form):
    # Given a set of tags
    tags = ['{r}', '{/r}', '{bl}', '{/bl}', '{br}', '{su}', '{/su}']

    # WHEN we validate them
    valid = edit_song_form._validate_tags(tags)

    # THEN they should be valid
    assert valid is True, "The tags list should be valid"


@patch('openlp.plugins.songs.forms.editsongform.set_case_insensitive_completer')
def test_load_objects(mocked_set_case_insensitive_completer, edit_song_form, settings):
    """
    Test the _load_objects() method
    """
    # GIVEN: A song edit form and some mocked stuff
    mocked_class = MagicMock()
    mocked_class.name = 'Author'
    mocked_combo = MagicMock()
    mocked_combo.count.return_value = 0
    mocked_cache = MagicMock()
    mocked_object = MagicMock()
    mocked_object.name = 'Charles'
    mocked_object.id = 1
    mocked_manager = MagicMock()
    mocked_manager.get_all_objects.return_value = [mocked_object]
    edit_song_form.manager = mocked_manager

    # WHEN: _load_objects() is called
    edit_song_form._load_objects(mocked_class, mocked_combo, mocked_cache)

    # THEN: All the correct methods should have been called
    edit_song_form.manager.get_all_objects.assert_called_once_with(mocked_class)
    mocked_combo.clear.assert_called_once_with()
    mocked_combo.count.assert_called_once_with()
    mocked_combo.addItem.assert_called_once_with('Charles')
    mocked_cache.append.assert_called_once_with('Charles')
    mocked_combo.setItemData.assert_called_once_with(0, 1)
    mocked_set_case_insensitive_completer.assert_called_once_with(mocked_cache, mocked_combo)
    mocked_combo.setCurrentIndex.assert_called_once_with(-1)
    mocked_combo.setCurrentText.assert_called_once_with('')


@patch('openlp.plugins.songs.forms.editsongform.critical_error_message_box')
def test_add_multiple_audio_from_file(mocked_error_message, edit_song_form_with_ui: EditSongForm):
    """
    Test that not more than one Linked Audio item can be added
    """
    # GIVEN: A Linked Audio list with 1 item and mocked error message handler
    item = QtWidgets.QListWidgetItem('Audio file')
    edit_song_form_with_ui.audio_list_widget.addItem(item)

    # WHEN: Add File is clicked
    edit_song_form_with_ui.on_audio_add_from_file_button_clicked()

    # THEN: A call to show an error message should have been made and no items should have been added
    mocked_error_message.assert_called_once()
    assert edit_song_form_with_ui.audio_list_widget.count() == 1


@patch('openlp.plugins.songs.forms.editsongform.critical_error_message_box')
def test_add_multiple_audio_from_media(mocked_error_message, edit_song_form_with_ui: EditSongForm):
    """
    Test that not more than one Linked Audio item can be added
    """
    # GIVEN: A Linked Audio list with 1 item and mocked error message handler
    item = QtWidgets.QListWidgetItem('Audio file')
    edit_song_form_with_ui.audio_list_widget.addItem(item)

    # WHEN: Add Media is clicked
    edit_song_form_with_ui.on_audio_add_from_media_button_clicked()

    # THEN: A call to show an error message should have been made and no items should have been added
    mocked_error_message.assert_called_once()
    assert edit_song_form_with_ui.audio_list_widget.count() == 1


@patch('openlp.plugins.songs.forms.editsongform.critical_error_message_box')
def test_validate_song_multiple_audio(mocked_error_message, edit_song_form_with_ui: EditSongForm):
    """
    Test that a form with multiple Linked Audio items does not pass validation
    """
    # GIVEN: A form with title, lyrics, an author, and 2 Linked Audio items
    edit_song_form_with_ui.title_edit.setText('Song Title')
    verse_def = '{tag}{number}'.format(tag=VerseType.tags[0], number=1)
    song_lyrics = 'Song Lyrics'
    verse_item = QtWidgets.QTableWidgetItem(song_lyrics)
    verse_item.setData(QtCore.Qt.UserRole, verse_def)
    verse_item.setText(song_lyrics)
    edit_song_form_with_ui.verse_list_widget.setRowCount(1)
    edit_song_form_with_ui.verse_list_widget.setItem(0, 0, verse_item)
    item_1 = QtWidgets.QListWidgetItem('Audio file 1')
    item_2 = QtWidgets.QListWidgetItem('Audio file 2')
    edit_song_form_with_ui.audio_list_widget.addItem(item_1)
    edit_song_form_with_ui.audio_list_widget.addItem(item_2)
    author = Author(first_name='', last_name='', display_name='Author')
    author_type = edit_song_form_with_ui.author_types_combo_box.itemData(0)
    edit_song_form_with_ui._add_author_to_list(author, author_type)

    # WHEN: Song is validated
    song_valid = edit_song_form_with_ui._validate_song()

    # THEN: It should not be valid
    assert song_valid is False


@patch('openlp.plugins.songs.forms.editsongform.critical_error_message_box')
def test_validate_song_one_audio(mocked_error_message, edit_song_form_with_ui: EditSongForm):
    """
    Test that a form with one Linked Audio item passes validation
    """
    # GIVEN: A form with title, lyrics, an author, and 1 Linked Audio item
    edit_song_form_with_ui.title_edit.setText('Song Title')
    verse_def = '{tag}{number}'.format(tag=VerseType.tags[0], number=1)
    song_lyrics = 'Song Lyrics'
    verse_item = QtWidgets.QTableWidgetItem(song_lyrics)
    verse_item.setData(QtCore.Qt.UserRole, verse_def)
    verse_item.setText(song_lyrics)
    edit_song_form_with_ui.verse_list_widget.setRowCount(1)
    edit_song_form_with_ui.verse_list_widget.setItem(0, 0, verse_item)
    item_1 = QtWidgets.QListWidgetItem('Audio file 1')
    edit_song_form_with_ui.audio_list_widget.addItem(item_1)
    author = Author(first_name='', last_name='', display_name='Author')
    author_type = edit_song_form_with_ui.author_types_combo_box.itemData(0)
    edit_song_form_with_ui._add_author_to_list(author, author_type)
    # If the validation does fail for some reason it will likely try to display an error message,
    # so make sure error_message exists to avoid an error

    # WHEN: Song is validated
    song_valid = edit_song_form_with_ui._validate_song()

    # Log the error message to help determine the cause in the case validation failed
    if mocked_error_message.called:
        message = mocked_error_message.call_args.kwargs['message']
        logging.error('Validation error message: {message}'.format(message=message))

    # THEN: It should be valid
    assert song_valid is True


def test_edit_all_parses_pasted_section_headings(edit_song_form_with_ui: EditSongForm, settings: Settings):
    """Plain headings in a pasted song become separate, correctly tagged slides."""
    settings.extend_default_settings({'songs/section color {key}'.format(key=key): color
                                      for key, color in DEFAULT_SECTION_COLORS.items()})
    settings.extend_default_settings({'songs/section background opacity minimum': 10,
                                      'songs/section background opacity maximum': 60})
    form = edit_song_form_with_ui
    lyrics = ('Verse 1\nFirst verse\n\nChorus 1\nFirst chorus\n\n'
              'Ending\nFinal line\n\nChorus 2\nSecond chorus\n\n'
              'Bridge\nBridge line\n\nVerse 4\nFourth verse')

    def paste_lyrics():
        clipboard = QtCore.QMimeData()
        clipboard.setText(lyrics)
        form.verse_form.verse_text_edit.insertFromMimeData(clipboard)
        assert form.verse_form.verse_text_edit.toPlainText().startswith('---[Verse:1]---\nFirst verse')
        assert '---[Chorus:2]---\nSecond chorus' in form.verse_form.verse_text_edit.toPlainText()
        return 1

    with patch.object(form.verse_form, 'exec', side_effect=paste_lyrics):
        form.on_verse_edit_all_button_clicked()

    assert [(form.verse_list_widget.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole),
             form.verse_list_widget.item(row, 0).text())
            for row in range(form.verse_list_widget.rowCount())] == [
                ('v1', 'First verse'), ('c1', 'First chorus'), ('e1', 'Final line'),
                ('c2', 'Second chorus'), ('b1', 'Bridge line'), ('v4', 'Fourth verse')]
