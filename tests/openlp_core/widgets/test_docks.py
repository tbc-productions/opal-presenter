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
Tests for Library dock tab behavior.
"""

from unittest.mock import patch

from PySide6 import QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.widgets.docks import MediaToolBox


def _add_item(media_tool_box, label):
    widget = QtWidgets.QWidget()
    media_tool_box.addItem(widget, QtGui.QIcon(), label)


def test_library_drag_filter_is_not_installed_on_application(qapp, qtbot):
    """WebEngine must be able to construct private objects without Python filters."""
    with patch.object(QtWidgets.QApplication.instance(), 'installEventFilter') as global_filter:
        box = MediaToolBox()
        qtbot.addWidget(box)
        _add_item(box, 'Songs')
    global_filter.assert_not_called()


def test_library_selector_stays_one_row_and_overflows(qapp):
    box = MediaToolBox()
    for label in ('Songs', 'Bibles', 'Presentations', 'Images', 'Media', 'Custom Slides'):
        _add_item(box, label)
    box.resize(250, 400)
    box.show()
    qapp.process_events()
    height = box._selector.height()
    assert box._selector.overflowBehavior() == QtWidgets.fluentqt.SelectorBar.OverflowBehavior.MoreButton
    assert box._selector.hiddenItemIndexes()
    assert not box._selector.overflowGeometry().isEmpty()
    box.resize(2000, 400)
    qapp.process_events()
    assert not box._selector.hiddenItemIndexes()
    assert box._selector.height() == height
    box.close()


def test_library_selector_preserves_selection_and_mutation(qapp):
    box = MediaToolBox()
    for label in ('Songs', 'Bibles', 'Images'):
        _add_item(box, label)
    assert box.currentIndex() == 0
    box.setCurrentIndex(2)
    page = box.currentWidget()
    box.removeItem(0)
    assert box.currentIndex() == 1
    assert box.currentWidget() is page
    box.setItemEnabled(1, False)
    assert box.currentIndex() == 0
    box.setCurrentIndex(1)
    assert box.currentIndex() == 0
    box.removeItem(1)
    box.removeItem(0)
    assert box.currentIndex() == -1
    assert box.currentWidget() is None


def test_library_selector_preserves_coloured_icons(qapp):
    box = MediaToolBox()
    pixmap = QtGui.QPixmap(16, 16)
    pixmap.fill(QtGui.QColor('#ff0099'))
    box.addItem(QtWidgets.QWidget(), QtGui.QIcon(pixmap), 'Songs')
    box.resize(400, 200)
    box.show()
    qapp.process_events()
    image = box._selector.grab().toImage()
    assert any(image.pixelColor(x, y).name() == '#ff0099'
               for y in range(image.height()) for x in range(image.width()))
    assert box.minimumSizeHint().width() == 0
    box.close()


def test_library_more_selection_keeps_earlier_tabs_when_they_fit(qapp):
    box = MediaToolBox()
    pixmap = QtGui.QPixmap(16, 16)
    pixmap.fill(QtGui.QColor('#ff0099'))
    for label in ('Songs', 'Bibles', 'Presentations', 'Images', 'Media', 'Custom Slides'):
        box.addItem(QtWidgets.QWidget(), QtGui.QIcon(pixmap), label)
    box.resize(440, 400)
    box.show()
    qapp.process_events()
    box.setCurrentIndex(5)
    qapp.process_events()
    assert 5 in box._selector.visibleItemIndexes()
    assert 0 in box._selector.visibleItemIndexes()
    assert len(box._selector.visibleItemIndexes()) >= 2
    box.setCurrentIndex(0)
    assert box.currentWidget() is box.widget(0)
    box.close()
