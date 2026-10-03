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
Package to test the openlp.core.display.webengine package.
"""
import os

from unittest.mock import MagicMock, patch

from openlp.core.display.webengine import LocalSchemeHelper, WebViewCustomScheme


def test_shared_profile_keeps_existing_scheme_handler():
    """Opening another preview must not cancel the first preview's script requests."""
    scheme = MagicMock()
    profile = MagicMock()
    existing = profile.urlSchemeHandler.return_value
    WebViewCustomScheme.init_handler(scheme, profile)
    assert scheme.handler is existing
    profile.removeUrlSchemeHandler.assert_not_called()
    profile.installUrlSchemeHandler.assert_not_called()


def test_request_path_to_file_decodes_encoded_path_segments():
	"""
	Test that encoded URL path segments are decoded before filesystem lookup.
	"""
	helper = LocalSchemeHelper()
	with patch('openlp.core.display.webengine.is_win', return_value=True), \
		 patch('openlp.core.display.webengine.os.path.realpath', side_effect=lambda path: path) as mocked_realpath:
		result = helper.request_path_to_file('', '/C:/Users/tyler/AppData/Roaming/openlp/data/themes/Geo%20Purple/geo5.jpg')

	expected_path = os.path.normpath('C:/Users/tyler/AppData/Roaming/openlp/data/themes/Geo Purple/geo5.jpg')
	assert mocked_realpath.call_args[0][0] == expected_path
	assert result == expected_path
