"""Packaging checks runnable without the application's Qt pytest fixtures.

Run with: python -m unittest discover -s tests/packaging -v
"""
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from openlp.__pyinstaller import get_hook_dirs


class QtHookTest(unittest.TestCase):
    def run_hook(self, package_dir, *, windows=True, version=(6, 10, 3)):
        compat = ModuleType('PyInstaller.compat')
        compat.is_win = windows
        hooks = ModuleType('PyInstaller.utils.hooks')
        hooks.get_package_paths = Mock(return_value=('', str(package_dir)))
        hooks.collect_dynamic_libs = Mock(return_value=[('Qt6Core.dll', 'PySide6')])
        qt = ModuleType('PyInstaller.utils.hooks.qt')
        qt.pyside6_library_info = SimpleNamespace(version=version)
        modules = {'PyInstaller.compat': compat, 'PyInstaller.utils.hooks': hooks,
                   'PyInstaller.utils.hooks.qt': qt}
        with patch.dict(sys.modules, modules):
            return runpy.run_path(str(Path(get_hook_dirs()[0]) / 'hook-openlp.core.py'))

    def test_does_not_collect_windows_runtime_on_other_platforms(self):
        self.assertEqual(self.run_hook('/not-installed', windows=False)['binaries'], [])

    def test_unloadable_qt_stops_build(self):
        with self.assertRaisesRegex(RuntimeError, 'could not be loaded'):
            self.run_hook('/not-installed', version=None)

    def test_bindings_without_qt_dlls_stop_build(self):
        # The installed 4.0.1 contained QtCore.pyd but no Qt6Core.dll.
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'QtCore.pyd').touch()
            with self.assertRaisesRegex(RuntimeError, 'missing Qt6Core.dll'):
                self.run_hook(directory)

    def test_missing_platform_plugin_stops_build(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll',
                         'Qt6WebEngineCore.dll', 'QtWebEngineProcess.exe'):
                (Path(directory) / name).touch()
            with self.assertRaisesRegex(RuntimeError, 'missing plugins/platforms/qwindows.dll'):
                self.run_hook(directory)


if __name__ == '__main__':
    unittest.main()
