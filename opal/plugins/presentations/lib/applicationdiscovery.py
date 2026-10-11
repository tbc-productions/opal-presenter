"""Discover presentation applications without starting them."""
import plistlib
from pathlib import Path


def find_macos_application(bundle_ids, application_folders=None):
    """Find an app by its bundle identifier, including renamed app bundles."""
    if application_folders is None:
        application_folders = (Path('/Applications'), Path.home() / 'Applications', Path('/System/Applications'))
    for folder in application_folders:
        for app in folder.glob('*.app'):
            try:
                with (app / 'Contents' / 'Info.plist').open('rb') as info_file:
                    bundle_id = plistlib.load(info_file).get('CFBundleIdentifier')
            except (OSError, ValueError):
                continue
            if bundle_id in bundle_ids:
                return app
    return None


def macos_application_version(app):
    """Read the installed version without sending Apple events to the app."""
    if app is None:
        return ()
    try:
        with (app / 'Contents' / 'Info.plist').open('rb') as info_file:
            version = plistlib.load(info_file).get('CFBundleShortVersionString', '')
        return tuple(int(part) for part in version.split('.'))
    except (OSError, ValueError, AttributeError):
        return ()


def is_com_registered(prog_id):
    """Check COM registration without creating an application instance."""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id + '\\CLSID'):
            return True
    except OSError:
        return False
