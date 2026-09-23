"""Help macOS users grant access needed for native presentations."""

import ctypes
import logging
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
    """Return the app bundle or the real interpreter used for a source launch."""
    bundle = _running_app_bundle()
    if bundle:
        return bundle, bundle.name
    executable = Path(sys.executable).resolve()
    if executable.is_file():
        label = translate('OpenLP.MacPermissions', 'Python {version}').format(
            version=f'{sys.version_info.major}.{sys.version_info.minor}')
        return executable, label
    return None, None


class _DraggableFileIcon(QtWidgets.QLabel):
    """Provide the current app or interpreter as a Finder-compatible file drag."""

    def __init__(self, file_path, label, parent):
        super().__init__(parent)
        self.file_path = file_path
        self._drag_start_pos = None
        icon_file = file_path / 'Contents' / 'Resources' / 'OpenLP.icns'
        icon = (QtGui.QIcon(str(icon_file)) if icon_file.is_file() else
                QtWidgets.QFileIconProvider().icon(QtCore.QFileInfo(str(file_path))))
        self.setPixmap(icon.pixmap(64, 64))
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(92, 92)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setToolTip(translate('OpenLP.MacPermissions', 'Drag {name} into Accessibility Settings').format(
            name=label))
        self.setAccessibleName(translate('OpenLP.MacPermissions', 'Drag {name}').format(name=label))

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
                missing.append((label, preflight, request, anchor))
    except (AttributeError, OSError):
        log.exception('Could not check macOS presentation permissions')
        return
    if not missing:
        return

    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(translate('OpenLP.MacPermissions', 'Presentation permissions'))
    dialog.setMinimumWidth(560)
    layout = QtWidgets.QVBoxLayout(dialog)
    explanation = QtWidgets.QLabel(dialog)
    explanation.setWordWrap(True)
    explanation.setText(translate(
        'OpenLP.MacPermissions',
        'OpenLP+ needs Accessibility to send slide numbers to PowerPoint and Screen Recording to show the '
        'presentation in its Live area. macOS may not show another alert if you denied access earlier. '
        'You can enable the missing access in System Settings > Privacy & Security. '
        'If the program shown below is not listed, use the + button to add it. '
        'Restart OpenLP+ after changing permissions.'))
    layout.addWidget(explanation)

    missing_label = QtWidgets.QLabel(dialog)
    missing_label.setWordWrap(True)
    missing_names = ', '.join(label for label, _, _, _ in missing)
    missing_label.setText(translate('OpenLP.MacPermissions', 'Missing access: {names}').format(names=missing_names))
    layout.addWidget(missing_label)

    status = QtWidgets.QLabel(dialog)
    status.setWordWrap(True)
    status.hide()
    layout.addWidget(status)

    request_button = QtWidgets.QPushButton(translate('OpenLP.MacPermissions', 'Ask macOS for Access'), dialog)

    def ask_macos():
        for label, preflight, request, _ in missing:
            if not preflight():
                try:
                    request()
                except Exception:
                    log.exception('Could not request macOS %s permission', label)
        status.setText(translate('OpenLP.MacPermissions',
                                 'If no macOS alert appeared, use the System Settings buttons below.'))
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
            drag_instruction = QtWidgets.QLabel(
                translate('OpenLP.MacPermissions',
                          'Drag {name} into the Accessibility list in System Settings, '
                          'then switch its permission on.').format(name=target_name), dialog)
            drag_instruction.setWordWrap(True)
            layout.addWidget(drag_instruction)
            layout.addWidget(_DraggableFileIcon(target, target_name, dialog),
                             alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
            layout.addSpacing(12)
            if target.suffix != '.app':
                source_note = QtWidgets.QLabel(
                    translate('OpenLP.MacPermissions',
                              'This development run uses the Python executable at {path}. '
                              'If dragging does not add it, use + and select this file.').format(path=target), dialog)
                source_note.setWordWrap(True)
                source_note.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
                layout.addWidget(source_note)

    done_button = QtWidgets.QPushButton(translate('OpenLP.MacPermissions', 'Done'), dialog)
    done_button.clicked.connect(dialog.accept)
    layout.addWidget(done_button)
    dialog.exec()
