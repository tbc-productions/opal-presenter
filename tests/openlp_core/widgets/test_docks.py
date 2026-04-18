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

from PySide6 import QtGui, QtWidgets

from openlp.core.widgets.docks import MediaToolBox


def _add_item(media_tool_box, label):
    widget = QtWidgets.QWidget()
    media_tool_box.addItem(widget, QtGui.QIcon(), label)


def test_media_tool_box_placeholder_tabs_are_hidden_and_disabled(qapp):
    """Placeholder tabs should be disabled and have zero width."""
    media_tool_box = MediaToolBox()
    _add_item(media_tool_box, 'Images')

    assert media_tool_box._top_tab_bar.isTabEnabled(0) is False
    assert media_tool_box._bottom_tab_bar.isTabEnabled(0) is False
    assert media_tool_box._top_tab_bar.tabSizeHint(0).width() == 0
    assert media_tool_box._bottom_tab_bar.tabSizeHint(0).width() == 0


def test_media_tool_box_shows_second_row_when_split(qapp):
    """Adding enough tabs should make the second row visible."""
    media_tool_box = MediaToolBox()
    media_tool_box.resize(150, 300)
    _add_item(media_tool_box, 'Images Library')
    _add_item(media_tool_box, 'Media Files')
    _add_item(media_tool_box, 'Custom Slides')

    assert media_tool_box._bottom_tab_bar.isHidden() is False


def test_media_tool_box_prefers_single_row_when_tabs_fit(qapp):
    """Tabs should stay on one row if there is enough room."""
    media_tool_box = MediaToolBox()
    media_tool_box.resize(2000, 300)
    _add_item(media_tool_box, 'Images')
    _add_item(media_tool_box, 'Media')
    _add_item(media_tool_box, 'Custom Slides')

    assert media_tool_box._bottom_tab_bar.isHidden() is True


def test_media_tool_box_reflows_rows_when_resized(qapp):
    """Tab rows should be recalculated when the toolbox width changes."""
    media_tool_box = MediaToolBox()
    media_tool_box.resize(150, 300)
    media_tool_box.show()
    qapp.process_events()
    _add_item(media_tool_box, 'Images Library')
    _add_item(media_tool_box, 'Media Files')
    _add_item(media_tool_box, 'Custom Slides')

    assert media_tool_box._bottom_tab_bar.isHidden() is False

    media_tool_box.resize(2000, 300)
    qapp.process_events()

    assert media_tool_box._bottom_tab_bar.isHidden() is True


def test_media_tool_box_inactive_row_selects_placeholder(qapp):
    """Only one row should have a real selected tab; the other row uses placeholder index 0."""
    media_tool_box = MediaToolBox()
    media_tool_box.resize(150, 300)
    _add_item(media_tool_box, 'Images Library')
    _add_item(media_tool_box, 'Media Files')
    _add_item(media_tool_box, 'Custom Slides')

    media_tool_box.setCurrentIndex(0)
    assert media_tool_box._top_tab_bar.currentIndex() == 1
    assert media_tool_box._bottom_tab_bar.currentIndex() == 0

    media_tool_box.setCurrentIndex(2)
    assert media_tool_box._top_tab_bar.currentIndex() == 0
    assert media_tool_box._bottom_tab_bar.currentIndex() == (2 - media_tool_box._top_count) + 1


def test_media_tool_box_tab_bars_do_not_draw_base_line(qapp):
    media_tool_box = MediaToolBox()

    assert media_tool_box._top_tab_bar.drawBase() is False
    assert media_tool_box._bottom_tab_bar.drawBase() is False


def test_media_tool_box_has_flexible_minimum_width(qapp):
    """Long tab labels should not force a large minimum width."""
    media_tool_box = MediaToolBox()
    _add_item(media_tool_box, 'Very Long Library Tab Label One')
    _add_item(media_tool_box, 'Very Long Library Tab Label Two')
    _add_item(media_tool_box, 'Very Long Library Tab Label Three')

    assert media_tool_box.minimumSizeHint().width() == 0


def test_media_tool_box_split_uses_tool_box_width(qapp):
    """Split should be based on toolbox width, not a stale larger tab bar width."""
    media_tool_box = MediaToolBox()
    media_tool_box.resize(150, 300)
    _add_item(media_tool_box, 'Images Library')
    _add_item(media_tool_box, 'Media Files')
    _add_item(media_tool_box, 'Custom Slides')

    media_tool_box._top_tab_bar.resize(2000, media_tool_box._top_tab_bar.height())
    media_tool_box._rebuild_tab_bars()

    assert media_tool_box._bottom_tab_bar.isHidden() is False


def test_media_tool_box_rechecks_with_rendered_tab_widths(qapp):
    """A one-row estimate should be corrected if rendered tabs overflow."""
    media_tool_box = MediaToolBox()
    media_tool_box.resize(200, 300)
    _add_item(media_tool_box, 'Images')
    _add_item(media_tool_box, 'Media')
    _add_item(media_tool_box, 'Custom')

    original_tab_width = media_tool_box._tab_width

    try:
        media_tool_box._tab_width = lambda item: 10
        media_tool_box._rebuild_tab_bars()
    finally:
        media_tool_box._tab_width = original_tab_width

    assert media_tool_box._bottom_tab_bar.isHidden() is False


def test_media_tool_box_selection_uses_rendered_split(qapp):
    """Selection sync should use the currently rendered split, not a recomputed split."""
    media_tool_box = MediaToolBox()
    media_tool_box.resize(150, 300)
    _add_item(media_tool_box, 'Images Library')
    _add_item(media_tool_box, 'Media Files')
    _add_item(media_tool_box, 'Custom Slides')

    # Simulate split estimator drift after the bars have already been rendered.
    original_tab_width = media_tool_box._tab_width
    try:
        media_tool_box._tab_width = lambda item: 10
        media_tool_box.setCurrentIndex(2)
    finally:
        media_tool_box._tab_width = original_tab_width

    assert media_tool_box._bottom_tab_bar.currentIndex() > 0
