from unittest.mock import MagicMock, patch
import ctypes
import plistlib
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.mac_permissions import (
    _DraggableFileIcon, _accessibility_drag_target, _launching_app_bundle, _open_privacy_settings, _running_app_bundle,
    request_post_event_access, request_presentation_permissions)


def test_running_app_bundle_uses_the_current_executable(tmp_path):
    bundle = tmp_path / 'OpenLP+.app'
    (bundle / 'Contents' / 'MacOS').mkdir(parents=True)
    (bundle / 'Contents' / 'Info.plist').touch()
    executable = bundle / 'Contents' / 'MacOS' / 'OpenLP+'

    with patch('openlp.core.common.mac_permissions.sys.executable', str(executable)):
        assert _running_app_bundle() == bundle
    python_bundle = tmp_path / 'Python.app'
    (python_bundle / 'Contents' / 'MacOS').mkdir(parents=True)
    (python_bundle / 'Contents' / 'Info.plist').touch()
    python_executable = python_bundle / 'Contents' / 'MacOS' / 'Python'
    with patch('openlp.core.common.mac_permissions.sys.executable', str(python_executable)):
        assert _running_app_bundle() == python_bundle


def test_development_drag_target_resolves_the_actual_python_executable(tmp_path):
    executable = tmp_path / 'python3.14'
    executable.touch()
    launcher = tmp_path / 'venv' / 'bin' / 'python'
    launcher.parent.mkdir(parents=True)
    launcher.symlink_to(executable)

    with patch('openlp.core.common.mac_permissions.sys.executable', str(launcher)), \
            patch('openlp.core.common.mac_permissions._launching_app_bundle', return_value=None):
        target, label = _accessibility_drag_target()

    assert target == executable
    assert label == f'Python {sys.version_info.major}.{sys.version_info.minor}'


def test_development_drag_target_uses_the_ide_instead_of_its_python(tmp_path):
    ide = tmp_path / 'Example IDE.app'
    (ide / 'Contents').mkdir(parents=True)
    with (ide / 'Contents' / 'Info.plist').open('wb') as info_file:
        plistlib.dump({'CFBundleDisplayName': 'Widget Workshop'}, info_file)
    helper = ide / 'Contents' / 'Frameworks' / 'IDE Helper.app' / 'Contents' / 'MacOS' / 'IDE Helper'
    parents = [MagicMock(stdout='12 /path/to/python3.14\n'), MagicMock(stdout='13 /bin/zsh\n'),
               MagicMock(stdout=f'14 {helper}\n')]

    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.os.getppid', return_value=11), \
            patch('openlp.core.common.mac_permissions.subprocess.run', side_effect=parents) as run, \
            patch('openlp.core.common.mac_permissions._running_app_bundle', return_value=None):
        target, label = _accessibility_drag_target()

    assert target == ide
    assert label == 'Widget Workshop'
    assert [call.args[0][4] for call in run.call_args_list] == ['-o', '-o', '-o']
    assert [call.args[0][3] for call in run.call_args_list] == ['11', '12', '13']


def test_packaged_launch_uses_its_own_app(tmp_path):
    bundle = tmp_path / 'OpenLP+.app'
    with patch('openlp.core.common.mac_permissions._running_app_bundle', return_value=bundle), \
            patch('openlp.core.common.mac_permissions._launching_app_bundle') as find_launcher:
        assert _accessibility_drag_target() == (bundle, 'OpenLP+')
    find_launcher.assert_not_called()


def test_launcher_detection_stops_if_parent_lookup_fails():
    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.subprocess.run', side_effect=OSError):
        assert _launching_app_bundle() is None


def test_native_accessibility_request_sets_prompt_option_and_releases_dictionary():
    services, foundation = MagicMock(), MagicMock()
    services.AXIsProcessTrustedWithOptions.return_value = False
    foundation.CFDictionaryCreate.return_value = 123
    with patch('openlp.core.common.mac_permissions.ctypes.CDLL', side_effect=[services, foundation]), \
            patch('openlp.core.common.mac_permissions.ctypes.c_void_p.in_dll',
                  side_effect=[ctypes.c_void_p(456), ctypes.c_void_p(789)]):
        assert not request_post_event_access()

    arguments = foundation.CFDictionaryCreate.call_args.args
    assert arguments[1][0] == 456
    assert arguments[2][0] == 789
    services.AXIsProcessTrustedWithOptions.assert_called_once_with(123)
    foundation.CFRelease.assert_called_once_with(123)


def test_app_icon_drag_contains_the_target_file_url(tmp_path):
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert application is not None
    bundle = tmp_path / 'OpenLP+.app'
    resources = bundle / 'Contents' / 'Resources'
    resources.mkdir(parents=True)
    with (bundle / 'Contents' / 'Info.plist').open('wb') as info_file:
        plistlib.dump({'CFBundleIconFile': 'sample.png'}, info_file)
    sample_icon = QtGui.QPixmap(64, 64)
    sample_icon.fill(QtCore.Qt.GlobalColor.red)
    sample_icon.save(str(resources / 'sample.png'))
    icon = _DraggableFileIcon(bundle, 'OpenLP+.app', None)
    assert icon.pixmap().toImage().pixelColor(32, 32) == QtGui.QColor('red')
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
                      if isinstance(widget, QtWidgets.QDialog) and widget.isVisible())
        try:
            buttons = {button.text(): button for button in dialog.findChildren(QtWidgets.QPushButton)}
            assert any('Access needed: Accessibility, Screen Recording' in label.text()
                       for label in dialog.findChildren(QtWidgets.QLabel))
            graphics.CGRequestPostEventAccess.assert_not_called()
            buttons['Request Access'].click()
            buttons['Open Accessibility Settings'].click()
            buttons['Open Screen Recording Settings'].click()
            buttons['Check Again'].click()
            assert dialog.isVisible()
            graphics.CGPreflightPostEventAccess.return_value = True
            graphics.CGPreflightScreenCaptureAccess.return_value = True
            buttons['Check Again'].click()
            assert not dialog.isVisible()
        finally:
            dialog.accept()

    QtCore.QTimer.singleShot(0, use_dialog)
    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.ctypes.CDLL', return_value=graphics), \
            patch('openlp.core.common.mac_permissions.request_post_event_access') as request_access, \
            patch('openlp.core.common.mac_permissions._launching_app_bundle', return_value=None), \
            patch('openlp.core.common.mac_permissions.QtGui.QDesktopServices.openUrl', return_value=True) as open_url:
        request_presentation_permissions(parent)

    request_access.assert_called_once_with()
    graphics.CGRequestScreenCaptureAccess.assert_called_once_with()
    assert [call.args[0].toString() for call in open_url.call_args_list] == [
        'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility',
        'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture']
    parent.close()


def test_accessibility_dialog_offers_drag_for_app_and_development_run(tmp_path):
    graphics = MagicMock()
    graphics.CGPreflightPostEventAccess.return_value = False
    graphics.CGPreflightScreenCaptureAccess.return_value = True
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert application is not None
    parent = QtWidgets.QWidget()
    bundle = tmp_path / 'OpenLP+.app'
    bundle.mkdir()
    interpreter = tmp_path / 'python3.14'
    interpreter.touch()
    offered_icons = []
    source_notes = []

    def inspect_dialog():
        dialog = next(widget for widget in QtWidgets.QApplication.topLevelWidgets()
                      if isinstance(widget, QtWidgets.QDialog) and widget.isVisible())
        offered_icons.append(dialog.findChildren(_DraggableFileIcon))
        source_notes.append([label.text() for label in dialog.findChildren(QtWidgets.QLabel)
                             if 'Or use + to add this file' in label.text()])
        dialog.accept()

    with patch('openlp.core.common.mac_permissions.is_macosx', return_value=True), \
            patch('openlp.core.common.mac_permissions.ctypes.CDLL', return_value=graphics), \
            patch('openlp.core.common.mac_permissions._accessibility_drag_target',
                  side_effect=[(bundle, 'OpenLP+.app'), (interpreter, 'Python 3.14')]):
        QtCore.QTimer.singleShot(0, inspect_dialog)
        request_presentation_permissions(parent)
        QtCore.QTimer.singleShot(0, inspect_dialog)
        request_presentation_permissions(parent)

    assert len(offered_icons[0]) == 1
    assert offered_icons[0][0].file_path == bundle
    assert len(offered_icons[1]) == 1
    assert offered_icons[1][0].file_path == interpreter
    assert source_notes[0] == []
    assert str(interpreter) in source_notes[1][0]
    parent.close()


def test_privacy_settings_link_falls_back_to_system_settings():
    with patch('openlp.core.common.mac_permissions.QtGui.QDesktopServices.openUrl', return_value=False), \
            patch('openlp.core.common.mac_permissions.subprocess.run') as run:
        _open_privacy_settings('Privacy_Accessibility')

    run.assert_called_once_with(['/usr/bin/open', '-a', 'System Settings'], check=False)
