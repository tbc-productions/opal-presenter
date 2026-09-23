"""Check Keynote app discovery across macOS packaging names."""
import plistlib
from unittest.mock import MagicMock, patch

from openlp.plugins.presentations.lib.keynotecontroller import (
    KEYNOTE_APPLESCRIPT, KeynoteDocument, _open_keynote_document, find_keynote_application)


def test_finds_renamed_keynote_application(tmp_path):
    app = tmp_path / 'Keynote Creator Studio.app'
    info = app / 'Contents' / 'Info.plist'
    info.parent.mkdir(parents=True)
    with info.open('wb') as info_file:
        plistlib.dump({'CFBundleIdentifier': 'com.apple.Keynote'}, info_file)

    assert find_keynote_application((tmp_path,)) == app


def test_keynote_opens_through_launch_services(tmp_path):
    app = tmp_path / 'Keynote Creator Studio.app'
    deck = tmp_path / 'copied-deck.pptx'
    with patch('openlp.plugins.presentations.lib.keynotecontroller.subprocess.run') as run:
        _open_keynote_document(deck, app)

    run.assert_called_once_with(
        ['/usr/bin/open', '-g', '-a', str(app), str(deck)],
        check=True, capture_output=True, text=True)
    assert 'open (POSIX file documentPath)' not in KEYNOTE_APPLESCRIPT
    assert 'open (POSIX file documentName)' not in KEYNOTE_APPLESCRIPT


def test_imported_powerpoint_is_identified_by_keynote_document_name(tmp_path, settings):
    controller = MagicMock()
    controller.applescript.call.return_value = True
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = KeynoteDocument(controller, tmp_path / 'copied-deck.pptx')
    document.file_path = tmp_path / 'copied-deck.pptx'

    assert document.is_loaded()
    controller.applescript.call.assert_called_once_with('is_loaded', 'copied-deck')


def test_keynote_starts_large_import_on_a_worker(tmp_path, settings):
    controller = MagicMock()
    controller.keynote_app = None
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = KeynoteDocument(controller, tmp_path / 'slides.pptx')
    document.file_path = tmp_path / 'slides.pptx'
    document.ui_slidenumber = 4
    with patch('openlp.plugins.presentations.lib.keynotecontroller.ScreenList') as screens, \
            patch('openlp.plugins.presentations.lib.keynotecontroller._KeynoteStartWorker') as worker_type:
        screens.return_value.current.custom_geometry = None
        document.start_presentation()

    assert document._opening
    assert worker_type.call_args.args[-1] == 4
    worker_type.return_value.start.assert_called_once_with()


def test_keynote_applies_slide_selected_during_import(tmp_path, settings):
    with patch('openlp.plugins.presentations.lib.presentationcontroller.PresentationDocument._setup'):
        document = KeynoteDocument(MagicMock(), tmp_path / 'slides.pptx')
    document._opening = True
    document._start_worker = MagicMock(error=None, start_slide=2)
    document.ui_slidenumber = 7
    document.goto_slide = MagicMock()

    document._finish_start_presentation()

    assert document._slideshow_started
    document.goto_slide.assert_called_once_with(7)
