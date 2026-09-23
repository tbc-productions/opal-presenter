"""Help macOS users grant access needed for native presentations."""

import ctypes
import logging
import subprocess

from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.platform import is_macosx


log = logging.getLogger(__name__)

_PERMISSIONS = (
    ('Accessibility', 'CGPreflightPostEventAccess', 'CGRequestPostEventAccess', 'Privacy_Accessibility'),
    ('Screen Recording', 'CGPreflightScreenCaptureAccess', 'CGRequestScreenCaptureAccess',
     'Privacy_ScreenCapture'),
)


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
    dialog.setMinimumWidth(440)
    layout = QtWidgets.QVBoxLayout(dialog)
    explanation = QtWidgets.QLabel(dialog)
    explanation.setWordWrap(True)
    explanation.setText(translate(
        'OpenLP.MacPermissions',
        'OpenLP+ needs Accessibility to send slide numbers to PowerPoint and Screen Recording to show the '
        'presentation in its Live area. macOS may not show another alert if you denied access earlier. '
        'You can enable the missing access in System Settings > Privacy & Security. '
        'If OpenLP+ is not listed, use the + button to add the app or the launcher you use to run it. '
        'Restart OpenLP+ after changing permissions.'))
    layout.addWidget(explanation)

    missing_label = QtWidgets.QLabel(dialog)
    missing_label.setWordWrap(True)
    missing_names = ', '.join(label for label, _, _, _ in missing)
    missing_label.setText(translate('OpenLP.MacPermissions', 'Missing access: {names}').format(names=missing_names))
    layout.addWidget(missing_label)

    status = QtWidgets.QLabel(dialog)
    status.setWordWrap(True)
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

    request_button.clicked.connect(ask_macos)
    layout.addWidget(request_button)

    for label, _, _, anchor in missing:
        button = QtWidgets.QPushButton(
            translate('OpenLP.MacPermissions', 'Open {name} Settings').format(name=label), dialog)
        button.clicked.connect(lambda checked=False, anchor=anchor: _open_privacy_settings(anchor))
        layout.addWidget(button)

    done_button = QtWidgets.QPushButton(translate('OpenLP.MacPermissions', 'Done'), dialog)
    done_button.clicked.connect(dialog.accept)
    layout.addWidget(done_button)
    dialog.exec()
