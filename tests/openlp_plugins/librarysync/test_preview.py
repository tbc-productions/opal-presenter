"""Cloud previews render independently and never import records into Library."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6 import QtCore, QtGui

from openlp.core.widgets import fluent as QtWidgets
from openlp.plugins.librarysync.lib.preview import (
    CloudMediaPreview, CloudPresentationPreview, CloudPreviewWindow, cloud_metadata, show_preview, text_service_item)
from openlp.plugins.librarysync.lib.provider import CloudItem, SyncError, friendly_name
from openlp.plugins.librarysync.lib.transfer import safe_xml


@pytest.mark.parametrize('name,expected', [
    ('Sunday [123456abcdef].png', 'Sunday'), ('Welcome.xml', 'Welcome'), ('First Sunday.pptx', 'First Sunday')])
def test_friendly_names_hide_extensions_and_old_generated_identifiers(name, expected):
    assert friendly_name(name) == expected
    assert CloudItem('id', name).display_name == expected
    assert CloudItem('id', name, title='Organisation welcome').display_name == 'Organisation welcome'


def test_song_preview_preserves_verse_order_and_line_breaks_without_database(settings):
    xml = b'''<song xmlns="http://openlyrics.info/namespace/2009/song" version="0.8">
      <properties><titles><title>Amazing Grace</title></titles><authors><author>John Newton</author></authors>
      <copyright>Public domain</copyright><ccliNo>123</ccliNo><verseOrder>v1 c1 v1</verseOrder></properties>
      <lyrics><verse name="v1"><lines>Amazing grace<br/>How sweet the sound</lines></verse>
      <verse name="c1"><lines>Welcome everyone</lines></verse></lyrics></song>'''
    service, metadata = text_service_item(CloudItem('song', 'technical.xml', category='songs'), safe_xml(xml))
    assert service.title == 'Amazing Grace'
    assert [slide['verse'] for slide in service.slides] == ['V1', 'C1', 'V1']
    assert service.slides[0]['text'] == 'Amazing grace\nHow sweet the sound'
    assert metadata == {'Authors': 'John Newton', 'Copyright': 'Public domain', 'CCLI number': '123',
                        'Verse order': 'V1 C1 V1'}
    assert list(metadata)[-2:] == ['CCLI number', 'Verse order']
    assert service.raw_footer == ['Amazing Grace', 'John Newton', 'Public domain', '123']
    assert service.edit_id is None


def test_custom_preview_preserves_title_credits_and_slide_list(settings):
    xml = b'<song><title>Welcome</title><credit>Organisation</credit><lyrics>' \
          b'<verse>Hello everyone</verse><verse>Announcements</verse></lyrics></song>'
    service, metadata = text_service_item(CloudItem('custom', 'technical.xml', category='custom'), safe_xml(xml))
    assert service.title == 'Welcome'
    assert [slide['text'] for slide in service.slides] == ['Hello everyone', 'Announcements']
    assert [slide['verse'] for slide in service.slides] == ['1', '2']
    assert metadata == {'Credits': 'Organisation'}


@pytest.mark.parametrize('order', ['', 'c1 v1 c1'])
def test_song_preview_splits_forced_breaks_and_preserves_design_keys(settings, order):
    lines = 'First half<br/><p page-break-after="always"/><br/>Second half'
    xml = f'''<song xmlns="http://openlyrics.info/namespace/2009/song" version="0.8">
      <properties><titles><title>Forced break</title></titles><verseOrder>{order}</verseOrder></properties>
      <lyrics><verse name="v1"><lines>Verse</lines></verse>
      <verse name="c1"><lines>{lines}</lines></verse></lyrics></song>'''.encode()
    service, metadata = text_service_item(CloudItem('song', 'song.xml', category='songs'), safe_xml(xml))
    expected = [('c1', 0, 'First half'), ('c1', 1, 'Second half'), ('v1', 0, 'Verse'),
                ('c1', 0, 'First half'), ('c1', 1, 'Second half')] if order else [
                        ('v1', 0, 'Verse'), ('c1', 0, 'First half'), ('c1', 1, 'Second half')]
    assert [slide['text'].strip() for slide in service.slides] == [text for tag, split, text in expected]
    assert [(slide['metadata']['design_section'], slide['metadata']['design_split'], slide['text'].strip())
            for slide in service.slides] == expected
    assert [slide['verse'] for slide in service.slides] == [tag.upper() for tag, split, text in expected]
    assert metadata['Verse order'] == (order.upper() or 'V1 C1')


def test_empty_or_mismatched_text_cannot_be_previewed(settings):
    with pytest.raises(SyncError, match='slides'):
        text_service_item(CloudItem('custom', 'item.xml', category='custom'), safe_xml(b'<song><lyrics/></song>'))
    with pytest.raises(SyncError, match='OpenLyrics'):
        text_service_item(CloudItem('song', 'item.xml', category='songs'), safe_xml(b'<song><lyrics/></song>'))


def test_cloud_image_uses_fluent_inspector_and_friendly_name(settings, qtbot, tmp_path):
    path = tmp_path / 'Sunday.png'
    image = QtGui.QImage(200, 100, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('blue'))
    image.save(str(path))
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    item = CloudItem('image', 'Sunday [123456abcdef].png', category='images', modified='2026-10-09T01:00:00Z',
                     provider_name='Google Drive', size=path.stat().st_size)
    window = show_preview(parent, item, path)
    assert isinstance(window, CloudMediaPreview)
    assert isinstance(window, QtWidgets.fluentqt.Window)
    assert window.isWindow()
    assert window.windowTitle() == 'Sunday'
    assert window.metadata['Source'].text() == 'Google Drive'
    assert window.metadata['Resolution'].text() == '200 × 100'
    assert window.metadata['Access'].text() == 'View'
    assert 'Modified' in window.metadata
    assert next(iter(window.metadata)) == 'Resolution'
    window.reject()


@pytest.mark.parametrize('dismiss', ['accept', 'reject', 'close', 'closeWindow', 'escape'])
def test_cloud_window_can_maximise_and_finishes_once_on_close(settings, qtbot, dismiss):
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    window = CloudPreviewWindow(parent)
    qtbot.addWidget(window)
    QtWidgets.QVBoxLayout(window.contentWidget())
    window.resize(1000, 660)
    finished = MagicMock()
    window.finished.connect(finished)
    parent.show()
    window.show()
    assert window.isWindow() and parent.isEnabled()
    assert window.windowFlags() & QtCore.Qt.WindowType.WindowMaximizeButtonHint
    assert window.windowFlags() & QtCore.Qt.WindowType.WindowCloseButtonHint
    window.showMaximized()
    assert window.isMaximized()
    window.showNormal()
    assert not window.isMaximized()
    if dismiss == 'escape':
        qtbot.keyClick(window, QtCore.Qt.Key.Key_Escape)
    else:
        getattr(window, dismiss)()
    result = (QtWidgets.QDialog.DialogCode.Accepted if dismiss == 'accept'
              else QtWidgets.QDialog.DialogCode.Rejected)
    finished.assert_called_once_with(result)
    assert not window.isVisible() and parent.isVisible()
    window.reject()
    finished.assert_called_once()


def test_cloud_media_title_bar_close_stops_playback(settings, qtbot, tmp_path):
    import wave
    path = tmp_path / 'Music.wav'
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\x00\x00' * 8000)
    item = CloudItem('audio', path.name, category='media', size=path.stat().st_size)
    window = show_preview(None, item, path)
    qtbot.addWidget(window)
    window.show()
    assert not window.player.source().isEmpty()
    window.closeWindow()
    assert window.player.source().isEmpty()


def test_cloud_presentation_has_async_thumbnails_and_selectable_slides(settings, qtbot, tmp_path):
    path = tmp_path / 'Welcome.pdf'
    writer = QtGui.QPdfWriter(str(path))
    painter = QtGui.QPainter(writer)
    painter.fillRect(0, 0, writer.width(), writer.height(), QtGui.QColor('red'))
    writer.newPage()
    painter.fillRect(0, 0, writer.width(), writer.height(), QtGui.QColor('blue'))
    painter.end()
    del writer
    item = CloudItem('presentation', 'Welcome.pptx', category='presentations', size=2048,
                     provider_name='Google Drive')
    window = show_preview(None, item, tmp_path / item.name, path)
    qtbot.addWidget(window)
    window.show()
    assert isinstance(window, CloudPresentationPreview) and window.isWindow()
    assert window.slide_list.rowCount() == 2
    assert window.split_view.handleCount() == 2
    assert not window.slide_list.dragEnabled()
    assert not hasattr(window, 'next_button') and not hasattr(window, 'previous_button')
    assert window.metadata['Slides'].text() == '2'
    assert window.metadata['File type'].text() == 'PPTX'
    assert window.metadata['File size'].text() == '2.0 kB'

    def colour(label):
        pixmap = label.pixmap()
        if pixmap is None or pixmap.isNull():
            return None
        return pixmap.toImage().pixelColor(pixmap.width() // 2, pixmap.height() // 2).name()

    thumbnails = [window.slide_list.cellWidget(row, 0).findChild(QtWidgets.QLabel) for row in range(2)]
    qtbot.waitUntil(lambda: colour(thumbnails[0]) == '#ff0000' and colour(thumbnails[1]) == '#0000ff')
    qtbot.waitUntil(lambda: colour(window.viewer) == '#ff0000')
    qtbot.mouseClick(window.slide_list.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=window.slide_list.visualItemRect(window.slide_list.item(1, 0)).center())
    qtbot.waitUntil(lambda: window.page == 1 and colour(window.viewer) == '#0000ff')
    qtbot.keyClick(window.slide_list, QtCore.Qt.Key.Key_Up)
    qtbot.waitUntil(lambda: window.page == 0 and colour(window.viewer) == '#ff0000')
    window.closeWindow()
    assert window.document.status() == window.document.Status.Null


def test_provider_viewer_uses_grouped_metadata_without_fetching_a_page(settings, qtbot, monkeypatch):
    from openlp.core.widgets.metadataview import MetadataView
    viewer = QtWidgets.QWidget()
    viewer.setUrl = MagicMock()
    viewer.stop = MagicMock()
    monkeypatch.setattr('PySide6.QtWebEngineWidgets.QWebEngineView', lambda *args: viewer)
    item = CloudItem('document', 'Welcome.pptx', category='presentations', can_download=False,
                     preview_url='https://drive.google.com/file/d/document/view', provider_name='Google Drive')
    window = show_preview(None, item, None)
    qtbot.addWidget(window)
    assert isinstance(window, CloudPreviewWindow) and window.isWindow()
    details = window.findChild(MetadataView)
    assert details.fields is window.metadata
    assert window.metadata['Source'].text() == 'Google Drive'
    assert window.metadata['Access'].text() == 'View'
    viewer.setUrl.assert_called_once_with(QtCore.QUrl(item.preview_url))
    window.reject()
    viewer.stop.assert_called_once()


def test_cloud_slide_window_uses_preview_controller_and_embedded_display(settings, qtbot, monkeypatch):
    from openlp.core.display.screens import ScreenList
    from openlp.plugins.librarysync.lib.preview import CloudSlidePreview
    from openlp.core.widgets.views import ListPreviewWidget
    ScreenList.create(QtWidgets.QApplication.instance())
    display = QtWidgets.QWidget()
    display.set_theme = MagicMock()
    display.set_scale = MagicMock()
    display.load_verses = MagicMock()
    display.go_to_slide = MagicMock()
    display.deregister_display = MagicMock()
    monkeypatch.setattr('openlp.core.display.window.DisplayWindow', lambda *args, **kwargs: display)
    words = 'One\nTwo\nThree\nFour\nFive\nSix'
    root, xml = safe_xml(b'<song><title>Welcome</title><lyrics><verse>Hello everyone</verse></lyrics></song>')
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    window = CloudSlidePreview(parent, CloudItem('custom', 'item.xml', category='custom'), (root, xml))
    assert isinstance(window, CloudPreviewWindow) and window.isWindow()
    service = window.service_item
    service.get_theme_data = MagicMock(return_value=SimpleNamespace())
    service._rendered_slides = [{'text': 'Hello everyone', 'verse': 0}]
    service._display_slides = [{'text': words, 'title': 'Welcome', 'verse': '1'}]
    window.render()
    assert isinstance(window.slide_list, ListPreviewWidget)
    assert window.slide_list.rowCount() == 1
    option = QtWidgets.QStyleOptionViewItem()
    option.font = window.slide_list.font()
    delegate = window.slide_list.itemDelegate()
    index = window.slide_list.model().index(0, 0)
    assert delegate._document(option, index).toPlainText() == words
    window.slide_list.setColumnWidth(0, 400)
    height = delegate.sizeHint(option, index).height()
    long_words = 'Words that must stay visible when the column becomes narrower. ' * 8
    window.slide_list.item(0, 0).setText(long_words)
    window.slide_list.setColumnWidth(0, 260)
    assert delegate._document(option, index).toPlainText() == long_words
    assert delegate.sizeHint(option, index).height() > height
    assert not window.slide_list.dragEnabled()
    assert isinstance(window.split_view, QtWidgets.fluentqt.SplitView)
    assert window.split_view.panePreferredSize(0) == 460
    assert window.split_view.handleCount() == 2
    assert list(window.metadata)[-3:] == ['Created', 'Modified', 'Modified by']
    from fluentqt import Spacing
    ratio = display.parentWidget().layout()
    ratio.setGeometry(QtCore.QRect(0, 0, 700, 400))
    assert display.geometry().left() >= Spacing.Medium
    assert 700 - display.geometry().right() - 1 >= Spacing.Medium
    display.load_verses.assert_called_once_with(service._rendered_slides)
    display.go_to_slide.assert_called_with(0, raise_window=False)
    window.reject()
    display.deregister_display.assert_called_once()


def test_cloud_metadata_does_not_show_storage_filename():
    fields = cloud_metadata(CloudItem('f', 'unreadable.png', category='images'))
    assert fields['Item type'] == 'Images'
    assert 'unreadable' not in str(fields)


def test_cloud_metadata_uses_provider_permissions_and_places_audit_fields_last():
    item = CloudItem('f', 'technical.xml', category='songs', provider_name='Another provider', size=2048,
                     can_edit=True, created='2026-10-08T01:00:00Z',
                     modified='2026-10-09T01:00:00Z', modified_by='Sam')
    fields = cloud_metadata(item, {'Authors': 'Song author'})
    assert next(iter(fields)) == 'Authors'
    assert fields['Source'] == 'Another provider' and fields['Access'] == 'View, edit'
    assert 'kb' in fields['File size'].lower()
    assert 'Created by' not in fields and fields['Modified by'] == 'Sam'
    assert list(fields)[-3:] == ['Created', 'Modified', 'Modified by']
    missing = cloud_metadata(CloudItem('f', 'f.xml', category='songs'))
    assert missing['Access'] == 'View'
    assert missing['Modified by'] == '—'


def test_specific_theme_is_reported_warned_and_preview_scales_on_resize(settings, qtbot, monkeypatch):
    from openlp.core.common.registry import Registry
    from openlp.core.display.screens import ScreenList
    from PySide6 import QtCore
    ScreenList.create(QtWidgets.QApplication.instance())
    Registry().register('theme_manager', SimpleNamespace(get_theme_names=lambda: []))
    display = QtWidgets.QWidget()
    display.set_scale = MagicMock()
    display.deregister_display = MagicMock()
    monkeypatch.setattr('openlp.core.display.window.DisplayWindow', lambda *args, **kwargs: display)
    prepared = safe_xml(b'<song xmlns:olp="https://openlp.org/ns/library-sync/1"><title>Welcome</title>'
                        b'<olp:theme>Organisation theme</olp:theme><lyrics>'
                        b'<verse>Welcome everyone</verse></lyrics></song>')
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    from openlp.plugins.librarysync.lib.preview import CloudSlidePreview
    from pathlib import Path
    window = show_preview(parent, CloudItem('custom', 'Welcome.xml', category='custom'), Path('Welcome.xml'), prepared)
    assert isinstance(window, CloudSlidePreview)
    assert window.service_item.theme == 'Organisation theme'
    assert not window.theme_warning.isHidden()
    assert 'not installed' in window.theme_warning.message()
    width = ScreenList().current.display_geometry.width()
    window.resize_preview(QtCore.QSize(width // 2, 300))
    display.set_scale.assert_called_with(0.5)
    window.resize_preview(QtCore.QSize(width // 4, 150))
    display.set_scale.assert_called_with(0.25)
    window.reject()
    window.stop_preview()
    display.deregister_display.assert_called_once()


@pytest.mark.parametrize('zone_name, date, hour', [('Australia/Sydney', 9, 1), ('America/New_York', 8, 10)])
def test_cloud_dates_use_system_timezone_with_daylight_saving(monkeypatch, zone_name, date, hour):
    from openlp.plugins.librarysync.lib.preview import format_local_time
    zone = QtCore.QTimeZone(zone_name.encode())
    monkeypatch.setattr(QtCore.QTimeZone, 'systemTimeZone', lambda: zone)
    local = QtCore.QDateTime(QtCore.QDate(2026, 10, date), QtCore.QTime(hour, 0), zone)
    expected = QtCore.QLocale().toString(local, QtCore.QLocale.FormatType.ShortFormat)
    item = CloudItem('song', 'song.xml', category='songs', created='2026-10-08T14:00:00Z',
                     modified='2026-10-08T16:00:00+02:00')
    fields = cloud_metadata(item)
    assert fields['Created'] == fields['Modified'] == expected
    assert format_local_time(item.modified) == expected
    assert format_local_time('') == format_local_time('invalid') == '—'
