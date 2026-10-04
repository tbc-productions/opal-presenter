"""Presentation discovery and cached documents must not start external apps."""
import plistlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore

from openlp.core.common.registry import Registry
from openlp.plugins.presentations.lib.applicationdiscovery import is_com_registered
from openlp.plugins.presentations.lib.impresscontroller import ImpressController, ImpressDocument
from openlp.plugins.presentations.lib.keynotecontroller import KeynoteController
from openlp.plugins.presentations.lib.maclocontroller import MacLOController, MacLODocument
from openlp.plugins.presentations.lib.powerpointcontroller import PowerpointController
from openlp.plugins.presentations.lib.powerpointmaccontroller import PowerPointMacController
from openlp.plugins.presentations.lib.presentationtab import PresentationTab
from openlp.plugins.presentations.presentationplugin import PresentationPlugin


def test_plugin_initialisation_does_not_launch_controllers(settings):
    plugin = object.__new__(PresentationPlugin)
    plugin.media_item = MagicMock()
    plugin.controllers = {'Keynote': MagicMock(), 'Powerpoint': MagicMock(), 'Impress': MagicMock()}
    with patch('openlp.plugins.presentations.presentationplugin.Plugin.initialise'):
        plugin.initialise()
    for controller in plugin.controllers.values():
        controller.start_process.assert_not_called()
    plugin.media_item.build_file_mask_string.assert_called_once_with()


def test_enabling_controller_does_not_launch_it(settings):
    Registry().register('settings_form', MagicMock())
    settings.setValue('presentations/Keynote', QtCore.Qt.CheckState.Unchecked)
    controller = MagicMock()
    controller.name = controller.display_name = 'Keynote'
    form = PresentationTab(None, 'presentations', None, {'Keynote': controller}, None)
    form.presenter_check_boxes['Keynote'].setChecked(True)
    form.activated = True
    form.save()
    assert settings.value('presentations/Keynote') == QtCore.Qt.CheckState.Checked
    controller.start_process.assert_not_called()
    controller.kill.assert_not_called()


@pytest.mark.parametrize('version,available', [('10.0', False), ('10.1', True), ('14.4', True), ('bad', False)])
def test_keynote_availability_reads_bundle_without_apple_events(tmp_path, version, available):
    app = tmp_path / 'Keynote.app'
    info = app / 'Contents' / 'Info.plist'
    info.parent.mkdir(parents=True)
    info.write_bytes(plistlib.dumps({'CFBundleShortVersionString': version}))
    controller = object.__new__(KeynoteController)
    controller.keynote_app = app
    controller.applescript = MagicMock()
    with patch('openlp.plugins.presentations.lib.keynotecontroller.APPLESCRIPT_AVAILABLE', True):
        assert controller.check_available() is available
    controller.applescript.call.assert_not_called()


@pytest.mark.parametrize('version,available', [('14.0', False), ('15.0', True), ('16.100', True), ('bad', False)])
def test_powerpoint_mac_availability_reads_bundle_without_apple_events(tmp_path, version, available):
    app = tmp_path / 'Microsoft PowerPoint.app'
    info = app / 'Contents' / 'Info.plist'
    info.parent.mkdir(parents=True)
    info.write_bytes(plistlib.dumps({'CFBundleShortVersionString': version}))
    controller = object.__new__(PowerPointMacController)
    controller.applescript = MagicMock()
    with patch('openlp.plugins.presentations.lib.powerpointmaccontroller.APPLESCRIPT_AVAILABLE', True), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.is_macosx', return_value=True), \
            patch('openlp.plugins.presentations.lib.powerpointmaccontroller.find_macos_application', return_value=app):
        assert controller.check_available() is available
    controller.applescript.call.assert_not_called()


def test_windows_powerpoint_discovery_does_not_create_com_instance(settings):
    controller = PowerpointController(MagicMock())
    with patch('openlp.plugins.presentations.lib.powerpointcontroller.is_win', return_value=True), \
            patch('openlp.plugins.presentations.lib.powerpointcontroller.is_com_registered',
                  side_effect=[False, True]), \
            patch('openlp.plugins.presentations.lib.powerpointcontroller.Dispatch', create=True) as dispatch:
        assert controller.check_available()
    assert controller.com_obj_name == 'PowerPoint.Application.16'
    dispatch.assert_not_called()


@pytest.mark.parametrize('registered', [False, True])
def test_com_discovery_reads_registry(registered):
    winreg = MagicMock()
    if not registered:
        winreg.OpenKey.side_effect = FileNotFoundError
    with patch.dict('sys.modules', {'winreg': winreg}):
        assert is_com_registered('PowerPoint.Application') is registered
    winreg.OpenKey.assert_called_once_with(winreg.HKEY_CLASSES_ROOT, 'PowerPoint.Application\\CLSID')


def test_unused_impress_shutdown_does_not_start_application(settings):
    controller = ImpressController(MagicMock())
    with patch.object(controller, 'get_uno_desktop') as uno, \
            patch.object(controller, 'get_com_desktop') as com:
        controller.kill()
    uno.assert_not_called()
    com.assert_not_called()


def test_impress_first_load_starts_application_on_windows(settings, tmp_path):
    controller = ImpressController(MagicMock())
    document = ImpressDocument(controller, tmp_path / 'slides.odp')
    with patch('openlp.plugins.presentations.lib.impresscontroller.is_win', return_value=True), \
            patch.object(controller, 'get_com_desktop', return_value=None) as desktop, \
            patch.object(controller, 'start_process') as start:
        assert not document.load_presentation()
    start.assert_called_once_with()
    assert desktop.call_count == 2


@pytest.mark.parametrize('becomes_ready', [True, False])
def test_impress_waits_for_cold_launch(settings, becomes_ready):
    controller = ImpressController(MagicMock())
    instance = MagicMock()
    attempts = [ConnectionError] * 4 + [instance] if becomes_ready else ConnectionError
    with patch('openlp.plugins.presentations.lib.impresscontroller.uno', create=True), \
            patch('openlp.plugins.presentations.lib.impresscontroller.get_uno_instance',
                  side_effect=attempts) as resolve, \
            patch('openlp.plugins.presentations.lib.impresscontroller.time.sleep') as sleep, \
            patch.object(controller, 'start_process') as start, \
            patch.object(controller, 'toggle_presentation_screen'):
        desktop = controller.get_uno_desktop()
    start.assert_called_once_with()
    if becomes_ready:
        assert desktop is instance.ServiceManager.createInstanceWithContext.return_value
        assert sleep.call_count == 4
    else:
        assert desktop is None
        assert resolve.call_count == 30
        assert sleep.call_count == 29


def test_maclo_cached_document_and_shutdown_do_not_launch_helper(settings, tmp_path):
    with patch.object(MacLOController, '_start_server') as start:
        controller = MacLOController(MagicMock())
        document = MacLODocument(controller, tmp_path / 'slides.odp')
        document.get_slide_image_paths()
        document.close_presentation()
        controller.kill()
    start.assert_not_called()


def test_maclo_reports_failed_first_launch(settings, tmp_path):
    controller = MacLOController(MagicMock())
    document = MacLODocument(controller, tmp_path / 'slides.odp')
    with patch.object(controller, 'start_process', side_effect=ConnectionError):
        assert not document.load_presentation()
    assert not controller._process_started


def test_maclo_first_load_launches_once_and_can_restart_after_shutdown(settings, tmp_path):
    controller = MacLOController(MagicMock())
    client = MagicMock()
    client.load_presentation.return_value = False

    def start_server():
        controller.server_process = MagicMock()

    with patch.object(controller, '_start_server', side_effect=start_server) as start, \
            patch('openlp.plugins.presentations.lib.maclocontroller.Proxy', return_value=client, create=True), \
            patch('openlp.plugins.presentations.lib.maclocontroller.ScreenList'):
        for _ in range(2):
            document = MacLODocument(controller, tmp_path / 'slides.odp')
            assert not document.load_presentation()
        start.assert_called_once_with()
        client.start_process.assert_called_once_with()
        controller.kill()
        document = MacLODocument(controller, tmp_path / 'slides.odp')
        assert not document.load_presentation()
        assert start.call_count == 2
        assert client.start_process.call_count == 2
