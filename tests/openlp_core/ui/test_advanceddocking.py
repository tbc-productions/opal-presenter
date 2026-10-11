"""Exercise real ADS floating, auto-hide, close and restore operations."""
import pytest
from PySide6 import QtCore, QtTest
from openlp.core.widgets import fluent as QtWidgets


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


def test_controllers_are_independent_docks_and_restore_with_other_panes(workspace):
    import PySide6QtAds as ads
    window, (_, library, _, _) = workspace
    preview, live = window.preview_controller_dock, window.live_controller_dock
    assert window.dock_manager.centralWidget() is None
    assert preview.dockAreaWidget() is not live.dockAreaWidget()
    for dock in (preview, live):
        dock.setWidget(QtWidgets.QLabel(dock.windowTitle()))
        assert dock.features() & ads.CDockWidget.DockWidgetFeature.DockWidgetMovable
        assert dock.features() & ads.CDockWidget.DockWidgetFeature.DockWidgetClosable
    window.tabifyDockWidget(library, preview)
    live.setFloating(True)
    preview.setDockVisible(False)
    saved = window.saveState()
    window.reset_controller_docks()
    preview.setDockVisible(True)
    assert window.restoreState(saved)
    assert preview.dockAreaWidget() is library.dockAreaWidget()
    assert preview.isClosed()
    assert live.isInFloatingContainer()
    window.set_controller_panel_visible('preview', True)
    assert preview.isDockOpen()


def test_tabs_dropdown_only_appears_for_multiple_tabs(workspace):
    import PySide6QtAds as ads
    window, (service, library, themes, _) = workspace
    assert service.dockAreaWidget().titleBarButton(ads.TitleBarButtonTabsMenu).isHidden()
    assert not library.dockAreaWidget().titleBarButton(ads.TitleBarButtonTabsMenu).isHidden()
    themes.setDockVisible(False)
    QtWidgets.QApplication.processEvents()
    assert library.dockAreaWidget().titleBarButton(ads.TitleBarButtonTabsMenu).isHidden()


def test_attaching_controller_moves_content_out_of_fixed_splitter(workspace):
    from types import SimpleNamespace
    window, _ = workspace
    splitter = QtWidgets.QSplitter(window)
    panel = QtWidgets.QWidget(splitter)
    controller = SimpleNamespace(is_live=False, panel=panel,
                                 top_icon=QtWidgets.QLabel(panel), type_label=QtWidgets.QLabel(panel))
    window.dock_slide_controller(controller)
    assert splitter.count() == 0
    assert window.preview_controller_dock.widget() is panel
    assert controller.top_icon.isHidden() and controller.type_label.isHidden()
    window.set_controller_panel_visible('preview', False)
    window.set_controller_panel_visible('preview', True)
    assert window.preview_controller_dock.widget() is panel


def test_factory_reset_preserves_visibility_and_clears_floating_autohide(workspace):
    import PySide6QtAds as ads
    window, _ = workspace
    preview, live = window.preview_controller_dock, window.live_controller_dock
    preview.setFloating(True)
    live.setAutoHide(True, ads.SideBarRight)
    preview.setDockVisible(False)
    spy = QtTest.QSignalSpy(preview.visibilityChanged)
    window.reset_controller_docks()
    assert preview.isClosed()
    assert not preview.isInFloatingContainer()
    assert not live.isAutoHide()
    assert live.isDockOpen()
    assert spy.count() == 0


def test_legacy_central_controller_layout_restores_with_new_docks(workspace):
    import PySide6QtAds as ads
    window, (service, _, _, _) = workspace
    legacy = ads.CDockManager()
    central = ads.CDockWidget('Slide controllers')
    central.setObjectName('slide_controllers_dock')
    central.setWidget(QtWidgets.QLabel('Slides'))
    legacy.setCentralWidget(central)
    old_service = ads.CDockWidget('Service')
    old_service.setObjectName('service')
    old_service.setWidget(QtWidgets.QLabel('Service'))
    legacy.addDockWidget(ads.LeftDockWidgetArea, old_service)
    assert window.restoreState(legacy.saveState())
    assert service.dockAreaWidget() is not None
    assert window.preview_controller_dock.dockAreaWidget() is not None
    assert window.live_controller_dock.dockAreaWidget() is not None
    legacy.deleteLater()


def test_controller_titles_visible_after_restoring_hidden_title_bars(workspace):
    import PySide6QtAds as ads
    window, _ = workspace
    docks = (window.preview_controller_dock, window.live_controller_dock)
    for dock in docks:
        dock.setWidget(QtWidgets.QLabel('Service item'))
        dock.dockAreaWidget().setDockAreaFlag(ads.CDockAreaWidget.eDockAreaFlag.HideSingleWidgetTitleBar, True)
    saved = window.saveState()
    assert window.restoreState(saved)
    QtWidgets.QApplication.processEvents()
    assert [dock.tabWidget().text() for dock in docks] == ['Preview', 'Live']
    for dock in docks:
        assert not dock.dockAreaWidget().titleBar().isHidden()
        assert not dock.tabWidget().isHidden()
