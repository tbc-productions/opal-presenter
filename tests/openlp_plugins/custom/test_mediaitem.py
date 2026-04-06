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
This module contains tests for the lib submodule of the Custom plugin.
"""
import pytest
from unittest.mock import MagicMock, patch

from openlp.core.common.registry import Registry
from openlp.core.lib.plugin import PluginStatus
from openlp.core.lib.serviceitem import ServiceItem
from openlp.plugins.custom.lib.mediaitem import CustomMediaItem


FOOTER = ['Arky Arky (Unknown)', 'Public Domain', 'CCLI 123456']


@pytest.fixture()
def media_item(mock_settings):
    Registry().register('main_window', MagicMock())

    with patch('openlp.core.lib.mediamanageritem.MediaManagerItem._setup'), \
            patch('openlp.core.lib.mediamanageritem.MediaManagerItem.setup_item'), \
            patch('openlp.plugins.custom.forms.editcustomform.EditCustomForm.__init__'), \
            patch('openlp.plugins.custom.lib.mediaitem.CustomMediaItem.setup_item'):
        m_item = CustomMediaItem(None, MagicMock())
    media_item.plugin = MagicMock()
    m_item.settings_section = 'bibles'
    m_item.results_view_tab = MagicMock()
    return m_item


def test_service_load_inactive(media_item):
    """
    Test the service load in custom with a default service item
    """
    # GIVEN: An empty Service Item
    service_item = ServiceItem(None)

    # WHEN: I search for the custom in the database
    item = media_item.service_load(service_item)

    # THEN: the processing should be ignored
    assert item is None, 'The Service item is inactive so processing should be bypassed'


def test_service_load_basic_custom_false(media_item):
    """
    Test the service load in custom with a default service item and no requirement to add to the database
    """
    # GIVEN: An empty Service Item and an active plugin
    service_item = ServiceItem(None)
    service_item.raw_footer = FOOTER
    media_item.plugin = MagicMock()
    media_item.plugin.status = PluginStatus.Active
    media_item.plugin.db_manager = MagicMock()
    media_item.plugin.db_manager.get_object_filtered = MagicMock()
    media_item.plugin.db_manager.get_object_filtered.return_value = None

    with patch('openlp.plugins.custom.lib.mediaitem.CustomSlide'):
        # WHEN: I search for the custom in the database
        media_item.add_custom_from_service = False
        media_item.create_from_service_item = MagicMock()
        media_item.service_load(service_item)

        # THEN: the item should not be added to the database.
        assert media_item.create_from_service_item.call_count == 0, \
            'The item should not have been added to the database'


def test_service_load_basic_custom_true(media_item):
    """
    Test the service load in custom with a default service item and a requirement to add to the database
    """
    # GIVEN: An empty Service Item and an active plugin
    service_item = ServiceItem(None)
    service_item.raw_footer = FOOTER
    media_item.plugin = MagicMock()
    media_item.plugin.status = PluginStatus.Active
    media_item.plugin.db_manager = MagicMock()
    media_item.plugin.db_manager.get_object_filtered = MagicMock()
    media_item.plugin.db_manager.get_object_filtered.return_value = None

    with patch('openlp.plugins.custom.lib.mediaitem.CustomSlide'):
        # WHEN: I search for the custom in the database
        media_item.add_custom_from_service = True
        media_item.create_from_service_item = MagicMock()
        media_item.service_load(service_item)

        # THEN: the item should not be added to the database.
        assert media_item.create_from_service_item.call_count == 1, \
            'The item should have been added to the database'


def test_on_selection_change_toggles_edit_action(mock_settings):
    """
    Test that the Edit selected item action is disabled without selection and enabled with selection.
    """
    # GIVEN: A custom media item with a mocked list and toolbar action map
    with patch('openlp.core.lib.mediamanageritem.MediaManagerItem._setup'), \
            patch('openlp.plugins.custom.forms.editcustomform.EditCustomForm.__init__'), \
            patch('openlp.plugins.custom.lib.mediaitem.CustomMediaItem.setup_item'):
        m_item = CustomMediaItem(None, MagicMock(name='plugin'))
    m_item.plugin = MagicMock()
    m_item.plugin.name = 'custom'
    m_item.list_view = MagicMock()
    edit_action = MagicMock()
    m_item.toolbar = MagicMock(actions_map={'customEditAction': edit_action})
    m_item.preview_action = None
    m_item.live_action = None
    m_item.add_to_service_action = None
    m_item.quick_preview_allowed = False
    m_item.auto_select_id = -1

    # WHEN: no list items are selected
    m_item.list_view.selectedIndexes.return_value = []
    m_item.on_selection_change()

    # THEN: Edit action should be disabled
    edit_action.setEnabled.assert_called_with(False)

    # WHEN: a list item is selected
    m_item.list_view.selectedIndexes.return_value = [MagicMock()]
    m_item.on_selection_change()

    # THEN: Edit action should be enabled
    edit_action.setEnabled.assert_called_with(True)
