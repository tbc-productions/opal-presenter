# -*- coding: utf-8 -*-

##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""
Package to test the openlp.core.ui package.
"""
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore
import fluentqt

from openlp.core.ui.splashscreen import SplashScreen
from openlp.core.resources import qInitResources


def test_splashscreen(mock_settings: MagicMock, qtbot):
    """Startup uses the simple native Fluent surface and its loading spinner."""
    qInitResources()
    splash = SplashScreen()
    qtbot.addWidget(splash)
    splash.show()

    assert not splash.icon().isNull()
    assert splash.iconSize() == QtCore.QSize(128, 128)
    assert isinstance(splash, fluentqt.SplashScreen)
    assert splash.objectName() == 'splashScreen'
    assert splash.size() == QtCore.QSize(370, 370)
    assert splash.contextMenuPolicy() == QtCore.Qt.ContextMenuPolicy.PreventContextMenu
    assert splash.windowFlags() & QtCore.Qt.WindowType.SplashScreen
    assert splash.presentation() == fluentqt.SplashScreen.Presentation.Simple
    assert not splash.isIndeterminate()
    assert splash.text() == 'Starting OpenLP+'
    ring = splash.findChild(fluentqt.ProgressRing, 'splashProgressRing')
    assert ring is not None
    assert ring.isVisible()
    assert ring.isActive()
    assert ring.isIndeterminate()
    percentage = splash.findChild(fluentqt.Label, 'splashPercentage')
    assert percentage.isVisible()
    assert percentage.text() == '0%'


def test_splashscreen_loading_status(mock_settings: MagicMock, qtbot):
    """A startup stage refreshes the UI while retaining indeterminate progress."""
    splash = SplashScreen()
    qtbot.addWidget(splash)
    with patch('openlp.core.ui.splashscreen.QtWidgets.QApplication.processEvents') as process_events:
        splash.set_status('Loading components')

    assert splash.text() == 'Loading components'
    assert not splash.isIndeterminate()
    assert splash.findChild(fluentqt.Label, 'splashPercentage').text() == '0%'
    process_events.assert_called_once_with(QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)


def test_splashscreen_hide_and_close(mock_settings: MagicMock, qtbot):
    """Backup prompts can hide and restore the splash before startup closes it."""
    splash = SplashScreen()
    qtbot.addWidget(splash)
    splash.show()
    splash.hide()
    assert not splash.isVisible()
    splash.show()
    assert splash.isVisible()
    splash.close()
    assert not splash.isVisible()


def test_overall_percentage_preserves_layout_and_progress(mock_settings: MagicMock, qtbot):
    """Stage totals contribute to startup progress, which persists between stages."""
    splash = SplashScreen()
    qtbot.addWidget(splash)
    splash.show()
    status = splash.findChild(fluentqt.Label, 'splashStatusText')
    ring = splash.findChild(fluentqt.ProgressRing, 'splashProgressRing')
    status_top = status.y()
    ring_top = ring.y()
    splash.set_status('Loading plugins', 55)
    splash.set_stage_progress('Initialising plugins', 3, 8, progress_range=(55, 75))

    assert splash.progress() == 62
    assert not splash.isIndeterminate()
    assert splash.text() == 'Initialising plugins - 3 of 8'
    ring = splash.findChild(fluentqt.ProgressRing, 'splashProgressRing')
    assert ring.isVisible()
    assert ring.isIndeterminate()
    percentage = splash.findChild(fluentqt.Label, 'splashPercentage')
    assert percentage.isVisible()
    assert percentage.text() == '62%'
    assert status.y() == status_top
    assert ring.y() == ring_top

    splash.hide()
    splash.show()
    assert ring.isIndeterminate()
    assert percentage.isVisible()

    splash.set_status('Preparing the main window')
    assert not splash.isIndeterminate()
    assert ring.isIndeterminate()
    assert percentage.isVisible()
    assert percentage.text() == '62%'
    assert status.y() == status_top
    assert ring.y() == ring_top

    splash.hide()
    splash.show()
    assert percentage.isVisible()
    assert percentage.text() == '62%'
    assert status.y() == status_top
    assert ring.y() == ring_top

    splash.set_stage_progress('Loading themes', 0, 2, progress_range=(75, 90))
    assert percentage.text() == '75%'
    assert status.y() == status_top
    assert ring.y() == ring_top

    splash.set_stage_progress('Loading themes', 2, 2, progress_range=(75, 90))
    assert percentage.text() == '90%'
    splash.set_status('Earlier stage', 55)
    assert percentage.text() == '90%'
    splash.set_status('Ready', 100)
    assert percentage.text() == '100%'


def test_empty_stage_preserves_overall_percentage(mock_settings: MagicMock, qtbot):
    """An empty stage preserves the progress made by earlier startup work."""
    splash = SplashScreen()
    qtbot.addWidget(splash)
    splash.set_status('Loading library', 75)
    splash.set_stage_progress('Loading themes', 0, 0, progress_range=(75, 90))
    assert not splash.isIndeterminate()
    assert splash.findChild(fluentqt.Label, 'splashPercentage').text() == '75%'
    assert splash.text() == 'Loading themes'


@pytest.mark.skipif(sys.platform != 'darwin' or os.environ.get('QT_QPA_PLATFORM') == 'offscreen',
                    reason='Requires the native macOS window server and WebEngine focus events')
def test_native_splash_webengine_accessibility():
    """A Fluent progress factory must not RTTI-cast WebEngine's private Quick item."""
    # Isolate the native crash regression from QtWebEngine mocks and the shared
    # QApplication used elsewhere in the suite. No user settings are loaded.
    code = """
from PySide6 import QtCore, QtWidgets, QtWebEngineWidgets
from openlp.core.resources import qInitResources
from openlp.core.ui.splashscreen import SplashScreen
import fluentqt
app = QtWidgets.QApplication([])
qInitResources()
fluentqt.initialize_resources()
splash = SplashScreen()
splash.show()
app.processEvents()
view = QtWebEngineWidgets.QWebEngineView()
view.setHtml('<html><body>Startup regression</body></html>')
view.show()
view.setFocus()
app.processEvents()
splash.set_stage_progress('Initialising plugins', 3, 8)
QtCore.QTimer.singleShot(300, app.quit)
app.exec()
"""
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-c', code],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
