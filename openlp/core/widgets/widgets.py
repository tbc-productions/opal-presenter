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
The :mod:`~openlp.core.widgets.widgets` module contains custom widgets used in OpenLP
"""
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QAbstractButton
import fluentqt
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.common.settings import ProxyMode
from openlp.core.lib.ui import critical_error_message_box


def _coerce_bounded_int(value, default, minimum=None, maximum=None):
    """
    Convert a value to an int, applying optional bounds and fallback defaults.
    """
    if isinstance(value, int):
        int_value = value
    elif isinstance(value, str) and value.strip().lstrip('-').isdigit():
        int_value = int(value)
    else:
        int_value = default
    if minimum is not None:
        int_value = max(minimum, int_value)
    if maximum is not None:
        int_value = min(maximum, int_value)
    return int_value


class ProxyWidget(QtWidgets.QGroupBox):
    """
    A proxy settings widget that implements loading and saving its settings.
    """
    def __init__(self, parent=None):
        """
        Initialise the widget.

        :param QtWidgets.QWidget | None parent: The widgets parent
        """
        super().__init__(parent)
        self.settings = Registry().get('settings')
        self._setup()

    def _setup(self):
        """
        A setup method seperate from __init__ to allow easier testing
        """
        self.setup_ui()
        self.load()

    def setup_ui(self):
        """
        Create the widget layout and sub widgets
        """
        self.layout = QtWidgets.QFormLayout(self)
        self.radio_group = QtWidgets.QButtonGroup(self)
        self.no_proxy_radio = QtWidgets.QRadioButton('', self)
        self.radio_group.addButton(self.no_proxy_radio, ProxyMode.NO_PROXY)
        self.layout.setWidget(0, QtWidgets.QFormLayout.ItemRole.SpanningRole, self.no_proxy_radio)
        self.use_sysem_proxy_radio = QtWidgets.QRadioButton('', self)
        self.radio_group.addButton(self.use_sysem_proxy_radio, ProxyMode.SYSTEM_PROXY)
        self.layout.setWidget(1, QtWidgets.QFormLayout.ItemRole.SpanningRole, self.use_sysem_proxy_radio)
        self.manual_proxy_radio = QtWidgets.QRadioButton('', self)
        self.radio_group.addButton(self.manual_proxy_radio, ProxyMode.MANUAL_PROXY)
        self.layout.setWidget(2, QtWidgets.QFormLayout.ItemRole.SpanningRole, self.manual_proxy_radio)
        self.http_edit = QtWidgets.QLineEdit(self)
        self.layout.addRow('HTTP:', self.http_edit)
        self.https_edit = QtWidgets.QLineEdit(self)
        self.layout.addRow('HTTPS:', self.https_edit)
        self.username_edit = QtWidgets.QLineEdit(self)
        self.layout.addRow('Username:', self.username_edit)
        self.password_edit = QtWidgets.QLineEdit(self)
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.layout.addRow('Password:', self.password_edit)
        # Signal / Slots
        self.radio_group.buttonToggled.connect(self.on_radio_group_button_toggled)

    def on_radio_group_button_toggled(self, button, checked):
        """
        Handles the toggled signal on the radio buttons. The signal is emitted twice if a radio butting being toggled on
        causes another radio button in the group to be toggled off.

        En/Disables the `Manual Proxy` line edits depending on the currently selected radio button

        :param QtWidgets.QRadioButton button: The button that has toggled
        :param bool checked: The buttons new state
        """
        group_id = self.radio_group.id(button)  # The work around (see above comment)
        enable_manual_edits = group_id == ProxyMode.MANUAL_PROXY and checked
        self.http_edit.setEnabled(enable_manual_edits)
        self.https_edit.setEnabled(enable_manual_edits)
        self.username_edit.setEnabled(enable_manual_edits)
        self.password_edit.setEnabled(enable_manual_edits)

    def retranslate_ui(self):
        """
        Translate the Ui
        """
        self.setTitle(translate('OpenLP.ProxyWidget', 'Proxy Server Settings'))
        self.no_proxy_radio.setText(translate('OpenLP.ProxyWidget', 'No prox&y'))
        self.use_sysem_proxy_radio.setText(translate('OpenLP.ProxyWidget', '&Use system proxy'))
        self.manual_proxy_radio.setText(translate('OpenLP.ProxyWidget', '&Manual proxy configuration'))
        proxy_example = translate('OpenLP.ProxyWidget', 'e.g. proxy_server_address:port_no')
        self.layout.labelForField(self.http_edit).setText(translate('OpenLP.ProxyWidget', 'HTTP:'))
        self.http_edit.setPlaceholderText(proxy_example)
        self.layout.labelForField(self.https_edit).setText(translate('OpenLP.ProxyWidget', 'HTTPS:'))
        self.https_edit.setPlaceholderText(proxy_example)
        self.layout.labelForField(self.username_edit).setText(translate('OpenLP.ProxyWidget', 'Username:'))
        self.layout.labelForField(self.password_edit).setText(translate('OpenLP.ProxyWidget', 'Password:'))

    def load(self):
        """
        Load the data from the settings to the widget.
        """
        checked_radio = self.radio_group.button(self.settings.value('advanced/proxy mode'))
        checked_radio.setChecked(True)
        self.http_edit.setText(self.settings.value('advanced/proxy http'))
        self.https_edit.setText(self.settings.value('advanced/proxy https'))
        self.username_edit.setText(self.settings.value('advanced/proxy username'))
        self.password_edit.setText(self.settings.value('advanced/proxy password'))

    def save(self):
        """
        Save the widget data to the settings
        """
        self.settings.setValue('advanced/proxy mode', self.radio_group.checkedId())
        self.settings.setValue('advanced/proxy http', self.http_edit.text())
        self.settings.setValue('advanced/proxy https', self.https_edit.text())
        self.settings.setValue('advanced/proxy username', self.username_edit.text())
        self.settings.setValue('advanced/proxy password', self.password_edit.text())


class ProxyDialog(QtWidgets.FormDialog):
    """
    A basic dialog to show proxy settingd
    """
    def __init__(self, *args, show_ftw_options=False, timeout=5, retries=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_ftw_options = show_ftw_options
        self.timeout = timeout
        self.retries = retries
        self.dialog_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.proxy_widget = ProxyWidget(self)
        self.dialog_layout.addWidget(self.proxy_widget)
        self.ftw_options_group_box = None
        self.timeout_spin_box = None
        self.retries_spin_box = None
        if self.show_ftw_options:
            self.ftw_options_group_box = QtWidgets.QGroupBox(self)
            self.ftw_options_layout = QtWidgets.QFormLayout(self.ftw_options_group_box)
            self.timeout_spin_box = QtWidgets.QSpinBox(self.ftw_options_group_box)
            self.timeout_spin_box.setRange(1, 120)
            self.timeout_spin_box.setValue(_coerce_bounded_int(timeout, 5, minimum=1, maximum=120))
            self.ftw_options_layout.addRow('Timeout:', self.timeout_spin_box)
            self.retries_spin_box = QtWidgets.QSpinBox(self.ftw_options_group_box)
            self.retries_spin_box.setRange(0, 10)
            self.retries_spin_box.setValue(_coerce_bounded_int(retries, 0, minimum=0, maximum=10))
            self.ftw_options_layout.addRow('Number of retry attempts:', self.retries_spin_box)
            self.dialog_layout.addWidget(self.ftw_options_group_box)
        self.button_box = \
            QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                       QtWidgets.QDialogButtonBox.StandardButton.Cancel, self)
        self.dialog_layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.setButtonBox(self.button_box)
        self.retranslate_ui()

    def accept(self):
        """
        Reimplement the accept slot so that the ProxyWidget settings can be saved.
        :rtype: None
        """
        self.proxy_widget.save()
        if self.show_ftw_options:
            self.timeout = self.timeout_spin_box.value()
            self.retries = self.retries_spin_box.value()
        super().accept()

    def retranslate_ui(self):
        self.proxy_widget.retranslate_ui()
        if self.show_ftw_options:
            self.ftw_options_group_box.setTitle(translate('OpenLP.ProxyDialog', 'Download Settings'))
            self.ftw_options_layout.labelForField(self.timeout_spin_box).setText(
                translate('OpenLP.ProxyDialog', 'Timeout (seconds):'))
            self.ftw_options_layout.labelForField(self.retries_spin_box).setText(
                translate('OpenLP.ProxyDialog', 'Number of retry attempts:'))
            self.setWindowTitle(translate('OpenLP.ProxyDialog', 'Internet Settings'))
        else:
            self.setWindowTitle(translate('OpenLP.ProxyDialog', 'Proxy Server Settings'))


class ScreenButton(QAbstractButton):
    """A proportional monitor tile with mouse, keyboard and accessible button selection."""

    def __init__(self, parent, screen):
        super().__init__(parent)
        self.setObjectName(f'screen_{screen.number}_button')
        self.screen = screen
        self.selector = self
        self.setCheckable(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._theme_host = fluentqt.FluentWidget(self)
        self._theme_host.hide()
        name = getattr(screen, 'name', '')
        self.monitor_name = name if isinstance(name, str) else ''
        description = str(screen)
        if self.monitor_name:
            description += '\n' + self.monitor_name
        if isinstance(screen.geometry, QtCore.QRect):
            description += '\n' + translate('OpenLP.ScreenButton', '{width} x {height} pixels').format(
                width=screen.geometry.width(), height=screen.geometry.height())
        self.setText(description)
        self.setAccessibleName(description.replace('\n', ', '))
        self.setToolTip(description)
        self.toggled.connect(self.update)

    def sizeHint(self):
        geometry = self.screen.geometry
        if isinstance(geometry, QtCore.QRect) and geometry.width() > 0:
            return QtCore.QSize(320, round(320 * geometry.height() / geometry.width()))
        return QtCore.QSize(320, 180)

    def paintEvent(self, event):
        colors = self._theme_host.theme_tokens().colors
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        bounds = QtCore.QRectF(self.rect()).adjusted(3, 3, -3, -3)
        selected = self.isChecked()
        background = colors.accentDefault if selected else colors.controlDefault
        if self.isDown():
            background = colors.accentTertiary if selected else colors.controlTertiary
        elif self.underMouse():
            background = colors.accentSecondary if selected else colors.controlSecondary
        painter.setBrush(background)
        painter.setPen(QtGui.QPen(colors.accentDefault if selected else colors.strokeStrong, 2))
        painter.drawRoundedRect(bounds, 8, 8)
        if self.hasFocus():
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(colors.strokeFocusOuter, 2, QtCore.Qt.PenStyle.DashLine))
            painter.drawRoundedRect(bounds.adjusted(4, 4, -4, -4), 5, 5)
        painter.setPen(colors.textOnAccent if selected else colors.textPrimary)
        text_bounds = bounds.adjusted(10, 8, -10, -8)
        # Keep numbers readable on small tiles; full details remain in the tooltip and selected-screen label.
        number_font = QtGui.QFont(self.font())
        number_font.setPixelSize(max(14, min(36, round(self.height() / 4))))
        number_font.setBold(True)
        painter.setFont(number_font)
        number_height = QtGui.QFontMetrics(number_font).height()
        label_font = QtGui.QFont(self.font())
        label_font.setPixelSize(12)
        label_height = QtGui.QFontMetrics(label_font).height()
        lines = []
        if self.monitor_name:
            lines.append((self.monitor_name, False))
        if self.screen.is_primary:
            lines.append((translate('OpenLP.ScreenButton', 'Primary'), True))
        if self.screen.is_display:
            lines.append((translate('OpenLP.ScreenButton', 'Projection'), False))
        visible_lines = max(0, min(len(lines), int((text_bounds.height() - number_height - 6) / label_height)))
        top = text_bounds.center().y() - (number_height + visible_lines * label_height) / 2
        painter.drawText(QtCore.QRectF(text_bounds.left(), top, text_bounds.width(), number_height),
                         QtCore.Qt.AlignmentFlag.AlignCenter, str(self.screen.number + 1))
        for index, (text, bold) in enumerate(lines[:visible_lines]):
            label_font.setBold(bold)
            painter.setFont(label_font)
            text = painter.fontMetrics().elidedText(text, QtCore.Qt.TextElideMode.ElideRight,
                                                    max(0, int(text_bounds.width())))
            painter.drawText(QtCore.QRectF(text_bounds.left(), top + number_height + index * label_height,
                                           text_bounds.width(), label_height),
                             QtCore.Qt.AlignmentFlag.AlignCenter, text)


class ScreenLayout(QtWidgets.QLayout):
    """Scale the OS desktop coordinates uniformly to fit the monitor map."""

    def __init__(self, parent):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(16, 16, 16, 16)

    def addItem(self, item):
        self.items.append(item)
        self.invalidate()

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        if 0 <= index < len(self.items):
            item = self.items.pop(index)
            self.invalidate()
            return item
        return None

    def sizeHint(self):
        return QtCore.QSize(560, 260)

    def minimumSize(self):
        return QtCore.QSize(240, 200)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        tiles = [(item.widget(), item.widget().screen.geometry) for item in self.items]
        tiles = [(widget, geometry) for widget, geometry in tiles
                 if isinstance(geometry, QtCore.QRect) and not geometry.isEmpty()]
        if not tiles:
            return
        desktop = QtCore.QRectF()
        for widget, geometry in tiles:
            desktop = desktop.united(QtCore.QRectF(geometry))
        left, top, right, bottom = self.getContentsMargins()
        available = QtCore.QRectF(rect).adjusted(left, top, -right, -bottom)
        scale = min(available.width() / desktop.width(), available.height() / desktop.height())
        offset = available.center() - desktop.center() * scale
        for widget, geometry in tiles:
            widget.setGeometry(QtCore.QRectF(offset.x() + geometry.x() * scale,
                                             offset.y() + geometry.y() * scale,
                                             geometry.width() * scale, geometry.height() * scale).toRect())


class ScreenIdentificationBanner(QtWidgets.QWidget):
    """Animated floating dots behind a large, high-contrast screen identifier."""
    def __init__(self, screen):
        super().__init__()
        self.setObjectName('screen_identification_banner')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet('#screen_identification_banner { background-color: #0f172a; }')
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint |
                            QtCore.Qt.WindowType.Tool |
                            QtCore.Qt.WindowType.WindowStaysOnTopHint |
                            QtCore.Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setGeometry(screen.geometry.x(), screen.geometry.y(), screen.geometry.width(), 160)
        layout = QtWidgets.QStackedLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)
        self.backdrop = fluentqt.ParticleBackdrop(self)
        self.backdrop.setEffect(fluentqt.ParticleBackdrop.Effect.FloatingDots)
        self.backdrop.setBackgroundMode(fluentqt.ParticleBackdrop.BackgroundMode.Transparent)
        self.backdrop.setGpuAccelerationEnabled(False)
        self.backdrop.setParticleCount(200)
        self.backdrop.setSpeed(1.0)
        self.backdrop.setMaximumFrameRate(30)
        self.backdrop.setInteractive(False)
        self.backdrop.setPauseWhenInactive(False)
        self.backdrop.setAnimationEnabled(True)
        layout.addWidget(self.backdrop)
        self.label = QtWidgets.QLabel(str(screen), self)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet('font-size: 64pt; font-weight: 600; color: #ffffff; background: transparent;')
        layout.addWidget(self.label)
        layout.setCurrentWidget(self.label)


class ScreenDisplaySettings(QtWidgets.Card):
    """A screen section whose details remain readable above its display toggle."""
    clicked = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enable_display_check = QtWidgets.QCheckBox(self)
        self.display_options = QtWidgets.QWidget(self)
        self.enable_display_check.clicked.connect(self.clicked)
        self.enable_display_check.toggled.connect(self.display_options.setEnabled)
        self.display_options.setEnabled(False)

    def setTitle(self, title):
        self.enable_display_check.setText(title)

    def isChecked(self):
        return self.enable_display_check.isChecked()

    def setChecked(self, checked):
        self.enable_display_check.setChecked(checked)


class ScreenSelectionWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, screens=None):
        super().__init__(parent)
        self.current_screen = None
        self.identify_labels = []
        self.screens = screens or []
        self.identify_seconds_remaining = 0
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_identify_timer_shot)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QtWidgets.QVBoxLayout(self)
        self.screen_frame = QtWidgets.QFrame(self)
        self.screen_frame.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.screen_frame.setObjectName('screen_frame')
        self.screen_frame.setFixedHeight(260)
        self.screen_frame_layout = ScreenLayout(self.screen_frame)
        self.screen_frame_layout.setObjectName('screen_frame_layout')
        self.layout.addWidget(self.screen_frame)
        # Mirrored/overlapping monitors can obscure one another in the OS map.
        self.overlapping_screen_combo = QtWidgets.QComboBox(self)
        self.overlapping_screen_combo.setObjectName('overlapping_screen_combo')
        self.overlapping_screen_combo.hide()
        self.overlapping_screen_combo.currentIndexChanged.connect(self.on_overlapping_screen_selected)
        self.layout.addWidget(self.overlapping_screen_combo)
        self.identify_layout = QtWidgets.QVBoxLayout()
        self.display_group_box = ScreenDisplaySettings(self)
        self.display_group_box.setObjectName('display_group_box')
        self.screen_details_layout = QtWidgets.QVBoxLayout(self.display_group_box)
        self.screen_details_layout.setObjectName('screen_details_layout')
        self.screen_details_layout.setContentsMargins(16, 16, 16, 16)
        self.screen_details_layout.setSpacing(12)
        self.screen_info_layout = QtWidgets.QVBoxLayout()
        self.screen_info_layout.setSpacing(2)
        self.screen_number_label = QtWidgets.QLabel(self.display_group_box)
        self.screen_number_label.setObjectName('screen_number_label')
        self.screen_number_label.setFluentTypography(fluentqt.FontRole.Subtitle)
        self.screen_name_label = QtWidgets.QLabel(self.display_group_box)
        self.screen_name_label.setObjectName('screen_name_label')
        self.screen_name_label.setFluentTypography(fluentqt.FontRole.BodyStrong)
        self.screen_resolution_label = QtWidgets.QLabel(self.display_group_box)
        self.screen_resolution_label.setObjectName('screen_resolution_label')
        self.screen_resolution_label.setFluentTypography(fluentqt.FontRole.Caption)
        for label in (self.screen_number_label, self.screen_name_label, self.screen_resolution_label):
            label.setWordWrap(True)
            label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.screen_info_layout.addWidget(self.screen_number_label)
        self.screen_name_layout = QtWidgets.QHBoxLayout()
        self.screen_name_layout.setSpacing(6)
        for label in (self.screen_name_label, self.screen_resolution_label):
            label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Preferred)
            self.screen_name_layout.addWidget(label, alignment=QtCore.Qt.AlignmentFlag.AlignBaseline)
        self.screen_resolution_label.setWordWrap(False)
        self.screen_name_layout.addStretch()
        self.screen_info_layout.addLayout(self.screen_name_layout)
        self.screen_details_layout.addLayout(self.screen_info_layout)
        self.use_screen_check_box = self.display_group_box.enable_display_check
        self.screen_details_layout.addWidget(self.use_screen_check_box)
        self.screen_details_layout.addWidget(self.display_group_box.display_options)
        self.display_group_box_layout = QtWidgets.QGridLayout(self.display_group_box.display_options)
        self.display_group_box_layout.setContentsMargins(0, 0, 0, 0)
        self.display_group_box_layout.setSpacing(8)
        self.display_group_box_layout.setObjectName('display_group_box_layout')
        self.full_screen_radio_button = QtWidgets.QRadioButton(self.display_group_box.display_options)
        self.full_screen_radio_button.setObjectName('full_screen_radio_button')
        self.display_group_box_layout.addWidget(self.full_screen_radio_button, 0, 0, 1, 4)
        self.custom_geometry_button = QtWidgets.QRadioButton(self.display_group_box.display_options)
        self.custom_geometry_button.setObjectName('custom_geometry_button')
        self.display_group_box_layout.addWidget(self.custom_geometry_button, 1, 0, 1, 4)
        self.left_label = QtWidgets.QLabel(self.display_group_box.display_options)
        self.left_label.setObjectName('left_label')
        self.display_group_box_layout.addWidget(self.left_label, 2, 0)
        self.top_label = QtWidgets.QLabel(self.display_group_box.display_options)
        self.top_label.setObjectName('top_label')
        self.display_group_box_layout.addWidget(self.top_label, 2, 2)
        self.width_label = QtWidgets.QLabel(self.display_group_box.display_options)
        self.width_label.setObjectName('width_label')
        self.display_group_box_layout.addWidget(self.width_label, 3, 0)
        self.height_label = QtWidgets.QLabel(self.display_group_box.display_options)
        self.height_label.setObjectName('height_label')
        self.display_group_box_layout.addWidget(self.height_label, 3, 2)
        self.left_spin_box = QtWidgets.QSpinBox(self.display_group_box.display_options)
        self.left_spin_box.setObjectName('left_spin_box')
        self.left_spin_box.setEnabled(False)
        self.display_group_box_layout.addWidget(self.left_spin_box, 2, 1)
        self.top_spin_box = QtWidgets.QSpinBox(self.display_group_box.display_options)
        self.top_spin_box.setObjectName('top_spin_box')
        self.top_spin_box.setEnabled(False)
        self.display_group_box_layout.addWidget(self.top_spin_box, 2, 3)
        self.width_spin_box = QtWidgets.QSpinBox(self.display_group_box.display_options)
        self.width_spin_box.setObjectName('width_spin_box')
        self.width_spin_box.setEnabled(False)
        self.display_group_box_layout.addWidget(self.width_spin_box, 3, 1)
        self.height_spin_box = QtWidgets.QSpinBox(self.display_group_box.display_options)
        self.height_spin_box.setObjectName('height_spin_box')
        self.height_spin_box.setEnabled(False)
        self.display_group_box_layout.addWidget(self.height_spin_box, 3, 3)
        self.display_group_box_layout.setColumnStretch(1, 1)
        self.display_group_box_layout.setColumnStretch(3, 1)
        self.display_group_box_layout.setHorizontalSpacing(16)
        self.identify_button = QtWidgets.QPushButton(self)
        self.identify_button.setObjectName('identify_button')
        self.identify_layout.addWidget(self.identify_button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.identify_layout.addWidget(self.display_group_box)
        self.screen_button_group = QtWidgets.QButtonGroup(self.screen_frame)
        self.screen_button_group.setExclusive(True)
        self.screen_button_group.setObjectName('screen_button_group')
        self.layout.addLayout(self.identify_layout)
        self.layout.addStretch()

        # Signals and slots
        self.display_group_box.clicked.connect(self.on_display_clicked)
        self.custom_geometry_button.toggled.connect(self.height_spin_box.setEnabled)
        self.custom_geometry_button.toggled.connect(self.left_spin_box.setEnabled)
        self.custom_geometry_button.toggled.connect(self.top_spin_box.setEnabled)
        self.custom_geometry_button.toggled.connect(self.width_spin_box.setEnabled)
        self.identify_button.clicked.connect(self.on_identify_button_clicked)

        self._setup_spin_box(self.left_spin_box, -99999, 99999, 0)
        self._setup_spin_box(self.top_spin_box, -99999, 99999, 0)
        self._setup_spin_box(self.width_spin_box, -99999, 99999, 0)
        self._setup_spin_box(self.height_spin_box, -99999, 99999, 0)

        self.retranslate_ui()

    def retranslate_ui(self):
        self.full_screen_radio_button.setText(translate('OpenLP.ScreensTab', 'F&ull screen'))
        self.width_label.setText(translate('OpenLP.ScreensTab', 'Width:'))
        use_screen_str = translate('OpenLP.ScreensTab', 'Use this screen as a display')
        self.use_screen_check_box.setText(use_screen_str)
        self.display_group_box.setTitle(use_screen_str)
        self.left_label.setText(translate('OpenLP.ScreensTab', 'Left:'))
        self.custom_geometry_button.setText(translate('OpenLP.ScreensTab', 'Custom &geometry'))
        self.top_label.setText(translate('OpenLP.ScreensTab', 'Top:'))
        self.height_label.setText(translate('OpenLP.ScreensTab', 'Height:'))
        self.identify_button.setText(translate('OpenLP.ScreensTab', 'Identify Screens'))
        self.overlapping_screen_combo.setAccessibleName(translate('OpenLP.ScreensTab', 'Select a screen'))
        self.overlapping_screen_combo.setToolTip(translate(
            'OpenLP.ScreensTab', 'Some screens overlap in your system display settings. '
            'You can select each screen here.'))

    def on_display_clicked(self, is_checked):
        if not is_checked:
            critical_error_message_box(translate('OpenLP.ScreensTab', 'Select a Display'),
                                       translate('OpenLP.ScreensTab', 'You need to select at least one screen to be '
                                                 'used as a display. Select the screen you wish to use as a display, '
                                                 'and check the checkbox for that screen.'),
                                       parent=self, question=False)
            self.use_screen_check_box.setChecked(True)
            self.display_group_box.setChecked(True)
        else:
            for screen in self.screens:
                screen.is_display = False
            self.current_screen.is_display = True
            for button in self.screen_button_group.buttons():
                button.update()

    def _save_screen(self, screen):
        """
        Save the details in the UI to the screen

        :param openlp.core.display.screens.Screen screen:
        :return: None
        """
        if not screen:
            return
        screen.is_display = self.display_group_box.isChecked()
        if self.custom_geometry_button.isChecked():
            screen.custom_geometry = QtCore.QRect(self.left_spin_box.value(), self.top_spin_box.value(),
                                                  self.width_spin_box.value(), self.height_spin_box.value())
        else:
            screen.custom_geometry = None

    def _setup_spin_box(self, spin_box, mininum, maximum, value):
        """
        Set up the spin box

        :param QtWidgets.QSpinBox spin_box:
        :param int minimun:
        :param int maximum:
        :param int value:
        :return: None
        """
        spin_box.setMinimum(mininum)
        spin_box.setMaximum(maximum)
        spin_box.setValue(value)

    def load(self):
        selected_screen = self.current_screen
        self.current_screen = None
        # Remove all the existing items in the layout
        while self.screen_frame_layout.count() > 0:
            item = self.screen_frame_layout.takeAt(0)
            if item.widget() is not None:
                widget = item.widget()
                if widget.selector in self.screen_button_group.buttons():
                    self.screen_button_group.removeButton(widget.selector)
                widget.setParent(None)
                widget.deleteLater()
            del item
        # Keep the selected monitor on refresh; otherwise start with the projection monitor.
        screens = list(self.screens)
        if selected_screen not in screens:
            selected_screen = next((screen for screen in screens if screen.is_display), screens[0] if screens else None)
        selected_button = None
        with QtCore.QSignalBlocker(self.overlapping_screen_combo):
            self.overlapping_screen_combo.clear()
            for screen in screens:
                name = getattr(screen, 'name', '')
                label = str(screen) + (' - ' + name if isinstance(name, str) and name else '')
                self.overlapping_screen_combo.addItem(label, screen.number)
        geometries = [screen.geometry for screen in screens if isinstance(screen.geometry, QtCore.QRect)]
        self.overlapping_screen_combo.setVisible(any(
            geometry.intersects(other)
            for index, geometry in enumerate(geometries) for other in geometries[index + 1:]))
        # Add the existing screens into the frame
        for screen in self.screens:
            screen_button = ScreenButton(self.screen_frame, screen)
            screen_button.clicked.connect(self.on_screen_button_clicked)
            self.screen_frame_layout.addWidget(screen_button)
            self.screen_button_group.addButton(screen_button.selector)
            if screen is selected_screen:
                selected_button = screen_button
        if selected_button is not None:
            selected_button.click()
        else:
            for label in (self.screen_number_label, self.screen_name_label, self.screen_resolution_label):
                label.setText('')
        self.identify_button.setEnabled(bool(screens))
        self.display_group_box.setEnabled(bool(screens))

    def save(self):
        """
        Save the screen settings
        """
        self._save_screen(self.current_screen)
        screen_settings = {}
        for screen in self.screens:
            screen_settings[screen.number] = screen.to_dict()
        Registry().get('settings').setValue('core/screens', screen_settings)
        # On save update the screens as well

    def use_simple_view(self):
        """
        Hide advanced options. Added for use in the FTW

        :rtype: None
        """
        self.use_screen_check_box.setVisible(True)
        self.display_group_box.display_options.setVisible(False)

    @QtCore.Slot()
    def _on_identify_timer_shot(self):
        self.identify_seconds_remaining = max(0, self.identify_seconds_remaining - 1)
        if self.identify_seconds_remaining:
            self._update_identify_button()
        else:
            self._clear_identification()

    def _update_identify_button(self):
        text = translate('OpenLP.ScreensTab', 'Identify Screens')
        if self.identify_seconds_remaining:
            text = f'{text} ({self.identify_seconds_remaining})'
        self.identify_button.setText(text)

    def _clear_identification(self):
        self.timer.stop()
        for banner in self.identify_labels:
            banner.hide()
            banner.setParent(None)
            banner.deleteLater()
        self.identify_labels = []
        self.identify_seconds_remaining = 0
        self._update_identify_button()

    def on_identify_button_clicked(self):
        """Identify every screen for five seconds and show the time remaining."""
        self._clear_identification()
        for screen in self.screens:
            banner = ScreenIdentificationBanner(screen)
            banner.show()
            self.identify_labels.append(banner)
        if self.identify_labels:
            self.identify_seconds_remaining = 5
            self._update_identify_button()
            self.timer.start()

    def hideEvent(self, event):
        self._clear_identification()
        super().hideEvent(event)

    def on_overlapping_screen_selected(self, index):
        number = self.overlapping_screen_combo.itemData(index)
        for button in self.screen_button_group.buttons():
            if button.screen.number == number:
                button.click()
                break

    def on_screen_button_clicked(self):
        """
        Respond to a screen button being clicked
        """
        screen = self.sender().screen
        if self.current_screen is not screen:
            self._save_screen(self.current_screen)
        name = getattr(screen, 'name', '')
        name = name if isinstance(name, str) else ''
        self.screen_number_label.setText(str(screen))
        self.screen_name_label.setText(name)
        self.screen_name_label.setVisible(bool(name))
        resolution = translate('OpenLP.ScreenButton', '{width} x {height} pixels').format(
            width=screen.geometry.width(), height=screen.geometry.height())
        self.screen_resolution_label.setText(('- ' if name else '') + resolution)
        self.use_screen_check_box.setChecked(screen.is_display)
        self.display_group_box.setChecked(screen.is_display)
        self.full_screen_radio_button.setChecked(screen.custom_geometry is None)
        self.custom_geometry_button.setChecked(screen.custom_geometry is not None)
        if isinstance(screen.custom_geometry, QtCore.QRect):
            self.left_spin_box.setValue(screen.custom_geometry.x())
            self.top_spin_box.setValue(screen.custom_geometry.y())
            self.width_spin_box.setValue(screen.custom_geometry.width())
            self.height_spin_box.setValue(screen.custom_geometry.height())
        else:
            self.left_spin_box.setValue(0)
            self.top_spin_box.setValue(0)
            self.width_spin_box.setValue(screen.geometry.width())
            self.height_spin_box.setValue(screen.geometry.height())

        self.current_screen = screen
        with QtCore.QSignalBlocker(self.overlapping_screen_combo):
            self.overlapping_screen_combo.setCurrentIndex(self.overlapping_screen_combo.findData(screen.number))
