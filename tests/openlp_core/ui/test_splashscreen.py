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
import hashlib
import json
import os
import subprocess
import sys
import time
from functools import partial
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets
import fluentqt

from openlp.core.ui.splashscreen import SplashScreen, SplashScreenProcess
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


def _run_observed_splash(*args, samples_file):
    """Observe painted frames in the helper without servicing the parent's Qt events."""
    from openlp.core.ui.splashscreen import _run_splash

    class ObservedSplash(SplashScreen):
        def __init__(self):
            super().__init__()
            self.sample_timer = QtCore.QTimer(self)
            self.sample_timer.timeout.connect(self.sample)
            self.sample_timer.start(60)

        def sample(self):
            ring = self.findChild(fluentqt.ProgressRing, 'splashProgressRing')
            pixels = ring.grab().toImage()
            sample = {'frame': hashlib.sha256(pixels.constBits()).hexdigest(), 'text': self.text(),
                      'progress': self.progress(), 'visible': self.isVisible(),
                      'theme': fluentqt.current_theme().value,
                      'topmost': bool(self.windowFlags() & QtCore.Qt.WindowType.WindowStaysOnTopHint)}
            if QtCore.QCoreApplication.instance().platformName() == 'cocoa':
                import AppKit
                native_app = AppKit.NSApplication.sharedApplication()
                sample['accessory'] = native_app.activationPolicy() == 1
                foreground = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
                sample['foreground_pid'] = foreground.processIdentifier()
                native_window = next((window for window in native_app.windows()
                                      if window.title() == self.windowTitle()), None)
                if native_window is not None:
                    sample['window_number'] = native_window.windowNumber()
                    sample['geometry'] = [self.x(), self.y(), self.width(), self.height()]
            with open(samples_file, 'a') as output:
                output.write(json.dumps(sample) + '\n')

    with patch('openlp.core.ui.splashscreen.SplashScreen', ObservedSplash):
        _run_splash(*args)


def test_splash_animates_during_blocked_startup(mock_settings, qtbot, tmp_path):
    """Painted ring frames keep changing during synchronous work in the parent."""
    samples_file = tmp_path / 'splash-frames.jsonl'
    target = partial(_run_observed_splash, samples_file=str(samples_file))
    with patch('openlp.core.ui.splashscreen._run_splash', target):
        splash = SplashScreenProcess()
    qtbot.addWidget(splash)
    process = splash._process
    try:
        splash.show()
        splash.set_status('Loading plugins', 55)
        splash.set_stage_progress('Initialising plugins', 3, 8, progress_range=(55, 75))
        # Deliberately do not process Qt events in the parent during the heavy task.
        time.sleep(0.6)
        samples = [json.loads(line) for line in samples_file.read_text().splitlines()]
        frames = [sample for sample in samples if sample['text'] == 'Initialising plugins - 3 of 8']
        assert len({sample['frame'] for sample in frames}) >= 3, (os.getpid(), frames)
        assert all(sample['progress'] == 62 and sample['visible'] for sample in frames)
        assert all(sample['theme'] == fluentqt.current_theme().value for sample in frames)
        assert all(sample.get('accessory', True) for sample in frames)
        assert all(sample['topmost'] == (QtWidgets.QApplication.platformName() == 'cocoa') for sample in frames)
        assert splash.isVisible()

        splash.hide()
        time.sleep(0.15)
        assert not splash.isVisible()
        assert not json.loads(samples_file.read_text().splitlines()[-1])['visible']
        splash.show()
        time.sleep(0.15)
        assert splash.isVisible()
        assert json.loads(samples_file.read_text().splitlines()[-1])['visible']
    finally:
        splash.close()
    assert not process.is_alive()
    splash.close()


def test_splash_exits_when_parent_connection_closes(mock_settings, qtbot):
    """Startup exceptions and parent exit must not leave a stranded splash window."""
    splash = SplashScreenProcess()
    qtbot.addWidget(splash)
    try:
        splash.show()
        splash._connection.close()
        splash._process.join(3)
        assert not splash._process.is_alive()
        assert not splash.isVisible()
    finally:
        splash.close()


def test_foreground_splash_yields_to_startup_dialog(mock_settings, qtbot):
    """Modal prompts hide the helper temporarily without undoing an explicit hide."""
    dialog = QtWidgets.QDialog()
    dialog.setModal(True)
    qtbot.addWidget(dialog)
    splash = SplashScreenProcess()
    qtbot.addWidget(splash)
    try:
        splash.show()
        assert splash.isVisible()
        dialog.show()
        qtbot.waitUntil(lambda: not splash.isVisible())
        dialog.hide()
        qtbot.waitUntil(splash.isVisible)

        splash.hide()
        dialog.show()
        dialog.hide()
        qtbot.wait(100)
        assert not splash.isVisible()
    finally:
        splash.close()


def test_splash_cleans_up_failed_launch(mock_settings):
    """A helper that never starts must release both pipe endpoints."""
    with patch('openlp.core.ui.splashscreen.multiprocessing.get_context') as get_context:
        context = get_context.return_value
        parent, child = MagicMock(), MagicMock()
        context.Pipe.return_value = (parent, child)
        parent.closed = False
        process = context.Process.return_value
        process.pid = None
        process.start.side_effect = OSError('Cannot launch helper')
        with pytest.raises(OSError, match='Cannot launch helper'):
            SplashScreenProcess()
        parent.close.assert_called_once()
        child.close.assert_called_once()
        process.join.assert_not_called()


@pytest.mark.skipif(sys.platform != 'darwin' or os.environ.get('QT_QPA_PLATFORM') == 'offscreen',
                    reason='Requires native macOS window ordering')
def test_native_splash_follows_parent_foreground(mock_settings, qtbot, tmp_path):
    """Stay above OpenLP, but yield when another application becomes active during blocked startup."""
    import AppKit

    competing = QtWidgets.QWidget()
    competing.setWindowTitle('Splash foreground regression')
    qtbot.addWidget(competing)
    samples_file = tmp_path / 'foreground.jsonl'
    target = partial(_run_observed_splash, samples_file=str(samples_file))
    with patch('openlp.core.ui.splashscreen._run_splash', target):
        splash = SplashScreenProcess()
    qtbot.addWidget(splash)
    try:
        splash.show()
        qtbot.waitUntil(lambda: samples_file.exists() and 'window_number' in samples_file.read_text())
        sample = json.loads(samples_file.read_text().splitlines()[-1])
        splash_number = sample['window_number']
        competing.setGeometry(*sample['geometry'])
        competing.show()
        competing.raise_()
        competing.activateWindow()
        native_app = AppKit.NSApplication.sharedApplication()
        native_app.activateIgnoringOtherApps_(True)
        window_number = next(window.windowNumber() for window in native_app.windows()
                             if window.title() == competing.windowTitle())

        def splash_is_above():
            windows = list(AppKit.NSWindow.windowNumbersWithOptions_(AppKit.NSWindowNumberListAllApplications))
            return splash_number in windows and windows.index(splash_number) < windows.index(window_number)

        qtbot.waitUntil(splash_is_above)
        qtbot.waitUntil(splash.is_foreground)
        finder = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_('com.apple.finder')[0]
        finder.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
        # The helper must notice switching apps even when the parent's event loop is blocked.
        time.sleep(0.4)
        assert not json.loads(samples_file.read_text().splitlines()[-1])['visible']
        sample = json.loads(samples_file.read_text().splitlines()[-1])
        assert sample['foreground_pid'] == finder.processIdentifier()
        assert not splash.is_foreground()
        assert not splash_is_above()
        native_app.activateIgnoringOtherApps_(True)
        qtbot.waitUntil(splash_is_above)
        splash.hide()
        qtbot.waitUntil(lambda: not splash_is_above())
        splash.show()
        qtbot.waitUntil(splash_is_above)
    finally:
        splash.close()


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
