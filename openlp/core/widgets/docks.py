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

from PySide6 import QtCore, QtGui
from sqlalchemy.exc import SQLAlchemyError
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.display.screens import ScreenList
from openlp.core.lib import build_icon
from openlp.core.lib.plugin import StringContent
from openlp.core.common.i18n import translate
from openlp.core.ui.style import get_dock_panel_header_stylesheet
from openlp.core.widgets.dnd import ItemDragData


log = logging.getLogger(__name__)


class FluentLibrarySelectorBar(QtWidgets.fluentqt.SelectorBar):
    """Native SelectorBar with the Library's existing coloured QIcons."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._icons = []
        self.setOverflowBehavior(self.OverflowBehavior.MoreButton)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        for index in self.visibleItemIndexes():
            if index >= len(self._icons) or self._icons[index].isNull():
                continue
            rect = self.itemGeometry(index)
            # SelectorBar's standard icon slot: 16 px inset, 16 px glyph.
            size = QtWidgets.fluentqt.Typography.IconSize.Standard
            if self.layoutDirection() == QtCore.Qt.LayoutDirection.RightToLeft:
                left = rect.right() - 16 - size + 1
            else:
                left = rect.left() + 16
            target = QtCore.QRect(left, rect.center().y() - size // 2 + 1, size, size)
            enabled = self.isEnabled() and self.itemAt(index).enabled
            mode = QtGui.QIcon.Mode.Normal if enabled else QtGui.QIcon.Mode.Disabled
            self._icons[index].paint(painter, target, QtCore.Qt.AlignmentFlag.AlignCenter, mode)
        painter.end()


class FluentLibraryOverflowMenu(QtWidgets.QMenu):
    """Activate leaf commands on a matching click without waiting for hover."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressed_action = None

    def mousePressEvent(self, event):
        self._pressed_action = None
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            action = self.actionAt(event.position().toPoint())
            if action and action.isEnabled() and not action.isSeparator() and not action.menu():
                self._pressed_action = action
                self.setActiveAction(action)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        action = self._pressed_action
        self._pressed_action = None
        if event.button() == QtCore.Qt.MouseButton.LeftButton and action:
            if self.actionAt(event.position().toPoint()) == action and action.isEnabled():
                self.close()
                action.trigger()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MediaToolBox(QtWidgets.QWidget):
    """Single-row Library SelectorBar backed by the existing page stack."""
    currentChanged = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._current_index = -1
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._selector = FluentLibrarySelectorBar(self)
        self._selector.setAccessibleName('Library')
        self._selector.currentChanged.connect(self._selected)
        self._selector.overflowActivated.connect(self._show_overflow)
        layout.addWidget(self._selector)
        self._stack = QtWidgets.QStackedWidget(self)
        layout.addWidget(self._stack, 1)
        self._overflow_menu = FluentLibraryOverflowMenu(self)
        self.setAcceptDrops(True)
        self._watch_drag_widgets(self)

    def _watch_drag_widgets(self, widget):
        # Global Python filters can crash while WebEngine constructs private Qt objects.
        widget.installEventFilter(self)
        for child in widget.findChildren(QtWidgets.QWidget):
            child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.Type.ChildPolished:
            self._watch_drag_widgets(event.child())
        if (event.type() not in (QtCore.QEvent.Type.DragEnter, QtCore.QEvent.Type.DragMove, QtCore.QEvent.Type.Drop)
                or not isinstance(watched, QtWidgets.QWidget)
                or watched is not self and not self.isAncestorOf(watched)):
            return super().eventFilter(watched, event)
        mime = event.mimeData()
        if not isinstance(mime, ItemDragData) or mime.library is not None:
            return super().eventFilter(watched, event)
        for index, entry in enumerate(self._items):
            library = entry['widget']
            if not entry['enabled'] or not library.can_import_service_item(mime.item):
                continue
            self.setCurrentIndex(index)
            if event.type() == QtCore.QEvent.Type.Drop:
                browser = getattr(library, 'library_view', None)
                if browser and browser.grid_button.isChecked():
                    point = browser.grid.viewport().mapFrom(watched, event.position().toPoint())
                    target = browser.grid.tree_item(browser.grid.itemAt(point)) or browser.folder_item()
                else:
                    point = library.list_view.viewport().mapFrom(watched, event.position().toPoint())
                    target = library.list_view.itemAt(point)
                try:
                    imported = library.import_service_item(mime.item, target)
                except (OSError, ValueError, RuntimeError, SyntaxError, SQLAlchemyError) as error:
                    QtWidgets.QMessageBox.critical(
                        self.window(), translate('OpenLP.MediaManagerItem', 'Import failed'), str(error))
                    imported = False
                if not imported:
                    event.ignore()
                    return True
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            return True
        event.ignore()
        return True

    def minimumSizeHint(self):
        return QtCore.QSize(0, super().minimumSizeHint().height())

    @staticmethod
    def _as_icon(icon):
        return icon if isinstance(icon, QtGui.QIcon) else build_icon(icon)

    def _rebuild_selector(self):
        blocker = QtCore.QSignalBlocker(self._selector)
        self._selector.clearItems()
        self._selector._icons = [item['icon'] for item in self._items]
        for item in self._items:
            # A blank glyph reserves the native icon slot; paintEvent supplies
            # the original QIcon without changing native selection or layout.
            glyph = ' ' if not item['icon'].isNull() else ''
            self._selector.addItem(QtWidgets.fluentqt.SelectorBarItem(
                item['label'], glyph, item['enabled']))
        self._selector.setSelectedIndex(max(0, self._current_index) if self._items else -1)
        selected = self._selector.selectedIndex()
        del blocker
        self._selected(selected)
        self._selector.update()

    def _selected(self, index):
        changed = self._current_index != index
        self._current_index = index
        if index >= 0:
            self._stack.setCurrentIndex(index)
        if changed:
            self.currentChanged.emit(index)

    def _show_overflow(self, indexes):
        self._overflow_menu.close()
        self._overflow_menu.deleteLater()
        self._overflow_menu = FluentLibraryOverflowMenu(self)
        for index in indexes:
            item = self._items[index]
            action = self._overflow_menu.addAction(item['icon'], item['label'])
            action.setData(index)
            action.setEnabled(item['enabled'])
            action.triggered.connect(lambda checked=False, index=index: self._select_overflow_item(index))
        rect = self._selector.overflowGeometry()
        self._overflow_menu.popup(self._selector.mapToGlobal(rect.bottomLeft()))

    def _select_overflow_item(self, index):
        # Finish closing the popup before changing the page and native geometry.
        self._overflow_menu.close()
        QtCore.QTimer.singleShot(0, lambda: self.setCurrentIndex(index))

    def addItem(self, widget, icon, label):
        self._items.append(dict(widget=widget, icon=self._as_icon(icon), label=label, enabled=True))
        self._stack.addWidget(widget)
        self._watch_drag_widgets(widget)
        self._rebuild_selector()
        return len(self._items) - 1

    def removeItem(self, index):
        if not 0 <= index < self.count():
            return
        self._stack.removeWidget(self._items.pop(index)['widget'])
        if index < self._current_index:
            self._current_index -= 1
        elif self._current_index >= self.count():
            self._current_index = self.count() - 1
        self._rebuild_selector()

    def itemText(self, index):
        return self._items[index]['label']

    def setItemEnabled(self, index, enabled):
        if 0 <= index < self.count():
            self._items[index]['enabled'] = enabled
            self._selector.setItemEnabled(index, enabled)

    def setItemIcon(self, index, icon):
        if 0 <= index < self.count():
            self._items[index]['icon'] = self._as_icon(icon)
            self._rebuild_selector()

    def count(self):
        return len(self._items)

    def widget(self, index):
        return self._items[index]['widget'] if 0 <= index < self.count() else None

    def currentWidget(self):
        return self.widget(self._current_index)

    def currentIndex(self):
        return self._current_index

    def setCurrentIndex(self, index):
        self._selector.setSelectedIndex(index)


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
