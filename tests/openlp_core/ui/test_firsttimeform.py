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
def wizard(mock_settings, qtbot):
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
        assert 'not endorsed by OpenLP' in wizard.information_label.text()
        wizard.accept()


def test_exec_restores_defaults(wizard):
    with patch.object(wizard, 'set_defaults') as defaults, patch.object(QtWidgets.QWizard, 'exec') as execute:
        wizard.exec()
        defaults.assert_called_once()
        execute.assert_called_once()


def test_accept_saves_local_choices(wizard):
    wizard.songs_check_box.setChecked(False)
    wizard.remote_interface_check_box.setChecked(True)
    with patch.object(wizard.screen_selection_widget, 'save') as save, patch.object(QtWidgets.QWizard, 'accept'):
        wizard.accept()
    wizard.settings.setValue.assert_any_call('songs/status', PluginStatus.Inactive)
    wizard.settings.setValue.assert_any_call('remote_interface/status', PluginStatus.Active)
    save.assert_called_once()


def test_rerun_restores_plugins(wizard):
    wizard.settings.value.return_value = True
    plugin = MagicMock()
    plugin.is_active.return_value = False
    with patch.object(Registry(), 'get', return_value=MagicMock(get_plugin_by_name=MagicMock(return_value=plugin))):
        wizard.set_defaults()
    assert not wizard.songs_check_box.isChecked()
    assert not wizard.bible_check_box.isChecked()


@pytest.mark.parametrize('exists', [True, False])
def test_failed_settings_import_stays_open(wizard, tmp_path, exists):
    path = tmp_path / 'backup.conf'
    if exists:
        path.write_text('invalid')
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


def test_settings_import_preserves_restored_configuration(wizard, tmp_path):
    path = tmp_path / 'backup.conf'
    path.write_text('[General]')
    wizard.import_settings_page.file_edit.setText(str(path))
    wizard.settings.import_settings.return_value = True
    with patch.object(QtWidgets.QWizard, 'accept') as accept, \
            patch.object(wizard.screen_selection_widget, 'save') as save:
        wizard.accept()
    wizard.settings.import_settings.assert_called_once_with(path)
    accept.assert_called_once()
    save.assert_not_called()
    wizard.settings.setValue.assert_not_called()


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
    assert '\n\nAlternatively' in page.info_label.text()
    QtTest.QTest.mouseClick(clear, QtCore.Qt.MouseButton.LeftButton)
    assert field.text() == ''
    assert not clear.isVisible()
    assert page.isComplete()
