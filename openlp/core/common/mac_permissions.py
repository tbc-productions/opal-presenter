"""Request the macOS permissions needed for native presentation control."""

import ctypes
import logging

from PySide6 import QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.platform import is_macosx


log = logging.getLogger(__name__)


def request_presentation_permissions(parent):
    """Explain and request missing macOS access before a presentation goes Live."""
    if not is_macosx():
        return
    try:
        graphics = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        permissions = (
            ('Accessibility', 'CGPreflightPostEventAccess', 'CGRequestPostEventAccess'),
            ('Screen Recording', 'CGPreflightScreenCaptureAccess', 'CGRequestScreenCaptureAccess'),
        )
        missing = []
        for label, preflight_name, request_name in permissions:
            preflight = getattr(graphics, preflight_name)
            preflight.restype = ctypes.c_bool
            if not preflight():
                request = getattr(graphics, request_name)
                request.restype = ctypes.c_bool
                missing.append((label, request))
    except (AttributeError, OSError):
        log.exception('Could not check macOS presentation permissions')
        return
    if not missing:
        return

    details = []
    if any(label == 'Accessibility' for label, _ in missing):
        details.append(translate('OpenLP.MacPermissions',
                                 'Accessibility lets OpenLP+ send a slide number and Return to PowerPoint.'))
    if any(label == 'Screen Recording' for label, _ in missing):
        details.append(translate('OpenLP.MacPermissions',
                                 'Screen Recording lets OpenLP+ show the live presentation in its Live area.'))
    details.append(translate('OpenLP.MacPermissions',
                             'macOS may separately ask to let OpenLP+ control Microsoft PowerPoint when it opens.'))
    details.append(translate('OpenLP.MacPermissions',
                             'macOS will ask for access now. If access was previously denied, enable OpenLP+ '
                             '(or the launcher used to run it from source) in System Settings > Privacy & Security, '
                             'then restart OpenLP+.'))
    QtWidgets.QMessageBox.information(parent, translate('OpenLP.MacPermissions', 'Presentation permissions'),
                                      '\n\n'.join(details))
    for label, request in missing:
        try:
            request()
        except Exception:
            log.exception('Could not request macOS %s permission', label)
