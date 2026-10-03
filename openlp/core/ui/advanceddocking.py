"""ADS integration for the Modern workspace; Classic keeps Qt's dock widgets."""
from PySide6 import QtCore, QtWidgets
from openlp.core.common.i18n import translate
from openlp.core.common.platform import is_win

if is_win():
    import PySide6QtAds as ads
else:
    ads = None


class AdvancedDockWidget(ads.CDockWidget if ads else QtWidgets.QWidget):
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
            ads.CDockManager.eConfigFlag.EqualSplitOnInsertion |
            ads.CDockManager.eConfigFlag.DockAreaHideDisabledButtons |
            ads.CDockManager.eConfigFlag.HideSingleCentralWidgetTitleBar)
        ads.CDockManager.setAutoHideConfigFlags(ads.CDockManager.eAutoHideFlag.DefaultAutoHideConfig)
        content = self.takeCentralWidget()
        self.dock_manager = ads.CDockManager(self)
        self.setCentralWidget(self.dock_manager)
        self.controller_dock = ads.CDockWidget(translate('OpenLP.MainWindow', 'Slide controllers'))
        self.controller_dock.setObjectName('slide_controllers_dock')
        self.controller_dock.setWidget(content, ads.CDockWidget.eInsertMode.ForceNoScrollArea)
        self.dock_manager.setCentralWidget(self.controller_dock)

    def addDockWidget(self, area, dock, *args):
        if not getattr(self, 'dock_manager', None):
            return super().addDockWidget(area, dock, *args)
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
        if not getattr(self, 'dock_manager', None):
            return super().removeDockWidget(dock)
        self.dock_manager.removeDockWidget(dock)

    def splitDockWidget(self, first, second, orientation):
        if not getattr(self, 'dock_manager', None):
            return super().splitDockWidget(first, second, orientation)
        area = ads.BottomDockWidgetArea if orientation == QtCore.Qt.Orientation.Vertical else ads.RightDockWidgetArea
        return self.dock_manager.addDockWidget(area, second, first.dockAreaWidget())

    def tabifyDockWidget(self, first, second):
        if not getattr(self, 'dock_manager', None):
            return super().tabifyDockWidget(first, second)
        return self.dock_manager.addDockWidget(ads.CenterDockWidgetArea, second, first.dockAreaWidget())

    def tabifiedDockWidgets(self, dock):
        if not getattr(self, 'dock_manager', None):
            return super().tabifiedDockWidgets(dock)
        area = dock.dockAreaWidget()
        return [item for item in area.dockWidgets() if item is not dock] if area else []

    def resizeDocks(self, docks, sizes, orientation):
        if not getattr(self, 'dock_manager', None):
            return super().resizeDocks(docks, sizes, orientation)
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
        if not getattr(self, 'dock_manager', None):
            return super().saveState(version)
        return self.dock_manager.saveState(version)

    def restoreState(self, state, version=0):
        if not getattr(self, 'dock_manager', None):
            return super().restoreState(state, version)
        if not state:
            return False
        return self.dock_manager.restoreState(state, version)
