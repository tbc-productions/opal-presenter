from unittest.mock import MagicMock, patch

from PySide6 import QtCore, QtWidgets

from openlp.core.common.mac_permissions import (
    _DraggableAppIcon, _open_privacy_settings, _running_app_bundle, request_presentation_permissions)


def test_running_app_bundle_uses_the_current_executable(tmp_path):
    bundle = tmp_path / 'OpenLP+.app'
    (bundle / 'Contents' / 'MacOS').mkdir(parents=True)
    (bundle / 'Contents' / 'Info.plist').touch()
    executable = bundle / 'Contents' / 'MacOS' / 'OpenLP+'

    with patch('openlp.core.common.mac_permissions.sys.executable', str(executable)):
        assert _running_app_bundle() == bundle
    python_executable = tmp_path / 'Python.app' / 'Contents' / 'MacOS' / 'Python'
    with patch('openlp.core.common.mac_permissions.sys.executable', str(python_executable)):
        assert _running_app_bundle() is None


def test_app_icon_drag_contains_the_app_bundle_file_url(tmp_path):
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert application is not None
    bundle = tmp_path / 'OpenLP+.app'
    bundle.mkdir()
    icon = _DraggableAppIcon(bundle, None)
    icon._drag_start_pos = QtCore.QPoint(0, 0)
    event = MagicMock()
    event.buttons.return_value = QtCore.Qt.MouseButton.LeftButton
    event.pos.return_value = QtCore.QPoint(100, 100)

    with patch('openlp.core.common.mac_permissions.QtGui.QDrag') as drag_type:
        icon.mouseMoveEvent(event)

    mime_data = drag_type.return_value.setMimeData.call_args.args[0]
    assert mime_data.hasUrls()
    assert [url.toLocalFile() for url in mime_data.urls()] == [str(bundle)]
    drag_type.return_value.exec.assert_called_once_with(QtCore.Qt.DropAction.CopyAction)
    icon.close()


def test_presentation_permissions_do_not_interrupt_startup_when_granted():
    graphics = MagicMock()
    graphics.CGPreflightPostEventAccess.return_value = True
    graphics.CGPreflightScreenCaptureAccess.return_value = True
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert application is not None
    parent = QtWidgets.QWidget()

    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.ctypes.CDLL', return_value=graphics):
        request_presentation_permissions(parent)

    graphics.CGRequestPostEventAccess.assert_not_called()
    graphics.CGRequestScreenCaptureAccess.assert_not_called()
    parent.close()


def test_missing_permissions_offer_native_request_and_system_settings():
    graphics = MagicMock()
    graphics.CGPreflightPostEventAccess.return_value = False
    graphics.CGPreflightScreenCaptureAccess.return_value = False
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert application is not None
    parent = QtWidgets.QWidget()

    def use_dialog():
        dialog = next(widget for widget in QtWidgets.QApplication.topLevelWidgets()
                      if isinstance(widget, QtWidgets.QDialog))
        try:
            buttons = {button.text(): button for button in dialog.findChildren(QtWidgets.QPushButton)}
            assert 'Missing access: Accessibility, Screen Recording' in dialog.findChildren(QtWidgets.QLabel)[1].text()
            graphics.CGRequestPostEventAccess.assert_not_called()
            buttons['Ask macOS for Access'].click()
            buttons['Open Accessibility Settings'].click()
            buttons['Open Screen Recording Settings'].click()
            buttons['Done'].click()
        finally:
            dialog.accept()

    QtCore.QTimer.singleShot(0, use_dialog)
    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.ctypes.CDLL', return_value=graphics), \
            patch('openlp.core.common.mac_permissions.QtGui.QDesktopServices.openUrl', return_value=True) as open_url:
        request_presentation_permissions(parent)

    graphics.CGRequestPostEventAccess.assert_called_once_with()
    graphics.CGRequestScreenCaptureAccess.assert_called_once_with()
    assert [call.args[0].toString() for call in open_url.call_args_list] == [
        'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility',
        'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture']
    parent.close()


def test_accessibility_dialog_offers_drag_only_when_running_as_app(tmp_path):
    graphics = MagicMock()
    graphics.CGPreflightPostEventAccess.return_value = False
    graphics.CGPreflightScreenCaptureAccess.return_value = True
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert application is not None
    parent = QtWidgets.QWidget()
    bundle = tmp_path / 'OpenLP+.app'
    bundle.mkdir()
    offered_icons = []

    def inspect_dialog():
        dialog = next(widget for widget in QtWidgets.QApplication.topLevelWidgets()
                      if isinstance(widget, QtWidgets.QDialog))
        offered_icons.append(dialog.findChildren(_DraggableAppIcon))
        dialog.accept()

    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.ctypes.CDLL', return_value=graphics), \
            patch('openlp.core.common.mac_permissions._running_app_bundle', side_effect=[bundle, None]):
        QtCore.QTimer.singleShot(0, inspect_dialog)
        request_presentation_permissions(parent)
        QtCore.QTimer.singleShot(0, inspect_dialog)
        request_presentation_permissions(parent)

    assert len(offered_icons[0]) == 1
    assert offered_icons[0][0].bundle == bundle
    assert offered_icons[1] == []
    parent.close()


def test_privacy_settings_link_falls_back_to_system_settings():
    with patch('openlp.core.common.mac_permissions.QtGui.QDesktopServices.openUrl', return_value=False), \
            patch('openlp.core.common.mac_permissions.subprocess.run') as run:
        _open_privacy_settings('Privacy_Accessibility')

    run.assert_called_once_with(['/usr/bin/open', '-a', 'System Settings'], check=False)
