from unittest.mock import MagicMock, patch

from PySide6 import QtCore, QtWidgets

from openlp.core.common.mac_permissions import _open_privacy_settings, request_presentation_permissions


def test_presentation_permissions_do_not_interrupt_startup_when_granted():
    graphics = MagicMock()
    graphics.CGPreflightPostEventAccess.return_value = True
    graphics.CGPreflightScreenCaptureAccess.return_value = True
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
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


def test_privacy_settings_link_falls_back_to_system_settings():
    with patch('openlp.core.common.mac_permissions.QtGui.QDesktopServices.openUrl', return_value=False), \
            patch('openlp.core.common.mac_permissions.subprocess.run') as run:
        _open_privacy_settings('Privacy_Accessibility')

    run.assert_called_once_with(['/usr/bin/open', '-a', 'System Settings'], check=False)
