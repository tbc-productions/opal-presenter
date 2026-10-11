"""Include the Windows Qt runtime even when dependency scanning misses DLLs.

Hook opal.core so the packaging repository's hook-opal.py (which discovers
plugins) can still run. The normal PySide6 hooks continue to collect Qt data,
translations and runtime hooks. Explicit binaries retain the wheel's layout.
"""
from pathlib import Path

from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import collect_dynamic_libs, get_package_paths
from PyInstaller.utils.hooks.qt import pyside6_library_info


binaries = []
if is_win:
    # Qt's normal hooks can warn and continue when introspection fails, leaving
    # Python bindings in a bundle with no Qt DLLs or platform plugins.
    if not pyside6_library_info.version:
        raise RuntimeError('Cannot package OpenLP: PySide6 Qt runtime could not be loaded on the build machine.')

    _, package_dir = get_package_paths('PySide6')
    package_dir = Path(package_dir)
    required = (
        'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll',
        'Qt6WebEngineCore.dll', 'QtWebEngineProcess.exe',
        'plugins/platforms/qwindows.dll',
    )
    missing = [name for name in required if not (package_dir / name).is_file()]
    if missing:
        raise RuntimeError(f'Cannot package OpenLP: incomplete PySide6 runtime; missing {", ".join(missing)}')

    binaries = collect_dynamic_libs('PySide6')
    binaries.append((str(package_dir / 'QtWebEngineProcess.exe'), 'PySide6'))
