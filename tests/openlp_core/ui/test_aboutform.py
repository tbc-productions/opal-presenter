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
Tests for the About dialog.
"""
import datetime
from unittest.mock import patch

import pytest
from PySide6 import QtCore, QtWidgets

from opal.core.ui.aboutform import AboutForm


@patch('opal.core.ui.aboutform.webbrowser')
@pytest.mark.parametrize('button_name,caption,url', [
    ('donate_button', 'Donate to OpenLP', 'http://openlp.org/donate'),
    ('contribute_button', 'Contribute to OpenLP', 'http://openlp.org/contribute')
])
def test_openlp_buttons(mocked_webbrowser, mock_settings, qtbot, button_name, caption, url):
    """
    Support actions name OpenLP, open its pages and leave the dialog open.
    """
    about_form = AboutForm(None)
    qtbot.addWidget(about_form)
    about_form.show()
    button = getattr(about_form, button_name)
    assert button.text() == caption

    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)

    mocked_webbrowser.open_new.assert_called_once_with(url)
    assert about_form.isVisible()


def test_about_form_credits_and_layout(mock_settings, qtbot):
    """Credit the upstream project without the old maintenance claim or banner."""
    about_form = AboutForm(None)
    qtbot.addWidget(about_form)
    credits = about_form.credits_text_edit.toPlainText()
    assert 'Opal Presenter is based on OpenLP.' in credits
    assert 'OpenLP developers and contributors' in credits
    assert 'maintained by volunteers' not in credits
    assert about_form.findChild(QtWidgets.QLabel, 'side_image_label') is None
    assert about_form.base_layout.count() == 1


def test_about_form_keyboard_close(mock_settings, qtbot):
    """Enter activates Close and Escape dismisses the dialog."""
    about_form = AboutForm(None)
    qtbot.addWidget(about_form)
    about_form.show()
    close_button = about_form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
    close_button.setFocus()
    qtbot.keyClick(close_button, QtCore.Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: not about_form.isVisible(), timeout=1000)
    about_form.show()
    qtbot.keyClick(about_form, QtCore.Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not about_form.isVisible(), timeout=1000)


@patch('opal.core.ui.aboutform.get_version')
def test_about_form_build_number(mocked_get_version, mock_settings):
    """
    Test that the build number is added to the about form
    """
    # GIVEN: A mocked out get_version function
    mocked_get_version.return_value = {'version': '3.1.5', 'build': '3000'}

    # WHEN: The about form is created
    about_form = AboutForm(None)

    # THEN: The build number should be in the text
    assert 'Opal Presenter 3.1.5 build 3000' in about_form.about_text_edit.toPlainText(), \
        "The build number should be set correctly"


def test_about_form_date(mock_settings):
    """
    Test that the copyright date is included correctly
    """
    # GIVEN: A correct application date
    date_string = '2004-{year}'.format(year=datetime.date.today().year)

    # WHEN: The about form is created
    about_form = AboutForm(None)
    about_text = about_form.about_text_edit.toPlainText()

    # THEN: The date should be in the text twice.
    assert about_text.count(date_string, 0) == 1, "The text string should be added twice to the license string"
