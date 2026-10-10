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
Package to test the openlp.plugins.bibles.forms.bibleimportform package.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtTest, QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.registry import Registry
from openlp.core.common.settings import Settings
from openlp.plugins.bibles.forms.bibleimportform import BibleImportForm, PYSWORD_AVAILABLE


@pytest.fixture
def import_form(registry: Registry, settings: Settings) -> BibleImportForm:
    registry.register('main_window', MagicMock())
    yield BibleImportForm(None, MagicMock(), MagicMock())


@patch('openlp.plugins.bibles.forms.bibleimportform.CWExtract.get_bibles_from_http')
@patch('openlp.plugins.bibles.forms.bibleimportform.BGExtract.get_bibles_from_http')
@patch('openlp.plugins.bibles.forms.bibleimportform.BSExtract.get_bibles_from_http')
def test_on_web_update_button_clicked(mocked_bsextract: MagicMock, mocked_bgextract: MagicMock,
                                      mocked_cwextract: MagicMock, import_form: BibleImportForm):
    """
    Test that on_web_update_button_clicked handles problems correctly
    """
    # GIVEN: Some mocked GUI components and mocked bibleextractors
    with patch('openlp.plugins.bibles.forms.bibleimportform.critical_error_message_box'):
        mocked_bsextract.return_value = None
        mocked_bgextract.return_value = None
        mocked_cwextract.return_value = None

        # WHEN: Running on_web_update_button_clicked
        import_form.on_web_update_button_clicked()

    # THEN: The webbible list should still be empty
    assert import_form.web_bible_list == {}, 'The webbible list should be empty'


def test_custom_init(import_form: BibleImportForm):
    """
    Test that custom_init works as expected if pysword is unavailable
    """
    # GIVEN: A mocked sword_tab_widget
    with patch.object(import_form, 'sword_tab_widget') as mocked_tab_widget:

        # WHEN: Running custom_init
        import_form.custom_init()

    # THEN: sword_tab_widget.setDisabled(True) should have been called
    if not PYSWORD_AVAILABLE:
        mocked_tab_widget.setDisabled.assert_called_with(True)
    else:
        mocked_tab_widget.setDisabled.assert_not_called()


def test_help(import_form: BibleImportForm):
    """
    Test the help button
    """
    # WHEN: The Help button is clicked
    with patch.object(import_form, 'provide_help') as mocked_help:
        QtTest.QTest.mouseClick(import_form.button(QtWidgets.QWizard.WizardButton.HelpButton),
                                QtCore.Qt.MouseButton.LeftButton)

    # THEN: The Help function should be called
    mocked_help.assert_called_once()


@pytest.mark.parametrize('result', [None, {}, {1: ''}, {1: '   '}])
def test_web_download_rejects_empty_chapter(import_form, result):
    """Even a listed translation with books must return actual verse text."""
    from openlp.plugins.bibles.lib import SearchResults
    import_form.web_bible_list = {0: {'King James Version': ('kjv', 'en')}}
    import_form.web_translation_combo_box.addItem('King James Version')
    chapter = SearchResults('Genesis', 1, result) if result is not None else None
    with patch('openlp.plugins.bibles.forms.bibleimportform.CWExtract') as extractor, \
            patch('openlp.plugins.bibles.forms.bibleimportform.critical_error_message_box') as error:
        extractor.return_value.get_books_from_http.return_value = ['Genesis']
        extractor.return_value.get_bible_chapter.return_value = chapter
        assert not import_form.validate_web_download()
        error.assert_called_once()


def test_web_download_validates_selected_translation(import_form):
    from openlp.plugins.bibles.lib import SearchResults
    import_form.web_bible_list = {1: {'King James Version': ('KJV', 'en')}}
    import_form.web_source_combo_box.setCurrentIndex(1)
    import_form.web_translation_combo_box.addItem('King James Version')
    with patch('openlp.plugins.bibles.forms.bibleimportform.BGExtract') as extractor:
        extractor.return_value.get_books_from_http.return_value = ['Genesis']
        extractor.return_value.get_bible_chapter.return_value = SearchResults('Genesis', 1, {1: 'In the beginning'})
        assert import_form.validate_web_download()
        extractor.return_value.get_books_from_http.assert_called_once_with('KJV')
        extractor.return_value.get_bible_chapter.assert_called_once_with('KJV', 'Genesis', 1)


@pytest.mark.parametrize('books', [None, [], ValueError('Website changed'), ConnectionError('Offline')])
def test_web_download_handles_failed_books(import_form, books):
    import_form.web_bible_list = {0: {'King James Version': ('kjv', 'en')}}
    import_form.web_translation_combo_box.addItem('King James Version')
    with patch('openlp.plugins.bibles.forms.bibleimportform.CWExtract') as extractor, \
            patch('openlp.plugins.bibles.forms.bibleimportform.critical_error_message_box') as error:
        if isinstance(books, Exception):
            extractor.return_value.get_books_from_http.side_effect = books
        else:
            extractor.return_value.get_books_from_http.return_value = books
        assert not import_form.validate_web_download()
        extractor.return_value.get_bible_chapter.assert_not_called()
        error.assert_called_once()


def test_web_lists_disable_unavailable_sources(import_form):
    with patch('openlp.plugins.bibles.forms.bibleimportform.CWExtract') as crosswalk, \
            patch('openlp.plugins.bibles.forms.bibleimportform.BGExtract') as gateway, \
            patch('openlp.plugins.bibles.forms.bibleimportform.BSExtract') as server:
        crosswalk.return_value.get_bibles_from_http.return_value = []
        gateway.return_value.get_bibles_from_http.return_value = [('King James Version', 'KJV', 'en')]
        server.return_value.get_bibles_from_http.return_value = []
        import_form.on_web_update_button_clicked()
    assert not import_form.web_source_combo_box.model().item(0).isEnabled()
    assert import_form.web_source_combo_box.model().item(1).isEnabled()
    assert not import_form.web_source_combo_box.model().item(2).isEnabled()
    assert import_form.web_source_combo_box.currentIndex() == 1
    assert import_form.web_translation_combo_box.currentText() == 'King James Version'
    assert import_form.web_update_button.isEnabled()
