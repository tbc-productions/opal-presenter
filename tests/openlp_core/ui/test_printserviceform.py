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
"""Tests for the modal Fluent print service window."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtTest, QtWidgets
import fluentqt

from openlp.core.ui.printserviceform import PrintServiceForm


@pytest.fixture
def print_form(settings, registry, qtbot, temp_folder):
    parent = QtWidgets.QWidget()
    parent.resize(1024, 768)
    qtbot.addWidget(parent)
    parent.show()
    registry.register('main_window', parent)
    service_manager = MagicMock()
    service_manager.service_items = []
    registry.register('service_manager', service_manager)
    with patch('openlp.core.ui.printserviceform.AppLocation.get_data_path', return_value=Path(temp_folder)):
        form = PrintServiceForm()
        qtbot.addWidget(form)
        yield form


@pytest.mark.parametrize('close_method', ['button', 'escape', 'caption'])
def test_print_window_closes_and_can_reopen(print_form, close_method):
    """Each close path ends the modal loop and permits opening the preview again."""
    assert isinstance(print_form, fluentqt.Window)
    original_modality = print_form.windowModality()
    closed = []

    def close_preview():
        try:
            assert print_form.isWindow()
            assert print_form.isVisible()
            assert print_form.windowModality() == QtCore.Qt.WindowModality.ApplicationModal
            close_button = next(widget for widget in print_form.toolbar.findChildren(QtWidgets.QWidget)
                                if widget.property('commandAction') is print_form.close_button)
            assert close_button.isVisible() and close_button.isEnabled()
            bottom_right = close_button.mapTo(print_form, close_button.rect().bottomRight())
            assert print_form.rect().contains(bottom_right)
            if close_method == 'button':
                QtTest.QTest.mouseClick(close_button, QtCore.Qt.MouseButton.LeftButton)
            elif close_method == 'escape':
                QtTest.QTest.keyClick(print_form.preview_widget, QtCore.Qt.Key.Key_Escape)
            else:
                print_form.closeWindow()
            assert not print_form.isVisible()
            closed.append(close_method)
        finally:
            # Release exec() even if an assertion fails inside the timer callback.
            print_form.close()

    for _ in range(2):
        QtCore.QTimer.singleShot(0, close_preview)
        assert print_form.exec() == QtWidgets.QDialog.DialogCode.Rejected
        assert not print_form.isVisible()
        assert print_form.windowModality() == original_modality
    assert closed == [close_method, close_method]


def test_options_pane_and_single_command_bar(print_form):
    """Settings stay alongside the preview, including when the window is resized."""
    print_form.show()
    assert print_form.findChildren(fluentqt.CommandBar) == [print_form.toolbar]
    assert not hasattr(print_form, 'options_button')
    assert print_form.options_group_box.title() == ''
    for width in (1100, 800):
        print_form.resize(width, 600)
        QtWidgets.QApplication.processEvents()
        assert print_form.options_widget.isVisible()
        options_right = print_form.options_scroll_area.mapTo(print_form, QtCore.QPoint(
            print_form.options_scroll_area.width(), 0)).x()
        preview_left = print_form.preview_widget.mapTo(print_form, QtCore.QPoint()).x()
        assert options_right <= preview_left


@pytest.mark.parametrize('parent_position', [(100, 80), (1400, 120), (-1200, 100)])
def test_print_window_opens_centred_over_main_window(print_form, parent_position):
    """Opening and reopening use the main window's current global position."""
    parent = print_form.parentWidget()
    for offset in (QtCore.QPoint(), QtCore.QPoint(200, 50)):
        parent.move(QtCore.QPoint(*parent_position) + offset)
        print_form.show()
        delta = print_form.frameGeometry().center() - parent.frameGeometry().center()
        # QRect centre rounding can differ by one pixel at negative screen coordinates.
        assert abs(delta.x()) <= 1 and abs(delta.y()) <= 1
        print_form.close()


def test_text_edits_update_preview(print_form):
    """Title and service notes apply without toggling an Options button."""
    print_form.title_line_edit.setText('Sunday service')
    assert 'Sunday service' in print_form.document.toPlainText()
    print_form.footer_text_edit.setPlainText('Please stay for morning tea.')
    assert 'Please stay for morning tea.' in print_form.document.toPlainText()


def test_options_update_preview_and_settings(print_form, settings):
    """Checkboxes refresh the document and preserve the selected print options."""
    with patch.object(print_form, 'update_preview_text') as update_preview:
        print_form.slide_text_check_box.setChecked(False)
        assert not print_form.page_break_after_text.isEnabled()
        print_form.slide_text_check_box.setChecked(True)
        assert print_form.page_break_after_text.isEnabled()
        print_form.page_break_after_text.setChecked(True)
        print_form.notes_check_box.setChecked(True)
        print_form.meta_data_check_box.setChecked(True)
        print_form.show_chords_check_box.setChecked(True)
    assert update_preview.call_count >= 5
    for key in ('print slide text', 'add page break', 'print notes', 'print file meta data'):
        assert settings.value('advanced/' + key) is True
