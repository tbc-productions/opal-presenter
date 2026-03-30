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
The :mod:`~openlp.core.widgets.docks` module contains a customised base dock widget and dock widgets
"""
import logging
import math

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.display.screens import ScreenList
from openlp.core.lib import build_icon
from openlp.core.lib.plugin import StringContent
from openlp.core.ui.style import get_dock_panel_header_stylesheet


log = logging.getLogger(__name__)


class LibraryTabBar(QtWidgets.QTabBar):
    """
    QTabBar with support for zero-width placeholder tabs.
    """

    def __init__(self, parent=None):
        super(LibraryTabBar, self).__init__(parent)
        self._placeholder_indices = set()

    def set_placeholder(self, index, enabled=True):
        if enabled:
            self._placeholder_indices.add(index)
        else:
            self._placeholder_indices.discard(index)

    def clear_placeholders(self):
        self._placeholder_indices.clear()

    def tabSizeHint(self, index):
        size = super(LibraryTabBar, self).tabSizeHint(index)
        if index in self._placeholder_indices:
            return QtCore.QSize(0, size.height())
        return size


class MediaToolBox(QtWidgets.QWidget):
    """
    Two-row tab-based media container backed by a QStackedWidget.
    """

    currentChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(MediaToolBox, self).__init__(parent)
        self._items = []
        self._current_index = -1
        self._syncing = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._top_tab_bar = LibraryTabBar(self)
        self._top_tab_bar.setDocumentMode(True)
        self._top_tab_bar.setExpanding(False)
        self._top_tab_bar.setElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self._top_tab_bar.setUsesScrollButtons(False)
        self._top_tab_bar.currentChanged.connect(self._on_top_tab_changed)
        layout.addWidget(self._top_tab_bar)

        self._bottom_tab_bar = LibraryTabBar(self)
        self._bottom_tab_bar.setDocumentMode(True)
        self._bottom_tab_bar.setExpanding(False)
        self._bottom_tab_bar.setElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self._bottom_tab_bar.setUsesScrollButtons(False)
        self._bottom_tab_bar.currentChanged.connect(self._on_bottom_tab_changed)
        layout.addWidget(self._bottom_tab_bar)

        self._stack = QtWidgets.QStackedWidget(self)
        layout.addWidget(self._stack)

    @staticmethod
    def _clear_tab_bar(tab_bar):
        while tab_bar.count() > 0:
            tab_bar.removeTab(0)

    @staticmethod
    def _add_placeholder_tab(tab_bar):
        placeholder_index = tab_bar.addTab('')
        tab_bar.setTabData(placeholder_index, None)
        tab_bar.setTabEnabled(placeholder_index, False)
        if isinstance(tab_bar, LibraryTabBar):
            tab_bar.set_placeholder(placeholder_index, True)

    def _split_index(self):
        return int(math.ceil(len(self._items) / 2.0))

    def _as_icon(self, icon):
        if isinstance(icon, QtGui.QIcon):
            return icon
        return build_icon(icon)

    def _update_tab_row_heights(self):
        base_height = max(self.fontMetrics().height() + 12, 24)
        top_height = self._top_tab_bar.sizeHint().height() if self._top_tab_bar.count() > 1 else 0
        bottom_height = self._bottom_tab_bar.sizeHint().height() if self._bottom_tab_bar.count() > 1 else 0
        self._top_tab_bar.setFixedHeight(max(top_height, base_height) if self._top_tab_bar.count() else 0)
        self._bottom_tab_bar.setFixedHeight(max(bottom_height, base_height)
                                            if self._bottom_tab_bar.count() > 1 else 0)

    def _sync_tab_selection(self):
        self._syncing = True
        top_count = self._split_index()
        if 0 <= self._current_index < len(self._items):
            if self._current_index < top_count:
                self._top_tab_bar.setCurrentIndex(self._current_index + 1)
                self._bottom_tab_bar.setCurrentIndex(0)
            else:
                self._top_tab_bar.setCurrentIndex(0)
                self._bottom_tab_bar.setCurrentIndex((self._current_index - top_count) + 1)
        else:
            self._top_tab_bar.setCurrentIndex(0)
            self._bottom_tab_bar.setCurrentIndex(0)
        self._syncing = False

    def _rebuild_tab_bars(self):
        top_count = self._split_index()
        self._top_tab_bar.clear_placeholders()
        self._bottom_tab_bar.clear_placeholders()
        self._clear_tab_bar(self._top_tab_bar)
        self._clear_tab_bar(self._bottom_tab_bar)

        self._add_placeholder_tab(self._top_tab_bar)
        self._add_placeholder_tab(self._bottom_tab_bar)

        for index, item in enumerate(self._items):
            tab_bar = self._top_tab_bar if index < top_count else self._bottom_tab_bar
            row_index = tab_bar.addTab(item['icon'], item['label'])
            tab_bar.setTabData(row_index, index)
            tab_bar.setTabEnabled(row_index, item['enabled'])

        self._bottom_tab_bar.setVisible(len(self._items) > top_count)
        self._update_tab_row_heights()
        self._sync_tab_selection()

    def _on_top_tab_changed(self, tab_index):
        if self._syncing or tab_index <= 0:
            return
        index = self._top_tab_bar.tabData(tab_index)
        if isinstance(index, int):
            self.setCurrentIndex(index)

    def _on_bottom_tab_changed(self, tab_index):
        if self._syncing or tab_index <= 0:
            return
        index = self._bottom_tab_bar.tabData(tab_index)
        if isinstance(index, int):
            self.setCurrentIndex(index)

    def addItem(self, widget, icon, label):
        tab_icon = self._as_icon(icon)
        self._items.append({'widget': widget, 'icon': tab_icon, 'label': label, 'enabled': True})
        self._stack.addWidget(widget)
        self._rebuild_tab_bars()
        new_index = len(self._items) - 1
        if self._current_index == -1:
            self.setCurrentIndex(0)
        return new_index

    def removeItem(self, index):
        if index < 0 or index >= len(self._items):
            return
        widget = self._items[index]['widget']
        self._stack.removeWidget(widget)
        del self._items[index]
        if index < self._current_index:
            self._current_index -= 1
        elif index == self._current_index and self._current_index >= len(self._items):
            self._current_index = len(self._items) - 1
        if not self._items:
            self._current_index = -1
            self._rebuild_tab_bars()
            self.currentChanged.emit(-1)
            return
        self._rebuild_tab_bars()
        self.setCurrentIndex(self._current_index)

    def itemText(self, index):
        return self._items[index]['label']

    def setItemEnabled(self, index, enabled):
        if index < 0 or index >= len(self._items):
            return
        self._items[index]['enabled'] = enabled
        self._rebuild_tab_bars()

    def count(self):
        return len(self._items)

    def widget(self, index):
        if index < 0 or index >= len(self._items):
            return None
        return self._items[index]['widget']

    def currentWidget(self):
        return self.widget(self._current_index)

    def currentIndex(self):
        return self._current_index

    def setCurrentIndex(self, index):
        if index < 0 or index >= len(self._items):
            return
        if self._current_index == index and self._stack.currentIndex() == index:
            self._sync_tab_selection()
            return
        self._current_index = index
        self._stack.setCurrentIndex(index)
        self._sync_tab_selection()
        self.currentChanged.emit(index)


class OpenLPDockWidget(QtWidgets.QDockWidget):
    """
    Custom DockWidget class to handle events
    """
    def __init__(self, parent=None, name=None, icon=None):
        """
        Initialise the DockWidget
        """
        log.debug('Initialise the %s widget' % name)
        super(OpenLPDockWidget, self).__init__(parent)
        if name:
            self.setObjectName(name)
        self.setStyleSheet(get_dock_panel_header_stylesheet())
        if icon:
            self.setWindowIcon(build_icon(icon))
        # Sort out the minimum width.
        screens = ScreenList()
        main_window_docbars = screens.current.display_geometry.width() // 5
        if main_window_docbars > 300:
            self.setMinimumWidth(300)
        else:
            self.setMinimumWidth(main_window_docbars)


class MediaDockManager(object):
    """
    Provide a repository for MediaManagerItems
    """
    def __init__(self, media_dock):
        """
        Initialise the media dock
        """
        self.media_dock = media_dock

    def add_item_to_dock(self, media_item):
        """
        Add a MediaManagerItem to the dock
        If the item has been added before, it's silently skipped

        :param media_item: The item to add to the dock
        """
        visible_title = media_item.plugin.get_string(StringContent.VisibleName)
        log.debug('Inserting %s dock' % visible_title['title'])
        match = False
        for dock_index in range(self.media_dock.count()):
            if self.media_dock.widget(dock_index).settings_section == media_item.plugin.name:
                match = True
                break
        if not match:
            self.media_dock.addItem(media_item, media_item.plugin.icon, visible_title['title'])

    def remove_dock(self, media_item):
        """
        Removes a MediaManagerItem from the dock

        :param media_item: The item to add to the dock
        """
        visible_title = media_item.plugin.get_string(StringContent.VisibleName)
        log.debug('remove %s dock' % visible_title['title'])
        for dock_index in range(self.media_dock.count()):
            if self.media_dock.widget(dock_index):
                if self.media_dock.widget(dock_index).settings_section == media_item.plugin.name:
                    self.media_dock.widget(dock_index).setVisible(False)
                    self.media_dock.removeItem(dock_index)
