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
Package to test the opal.plugins.bibles.forms.bibleimportform package.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.registry import Registry
from opal.core.common.settings import Settings
from opal.plugins.bibles.forms.bibleimportform import BibleImportForm, PYSWORD_AVAILABLE


@pytest.fixture
def import_form(registry: Registry, settings: Settings) -> BibleImportForm:
    registry.register('main_window', MagicMock())
    yield BibleImportForm(None, MagicMock(), MagicMock())


@patch('opal.plugins.bibles.forms.bibleimportform.CWExtract.get_bibles_from_http')
@patch('opal.plugins.bibles.forms.bibleimportform.BGExtract.get_bibles_from_http')
@patch('opal.plugins.bibles.forms.bibleimportform.BSExtract.get_bibles_from_http')
def test_on_web_update_button_clicked(mocked_bsextract: MagicMock, mocked_bgextract: MagicMock,
                                      mocked_cwextract: MagicMock, import_form: BibleImportForm):
    """
    Test that on_web_update_button_clicked handles problems correctly
    """
    # GIVEN: Some mocked GUI components and mocked bibleextractors
    with patch('opal.plugins.bibles.forms.bibleimportform.critical_error_message_box'):
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


def test_no_help_button(import_form: BibleImportForm):
    assert not import_form.testOption(QtWidgets.QWizard.WizardOption.HaveHelpButton)
    assert not import_form.button(QtWidgets.QWizard.WizardButton.HelpButton).isVisible()


@pytest.mark.parametrize('result', [None, {}, {1: ''}, {1: '   '}])
def test_web_download_rejects_empty_chapter(import_form, result):
    """Even a listed translation with books must return actual verse text."""
    from opal.plugins.bibles.lib import SearchResults
    import_form.web_bible_list = {0: {'King James Version': ('kjv', 'en')}}
    import_form.web_translation_combo_box.addItem('King James Version')
    chapter = SearchResults('Genesis', 1, result) if result is not None else None
    with patch('opal.plugins.bibles.forms.bibleimportform.CWExtract') as extractor, \
            patch('opal.plugins.bibles.forms.bibleimportform.critical_error_message_box') as error:
        extractor.return_value.get_books_from_http.return_value = ['Genesis']
        extractor.return_value.get_bible_chapter.return_value = chapter
        assert not import_form.validate_web_download()
        error.assert_called_once()


def test_web_download_validates_selected_translation(import_form):
    from opal.plugins.bibles.lib import SearchResults
    import_form.web_bible_list = {1: {'King James Version': ('KJV', 'en')}}
    import_form.web_source_combo_box.setCurrentIndex(1)
    import_form.web_translation_combo_box.addItem('King James Version')
    with patch('opal.plugins.bibles.forms.bibleimportform.BGExtract') as extractor:
        extractor.return_value.get_books_from_http.return_value = ['Genesis']
        extractor.return_value.get_bible_chapter.return_value = SearchResults('Genesis', 1, {1: 'In the beginning'})
        assert import_form.validate_web_download()
        extractor.return_value.get_books_from_http.assert_called_once_with('KJV')
        extractor.return_value.get_bible_chapter.assert_called_once_with('KJV', 'Genesis', 1)


@pytest.mark.parametrize('books', [None, [], ValueError('Website changed'), ConnectionError('Offline')])
def test_web_download_handles_failed_books(import_form, books):
    import_form.web_bible_list = {0: {'King James Version': ('kjv', 'en')}}
    import_form.web_translation_combo_box.addItem('King James Version')
    with patch('opal.plugins.bibles.forms.bibleimportform.CWExtract') as extractor, \
            patch('opal.plugins.bibles.forms.bibleimportform.critical_error_message_box') as error:
        if isinstance(books, Exception):
            extractor.return_value.get_books_from_http.side_effect = books
        else:
            extractor.return_value.get_books_from_http.return_value = books
        assert not import_form.validate_web_download()
        extractor.return_value.get_bible_chapter.assert_not_called()
        error.assert_called_once()


def test_web_lists_disable_unavailable_sources(import_form):
    with patch('opal.plugins.bibles.forms.bibleimportform.CWExtract') as crosswalk, \
            patch('opal.plugins.bibles.forms.bibleimportform.BGExtract') as gateway, \
            patch('opal.plugins.bibles.forms.bibleimportform.BSExtract') as server:
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
    assert import_form.web_source_combo_box.itemText(0) == 'Crosswalk - unavailable'
    assert import_form.web_source_combo_box.itemText(1) == 'BibleGateway'
    assert import_form.web_source_combo_box.itemText(2) == 'BibleServer - unavailable'
    # A later successful refresh restores the labels and enables every source.
    with patch('opal.plugins.bibles.forms.bibleimportform.CWExtract') as crosswalk, \
            patch('opal.plugins.bibles.forms.bibleimportform.BGExtract') as gateway, \
            patch('opal.plugins.bibles.forms.bibleimportform.BSExtract') as server:
        for extractor in (crosswalk, gateway, server):
            extractor.return_value.get_bibles_from_http.return_value = [('King James Version', 'KJV', 'en')]
        import_form.on_web_update_button_clicked()
    for index, name in enumerate(('Crosswalk', 'BibleGateway', 'BibleServer')):
        assert import_form.web_source_combo_box.itemText(index) == name
        assert import_form.web_source_combo_box.model().item(index).isEnabled()


def test_source_fields_align_and_match_button_heights(import_form, qtbot):
    from opal.plugins.bibles.lib.manager import BibleFormat
    qtbot.addWidget(import_form)
    import_form.show()
    import_form.next()
    import_form.format_combo_box.setCurrentIndex(BibleFormat.WebDownload)
    QtWidgets.QApplication.processEvents()
    page = import_form.select_page
    labels = (import_form.format_label, import_form.web_update_label,
              import_form.web_source_label, import_form.web_translation_label)
    assert len({label.mapTo(page, QtCore.QPoint()).x() for label in labels}) == 1
    fields = (import_form.format_combo_box, import_form.web_update_button,
              import_form.web_source_combo_box, import_form.web_translation_combo_box)
    assert len({field.mapTo(page, QtCore.QPoint()).x() for field in fields}) == 1
    assert len({field.height() for field in fields}) == 1
    assert import_form.web_update_button.width() < import_form.web_source_combo_box.width()
    assert not import_form.web_update_button.icon().isNull()
    assert import_form.web_update_button.text() == 'Retrieve translations'
    assert import_form.web_update_button.fluentStyle() == QtWidgets.QPushButton().fluentStyle()
    assert import_form.web_progress_spinner.isIndeterminate()
    assert import_form.web_progress_spinner.isHidden()
    import_form.format_combo_box.setCurrentIndex(BibleFormat.OSIS)
    QtWidgets.QApplication.processEvents()
    path_edit = import_form.osis_path_edit
    assert path_edit.line_edit.height() == path_edit.browse_button.height()


def test_license_error_is_modal_over_wizard_and_blocks_repeat_next(import_form, qtbot):
    from PySide6 import QtTest
    qtbot.addWidget(import_form)
    import_form.setStartId(import_form.pageIds()[2])
    import_form.restart()
    import_form.show()
    QtWidgets.QApplication.processEvents()
    import_form.version_name_edit.setText('NIV')
    next_button = import_form.button(import_form.WizardButton.NextButton)
    observed = {}

    def inspect_prompt():
        prompts = import_form.findChildren(QtWidgets.QMessageBox)
        observed['count'] = len(prompts)
        if not prompts:
            return
        prompt = prompts[0]
        observed['host'] = prompt.parentWidget()
        observed['modal'] = prompt.isModal()
        observed['disabled'] = not next_button.isEnabled()
        for _ in range(3):
            QtTest.QTest.mouseClick(next_button, QtCore.Qt.MouseButton.LeftButton)
        QtTest.QTest.keyClick(import_form, QtCore.Qt.Key.Key_Return)
        observed['after_clicks'] = len(import_form.findChildren(QtWidgets.QMessageBox))
        prompt.button(QtWidgets.QMessageBox.StandardButton.Ok).click()

    QtCore.QTimer.singleShot(100, inspect_prompt)
    next_button.click()
    assert observed == {'count': 1, 'host': import_form, 'modal': True, 'disabled': True, 'after_clicks': 1}
    assert import_form.currentPage() is import_form.license_details_page
    assert next_button.isEnabled()
    assert import_form.copyright_edit.hasFocus()
    qtbot.waitUntil(lambda: not import_form.findChildren(QtWidgets.QMessageBox))


def test_web_import_uses_spinner_and_local_import_keeps_progress_bar(import_form):
    from opal.plugins.bibles.lib.manager import BibleFormat
    import_form.format_combo_box.setCurrentIndex(BibleFormat.WebDownload)
    import_form.pre_wizard()
    assert import_form.progress_bar.isHidden()
    assert not import_form.import_spinner.isHidden()
    assert import_form.import_spinner.isIndeterminate() and import_form.import_spinner.isActive()
    import_form.post_wizard()
    assert import_form.import_spinner.isHidden() and not import_form.import_spinner.isActive()
    import_form.format_combo_box.setCurrentIndex(BibleFormat.OSIS)
    import_form.pre_wizard()
    assert not import_form.progress_bar.isHidden()
    assert import_form.import_spinner.isHidden()


@pytest.mark.parametrize('web_import', [True, False])
@pytest.mark.parametrize('size', [(640, 540), (460, 380)])
def test_import_status_stays_below_instructions_without_large_gaps(import_form, qtbot, web_import, size):
    from opal.plugins.bibles.lib.manager import BibleFormat
    qtbot.addWidget(import_form)
    import_form.setStartId(import_form.pageIds()[-1])
    with patch.object(import_form, 'perform_wizard'), patch.object(import_form, 'post_wizard'):
        import_form.restart()
        import_form.resize(*size)
        import_form.show()
    import_form.format_combo_box.setCurrentIndex(BibleFormat.WebDownload if web_import else BibleFormat.OSIS)
    import_form.pre_wizard()
    import_form.progress_label.setText('Registering language for a translation with a long name. ' * 3)
    QtWidgets.QApplication.processEvents()
    page = import_form.progress_page
    description_bottom = page.description.mapTo(page, QtCore.QPoint(0, page.description.height())).y()
    status_top = import_form.progress_label.mapTo(page, QtCore.QPoint()).y()
    status_bottom = import_form.progress_label.mapTo(page, QtCore.QPoint(0, import_form.progress_label.height())).y()
    indicator = import_form.import_spinner if web_import else import_form.progress_bar
    indicator_top = indicator.mapTo(page, QtCore.QPoint()).y()
    assert 0 <= status_top - description_bottom <= 32
    assert 0 <= indicator_top - status_bottom <= 16
    assert import_form.cancel_button.isVisible()
