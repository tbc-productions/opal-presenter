"""ADS integration for the Modern workspace."""
from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.i18n import UiStrings
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.fluentstyle import get_fluent_dock_stylesheet

import PySide6QtAds as ads


class AdvancedDockWidget(ads.CDockWidget):
    """Expose the dock operations used by OpenLP on an ADS dock widget."""

    visibilityChanged = QtCore.Signal(bool)

    def __init__(self, parent=None, name=None, icon=None):
        super().__init__('', parent)
        self.setObjectName(name)
        if icon:
            self.setIcon(icon)
        self._open = True
        self.viewToggled.connect(self._view_toggled)
        self.setMinimumWidth(200)

    def _view_toggled(self, opened):
        self._open = opened
        self.visibilityChanged.emit(opened)

    def setDockVisible(self, visible):
        self._open = visible
        if self.dockManager() and self.isClosed() == visible:
            self.toggleView(visible)

    def isDockOpen(self):
        # Inactive tabs and collapsed auto-hide panels are still open workspace panes.
        return not self.isClosed() if self.dockManager() else self._open

    def raise_(self):
        self.toggleView(True)

    def setFeatures(self, features):
        if isinstance(features, QtWidgets.QDockWidget.DockWidgetFeature):
            flags = ads.CDockWidget.DockWidgetFeature.NoDockWidgetFeatures
            for qt_flag, ads_flag in (
                    (QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable,
                     ads.CDockWidget.DockWidgetFeature.DockWidgetClosable),
                    (QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable,
                     ads.CDockWidget.DockWidgetFeature.DockWidgetMovable),
                    (QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable,
                     ads.CDockWidget.DockWidgetFeature.DockWidgetFloatable)):
                if features & qt_flag:
                    flags |= ads_flag
            if features:
                flags |= (ads.CDockWidget.DockWidgetFeature.DockWidgetPinnable |
                          ads.CDockWidget.DockWidgetFeature.DockWidgetFocusable)
            features = flags
        super().setFeatures(features)

    def setFloating(self, floating):
        if floating:
            super().setFloating()
        elif self.isAutoHide():
            self.setAutoHide(False)


class AdvancedDockingMixin:
    """Route the main window's existing layout operations to the Modern dock manager."""

    def initialize_advanced_docking(self):
        ads.CDockManager.setConfigFlags(
            ads.CDockManager.eConfigFlag.DefaultOpaqueConfig |
            ads.CDockManager.eConfigFlag.FocusHighlighting |
            ads.CDockManager.eConfigFlag.AlwaysShowTabs |
            ads.CDockManager.eConfigFlag.EqualSplitOnInsertion |
            ads.CDockManager.eConfigFlag.DockAreaHideDisabledButtons |
            ads.CDockManager.eConfigFlag.DockAreaDynamicTabsMenuButtonVisibility)
        ads.CDockManager.setAutoHideConfigFlags(ads.CDockManager.eAutoHideFlag.DefaultAutoHideConfig)
        self.takeCentralWidget()
        self.dock_manager = ads.CDockManager(self)
        self.dock_manager.setStyleSheet(self.dock_manager.styleSheet() + get_fluent_dock_stylesheet())
        self.setCentralWidget(self.dock_manager)
        # Every workspace pane is an ordinary dock, including both controllers.
        self.preview_controller_dock = AdvancedDockWidget(self, 'preview_controller_dock', UiIcons().preview)
        self.preview_controller_dock.setWindowTitle(UiStrings().Preview)
        self.live_controller_dock = AdvancedDockWidget(self, 'live_controller_dock', UiIcons().live)
        self.live_controller_dock.setWindowTitle(UiStrings().Live)
        self.reset_controller_docks()

    def reset_controller_docks(self):
        """Place Preview and Live side by side for a factory layout."""
        docks = (self.preview_controller_dock, self.live_controller_dock)
        opened = [dock.isDockOpen() for dock in docks]
        blockers = [QtCore.QSignalBlocker(dock) for dock in docks]
        for dock in docks:
            if dock.isAutoHide():
                dock.setAutoHide(False)
            if dock.dockManager():
                self.dock_manager.removeDockWidget(dock)
        self.dock_manager.addDockWidget(ads.RightDockWidgetArea, self.preview_controller_dock)
        self.dock_manager.addDockWidget(
            ads.RightDockWidgetArea, self.live_controller_dock, self.preview_controller_dock.dockAreaWidget())
        self._show_dock_titles()
        for dock, visible in zip(docks, opened):
            dock.setDockVisible(visible)
        del blockers

    def dock_slide_controller(self, controller):
        """Attach a controller after its UI has been initialised."""
        dock = self.live_controller_dock if controller.is_live else self.preview_controller_dock
        dock.setWidget(controller.panel, ads.CDockWidget.eInsertMode.ForceNoScrollArea)
        self._show_dock_titles()
        # The dock tab supplies the controller name; keep the item title/status in the panel.
        controller.top_icon.hide()
        controller.type_label.hide()

    def _show_dock_titles(self):
        """Keep pane names and drag handles visible, including in older saved layouts."""
        for index in range(self.dock_manager.dockAreaCount()):
            area = self.dock_manager.dockArea(index)
            area.setDockAreaFlag(ads.CDockAreaWidget.eDockAreaFlag.HideSingleWidgetTitleBar, False)
            area.updateTitleBarVisibility()

    def set_controller_panel_visible(self, controller, visible):
        """Use workspace visibility rather than hiding a dock's content widget."""
        dock = getattr(self, f'{controller}_controller_dock', None)
        if dock is not None:
            # Menu/preset callers update settings themselves. Only user dock actions
            # should emit a visibility change back into those callers.
            with QtCore.QSignalBlocker(dock):
                dock.setDockVisible(visible)
        else:
            getattr(self, f'{controller}_controller').panel.setVisible(visible)

    def addDockWidget(self, area, dock, *args):
        areas = {
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea: ads.LeftDockWidgetArea,
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea: ads.RightDockWidgetArea,
            QtCore.Qt.DockWidgetArea.TopDockWidgetArea: ads.TopDockWidgetArea,
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea: ads.BottomDockWidgetArea,
        }
        opened = dock._open
        result = self.dock_manager.addDockWidget(areas[area], dock)
        dock.setDockVisible(opened)
        return result

    def removeDockWidget(self, dock):
        self.dock_manager.removeDockWidget(dock)

    def splitDockWidget(self, first, second, orientation):
        area = ads.BottomDockWidgetArea if orientation == QtCore.Qt.Orientation.Vertical else ads.RightDockWidgetArea
        return self.dock_manager.addDockWidget(area, second, first.dockAreaWidget())

    def tabifyDockWidget(self, first, second):
        area = first.dockAreaWidget()
        if area is not None and second.dockAreaWidget() is area:
            return area
        return self.dock_manager.addDockWidget(ads.CenterDockWidgetArea, second, area)

    def tabifiedDockWidgets(self, dock):
        area = dock.dockAreaWidget()
        return [item for item in area.dockWidgets() if item is not dock] if area else []

    def resizeDocks(self, docks, sizes, orientation):
        for dock, size in zip(docks, sizes):
            area = dock.dockAreaWidget()
            if not area:
                continue
            child = area
            splitter = area.parentSplitter()
            while splitter and splitter.orientation() != orientation:
                child = splitter
                splitter = splitter.parentWidget()
                if not isinstance(splitter, QtWidgets.QSplitter):
                    splitter = None
            if splitter:
                values = splitter.sizes()
                values[splitter.indexOf(child)] = size
                splitter.setSizes(values)

    def saveState(self, version=0):
        return self.dock_manager.saveState(version)

    def restoreState(self, state, version=0):
        if not state:
            return False
        restored = self.dock_manager.restoreState(state, version)
        # Missing panes stay registered but unassigned; opening one would otherwise float it.
        right_docks = (self.preview_controller_dock, self.live_controller_dock,
                       getattr(self, 'projector_manager_dock', None), getattr(self, 'cloud_library_dock', None))
        for dock in self.dock_manager.dockWidgetsMap().values():
            if dock.dockAreaWidget() is None and not dock.isAutoHide():
                opened = dock.isDockOpen()
                area = ads.RightDockWidgetArea if dock in right_docks else ads.LeftDockWidgetArea
                self.dock_manager.addDockWidget(area, dock)
                dock.setDockVisible(opened)
        self._show_dock_titles()
        return restored
