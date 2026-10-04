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
Provide common toolbar handling for OpenLP
"""
import logging

from PySide6 import QtCore, QtGui

from openlp.core.ui.fluenticons import fluent_icon
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.common.i18n import translate

from openlp.core.lib.ui import create_action
from openlp.core.ui.icons import UiIcons


log = logging.getLogger(__name__)


class ClickableSlider(QtWidgets.QSlider):
    """
    A QSlider subclass that allows clicking anywhere on the progress bar to jump to that position.
    """

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Handle mouse press events to allow click-to-seek.
        """
        if self.orientation() == QtCore.Qt.Orientation.Horizontal and \
                event.button() == QtCore.Qt.MouseButton.LeftButton:
            click_x = event.pos().x()
            slider_width = self.width()
            if slider_width > 0:
                ratio = click_x / slider_width
                ratio = max(0.0, min(1.0, ratio))
                new_value = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
                new_value = max(self.minimum(), min(self.maximum(), new_value))
                # Move the handle to the click location first, then let Qt continue handling the press.
                # This keeps drag scrubbing working naturally after clicking anywhere on the slider.
                self.setSliderPosition(new_value)
                self.setValue(new_value)
        super().mousePressEvent(event)


class OpenLPToolbar(QtWidgets.QToolBar):
    """
    Lots of toolbars around the place, so it makes sense to have a common way to manage them. This is the base toolbar
    class.
    """
    def __init__(self, parent, *, single_command_bar=True):
        """
        Initialise the toolbar.
        """
        super().__init__(parent, single_command_bar=single_command_bar)
        # useful to be able to reuse button icons...
        self.setIconSize(QtCore.QSize(20, 20))
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.actions_map: dict[str, QtGui.QAction] = {}
        self._fluent_actions = {}
        log.debug('Init done for %s' % parent.__class__.__name__)

    def _add_action_widget(self, action, button):
        button.setDefaultAction(action)
        button.setIconSize(self.iconSize())
        button.setAutoRaise(True)
        button.setToolButtonStyle(self.toolButtonStyle())
        self.iconSizeChanged.connect(button.setIconSize)
        self.toolButtonStyleChanged.connect(button.setToolButtonStyle)
        wrapper = QtWidgets.QWidgetAction(self)
        wrapper.setDefaultWidget(button)
        button.addAction(action)

        def sync():
            wrapper.setVisible(action.isVisible())
            wrapper.setEnabled(action.isEnabled())
        action.changed.connect(sync)
        self._fluent_actions[action] = (wrapper, button, sync)
        sync()
        super().addAction(wrapper)

    def addAction(self, action, *args):
        """Use native Fluent controls for QAction-backed toolbar commands."""
        if not isinstance(action, QtGui.QAction):
            if isinstance(action, QtGui.QIcon):
                action = QtGui.QAction(action, args[0], self)
                args = args[1:]
            else:
                action = QtGui.QAction(action, self)
            if args:
                action.triggered.connect(args[0])
        if isinstance(action, QtWidgets.QWidgetAction) or action.isSeparator():
            return super().addAction(action)
        return super().addAction(action)

    def widgetForAction(self, action):
        if action in self._fluent_actions:
            return self._fluent_actions[action][1]
        return super().widgetForAction(action)

    def removeAction(self, action):
        if action in self._fluent_actions:
            wrapper, button, sync = self._fluent_actions.pop(action)
            action.changed.disconnect(sync)
            action.changed.disconnect(button._sync_action)
            super().removeAction(wrapper)
            wrapper.deleteLater()
        else:
            super().removeAction(action)

    def clear(self):
        for action in list(self._fluent_actions):
            self.removeAction(action)
        super().clear()
        self.actions_map.clear()

    def add_split_action(self, name, **kwargs):
        """A native FluentQt split button with independent primary/menu actions."""
        action = create_action(self, name, **kwargs)
        self._add_action_widget(action, QtWidgets.QSplitButton(self))
        self.actions_map[name] = action
        return action

    def add_pinned_action(self, action):
        """Keep an essential command visible outside CommandBar overflow."""
        self._add_action_widget(action, QtWidgets.QToolButton(self))

    def add_toolbar_action(self, name, *, pinned=False, **kwargs):
        """
        A method to help developers easily add a button to the toolbar. A new QAction is created by calling
        ``create_action()``. The action is added to the toolbar and the toolbar is set as parent. For more details
        please look at openlp.core.lib.ui.create_action()
        """
        action = create_action(self, name, **kwargs)
        if pinned:
            self.add_pinned_action(action)
        else:
            self.addAction(action)
        self.actions_map[name] = action
        return action

    def add_toolbar_widget(self, widget):
        """
        Add a widget and store it's handle under the widgets object name.
        """
        action = self.addWidget(widget)
        self.actions_map[widget.objectName()] = action

    def set_widget_visible(self, widgets, visible=True):
        """
        Set the visibility for a widget or a list of widgets.

        :param widgets: A list of strings or individual string with widget object names.
        :param visible: The new state as bool.
        """
        if isinstance(widgets, list):
            for handle in widgets:
                if handle in self.actions_map:
                    self.actions_map[handle].setVisible(visible)
                else:
                    log.warning('No handle "%s" in actions list.', str(handle))
        else:
            if widgets in self.actions_map:
                self.actions_map[widgets].setVisible(visible)
            else:
                log.warning('No handle "%s" in actions list.', str(widgets))

    def set_widget_enabled(self, widgets, enabled=True):
        """
        Set the enabled state for a widget or a list of widgets.

        :param widgets: A list of strings or individual string with widget object names.
        :param enabled: The new state as bool.
        """
        if not isinstance(widgets, list):
            widgets = [widgets]
        for handle in widgets:
            if handle in self.actions_map:
                action = self.actions_map[handle]
                action.setEnabled(enabled)
                widget = self.widgetForAction(action)
                if widget is not None:
                    widget.setEnabled(enabled)
            else:
                log.warning('No handle "%s" in actions list.', str(handle))

    def set_widget_checked(self, widgets, checked=True):
        """
        Set the checked state for a widget or a list of widgets.

        :param widgets: A list of string with widget object names.
        :param enabled: The new state as bool.
        """
        if isinstance(widgets, list):
            for handle in widgets:
                if handle in self.actions_map:
                    self.actions_map[handle].setChecked(checked)
                else:
                    log.warning('No handle "%s" in actions list.', str(handle))
        else:
            if widgets in self.actions_map:
                self.actions_map[widgets].setChecked(checked)
            else:
                log.warning('No handle "%s" in actions list.', str(widgets))

    def remove_widget(self, name):
        """
        Find and remove an action from the toolbar
        :param name: The name of the action to me removed
        :return:
        """
        try:
            act = self.actions_map[name]
            self.removeAction(act)
        except KeyError:
            log.warning(f'No handle {name} in actions list.')

    def add_spacer(self):
        """Right-align the following commands within the shared CommandBar."""
        super().add_spacer()


class MediaToolbar(QtWidgets.QWidget):
    """
    A two-toolbar media control bar.
    Top row: playback and volume controls.
    Bottom row: current-time label, seek slider, and total-time label.
    """

    def __init__(self, parent, hide_components=[], action_prefixes=''):
        super().__init__(parent)
        self.parent = parent
        self.on_action = lambda *args: None
        self.hide_components = hide_components
        self.action_prefixes = action_prefixes
        self._last_nonzero_volume = 100
        # Inner toolbar holds the action buttons so actions_map still works.
        self._toolbar = OpenLPToolbar(self)
        self.setup_ui()

    @property
    def actions_map(self):
        return self._toolbar.actions_map

    def setup_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        outer.addWidget(self._toolbar)

        self.identification_label = QtWidgets.QLabel()
        self.identification_label.setContentsMargins(0, 0, 8, 0)
        self.set_label(None)
        self._toolbar.add_toolbar_widget(self.identification_label)

        self._toolbar.add_toolbar_action(
            self.action_prefixes + 'playbackPlay', text='media_playback_play',
            icon=UiIcons().play,
            tooltip=translate('OpenLP.SlideController', 'Start playing media.'),
            triggers=self._on_action)
        self._toolbar.add_toolbar_action(
            self.action_prefixes + 'playbackPause', text='media_playback_pause',
            icon=UiIcons().pause,
            tooltip=translate('OpenLP.SlideController', 'Pause playing media.'),
            triggers=self._on_action)
        self._toolbar.add_toolbar_action(
            self.action_prefixes + 'playbackStop', text='media_playback_stop',
            icon=UiIcons().stop,
            tooltip=translate('OpenLP.SlideController', 'Stop playing media.'),
            triggers=self._on_action)
        if 'loop' not in self.hide_components:
            self._toolbar.add_toolbar_action(
                self.action_prefixes + 'playbackLoop', text='media_playback_loop',
                icon=UiIcons().get_icon_variant_selected('repeat'), checked=False,
                tooltip=translate('OpenLP.SlideController', 'Loop playing media.'),
                triggers=self._on_action)

        self._toolbar.add_spacer()

        if 'volume' not in self.hide_components:
            self.volume_button = QtWidgets.QToolButton()
            self.volume_button.setObjectName(self.action_prefixes + 'volume_mute_button')
            self.volume_button.setToolTip(translate('OpenLP.SlideController', 'Mute/Unmute audio.'))
            self.volume_button.setAutoRaise(True)
            self.volume_button.clicked.connect(self._toggle_mute)
            self._toolbar.add_toolbar_widget(self.volume_button)

            self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            self.volume_slider.setSingleStep(5)
            self.volume_slider.setPageStep(5)
            self.volume_slider.setTickInterval(5)
            self.volume_slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksAbove)
            self.volume_slider.setMinimum(0)
            self.volume_slider.setMaximum(100)
            self.volume_slider.setTracking(True)
            self.volume_slider.setToolTip(translate('OpenLP.SlideController', 'Audio Volume.'))
            self.volume_slider.setFixedWidth(80)
            self.volume_slider.setObjectName(self.action_prefixes + 'volume_slider')
            self.volume_slider.setValue(100)
            self._toolbar.add_toolbar_widget(self.volume_slider)
            self.volume_slider.valueChanged.connect(self._on_action)
            self._update_volume_button_icon(self.volume_slider.value())

        self.volume_label = QtWidgets.QLabel('100')
        self.volume_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.volume_label.setToolTip(translate('OpenLP.SlideController', 'Volume.'))
        self.volume_label.setContentsMargins(0, 0, 8, 0)
        volume_text_width = self.volume_label.fontMetrics().horizontalAdvance('100')
        volume_margins = self.volume_label.contentsMargins()
        self.volume_label.setFixedWidth(volume_text_width + volume_margins.left() + volume_margins.right() + 6)
        self.volume_label.setObjectName(self.action_prefixes + 'volume_label')
        self._toolbar.add_toolbar_widget(self.volume_label)

        if 'seek' not in self.hide_components:
            self._seek_toolbar = OpenLPToolbar(self)
            self._seek_toolbar.setObjectName(self.action_prefixes + 'seek_toolbar')
            self._seek_toolbar.setIconSize(QtCore.QSize(16, 16))

            self.position_label = QtWidgets.QLabel('00:00')
            self.position_label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.position_label.setToolTip(translate('OpenLP.SlideController', 'Current position.'))
            self.position_label.setMinimumWidth(40)
            self.position_label.setContentsMargins(8, 0, 0, 0)
            self.position_label.setObjectName(self.action_prefixes + 'position_label')
            self._seek_toolbar.add_toolbar_widget(self.position_label)

            self.seek_slider = ClickableSlider(QtCore.Qt.Orientation.Horizontal)
            self.seek_slider.setMaximum(1000)
            self.seek_slider.setTracking(True)
            self.seek_slider.setMouseTracking(True)
            self.seek_slider.setToolTip(translate('OpenLP.SlideController', 'Video position. Click to seek.'))
            self.seek_slider.setObjectName(self.action_prefixes + 'seek_slider')
            self.seek_slider.setMinimumWidth(140)
            self.seek_slider.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                           QtWidgets.QSizePolicy.Policy.Fixed)
            self._seek_toolbar.add_toolbar_widget(self.seek_slider)
            self.seek_slider.valueChanged.connect(self._on_action)
            self.seek_slider.sliderPressed.connect(self._on_seek_slider_pressed)
            self.seek_slider.sliderReleased.connect(self._on_seek_slider_released)

            self.duration_label = QtWidgets.QLabel('00:00')
            self.duration_label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.duration_label.setToolTip(translate('OpenLP.SlideController', 'Total duration.'))
            self.duration_label.setMinimumWidth(40)
            self.duration_label.setContentsMargins(0, 0, 8, 0)
            self.duration_label.setObjectName(self.action_prefixes + 'duration_label')
            self._seek_toolbar.add_toolbar_widget(self.duration_label)

            outer.addWidget(self._seek_toolbar)

    def _on_seek_slider_pressed(self):
        self.on_action(self.action_prefixes + 'seek_slider_pressed')

    def _on_seek_slider_released(self):
        self.on_action(self.action_prefixes + 'seek_slider_released')

    def set_label(self, label):
        if label:
            self.identification_label.setText(label)
            self.identification_label.setVisible(True)
        else:
            self.identification_label.setText('')
            self.identification_label.setVisible(False)

    def _on_action(self, *args):
        sender_name = self.sender().objectName() if self.sender().objectName() else self.sender().text()
        if sender_name == self.action_prefixes + 'volume_slider':
            value = self.volume_slider.value()
            if value > 0:
                self._last_nonzero_volume = value
            self._update_volume_button_icon(value)
        self.on_action(sender_name, *args)

    def _toggle_mute(self):
        if 'volume' in self.hide_components:
            return
        current = self.volume_slider.value()
        if current > 0:
            self._last_nonzero_volume = current
            self.volume_slider.setValue(0)
        else:
            self.volume_slider.setValue(self._last_nonzero_volume or 100)

    def _update_volume_button_icon(self, value: int):
        if not hasattr(self, 'volume_button'):
            return
        if value == 0:
            icon = UiIcons().volume_off
        else:
            icon = UiIcons().volume_high
        if not isinstance(icon, QtGui.QIcon):
            name = 'speaker_off' if value == 0 else 'speaker_2'
            icon = fluent_icon(f'ic_fluent_{name}_24_regular')
        self.volume_button.setIcon(icon)
