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
Module to test the EditCustomSlideForm.
"""
import pytest
from unittest.mock import MagicMock, patch

from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.registry import Registry
from openlp.plugins.custom.forms.editcustomslideform import EditCustomSlideForm


@pytest.fixture()
def form(settings):
    main_window = QtWidgets.QMainWindow()
    Registry().register('main_window', main_window)
    frm = EditCustomSlideForm()
    yield frm
    del frm
    del main_window


def test_basic(form):
    """
    Test if the dialog is correctly set up.
    """
    # GIVEN: A mocked QDialog.exec() method
    with patch('openlp.core.widgets.fluent.QDialog.exec'):
        # WHEN: Show the dialog.
        form.exec()

        # THEN: The dialog should be empty.
        assert form.slide_text_edit.toPlainText() == '', 'There should not be any text in the text editor.'


def test_set_text(form):
    """
    Test the set_text() method.
    """
    # GIVEN: A mocked QDialog.exec() method
    with patch('openlp.core.widgets.fluent.QDialog.exec'):
        mocked_set_focus = MagicMock()
        form.slide_text_edit.setFocus = mocked_set_focus
        wanted_text = 'THIS TEXT SHOULD BE SHOWN.'

        # WHEN: Show the dialog and set the text.
        form.exec()
        form.set_text(wanted_text)

        # THEN: The dialog should show the text.
        assert form.slide_text_edit.toPlainText() == wanted_text, \
            'The text editor should show the correct text.'

        # THEN: The dialog should have focus.
        mocked_set_focus.assert_called_with()


def test_set_text_scrolls_to_top(form):
    """Loading text should leave the editor scrolled to the top."""
    form.resize(400, 120)
    form.show()
    QtWidgets.QApplication.processEvents()

    long_text = '\n'.join('Line {line}'.format(line=line) for line in range(50))
    form.set_text(long_text)
    QtWidgets.QApplication.processEvents()

    assert form.slide_text_edit.verticalScrollBar().value() == 0


def test_custom_text_editor_fits_parent_with_padding(settings, qtbot):
    """The custom text editor shares the lyric editor's bounded, resizable sizing."""
    parent = QtWidgets.QMainWindow()
    parent.resize(1200, 900)
    parent.show()
    editor = EditCustomSlideForm(parent)
    editor.setAnimationEnabled(False)
    editor.set_text('\n'.join(f'Line {row}' for row in range(60)))
    editor.show()
    qtbot.wait(50)
    try:
        assert editor.isSizeGripEnabled()
        assert editor.width() >= 1000
        assert editor.height() == parent.height() - 48
        assert editor.y() >= 24
        assert editor.geometry().bottom() < parent.height() - 24
        parent.resize(1200, 650)
        qtbot.wait(50)
        assert editor.height() <= parent.height() - 48
        assert editor.geometry().bottom() < parent.height() - 24
    finally:
        editor.close()
        parent.close()
