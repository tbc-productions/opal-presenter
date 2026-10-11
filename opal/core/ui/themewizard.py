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
The Create/Edit theme dialog
"""
import fluentqt
from PySide6 import QtCore, QtGui
from opal.core.widgets import fluent as QtWidgets
from opal.core.widgets.toolbar import OpenLPToolbar

from opal.core.common.i18n import translate
from opal.core.display.render import ThemePreviewRenderer
from opal.core.lib.ui import create_button_box
from opal.core.pages.alignment import AlignmentPage, TransitionsPage
from opal.core.pages.areaposition import AreaPositionPage
from opal.core.pages.background import BackgroundPage
from opal.core.pages.fontselect import FontSelectPage
from opal.core.ui.icons import UiIcons
from opal.core.ui.fluenticons import fluent_icon
from opal.core.widgets.themeeditor import ThemeAreaOverlay
from opal.core.widgets.layouts import AspectRatioLayout


class ThemeDesignerPreview(ThemePreviewRenderer):
    """Capture the embedded slide without moving it or including editor handles."""
    def save_screenshot(self, fname=None):
        pixmap = self.webview.grab()
        if fname:
            pixmap.save(str(fname))
        else:
            return pixmap


class _SelectedFontHost(QtWidgets.QWidget):
    """
    Keep the typography height tied to the selected area's font controls.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages = []
        self._current_index = -1
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def addWidget(self, widget):
        self._pages.append(widget)
        widget.setParent(self)
        widget.hide()
        if len(self._pages) == 1:
            self.setCurrentIndex(0)

    def count(self):
        return len(self._pages)

    def widget(self, index):
        if 0 <= index < len(self._pages):
            return self._pages[index]
        return None

    def currentWidget(self):
        if 0 <= self._current_index < len(self._pages):
            return self._pages[self._current_index]
        return None

    def setCurrentIndex(self, index):
        if index < 0 or index >= len(self._pages):
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.hide()
        self._current_index = index
        page = self._pages[index]
        self._layout.addWidget(page, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        page.show()

    def setCurrentWidget(self, widget):
        try:
            index = self._pages.index(widget)
        except ValueError:
            return
        self.setCurrentIndex(index)


class _ThemePropertySection(fluentqt.Expander):
    """Keep Fluent's clip and drawer height in sync with changing form contents."""
    def __init__(self, caption, widget, expanded=False):
        super().__init__(headerText=caption, expanded=expanded)
        self.setAccessibleName(caption)
        self._height_timer = QtCore.QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.timeout.connect(self._fit_content)
        QtWidgets.QWidget.layout(widget).setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetMinimumSize)
        self.setOwnedContentWidget(widget)
        widget.installEventFilter(self)
        self.expandedChanged.connect(self._queue_fit)
        self._queue_fit()

    def _queue_fit(self, *args):
        self._height_timer.start(0)

    def eventFilter(self, watched, event):
        if event.type() in (QtCore.QEvent.Type.LayoutRequest, QtCore.QEvent.Type.Resize,
                            QtCore.QEvent.Type.Show, QtCore.QEvent.Type.FontChange):
            self._queue_fit()
        return super().eventFilter(watched, event)

    def _fit_content(self):
        if not self.isExpanded():
            return
        # Let the native opening animation finish before correcting its cached target.
        if any(animation.state() == QtCore.QAbstractAnimation.State.Running
               for animation in self.findChildren(QtCore.QAbstractAnimation)):
            self._height_timer.start(16)
            return
        content = self.contentWidget()
        QtWidgets.QWidget.layout(content).activate()
        height = max(content.sizeHint().height(), content.minimumSizeHint().height())
        if content.hasHeightForWidth():
            height = max(height, content.heightForWidth(content.width()))
        clip = content.parentWidget()
        if clip.minimumHeight() != height or clip.maximumHeight() != height or content.height() != height:
            clip.setFixedHeight(height)
            self.setFixedHeight(clip.y() + height)
            content.resize(clip.width(), height)
            self.updateGeometry()
            self.layoutHeightChanged.emit(self.height())


class Ui_ThemeWizard(object):
    """
    The Create/Edit theme dialog
    """
    def setup_ui(self, theme_dialog):
        """
        Set up the UI
        """
        theme_dialog.setObjectName('OpenLP.ThemeWizard')
        theme_dialog.setWindowIcon(UiIcons().main_icon)
        theme_dialog.resize(1440, 900)
        self.window_title_label = QtWidgets.QLabel()
        self.window_title_label.setContentsMargins(12, 0, 12, 0)
        self.window_title_label.setFluentTypography(fluentqt.FontRole.BodyStrong)
        theme_dialog.titleBar().setContentWidget(self.window_title_label)
        self.content_widget = QtWidgets.QWidget()
        theme_dialog.setContentWidget(self.content_widget)
        self.dialog_main_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.dialog_main_layout.setObjectName('dialog_main_layout')
        self.dialog_main_layout.setContentsMargins(0, 0, 0, 0)
        self.dialog_main_layout.setSpacing(0)
        self.dialog_layout_widget = QtWidgets.QWidget(theme_dialog)
        self.dialog_layout_widget.setObjectName('theme_wizard_content')
        self.dialog_layout = QtWidgets.QGridLayout(self.dialog_layout_widget)
        self.dialog_layout.setObjectName('dialog_layout')
        self.dialog_layout.setContentsMargins(14, 6, 14, 12)
        self.dialog_layout.setHorizontalSpacing(12)
        self.dialog_layout.setVerticalSpacing(10)
        self.dialog_main_layout.addWidget(self.dialog_layout_widget)

        self.command_row = QtWidgets.QHBoxLayout()
        self.command_row.setSpacing(12)
        self.theme_name_label = QtWidgets.QLabel(translate('OpenLP.ThemeWizard', 'Theme name'))
        self.theme_name_edit = QtWidgets.QLineEdit()
        self.theme_name_edit.setValidator(QtGui.QRegularExpressionValidator(
            QtCore.QRegularExpression(r'[^/\\?*|<>\[\]":<>+%]+'), theme_dialog))
        self.theme_name_edit.setObjectName('ThemeNameEdit')
        self.theme_name_edit.setMaximumWidth(320)
        self.theme_name_edit.setMinimumWidth(180)
        self.theme_name_label.setBuddy(self.theme_name_edit)
        self.command_row.addWidget(self.theme_name_label)
        self.command_row.addWidget(self.theme_name_edit, 1)
        self.command_bar = OpenLPToolbar(self.content_widget)
        self.command_bar.setObjectName('theme_command_bar')
        self.command_bar.setFloatable(False)
        self.command_bar.setMovable(False)
        self.command_bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.command_bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self.command_bar.setFixedHeight(52)
        self.command_row.addWidget(self.command_bar, 1)
        self.dialog_layout.addLayout(self.command_row, 0, 0, 1, 2)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        self.dialog_layout.addWidget(self.splitter, 1, 0, 1, 2)
        self.editor_widget = QtWidgets.QWidget()
        self.editor_widget.setObjectName('theme_properties')
        self.editor_widget.setMinimumWidth(360)
        self.editor_layout = QtWidgets.QVBoxLayout(self.editor_widget)
        self.editor_layout.setContentsMargins(12, 6, 0, 0)
        self.editor_layout.setSpacing(8)
        self.properties_label = QtWidgets.QLabel(translate('OpenLP.ThemeWizard', 'Properties'))
        self.properties_label.setFluentTypography(fluentqt.FontRole.BodyStrong)
        self.properties_label.setMinimumHeight(32)
        self.editor_layout.addWidget(self.properties_label)
        self.properties_accordion = fluentqt.Accordion()
        self.properties_accordion.setExpansionMode(fluentqt.Accordion.ExpansionMode.Multiple)
        self.inspector = QtWidgets.QWidget()
        inspector_layout = QtWidgets.QVBoxLayout(self.inspector)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.addWidget(self.properties_accordion)
        inspector_layout.addStretch()
        self.sidebar_scroll = QtWidgets.QScrollArea(self.editor_widget)
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.sidebar_scroll.setWidget(self.inspector)
        self.editor_layout.addWidget(self.sidebar_scroll)

        self.preview_panel = QtWidgets.QWidget(theme_dialog)
        self.preview_panel.setObjectName('preview_panel')
        self.preview_panel.setMinimumWidth(360)
        self.preview_panel_layout = QtWidgets.QVBoxLayout(self.preview_panel)
        self.preview_panel_layout.setObjectName('preview_panel_layout')
        self.preview_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_panel_layout.setSpacing(0)
        self.preview_area = QtWidgets.QWidget(self.preview_panel)
        self.preview_area.setObjectName('PreviewArea')
        self.preview_area.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.preview_area.setMinimumHeight(290)
        self.preview_area_layout = AspectRatioLayout(self.preview_area, 0.75)  # Dummy ratio, will be updated
        self.preview_area_layout.margin = 8
        self.preview_area_layout.setSpacing(0)
        self.preview_area_layout.setObjectName('preview_web_layout')
        self.preview_box = ThemeDesignerPreview(
            theme_dialog, window_title='Theme Designer Preview', embedded=True, can_show_startup_screen=False,
            show_transparency=True)
        self.preview_box.setObjectName('preview_box')
        self.preview_box.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
        self.preview_canvas = QtWidgets.QWidget()
        canvas_layout = QtWidgets.QGridLayout(self.preview_canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(self.preview_box, 0, 0)
        self.area_overlay = ThemeAreaOverlay(self.preview_canvas)
        canvas_layout.addWidget(self.area_overlay, 0, 0)
        self.area_overlay.raise_()
        self.preview_area_layout.addWidget(self.preview_canvas)
        self.preview_panel_layout.addWidget(self.preview_area, 1)
        self.preview_footer = QtWidgets.QHBoxLayout()
        self.preview_footer.setSpacing(8)
        self.preview_footer.addStretch()
        self.preview_footer.addWidget(QtWidgets.QLabel(translate('OpenLP.ThemeWizard', 'Preview')))
        self.canvas_combo = QtWidgets.QComboBox()
        self.canvas_combo.setAccessibleName(translate('OpenLP.ThemeWizard', 'Preview aspect ratio'))
        for caption, dimensions in (
                ('16:9', (1920, 1080)), ('16:10', (1728, 1080)),
                ('64:27', (2560, 1080)), ('4:3', (1440, 1080))):
            self.canvas_combo.addItem(caption, dimensions)
        self.preview_footer.addWidget(self.canvas_combo)
        self.preview_panel_layout.addLayout(self.preview_footer)
        self.align_button = QtWidgets.QToolButton(self.command_bar)
        self.align_button.setText(translate('OpenLP.ThemeWizard', 'Align'))
        self.align_button.setIcon(fluent_icon('ic_fluent_align_left_24_regular'))
        self.align_button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.align_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        align_menu = QtWidgets.QMenu(self.align_button)
        self.alignment_actions = {}
        for caption, operation, icon in (
                ('Align left', 'left', 'align_left'),
                ('Align centre', 'center', 'align_center_horizontal'),
                ('Align right', 'right', 'align_right'),
                ('Align top', 'top', 'align_top'),
                ('Align middle', 'middle', 'align_center_vertical'),
                ('Align bottom', 'bottom', 'align_bottom')):
            if operation == 'top':
                align_menu.addSeparator()
            action = align_menu.addAction(fluent_icon(f'ic_fluent_{icon}_24_regular'),
                                          translate('OpenLP.ThemeWizard', caption))
            action.triggered.connect(lambda checked=False, op=operation: theme_dialog.align_area(op))
            self.alignment_actions[operation] = action
        self.align_button.setMenu(align_menu)
        self.command_bar.addWidget(self.align_button)
        self.command_bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.play_transition_action = QtGui.QAction(fluent_icon('ic_fluent_play_24_regular'), '', self.command_bar)
        self.play_transition_action.setVisible(False)
        self.command_bar.addAction(self.play_transition_action)
        self.play_transition_button = self.play_transition_action
        self.play_transition_button.setVisible(False)
        self.splitter.addWidget(self.preview_panel)
        self.splitter.addWidget(self.editor_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([980, 400])
        self.dialog_layout.setRowStretch(1, 1)

        self.background_page = BackgroundPage()
        background = self.background_page
        background.background_label.hide()
        background.background_combo_box.setAccessibleName(translate('OpenLP.ThemeWizard', 'Background type'))
        background.background_type_group_box.hide()
        background.layout.removeWidget(background.background_type_group_box)
        background.layout.addWidget(background.background_combo_box, 0, 0, 1, 2)
        background.layout.addWidget(background.background_fit_label, 1, 0, 1, 2)
        background.layout.addWidget(background.background_fit_combo_box, 2, 0, 1, 2)
        background.layout.addWidget(background.background_style_group_box, 3, 0, 1, 2)
        background.layout.addWidget(background.background_media_group_box, 4, 0, 1, 2)
        background.layout.removeItem(background.layout_spacer)
        background.layout.setContentsMargins(12, 12, 12, 12)
        self.background_section = self.add_property_section('Background', self.background_page)
        # Keep the page objects as the value/signal owners; present their controls
        # in compact, selection-aware drawers instead of nested page group boxes.
        self.property_sources = QtWidgets.QWidget(self.content_widget)
        self.property_sources.hide()
        self.main_area_page = FontSelectPage(self.property_sources)
        self.main_area_page.disable_features(FontSelectPage.Wrap)
        self.footer_area_page = FontSelectPage(self.property_sources)
        self.alignment_page = AlignmentPage(self.property_sources)
        self.area_position_page = AreaPositionPage(self.property_sources)
        self.area_property_stacks = []
        self.position_section, self.position_stack, position_layouts = self.add_area_section('Position')
        self.typography_section, self.typography_stack, typography_layouts = self.add_area_section(
            'Typography', expanded=True)
        self.spacing_section, self.spacing_stack, spacing_layouts = self.add_area_section('Spacing & alignment')
        self.effects_section, self.effects_stack, effects_layouts = self.add_area_section('Text effects')
        for index, area in enumerate(('main', 'footer')):
            font_page = getattr(self, f'{area}_area_page')
            typography = typography_layouts[index]
            typography.addWidget(self.labelled_field('Font', font_page.font_name_combobox), 1, 0, 1, 2)
            style = QtWidgets.QWidget()
            style_row = QtWidgets.QHBoxLayout(style)
            style_row.setContentsMargins(0, 0, 0, 0)
            style_row.setSpacing(8)
            style_row.addWidget(font_page.font_weight_combo, 1)
            style_row.addWidget(font_page.style_bold_button)
            style_row.addWidget(font_page.style_italic_button)
            typography.addWidget(self.labelled_field('Weight and style', style), 2, 0, 1, 2)
            typography.addWidget(self.labelled_field('Size (pt)', font_page.font_size_spinbox), 3, 0)
            typography.addWidget(self.labelled_field('Colour', font_page.font_color_button), 3, 1)

            spacing = spacing_layouts[index]
            spacing.addWidget(self.labelled_field('Line spacing', font_page.line_spacing_spinbox), 1, 0)
            spacing.addWidget(self.labelled_field(
                'Letter spacing (px)', font_page.letter_spacing_spinbox), 1, 1)
            prefix = '' if area == 'main' else 'footer_'
            horizontal = getattr(self.alignment_page, f'{prefix}horizontal_combo_box')
            vertical = getattr(self.alignment_page, f'{prefix}vertical_combo_box')
            spacing.addWidget(self.labelled_field('Horizontal alignment', horizontal), 2, 0)
            spacing.addWidget(self.labelled_field('Vertical alignment', vertical), 2, 1)
            if area == 'footer':
                spacing.addWidget(font_page.wrap_check_box, 3, 0, 1, 2)
            else:
                self.main_line_count_label = QtWidgets.QLabel()
                self.main_line_count_label.setWordWrap(True)
                spacing.addWidget(self.main_line_count_label, 3, 0, 1, 2)

            effects = effects_layouts[index]
            effects.addWidget(font_page.outline_groupbox, 1, 0, 1, 2)
            effects.addWidget(font_page.shadow_groupbox, 2, 0, 1, 2)
            position = position_layouts[index]
            position.addWidget(getattr(self.area_position_page, f'{area}_position_check_box'), 1, 0, 1, 2)
            for field_index, (field, caption) in enumerate((('x', 'X (%)'), ('y', 'Y (%)'),
                                                           ('width', 'Width (%)'), ('height', 'Height (%)'))):
                widget = getattr(self.area_position_page, f'{area}_{field}_spin_box')
                position.addWidget(self.labelled_field(caption, widget), 2 + field_index // 2, field_index % 2)
        self.transitions_page = TransitionsPage()
        self.transitions_section = self.add_property_section('Transitions', self.transitions_page)
        # Reverse direction is a theme-wide transition setting.
        self.transitions_page.layout.addWidget(self.alignment_page.transition_reverse_check_box, 1, 0, 1, 4)

        self.export_theme_action = QtGui.QAction(
            fluent_icon('ic_fluent_arrow_export_24_regular'),
            translate('OpenLP.ThemeWizard', 'Export Theme'), self.command_bar)
        self.command_bar.addAction(self.export_theme_action)
        self.button_box = create_button_box(theme_dialog, 'button_box', ['cancel', 'save'])
        self.footer_buttons_layout = QtWidgets.QHBoxLayout()
        self.footer_buttons_layout.setObjectName('footer_buttons_layout')
        self.footer_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_buttons_layout.setSpacing(8)
        self.footer_buttons_layout.addStretch(1)
        self.footer_buttons_layout.addWidget(self.button_box)
        self.dialog_layout.addLayout(self.footer_buttons_layout, 2, 0, 1, 2)
        self.retranslate_ui(theme_dialog)

    def retranslate_ui(self, theme_dialog):
        """
        Translate the UI on the fly
        """
        theme_dialog.setWindowTitle(translate('OpenLP.ThemeWizard', 'Theme Designer'))
        self.window_title_label.setText(theme_dialog.windowTitle())
        self.play_transition_action.setText(translate('OpenLP.ThemeWizard', 'Play'))
        self.play_transition_button.setText(translate('OpenLP.ThemeWizard', 'Play'))
        self.play_transition_button.setToolTip(translate('OpenLP.ThemeWizard', 'Preview transition'))
        self.theme_name_label.setText(translate('OpenLP.ThemeWizard', 'Theme name'))

    def add_property_section(self, caption, widget, expanded=False):
        caption = translate('OpenLP.ThemeWizard', caption)
        section = _ThemePropertySection(caption, widget, expanded)
        self.properties_accordion.addOwnedItem(section)
        return section

    @staticmethod
    def labelled_field(caption, widget):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QtWidgets.QLabel(translate('OpenLP.ThemeWizard', caption))
        label.setBuddy(widget)
        widget.setAccessibleName(label.text())
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        layout.addWidget(label)
        layout.addWidget(widget)
        return container

    def add_area_section(self, caption, expanded=False):
        stack = _SelectedFontHost()
        self.area_property_stacks.append(stack)
        layouts = []
        for name in ('Main text', 'Footer text'):
            content = QtWidgets.QWidget()
            grid = QtWidgets.QGridLayout(content)
            grid.setContentsMargins(12, 12, 12, 12)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(10)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            label = QtWidgets.QLabel(translate('OpenLP.ThemeWizard', name))
            label.setObjectName('selected_area_label')
            label.setFluentTypography(fluentqt.FontRole.BodyStrong)
            grid.addWidget(label, 0, 0, 1, 2)
            stack.addWidget(content)
            layouts.append(grid)
        return self.add_property_section(caption, stack, expanded), stack, layouts
