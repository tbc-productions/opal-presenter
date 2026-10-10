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
Package to test the openlp.plugins.songusage.forms.songusagedetailform package.
"""
from unittest.mock import MagicMock

from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.settings import Settings
from openlp.plugins.songusage.forms.songusagedetailform import SongUsageDetailForm


def test_no_help_button(settings: Settings):
    """
    Help buttons are absent
    """
    # GIVEN: A songusage detail form and a patched help function
    main_window = QtWidgets.QMainWindow()
    detail_form = SongUsageDetailForm(MagicMock(), main_window)

    assert detail_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Help) is None


def test_date_range_uses_two_compact_calendar_date_pickers(settings, qtbot):
    main_window = QtWidgets.QMainWindow()
    qtbot.addWidget(main_window)
    main_window.resize(1000, 800)
    main_window.show()
    form = SongUsageDetailForm(MagicMock(), main_window)
    form.setAnimationEnabled(False)
    form.open()
    QtWidgets.QApplication.processEvents()
    assert form.from_label.text() == 'From'
    assert form.to_label.text() == 'To'
    assert form.from_date_picker.accessibleName() == 'From date'
    assert form.to_date_picker.accessibleName() == 'To date'
    assert form._content_scroll.horizontalScrollBar().maximum() == 0
    assert isinstance(form.from_date_picker, QtWidgets.CalendarDatePicker)
    assert isinstance(form.to_date_picker, QtWidgets.CalendarDatePicker)
    assert form.width() == 420
    assert form.height() < 350
    viewport = form._content_scroll.viewport()
    for calendar in (form.from_date_picker, form.to_date_picker):
        assert viewport.rect().contains(QtCore.QRect(calendar.mapTo(viewport, QtCore.QPoint()), calendar.size()))
    form.from_date_picker.openCalendar()
    form.from_date_picker.calendarView().dateActivated.emit(QtCore.QDate(2025, 8, 1))
    assert form.from_date_picker.date() == QtCore.QDate(2025, 8, 1)
    assert form.isOpen()
    main_window.resize(450, 350)
    QtWidgets.QApplication.processEvents()
    assert main_window.rect().contains(form.geometry())
    assert form._content_scroll.horizontalScrollBar().maximum() == 0
    close = form._native_commands['close']
    assert form.rect().contains(QtCore.QRect(close.mapTo(form, QtCore.QPoint()), close.size()))
    form.reject()


def test_date_pickers_restore_and_export_selected_range(settings, qtbot, tmp_path):
    from openlp.core.common.registry import Registry
    from openlp.plugins.songusage.lib.db import SongUsageItem
    main_window = QtWidgets.QMainWindow()
    qtbot.addWidget(main_window)
    main_window.information_message = MagicMock()
    Registry().register('main_window', main_window)
    plugin = MagicMock()
    plugin.manager.get_all_objects.return_value = []
    settings.setValue('songusage/from date', QtCore.QDate(2025, 7, 1))
    settings.setValue('songusage/to date', QtCore.QDate(2026, 7, 1))
    settings.setValue('songusage/last directory export', tmp_path)
    form = SongUsageDetailForm(plugin, main_window)
    form.initialise()
    assert form.from_date_picker.date() == QtCore.QDate(2025, 7, 1)
    assert form.to_date_picker.date() == QtCore.QDate(2026, 7, 1)
    form.to_date_picker.setDate(QtCore.QDate(2026, 10, 10))
    form.accept()
    assert settings.value('songusage/to date') == QtCore.QDate(2026, 10, 10)
    assert (tmp_path / 'usage_detail_01072025_10102026.txt').exists()
    model, expression, order = plugin.manager.get_all_objects.call_args.args
    assert model is SongUsageItem
    assert expression.clauses[0].compare(SongUsageItem.usagedate >= QtCore.QDate(2025, 7, 1).toPyDate())
    assert expression.clauses[1].compare(SongUsageItem.usagedate < QtCore.QDate(2026, 10, 10).toPyDate())
