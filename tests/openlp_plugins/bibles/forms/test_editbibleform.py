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
Package to test the opal.plugins.bibles.forms.editbibleform package.
"""
from unittest.mock import MagicMock

from opal.core.widgets import fluent as QtWidgets

from opal.plugins.bibles.forms.editbibleform import EditBibleForm


def test_no_help_button(settings):
    """
    Help buttons are absent
    """
    # GIVEN: An edit bible form and a patched help function
    main_window = QtWidgets.QMainWindow()
    edit_bible_form = EditBibleForm(MagicMock(), main_window, MagicMock())

    assert edit_bible_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Help) is None
