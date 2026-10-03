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

from PySide6 import QtCore, QtGui
import fluentqt

from openlp.core.common.i18n import translate
from openlp.core.widgets import fluent as QtWidgets


class SplashScreen(fluentqt.SplashScreen):
    """Simple Fluent startup surface with overall progress and a loading spinner."""

    def __init__(self):
        super().__init__()
        self.setObjectName('splashScreen')
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
        self.setWindowFlags(QtCore.Qt.WindowType.SplashScreen | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('OpenLP+')
        self.setPresentation(fluentqt.SplashScreen.Presentation.Simple)
        self.setIcon(QtGui.QIcon(':/icon/openlp-logo.svg'))
        self.setIconSize(QtCore.QSize(128, 128))
        self.setText(translate('OpenLP.SplashScreen', 'Starting OpenLP+…'))
        # Keep the percentage row visible throughout startup.
        self.setIndeterminate(False)
        self._refresh_progress_display()
        self.resize(370, 370)

    def showEvent(self, event):
        """Native show refreshes progress; retain the indeterminate spinner."""
        super().showEvent(event)
        self._refresh_progress_display()

    def _refresh_progress_display(self):
        """Keep the loading spinner independent of completed startup work."""
        self.findChild(fluentqt.ProgressRing, 'splashProgressRing').setIsIndeterminate(True)

    def set_status(self, message, progress=None):
        """Refresh the loading stage before the next synchronous startup task."""
        if progress is not None:
            self.setProgress(max(self.progress(), min(100, progress)), 100)
        self.setText(message)
        self._refresh_progress_display()
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

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
        self.set_status(translate('OpenLP.SplashScreen', '{stage} — {completed} of {total}').format(
            stage=stage, completed=completed, total=total), progress)
