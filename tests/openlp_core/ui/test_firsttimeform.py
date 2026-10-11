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
Package to test the openlp.core.ui.firsttimeform package.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtTest
from openlp.core.common.registry import Registry
from openlp.core.lib.plugin import PluginStatus
from openlp.core.ui.firsttimeform import FirstTimeForm
from openlp.core.ui.firsttimewizard import FirstTimePage
from openlp.core.widgets import fluent as QtWidgets


@pytest.fixture
def opal_import_notice():
    with patch.object(QtWidgets.QMessageBox, 'information') as opal_notice:
        yield opal_notice


@pytest.fixture
def wizard(mock_settings, qtbot, opal_import_notice):
    widget = FirstTimeForm()
    qtbot.addWidget(widget)
    widget.initialize(MagicMock())
    widget.restart()
    yield widget
    widget.reject()


def test_setup_is_local(wizard):
    """Every page is local, and navigating through setup never makes HTTP requests."""
    with patch('requests.sessions.Session.request', side_effect=AssertionError('Setup accessed the network')):
        wizard.show()
        assert wizard.pageIds() == [FirstTimePage.Welcome, FirstTimePage.Plugins,
                                    FirstTimePage.ScreenConfig, FirstTimePage.ImportSettings]
        for page_id in wizard.pageIds()[1:]:
            wizard.next()
            assert wizard.currentId() == page_id
        assert wizard.nextId() == -1
        assert wizard.information_label.text() == (
            'Thank you for installing Opal Presenter. Let\'s get you set up.\n\n'
            'You can import an existing Opal Presenter (or OpenLP) library during setup.')
        wizard.accept()


def test_exec_restores_defaults(wizard):
    with patch.object(wizard, 'set_defaults') as defaults, patch.object(QtWidgets.QWizard, 'exec') as execute:
        wizard.exec()
        defaults.assert_called_once()
        execute.assert_called_once()


def test_new_features_selected_by_default(wizard):
    wizard.settings.value.return_value = False
    wizard.set_defaults()
    assert wizard.slide_designer_check_box.text() == 'Slide Designer'
    assert wizard.slide_designer_check_box.isChecked()
    assert wizard.library_sync_check_box.text() == 'Library Sync'
    assert wizard.library_sync_check_box.isChecked()


@pytest.mark.parametrize('enabled', [True, False])
def test_accept_saves_local_choices(wizard, enabled):
    wizard.songs_check_box.setChecked(False)
    wizard.remote_interface_check_box.setChecked(True)
    wizard.slide_designer_check_box.setChecked(enabled)
    wizard.library_sync_check_box.setChecked(enabled)
    with patch.object(wizard.screen_selection_widget, 'save') as save, patch.object(QtWidgets.QWizard, 'accept'):
        wizard.accept()
    wizard.settings.setValue.assert_any_call('songs/status', PluginStatus.Inactive)
    wizard.settings.setValue.assert_any_call('remote_interface/status', PluginStatus.Active)
    status = PluginStatus.Active if enabled else PluginStatus.Inactive
    wizard.settings.setValue.assert_any_call('slide_designer/status', status)
    wizard.settings.setValue.assert_any_call('librarysync/status', status)
    save.assert_called_once()


@pytest.mark.parametrize('enabled', [True, False])
def test_rerun_restores_plugins(wizard, enabled):
    wizard.settings.value.return_value = True
    plugin = MagicMock()
    plugin.is_active.return_value = False
    manager = MagicMock()
    manager.get_plugin_by_name.side_effect = lambda name: (
        MagicMock(is_active=MagicMock(return_value=enabled))
        if name in ('slide_designer', 'librarysync') else plugin)
    wizard.slide_designer_check_box.setChecked(not enabled)
    wizard.library_sync_check_box.setChecked(not enabled)
    with patch.object(Registry(), 'get', return_value=manager):
        wizard.set_defaults()
    assert not wizard.songs_check_box.isChecked()
    assert not wizard.bible_check_box.isChecked()
    assert wizard.slide_designer_check_box.isChecked() == enabled
    assert wizard.library_sync_check_box.isChecked() == enabled
    manager.get_plugin_by_name.assert_any_call('slide_designer')
    manager.get_plugin_by_name.assert_any_call('librarysync')


@pytest.mark.parametrize('exists', [True, False])
def test_failed_settings_import_stays_open(wizard, tmp_path, exists):
    path = tmp_path / 'backup.conf'
    if exists:
        path.write_text('invalid')
    wizard.import_settings_page.opal_source_combo.setCurrentIndex(1)
    wizard.import_settings_page.opal_settings_radio.setChecked(True)
    wizard.import_settings_page.file_edit.setText(str(path))
    wizard.settings.import_settings.return_value = False
    with patch.object(QtWidgets.QMessageBox, 'critical'), patch.object(QtWidgets.QWizard, 'accept') as accept, \
            patch.object(wizard.screen_selection_widget, 'save') as save:
        wizard.accept()
    accept.assert_not_called()
    save.assert_not_called()
    wizard.settings.setValue.assert_not_called()
    wizard.import_settings_page.file_edit.clear()
    assert wizard.import_settings_page.file_edit.text() == ''


def test_settings_import_preserves_wizard_choices(wizard, tmp_path, opal_import_notice):
    path = tmp_path / 'backup.conf'
    path.write_text('[General]')
    wizard.import_settings_page.opal_source_combo.setCurrentIndex(1)
    wizard.import_settings_page.opal_settings_radio.setChecked(True)
    wizard.import_settings_page.file_edit.setText(str(path))
    wizard.songs_check_box.setChecked(False)
    wizard.settings.import_settings.return_value = True
    with patch.object(QtWidgets.QWizard, 'accept') as accept, \
            patch.object(wizard.screen_selection_widget, 'save') as save:
        wizard.accept()
    assert wizard.settings.import_settings.call_args.args == (path,)
    accept.assert_called_once()
    save.assert_called_once()
    wizard.settings.setValue.assert_any_call('songs/status', PluginStatus.Inactive)
    opal_import_notice.assert_called_once_with(wizard, 'Import complete', 'Settings copied successfully.')


def test_cancel_unregisters_screen_refresh(wizard):
    with patch.object(Registry(), 'remove_function') as remove, patch.object(QtWidgets.QWizard, 'reject'):
        wizard.reject()
    remove.assert_called_once_with('config_screen_changed', wizard.screen_selection_widget.load)
    wizard.settings.setValue.assert_not_called()


def test_keyboard_setup_navigation(wizard, qtbot):
    wizard.show()
    qtbot.waitUntil(lambda: wizard.isVisible())
    next_button = wizard.button(QtWidgets.QWizard.WizardButton.NextButton)
    next_button.setFocus()
    QtTest.QTest.keyClick(next_button, QtCore.Qt.Key.Key_Return)
    assert wizard.currentId() == FirstTimePage.Plugins
    QtTest.QTest.keyClick(wizard, QtCore.Qt.Key.Key_Escape)
    assert not wizard.isVisible()


def test_setup_display_fits_and_features_scroll_below_heading(wizard, qtbot):
    from openlp.core.display.screens import Screen
    widget = wizard.screen_selection_widget
    widget.screens = [Screen(0, QtCore.QRect(0, 0, 1920, 1080), is_primary=True, is_display=True)]
    widget.load()
    wizard.show()
    wizard.next()
    wizard.resize(460, 380)
    qtbot.waitUntil(lambda: wizard.plugin_page.scroll_area.verticalScrollBar().maximum() > 0)
    page = wizard.plugin_page
    heading_position = page.heading.mapTo(wizard, QtCore.QPoint())
    scrollbar = page.scroll_area.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    assert page.heading.mapTo(wizard, QtCore.QPoint()) == heading_position
    wizard.resize(760, 640)
    wizard.next()
    QtWidgets.QApplication.processEvents()
    viewport = wizard.screen_page.scroll_area.viewport()
    details_bottom = widget.display_group_box.mapTo(viewport, widget.display_group_box.rect().bottomRight())
    assert viewport.rect().contains(details_bottom)
    assert widget.screen_frame.height() == 180


def test_backup_field_inline_clear_and_open(wizard, qtbot, tmp_path):
    wizard.show()
    for _ in range(3):
        wizard.next()
    page = wizard.import_settings_page
    page.opal_source_combo.setCurrentIndex(1)
    page.opal_settings_radio.setChecked(True)
    field = page.file_edit
    clear = field.findChild(QtWidgets.QWidget, 'fluentLineEditClearButton')
    assert not clear.isVisible()
    path = tmp_path / 'backup.conf'
    with patch('openlp.core.widgets.dialogs.FileDialog.getOpenFileName', return_value=(path, '')):
        QtTest.QTest.mouseClick(page.browse_button, QtCore.Qt.MouseButton.LeftButton)
    field.setFocus()
    qtbot.waitUntil(clear.isVisible)
    assert field.text() == str(path)
    assert field.height() == page.browse_button.height()
    assert not page.browse_button.icon().isNull()
    QtTest.QTest.mouseClick(clear, QtCore.Qt.MouseButton.LeftButton)
    assert field.text() == ''
    assert not clear.isVisible()
    assert not page.isComplete()


def test_opal_import_source_options(wizard, qtbot, tmp_path):
    wizard.show()
    for _ in range(3):
        wizard.next()
    opal_page = wizard.import_settings_page
    assert [opal_page.opal_source_combo.itemText(opal_index) for opal_index in range(3)] == [
        'None', 'Opal Presenter', 'OpenLP']
    assert opal_page.opal_source_combo.currentIndex() == 0
    assert not opal_page.opal_library_card.isVisible()
    assert not opal_page.opal_settings_card.isVisible()
    opal_page.opal_source_combo.setCurrentIndex(1)
    assert opal_page.opal_library_card.isVisible()
    assert opal_page.opal_settings_card.isVisible()
    assert opal_page.file_edit.isVisible()
    assert opal_page.opal_library_radio.isChecked()
    assert not opal_page.file_edit.isEnabled()
    QtWidgets.QApplication.processEvents()
    qtbot.mouseClick(opal_page.opal_settings_radio, QtCore.Qt.MouseButton.LeftButton,
                     pos=QtCore.QPoint(12, opal_page.opal_settings_radio.height() // 2))
    assert opal_page.opal_settings_radio.isChecked()
    assert not opal_page.opal_library_radio.isChecked()
    assert not opal_page.opal_library_edit.isEnabled()
    assert not opal_page.opal_library_button.isEnabled()
    assert opal_page.file_edit.isEnabled()
    assert opal_page.browse_button.isEnabled()
    opal_page.file_edit.setText(str(tmp_path / 'settings.opal-settings'))
    opal_page.opal_source_combo.setCurrentIndex(2)
    assert not opal_page.file_edit.isVisible()
    assert not opal_page.browse_button.isVisible()
    assert opal_page.opal_library_edit.isVisible()
    assert opal_page.opal_library_radio.isChecked()
    assert opal_page.opal_library_edit.isEnabled()
    (tmp_path / 'library').mkdir()
    opal_page.opal_library_edit.setText(str(tmp_path / 'library'))
    with patch('openlp.core.ui.firsttimeform.copy_opal_library', return_value=tmp_path / 'copy'), \
            patch.object(QtWidgets.QWizard, 'accept') as opal_accept:
        wizard.accept()
    opal_accept.assert_called_once()
    wizard.settings.import_settings.assert_not_called()
    opal_page.opal_source_combo.setCurrentIndex(1)
    assert opal_page.file_edit.isVisible()
    assert not opal_page.file_edit.isEnabled()
    opal_page.opal_settings_radio.setFocus()
    QtTest.QTest.keyClick(opal_page.opal_settings_radio, QtCore.Qt.Key.Key_Space)
    assert opal_page.opal_settings_radio.isChecked()
    assert not opal_page.opal_library_radio.isChecked()


def test_opal_library_folder_picker(wizard, qtbot, tmp_path):
    wizard.show()
    for _ in range(3):
        wizard.next()
    opal_page = wizard.import_settings_page
    opal_page.opal_source_combo.setCurrentIndex(1)
    with patch('openlp.core.widgets.dialogs.FileDialog.getExistingDirectory', return_value=tmp_path):
        QtTest.QTest.mouseClick(opal_page.opal_library_button, QtCore.Qt.MouseButton.LeftButton)
    assert opal_page.opal_library_edit.text() == str(tmp_path)
    with patch('openlp.core.widgets.dialogs.FileDialog.getExistingDirectory', return_value=None):
        QtTest.QTest.mouseClick(opal_page.opal_library_button, QtCore.Qt.MouseButton.LeftButton)
    assert opal_page.opal_library_edit.text() == str(tmp_path)


@pytest.mark.parametrize('opal_source, opal_settings_selected', [(1, False), (1, True), (2, False)])
def test_opal_finish_requires_selected_import_path(wizard, qtbot, tmp_path, opal_source, opal_settings_selected):
    opal_library = tmp_path / 'library'
    opal_library.mkdir()
    opal_backup = tmp_path / 'backup.opal-settings'
    opal_backup.write_text('backup')
    wizard.show()
    for _ in range(3):
        wizard.next()
    opal_page = wizard.import_settings_page
    opal_finish = wizard.button(QtWidgets.QWizard.WizardButton.FinishButton)
    assert opal_finish.isEnabled()
    opal_page.opal_source_combo.setCurrentIndex(opal_source)
    if opal_settings_selected:
        opal_page.opal_settings_radio.setChecked(True)
    opal_selected = opal_page.file_edit if opal_settings_selected else opal_page.opal_library_edit
    opal_unselected = opal_page.opal_library_edit if opal_settings_selected else opal_page.file_edit
    opal_unselected.setText(str(opal_library if opal_settings_selected else opal_backup))
    opal_selected.setText('   ')
    assert not opal_page.isComplete()
    assert not opal_finish.isEnabled()
    with patch.object(QtWidgets.QWizard, 'accept') as opal_accept, \
            patch('openlp.core.ui.firsttimeform.copy_opal_library') as opal_copy:
        qtbot.mouseClick(opal_finish, QtCore.Qt.MouseButton.LeftButton)
        QtTest.QTest.keyClick(opal_finish, QtCore.Qt.Key.Key_Return)
        wizard.accept()
    opal_accept.assert_not_called()
    opal_copy.assert_not_called()
    wizard.settings.import_settings.assert_not_called()
    wizard.settings.setValue.assert_not_called()
    opal_selected.setText(str(tmp_path / 'missing'))
    assert not opal_page.isComplete()
    assert not opal_finish.isEnabled()
    opal_selected.setText(str(opal_library if opal_settings_selected else opal_backup))
    assert not opal_page.isComplete()
    assert not opal_finish.isEnabled()
    opal_selected.setText(str(opal_backup if opal_settings_selected else opal_library))
    assert opal_page.isComplete()
    assert opal_finish.isEnabled()
    if opal_source == 1:
        opal_unselected.clear()
        opal_radio = opal_page.opal_library_radio if opal_settings_selected else opal_page.opal_settings_radio
        opal_radio.setChecked(True)
        assert not opal_finish.isEnabled()
        opal_radio = opal_page.opal_settings_radio if opal_settings_selected else opal_page.opal_library_radio
        opal_radio.setChecked(True)
        assert opal_finish.isEnabled()
    opal_selected.clear()
    assert not opal_finish.isEnabled()
    opal_page.opal_source_combo.setCurrentIndex(0)
    assert opal_page.isComplete()
    assert opal_finish.isEnabled()


@pytest.mark.parametrize('opal_settings_selected', [False, True])
def test_opal_finish_rechecks_removed_import_path(wizard, qtbot, tmp_path, opal_settings_selected):
    opal_path = tmp_path / 'selected'
    opal_path.write_text('backup') if opal_settings_selected else opal_path.mkdir()
    wizard.show()
    for _ in range(3):
        wizard.next()
    opal_page = wizard.import_settings_page
    opal_page.opal_source_combo.setCurrentIndex(1)
    if opal_settings_selected:
        opal_page.opal_settings_radio.setChecked(True)
    opal_field = opal_page.file_edit if opal_settings_selected else opal_page.opal_library_edit
    opal_field.setText(str(opal_path))
    opal_finish = wizard.button(QtWidgets.QWizard.WizardButton.FinishButton)
    assert opal_finish.isEnabled()
    opal_path.unlink() if opal_settings_selected else opal_path.rmdir()
    with patch.object(QtWidgets.QWizard, 'accept') as opal_accept, \
            patch('openlp.core.ui.firsttimeform.copy_opal_library') as opal_copy:
        qtbot.mouseClick(opal_finish, QtCore.Qt.MouseButton.LeftButton)
    opal_accept.assert_not_called()
    opal_copy.assert_not_called()
    wizard.settings.import_settings.assert_not_called()
    assert wizard.isVisible()
    assert not opal_finish.isEnabled()


def test_opal_none_ignores_hidden_import_fields(wizard, tmp_path, opal_import_notice):
    opal_page = wizard.import_settings_page
    opal_page.opal_source_combo.setCurrentIndex(1)
    opal_page.opal_library_edit.setText(str(tmp_path / 'missing-library'))
    opal_page.file_edit.setText(str(tmp_path / 'missing-settings'))
    opal_page.opal_source_combo.setCurrentIndex(0)
    with patch('openlp.core.ui.firsttimeform.copy_opal_library') as opal_copy, \
            patch.object(QtWidgets.QWizard, 'accept') as opal_accept:
        wizard.accept()
    opal_accept.assert_called_once()
    opal_copy.assert_not_called()
    wizard.settings.import_settings.assert_not_called()
    opal_import_notice.assert_not_called()


@pytest.mark.parametrize('opal_rerun', [False, True])
def test_opal_library_import_on_finish(wizard, tmp_path, opal_rerun, opal_import_notice):
    opal_source = tmp_path / 'source'
    (opal_source / 'media').mkdir(parents=True)
    (opal_source / 'media/video.mp4').write_bytes(b'video')
    (tmp_path / 'external.mp4').write_bytes(b'external video')
    (opal_source / 'custom').mkdir(parents=True)
    import sqlite3
    with sqlite3.connect(opal_source / 'custom/custom.sqlite') as opal_database:
        opal_database.execute('CREATE TABLE custom_slide (id INTEGER PRIMARY KEY, title TEXT)')
        opal_database.execute('INSERT INTO custom_slide VALUES (1, ?)', ('Imported custom slide',))
    wizard.has_run_wizard = opal_rerun
    wizard.import_settings_page.opal_source_combo.setCurrentIndex(2)
    wizard.import_settings_page.opal_library_edit.setText(str(opal_source))
    with patch('openlp.core.ui.firsttimeform.AppLocation.get_directory', return_value=tmp_path / 'opal/data'), \
            patch('openlp.core.ui.firsttimeform.AppLocation.get_data_path', return_value=tmp_path / 'current'), \
            patch.object(QtWidgets.QWizard, 'accept') as opal_accept:
        wizard.accept()
    opal_accept.assert_called_once()
    opal_import_notice.assert_called_once_with(wizard, 'Import complete', 'Library copied successfully.')
    assert (wizard.opal_imported_library / 'custom/custom.sqlite').is_file()
    if opal_rerun:
        assert not any(opal_call.args[0] == 'advanced/data path'
                       for opal_call in wizard.settings.setValue.call_args_list)
    else:
        wizard.settings.setValue.assert_any_call('advanced/data path', wizard.opal_imported_library)


def test_opal_failed_library_import_stays_open(wizard, tmp_path):
    wizard.import_settings_page.opal_source_combo.setCurrentIndex(1)
    (tmp_path / 'empty-library').mkdir()
    wizard.import_settings_page.opal_library_edit.setText(str(tmp_path / 'empty-library'))
    with patch.object(QtWidgets.QMessageBox, 'critical') as opal_error, \
            patch.object(QtWidgets.QWizard, 'accept') as opal_accept:
        wizard.accept()
    opal_error.assert_called_once()
    opal_accept.assert_not_called()
    wizard.settings.setValue.assert_not_called()
    wizard.settings.import_settings.assert_not_called()


def test_opal_failed_import_can_be_corrected(wizard, qtbot, tmp_path, opal_import_notice):
    wizard.show()
    for _ in range(3):
        wizard.next()
    opal_page = wizard.import_settings_page
    opal_page.opal_source_combo.setCurrentIndex(2)
    (tmp_path / 'empty-library').mkdir()
    opal_page.opal_library_edit.setText(str(tmp_path / 'empty-library'))
    opal_finish = wizard.button(QtWidgets.QWizard.WizardButton.FinishButton)
    with patch.object(QtWidgets.QMessageBox, 'critical') as opal_error:
        qtbot.mouseClick(opal_finish, QtCore.Qt.MouseButton.LeftButton)
    opal_error.assert_called_once()
    opal_import_notice.assert_not_called()
    assert wizard.isVisible()
    assert wizard.currentId() == FirstTimePage.ImportSettings
    (tmp_path / 'corrected').mkdir()
    opal_page.opal_library_edit.setText(str(tmp_path / 'corrected'))
    with patch('openlp.core.ui.firsttimeform.copy_opal_library', return_value=tmp_path / 'copy'):
        opal_finish.setFocus()
        QtTest.QTest.keyClick(opal_finish, QtCore.Qt.Key.Key_Return)
    assert wizard.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert not wizard.isVisible()
    opal_import_notice.assert_called_once_with(wizard, 'Import complete', 'Library copied successfully.')


def test_opal_failed_settings_import_ignores_unselected_library(wizard, tmp_path):
    opal_library = tmp_path / 'copy'
    opal_library.mkdir()
    opal_settings = tmp_path / 'bad.conf'
    opal_settings.write_text('bad settings')
    wizard.import_settings_page.opal_source_combo.setCurrentIndex(1)
    wizard.import_settings_page.opal_settings_radio.setChecked(True)
    wizard.import_settings_page.opal_library_edit.setText(str(tmp_path / 'source'))
    wizard.import_settings_page.file_edit.setText(str(opal_settings))
    wizard.settings.import_settings.return_value = False
    with patch('openlp.core.ui.firsttimeform.copy_opal_library') as opal_copy, \
            patch.object(QtWidgets.QMessageBox, 'critical'), patch.object(QtWidgets.QWizard, 'accept') as opal_accept:
        wizard.accept()
    opal_accept.assert_not_called()
    opal_copy.assert_not_called()
    assert opal_library.exists()
    assert wizard.opal_imported_library is None
    wizard.settings.setValue.assert_not_called()


def test_opal_cancel_does_not_copy(wizard, tmp_path):
    wizard.import_settings_page.opal_source_combo.setCurrentIndex(1)
    wizard.import_settings_page.opal_library_edit.setText(str(tmp_path))
    with patch('openlp.core.ui.firsttimeform.copy_opal_library') as opal_copy:
        wizard.reject()
    opal_copy.assert_not_called()


@pytest.mark.parametrize('opal_settings_selected', [False, True])
def test_opal_import_uses_only_selected_card(wizard, tmp_path, opal_settings_selected, opal_import_notice):
    opal_library = tmp_path / 'copy'
    opal_library.mkdir()
    opal_settings = tmp_path / 'backup.opal-settings'
    opal_settings.write_text('backup')
    opal_source = tmp_path / 'source'
    opal_source.mkdir()
    wizard.import_settings_page.opal_source_combo.setCurrentIndex(1)
    wizard.import_settings_page.opal_settings_radio.setChecked(opal_settings_selected)
    wizard.import_settings_page.opal_library_edit.setText(str(opal_source))
    wizard.import_settings_page.file_edit.setText(str(opal_settings))

    wizard.settings.import_settings.return_value = True
    with patch('openlp.core.ui.firsttimeform.copy_opal_library', return_value=opal_library) as opal_copy, \
            patch('openlp.core.ui.firsttimeform.AppLocation.get_data_path', return_value=tmp_path / 'current'), \
            patch.object(QtWidgets.QWizard, 'accept') as opal_accept:
        wizard.accept()
    opal_accept.assert_called_once()
    if opal_settings_selected:
        opal_copy.assert_not_called()
        assert wizard.settings.import_settings.call_args.args == (opal_settings,)
        assert wizard.opal_settings_imported
        assert wizard.opal_imported_library is None
        opal_message = 'Settings copied successfully.'
    else:
        opal_copy.assert_called_once()
        wizard.settings.import_settings.assert_not_called()
        assert not wizard.opal_settings_imported
        assert wizard.opal_imported_library == opal_library
        opal_message = 'Library copied successfully.'
    opal_import_notice.assert_called_once_with(wizard, 'Import complete', opal_message)
    wizard.settings.setValue.assert_any_call('songs/status', PluginStatus.Active)


def test_opal_import_keyboard_and_narrow_host(wizard, qtbot):
    wizard.show()
    for _ in range(3):
        wizard.next()
    opal_page = wizard.import_settings_page
    wizard.resize(460, 380)
    opal_page.opal_source_combo.setCurrentIndex(1)
    opal_page.opal_library_edit.setPlaceholderText('/Users/operator/Documents/A library with a long folder name/Data')
    qtbot.waitUntil(lambda: opal_page.scroll_area.verticalScrollBar().maximum() > 0)
    opal_heading = opal_page.heading.mapTo(wizard, QtCore.QPoint())
    opal_page.scroll_area.verticalScrollBar().setValue(opal_page.scroll_area.verticalScrollBar().maximum())
    assert opal_page.heading.mapTo(wizard, QtCore.QPoint()) == opal_heading
    opal_finish = wizard.button(QtWidgets.QWizard.WizardButton.FinishButton)
    assert opal_finish.isVisible()
    assert not opal_finish.isEnabled()
    opal_finish.setFocus()
    QtTest.QTest.keyClick(opal_finish, QtCore.Qt.Key.Key_Return)
    assert wizard.isVisible()
    opal_page.opal_source_combo.setCurrentIndex(0)
    assert opal_finish.isEnabled()
    opal_finish.setFocus()
    QtTest.QTest.keyClick(opal_finish, QtCore.Qt.Key.Key_Return)
    assert wizard.result() == QtWidgets.QDialog.DialogCode.Accepted


@pytest.mark.parametrize('opal_missing', [False, True])
def test_opal_native_settings_copy_files(
        settings, qtbot, tmp_path, opal_missing, opal_import_notice):
    from openlp.core.display.screens import Screen
    opal_external = tmp_path / 'video.mp4'
    if not opal_missing:
        opal_external.write_bytes(b'original video')
    settings.setValue('advanced/data path', tmp_path / 'current')
    settings.setValue('core/ccli number', 'backup')
    settings.setValue('media/media files', [opal_external])
    settings.setValue('songs/status', PluginStatus.Inactive)
    settings.setValue('core/screens', {99: {'is_display': True}})
    opal_backup = tmp_path / 'backup.opal-settings'
    assert settings.export_zip(opal_backup)
    settings.setValue('core/ccli number', 'current')
    opal_wizard = FirstTimeForm()
    qtbot.addWidget(opal_wizard)
    opal_wizard.initialize(MagicMock())
    opal_screen = Screen(0, QtCore.QRect(0, 0, 1920, 1080), is_primary=True, is_display=True)
    opal_wizard.screen_selection_widget.screens = [opal_screen]
    opal_wizard.screen_selection_widget.load()
    opal_wizard.songs_check_box.setChecked(True)
    opal_wizard.import_settings_page.opal_source_combo.setCurrentIndex(1)
    opal_wizard.import_settings_page.opal_settings_radio.setChecked(True)
    opal_wizard.import_settings_page.file_edit.setText(str(opal_backup))
    opal_wizard.import_settings_page.opal_library_edit.setText(str(tmp_path / 'unselected-library'))
    with patch('openlp.core.ui.firsttimeform.AppLocation.get_directory', return_value=tmp_path / 'opal/data'), \
            patch.object(QtWidgets.QWizard, 'accept') as opal_accept, patch.object(QtWidgets.QMessageBox, 'critical'):
        opal_wizard.accept()
    if opal_missing:
        opal_accept.assert_not_called()
        assert settings.value('core/ccli number') == 'current'
        assert settings.value('advanced/data path') == tmp_path / 'current'
        assert list((tmp_path / 'current').iterdir()) == []
    else:
        opal_accept.assert_called_once()
        opal_copied = settings.value('media/media files')[0]
        assert opal_copied.is_relative_to(opal_wizard.opal_imported_library or tmp_path / 'current')
        opal_external.unlink()
        assert opal_copied.read_bytes() == b'original video'
        assert settings.value('core/ccli number') == 'backup'
        assert settings.value('songs/status') == PluginStatus.Active
        assert settings.value('core/screens') == {'0': opal_screen.to_dict()}
    opal_wizard.reject()
