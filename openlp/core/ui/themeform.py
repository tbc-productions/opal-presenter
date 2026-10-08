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
The Theme wizard
"""
import copy
import logging
from pathlib import Path

from PySide6 import QtCore, QtGui
from fluentqt import Window as FluentWindow
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import is_not_image_file
from openlp.core.common.enum import ServiceItemType
from openlp.core.common.i18n import UiStrings, translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.common.registry import Registry
from openlp.core.display.screens import ScreenList
from openlp.core.lib.theme import BackgroundType
from openlp.core.lib.ui import critical_error_message_box
from openlp.core.ui.themewizard import Ui_ThemeWizard
from openlp.core.widgets.dialogs import FileDialog


log = logging.getLogger(__name__)


class ThemeForm(FluentWindow, Ui_ThemeWizard, RegistryProperties):
    """
    This is the Theme dialog, which allows easy creation and editing of
    OpenLP themes.
    """
    accepted = QtCore.Signal()
    rejected = QtCore.Signal()
    finished = QtCore.Signal(int)

    log.info('ThemeWizardForm loaded')

    def __init__(self, parent):
        """
        Instantiate the dialog, and run any extra setup we need to.

        :param parent: The QWidget-derived parent of the wizard.
        """
        super().__init__(parent)
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self._event_loop = None
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        self._setup()

    def _setup(self):
        """
        Set up the class. This method is mocked out by the tests.
        """
        self.setup_ui(self)
        self.setMinimumSize(1000, 640)
        self.can_update_theme = True
        self._updating_page_values = False
        self._initial_preview_refresh_pending = False
        self._applying_preview_layout_geometry = False
        self.temp_background_filename = None
        self._last_preview_scale = None
        self.layout_guides_visible = False
        if hasattr(self, 'preview_area_layout'):
            try:
                self.preview_area_layout.set_aspect_ratio(self.renderer.width() / self.renderer.height())
            except ZeroDivisionError:
                self.preview_area_layout.set_aspect_ratio(1)
            self.preview_area_layout.resize.connect(self._on_preview_area_resized)
        self.layout_guide_button.triggered.connect(self.on_toggle_layout_guide_clicked)
        self._update_layout_guide_button_tooltip(False)
        if hasattr(self, 'play_transition_button'):
            self.play_transition_button.triggered.connect(self.preview_transition)
            self._set_play_transition_button_visible(False)
        if hasattr(self, 'preview_box'):
            self.preview_box.allow_theme_transitions = False
        if hasattr(self, 'help_action'):
            self.help_action.triggered.connect(self.provide_help)
        if hasattr(self, 'export_theme_action'):
            self.export_theme_action.triggered.connect(self.on_export_theme_clicked)
            self.export_theme_action.setEnabled(False)
        if hasattr(self, 'theme_name_edit'):
            self.theme_name_edit.textChanged.connect(self.on_theme_name_changed)
        Registry().register_function('theme_line_count', self.update_lines_text)
        self.main_area_page.font_name_changed.connect(self.calculate_lines)
        self.main_area_page.font_color_changed.connect(self.calculate_lines)
        self.main_area_page.font_weight_changed.connect(self.calculate_lines)
        self.main_area_page.is_bold_changed.connect(self.calculate_lines)
        self.main_area_page.is_italic_changed.connect(self.calculate_lines)
        self.main_area_page.font_size_changed.connect(self.calculate_lines)
        self.main_area_page.line_spacing_changed.connect(self.calculate_lines)
        self.main_area_page.letter_spacing_changed.connect(self.calculate_lines)
        self.main_area_page.is_outline_enabled_changed.connect(self.on_outline_toggled)
        self.main_area_page.outline_color_changed.connect(self.calculate_lines)
        self.main_area_page.outline_size_changed.connect(self.calculate_lines)
        self.main_area_page.is_shadow_enabled_changed.connect(self.on_shadow_toggled)
        self.main_area_page.shadow_color_changed.connect(self.calculate_lines)
        self.main_area_page.shadow_size_changed.connect(self.calculate_lines)
        self.main_area_page.shadow_blur_changed.connect(self.calculate_lines)
        self.footer_area_page.font_name_changed.connect(self.calculate_lines)
        self.footer_area_page.font_color_changed.connect(self.calculate_lines)
        self.footer_area_page.font_weight_changed.connect(self.calculate_lines)
        self.footer_area_page.is_bold_changed.connect(self.calculate_lines)
        self.footer_area_page.is_italic_changed.connect(self.calculate_lines)
        self.footer_area_page.font_size_changed.connect(self.calculate_lines)
        self.footer_area_page.wrap_changed.connect(self.calculate_lines)
        self.footer_area_page.line_spacing_changed.connect(self.calculate_lines)
        self.footer_area_page.letter_spacing_changed.connect(self.calculate_lines)
        self.footer_area_page.is_outline_enabled_changed.connect(self.calculate_lines)
        self.footer_area_page.outline_color_changed.connect(self.calculate_lines)
        self.footer_area_page.outline_size_changed.connect(self.calculate_lines)
        self.footer_area_page.is_shadow_enabled_changed.connect(self.calculate_lines)
        self.footer_area_page.shadow_color_changed.connect(self.calculate_lines)
        self.footer_area_page.shadow_size_changed.connect(self.calculate_lines)
        self.footer_area_page.shadow_blur_changed.connect(self.calculate_lines)
        self._connect_live_preview_signals()
        if hasattr(self, 'area_overlay'):
            self.area_overlay.areaSelected.connect(self.on_area_selected)
            self.area_overlay.areaChanged.connect(self.on_area_geometry_changed)
            self.area_overlay.gestureFinished.connect(self.on_area_gesture_finished)
            self.area_preview_timer = QtCore.QTimer(self)
            self.area_preview_timer.setSingleShot(True)
            self.area_preview_timer.setInterval(16)
            self.area_preview_timer.timeout.connect(self.update_preview_area_geometry)
            self.canvas_combo.currentIndexChanged.connect(self.on_preview_size_changed)
            self.on_area_selected('main')

    def provide_help(self):
        """
        Provide help within the wizard by opening the appropriate page of the openlp manual in the user's browser
        """
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://manual.openlp.org/themes.html"))

    def set_defaults(self):
        """
        Set up display at start of theme edit.
        """
        self.set_background_page_values()
        self.set_main_area_page_values()
        self.set_footer_area_page_values()
        self.set_alignment_page_values()
        self.set_transition_page_values()
        self.set_position_page_values()
        self.set_preview_page_values()

    def calculate_lines(self, *args):
        """
        Calculate the number of lines on a page by rendering text
        """
        if not self.can_update_theme or getattr(self, '_updating_page_values', False):
            return
        self.update_theme()
        self.theme_manager.generate_image(self.theme, True)
        self.refresh_preview()

    def preview_transition(self, *args):
        """
        Preview the current transition settings by loading two demo slides,
        transitioning to the second, then back to the first after a short delay.
        """
        if not self.can_update_theme or getattr(self, '_updating_page_values', False):
            return
        if not hasattr(self, 'preview_box'):
            return
        self.update_theme()
        self.theme_manager.generate_image(self.theme, True)
        self.preview_box.allow_theme_transitions = True
        self.preview_box.run_in_display('setAllowThemeTransitions', True)
        self.preview_box.clear_slides()
        self.preview_box.show()
        self.preview_box.generate_preview_two_slides(self._preview_theme())
        QtCore.QTimer.singleShot(0, self._set_preview_scale)
        self.update_layout_guide_overlay()
        # Tell the JS side to handle the timed transition demo
        self.preview_box.run_in_display('previewTransition', 300, 3500)

    def _set_play_transition_button_visible(self, visible):
        """
        Show or hide the play transition toolbar button.
        """
        if hasattr(self, 'play_transition_action'):
            self.play_transition_action.setVisible(bool(visible))
        if hasattr(self, 'play_transition_button'):
            self.play_transition_button.setVisible(bool(visible))

    def update_lines_text(self, lines):
        """
        Updates the lines on a page on the wizard
        :param lines: then number of lines to be displayed
        """
        self.main_line_count_label.setText(
            translate('OpenLP.ThemeForm', '(approximately %d lines per slide)') % int(lines))

    def resizeEvent(self, event=None):
        """
        Handle resize events.
        """
        if not event:
            event = QtGui.QResizeEvent(self.size(), self.size())
        FluentWindow.resizeEvent(self, event)

    def showEvent(self, event):
        """
        Ensure preview layout and scaling are recomputed whenever the dialog is shown.
        """
        FluentWindow.showEvent(self, event)
        self._apply_preview_layout_geometry()
        if getattr(self, '_initial_preview_refresh_pending', False):
            QtCore.QTimer.singleShot(0, self._refresh_preview_when_ready)
        else:
            QtCore.QTimer.singleShot(0, self._set_preview_scale)

    def validateCurrentPage(self):
        """Validate the background before saving or exporting the theme."""
        background_image = BackgroundType.to_string(BackgroundType.Image)
        background_video = BackgroundType.to_string(BackgroundType.Video)
        background_stream = BackgroundType.to_string(BackgroundType.Stream)
        if self.background_page.background_type == background_image and \
                is_not_image_file(self.background_page.image_path):
            QtWidgets.QMessageBox.critical(self, translate('OpenLP.ThemeWizard', 'Background Image Empty'),
                                           translate('OpenLP.ThemeWizard', 'You have not selected a '
                                                     'background image. Please select one before continuing.'))
            return False
        elif self.background_page.background_type == background_video and \
                not self.background_page.video_path:
            QtWidgets.QMessageBox.critical(self, translate('OpenLP.ThemeWizard', 'Background Video Empty'),
                                           translate('OpenLP.ThemeWizard', 'You have not selected a '
                                                     'background video. Please select one before continuing.'))
            return False
        elif self.background_page.background_type == background_stream and \
                not self.background_page.stream_mrl.strip():
            QtWidgets.QMessageBox.critical(self, translate('OpenLP.ThemeWizard', 'Background Stream Empty'),
                                           translate('OpenLP.ThemeWizard', 'You have not selected a '
                                                     'background stream. Please select one before continuing.'))
            return False
        else:
            return True

    def validate_background_page(self):
        return self.validateCurrentPage()

    def on_toggle_layout_guide_clicked(self, is_checked=False):
        """
        Toggle the layout guide overlay in the preview.
        """
        self.layout_guides_visible = bool(is_checked)
        self._update_layout_guide_button_tooltip(self.layout_guides_visible)
        self.update_layout_guide_overlay()

    def on_refresh_preview_clicked(self):
        """
        Manually refresh the preview slide rendering.
        """
        self.refresh_preview()

    def _update_layout_guide_button_tooltip(self, is_enabled):
        """
        Update tooltip text for the layout guide toggle button.
        """
        tooltip = translate('OpenLP.ThemeWizard', 'Hide layout guide') if is_enabled else \
            translate('OpenLP.ThemeWizard', 'Show layout guide')
        self.layout_guide_button.setToolTip(tooltip)

    def on_export_theme_clicked(self):
        """
        Export the currently named theme using the same flow as Theme Manager export.
        """
        theme_name = self.theme_name_edit.text().strip()
        if not theme_name:
            critical_error_message_box(
                translate('OpenLP.ThemeWizard', 'Theme Name Missing'),
                translate('OpenLP.ThemeWizard', 'Please enter a name for the theme.'))
            return
        last_export_directory = self.settings.value('themes/last directory export')
        if not last_export_directory:
            default_export_path = Path('{name}.otz'.format(name=theme_name))
        else:
            last_export_directory = Path(last_export_directory)
            default_export_path = last_export_directory / '{name}.otz'.format(name=theme_name)
        export_path, filter_used = FileDialog.getSaveFileName(
            self,
            translate('OpenLP.ThemeManager', 'Save Theme - ({name})').format(name=theme_name),
            default_export_path,
            translate('OpenLP.ThemeManager', 'OpenLP+ Themes (*.otz)'),
            translate('OpenLP.ThemeManager', 'OpenLP+ Themes (*.otz)'))
        if not export_path:
            return
        self.application.set_busy_cursor()
        try:
            self.settings.setValue('themes/last directory export', export_path.parent)
            if self.theme_manager._export_theme(export_path.with_suffix('.otz'), theme_name):
                QtWidgets.QMessageBox.information(
                    self,
                    translate('OpenLP.ThemeManager', 'Theme Exported'),
                    translate('OpenLP.ThemeManager', '{name} theme has been successfully exported.')
                    .format(name=theme_name))
        finally:
            self.application.set_normal_cursor()

    def on_theme_name_changed(self, theme_name):
        """
        Enable export only when a non-empty theme name is entered.
        """
        if hasattr(self, 'export_theme_action'):
            self.export_theme_action.setEnabled(bool(str(theme_name).strip()))

    def on_outline_toggled(self, is_enabled):
        """
        Change state as Outline check box changed
        """
        if self.can_update_theme:
            self.theme.font_main_outline = is_enabled
            self.calculate_lines()

    def on_shadow_toggled(self, is_enabled):
        """
        Change state as Shadow check box changed
        """
        if self.can_update_theme:
            self.theme.font_main_shadow = is_enabled
            self.calculate_lines()

    def exec(self, edit=False):
        """
        Run the dialog.
        """
        log.debug('Editing theme {name}'.format(name=self.theme.theme_name))
        self.temp_background_filename = self.theme.background_source
        self.can_update_theme = False
        if hasattr(self, 'preview_box'):
            self.preview_box.set_scale(1)
        if hasattr(self, 'canvas_combo'):
            with QtCore.QSignalBlocker(self.canvas_combo):
                self.canvas_combo.setCurrentIndex(0)
        self.set_defaults()
        self.can_update_theme = True
        self.edit_mode = edit
        self.layout_guides_visible = False
        self._last_preview_scale = None
        self._sync_preview_to_current_screen()
        self._apply_preview_layout_geometry()
        self.layout_guide_button.setChecked(False)
        self._update_layout_guide_button_tooltip(False)
        if edit:
            self.setWindowTitle(translate('OpenLP.ThemeWizard', 'Edit Theme - {name}'
                                          ).format(name=self.theme.theme_name))
        else:
            self.setWindowTitle(UiStrings().NewTheme)
        self._initial_preview_refresh_pending = True
        QtCore.QTimer.singleShot(0, self._refresh_preview_when_ready)
        if hasattr(self, 'window_title_label'):
            self.window_title_label.setText(self.windowTitle())
        if hasattr(self, 'area_overlay'):
            self.area_overlay.select_area('main')
            self.update_area_overlay()
        return self._exec_window()

    def _exec_window(self):
        """Wait for Save/Cancel while displaying the native Fluent window."""
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        loop = QtCore.QEventLoop(self)
        self._event_loop = loop
        try:
            # ADS can disable painting on the Theme Manager during startup. Qt
            # does not restore it on this separately owned top-level window.
            self.setUpdatesEnabled(True)
            self.ensurePolished()
            self.layout().activate()
            self.show()
            self.raise_()
            self.activateWindow()
            loop.exec()
        finally:
            self._event_loop = None
            loop.deleteLater()
        return self._result

    def result(self):
        return self._result

    def done(self, result):
        self._result = result
        self._initial_preview_refresh_pending = False
        if hasattr(self, 'area_preview_timer'):
            self.area_preview_timer.stop()
        self.hide()
        if self._event_loop is not None:
            self._event_loop.quit()
        if result == QtWidgets.QDialog.DialogCode.Accepted:
            self.accepted.emit()
        else:
            self.rejected.emit()
        self.finished.emit(result)

    def reject(self):
        self.done(QtWidgets.QDialog.DialogCode.Rejected)

    def closeEvent(self, event):
        self.reject()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
            event.accept()
        else:
            super().keyPressEvent(event)

    def on_area_selected(self, area):
        """Show typography, alignment and position controls for the selected area."""
        for stack in self.area_property_stacks:
            stack.setCurrentIndex(0 if area == 'main' else 1)

    def _preview_size(self):
        dimensions = self.canvas_combo.currentData() if hasattr(self, 'canvas_combo') else None
        if dimensions:
            return QtCore.QSize(*dimensions)
        return QtCore.QSize(int(self.renderer.width()), int(self.renderer.height()))

    def _preview_theme(self):
        """Preview other aspect ratios without modifying saved output coordinates."""
        if not hasattr(self, 'canvas_combo') or not self.canvas_combo.currentData():
            return self.theme
        theme = copy.deepcopy(self.theme)
        size = self._preview_size()
        theme.display_size_width = size.width()
        theme.display_size_height = size.height()
        for area in ('main', 'footer'):
            for field in ('x', 'y', 'width', 'height'):
                scale = (size.width() / self.renderer.width() if field in ('x', 'width')
                         else size.height() / self.renderer.height())
                name = f'font_{area}_{field}'
                setattr(theme, name, getattr(theme, name) * scale)
        return theme

    def on_preview_size_changed(self, index):
        self.area_preview_timer.stop()
        self._last_preview_scale = None
        size = self._preview_size()
        self.preview_area_layout.set_aspect_ratio(size.width() / max(1, size.height()))
        self._apply_preview_layout_geometry()
        self.update_area_overlay()
        self._initial_preview_refresh_pending = True
        self._refresh_preview_when_ready()

    def on_area_geometry_changed(self, area, rect):
        """An interactive edit opts the area into custom geometry and updates its fields."""
        if not self.can_update_theme or self._updating_page_values:
            return
        size = self._preview_size()
        scale_x = self.renderer.width() / max(1, size.width())
        scale_y = self.renderer.height() / max(1, size.height())
        rect = QtCore.QRectF(rect.x() * scale_x, rect.y() * scale_y,
                             rect.width() * scale_x, rect.height() * scale_y).toRect()
        self._updating_page_values = True
        try:
            setattr(self.area_position_page, f'use_{area}_default_location', False)
            for field, value in (('x', rect.x()), ('y', rect.y()),
                                 ('width', rect.width()), ('height', rect.height())):
                setattr(self.area_position_page, f'{area}_{field}', value)
        finally:
            self._updating_page_values = False
        self.update_theme()
        # Move existing text in place; pagination rebuilds the slide only after the gesture.
        if not self.area_preview_timer.isActive():
            self.area_preview_timer.start()

    def update_preview_area_geometry(self):
        """Keep the current slide and background mounted throughout a drag or resize."""
        if not getattr(self.preview_box, 'is_initialised', True):
            return
        theme = self._preview_theme()
        self.preview_box.run_in_display('setThemePreviewAreas', {
            area: {field: getattr(theme, f'font_{area}_{field}') for field in ('x', 'y', 'width', 'height')}
            for area in ('main', 'footer')})

    def on_area_gesture_finished(self):
        self.area_preview_timer.stop()
        self.calculate_lines()

    def update_area_overlay(self):
        if not hasattr(self, 'area_overlay') or not hasattr(self, 'theme'):
            return
        size = self._preview_size()
        theme = self._preview_theme()
        self.area_overlay.set_areas(size, {
            area: QtCore.QRectF(*(float(getattr(theme, f'font_{area}_{field}'))
                                  for field in ('x', 'y', 'width', 'height')))
            for area in ('main', 'footer')})
        self.area_overlay.show_guides = self.layout_guides_visible
        self.area_overlay.raise_()

    def align_area(self, operation):
        """Align the selected area to the slide, independently of its text alignment."""
        if not self.can_update_theme or not hasattr(self, 'theme'):
            return
        self.update_area_overlay()
        area = self.area_overlay.selected
        rect = QtCore.QRectF(self.area_overlay.areas[area])
        width, height = self.area_overlay.canvas_size.width(), self.area_overlay.canvas_size.height()
        if operation in ('left', 'center', 'right'):
            rect.moveLeft({'left': 0, 'center': (width - rect.width()) / 2,
                           'right': width - rect.width()}[operation])
        elif operation in ('top', 'middle', 'bottom'):
            rect.moveTop({'top': 0, 'middle': (height - rect.height()) / 2,
                          'bottom': height - rect.height()}[operation])
        else:
            return
        self.on_area_geometry_changed(area, rect.toRect())
        self.on_area_gesture_finished()

    def _sync_preview_to_current_screen(self):
        """
        Sync output coordinates while keeping the selected preview aspect ratio.
        """
        try:
            current_screen = ScreenList().current
            screen_geometry = current_screen.display_geometry
        except (AttributeError, IndexError):
            return
        if hasattr(self, 'preview_area_layout'):
            dimensions = self.canvas_combo.currentData() if hasattr(self, 'canvas_combo') else None
            width, height = dimensions or (screen_geometry.width(), screen_geometry.height())
            try:
                self.preview_area_layout.set_aspect_ratio(width / height)
            except ZeroDivisionError:
                self.preview_area_layout.set_aspect_ratio(1)
        if hasattr(self, 'preview_box'):
            self.preview_box.update_from_screen(current_screen)

    def _transition_settings_widget(self):
        """
        Return the widget that owns slide transition settings when the UI exposes them.

        Prefer the standalone Transitions page; otherwise use a combined alignment page that
        embeds transition controls. Returns None when there are no transition controls.
        """
        page = getattr(self, 'transitions_page', None)
        if page is not None:
            return page
        alignment = getattr(self, 'alignment_page', None)
        if alignment is not None and hasattr(alignment, 'transitions_enabled_check_box'):
            return alignment
        return None

    def _connect_live_preview_signals(self):
        """
        Connect controls that do not emit the page-level signals used by font pages.
        """
        self.background_page.background_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.background_page.background_fit_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.background_page.color_button.colorChanged.connect(self.calculate_lines)
        self.background_page.gradient_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.background_page.gradient_start_button.colorChanged.connect(self.calculate_lines)
        self.background_page.gradient_end_button.colorChanged.connect(self.calculate_lines)
        self.background_page.image_path_edit.pathChanged.connect(self.calculate_lines)
        self.background_page.image_color_button.colorChanged.connect(self.calculate_lines)
        self.background_page.video_path_edit.pathChanged.connect(self.calculate_lines)
        self.background_page.video_color_button.colorChanged.connect(self.calculate_lines)
        self.background_page.stream_lineedit.textChanged.connect(self.calculate_lines)
        self.background_page.stream_color_button.colorChanged.connect(self.calculate_lines)
        self.alignment_page.horizontal_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.alignment_page.vertical_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.alignment_page.footer_horizontal_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.alignment_page.footer_vertical_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.alignment_page.transition_reverse_check_box.toggled.connect(self.calculate_lines)
        transitions = self._transition_settings_widget()
        if transitions is not None:
            transitions.transitions_enabled_check_box.toggled.connect(self._set_play_transition_button_visible)
            transitions.transitions_enabled_check_box.toggled.connect(self._sync_transition_reverse_enabled_state)
            transitions.transitions_enabled_check_box.toggled.connect(self.calculate_lines)
            transitions.transition_effect_combo_box.currentIndexChanged.connect(self.calculate_lines)
            transitions.transition_speed_combo_box.currentIndexChanged.connect(self.calculate_lines)
            transitions.transition_direction_combo_box.currentIndexChanged.connect(self.calculate_lines)
        self.area_position_page.main_position_check_box.toggled.connect(self.calculate_lines)
        self.area_position_page.main_x_spin_box.valueChanged.connect(self.calculate_lines)
        self.area_position_page.main_y_spin_box.valueChanged.connect(self.calculate_lines)
        self.area_position_page.main_width_spin_box.valueChanged.connect(self.calculate_lines)
        self.area_position_page.main_height_spin_box.valueChanged.connect(self.calculate_lines)
        self.area_position_page.footer_position_check_box.toggled.connect(self.calculate_lines)
        self.area_position_page.footer_x_spin_box.valueChanged.connect(self.calculate_lines)
        self.area_position_page.footer_y_spin_box.valueChanged.connect(self.calculate_lines)
        self.area_position_page.footer_width_spin_box.valueChanged.connect(self.calculate_lines)
        self.area_position_page.footer_height_spin_box.valueChanged.connect(self.calculate_lines)

    def refresh_preview(self, force_page=False):
        """
        Re-render the preview with the current theme values.
        """
        if not hasattr(self, 'preview_box'):
            return
        self.preview_box.allow_theme_transitions = False
        self.preview_box.run_in_display('setAllowThemeTransitions', False)
        self._initial_preview_refresh_pending = False
        self.preview_box.clear_slides()
        self.preview_box.show()
        self.preview_box.generate_preview(self._preview_theme(), bool(force_page), False)
        QtCore.QTimer.singleShot(0, self._set_preview_scale)
        self.update_layout_guide_overlay()

    def _refresh_preview_when_ready(self):
        """
        Refresh the preview once the preview widget has a usable size.
        """
        if not getattr(self, '_initial_preview_refresh_pending', False) or not hasattr(self, 'preview_box'):
            return
        if not getattr(self.preview_box, 'is_initialised', True):
            QtCore.QTimer.singleShot(25, self._refresh_preview_when_ready)
            return
        self._apply_preview_layout_geometry()
        renderer = getattr(self, 'renderer', None)
        if renderer is None:
            QtCore.QTimer.singleShot(25, self._refresh_preview_when_ready)
            return
        try:
            preview_width = self._get_preview_viewport_width()
            renderer_width = int(renderer.width())
        except (TypeError, ValueError):
            QtCore.QTimer.singleShot(25, self._refresh_preview_when_ready)
            return
        if preview_width <= 0 or renderer_width <= 0:
            QtCore.QTimer.singleShot(25, self._refresh_preview_when_ready)
            return
        self.refresh_preview(force_page=True)

    def _on_preview_area_resized(self, size):
        """
        Keep preview content scaled to the preview viewport.
        """
        if self._applying_preview_layout_geometry:
            return
        if self._initial_preview_refresh_pending:
            self._refresh_preview_when_ready()
            return
        self._set_preview_scale(size.width())
        self.update_layout_guide_overlay()

    def _apply_preview_layout_geometry(self):
        """
        Force the aspect-ratio layout to place the preview widget using the current dialog geometry.
        """
        if not hasattr(self, 'preview_area_layout') or not hasattr(self, 'preview_area'):
            return
        if self._applying_preview_layout_geometry:
            return
        self._applying_preview_layout_geometry = True
        try:
            self.preview_area_layout.setGeometry(self.preview_area.contentsRect())
        finally:
            self._applying_preview_layout_geometry = False

    def _get_preview_viewport_width(self):
        """
        Get the width allocated by the preview aspect-ratio layout.
        """
        if hasattr(self, 'preview_area_layout'):
            item = self.preview_area_layout.itemAt(0)
            if item is not None:
                width = int(item.geometry().width())
                if width > 0:
                    return width
        if hasattr(self, 'preview_box'):
            return int(self.preview_box.width())
        return 0

    def _set_preview_scale(self, preview_width=None):
        """
        Compute and apply a stable preview scale from the current preview width.
        """
        renderer_width = self._preview_size().width()
        if renderer_width <= 0:
            return
        if preview_width is None:
            self._apply_preview_layout_geometry()
            preview_width = self._get_preview_viewport_width()
        scale = float(preview_width) / float(renderer_width)
        if scale <= 0:
            return
        if self._last_preview_scale is None or abs(scale - self._last_preview_scale) > 0.01:
            self._last_preview_scale = scale
            self.preview_box.set_scale(scale)

    def update_layout_guide_overlay(self):
        """
        Update and paint layout guide rectangles over the preview.
        """
        if not hasattr(self, 'preview_box') or self.preview_box is None:
            return
        self.update_area_overlay()
        if hasattr(self, 'area_overlay'):
            self.preview_box.run_in_display('clearLayoutGuide')
            return
        if not self.layout_guides_visible:
            self.preview_box.run_in_display('clearLayoutGuide')
            return
        if not hasattr(self, 'theme'):
            return
        self.preview_box.run_in_display('setLayoutGuide', {
            'main': {
                'x': int(self.theme.font_main_x),
                'y': int(self.theme.font_main_y),
                'width': int(self.theme.font_main_width),
                'height': int(self.theme.font_main_height)
            },
            'footer': {
                'x': int(self.theme.font_footer_x),
                'y': int(self.theme.font_footer_y),
                'width': int(self.theme.font_footer_width),
                'height': int(self.theme.font_footer_height)
            }
        })

    def set_background_page_values(self):
        """
        Handle the display and state of the Background page.
        """
        self.background_page.background_fit = getattr(self.theme, 'background_fit', 'cover')
        self.background_page.background_type = self.theme.background_type
        if self.theme.background_type == BackgroundType.to_string(BackgroundType.Solid):
            self.background_page.color = self.theme.background_color
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Gradient):
            self.background_page.gradient_start = self.theme.background_start_color
            self.background_page.gradient_end = self.theme.background_end_color
            self.background_page.gradient_type = self.theme.background_direction
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Image):
            self.background_page.image_color = self.theme.background_border_color
            if self.theme.background_source and self.theme.background_source.exists():
                self.background_page.image_path = self.theme.background_source
            else:
                self.background_page.image_path = self.theme.background_filename
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Video):
            self.background_page.video_color = self.theme.background_border_color
            if self.theme.background_source and self.theme.background_source.exists():
                self.background_page.video_path = self.theme.background_source
            else:
                self.background_page.video_path = self.theme.background_filename
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Stream):
            self.background_page.stream_color = self.theme.background_border_color
            self.background_page.stream_mrl = self.theme.background_source

    def set_main_area_page_values(self):
        """
        Handle the display and state of the Main Area page.
        """
        self.main_area_page.font_name = self.theme.font_main_name
        self.main_area_page.font_color = self.theme.font_main_color
        self.main_area_page.font_size = self.theme.font_main_size
        self.main_area_page.line_spacing = self.theme.font_main_line_adjustment
        self.main_area_page.letter_spacing = self.theme.font_main_letter_adjustment
        self.main_area_page.is_outline_enabled = self.theme.font_main_outline
        self.main_area_page.outline_color = self.theme.font_main_outline_color
        self.main_area_page.outline_size = self.theme.font_main_outline_size
        self.main_area_page.is_shadow_enabled = self.theme.font_main_shadow
        self.main_area_page.shadow_color = self.theme.font_main_shadow_color
        self.main_area_page.shadow_size = self.theme.font_main_shadow_size
        self.main_area_page.shadow_blur = self.theme.font_main_shadow_blur
        self.main_area_page.is_bold = self.theme.font_main_bold
        self.main_area_page.font_weight = (
            self.theme.font_main_weight or (700 if self.theme.font_main_bold else 400))
        self.main_area_page.is_italic = self.theme.font_main_italics

    def set_footer_area_page_values(self):
        """
        Handle the display and state of the Footer Area page.
        """
        self.footer_area_page.font_name = self.theme.font_footer_name
        self.footer_area_page.font_color = self.theme.font_footer_color
        self.footer_area_page.is_bold = self.theme.font_footer_bold
        self.footer_area_page.font_weight = (
            self.theme.font_footer_weight or (700 if self.theme.font_footer_bold else 400))
        self.footer_area_page.is_italic = self.theme.font_footer_italics
        self.footer_area_page.font_size = self.theme.font_footer_size
        self.footer_area_page.wrap = self.theme.font_footer_wrap
        self.footer_area_page.line_spacing = self.theme.font_footer_line_adjustment
        self.footer_area_page.letter_spacing = self.theme.font_footer_letter_adjustment
        self.footer_area_page.is_outline_enabled = self.theme.font_footer_outline
        self.footer_area_page.outline_color = self.theme.font_footer_outline_color
        self.footer_area_page.outline_size = self.theme.font_footer_outline_size
        self.footer_area_page.is_shadow_enabled = self.theme.font_footer_shadow
        self.footer_area_page.shadow_color = self.theme.font_footer_shadow_color
        self.footer_area_page.shadow_size = self.theme.font_footer_shadow_size
        self.footer_area_page.shadow_blur = self.theme.font_footer_shadow_blur

    def set_position_page_values(self):
        """
        Handle the display and state of the _position page.
        """
        # Main Area
        self.area_position_page.use_main_default_location = not self.theme.font_main_override
        self.area_position_page.main_x = int(self.theme.font_main_x)
        self.area_position_page.main_y = int(self.theme.font_main_y)
        self.area_position_page.main_height = int(self.theme.font_main_height)
        self.area_position_page.main_width = int(self.theme.font_main_width)
        # Footer
        self.area_position_page.use_footer_default_location = not self.theme.font_footer_override
        self.area_position_page.footer_x = int(self.theme.font_footer_x)
        self.area_position_page.footer_y = int(self.theme.font_footer_y)
        self.area_position_page.footer_height = int(self.theme.font_footer_height)
        self.area_position_page.footer_width = int(self.theme.font_footer_width)

    def set_alignment_page_values(self):
        """
        Handle the display and state of the Alignments page.
        """
        self.alignment_page.horizontal_align = self.theme.display_horizontal_align
        self.alignment_page.vertical_align = self.theme.display_vertical_align
        self.alignment_page.horizontal_align_footer = self.theme.display_horizontal_align_footer
        self.alignment_page.vertical_align_footer = self.theme.display_vertical_align_footer
        self.alignment_page.is_transition_reverse_enabled = self.theme.display_slide_transition_reverse

    def set_transition_page_values(self):
        """
        Handle the display and state of the Transitions page.
        """
        transitions_page = self._transition_settings_widget()
        if transitions_page is None:
            self._sync_transition_reverse_enabled_state(self.theme.display_slide_transition)
            self._set_play_transition_button_visible(self.theme.display_slide_transition)
            return
        transitions_page.is_transition_enabled = self.theme.display_slide_transition
        transitions_page.transition_type = self.theme.display_slide_transition_type
        transitions_page.transition_speed = self.theme.display_slide_transition_speed
        transitions_page.transition_direction = self.theme.display_slide_transition_direction
        self._sync_transition_reverse_enabled_state(self.theme.display_slide_transition)
        self._set_play_transition_button_visible(self.theme.display_slide_transition)

    def _sync_transition_reverse_enabled_state(self, is_enabled):
        """
        Keep the formatting page RTL option always enabled.
        """
        if hasattr(self, 'alignment_page') and hasattr(self.alignment_page, 'transition_reverse_check_box'):
            self.alignment_page.transition_reverse_check_box.setEnabled(True)

    def set_preview_page_values(self):
        """
        Handle the display and state of the Preview page.
        """
        self.theme_name_edit.setText(self.theme.theme_name)
        self.on_theme_name_changed(self.theme.theme_name)
        self.preview_box.set_theme(self.theme, service_item_type=ServiceItemType.Text)

    def update_theme(self):
        """
        Update the theme object from the UI for fields not already updated
        when the are changed.
        """
        if not self.can_update_theme:
            return
        log.debug('update_theme')
        # background page
        self.theme.background_type = self.background_page.background_type
        self.theme.background_fit = self.background_page.background_fit
        if self.theme.background_type == BackgroundType.to_string(BackgroundType.Solid):
            self.theme.background_color = self.background_page.color
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Gradient):
            self.theme.background_direction = self.background_page.gradient_type
            self.theme.background_start_color = self.background_page.gradient_start
            self.theme.background_end_color = self.background_page.gradient_end
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Image):
            self.theme.background_border_color = self.background_page.image_color
            self.theme.background_source = self.background_page.image_path
            self.theme.background_filename = self.background_page.image_path
            self.theme.background_label = self.background_page.image_path_edit.line_edit.text()
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Video):
            self.theme.background_border_color = self.background_page.video_color
            self.theme.background_source = self.background_page.video_path
            self.theme.background_filename = self.background_page.video_path
            self.theme.background_label = self.background_page.video_path_edit.line_edit.text()
        elif self.theme.background_type == BackgroundType.to_string(BackgroundType.Stream):
            self.theme.background_border_color = self.background_page.stream_color
            self.theme.background_source = self.background_page.stream_mrl
            self.theme.background_filename = self.background_page.stream_mrl
        # main page
        self.theme.font_main_name = self.main_area_page.font_name
        self.theme.font_main_color = self.main_area_page.font_color
        self.theme.font_main_size = self.main_area_page.font_size
        self.theme.font_main_line_adjustment = self.main_area_page.line_spacing
        self.theme.font_main_letter_adjustment = self.main_area_page.letter_spacing
        self.theme.font_main_outline = self.main_area_page.is_outline_enabled
        self.theme.font_main_outline_color = self.main_area_page.outline_color
        self.theme.font_main_outline_size = self.main_area_page.outline_size
        self.theme.font_main_shadow = self.main_area_page.is_shadow_enabled
        self.theme.font_main_shadow_size = self.main_area_page.shadow_size
        self.theme.font_main_shadow_blur = self.main_area_page.shadow_blur
        self.theme.font_main_shadow_color = self.main_area_page.shadow_color
        self.theme.font_main_bold = self.main_area_page.is_bold
        self.theme.font_main_weight = self.main_area_page.font_weight
        self.theme.font_main_italics = self.main_area_page.is_italic
        # footer page
        self.theme.font_footer_name = self.footer_area_page.font_name
        self.theme.font_footer_color = self.footer_area_page.font_color
        self.theme.font_footer_bold = self.footer_area_page.is_bold
        self.theme.font_footer_weight = self.footer_area_page.font_weight
        self.theme.font_footer_italics = self.footer_area_page.is_italic
        self.theme.font_footer_size = self.footer_area_page.font_size
        self.theme.font_footer_wrap = self.footer_area_page.wrap
        self.theme.font_footer_line_adjustment = self.footer_area_page.line_spacing
        self.theme.font_footer_letter_adjustment = self.footer_area_page.letter_spacing
        self.theme.font_footer_outline = self.footer_area_page.is_outline_enabled
        self.theme.font_footer_outline_color = self.footer_area_page.outline_color
        self.theme.font_footer_outline_size = self.footer_area_page.outline_size
        self.theme.font_footer_shadow = self.footer_area_page.is_shadow_enabled
        self.theme.font_footer_shadow_size = self.footer_area_page.shadow_size
        self.theme.font_footer_shadow_blur = self.footer_area_page.shadow_blur
        self.theme.font_footer_shadow_color = self.footer_area_page.shadow_color
        # position page (main)
        self.theme.font_main_override = not self.area_position_page.use_main_default_location
        if self.theme.font_main_override:
            self.theme.font_main_x = self.area_position_page.main_x
            self.theme.font_main_y = self.area_position_page.main_y
            self.theme.font_main_height = self.area_position_page.main_height
            self.theme.font_main_width = self.area_position_page.main_width
        else:
            self.theme.set_default_header()
        # position page (footer)
        self.theme.font_footer_override = not self.area_position_page.use_footer_default_location
        if self.theme.font_footer_override:
            self.theme.font_footer_x = self.area_position_page.footer_x
            self.theme.font_footer_y = self.area_position_page.footer_y
            self.theme.font_footer_height = self.area_position_page.footer_height
            self.theme.font_footer_width = self.area_position_page.footer_width
        else:
            self.theme.set_default_footer()
        # alignment page
        self.theme.display_horizontal_align = self.alignment_page.horizontal_align
        self.theme.display_vertical_align = self.alignment_page.vertical_align
        self.theme.display_horizontal_align_footer = self.alignment_page.horizontal_align_footer
        self.theme.display_vertical_align_footer = self.alignment_page.vertical_align_footer
        transitions_page = self._transition_settings_widget()
        if transitions_page is not None:
            self.theme.display_slide_transition = transitions_page.is_transition_enabled
            self.theme.display_slide_transition_type = transitions_page.transition_type
            self.theme.display_slide_transition_speed = transitions_page.transition_speed
            self.theme.display_slide_transition_direction = transitions_page.transition_direction
        self.theme.display_slide_transition_reverse = self.alignment_page.is_transition_reverse_enabled

    def accept(self):
        """
        Lets save the theme as Finish has been triggered
        """
        if not self.validate_background_page():
            return
        self.update_theme()
        # Save the theme name
        self.theme.theme_name = self.theme_name_edit.text()
        if not self.theme.theme_name:
            critical_error_message_box(
                translate('OpenLP.ThemeWizard', 'Theme Name Missing'),
                translate('OpenLP.ThemeWizard', 'Please enter a name for the theme.'))
            return
        if self.theme.theme_name == '-1' or self.theme.theme_name == 'None':
            critical_error_message_box(
                translate('OpenLP.ThemeWizard', 'Theme Name Invalid'),
                translate('OpenLP.ThemeWizard', 'Please enter a valid theme name.'))
            return
        destination_path = None
        if self.theme.background_type == BackgroundType.to_string(BackgroundType.Image) or \
                self.theme.background_type == BackgroundType.to_string(BackgroundType.Video):
            file_name = self.theme.background_filename.name
            destination_path = self.path / self.theme.theme_name / file_name
            from openlp.core.lib.designmedia import cache_media, resolve_media, MIME_TYPES
            source = self.theme.background_filename
            if (isinstance(source, Path) and source.is_file()
                    and source.suffix.lower().lstrip('.') in MIME_TYPES):
                destination_path = resolve_media(cache_media(source))
        if self.theme.background_type == BackgroundType.to_string(BackgroundType.Stream):
            destination_path = self.theme.background_source
        if not self.edit_mode and not self.theme_manager.check_if_theme_exists(self.theme.theme_name):
            return
        # Set the theme background to the cache location
        self.theme.background_filename = destination_path
        self.theme_manager.save_theme(self.theme)
        preview = (self.theme_manager.generate_image(self.theme)
                   if hasattr(self, 'canvas_combo') and self.canvas_combo.currentData()
                   else self.preview_box.save_screenshot())
        self.theme_manager.save_preview(self.theme.theme_name, preview)
        self.done(QtWidgets.QDialog.DialogCode.Accepted)
