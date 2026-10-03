"""Exercise real ADS floating, auto-hide, close and restore operations."""
import pytest
from PySide6 import QtCore, QtTest, QtWidgets

from openlp.core.common.platform import is_win

pytestmark = pytest.mark.skipif(not is_win(), reason='Modern docking is Windows-only')


@pytest.fixture
def workspace(settings):
    from openlp.core.ui.advanceddocking import AdvancedDockingMixin, AdvancedDockWidget

    class Workspace(AdvancedDockingMixin, QtWidgets.QMainWindow):
        pass

    window = Workspace()
    window.setCentralWidget(QtWidgets.QLabel('Slides'))
    window.initialize_advanced_docking()
    window.resize(1000, 700)
    docks = [AdvancedDockWidget(window, name) for name in ('service', 'library', 'themes', 'projectors')]
    for dock in docks:
        dock.setWindowTitle(dock.objectName())
        dock.setWidget(QtWidgets.QLabel(dock.objectName()))
    window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, docks[0])
    window.splitDockWidget(docks[0], docks[1], QtCore.Qt.Orientation.Vertical)
    window.tabifyDockWidget(docks[1], docks[2])
    docks[3].setDockVisible(False)
    window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, docks[3])
    window.show()
    QtWidgets.QApplication.processEvents()
    yield window, docks
    for floating in window.dock_manager.floatingWidgets():
        floating.hide()
    window.hide()
    window.deleteLater()


def test_tabs_and_initially_closed_pane(workspace):
    window, (service, library, themes, projectors) = workspace
    assert library.dockAreaWidget() is themes.dockAreaWidget()
    assert service.dockAreaWidget() is not library.dockAreaWidget()
    assert window.tabifiedDockWidgets(library) == [themes]
    assert library.isDockOpen() and themes.isDockOpen()
    assert projectors.isClosed()
    projectors.setDockVisible(True)
    assert not projectors.isClosed()


def test_float_autohide_and_closed_state_round_trip(workspace):
    import PySide6QtAds as ads
    window, (service, library, themes, projectors) = workspace
    service.setFloating(True)
    library.setAutoHide(True, ads.SideBarLeft)
    themes.setDockVisible(False)
    saved = window.saveState()
    window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, service)
    library.setAutoHide(False)
    themes.setDockVisible(True)
    assert window.restoreState(saved)
    assert service.isInFloatingContainer()
    assert library.isAutoHide()
    assert library.autoHideLocation() == ads.SideBarLeft
    assert themes.isClosed()
    assert not themes.isDockOpen()
    assert library.isDockOpen()


def test_closing_emits_visibility_and_reopening_retains_content(workspace):
    window, (_, library, _, _) = workspace
    content = library.widget()
    spy = QtTest.QSignalSpy(library.visibilityChanged)
    library.toggleView(False)
    assert spy.count() == 1 and spy.at(0) == [False]
    assert not library.isDockOpen()
    library.setDockVisible(True)
    assert spy.at(1) == [True]
    assert library.widget() is content


def test_tab_group_in_floating_window_round_trip(workspace):
    window, (_, library, themes, _) = workspace
    library.setFloating(True)
    window.tabifyDockWidget(library, themes)
    saved = window.saveState()
    window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, library)
    window.tabifyDockWidget(library, themes)
    assert window.restoreState(saved)
    assert library.isInFloatingContainer() and themes.isInFloatingContainer()
    assert library.dockAreaWidget() is themes.dockAreaWidget()


def test_lock_disables_float_move_close_and_pin(workspace):
    import PySide6QtAds as ads
    _, (service, _, _, _) = workspace
    service.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
    assert service.features() == ads.CDockWidget.DockWidgetFeature.NoDockWidgetFeatures
    service.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable |
                        QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable |
                        QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
    assert service.features() & ads.CDockWidget.DockWidgetFeature.DockWidgetPinnable
