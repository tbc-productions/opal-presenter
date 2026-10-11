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
Package to test the opal.core.pages.alignment package.
"""

import pytest

from opal.core.pages.areaposition import AreaPositionPage


def test_init_(settings):
    """
    Test the initialisation of AreaPositionPage
    """
    # GIVEN: The AreaPositionPage class
    # WHEN: Initialising AreaPositionPage
    # THEN: We should have an instance of the widget with no errors
    AreaPositionPage()


def test_get_use_main_default_location(settings):
    """
    Test the use_main_default_location getter
    """
    # GIVEN: A AreaPositionPage instance with the combobox set to index 1
    page = AreaPositionPage()
    page.main_position_check_box.setChecked(False)

    # WHEN: The property is accessed
    result = page.use_main_default_location

    # THEN: The result should be correct
    assert result is False


def test_set_use_main_default_location(settings):
    """
    Test the use_main_default_location setter with an int
    """
    # GIVEN: A AreaPositionPage instance
    page = AreaPositionPage()

    # WHEN: The property is set
    page.use_main_default_location = True

    # THEN: The combobox should be correct
    assert page.main_position_check_box.isChecked() is True


def test_get_use_footer_default_location(settings):
    """
    Test the use_footer_default_location getter
    """
    # GIVEN: A AreaPositionPage instance with the combobox set to index 1
    page = AreaPositionPage()
    page.footer_position_check_box.setChecked(False)

    # WHEN: The property is accessed
    result = page.use_footer_default_location

    # THEN: The result should be correct
    assert result is False


def test_set_use_footer_default_location(settings):
    """
    Test the use_footer_default_location setter with an int
    """
    # GIVEN: A AreaPositionPage instance
    page = AreaPositionPage()

    # WHEN: The property is set
    page.use_footer_default_location = True

    # THEN: The combobox should be correct
    assert page.footer_position_check_box.isChecked() is True


@pytest.mark.parametrize('width,height', [(1280, 720), (1920, 1080), (3840, 2160)])
@pytest.mark.parametrize('area', ['main', 'footer'])
@pytest.mark.parametrize('field', ['x', 'y', 'width', 'height'])
def test_percentages_preserve_canvas_coordinates(settings, width, height, area, field):
    page = AreaPositionPage()
    page.canvas_width, page.canvas_height = width, height
    dimension = width if field in ('x', 'width') else height
    name = f'{area}_{field}'
    control = getattr(page, name + '_spin_box')
    setattr(page, name, dimension * 0.123456)
    assert control.value() == pytest.approx(12.3456)
    assert getattr(page, name) == pytest.approx(dimension * 0.123456)
    control.setValue(25.25)
    assert getattr(page, name) == pytest.approx(dimension * 0.2525)
