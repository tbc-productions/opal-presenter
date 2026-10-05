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
Test the ThemeForm class and related methods.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.registry import Registry
from openlp.core.lib.theme import BackgroundType, HorizontalType
from openlp.core.pages.alignment import AlignmentPage, AlignmentTransitionsPage
from openlp.core.ui.themeform import ThemeForm


def _make_path(s):
    return MagicMock(**{'__str__.return_value': s, 'exists.return_value': True})


THEME_BACKGROUNDS = {
    'solid': [
        ('color', 'background_color', '#ff0')
    ],
    'gradient': [
        ('gradient_type', 'background_direction', 'horizontal'),
        ('gradient_start', 'background_start_color', '#fff'),
        ('gradient_end', 'background_end_color', '#000')
    ],
    'image': [
        ('image_color', 'background_border_color', '#f0f0f0'),
        ('image_path', 'background_source', '/path/to/image.png'),
        ('image_path', 'background_filename', '/path/to/image.png')
    ],
    'video': [
        ('video_color', 'background_border_color', '#222'),
        ('video_path', 'background_source', '/path/to/video.mkv'),
        ('video_path', 'background_filename', '/path/to/video.mkv')
    ],
    'stream': [
        ('stream_color', 'background_border_color', '#222'),
        ('stream_mrl', 'background_source', 'http:/127.0.0.1/stream.mkv'),
        ('stream_mrl', 'background_filename', 'http:/127.0.0.1/stream.mkv')
    ]
}


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_create_theme_wizard(mocked_setup, settings):
    """
    Test creating a ThemeForm instance
    """
    # GIVEN: A ThemeForm class
    # WHEN: An object is created
    # THEN: There should be no problems
    ThemeForm(None)


def test_setup(settings):
    """
    Test the _setup method
    """
    # GIVEN: A ThemeForm instance
    with patch('openlp.core.ui.themeform.ThemeForm._setup'):
        theme_form = ThemeForm(None)
    theme_form.setup_ui = MagicMock()
    theme_form.layout_guide_button = MagicMock()
    theme_form.layout_guide_button.triggered = MagicMock()
    theme_form.play_transition_button = MagicMock()
    theme_form.play_transition_button.triggered = MagicMock()
    theme_form.area_position_page = MagicMock()
    theme_form.main_area_page = MagicMock()
    theme_form.footer_area_page = MagicMock()
    theme_form._connect_live_preview_signals = MagicMock()

    # WHEN: _setup() is called
    theme_form._setup()

    # THEN: The right calls should have been made
    theme_form.setup_ui.assert_called_once_with(theme_form)
    assert theme_form.can_update_theme is True
    assert theme_form.temp_background_filename is None
    theme_form.layout_guide_button.triggered.connect.assert_called_once_with(
        theme_form.on_toggle_layout_guide_clicked)
    theme_form.play_transition_button.triggered.connect.assert_called_once_with(theme_form.preview_transition)
    theme_form.main_area_page.font_name_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.main_area_page.font_size_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.main_area_page.line_spacing_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.main_area_page.letter_spacing_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.main_area_page.is_outline_enabled_changed.connect.assert_called_once_with(
        theme_form.on_outline_toggled)
    theme_form.main_area_page.outline_size_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.main_area_page.is_shadow_enabled_changed.connect.assert_called_once_with(
        theme_form.on_shadow_toggled)
    theme_form.main_area_page.shadow_size_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.main_area_page.shadow_blur_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.font_name_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.font_size_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.wrap_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.line_spacing_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.letter_spacing_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.is_outline_enabled_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.outline_color_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.outline_size_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.is_shadow_enabled_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.shadow_color_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.shadow_size_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form.footer_area_page.shadow_blur_changed.connect.assert_called_once_with(theme_form.calculate_lines)
    theme_form._connect_live_preview_signals.assert_called_once_with()


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_set_play_transition_button_visible(mocked_setup, settings):
    """
    Test the helper that shows or hides the play transition button.
    """
    # GIVEN: A ThemeForm with toolbar controls
    theme_form = ThemeForm(None)
    theme_form.play_transition_action = MagicMock()
    theme_form.play_transition_button = MagicMock()

    # WHEN: The play button is shown
    theme_form._set_play_transition_button_visible(True)

    # THEN: Both action and button should be shown
    theme_form.play_transition_action.setVisible.assert_called_once_with(True)
    theme_form.play_transition_button.setVisible.assert_called_once_with(True)


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_set_defaults(mocked_setup, settings):
    """
    Test that the right methods are called by the set_defaults() method
    """
    # GIVEN: A ThemeForm instance with mocked methods
    theme_form = ThemeForm(None)
    theme_form.set_background_page_values = MagicMock()
    theme_form.set_main_area_page_values = MagicMock()
    theme_form.set_footer_area_page_values = MagicMock()
    theme_form.set_alignment_page_values = MagicMock()
    theme_form.set_transition_page_values = MagicMock()
    theme_form.set_position_page_values = MagicMock()
    theme_form.set_preview_page_values = MagicMock()

    # WHEN: set_defaults() is called
    theme_form.set_defaults()

    # THEN: all the mocks are called
    theme_form.set_background_page_values.assert_called_once()
    theme_form.set_main_area_page_values.assert_called_once()
    theme_form.set_footer_area_page_values.assert_called_once()
    theme_form.set_alignment_page_values.assert_called_once()
    theme_form.set_transition_page_values.assert_called_once()
    theme_form.set_position_page_values.assert_called_once()
    theme_form.set_preview_page_values.assert_called_once()


@patch('openlp.core.ui.themeform.ThemeForm._exec_window')
@patch('openlp.core.ui.themeform.ScreenList')
@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_exec_syncs_preview_to_current_screen(mocked_setup, mocked_screen_list, mocked_dialog_exec, settings):
    """
    Test that opening the edit dialog syncs the preview widget to the current screen.
    """
    # GIVEN: A ThemeForm instance with the pieces needed by exec()
    theme_form = ThemeForm(None)
    theme_form.theme = MagicMock(theme_name='Theme Name')
    theme_form.set_defaults = MagicMock()
    theme_form.refresh_preview = MagicMock()
    theme_form.preview_area_layout = MagicMock()
    theme_form.preview_box = MagicMock()
    theme_form.theme_name_label = MagicMock()
    theme_form.theme_name_edit = MagicMock()
    theme_form.layout_guide_button = MagicMock()
    theme_form.setWindowTitle = MagicMock()
    current_screen = MagicMock()
    current_screen.display_geometry.width.return_value = 1920
    current_screen.display_geometry.height.return_value = 1080
    mocked_screen_list.return_value.current = current_screen
    mocked_dialog_exec.return_value = 0

    # WHEN: The dialog is opened in edit mode
    theme_form.exec(True)

    # THEN: The preview should be resized to the current screen and rendering should be deferred
    theme_form.preview_area_layout.set_aspect_ratio.assert_called_once_with(1920 / 1080)
    theme_form.preview_box.update_from_screen.assert_called_once_with(current_screen)
    theme_form.refresh_preview.assert_not_called()


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_calculate_lines(mocked_setup, settings):
    """
    Test the calculate_lines() method
    """
    # GIVEN: A ThemeForm instance with some mocked methods
    theme_form = ThemeForm(None)
    theme_form.theme = None
    theme_form.can_update_theme = True
    theme_form.update_theme = MagicMock()
    theme_form.refresh_preview = MagicMock()
    mocked_theme_manager = MagicMock()
    Registry().register('theme_manager', mocked_theme_manager)

    # WHEN: calculate_lines() is called
    theme_form.calculate_lines()

    # THEN: The mocks should have been called correctly
    theme_form.update_theme.assert_called_once()
    mocked_theme_manager.generate_image.assert_called_once_with(None, True)
    theme_form.refresh_preview.assert_called_once()


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_update_lines_text(mocked_setup, settings):
    """
    Test the update_lines_text() method
    """
    # GIVEN: A ThemeForm instance with some mocked methods
    theme_form = ThemeForm(None)
    theme_form.main_line_count_label = MagicMock()

    # WHEN: calculate_lines() is called
    theme_form.update_lines_text(10)

    # THEN: The mocks should have been called correctly
    theme_form.main_line_count_label.setText.assert_called_once_with('(approximately 10 lines per slide)')


@patch('openlp.core.ui.themeform.FluentWindow.resizeEvent')
@patch('openlp.core.ui.themeform.QtGui.QResizeEvent')
@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_resize_event(mocked_setup, MockResizeEvent, mocked_resizeEvent, settings):
    """
    Test that the resizeEvent method handles resizing correctly
    """
    # GIVEN: A ThemeForm instance with a number of mocked methods
    mocked_event = MagicMock()
    MockResizeEvent.return_value = mocked_event
    theme_form = ThemeForm(None)
    theme_form.size = MagicMock(return_value=1920)
    theme_form.preview_area_layout = MagicMock()
    theme_form.preview_box = MagicMock(**{'width.return_value': 300})

    # WHEN: resizeEvent() is called
    theme_form.resizeEvent()

    # THEN: The correct calls should have been made
    MockResizeEvent.assert_called_once_with(1920, 1920)
    mocked_resizeEvent.assert_called_once_with(theme_form, mocked_event)
    theme_form.preview_area_layout.set_aspect_ratio.assert_not_called()
    theme_form.preview_box.set_scale.assert_not_called()


@patch('openlp.core.ui.themeform.FluentWindow.resizeEvent')
@patch('openlp.core.ui.themeform.QtGui.QResizeEvent')
@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_resize_event_dbze(mocked_setup, MockResizeEvent, mocked_resizeEvent, settings):
    """
    Test that the resizeEvent method handles a divide by zero exception correctly
    """
    # GIVEN: A ThemeForm instance with a number of mocked methods
    mocked_event = MagicMock()
    MockResizeEvent.return_value = mocked_event
    theme_form = ThemeForm(None)
    theme_form.size = MagicMock(return_value=1920)
    theme_form.preview_area_layout = MagicMock()
    theme_form.preview_box = MagicMock(**{'width.return_value': 300})

    # WHEN: resizeEvent() is called
    theme_form.resizeEvent()

    # THEN: The correct calls should have been made
    MockResizeEvent.assert_called_once_with(1920, 1920)
    mocked_resizeEvent.assert_called_once_with(theme_form, mocked_event)
    theme_form.preview_area_layout.set_aspect_ratio.assert_not_called()
    theme_form.preview_box.set_scale.assert_not_called()


@patch('openlp.core.ui.themeform.ThemeForm._exec_window', return_value=0)
@patch('openlp.core.ui.themeform.QtCore.QTimer.singleShot')
@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_exec_schedules_deferred_preview_refresh(mocked_setup, mocked_single_shot, mocked_dialog_exec, settings):
    """
    Test that opening the dialog schedules a refresh after the dialog is shown.
    """
    # GIVEN: A ThemeForm instance with the minimum pieces needed for exec()
    theme_form = ThemeForm(None)
    theme_form.theme = MagicMock(theme_name='Theme Name')
    theme_form.set_defaults = MagicMock()
    theme_form.refresh_preview = MagicMock()
    theme_form.theme_name_label = MagicMock()
    theme_form.theme_name_edit = MagicMock()
    theme_form.setWindowTitle = MagicMock()
    theme_form.layout_guide_button = MagicMock()

    # WHEN: The dialog is opened
    theme_form.exec(True)

    # THEN: A deferred refresh should be scheduled after the dialog becomes visible
    mocked_single_shot.assert_called_once_with(0, theme_form._refresh_preview_when_ready)


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_calculate_lines_is_suppressed_while_populating_page(mocked_setup, settings):
    """
    Test that calculate_lines() does not refresh the preview while page values are being populated.
    """
    # GIVEN: A ThemeForm instance that is currently filling in a page
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = True
    theme_form._updating_page_values = True
    theme_form.update_theme = MagicMock()
    theme_form.refresh_preview = MagicMock()
    mocked_theme_manager = MagicMock()
    Registry().register('theme_manager', mocked_theme_manager)

    # WHEN: calculate_lines() is called
    theme_form.calculate_lines()

    # THEN: No preview work should be triggered
    theme_form.update_theme.assert_not_called()
    mocked_theme_manager.generate_image.assert_not_called()
    theme_form.refresh_preview.assert_not_called()


@patch('openlp.core.ui.themeform.ThemeForm._setup')
@patch('openlp.core.ui.themeform.QtCore.QTimer.singleShot')
def test_refresh_preview_disables_theme_transitions(mocked_single_shot, mocked_setup, settings):
    """
    Test that normal preview refresh keeps theme transitions disabled.
    """
    # GIVEN: A ThemeForm with a preview box
    theme_form = ThemeForm(None)
    theme_form.theme = MagicMock()
    theme_form.preview_box = MagicMock()
    theme_form.update_layout_guide_overlay = MagicMock()

    # WHEN: refresh_preview() is called
    theme_form.refresh_preview()

    # THEN: Theme transitions should remain disabled for normal refresh updates
    assert theme_form.preview_box.allow_theme_transitions is False


@patch('openlp.core.ui.themeform.ThemeForm._setup')
@patch('openlp.core.ui.themeform.QtCore.QTimer.singleShot')
def test_preview_transition_enables_theme_transitions(mocked_single_shot, mocked_setup, settings):
    """
    Test that the Play action enables theme transitions for the transition demo.
    """
    # GIVEN: A ThemeForm that can preview transitions
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = True
    theme_form._updating_page_values = False
    theme_form.theme = MagicMock()
    theme_form.preview_box = MagicMock()
    mocked_theme_manager = MagicMock()
    Registry().register('theme_manager', mocked_theme_manager)
    theme_form.update_theme = MagicMock()
    theme_form.update_layout_guide_overlay = MagicMock()

    # WHEN: preview_transition() is called
    theme_form.preview_transition()

    # THEN: Theme transitions should be enabled only for explicit play preview
    assert theme_form.preview_box.allow_theme_transitions is True


@patch('openlp.core.ui.themeform.QtWidgets.QMessageBox.critical')
@patch('openlp.core.ui.themeform.is_not_image_file')
@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_validate_current_page_with_image(mocked_setup, mocked_is_not_image_file, mocked_critical, settings):
    """
    Test the validateCurrentPage() method
    """
    # GIVEN: An instance of ThemeForm with some mocks
    theme_form = ThemeForm(None)
    theme_form.background_page = MagicMock(background_type=BackgroundType.to_string(BackgroundType.Image),
                                           image_path=Path('picture.jpg'))
    mocked_is_not_image_file.return_value = True

    # WHEN: validateCurrentPage() is called
    result = theme_form.validateCurrentPage()

    # THEN: The right methods were called, and the result is False
    mocked_critical.assert_called_once_with(theme_form, 'Background Image Empty',
                                            'You have not selected a background image. '
                                            'Please select one before continuing.')
    assert result is False


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_validate_current_page(mocked_setup, settings):
    """
    Test the validateCurrentPage() method
    """
    # GIVEN: An instance of ThemeForm with some mocks
    theme_form = ThemeForm(None)
    theme_form.background_page = MagicMock()

    # WHEN: validateCurrentPage() is called
    result = theme_form.validateCurrentPage()

    # THEN: The right methods were called, and the result is False
    assert result is True


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_on_outline_toggled(mocked_setup, settings):
    """
    Test the on_outline_toggled() method
    """
    # GIVEN: An instance of ThemeForm with some mocks
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = True
    theme_form.theme = MagicMock()
    theme_form.calculate_lines = MagicMock()

    # WHEN: on_outline_toggled is called
    theme_form.on_outline_toggled(True)

    # THEN: Everything is working right
    assert theme_form.theme.font_main_outline is True
    theme_form.calculate_lines.assert_called_once()


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_on_shadow_toggled(mocked_setup, settings):
    """
    Test the on_shadow_toggled() method
    """
    # GIVEN: An instance of ThemeForm with some mocks
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = True
    theme_form.theme = MagicMock()
    theme_form.calculate_lines = MagicMock()

    # WHEN: on_shadow_toggled is called
    theme_form.on_shadow_toggled(True)

    # THEN: Everything is working right
    assert theme_form.theme.font_main_shadow is True
    theme_form.calculate_lines.assert_called_once()


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_update_theme_static(mocked_setup, settings):
    """
    Test that the update_theme() method correctly sets all the "static" theme variables
    """
    # GIVEN: An instance of a ThemeForm with some mocked out pages which return certain values
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = True
    theme_form.theme = MagicMock()
    theme_form.background_page = MagicMock()
    theme_form.main_area_page = MagicMock(font_name='Montserrat', font_color='#f00', font_size=50, line_spacing=12,
                                          is_outline_enabled=True, outline_color='#00f', outline_size=3,
                                          is_shadow_enabled=True, shadow_color='#111', shadow_size=5, shadow_blur=1,
                                          is_bold=True,
                                          is_italic=False, letter_spacing=2)
    theme_form.footer_area_page = MagicMock(font_name='Oxygen', font_color='#fff', font_size=20, wrap=False,
                                            is_bold=False, is_italic=True, line_spacing=2, letter_spacing=-1,
                                            is_outline_enabled=True, outline_color='#0f0', outline_size=2,
                                            is_shadow_enabled=True, shadow_color='#222', shadow_size=4,
                                            shadow_blur=2)
    theme_form.alignment_page = MagicMock(horizontal_align='left', vertical_align='top',
                                          is_transition_enabled=True,
                                          transition_type='fade', transition_speed='normal',
                                          transition_direction='horizontal', is_transition_reverse_enabled=False)
    theme_form.area_position_page = MagicMock(use_main_default_location=True, use_footer_default_location=True)

    # WHEN: ThemeForm.update_theme() is called
    theme_form.update_theme()

    # THEN: The theme should be correct
    # Main area
    assert theme_form.theme.font_main_name == 'Montserrat'
    assert theme_form.theme.font_main_color == '#f00'
    assert theme_form.theme.font_main_size == 50
    assert theme_form.theme.font_main_line_adjustment == 12
    assert theme_form.theme.font_main_letter_adjustment == 2
    assert theme_form.theme.font_main_outline is True
    assert theme_form.theme.font_main_outline_color == '#00f'
    assert theme_form.theme.font_main_outline_size == 3
    assert theme_form.theme.font_main_shadow is True
    assert theme_form.theme.font_main_shadow_color == '#111'
    assert theme_form.theme.font_main_shadow_size == 5
    assert theme_form.theme.font_main_shadow_blur == 1
    assert theme_form.theme.font_main_bold is True
    assert theme_form.theme.font_main_italics is False
    assert theme_form.theme.font_main_override is False
    theme_form.theme.set_default_header.assert_called_once_with()
    # Footer
    assert theme_form.theme.font_footer_name == 'Oxygen'
    assert theme_form.theme.font_footer_color == '#fff'
    assert theme_form.theme.font_footer_size == 20
    assert theme_form.theme.font_footer_wrap is False
    assert theme_form.theme.font_footer_bold is False
    assert theme_form.theme.font_footer_italics is True
    assert theme_form.theme.font_footer_override is False
    assert theme_form.theme.font_footer_line_adjustment == 2
    assert theme_form.theme.font_footer_letter_adjustment == -1
    assert theme_form.theme.font_footer_outline is True
    assert theme_form.theme.font_footer_outline_color == '#0f0'
    assert theme_form.theme.font_footer_outline_size == 2
    assert theme_form.theme.font_footer_shadow is True
    assert theme_form.theme.font_footer_shadow_color == '#222'
    assert theme_form.theme.font_footer_shadow_size == 4
    assert theme_form.theme.font_footer_shadow_blur == 2
    theme_form.theme.set_default_footer.assert_called_once_with()
    # Alignment
    assert theme_form.theme.display_horizontal_align == 'left'
    assert theme_form.theme.display_vertical_align == 'top'
    # Transitions
    assert theme_form.theme.display_slide_transition is True
    assert theme_form.theme.display_slide_transition_type == 'fade'
    assert theme_form.theme.display_slide_transition_direction == 'horizontal'
    assert theme_form.theme.display_slide_transition_speed == 'normal'
    assert theme_form.theme.display_slide_transition_reverse is False


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_transition_settings_widget_prefers_standalone_transitions_page(mocked_setup, settings):
    """
    When both exist, the dedicated Transitions page owns transition settings.
    """
    theme_form = ThemeForm(None)
    theme_form.transitions_page = MagicMock()
    theme_form.alignment_page = AlignmentPage()
    assert theme_form._transition_settings_widget() is theme_form.transitions_page


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_transition_settings_widget_none_for_alignment_page_only(mocked_setup, settings):
    """
    Split wizard: AlignmentPage must not be used as the transition settings widget
    (it has no transition_type / is_transition_enabled, etc.).
    """
    theme_form = ThemeForm(None)
    theme_form.transitions_page = None
    theme_form.alignment_page = AlignmentPage()
    assert theme_form._transition_settings_widget() is None


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_transition_settings_widget_combined_alignment_transitions_page(mocked_setup, settings):
    """
    Legacy combined page embeds transition controls on the alignment widget.
    """
    theme_form = ThemeForm(None)
    theme_form.transitions_page = None
    theme_form.alignment_page = AlignmentTransitionsPage()
    assert theme_form._transition_settings_widget() is theme_form.alignment_page


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_set_transition_page_values_without_transition_widget(mocked_setup, settings):
    """
    Opening a form with only AlignmentPage (no transition UI) must not touch missing properties.
    """
    theme_form = ThemeForm(None)
    theme_form.theme = MagicMock(display_slide_transition=False)
    theme_form.transitions_page = None
    theme_form.alignment_page = AlignmentPage()
    theme_form._set_play_transition_button_visible = MagicMock()
    theme_form._sync_transition_reverse_enabled_state = MagicMock()
    theme_form.set_transition_page_values()
    theme_form._sync_transition_reverse_enabled_state.assert_called_once_with(False)
    theme_form._set_play_transition_button_visible.assert_called_once_with(False)


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_set_transition_page_values_updates_play_button_visibility(mocked_setup, settings):
    """
    Test that the play transition button visibility follows the transition enabled state.
    """
    # GIVEN: A ThemeForm with a theme that has transitions enabled
    theme_form = ThemeForm(None)
    theme_form.theme = MagicMock(display_horizontal_align='left', display_vertical_align='top',
                                 display_horizontal_align_footer='left', display_vertical_align_footer='top',
                                 display_slide_transition=True, display_slide_transition_type='slide',
                                 display_slide_transition_speed='normal',
                                 display_slide_transition_direction='horizontal',
                                 display_slide_transition_reverse=False)
    theme_form.alignment_page = MagicMock()
    theme_form.transitions_page = MagicMock()
    theme_form._set_play_transition_button_visible = MagicMock()
    theme_form._sync_transition_reverse_enabled_state = MagicMock()

    # WHEN: The transitions page values are populated
    theme_form.set_transition_page_values()

    # THEN: The toolbar play button should be shown
    theme_form._sync_transition_reverse_enabled_state.assert_called_once_with(True)
    theme_form._set_play_transition_button_visible.assert_called_once_with(True)


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_update_theme_overridden_areas(mocked_setup, settings):
    """
    Test that the update_theme() method correctly sets all the positioning information for a custom position
    """
    # GIVEN: An instance of a ThemeForm with some mocked out pages which return certain values
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = True
    theme_form.theme = MagicMock()
    theme_form.background_page = MagicMock()
    theme_form.main_area_page = MagicMock()
    theme_form.footer_area_page = MagicMock()
    theme_form.alignment_page = MagicMock()
    theme_form.area_position_page = MagicMock(use_main_default_location=False, use_footer_default_location=False,
                                              main_x=20, main_y=50, main_height=900, main_width=1880,
                                              footer_x=20, footer_y=910, footer_height=70, footer_width=1880)

    # WHEN: ThemeForm.update_theme() is called
    theme_form.update_theme()

    # THEN: The theme should be correct
    assert theme_form.theme.font_main_override is True
    assert theme_form.theme.font_main_x == 20
    assert theme_form.theme.font_main_y == 50
    assert theme_form.theme.font_main_height == 900
    assert theme_form.theme.font_main_width == 1880
    assert theme_form.theme.font_footer_override is True
    assert theme_form.theme.font_footer_x == 20
    assert theme_form.theme.font_footer_y == 910
    assert theme_form.theme.font_footer_height == 70
    assert theme_form.theme.font_footer_width == 1880


@pytest.mark.parametrize('background_type', THEME_BACKGROUNDS.keys())
@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_update_theme_background(mocked_setup, background_type, settings):
    """
    Test that the update_theme() method correctly sets all the theme background variables for each background type
    """
    # GIVEN: An instance of a ThemeForm with some mocked out pages which return certain values
    page_props = {page_prop: value for page_prop, _, value in THEME_BACKGROUNDS[background_type]}
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = True
    theme_form.theme = MagicMock()
    theme_form.background_page = MagicMock(background_type=background_type, **page_props)
    theme_form.main_area_page = MagicMock()
    theme_form.footer_area_page = MagicMock()
    theme_form.alignment_page = MagicMock()
    theme_form.area_position_page = MagicMock()

    # WHEN: ThemeForm.update_theme() is called
    theme_form.update_theme()

    # THEN: The theme should be correct
    for _, theme_prop, value in THEME_BACKGROUNDS[background_type]:
        assert getattr(theme_form.theme, theme_prop) == value, f'{theme_prop} should have been {value}'


@pytest.mark.skip('Being a bit problematic right now')
@pytest.mark.parametrize('background_type', THEME_BACKGROUNDS.keys())
@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_set_background_page_values(mocked_setup, background_type, settings):
    """
    Test that the set_background_page_values() method sets the background page values correctly
    """
    # GIVEN: An instance of a ThemeForm with some mocked out pages and a mocked theme with values
    theme_props = {theme_prop: value for _, theme_prop, value in THEME_BACKGROUNDS[background_type]}
    theme_form = ThemeForm(None)
    theme_form.theme = MagicMock(background_type=background_type, **theme_props)
    theme_form.background_page = MagicMock()
    theme_form.main_area_page = MagicMock()
    theme_form.footer_area_page = MagicMock()
    theme_form.alignment_page = MagicMock()
    theme_form.area_position_page = MagicMock()

    # WHEN: set_background_page_values() is called
    theme_form.set_background_page_values()

    # THEN: The correct values are set on the page
    for page_prop, _, value in THEME_BACKGROUNDS[background_type]:
        assert getattr(theme_form.background_page, page_prop) == value, (
            f'{page_prop} should have been {value} but was {getattr(theme_form.background_page, page_prop)}'
        )


@patch('openlp.core.ui.themeform.ThemeForm._setup')
def test_update_theme_cannot_update(mocked_setup, settings):
    """
    Test that the update_theme() method skips out early when the theme cannot be updated
    """
    # GIVEN: An instance of a ThemeForm with some mocked out pages which return certain values
    theme_form = ThemeForm(None)
    theme_form.can_update_theme = False

    # WHEN: ThemeForm.update_theme() is called
    theme_form.update_theme()

    # THEN: The theme should be correct
    # TODO: Figure out a way to check this


@pytest.fixture
def interactive_theme_form(settings):
    """Exercise real property widgets and native chrome without starting WebEngine."""
    from PySide6 import QtWidgets
    from openlp.core.lib.theme import Theme

    renderer = MagicMock()
    renderer.width.return_value = 1920
    renderer.height.return_value = 1080
    Registry().register('renderer', renderer)
    Registry().register('theme_manager', MagicMock())
    display = QtWidgets.QWidget()
    for name in ('run_in_display', 'set_theme', 'set_scale', 'generate_preview', 'clear_slides', 'save_screenshot'):
        setattr(display, name, MagicMock())
    with patch('openlp.core.ui.themewizard.ThemeDesignerPreview', return_value=display) as preview_constructor:
        form = ThemeForm(None)
    preview_constructor.assert_called_once_with(form, window_title='Theme Designer Preview',
                                                embedded=True, can_show_startup_screen=False)
    with patch('openlp.core.lib.theme.ScreenList') as screens:
        screens.return_value.current.display_geometry = QtCore.QRect(0, 0, 1920, 1080)
        form.theme = Theme()
    form.theme.theme_name = 'Sunday'
    form.theme.font_main_override = True
    form.theme.font_footer_override = True
    for area, rect in (('main', (100, 100, 600, 300)), ('footer', (100, 900, 600, 100))):
        for field, value in zip(('x', 'y', 'width', 'height'), rect):
            setattr(form.theme, f'font_{area}_{field}', value)
    form.can_update_theme = False
    form.set_defaults()
    form.can_update_theme = True
    form.edit_mode = True
    form.update_area_overlay()
    yield form
    form.reject()
    form.deleteLater()


def test_native_theme_layout_keeps_properties_on_right(interactive_theme_form):
    import fluentqt
    form = interactive_theme_form
    assert isinstance(form, fluentqt.Window)
    assert form.splitter.widget(0) is form.preview_panel
    assert form.splitter.widget(1) is form.editor_widget
    assert not form.splitter.childrenCollapsible()
    assert form.typography_section.headerText() == 'Typography'
    assert form.position_section.headerText() == 'Position'
    assert form.maximumHeight() > 900
    assert form.align_button.menu().actions()


@pytest.mark.parametrize('area', ['main', 'footer'])
@pytest.mark.parametrize('operation, expected', [
    ('left', (0, 100)), ('center', (660, 100)), ('right', (1320, 100)),
    ('top', (100, 0)), ('middle', (100, 390)), ('bottom', (100, 780))])
def test_align_area_updates_position_fields_and_saved_theme(interactive_theme_form, area, operation, expected):
    form = interactive_theme_form
    # Both areas start at the same bounds for these alignment checks.
    rect = QtCore.QRect(100, 100, 600, 300)
    form.on_area_geometry_changed(area, rect)
    form.area_overlay.select_area(area)
    form.align_area(operation)
    assert (getattr(form.theme, f'font_{area}_x'), getattr(form.theme, f'font_{area}_y')) == expected
    assert getattr(form.theme, f'font_{area}_override') is True
    assert getattr(form.area_position_page, f'{area}_width') == 600
    assert getattr(form.area_position_page, f'{area}_height') == 300
    assert getattr(form.area_position_page, f'use_{area}_default_location') is False
    assert not form.area_preview_timer.isActive()
    form.accept()
    Registry().get('theme_manager').save_theme.assert_called_once_with(form.theme)
    assert form.result() == QtWidgets.QDialog.DialogCode.Accepted


def test_canvas_gesture_turns_default_area_into_custom_geometry(interactive_theme_form):
    form = interactive_theme_form
    form.can_update_theme = False
    form.area_position_page.use_main_default_location = True
    form.can_update_theme = True
    form.on_area_geometry_changed('main', QtCore.QRect(450, 200, 800, 450))
    assert not form.area_position_page.use_main_default_location
    assert form.area_position_page.main_x == 450
    assert form.theme.font_main_override
    assert form.theme.font_main_width == 800
    assert form.area_preview_timer.isActive()
    form.on_area_gesture_finished()
    Registry().get('theme_manager').generate_image.assert_called_once_with(form.theme, True)
    assert form.area_overlay.areas['main'] == QtCore.QRectF(450, 200, 800, 450)


@pytest.mark.parametrize('area', ['main', 'footer'])
@pytest.mark.parametrize('preview_index', [0, 3])
def test_drag_updates_existing_preview_without_rebuilding_it(interactive_theme_form, qtbot, area, preview_index):
    form = interactive_theme_form
    form.canvas_combo.setCurrentIndex(preview_index)
    preview = form.preview_box
    for method in (preview.run_in_display, preview.clear_slides, preview.generate_preview):
        method.reset_mock()
    manager = Registry().get('theme_manager')
    manager.generate_image.reset_mock()

    for rect in (QtCore.QRect(150, 200, 450, 300), QtCore.QRect(225, 250, 600, 400)):
        form.on_area_geometry_changed(area, rect)
        qtbot.waitUntil(lambda: not form.area_preview_timer.isActive())
        action, bounds = preview.run_in_display.call_args.args
        assert action == 'setThemePreviewAreas'
        assert bounds[area] == {'x': rect.x(), 'y': rect.y(), 'width': rect.width(), 'height': rect.height()}
        preview.clear_slides.assert_not_called()
        preview.generate_preview.assert_not_called()
        manager.generate_image.assert_not_called()

    form.on_area_gesture_finished()
    preview.clear_slides.assert_called_once()
    preview.generate_preview.assert_called_once()
    manager.generate_image.assert_called_once_with(form.theme, True)


def test_theme_window_close_releases_modal_loop(interactive_theme_form):
    form = interactive_theme_form
    finished = []
    form.finished.connect(finished.append)
    QtCore.QTimer.singleShot(0, form.close)
    assert form._exec_window() == QtWidgets.QDialog.DialogCode.Rejected
    assert finished == [QtWidgets.QDialog.DialogCode.Rejected]
    assert form._event_loop is None
    assert not form.isVisible()


def test_embedded_theme_preview_capture_excludes_handles():
    from openlp.core.ui.themewizard import ThemeDesignerPreview
    preview = MagicMock()
    screenshot = ThemeDesignerPreview.save_screenshot(preview)
    assert screenshot is preview.webview.grab.return_value
    preview.grab.assert_not_called()
    preview.setGeometry.assert_not_called()
    preview.hide.assert_not_called()


@patch('openlp.core.ui.themeform.ThemeForm._setup')
@patch('openlp.core.ui.themeform.QtCore.QTimer.singleShot')
def test_initial_theme_refresh_waits_for_webengine(mocked_timer, mocked_setup, settings):
    form = ThemeForm(None)
    form._initial_preview_refresh_pending = True
    form.preview_box = MagicMock(is_initialised=False)
    form.refresh_preview = MagicMock()
    form._refresh_preview_when_ready()
    form.refresh_preview.assert_not_called()
    mocked_timer.assert_called_once_with(25, form._refresh_preview_when_ready)


def test_theme_window_restores_painting_on_open(interactive_theme_form):
    """A preconstructed window must recover the update state inherited from its dock."""
    form = interactive_theme_form
    form.setUpdatesEnabled(False)
    assert not form.content_widget.updatesEnabled()
    observed = []

    def dismiss():
        observed.append((form.updatesEnabled(), form.content_widget.updatesEnabled(),
                         form.theme_name_edit.updatesEnabled(), form.preview_box.updatesEnabled()))
        form.reject()

    QtCore.QTimer.singleShot(0, dismiss)
    assert form._exec_window() == QtWidgets.QDialog.DialogCode.Rejected
    assert observed == [(True, True, True, True)]


def test_theme_commands_share_top_command_bar(interactive_theme_form):
    form = interactive_theme_form
    groups = form.command_bar._command_groups
    assert len(groups) == 1
    assert groups[0].primaryActions() == [form.layout_guide_action, form.play_transition_action,
                                          form.help_action, form.export_theme_action]
    assert not form.help_action.icon().isNull()
    assert not form.export_theme_action.icon().isNull()
    assert form.area_overlay.snapping
    assert not hasattr(form, 'snap_action')
    assert not hasattr(form, 'area_selector')
    assert not hasattr(form, 'refresh_preview_action')


def test_preview_selection_controls_typography_and_position(interactive_theme_form):
    form = interactive_theme_form
    form.area_overlay.select_area('footer')
    assert form.typography_stack.currentWidget().isAncestorOf(form.footer_area_page.font_name_combobox)
    assert form.position_stack.currentWidget().isAncestorOf(form.area_position_page.footer_x_spin_box)
    assert form.spacing_stack.currentWidget().isAncestorOf(form.alignment_page.footer_horizontal_combo_box)
    form.footer_area_page.font_size = 32
    form.alignment_page.horizontal_align_footer = 'right'
    form.area_position_page.footer_x = 240
    assert form.theme.font_footer_size == 32
    assert form.theme.display_horizontal_align_footer == HorizontalType.Right
    assert form.theme.font_footer_x == 240
    assert form.theme.font_main_x == 100
    form.area_overlay.select_area('main')
    assert form.typography_stack.currentWidget().isAncestorOf(form.main_area_page.font_name_combobox)
    assert form.position_stack.currentWidget().isAncestorOf(form.area_position_page.main_x_spin_box)
    form.main_area_page.font_size = 54
    assert form.theme.font_main_size == 54
    assert form.theme.font_footer_size == 32
    form.area_overlay.select_area('footer')
    assert form.footer_area_page.font_size == 32


def test_preview_aspect_ratio_preserves_theme_and_maps_gestures(interactive_theme_form):
    form = interactive_theme_form
    form.canvas_combo.setCurrentIndex(3)  # 4:3 at 1440 x 1080
    preview = form.preview_box.generate_preview.call_args.args[0]
    assert (preview.display_size_width, preview.display_size_height) == (1440, 1080)
    assert preview.font_main_x == 75
    assert preview.font_main_width == 450
    assert form.theme.font_main_x == 100
    assert form.theme.font_main_width == 600
    assert form.area_overlay.canvas_size == QtCore.QSize(1440, 1080)
    assert form.area_overlay.areas['main'] == QtCore.QRectF(75, 100, 450, 300)
    form.on_area_geometry_changed('main', QtCore.QRect(150, 200, 600, 400))
    form.on_area_gesture_finished()
    assert form.theme.font_main_x == 200
    assert form.theme.font_main_width == 800
    form.canvas_combo.setCurrentIndex(0)
    assert form.area_overlay.areas['main'] == QtCore.QRectF(200, 200, 800, 400)


def test_saving_alternate_preview_uses_output_thumbnail(interactive_theme_form):
    form = interactive_theme_form
    form.canvas_combo.setCurrentIndex(3)
    form.accept()
    manager = Registry().get('theme_manager')
    manager.generate_image.assert_called_with(form.theme)
    manager.save_preview.assert_called_once_with('Sunday', manager.generate_image.return_value)
    assert form.theme.font_main_width == 600


def test_selected_font_weight_survives_save_and_reload(interactive_theme_form):
    from openlp.core.lib.theme import Theme
    form = interactive_theme_form
    page = form.footer_area_page
    with patch.object(page, 'supported_weights', return_value=[300, 400, 500, 600, 700]):
        page._populate_font_weights()
    form.area_overlay.select_area('footer')
    page.font_weight_combo.setCurrentIndex(3)
    assert form.theme.font_footer_weight == 600
    assert form.theme.font_main_weight == 400
    assert form.preview_box.generate_preview.call_args.args[0].font_footer_weight == 600
    form.accept()
    with patch('openlp.core.lib.theme.ScreenList') as screens:
        screens.return_value.current.display_geometry = QtCore.QRect(0, 0, 1920, 1080)
        restored = Theme()
        restored.load_theme(form.theme.export_theme())
    form.theme = restored
    form.can_update_theme = False
    form.set_defaults()
    assert page.font_weight == 600
    assert page.font_weight_combo.currentData() == 600


def test_drawers_follow_selection_with_consistent_content_insets(interactive_theme_form):
    form = interactive_theme_form
    for area in ('main', 'footer'):
        form.area_overlay.select_area(area)
        for stack in form.area_property_stacks:
            content = stack.currentWidget()
            grid = content.layout()
            assert grid.contentsMargins() == QtCore.QMargins(12, 12, 12, 12)
            assert grid.itemAtPosition(0, 0).widget().text() == ('Main text' if area == 'main' else 'Footer text')
        assert form.effects_stack.currentWidget().isAncestorOf(getattr(form, f'{area}_area_page').outline_groupbox)
    assert form.theme_name_edit.maximumWidth() == 320


def test_expanded_background_resizes_for_gradient_controls(interactive_theme_form):
    from PySide6 import QtTest
    form = interactive_theme_form
    form.show()
    form.background_section.setExpanded(True)
    QtTest.QTest.qWait(300)
    form.background_page.background_type = 'gradient'
    QtTest.QTest.qWait(300)
    page = form.background_page
    assert page.gradient_start_button.height() >= page.gradient_start_button.sizeHint().height()
    assert page.gradient_end_label.y() >= page.gradient_start_button.geometry().bottom()
    assert page.height() >= page.minimumSizeHint().height()
    assert form.background_section.height() >= page.height() + 40


def test_drawers_fit_dynamic_contents_and_scroll_when_all_expanded(interactive_theme_form):
    from PySide6 import QtTest
    form = interactive_theme_form
    form.can_update_theme = False
    form.resize(1100, 650)
    form.show()
    sections = [form.background_section, form.position_section, form.typography_section,
                form.spacing_section, form.effects_section, form.transitions_section]
    for section in sections:
        section.setExpanded(True)
    QtTest.QTest.qWait(350)
    heights = {}
    for background in ('solid', 'gradient', 'image', 'video', 'stream', 'transparent', 'gradient', 'solid'):
        form.background_page.background_type = background
        form.area_overlay.select_area('footer' if background == 'gradient' else 'main')
        form.transitions_page.is_transition_enabled = True
        form.transitions_page.transition_type = 'fade' if background == 'solid' else 'slide'
        QtTest.QTest.qWait(60)
        for section in sections:
            content = section.contentWidget()
            assert not section._height_timer.isActive(), section.headerText()
            assert content.height() >= content.minimumSizeHint().height(), section.headerText()
            assert content.parentWidget().height() >= content.height(), section.headerText()
            assert section.height() >= content.mapTo(section, QtCore.QPoint()).y() + content.height()
        for first, second in zip(sections, sections[1:]):
            assert first.geometry().bottom() < second.y()
        assert form.sidebar_scroll.verticalScrollBar().maximum() > 0
        heights[background] = form.background_section.height()
    assert heights['gradient'] > heights['solid'] > heights['transparent']
    assert form.background_page.background_label.isHidden()
    assert form.background_page.background_type_group_box.isHidden()
    form.background_section.setExpanded(False)
    QtTest.QTest.qWait(300)
    form.background_page.background_type = 'gradient'
    form.background_section.setExpanded(True)
    QtTest.QTest.qWait(300)
    assert form.background_section.height() == heights['gradient']
