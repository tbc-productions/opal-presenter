"""Help macOS users grant access needed for native presentations."""

import ctypes
import logging
import os
import plistlib
import subprocess
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.platform import is_macosx


log = logging.getLogger(__name__)

_PERMISSIONS = (
    ('Accessibility', 'CGPreflightPostEventAccess', 'CGRequestPostEventAccess', 'Privacy_Accessibility'),
    ('Screen Recording', 'CGPreflightScreenCaptureAccess', 'CGRequestScreenCaptureAccess',
     'Privacy_ScreenCapture'),
)


def _running_app_bundle():
    """Find the app bundle containing the current executable, if there is one."""
    executable = Path(sys.executable).absolute()
    for parent in executable.parents:
        if (parent.suffix == '.app' and executable.parent == parent / 'Contents' / 'MacOS' and
                (parent / 'Contents' / 'Info.plist').is_file()):
            return parent
    return None


def _accessibility_drag_target():
    """Offer the owning app, including the IDE/terminal responsible for a source run."""
    bundle = _running_app_bundle()
    if bundle:
        return bundle, _app_display_name(bundle)
    launcher = _launching_app_bundle()
    if launcher:
        return launcher, _app_display_name(launcher)
    executable = Path(sys.executable).resolve()
    if executable.is_file():
        label = translate('OpenLP.MacPermissions', 'Python {version}').format(
            version=f'{sys.version_info.major}.{sys.version_info.minor}')
        return executable, label
    return None, None


def _app_display_name(bundle):
    """Use the app's own display name instead of assuming its folder name."""
    try:
        with (bundle / 'Contents' / 'Info.plist').open('rb') as info_file:
            info = plistlib.load(info_file)
        return info.get('CFBundleDisplayName') or info.get('CFBundleName') or bundle.stem
    except (OSError, ValueError):
        return bundle.stem


def _launching_app_bundle():
    """Follow source-run parents through shells/debuggers to their containing GUI app.

    TCC attributes IDE and terminal launches to that app. In particular, a
    debugger's interpreter path alone is not the permission identity. Do not
    read process arguments, which can contain debugger credentials.
    """
    if not is_macosx():
        return None
    pid = os.getppid()
    seen = set()
    try:
        while pid > 1 and pid not in seen and len(seen) < 32:
            seen.add(pid)
            result = subprocess.run(['/bin/ps', '-ww', '-p', str(pid), '-o', 'ppid=,comm='],
                                    check=True, capture_output=True, text=True, timeout=2)
            parent_pid, executable = result.stdout.strip().split(maxsplit=1)
            # Electron helpers are nested inside the app the user actually launches.
            for candidate in reversed(Path(executable).parents):
                if candidate.suffix == '.app' and (candidate / 'Contents' / 'Info.plist').is_file():
                    return candidate
            pid = int(parent_pid)
    except (OSError, ValueError, subprocess.SubprocessError):
        log.debug('Could not identify the app that launched OpenLP+', exc_info=True)
    return None


def has_post_event_access():
    """Check the permission required for sending PowerPoint's slide shortcut."""
    try:
        graphics = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        graphics.CGPreflightPostEventAccess.argtypes = []
        graphics.CGPreflightPostEventAccess.restype = ctypes.c_bool
        return bool(graphics.CGPreflightPostEventAccess())
    except (OSError, AttributeError):
        log.exception('Could not check macOS event-posting access')
        return False


def request_post_event_access():
    """Use the Accessibility prompt API, then request event access if still needed."""
    services = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
    foundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
    services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
    foundation.CFDictionaryCreate.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
    foundation.CFDictionaryCreate.restype = ctypes.c_void_p
    foundation.CFRelease.argtypes = [ctypes.c_void_p]
    prompt_key = ctypes.c_void_p.in_dll(services, 'kAXTrustedCheckOptionPrompt')
    true_value = ctypes.c_void_p.in_dll(foundation, 'kCFBooleanTrue')
    options = foundation.CFDictionaryCreate(None, (ctypes.c_void_p * 1)(prompt_key.value),
                                            (ctypes.c_void_p * 1)(true_value.value), 1, None, None)
    if not options:
        return False
    try:
        trusted = services.AXIsProcessTrustedWithOptions(options)
    finally:
        foundation.CFRelease(options)
    if not trusted:
        # The native permission prompt is asynchronous.
        return False
    graphics = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    graphics.CGRequestPostEventAccess.argtypes = []
    graphics.CGRequestPostEventAccess.restype = ctypes.c_bool
    return bool(graphics.CGRequestPostEventAccess())


def accessibility_target_name():
    """Name the same permission entry in startup guidance and slide errors."""
    return _accessibility_drag_target()[1] or translate('OpenLP.MacPermissions', 'the app that launched OpenLP+')


class _DraggableFileIcon(QtWidgets.QLabel):
    """Provide the current app or interpreter as a Finder-compatible file drag."""

    def __init__(self, file_path, label, parent):
        super().__init__(parent)
        self.file_path = file_path
        self._drag_start_pos = None
        icon = QtWidgets.QFileIconProvider().icon(QtCore.QFileInfo(str(file_path)))
        if file_path.suffix == '.app':
            try:
                with (file_path / 'Contents' / 'Info.plist').open('rb') as info_file:
                    icon_name = plistlib.load(info_file).get('CFBundleIconFile', '')
                if icon_name:
                    icon_file = file_path / 'Contents' / 'Resources' / icon_name
                    if not icon_file.suffix:
                        icon_file = icon_file.with_suffix('.icns')
                    if icon_file.is_file():
                        icon = QtGui.QIcon(str(icon_file))
            except (OSError, ValueError):
                log.debug('Could not load the app icon from %s', file_path)
        self.setPixmap(icon.pixmap(64, 64))
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(92, 92)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setToolTip(translate('OpenLP.MacPermissions', 'Drag {name} into Accessibility Settings').format(
            name=label))
        self.setAccessibleName(translate('OpenLP.MacPermissions', 'Drag {name}').format(name=label))

    def heightForWidth(self, width):
        return 92

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_start_pos is None or
                not event.buttons() & QtCore.Qt.MouseButton.LeftButton or
                (event.pos() - self._drag_start_pos).manhattanLength() <
                QtWidgets.QApplication.startDragDistance()):
            super().mouseMoveEvent(event)
            return
        self._drag_start_pos = None
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        mime_data.setUrls([QtCore.QUrl.fromLocalFile(str(self.file_path))])
        drag.setMimeData(mime_data)
        drag.setPixmap(self.pixmap())
        drag.setHotSpot(QtCore.QPoint(self.pixmap().width() // 2, self.pixmap().height() // 2))
        self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        try:
            drag.exec(QtCore.Qt.DropAction.CopyAction)
        finally:
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


def _open_privacy_settings(anchor):
    """Open the requested macOS privacy pane, falling back to System Settings."""
    url = QtCore.QUrl(f'x-apple.systempreferences:com.apple.preference.security?{anchor}')
    if not QtGui.QDesktopServices.openUrl(url):
        subprocess.run(['/usr/bin/open', '-a', 'System Settings'], check=False)


def request_presentation_permissions(parent):
    """Offer native requests and direct Settings links for missing access."""
    if not is_macosx():
        return
    try:
        graphics = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        missing = []
        for label, preflight_name, request_name, anchor in _PERMISSIONS:
            preflight = getattr(graphics, preflight_name)
            request = getattr(graphics, request_name)
            preflight.restype = ctypes.c_bool
            request.restype = ctypes.c_bool
            if not preflight():
                if label == 'Accessibility':
                    request = request_post_event_access
                missing.append((label, preflight, request, anchor))
    except (AttributeError, OSError):
        log.exception('Could not check macOS presentation permissions')
        return
    if not missing:
        return

    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(translate('OpenLP.MacPermissions', 'PowerPoint permissions'))
    dialog.setMinimumWidth(480)
    layout = QtWidgets.QVBoxLayout(dialog)
    missing_label = QtWidgets.QLabel(dialog)
    missing_label.setWordWrap(True)
    missing_names = ', '.join(label for label, _, _, _ in missing)
    missing_label.setText(translate('OpenLP.MacPermissions', 'Access needed: {names}').format(names=missing_names))
    layout.addWidget(missing_label)

    status = QtWidgets.QLabel(dialog)
    status.setWordWrap(True)
    status.hide()
    layout.addWidget(status)

    request_button = QtWidgets.QPushButton(translate('OpenLP.MacPermissions', 'Request Access'), dialog)

    def ask_macos():
        for label, preflight, request, _ in missing:
            if not preflight():
                try:
                    request()
                except Exception:
                    log.exception('Could not request macOS %s permission', label)
        status.setText(translate('OpenLP.MacPermissions', 'No prompt? Use the Settings buttons.'))
        request_button.hide()
        status.show()

    request_button.clicked.connect(ask_macos)
    layout.addWidget(request_button)

    for label, _, _, anchor in missing:
        button = QtWidgets.QPushButton(
            translate('OpenLP.MacPermissions', 'Open {name} Settings').format(name=label), dialog)
        button.clicked.connect(lambda checked=False, anchor=anchor: _open_privacy_settings(anchor))
        layout.addWidget(button)

    if any(label == 'Accessibility' for label, _, _, _ in missing):
        target, target_name = _accessibility_drag_target()
        if target:
            target_row = QtWidgets.QHBoxLayout()
            target_row.addWidget(_DraggableFileIcon(target, target_name, dialog),
                                 alignment=QtCore.Qt.AlignmentFlag.AlignTop)
            target_details = QtWidgets.QVBoxLayout()
            drag_instruction = QtWidgets.QLabel(
                translate('OpenLP.MacPermissions',
                          'Drag {name} into Accessibility Settings, then enable it.').format(name=target_name), dialog)
            drag_instruction.setWordWrap(True)
            target_details.addWidget(drag_instruction)
            if target.suffix != '.app':
                source_note = QtWidgets.QLabel(
                    translate('OpenLP.MacPermissions',
                              'Or use + to add this file: {path}').format(path=target), dialog)
                source_note.setWordWrap(True)
                source_note.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
                target_details.addWidget(source_note)
            target_row.addLayout(target_details, 1)
            layout.addLayout(target_row)

    check_button = QtWidgets.QPushButton(translate('OpenLP.MacPermissions', 'Check Again'), dialog)

    def check_again():
        remaining = [label for label, preflight, _, _ in missing if not preflight()]
        if not remaining:
            dialog.accept()
            return
        missing_label.setText(translate('OpenLP.MacPermissions', 'Access needed: {names}').format(
            names=', '.join(remaining)))
        status.setText(translate('OpenLP.MacPermissions', 'Still unavailable. Restart OpenLP+ after enabling access.'))
        status.show()

    check_button.clicked.connect(check_again)
    layout.addWidget(check_button)
    done_button = QtWidgets.QPushButton(translate('OpenLP.MacPermissions', 'Done'), dialog)
    done_button.clicked.connect(dialog.accept)
    layout.addWidget(done_button)
    dialog.exec()
