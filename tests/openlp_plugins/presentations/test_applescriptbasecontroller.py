# -*- coding: utf-8 -*-
"""
Tests for AppleScriptBaseDocument polling robustness (macOS Keynote/PowerPoint sync).
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from openlp.core.common.registry import Registry
from openlp.plugins.presentations.lib.applescriptbasecontroller import AppleScriptBaseDocument

class DummyController:
    applescript = MagicMock()
    thumbnail_folder = 'presentations'

@pytest.fixture
def applescript_doc(settings):
    doc = AppleScriptBaseDocument(DummyController(), Path('dummy.key'))
    doc.slide_number = 1
    doc.ui_slidenumber = 1
    doc.get_slide_count = MagicMock(return_value=5)
    return doc

def test_poll_slidenumber_success_resets_error(applescript_doc):
    applescript_doc.is_active = MagicMock(return_value=True)
    applescript_doc.get_slide_number = MagicMock(return_value=2)
    with patch('openlp.core.common.registry.Registry.execute') as reg_exec:
        applescript_doc.poll_slidenumber(is_live=True, hide_mode=None)
        assert applescript_doc.slide_number == 2
        reg_exec.assert_called_once_with('slidecontroller_live_change', 1)

def test_poll_slidenumber_error_sets_out_of_sync(applescript_doc):
    applescript_doc.is_active = MagicMock(return_value=True)
    applescript_doc.get_slide_number = MagicMock(side_effect=Exception('fail'))
    with patch('openlp.core.common.registry.Registry.execute'):
        with pytest.raises(Exception, match='fail'):
            applescript_doc.poll_slidenumber(is_live=True, hide_mode=None)

def test_poll_slidenumber_recovers_from_error(applescript_doc):
    applescript_doc.is_active = MagicMock(return_value=True)
    applescript_doc.slide_number = 3
    applescript_doc.get_slide_number = MagicMock(return_value=3)
    with patch('openlp.core.common.registry.Registry.execute') as reg_exec:
        applescript_doc.poll_slidenumber(is_live=True, hide_mode=None)
        reg_exec.assert_not_called()
