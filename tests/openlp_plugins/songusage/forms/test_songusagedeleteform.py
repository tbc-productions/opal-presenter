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
Package to test the opal.plugins.songusage.forms.songusagedeleteform package.
"""
import pytest
from unittest.mock import MagicMock

from PySide6 import QtCore
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.settings import Settings
from opal.plugins.songusage.forms.songusagedeleteform import SongUsageDeleteForm


def test_no_help_button(settings: Settings):
    """
    Help buttons are absent
    """
    # GIVEN: A songusage delete form and a patched help function
    main_window = QtWidgets.QMainWindow()
    delete_form = SongUsageDeleteForm(MagicMock(), main_window)

    assert delete_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Help) is None


@pytest.mark.parametrize('confirmed', [False, True])
def test_deletion_requires_confirmation_and_matches_inclusive_date(settings, qtbot, monkeypatch, confirmed):
    from opal.core.common.registry import Registry
    from opal.plugins.songusage.lib.db import SongUsageItem
    main_window = QtWidgets.QMainWindow()
    qtbot.addWidget(main_window)
    main_window.resize(1000, 800)
    main_window.information_message = MagicMock()
    Registry().register('main_window', main_window)
    main_window.show()
    manager = MagicMock()
    form = SongUsageDeleteForm(manager, main_window)
    form.delete_calendar.setSelectedDate(QtCore.QDate(2026, 10, 9))
    messages = []

    def confirm(dialog):
        messages.append(dialog.content().text())
        return dialog.ResultPrimary if confirmed else dialog.ResultNone

    monkeypatch.setattr(QtWidgets.ContentDialog, 'exec', confirm)
    form.setAnimationEnabled(False)
    form.open()
    assert not form._native_commands['secondary'].isVisible()
    form._native_commands['primary'].click()
    assert messages == ['Permanently delete all song usage data on or before 2026-10-09?']
    if confirmed:
        model, expression = manager.delete_all_objects.call_args.args
        assert model is SongUsageItem
        assert expression.compare(SongUsageItem.usagedate <= QtCore.QDate(2026, 10, 9).toPyDate())
        main_window.information_message.assert_called_once()
        assert form.result() == form.DialogCode.Accepted
        assert not form.isOpen()
    else:
        manager.delete_all_objects.assert_not_called()
        main_window.information_message.assert_not_called()
        assert form.isOpen()
        form.reject()
