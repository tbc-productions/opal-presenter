# -*- coding: utf-8 -*-
"""
Tests for AppleScriptBaseDocument polling robustness (macOS Keynote/PowerPoint sync).
"""
import pytest
from unittest.mock import MagicMock, patch
from openlp.plugins.presentations.lib.applescriptbasecontroller import AppleScriptBaseDocument

class DummyController:
    applescript = MagicMock()

@pytest.fixture
def applescript_doc():
    doc = AppleScriptBaseDocument(DummyController(), 'dummy.key')
    doc.slide_number = 1
    doc.ui_slidenumber = 1
    doc.get_slide_count = MagicMock(return_value=5)
    return doc

def test_poll_slidenumber_success_resets_error(applescript_doc):
    applescript_doc.is_active = MagicMock(return_value=True)
    applescript_doc.get_slide_number = MagicMock(return_value=2)
    applescript_doc.poll_error_count = 3
    applescript_doc.out_of_sync = True
    with patch('openlp.core.common.registry.Registry.execute') as reg_exec:
        applescript_doc.poll_slidenumber(is_live=True, hide_mode=None)
        assert applescript_doc.poll_error_count == 0
        assert applescript_doc.out_of_sync is False
        reg_exec.assert_called_once()

def test_poll_slidenumber_error_sets_out_of_sync(applescript_doc):
    applescript_doc.is_active = MagicMock(return_value=True)
    applescript_doc.get_slide_number = MagicMock(side_effect=Exception('fail'))
    applescript_doc.poll_error_count = 4
    applescript_doc.out_of_sync = False
    with patch('openlp.core.common.registry.Registry.execute'):
        applescript_doc.poll_slidenumber(is_live=True, hide_mode=None)
        assert applescript_doc.poll_error_count == 5
        assert applescript_doc.out_of_sync is True

def test_poll_slidenumber_recovers_from_error(applescript_doc):
    applescript_doc.is_active = MagicMock(return_value=True)
    applescript_doc.get_slide_number = MagicMock(return_value=3)
    applescript_doc.poll_error_count = 5
    applescript_doc.out_of_sync = True
    with patch('openlp.core.common.registry.Registry.execute') as reg_exec:
        applescript_doc.poll_slidenumber(is_live=True, hide_mode=None)
        assert applescript_doc.poll_error_count == 0
        assert applescript_doc.out_of_sync is False
        reg_exec.assert_called_once()
