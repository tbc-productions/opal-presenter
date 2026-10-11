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
Package to test the opal.plugins.alerts.forms.alertform package.
"""
from unittest.mock import MagicMock

from opal.core.widgets import fluent as QtWidgets

from opal.core.common.registry import Registry
from opal.core.common.settings import Settings
from opal.plugins.alerts.forms.alertform import AlertForm


def test_no_help_button(settings: Settings, registry: Registry):
    """
    Help buttons are absent
    """
    # GIVEN: An alert form and a patched help function
    registry.register('main_window', None)
    alert_form = AlertForm(MagicMock())

    assert alert_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Help) is None
