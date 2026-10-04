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
    return form


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
            close_button = print_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
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
