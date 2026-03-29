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
Package to test the OpenLP default toolbars.
"""
from unittest.mock import MagicMock, patch
import pytest

from PySide6 import QtCore, QtGui

from openlp.core.widgets.toolbar import MediaToolbar, ClickableSlider


HIDE_COMPONENTS = [
    ('seek', lambda toolbar: not hasattr(toolbar, 'seek_slider')),
    ('volume', lambda toolbar: not hasattr(toolbar, 'volume_slider')),
    ('loop', lambda toolbar: 'playbackLoop' not in toolbar.actions_map)
]
HAS_PREFIX_CHECKS = [
    ('play', lambda toolbar, prefix: prefix + 'playbackPlay' in toolbar.actions_map),
    ('pause', lambda toolbar, prefix: prefix + 'playbackPause' in toolbar.actions_map),
    ('stop', lambda toolbar, prefix: prefix + 'playbackStop' in toolbar.actions_map),
    ('loop', lambda toolbar, prefix: prefix + 'playbackLoop' in toolbar.actions_map),
    ('seek', lambda toolbar, prefix: toolbar.seek_slider.objectName() == prefix + 'seek_slider'),
    ('volume', lambda toolbar, prefix: toolbar.volume_slider.objectName() == prefix + 'volume_slider'),
]


@pytest.mark.parametrize('hide_component, check_missing', [tuple for tuple in HIDE_COMPONENTS])
@patch('openlp.core.widgets.toolbar.UiIcons')
def test_mediatoolbar_honors_hide_components(MockedUiIcons, hide_component, check_missing, settings):
    """
    Test if MediaToolbar's hide_components arguments is honoured
    """
    # GIVEN: The components to be hidden
    hide_components = [hide_component]

    # WHEN: Is instantiated
    toolbar = MediaToolbar(None, hide_components=hide_components)
    # THEN: Toolbar item shouldn't have this component
    assert check_missing(toolbar) is True


@pytest.mark.parametrize('component, prefix_check', [tuple for tuple in HAS_PREFIX_CHECKS])
@patch('openlp.core.widgets.toolbar.UiIcons')
def test_mediatoolbar_honors_action_prefix(MockedUiIcons, component, prefix_check, settings):
    """
    Test if MediaToolbar's action_prefix argument is honoured
    """
    # GIVEN: MediaToolbar and prefix
    prefix = "_theTeST__"
    # WHEN: Is instantiated
    toolbar = MediaToolbar(None, action_prefixes=prefix)
    # THEN: Toolbar item should have prefix set
    assert prefix_check(toolbar, prefix) is True


@patch('openlp.core.widgets.toolbar.UiIcons')
@pytest.mark.parametrize('label_visibility, label_text', [
    (True, 'Test Mediabar'),
    (False, ''),
    (False, None),
])
def test_mediatoolbar_set_label_works(MockedUiIcons, label_visibility, label_text, settings):
    """
    Test if MediaToolbar's set_label function works
    """
    # GIVEN: MediaToolbar
    toolbar = MediaToolbar(None)
    toolbar.identification_label = MagicMock()
    # WHEN: Label is set
    toolbar.set_label(label_text)
    # THEN: Identification_label should match set_text call
    toolbar.identification_label.setVisible.assert_called_once_with(label_visibility)
    # 'None' texts are empty
    toolbar.identification_label.setText.assert_called_once_with(label_text if label_text else '')


def test_clickable_slider_click_at_left_edge(qapp):
    """
    Test that clicking at the left edge of the slider sets minimum value.
    """
    # GIVEN: A ClickableSlider with range 0-100
    slider = ClickableSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)
    slider.setFixedWidth(100)
    slider.show()
    slider.raise_()

    # WHEN: A click event at x=0 (left edge) is simulated
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(0, 0),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier
    )
    slider.mousePressEvent(event)

    # THEN: The slider value should be at or near minimum
    assert slider.value() <= 5, f"Expected value <= 5, got {slider.value()}"


def test_clickable_slider_click_at_right_edge(qapp):
    """
    Test that clicking at the right edge of the slider sets maximum value.
    """
    # GIVEN: A ClickableSlider with range 0-100
    slider = ClickableSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)
    slider.setFixedWidth(100)
    slider.show()
    slider.raise_()

    # WHEN: A click event at x=99 (right edge) is simulated
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(99, 0),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier
    )
    slider.mousePressEvent(event)

    # THEN: The slider value should be at or near maximum
    assert slider.value() >= 95, f"Expected value >= 95, got {slider.value()}"


def test_clickable_slider_click_at_middle(qapp):
    """
    Test that clicking in the middle of the slider sets middle value.
    """
    # GIVEN: A ClickableSlider with range 0-100
    slider = ClickableSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)
    slider.setFixedWidth(100)
    slider.show()
    slider.raise_()

    # WHEN: A click event at x=50 (middle) is simulated
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(50, 0),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier
    )
    slider.mousePressEvent(event)

    # THEN: The slider value should be around 50 (allows 5% tolerance)
    assert 45 <= slider.value() <= 55, f"Expected value 45-55, got {slider.value()}"

