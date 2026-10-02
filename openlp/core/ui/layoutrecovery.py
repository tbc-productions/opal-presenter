"""Recover saved Qt layouts after a monitor change or an interrupted window startup."""
import logging

from PySide6 import QtCore


log = logging.getLogger(__name__)
_PENDING_KEY = 'core/layout startup pending'
_BACKUP_PREFIX = 'layout recovery/'
_LAYOUT_FIELDS = {
    'main window state', 'main window geometry', 'main window position',
    'main window splitter geometry', 'live splitter geometry', 'preview splitter geometry'
}


def begin_layout_startup(settings, screens):
    """Quarantine unsafe layout settings, then persist a marker before entering native Qt code.

    A native access violation cannot be caught in Python. Leave the marker set until
    the window and deferred dock layout have made it into the application event loop.
    Only window/splitter state is reset; keep panel visibility and all user content.
    """
    saved_screens = settings.value('core/screens')
    screens_changed = bool(saved_screens) and (
        len(saved_screens) != len(screens)
        or any(screens.get_screen_number(screen) is None for screen in saved_screens.values()))
    interrupted = settings.value(_PENDING_KEY)
    if interrupted or screens_changed:
        reason = 'interrupted window startup' if interrupted else 'changed monitor configuration'
        keys = [key for key in settings.allKeys()
                if key.startswith('user interface/') and key.rsplit('/', 1)[-1] in _LAYOUT_FIELDS
                and (key.count('/') == 1 or key.startswith('user interface/preset layout/'))]
        if keys:
            # Preserve the most recent discarded layout using raw QSettings values, including QByteArrays.
            settings.remove(_BACKUP_PREFIX.rstrip('/'))
            for key in keys:
                QtCore.QSettings.setValue(settings, _BACKUP_PREFIX + key, QtCore.QSettings.value(settings, key))
                settings.remove(key)
        log.warning('Resetting saved window layouts after %s (%d settings); backup in %s',
                    reason, len(keys), _BACKUP_PREFIX)
    settings.setValue(_PENDING_KEY, True)
    settings.sync()
    return bool(interrupted or screens_changed)


def complete_layout_startup(settings, screens):
    """Commit the current monitor mapping and clear the marker after successful startup."""
    screens.save_screen_settings()
    settings.setValue(_PENDING_KEY, False)
    settings.sync()
