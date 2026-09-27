"""Freeze this probe to verify Qt works without the build environment on PATH."""
import sys
from pathlib import Path

import openlp.core.app  # noqa: F401 -- exercise the application's full startup imports
from PySide6 import QtCore, QtGui, QtMultimedia, QtWebEngineWidgets, QtWidgets


app = QtWidgets.QApplication([])
assert QtGui.QGuiApplication.platformName() == 'windows'
assert QtWidgets.QWidget().metaObject().className() == 'QWidget'
assert QtMultimedia.QMediaPlayer
assert QtWebEngineWidgets.QWebEngineView
runtime = Path(sys._MEIPASS) / 'PySide6'
for relative in ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'Qt6WebEngineCore.dll',
                 'plugins/platforms/qwindows.dll', 'QtWebEngineProcess.exe', 'resources/icudtl.dat'):
    assert (runtime / relative).is_file(), relative
print(f'Frozen Qt {QtCore.qVersion()} smoke test passed')
