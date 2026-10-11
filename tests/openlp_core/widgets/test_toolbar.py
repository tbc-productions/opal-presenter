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
from opal.core.widgets import fluent as QtWidgets

from opal.core.widgets.toolbar import MediaToolbar, ClickableSlider, OpenLPToolbar


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
@patch('opal.core.widgets.toolbar.UiIcons')
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
@patch('opal.core.widgets.toolbar.UiIcons')
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


@patch('opal.core.widgets.toolbar.UiIcons')
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


@patch('opal.core.widgets.toolbar.UiIcons')
def test_mediatoolbar_places_seek_controls_in_toolbar(MockedUiIcons, settings):
    """Seek controls should be in their own toolbar directly below the main toolbar."""
    toolbar = MediaToolbar(None)

    assert toolbar.layout().count() == 2
    assert toolbar.layout().itemAt(0).widget() is toolbar._toolbar
    assert toolbar.layout().itemAt(1).widget() is toolbar._seek_toolbar
    assert toolbar.seek_slider.parent() is toolbar._seek_toolbar


@patch('opal.core.widgets.toolbar.UiIcons')
def test_mediatoolbar_volume_label_width_is_fixed(MockedUiIcons, settings):
    """Changing volume text should not change volume label width."""
    toolbar = MediaToolbar(None)

    fixed_width = toolbar.volume_label.width()
    toolbar.volume_label.setText('5')
    narrow_width = toolbar.volume_label.width()
    toolbar.volume_label.setText('100')
    wide_width = toolbar.volume_label.width()

    assert narrow_width == fixed_width
    assert wide_width == fixed_width

    margins = toolbar.volume_label.contentsMargins()
    minimum_required = toolbar.volume_label.fontMetrics().horizontalAdvance('100') + margins.left() + margins.right()
    assert fixed_width >= minimum_required


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


def test_clickable_slider_click_then_drag_scrubs_position(qapp):
    """Click-to-seek should still allow immediate drag scrubbing."""
    slider = ClickableSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)
    slider.setFixedWidth(100)
    slider.show()
    slider.raise_()

    press_event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(10, 0),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier
    )
    slider.mousePressEvent(press_event)

    move_event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(90, 0),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier
    )
    slider.mouseMoveEvent(move_event)

    release_event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease,
        QtCore.QPointF(90, 0),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier
    )
    slider.mouseReleaseEvent(release_event)

    assert slider.value() >= 80, f"Expected value >= 80 after dragging, got {slider.value()}"


def test_set_widget_enabled_disables_embedded_widget(qapp):
    """Disabling a toolbar widget should disable the underlying embedded widget too."""
    toolbar = OpenLPToolbar(None)
    button = QtWidgets.QToolButton()
    button.setObjectName('test_button')
    toolbar.add_toolbar_widget(button)

    toolbar.set_widget_enabled('test_button', False)

    assert toolbar.actions_map['test_button'].isEnabled() is False
    assert button.isEnabled() is False

    toolbar.set_widget_enabled('test_button', True)

    assert toolbar.actions_map['test_button'].isEnabled() is True
    assert button.isEnabled() is True

