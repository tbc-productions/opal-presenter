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
        self._placeholder_indices = set()
        super(LibraryTabBar, self).__init__(parent)

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
        self._top_count = 0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._top_tab_bar = LibraryTabBar(self)
        self._top_tab_bar.setDocumentMode(True)
        self._top_tab_bar.setExpanding(False)
        self._top_tab_bar.setDrawBase(False)
        self._top_tab_bar.setElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self._top_tab_bar.setUsesScrollButtons(False)
        self._top_tab_bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                        QtWidgets.QSizePolicy.Policy.Fixed)
        self._top_tab_bar.setMinimumWidth(0)
        self._top_tab_bar.currentChanged.connect(self._on_top_tab_changed)
        layout.addWidget(self._top_tab_bar)

        self._bottom_tab_bar = LibraryTabBar(self)
        self._bottom_tab_bar.setDocumentMode(True)
        self._bottom_tab_bar.setExpanding(False)
        self._bottom_tab_bar.setDrawBase(False)
        self._bottom_tab_bar.setElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self._bottom_tab_bar.setUsesScrollButtons(False)
        self._bottom_tab_bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                           QtWidgets.QSizePolicy.Policy.Fixed)
        self._bottom_tab_bar.setMinimumWidth(0)
        self._bottom_tab_bar.currentChanged.connect(self._on_bottom_tab_changed)
        layout.addWidget(self._bottom_tab_bar)

        self._stack = QtWidgets.QStackedWidget(self)
        layout.addWidget(self._stack)

    def minimumSizeHint(self):
        hint = super(MediaToolBox, self).minimumSizeHint()
        return QtCore.QSize(0, hint.height())

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
        item_count = len(self._items)
        if item_count <= 1:
            return item_count

        available_width = self._available_width()
        tab_widths = [self._tab_width(item) for item in self._items]
        return self._split_index_for_widths(tab_widths, available_width)

    def _available_width(self):
        return max(self.contentsRect().width(), self.width(), 1)

    @staticmethod
    def _split_index_for_widths(tab_widths, available_width):
        item_count = len(tab_widths)
        if item_count <= 1:
            return item_count

        total_width = sum(tab_widths)
        if total_width <= available_width:
            return len(tab_widths)

        running_width = 0
        for split_index, tab_width in enumerate(tab_widths, start=1):
            running_width += tab_width
            bottom_width = total_width - running_width
            if running_width <= available_width and bottom_width <= available_width:
                return split_index

        best_split = int(math.ceil(len(tab_widths) / 2.0))
        best_overflow = None
        running_width = 0
        for split_index, tab_width in enumerate(tab_widths, start=1):
            running_width += tab_width
            bottom_width = total_width - running_width
            overflow = max(0, running_width - available_width) + max(0, bottom_width - available_width)
            if best_overflow is None or overflow < best_overflow:
                best_overflow = overflow
                best_split = split_index
        return best_split

    def _tab_width(self, item):
        option = QtWidgets.QStyleOptionTab()
        option.initFrom(self._top_tab_bar)
        option.shape = self._top_tab_bar.shape()
        option.text = item['label']
        option.icon = item['icon']
        option.iconSize = self._top_tab_bar.iconSize()
        tab_size = self._top_tab_bar.style().sizeFromContents(
            QtWidgets.QStyle.ContentsType.CT_TabBarTab,
            option,
            QtCore.QSize(),
            self._top_tab_bar
        )
        return tab_size.width()

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
        top_count = self._top_count
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

    def _rebuild_tab_bars(self, top_count=None):
        top_blocker = QtCore.QSignalBlocker(self._top_tab_bar)
        bottom_blocker = QtCore.QSignalBlocker(self._bottom_tab_bar)
        if top_count is None:
            top_count = self._split_index()
        self._top_count = top_count
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

        # If one-row mode was chosen but the rendered tab widths still overflow,
        # recalculate with actual tabSizeHint widths and rebuild once.
        if top_count == len(self._items) and len(self._items) > 1:
            actual_widths = [self._top_tab_bar.tabSizeHint(i).width() for i in range(1, self._top_tab_bar.count())]
            actual_top_count = self._split_index_for_widths(actual_widths, self._available_width())
            if actual_top_count < len(self._items):
                self._rebuild_tab_bars(top_count=actual_top_count)
                return

        self._bottom_tab_bar.setVisible(len(self._items) > top_count)
        self._update_tab_row_heights()
        del top_blocker
        del bottom_blocker
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

    def setItemIcon(self, index, icon):
        if index < 0 or index >= len(self._items):
            return
        self._items[index]['icon'] = self._as_icon(icon)
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

    def resizeEvent(self, event):
        super(MediaToolBox, self).resizeEvent(event)
        if event.oldSize().width() != event.size().width() and self._items:
            self._rebuild_tab_bars()

    def showEvent(self, event):
        super(MediaToolBox, self).showEvent(event)
        if self._items:
            self._rebuild_tab_bars()


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
            icon = media_item.get_library_tab_icon() if hasattr(media_item, 'get_library_tab_icon') \
                else media_item.plugin.icon
            self.media_dock.addItem(media_item, icon, visible_title['title'])

    def refresh_item_icons(self):
        """
        Reapply tinted library icons from current settings to media dock tabs.
        """
        for dock_index in range(self.media_dock.count()):
            media_item = self.media_dock.widget(dock_index)
            if not media_item:
                continue
            icon = media_item.get_library_tab_icon() if hasattr(media_item, 'get_library_tab_icon') \
                else media_item.plugin.icon
            self.media_dock.setItemIcon(dock_index, icon)

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
