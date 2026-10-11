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
The :mod:`~opal.core.pages.fontselect` module contains the font selection page used in the theme wizard
"""
from PySide6 import QtCore, QtGui
import fluentqt
from opal.core.widgets import fluent as QtWidgets

from opal.core.common.i18n import translate
from opal.core.pages import GridLayoutPage
from opal.core.ui.icons import UiIcons
from opal.core.widgets.buttons import ColorButton
from opal.core.widgets.labels import FormLabel
from opal.core.widgets.fluent_inputs import FontPreviewComboBox


class FontSelectPage(GridLayoutPage):
    """
    A font selection widget
    """
    Outline = 'outline'
    Shadow = 'shadow'
    Wrap = 'wrap'
    LineSpacing = 'line_spacing'
    LetterSpacing = 'letter_spacing'

    font_name_changed = QtCore.Signal(str)
    font_color_changed = QtCore.Signal(str)
    font_weight_changed = QtCore.Signal(int)
    is_bold_changed = QtCore.Signal(bool)
    is_italic_changed = QtCore.Signal(bool)
    font_size_changed = QtCore.Signal(float)
    wrap_changed = QtCore.Signal(bool)
    line_spacing_changed = QtCore.Signal(int)
    letter_spacing_changed = QtCore.Signal(float)
    is_outline_enabled_changed = QtCore.Signal(bool)
    outline_color_changed = QtCore.Signal(str)
    outline_size_changed = QtCore.Signal(float)
    is_shadow_enabled_changed = QtCore.Signal(bool)
    shadow_color_changed = QtCore.Signal(str)
    shadow_size_changed = QtCore.Signal(float)
    shadow_blur_changed = QtCore.Signal(float)

    def __init__(self, parent=None):
        self._font_weight = 400
        super().__init__(parent)
        self._populate_font_weights()
        self.feature_widgets = {
            FontSelectPage.Outline: [self.outline_groupbox],
            FontSelectPage.Shadow: [self.shadow_groupbox],
            FontSelectPage.Wrap: [self.wrap_check_box],
            FontSelectPage.LineSpacing: [self.line_spacing_label, self.line_spacing_spinbox],
            FontSelectPage.LetterSpacing: [self.letter_spacing_label, self.letter_spacing_spinbox]
        }

    def setup_ui(self):
        row = 0
        self.text_groupbox = QtWidgets.QGroupBox(self)
        self.text_groupbox.setObjectName('text_groupbox')
        self.text_layout = QtWidgets.QGridLayout(self.text_groupbox)
        self.layout.addWidget(self.text_groupbox, row, 0, 1, 4)
        row += 1
        self.spacing_groupbox = QtWidgets.QGroupBox(self)
        self.spacing_groupbox.setObjectName('spacing_groupbox')
        self.spacing_layout = QtWidgets.QGridLayout(self.spacing_groupbox)
        self.layout.addWidget(self.spacing_groupbox, row, 0, 1, 4)
        row += 1
        text_row = 0
        spacing_row = 0
        # Font name
        self.font_name_label = FormLabel(self)
        self.font_name_label.setObjectName('font_name_label')
        self.text_layout.addWidget(self.font_name_label, text_row, 0)
        text_row += 1
        self.font_name_combobox = QtWidgets.QFontComboBox(self)
        self.font_name_combobox.setObjectName('font_name_combobox')
        self.text_layout.addWidget(self.font_name_combobox, text_row, 0, 1, 4)
        text_row += 1
        # Font color
        self.font_color_label = FormLabel(self)
        self.font_color_label.setObjectName('font_color_label')
        self.text_layout.addWidget(self.font_color_label, text_row, 0)
        text_row += 1
        self.font_color_button = ColorButton(self)
        self.font_color_button.setObjectName('font_color_button')
        self.text_layout.addWidget(self.font_color_button, text_row, 0)
        text_row += 1
        # Font style
        self.font_style_label = FormLabel(self)
        self.font_style_label.setObjectName('font_style_label')
        self.text_layout.addWidget(self.font_style_label, text_row, 0)
        text_row += 1
        self.style_layout = QtWidgets.QHBoxLayout()
        self.style_bold_button = QtWidgets.QToolButton(self)
        self.style_bold_button.setCheckable(True)
        self.style_bold_button.setIcon(UiIcons().bold)
        self.style_bold_button.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Bold))
        self.style_bold_button.setObjectName('style_bold_button')
        self.style_layout.addWidget(self.style_bold_button)
        self.font_weight_combo = FontPreviewComboBox(self)
        self.font_weight_combo.setAccessibleName(translate('OpenLP.FontSelectWidget', 'Font weight'))
        self.style_layout.addWidget(self.font_weight_combo)
        self.font_weight_combo.currentIndexChanged.connect(self._on_font_weight_changed)
        self.style_italic_button = QtWidgets.QToolButton(self)
        self.style_italic_button.setCheckable(True)
        self.style_italic_button.setIcon(UiIcons().italic)
        self.style_italic_button.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Italic))
        self.style_italic_button.setObjectName('style_italic_button')
        self.style_layout.addWidget(self.style_italic_button)
        self.style_layout.addStretch(1)
        self.text_layout.addLayout(self.style_layout, text_row, 0, 1, 4)
        text_row += 1
        # Font size
        self.font_size_label = FormLabel(self)
        self.font_size_label.setObjectName('font_size_label')
        self.text_layout.addWidget(self.font_size_label, text_row, 0)
        text_row += 1
        self.font_size_spinbox = fluentqt.NumberBox(self)
        self.font_size_spinbox.setRange(1, 999)
        self.font_size_spinbox.setDisplayPrecision(0)
        self.font_size_spinbox.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
        self.font_size_spinbox.setValue(16)
        self.font_size_spinbox.setObjectName('font_size_spinbox')
        self.text_layout.addWidget(self.font_size_spinbox, text_row, 0)
        text_row += 1
        # Word wrap
        self.wrap_check_box = QtWidgets.QCheckBox(self)
        self.wrap_check_box.setObjectName('wrap_check_box')
        self.spacing_layout.addWidget(self.wrap_check_box, spacing_row, 0, 1, 4)
        spacing_row += 1
        # Line spacing
        self.line_spacing_label = FormLabel(self)
        self.line_spacing_label.setObjectName('line_spacing_label')
        self.spacing_layout.addWidget(self.line_spacing_label, spacing_row, 0)
        spacing_row += 1
        self.line_spacing_spinbox = QtWidgets.QSpinBox(self)
        self.line_spacing_spinbox.setMinimum(-250)
        self.line_spacing_spinbox.setMaximum(250)
        self.line_spacing_spinbox.setObjectName('line_spacing_spinbox')
        self.spacing_layout.addWidget(self.line_spacing_spinbox, spacing_row, 0)
        spacing_row += 1
        # Letter spacing
        self.letter_spacing_label = FormLabel(self)
        self.letter_spacing_label.setObjectName('letter_spacing_label')
        self.spacing_layout.addWidget(self.letter_spacing_label, spacing_row, 0)
        spacing_row += 1
        self.letter_spacing_spinbox = fluentqt.NumberBox(self)
        self.letter_spacing_spinbox.setRange(-250, 250)
        self.letter_spacing_spinbox.setDisplayPrecision(1)
        self.letter_spacing_spinbox.setSmallChange(0.1)
        self.letter_spacing_spinbox.setValue(0)
        self.letter_spacing_spinbox.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
        self.letter_spacing_spinbox.setObjectName('letter_spacing_spinbox')
        self.spacing_layout.addWidget(self.letter_spacing_spinbox, spacing_row, 0)
        spacing_row += 1
        # Outline
        self.outline_groupbox = QtWidgets.QGroupBox(self)
        self.outline_groupbox.setCheckable(True)
        self.outline_groupbox.setChecked(False)
        self.outline_groupbox.setObjectName('outline_groupbox')
        self.outline_layout = QtWidgets.QGridLayout(self.outline_groupbox)
        self.layout.addWidget(self.outline_groupbox, row, 0, 1, 4)
        row += 1
        # Outline colour
        self.outline_color_label = FormLabel(self.outline_groupbox)
        self.outline_color_label.setObjectName('outline_color_label')
        self.outline_layout.addWidget(self.outline_color_label, 0, 0)
        self.outline_color_button = ColorButton(self.outline_groupbox)
        self.outline_color_button.setObjectName('outline_color_button')
        self.outline_layout.addWidget(self.outline_color_button, 0, 1)
        # Outline size
        self.outline_size_label = FormLabel(self.outline_groupbox)
        self.outline_size_label.setObjectName('outline_size_label')
        self.outline_layout.addWidget(self.outline_size_label, 1, 0)
        self.outline_size_spinbox = fluentqt.NumberBox(self.outline_groupbox)
        self.outline_size_spinbox.setRange(0, 9999)
        self.outline_size_spinbox.setDisplayPrecision(0)
        self.outline_size_spinbox.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
        self.outline_size_spinbox.setObjectName('outline_size_spinbox')
        self.outline_layout.addWidget(self.outline_size_spinbox, 1, 1)
        # Shadow
        self.shadow_groupbox = QtWidgets.QGroupBox(self)
        self.shadow_groupbox.setCheckable(True)
        self.shadow_groupbox.setChecked(False)
        self.shadow_groupbox.setObjectName('shadow_groupbox')
        self.shadow_layout = QtWidgets.QGridLayout(self.shadow_groupbox)
        self.layout.addWidget(self.shadow_groupbox, row, 0, 1, 4)
        # Shadow color
        self.shadow_color_label = FormLabel(self.shadow_groupbox)
        self.shadow_color_label.setObjectName('shadow_color_label')
        self.shadow_layout.addWidget(self.shadow_color_label, 0, 0)
        self.shadow_color_button = ColorButton(self.shadow_groupbox)
        self.shadow_color_button.setObjectName('shadow_color_button')
        self.shadow_layout.addWidget(self.shadow_color_button, 0, 1)
        # Shadow size
        self.shadow_size_label = FormLabel(self.shadow_groupbox)
        self.shadow_size_label.setObjectName('shadow_size_label')
        self.shadow_layout.addWidget(self.shadow_size_label, 1, 0)
        self.shadow_size_spinbox = fluentqt.NumberBox(self.shadow_groupbox)
        self.shadow_size_spinbox.setRange(0, 9999)
        self.shadow_size_spinbox.setDisplayPrecision(0)
        self.shadow_size_spinbox.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
        self.shadow_size_spinbox.setObjectName('shadow_size_spinbox')
        self.shadow_layout.addWidget(self.shadow_size_spinbox, 1, 1)
        # Shadow blur
        self.shadow_blur_label = FormLabel(self.shadow_groupbox)
        self.shadow_blur_label.setObjectName('shadow_blur_label')
        self.shadow_layout.addWidget(self.shadow_blur_label, 2, 0)
        self.shadow_blur_spinbox = fluentqt.NumberBox(self.shadow_groupbox)
        self.shadow_blur_spinbox.setRange(0, 9999)
        self.shadow_blur_spinbox.setDisplayPrecision(0)
        self.shadow_blur_spinbox.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
        self.shadow_blur_spinbox.setObjectName('shadow_blur_spinbox')
        self.shadow_layout.addWidget(self.shadow_blur_spinbox, 2, 1)
        # Connect all the signals
        self.font_name_combobox.currentFontChanged.connect(self._on_font_name_changed)
        self.font_color_button.colorChanged.connect(self._on_font_color_changed)
        self.style_bold_button.toggled.connect(self._on_style_bold_toggled)
        self.style_italic_button.toggled.connect(self._on_style_italic_toggled)
        self.font_size_spinbox.valueChanged.connect(self._on_font_size_changed)
        self.wrap_check_box.stateChanged.connect(self._on_wrap_changed)
        self.line_spacing_spinbox.valueChanged.connect(self._on_line_spacing_changed)
        self.letter_spacing_spinbox.valueChanged.connect(self._on_letter_spacing_changed)
        self.outline_groupbox.toggled.connect(self._on_outline_toggled)
        self.outline_color_button.colorChanged.connect(self._on_outline_color_changed)
        self.outline_size_spinbox.valueChanged.connect(self._on_outline_size_changed)
        self.shadow_groupbox.toggled.connect(self._on_shadow_toggled)
        self.shadow_color_button.colorChanged.connect(self._on_shadow_color_changed)
        self.shadow_size_spinbox.valueChanged.connect(self._on_shadow_size_changed)
        self.shadow_blur_spinbox.valueChanged.connect(self._on_shadow_blur_changed)

    def retranslate_ui(self):
        self.text_groupbox.setTitle(translate('OpenLP.FontSelectWidget', 'Text'))
        self.spacing_groupbox.setTitle(translate('OpenLP.FontSelectWidget', 'Spacing'))
        self.font_name_label.setText(translate('OpenLP.FontSelectWidget', 'Font'))
        self.font_color_label.setText(translate('OpenLP.FontSelectWidget', 'Color'))
        self.font_style_label.setText(translate('OpenLP.FontSelectWidget', 'Style'))
        self.style_bold_button.setToolTip('{name} ({shortcut})'.format(
            name=translate('OpenLP.FontSelectWidget', 'Bold'),
            shortcut=QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Bold).toString()
        ))
        self.style_italic_button.setToolTip('{name} ({shortcut})'.format(
            name=translate('OpenLP.FontSelectWidget', 'Italic'),
            shortcut=QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Italic).toString()
        ))
        self.font_size_label.setText(translate('OpenLP.FontSelectWidget', 'Size (pt)'))
        self.font_size_spinbox.setToolTip(translate(
            'OpenLP.FontSelectWidget', 'Point sizes use a 1080-high reference canvas and scale with the output.'))
        self.wrap_check_box.setText(translate('OpenLP.FontSelectWidget', 'Word Wrap'))
        self.line_spacing_label.setText(translate('OpenLP.FontSelectWidget', 'Line Spacing'))
        self.letter_spacing_label.setText(translate('OpenLP.FontSelectWidget', 'Letter Spacing (px)'))
        self.outline_groupbox.setTitle(translate('OpenLP.FontSelectWidget', 'Outline'))
        self.outline_color_label.setText(translate('OpenLP.FontSelectWidget', 'Color'))
        self.outline_size_label.setText(translate('OpenLP.FontSelectWidget', 'Size (pt)'))
        self.shadow_groupbox.setTitle(translate('OpenLP.FontSelectWidget', 'Shadow'))
        self.shadow_color_label.setText(translate('OpenLP.FontSelectWidget', 'Color'))
        self.shadow_size_label.setText(translate('OpenLP.FontSelectWidget', 'Size (pt)'))
        self.shadow_blur_label.setText(translate('OpenLP.FontSelectWidget', 'Blur (pt)'))

    def _on_font_name_changed(self, font):
        if isinstance(font, (QtGui.QFont, str)):
            self._populate_font_weights(font.family() if isinstance(font, QtGui.QFont) else font)
        if isinstance(font, QtGui.QFont):
            self.font_name_changed.emit(font.family())
        elif isinstance(font, str):
            self.font_name_changed.emit(font)

    def _on_font_color_changed(self, color):
        self.font_color_changed.emit(color)

    def _on_style_bold_toggled(self, is_bold):
        self.font_weight = 700 if is_bold else 400
        self.is_bold_changed.emit(is_bold)

    def _on_style_italic_toggled(self, is_italic):
        self.is_italic_changed.emit(is_italic)

    def _on_font_size_changed(self, size):
        self.font_size_changed.emit(size)

    def _on_wrap_changed(self, _):
        self.wrap_changed.emit(self.wrap_check_box.isChecked())

    def _on_line_spacing_changed(self, spacing):
        self.line_spacing_changed.emit(spacing)

    def _on_letter_spacing_changed(self, spacing):
        self.letter_spacing_changed.emit(spacing)

    def _on_outline_toggled(self, is_enabled):
        self.is_outline_enabled_changed.emit(is_enabled)

    def _on_outline_color_changed(self, color):
        self.outline_color_changed.emit(color)

    def _on_outline_size_changed(self, size):
        self.outline_size_changed.emit(size)

    def _on_shadow_toggled(self, is_enabled):
        self.is_shadow_enabled_changed.emit(is_enabled)

    def _on_shadow_color_changed(self, color):
        self.shadow_color_changed.emit(color)

    def _on_shadow_size_changed(self, size):
        self.shadow_size_changed.emit(size)

    def _on_shadow_blur_changed(self, blur):
        self.shadow_blur_changed.emit(blur)

    def enable_features(self, *features):
        """
        Enable a feature
        """
        for feature_name in features:
            if feature_name not in self.feature_widgets.keys():
                raise KeyError('No such feature: {feature_name}'.format(feature_name=feature_name))
            for widget in self.feature_widgets[feature_name]:
                widget.show()

    def disable_features(self, *features):
        """
        Disable a feature
        """
        for feature_name in features:
            if feature_name not in self.feature_widgets.keys():
                raise KeyError('No such feature: {feature_name}'.format(feature_name=feature_name))
            for widget in self.feature_widgets[feature_name]:
                widget.hide()

    @property
    def font_name(self):
        return self.font_name_combobox.currentFont().family()

    @font_name.setter
    def font_name(self, font):
        self.font_name_combobox.setCurrentFont(QtGui.QFont(font))

    @property
    def font_color(self):
        return self.font_color_button.color

    @font_color.setter
    def font_color(self, color):
        self.font_color_button.color = color

    @staticmethod
    def supported_weights(family):
        """Deduplicate regular/italic faces into the family's installed weight choices."""
        return sorted({QtGui.QFontDatabase.weight(family, style)
                       for style in QtGui.QFontDatabase.styles(family)
                       if 1 <= QtGui.QFontDatabase.weight(family, style) <= 1000})

    def _populate_font_weights(self, family=None):
        family = family or self.font_name
        weights = self.supported_weights(family)
        labels = {100: 'Thin', 200: 'Extra light', 300: 'Light', 400: 'Regular', 500: 'Medium',
                  600: 'Semi bold', 700: 'Bold', 800: 'Extra bold', 900: 'Black'}
        with QtCore.QSignalBlocker(self.font_weight_combo):
            self.font_weight_combo.clear()
            for weight in weights:
                caption = translate('OpenLP.FontSelectWidget', labels.get(weight, 'Weight'))
                self.font_weight_combo.addItem(f'{caption} ({weight})', weight)
                font = QtGui.QFont(self.font_weight_combo.font())
                font.setStyleName('')
                font.setFamily(family)
                font.setWeight(QtGui.QFont.Weight(weight))
                self.font_weight_combo.setItemData(
                    self.font_weight_combo.count() - 1, font, QtCore.Qt.ItemDataRole.FontRole)
        self.font_weight_combo.setVisible(len(weights) > 1)
        self.style_bold_button.setVisible(len(weights) <= 1)
        self.font_weight = min(weights, key=lambda weight: abs(weight - self._font_weight)) if len(weights) > 1 \
            else (700 if self._font_weight >= 600 else 400)

    def _on_font_weight_changed(self, index):
        weight = self.font_weight_combo.itemData(index)
        if weight is not None:
            self.font_weight = weight
            self.font_weight_changed.emit(self.font_weight)

    @property
    def font_weight(self):
        return self._font_weight

    @font_weight.setter
    def font_weight(self, weight):
        self._font_weight = max(1, min(1000, int(weight)))
        with QtCore.QSignalBlocker(self.style_bold_button):
            self.style_bold_button.setChecked(self.is_bold)
        with QtCore.QSignalBlocker(self.font_weight_combo):
            weights = [self.font_weight_combo.itemData(i) for i in range(self.font_weight_combo.count())]
            if weights:
                closest = min(weights, key=lambda candidate: abs(candidate - self._font_weight))
                self.font_weight_combo.setCurrentIndex(weights.index(closest))

    @property
    def is_bold(self):
        return self._font_weight >= 600

    @is_bold.setter
    def is_bold(self, is_bold):
        self.font_weight = 700 if is_bold else 400

    @property
    def is_italic(self):
        return self.style_italic_button.isChecked()

    @is_italic.setter
    def is_italic(self, is_italic):
        self.style_italic_button.setChecked(is_italic)

    @property
    def font_size(self):
        return self.font_size_spinbox.value()

    @font_size.setter
    def font_size(self, size):
        self.font_size_spinbox.setValue(size)

    @property
    def wrap(self):
        return self.wrap_check_box.isChecked()

    @wrap.setter
    def wrap(self, wrap):
        self.wrap_check_box.setChecked(wrap)

    @property
    def line_spacing(self):
        return self.line_spacing_spinbox.value()

    @line_spacing.setter
    def line_spacing(self, line_spacing):
        self.line_spacing_spinbox.setValue(line_spacing)

    @property
    def letter_spacing(self):
        return self.letter_spacing_spinbox.value()

    @letter_spacing.setter
    def letter_spacing(self, letter_spacing):
        self.letter_spacing_spinbox.setValue(letter_spacing)

    @property
    def is_outline_enabled(self):
        return self.outline_groupbox.isChecked()

    @is_outline_enabled.setter
    def is_outline_enabled(self, is_enabled):
        self.outline_groupbox.setChecked(is_enabled)

    @property
    def outline_color(self):
        return self.outline_color_button.color

    @outline_color.setter
    def outline_color(self, color):
        self.outline_color_button.color = color

    @property
    def outline_size(self):
        return self.outline_size_spinbox.value()

    @outline_size.setter
    def outline_size(self, size):
        self.outline_size_spinbox.setValue(size)

    @property
    def is_shadow_enabled(self):
        return self.shadow_groupbox.isChecked()

    @is_shadow_enabled.setter
    def is_shadow_enabled(self, is_enabled):
        self.shadow_groupbox.setChecked(is_enabled)

    @property
    def shadow_color(self):
        return self.shadow_color_button.color

    @shadow_color.setter
    def shadow_color(self, color):
        self.shadow_color_button.color = color

    @property
    def shadow_size(self):
        return self.shadow_size_spinbox.value()

    @shadow_size.setter
    def shadow_size(self, size):
        self.shadow_size_spinbox.setValue(size)

    @property
    def shadow_blur(self):
        return self.shadow_blur_spinbox.value()

    @shadow_blur.setter
    def shadow_blur(self, blur):
        self.shadow_blur_spinbox.setValue(blur)
