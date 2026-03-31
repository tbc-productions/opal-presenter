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

import re

from PySide6 import QtGui


DEFAULT_SECTION_COLORS = {
    'intro': '#4ADE80',
    'verse': '#60A5FA',
    'pre_chorus': '#FBBF24',
    'chorus': '#F87171',
    'bridge': '#C084FC',
    'ending': '#94A3B8',
    'other': '#E2E8F0'
}

SECTION_KEYS_ORDERED = ['intro', 'verse', 'pre_chorus', 'chorus', 'bridge', 'ending', 'other']

VERSE_TAG_TO_SECTION_KEY = {
    'v': 'verse',
    'c': 'chorus',
    'b': 'bridge',
    'p': 'pre_chorus',
    'i': 'intro',
    'e': 'ending',
    'o': 'other'
}

RGB_HEX_REGEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
RGBA_HEX_REGEX = re.compile(r'^#[0-9A-Fa-f]{8}$')


def normalize_rgb_hex(color_text, default=''):
    """
    Normalize a color to #RRGGBB uppercase format.

    :param color_text: Candidate color text.
    :param default: Value returned when color_text is invalid.
    :return: Normalized RGBA hex color or default.
    """
    if color_text is None:
        return default
    color_text = str(color_text).strip().upper()
    if not color_text.startswith('#'):
        color_text = '#{text}'.format(text=color_text)
    if RGB_HEX_REGEX.match(color_text):
        return color_text
    if RGBA_HEX_REGEX.match(color_text):
        return color_text[:7]
    return default


def opacity_from_verse_number(verse_number, minimum=10, maximum=60):
    """
    Calculate opacity from verse number: minimum% for 1, +10% for each subsequent number, capped at maximum%.

    :param verse_number: Verse number as int or string.
    :param minimum: Minimum opacity percentage (default 10).
    :param maximum: Maximum opacity percentage (default 60).
    :return: Opacity as a float between 0 and 1.
    """
    verse_number = verse_number_from_text(verse_number)
    opacity_percent = min(maximum, minimum + ((verse_number - 1) * 10))
    return opacity_percent / 100.0


def opacity_from_verse_number_with_settings(verse_number, settings):
    """
    Calculate opacity from verse number using configured min/max from settings.

    :param verse_number: Verse number as int or string.
    :param settings: Settings object to retrieve min/max opacity values.
    :return: Opacity as a float between 0 and 1.
    """
    minimum = int(settings.value('songs/section background opacity minimum'))
    maximum = int(settings.value('songs/section background opacity maximum'))
    return opacity_from_verse_number(verse_number, minimum, maximum)


def verse_number_from_text(value, default=1):
    """
    Extract a verse number from text such as "2", "v2" or "2a".

    :param value: Text containing a verse number.
    :param default: Default value when no number can be found.
    :return: Positive integer verse number.
    """
    match = re.search(r'(\d+)', str(value))
    if not match:
        return default
    try:
        number = int(match.group(1))
    except (TypeError, ValueError):
        return default
    return max(1, number)


def section_key_from_verse_tag(verse_tag):
    """
    Resolve a song section key from a verse tag.

    :param verse_tag: Verse tag (e.g. 'v', 'C', 'verse').
    :return: Section key used in settings.
    """
    first_char = str(verse_tag).strip().lower()[:1]
    return VERSE_TAG_TO_SECTION_KEY.get(first_char, 'other')


def color_from_settings(settings, verse_tag, verse_number=1):
    """
    Resolve the configured QColor for a verse tag from settings.

    :param settings: Settings object.
    :param verse_tag: Verse tag to resolve.
    :param verse_number: Verse number used to calculate opacity.
    :return: QColor instance.
    """
    section_key = section_key_from_verse_tag(verse_tag)
    color_text = settings.value('songs/section color {key}'.format(key=section_key))
    color_text = normalize_rgb_hex(color_text, DEFAULT_SECTION_COLORS[section_key])
    if not color_text:
        return QtGui.QColor()
    color = QtGui.QColor(color_text)
    color.setAlphaF(opacity_from_verse_number_with_settings(verse_number, settings))
    return color
