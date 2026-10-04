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
Shared Fluent System Icons and explicitly retained application glyphs.
"""
import logging

import qtawesome as qta
from openlp.core.ui.fluenticons import fluent_icon
from PySide6 import QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import Singleton
from openlp.core.common.applocation import AppLocation
from openlp.core.common.registry import Registry
from openlp.core.lib import build_icon
from openlp.core.ui.style import is_ui_theme_dark


log = logging.getLogger(__name__)


class UiIcons(metaclass=Singleton):
    """
    Provide standard icons for objects to use.
    """
    def __init__(self):
        """
        These are the font icons used in the code.
        """
        # Preserve the custom logo glyph, which has no Fluent equivalent.
        font_path = AppLocation.get_directory(AppLocation.AppDir) / 'core' / 'ui' / 'fonts'
        qta.load_font('op', 'OpenLP.ttf', 'openlp-charmap.json', directory=str(font_path))
        palette = QtWidgets.QApplication.palette()
        self._default_icon_colors = {
            "color": palette.color(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.WindowText),
            "color_disabled": palette.color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText)
        }
        qta.set_defaults(**self._default_icon_colors)
        self._icon_list = {
            'redo': {'icon': 'ic_fluent_arrow_redo_24_regular'},
            'underline': {'icon': 'ic_fluent_text_underline_24_regular'},
            'uppercase': {'icon': 'ic_fluent_text_case_uppercase_24_regular'},
            'text_color': {'icon': 'ic_fluent_text_color_24_regular'},
            'palette': {'icon': 'ic_fluent_color_24_regular'},
            'clear_formatting': {'icon': 'ic_fluent_text_clear_formatting_24_regular'},
            'remove_formatting': {'icon': 'ic_fluent_text_grammar_dismiss_24_regular'},
            'code': {'icon': 'ic_fluent_code_24_regular'},
            'subscript': {'icon': 'ic_fluent_text_subscript_24_regular'},
            'superscript': {'icon': 'ic_fluent_text_superscript_24_regular'},
            'active': {'icon': 'ic_fluent_accessibility_24_regular'},
            'add': {'icon': 'ic_fluent_add_circle_24_regular'},
            'add_starburst': {'icon': 'ic_fluent_add_starburst_24_regular'},
            'alert': {'icon': 'ic_fluent_warning_24_regular'},
            'arrow_down': {'icon': 'ic_fluent_arrow_down_24_regular'},
            'arrow_collapse_vertical': {'icon': 'ic_fluent_text_collapse_24_regular'},
            'arrow_expand_vertical': {'icon': 'ic_fluent_text_expand_24_regular'},
            'arrow_left': {'icon': 'ic_fluent_arrow_left_24_regular'},
            'arrow_right': {'icon': 'ic_fluent_arrow_right_24_regular'},
            'arrow_up': {'icon': 'ic_fluent_arrow_up_24_regular'},
            'audio': {'icon': 'ic_fluent_music_note_2_24_regular'},
            'authentication': {'icon': 'ic_fluent_warning_24_regular', 'attr': 'red'},
            'address': {'icon': 'ic_fluent_book_contacts_24_regular'},
            'back': {'icon': 'ic_fluent_previous_24_regular'},
            'backspace': {'icon': 'ic_fluent_dismiss_24_regular'},
            # 'backspace': {'icon': 'ic_fluent_dismiss_24_regular'},
            'cancel': {'icon': 'ic_fluent_prohibited_24_regular'},
            'bible': {'icon': 'ic_fluent_book_open_24_regular'},
            'blank': {'icon': 'ic_fluent_dismiss_circle_24_regular'},
            'blank_theme': {'icon': 'ic_fluent_image_24_regular'},
            'bold': {'icon': 'ic_fluent_text_bold_24_regular'},
            'book': {'icon': 'ic_fluent_book_open_24_regular'},
            'border_all': {'icon': 'ic_fluent_border_all_24_regular'},
            'bottom': {'icon': 'ic_fluent_chevron_double_down_16_regular'},
            'box': {'icon': 'ic_fluent_briefcase_24_regular'},
            'clapperboard': {'icon': 'ic_fluent_movies_and_tv_24_regular'},
            'clock': {'icon': 'ic_fluent_clock_24_regular'},
            'clone': {'icon': 'ic_fluent_document_copy_24_regular'},
            'close': {'icon': 'ic_fluent_dismiss_circle_24_regular'},
            'copy': {'icon': 'ic_fluent_copy_24_regular'},
            # Retained by request: Fluent has no copyright symbol.
            'copyright': {'icon': 'mdi.copyright'},
            'custom': {'icon': 'ic_fluent_textbox_24_regular'},
            'dashboard': {'icon': 'ic_fluent_board_24_regular'},
            'database': {'icon': 'ic_fluent_database_24_regular'},
            'default': {'icon': 'ic_fluent_info_24_regular'},
            'desktop': {'icon': 'ic_fluent_desktop_24_regular'},
            'delete': {'icon': 'ic_fluent_delete_24_regular'},
            'device_stream': {'icon': 'ic_fluent_video_24_regular'},
            'donate': {'icon': 'ic_fluent_money_24_regular'},
            'download': {'icon': 'ic_fluent_arrow_download_24_regular'},
            'edit': {'icon': 'ic_fluent_document_edit_24_regular'},
            'email': {'icon': 'ic_fluent_mail_24_regular'},
            'error': {'icon': 'ic_fluent_error_circle_24_regular', 'attr': 'red'},
            'exception': {'icon': 'ic_fluent_dismiss_circle_24_regular'},
            'exit': {'icon': 'ic_fluent_sign_out_24_regular'},
            'favourite': {'icon': 'ic_fluent_star_24_regular'},
            'folder': {'icon': 'ic_fluent_folder_24_regular'},
            'folder_plus': {'icon': 'ic_fluent_folder_add_24_regular'},
            'go_to': {'icon': 'ic_fluent_arrow_hook_down_right_24_regular'},
            'group': {'icon': 'ic_fluent_group_24_regular'},
            'help': {'icon': 'ic_fluent_question_circle_24_regular'},
            'inactive': {'icon': 'ic_fluent_accessibility_24_regular', 'attr': 'lightGray'},
            'info': {'icon': 'ic_fluent_info_24_regular'},
            'italic': {'icon': 'ic_fluent_text_italic_24_regular'},
            'keyboard': {'icon': 'ic_fluent_keyboard_24_regular'},
            'library': {'icon': 'ic_fluent_library_24_regular'},
            'light_bulb': {'icon': 'ic_fluent_lightbulb_24_regular'},
            'live': {'icon': 'ic_fluent_projection_screen_24_regular'},
            'live_presentation': {'icon': 'ic_fluent_slide_text_24_regular'},
            'live_theme': {'icon': 'ic_fluent_slide_hide_24_regular'},
            # Retained by request alongside the application branding.
            'live_logo': {'icon': 'op.live-logo'},
            'live_black': {'icon': 'ic_fluent_rectangle_landscape_24_regular'},
            'live_desktop': {'icon': 'ic_fluent_desktop_24_regular'},
            'lock': {'icon': 'ic_fluent_lock_closed_24_regular'},
            'loop': {'icon': 'ic_fluent_arrow_counterclockwise_24_regular'},
            'manual': {'icon': 'ic_fluent_hat_graduation_24_regular'},
            'media': {'icon': 'ic_fluent_video_clip_24_regular'},
            'minus': {'icon': 'ic_fluent_subtract_circle_24_regular'},
            'move_start': {'icon': 'ic_fluent_arrow_upload_24_regular'},
            'move_up': {'icon': 'ic_fluent_arrow_up_24_regular'},
            'move_down': {'icon': 'ic_fluent_arrow_down_24_regular'},
            'mode_setup': {'icon': 'ic_fluent_drafts_24_regular'},
            'move_end': {'icon': 'ic_fluent_arrow_download_24_regular'},
            'music': {'icon': 'ic_fluent_music_note_2_24_regular'},
            'network_stream': {'icon': 'ic_fluent_network_check_24_regular'},
            'new': {'icon': 'ic_fluent_document_add_24_regular'},
            'new_group': {'icon': 'ic_fluent_folder_24_regular'},
            'notes': {'icon': 'ic_fluent_comment_note_24_regular'},
            'obs_studio': {'icon': 'ic_fluent_record_24_regular'},
            'open': {'icon': 'ic_fluent_folder_open_24_regular'},
            'pause': {'icon': 'ic_fluent_pause_24_regular'},
            'planning_center': {'icon': 'ic_fluent_cloud_arrow_down_24_regular'},
            'play': {'icon': 'ic_fluent_play_24_regular'},
            'player': {'icon': 'ic_fluent_tablet_24_regular'},
            'play_slides': {'icon': 'ic_fluent_slide_play_24_regular'},
            'skip_next': {'icon': 'ic_fluent_next_24_regular'},
            'plugin_list': {'icon': 'ic_fluent_puzzle_piece_24_regular'},
            'plus': {'icon': 'ic_fluent_add_24_regular'},
            'presentation': {'icon': 'ic_fluent_slide_content_24_regular'},
            'preview': {'icon': 'ic_fluent_laptop_24_regular'},
            # Retained by request: no close Fluent projector hardware match.
            'projector': {'icon': 'mdi.projector'},
            'projector_connect': {'icon': 'ic_fluent_plug_connected_24_regular'},
            'projector_cooldown': {'icon': 'mdi.projector', 'attr': 'blue'},
            'projector_disconnect': {'icon': 'ic_fluent_plug_disconnected_24_regular', 'attr': 'lightGray'},
            'projector_error': {'icon': 'mdi.projector', 'attr': 'red'},
            'projector_hdmi': {'icon': 'ic_fluent_port_hdmi_24_regular'},
            'projector_power_off': {'icon': 'mdi.projector', 'attr': 'red'},  # Toolbar power off
            'projector_power_on': {'icon': 'mdi.projector', 'attr': 'green'},  # Toolbar power on
            'projector_off': {'icon': 'mdi.projector', 'attr': 'black'},  # Projector off
            'projector_on': {'icon': 'mdi.projector', 'attr': 'green'},  # Projector on
            'projector_select_connect': {'icon': 'ic_fluent_plug_connected_24_regular', 'attr': 'green'},
            'projector_select_disconnect': {'icon': 'ic_fluent_plug_disconnected_24_regular', 'attr': 'red'},
            'projector_warmup': {'icon': 'mdi.projector', 'attr': 'yellow'},
            'picture': {'icon': 'ic_fluent_image_24_regular'},
            'image_plus': {'icon': 'ic_fluent_image_multiple_24_regular'},
            'print': {'icon': 'ic_fluent_print_24_regular'},
            'remote': {'icon': 'ic_fluent_cast_24_regular'},
            'refresh': {'icon': 'ic_fluent_arrow_clockwise_24_regular'},
            'repeat': {'icon': 'ic_fluent_arrow_repeat_all_24_regular'},
            'save': {'icon': 'ic_fluent_save_24_regular'},
            'search': {'icon': 'ic_fluent_search_24_regular'},
            'search_ccli': {'icon': 'ic_fluent_number_symbol_24_regular'},
            'search_comb': {'icon': 'ic_fluent_text_column_two_24_regular'},
            'search_lyrics': {'icon': 'ic_fluent_document_search_24_regular'},
            'search_minus': {'icon': 'ic_fluent_zoom_out_24_regular'},
            'search_plus': {'icon': 'ic_fluent_zoom_in_24_regular'},
            'search_ref': {'icon': 'ic_fluent_book_search_24_regular'},
            'search_text': {'icon': 'ic_fluent_text_field_24_regular'},
            'select_all': {'icon': 'ic_fluent_checkbox_checked_24_regular'},
            'select_none': {'icon': 'ic_fluent_checkbox_unchecked_24_regular'},
            'settings': {'icon': 'ic_fluent_settings_24_regular'},
            'shortcuts': {'icon': 'ic_fluent_wrench_24_regular'},
            'song_usage': {'icon': 'ic_fluent_slide_record_24_regular'},
            'song_usage_active': {'icon': 'ic_fluent_slide_record_24_regular'},
            'song_usage_inactive': {'icon': 'ic_fluent_slide_record_24_regular'},
            'sort': {'icon': 'ic_fluent_arrow_sort_24_regular'},
            'sync': {'icon': 'ic_fluent_arrow_sync_24_regular'},
            'stop': {'icon': 'ic_fluent_record_stop_24_regular'},
            'tab': {'icon': 'ic_fluent_tab_24_regular'},
            'square': {'icon': 'ic_fluent_square_24_regular'},
            'text': {'icon': 'ic_fluent_document_text_24_regular'},
            'time': {'icon': 'ic_fluent_history_24_regular'},
            'theme': {'icon': 'ic_fluent_paint_brush_24_regular'},
            'translation': {'icon': 'ic_fluent_translate_24_regular'},
            'top': {'icon': 'ic_fluent_chevron_double_up_16_regular'},
            'transition': {'icon': 'ic_fluent_slide_transition_24_regular'},
            'undo': {'icon': 'ic_fluent_arrow_undo_24_regular'},
            'upload': {'icon': 'ic_fluent_arrow_upload_24_regular'},
            'save_plus': {'icon': 'ic_fluent_save_edit_24_regular'},
            'user': {'icon': 'ic_fluent_person_24_regular'},
            'usermo': {'icon': 'ic_fluent_person_add_24_regular'},
            'users': {'icon': 'ic_fluent_people_24_regular'},
            'video': {'icon': 'ic_fluent_video_clip_24_regular'},
            'view_list': {'icon': 'ic_fluent_apps_list_24_regular'},
            'view_grid': {'icon': 'ic_fluent_grid_24_regular'},
            'volunteer': {'icon': 'ic_fluent_people_24_regular'},
            'web': {'icon': 'ic_fluent_globe_24_regular'},
            'volume_high': {'icon': 'ic_fluent_speaker_2_24_regular'},
            'volume_off': {'icon': 'ic_fluent_speaker_off_24_regular'}
        }
        self.load_icons(self._icon_list)
        self.main_icon = build_icon(':/icon/openlp-logo.svg')

    @staticmethod
    def _build_icon(name, **colors):
        """Keep explicitly approved legacy glyphs; render all others with Fluent."""
        if name.startswith(('mdi.', 'op.')):
            return qta.icon(name, **colors)
        return fluent_icon(name, **colors)

    def load_icons(self, icon_list):
        """
        Load the list of icons to be processed
        """
        is_dark = is_ui_theme_dark()
        for key in icon_list:
            try:
                icon = icon_list[key]['icon']
                try:
                    attr = icon_list[key]['attr']
                    setattr(self, key, self._build_icon(icon, color=attr))
                except KeyError:
                    if is_dark:
                        setattr(self, key, self._build_icon(icon, color='white'))
                    else:
                        setattr(self, key, self._build_icon(icon))
                except Exception:
                    log.exception(f'Unexpected error for icon: {icon}')
                    setattr(self, key, fluent_icon('ic_fluent_error_circle_24_regular', color='red'))
            except Exception:
                log.exception(f'Unexpected error for icon with key: {key}')
                setattr(self, key, fluent_icon('ic_fluent_error_circle_24_regular', color='red'))

    def get_icon_variant(self, icon_name, **kwargs):
        """
        Return an icon with optional Qt mode and state colours.

        :param icon_name: UiIcons' icon name
        """
        if icon_name not in self._icon_list:
            raise KeyError("Icon '{icon}' is not defined.".format(icon=icon_name))
        icon = self._icon_list[icon_name]['icon']
        is_dark = is_ui_theme_dark()
        if is_dark:
            args = {"color": "white", **kwargs}
        else:
            args = kwargs
        return self._build_icon(icon, **args)

    def get_icon_variant_selected(self, icon_name):
        """
        Returns an icon that honors the Qt's Pallete HighlightText color when host button is selected.
        """
        qtApp = Registry().get('application-qt')
        color = qtApp.palette().highlightedText().color()
        icon = self.get_icon_variant(icon_name, color_on=color, color_off_active=self._default_icon_colors['color'])
        return icon
