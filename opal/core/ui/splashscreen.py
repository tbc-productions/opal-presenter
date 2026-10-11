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
The splash screen
"""

import atexit
import logging
import multiprocessing
import os

from PySide6 import QtCore, QtGui
import fluentqt

from opal.core.common.i18n import translate
from opal.core.widgets import fluent as QtWidgets


class SplashScreen(fluentqt.SplashScreen):
    """Branded artwork with overall progress and an independent loading spinner."""

    def __init__(self):
        super().__init__()
        self.setObjectName('splashScreen')
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
        self.setWindowFlags(QtCore.Qt.WindowType.SplashScreen | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('Opal Presenter')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self._artwork = QtGui.QPixmap(':/graphics/opal-presenter-startup.png')
        self._logo = QtGui.QPixmap(':/icon/opal-presenter-logo-512x512.png')
        self._title_font = fluentqt.font_for_role(fluentqt.FontRole.Body)
        self._title_font.setPixelSize(48)
        self._title_font.setWeight(QtGui.QFont.Weight.Normal)
        self.setPresentation(fluentqt.SplashScreen.Presentation.Simple)
        self.setIcon(QtGui.QIcon(':/icon/opal-presenter.png'))
        self.setIconSize(QtCore.QSize(128, 128))
        self.setText(translate('OpenLP.SplashScreen', 'Starting…'))
        self._pending_text = self.text()
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(500)
        self._status_timer.timeout.connect(self._update_status_text)
        # Keep the percentage row visible throughout startup.
        self.setIndeterminate(False)
        self.setFixedSize(640, 400)
        ring = self.findChild(fluentqt.ProgressRing, 'splashProgressRing')
        ring.setStrokeWidth(1.5)
        fluentqt.set_widget_theme_overrides(ring, {
            'light': {'accentDefault': '#ffffff'}, 'dark': {'accentDefault': '#ffffff'}})
        self._refresh_progress_display()

    def paintEvent(self, event):
        """Compose the background, transparent logo and live title text."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self._artwork)
        painter.scale(self.width() / 793, self.height() / 496)
        painter.drawPixmap(QtCore.QRect(85, 116, 226, 226), self._logo)
        painter.setFont(self._title_font)
        painter.setPen(QtCore.Qt.GlobalColor.white)
        title = self.windowTitle()
        left_bearing = QtGui.QFontMetrics(self._title_font).tightBoundingRect(title).left()
        painter.drawText(QtCore.QPoint(350 - left_bearing, 239), title)

    def showEvent(self, event):
        """Native show refreshes progress; retain the indeterminate spinner."""
        super().showEvent(event)
        self._refresh_progress_display()
        if not self._status_timer.isActive():
            self._status_timer.start()

    def _refresh_progress_display(self):
        """Keep the loading spinner independent of completed startup work."""
        ring = self.findChild(fluentqt.ProgressRing, 'splashProgressRing')
        ring.setIsIndeterminate(True)
        # Align loading text with the title as the branding scales down.
        scale = self.width() / 793
        for name, top in (('splashStatusText', 263), ('splashPercentage', 291)):
            label = self.findChild(fluentqt.Label, name)
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            label.setWordWrap(False)
            label.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
            label.setStyleSheet('color: white; background: transparent;')
            label.setGeometry(round(350 * scale), round(top * scale), round(340 * scale), 20)
        percentage = self.findChild(fluentqt.Label, 'splashPercentage')
        ring.setFixedSize(16, 16)
        ring.move(percentage.x() + percentage.fontMetrics().horizontalAdvance(percentage.text()) + 8,
                  percentage.y() + (percentage.height() - ring.height()) // 2)

    def set_status(self, message, progress=None):
        """Refresh the loading stage before the next synchronous startup task."""
        if progress is not None:
            self.setProgress(max(self.progress(), min(100, progress)), 100)
        if message is not None:
            self._queue_status_text(message)
        self._refresh_progress_display()
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def _queue_status_text(self, message):
        self._pending_text = message
        if not self._status_timer.isActive():
            self._update_status_text()

    def _update_status_text(self):
        # Coalesce brief stages without holding up startup or percentage updates.
        if self._pending_text != self.text():
            self.setText(self._pending_text)
            self._refresh_progress_display()
            self._status_timer.start()

    def set_stage_progress(self, stage, completed=None, total=None, progress_range=None):
        """Map stage item counts into their share of overall startup progress."""
        if total is None or total <= 0 or completed is None:
            self.set_status(stage)
            return
        completed = max(0, min(completed, total))
        progress = None
        if progress_range is not None:
            start, end = progress_range
            progress = start + (end - start) * completed // total
        self.set_status(stage, progress)

    def is_foreground(self):
        return is_application_foreground()


def is_application_foreground():
    """Whether this process currently owns application focus."""
    return QtGui.QGuiApplication.applicationState() == QtCore.Qt.ApplicationState.ApplicationActive


def _run_splash(connection, theme, font, text, platform, parent_pid):
    """Own the splash's GUI thread independently of synchronous application startup."""
    from opal.core.resources import qInitResources

    if platform == 'cocoa':
        # Qt otherwise activates this helper as a separate application when its event loop starts.
        os.environ['QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM'] = '1'
    fluentqt.prepare_high_dpi_application()
    app = QtWidgets.QApplication(['Opal Presenter', '-platform', platform])
    app.setQuitOnLastWindowClosed(False)
    if platform == 'cocoa':
        import AppKit
        # The splash helper must not add a second application icon to the Dock.
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    qInitResources()
    fluentqt.initialize_resources()
    fluentqt.set_theme(fluentqt.Theme(theme))
    splash_font = QtGui.QFont()
    splash_font.fromString(font)
    app.setFont(splash_font)
    splash = SplashScreen()
    if platform == 'cocoa':
        splash.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint)
    # Cocoa treats splash windows as panels, which otherwise hide when another process is active.
    splash.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
    splash.setText(text)
    show_requested = False
    first_show = True

    def startup_is_foreground():
        if platform == 'cocoa':
            active_app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
            return active_app is not None and active_app.processIdentifier() in (parent_pid, os.getpid())
        return is_application_foreground()

    def sync_visibility():
        nonlocal first_show
        visible = show_requested and (first_show or platform != 'cocoa' or startup_is_foreground())
        if visible != splash.isVisible():
            if visible:
                splash.show()
                splash.raise_()
                if first_show and platform == 'cocoa':
                    AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
                first_show = False
            else:
                splash.hide()

    def receive_updates():
        nonlocal show_requested
        try:
            # Bound each batch so a large library cannot starve animation events.
            for _ in range(32):
                if not connection.poll():
                    break
                action, args = connection.recv()
                if action == 'status':
                    splash._queue_status_text(args[0])
                    splash.setProgress(args[1], 100)
                    splash._refresh_progress_display()
                elif action == 'show':
                    show_requested = True
                    sync_visibility()
                    connection.send(None)
                elif action == 'hide':
                    show_requested = False
                    sync_visibility()
                    connection.send(None)
                elif action == 'foreground':
                    connection.send(startup_is_foreground())
                elif action == 'close':
                    app.quit()
                    return
            sync_visibility()
        except (EOFError, OSError):
            app.quit()

    timer = QtCore.QTimer()
    timer.timeout.connect(receive_updates)
    timer.start(16)
    connection.send(None)
    try:
        app.exec()
    finally:
        connection.close()


class SplashScreenProcess(SplashScreen):
    """Keep progress state locally; display it in a process with an unblocked event loop."""

    def __init__(self):
        super().__init__()
        self._visible = False
        self._show_requested = False
        self._modal_timer = QtCore.QTimer(self)
        self._modal_timer.timeout.connect(self._sync_visibility)
        context = multiprocessing.get_context('spawn')
        self._connection, child_connection = context.Pipe()
        self._process = context.Process(target=_run_splash, args=(
            child_connection, fluentqt.current_theme().value, QtWidgets.QApplication.font().toString(),
            self.text(), QtGui.QGuiApplication.platformName(), os.getpid()), daemon=True, name='OpenLP splash')
        try:
            self._process.start()
            child_connection.close()
            self._wait_for_splash()
        except Exception:
            child_connection.close()
            self.close()
            raise
        atexit.register(self.close)
        self._modal_timer.start(50)

    def _wait_for_splash(self):
        if not self._connection.poll(10):
            raise TimeoutError('The splash screen did not respond')
        return self._connection.recv()

    def _send(self, action, *args, wait=False):
        if self._connection.closed:
            return
        try:
            self._connection.send((action, args))
            if wait:
                return self._wait_for_splash()
        except (OSError, EOFError):
            logging.getLogger(__name__).exception('The splash screen process stopped responding')
            self.close()

    def set_status(self, message, progress=None):
        super().set_status(message, progress)
        self._send('status', self._pending_text, self.progress())

    def show(self):
        self._show_requested = True
        self._sync_visibility()

    def hide(self):
        self._show_requested = False
        self._sync_visibility()

    def _sync_visibility(self):
        """Keep the foreground splash out of the way of startup prompts."""
        visible = self._show_requested and QtWidgets.QApplication.activeModalWidget() is None
        if visible != self._visible:
            self._send('show' if visible else 'hide', wait=True)
            self._visible = visible and not self._connection.closed

    def isVisible(self):
        return self._visible and self._process.is_alive()

    def is_foreground(self):
        if self._connection.closed:
            return super().is_foreground()
        # The helper's native event loop observes app switches while startup blocks this process.
        foreground = self._send('foreground', wait=True)
        return foreground or (QtGui.QGuiApplication.platformName() != 'cocoa' and super().is_foreground())

    def close(self):
        """Reap the helper even after a startup failure or an unresponsive splash."""
        self._visible = False
        self._show_requested = False
        self._modal_timer.stop()
        atexit.unregister(self.close)
        if not self._connection.closed:
            try:
                self._connection.send(('close', ()))
            except OSError:
                pass
            self._connection.close()
        if self._process.pid is not None:
            self._process.join(2)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join()
        return super().close()
