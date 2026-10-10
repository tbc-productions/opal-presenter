"""Native cloud previews using the same slide renderer and media inspector as Library."""
import html
from pathlib import Path

from fluentqt import Spacing

from PySide6 import QtCore, QtGui
from PySide6.QtPdf import QPdfDocument, QPdfPageRenderer

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.display.screens import ScreenList
from openlp.core.lib import ItemCapabilities
from openlp.core.lib.itemexport import xml_design
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.layouts import AspectRatioLayout
from openlp.core.widgets.mediapreview import MediaPreviewMixin
from openlp.core.widgets.metadataview import MetadataView
from openlp.core.widgets.views import ListPreviewWidget
from openlp.plugins.librarysync.lib.provider import CATEGORIES, SyncError, preview_url_allowed


def tr(text):
    return translate('LibrarySync', text)


def format_local_time(value):
    parsed = QtCore.QDateTime.fromString(value, QtCore.Qt.DateFormat.ISODate)
    if not parsed.isValid():
        return '—'
    local = parsed.toTimeZone(QtCore.QTimeZone.systemTimeZone())
    return QtCore.QLocale().toString(local, QtCore.QLocale.FormatType.ShortFormat)


def cloud_metadata(item, details=None):
    return {**(details or {}),
            'File size': QtCore.QLocale().formattedDataSize(
                item.size, 1, QtCore.QLocale.DataSizeFormat.DataSizeTraditionalFormat),
            'Item type': tr(CATEGORIES[item.category]), 'Source': item.provider_name or tr('Cloud Library'),
            'Access': tr('View, edit') if item.can_edit else tr('View'),
            'Created': format_local_time(item.created),
            'Modified': format_local_time(item.modified), 'Modified by': item.modified_by or '—'}


def text_service_item(item, prepared):
    """Build a preview without saving a temporary song or changing the local database."""
    service = ServiceItem()
    service.name = item.category
    metadata = {}
    if item.category == 'themes':
        from openlp.core.display.render import VERSE, VERSE2
        service.title = item.display_name
        service.get_theme_data = lambda *args, **kwargs: prepared
        service.raw_footer = [tr('Theme preview')]
        for index, text in enumerate((VERSE, VERSE2), 1):
            service.add_from_text(text, f'V{index}')
        return service, {'Theme': service.title}
    root, xml = prepared
    if item.category == 'songs':
        namespace = '{http://openlyrics.info/namespace/2009/song}'
        if root.tag != namespace + 'song':
            raise SyncError('This cloud item is not an OpenLyrics song.')
        properties = root.find(namespace + 'properties')
        if properties is None:
            raise SyncError('The cloud song has no metadata.')
        service.title = properties.findtext(namespace + 'titles/' + namespace + 'title') or item.display_name
        authors = properties.findall(namespace + 'authors/' + namespace + 'author')
        metadata['Authors'] = ', '.join(''.join(author.itertext()) for author in authors)
        metadata['Copyright'] = properties.findtext(namespace + 'copyright') or ''
        metadata['CCLI number'] = properties.findtext(namespace + 'ccliNo') or ''
        order = (properties.findtext(namespace + 'verseOrder') or '').split()
        from openlp.plugins.songs.lib.openlyricsxml import OpenLyrics
        converter = OpenLyrics(None)
        verses = []
        for verse in root.findall(namespace + 'lyrics/' + namespace + 'verse'):
            text = '\n[---]\n'.join(converter._process_verse_lines(lines, root.get('version', '0.8'))
                                    for lines in verse.findall(namespace + 'lines'))
            tag = verse.get('name', 'v1')
            verses.append((tag, text))
        ordered = []
        for tag in order:
            ordered.extend(verse for verse in verses if verse[0] == tag or (
                verse[0].startswith(tag) and verse[0][len(tag):].isalpha()))
        verses = ordered or verses
        metadata['Verse order'] = ' '.join(tag.upper() for tag, text in verses)
    else:
        if root.tag != 'song':
            raise SyncError('This cloud item is not a Custom Slides document.')
        service.title = root.findtext('title') or item.display_name
        metadata['Credits'] = root.findtext('credit') or ''
        verses = [(str(index), verse.text or '') for index, verse in enumerate(root.findall('lyrics/verse'), 1)]
    if not 1 <= len(verses) <= 1000:
        raise SyncError('The cloud item must contain between 1 and 1000 slides.')
    service.slide_design = xml_design(xml)
    service.title = item.title or service.title
    service.theme = root.findtext('{https://openlp.org/ns/library-sync/1}theme') or ''
    if service.theme:
        metadata['Theme'] = service.theme
        service.add_capability(ItemCapabilities.ProvidesOwnTheme)
    footer = [service.title, *(value for key, value in metadata.items() if key != 'Verse order')]
    service.raw_footer = [html.escape(value) for value in footer if value]
    for index, (tag, text) in enumerate(verses):
        section = tag if item.category == 'songs' else f'custom-{index + 1}'
        parts = text.split('[--}{--]\n') if item.category == 'songs' else [text]
        for split_index, part in enumerate(parts):
            service.add_from_text(
                part, tag.upper(), metadata={'design_section': section, 'design_split': split_index})
    return service, {key: value for key, value in metadata.items() if value}


class CloudPreviewWindow(QtWidgets.fluentqt.Window):
    """Independent Fluent preview with the panel's existing close/cleanup contract."""
    finished = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentWidget(QtWidgets.QWidget(self))
        self._result = QtWidgets.QDialog.DialogCode.Rejected
        self._preview_finished = False

    def accept(self):
        self._result = QtWidgets.QDialog.DialogCode.Accepted
        self.close()

    def reject(self):
        self.close()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and not self._preview_finished:
            self._preview_finished = True
            self.finished.emit(self._result)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
            event.accept()
        else:
            super().keyPressEvent(event)


class CloudMediaPreview(MediaPreviewMixin, CloudPreviewWindow):
    """Library inspector content in a Cloud Library Fluent window."""


class CloudPresentationPreview(CloudPreviewWindow):
    """Asynchronous slide thumbnails and a full-size page in resizable Fluent panes."""
    def __init__(self, parent, item, path, prepared=None):
        super().__init__(parent)
        self.setWindowTitle(item.display_name)
        self.resize(1480, 900)
        self.setMinimumSize(960, 600)
        layout = QtWidgets.QVBoxLayout(self.contentWidget())
        source = prepared if isinstance(prepared, Path) else path
        self.document = QPdfDocument(self)
        self.document.load(str(source))
        self.pdf = self.document.status() == QPdfDocument.Status.Ready
        self.page_count = self.document.pageCount() if self.pdf else 1
        cover = QtGui.QImage(str(source)) if not self.pdf else QtGui.QImage()
        if not self.pdf and cover.isNull():
            raise SyncError('This presentation preview could not be opened.')
        if not self.pdf:
            warning = QtWidgets.fluentqt.InfoBar(self)
            warning.setSeverity(QtWidgets.fluentqt.InfoBar.InfoBarSeverity.Warning)
            warning.setIsClosable(False)
            warning.setMessage(tr('Only the cover is available. Enable a compatible presentation application '
                                  'to view all slides.'))
            layout.addWidget(warning)
        size = self.document.pagePointSize(0).toSize() if self.pdf else cover.size()
        ratio = size.width() / max(1, size.height()) if size.width() else 16 / 9
        self.split_view = QtWidgets.SplitView(self)
        self.slide_list = ListPreviewWidget(self, ratio)
        self.slide_list.setDragEnabled(False)
        self.split_view.addPane(self.slide_list)
        self.split_view.setPaneMinimumSize(0, 220)
        self.split_view.setPaneMaximumSize(0, 650)
        self.split_view.setPanePreferredSize(0, 380)
        viewer = QtWidgets.QWidget(self)
        self.viewer = QtWidgets.QLabel(viewer)
        self.viewer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.viewer.setScaledContents(True)
        self.viewer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
        self.viewer.setText(tr('Loading slide…'))
        display_layout = AspectRatioLayout(viewer, ratio)
        display_layout.margin = Spacing.Medium
        display_layout.addWidget(self.viewer)
        self.split_view.addPane(viewer)
        self.split_view.setPaneMinimumSize(1, 280)
        self.split_view.setFillPaneIndex(1)
        details = {'Slides': str(self.page_count)} if self.pdf else {}
        details['File type'] = Path(item.name).suffix.lstrip('.').upper()
        details_scroll = MetadataView(cloud_metadata(item, details), self)
        self.metadata = details_scroll.fields
        self.split_view.addPane(details_scroll)
        self.split_view.setPaneMinimumSize(2, 260)
        self.split_view.setPaneMaximumSize(2, 540)
        self.split_view.setPanePreferredSize(2, 300)
        layout.addWidget(self.split_view, 1)
        close = QtWidgets.QPushButton(tr('Close'), self)
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        placeholder = Path(source).parent / 'slide-placeholder.png'
        image = QtGui.QImage(320, max(1, int(320 / ratio)), QtGui.QImage.Format.Format_RGB32)
        image.fill(self.palette().color(QtGui.QPalette.ColorRole.Base))
        image.save(str(placeholder))
        service = ServiceItem()
        for page in range(self.page_count):
            service.add_from_image(placeholder, str(page + 1), file_hash=str(page))
        self.slide_list.replace_service_item(service, 380, 0)
        self.page = 0
        self.slide_list.cellClicked.connect(lambda row, column: self.show_page(row))
        self.slide_list.keyboard_slide_changed.connect(lambda: self.show_page(self.slide_list.currentRow()))
        self.page_renderer = QPdfPageRenderer(self)
        self.thumbnail_renderer = QPdfPageRenderer(self)
        for renderer in (self.page_renderer, self.thumbnail_renderer):
            renderer.setDocument(self.document)
            renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        self.page_renderer.pageRendered.connect(self.page_rendered)
        self.thumbnail_renderer.pageRendered.connect(self.thumbnail_rendered)
        self.finished.connect(self.stop_preview)
        self.show_page(0)
        if self.pdf:
            for page in range(self.page_count):
                thumb_size = self.document.pagePointSize(page).toSize().scaled(
                    320, 240, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
                self.thumbnail_renderer.requestPage(page, thumb_size)
        else:
            self.thumbnail_rendered(0, cover.size(), cover, None, 0)

    def show_page(self, page):
        if not 0 <= page < self.page_count:
            return
        self.page = page
        self.slide_list.change_slide(page)
        if self.pdf:
            size = self.document.pagePointSize(page).toSize().scaled(
                1920, 1080, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.page_renderer.requestPage(page, size)
        else:
            self.viewer.setPixmap(self.slide_list.cellWidget(page, 0).findChild(QtWidgets.QLabel).pixmap())

    def page_rendered(self, page, size, image, options, request):
        if page == self.page and not self._preview_finished:
            self.viewer.setPixmap(QtGui.QPixmap.fromImage(image))

    def thumbnail_rendered(self, page, size, image, options, request):
        if not self._preview_finished and not image.isNull():
            cell = self.slide_list.cellWidget(page, 0)
            cell.layout().aspect_ratio = image.width() / image.height()
            cell.findChild(QtWidgets.QLabel).setPixmap(QtGui.QPixmap.fromImage(image))
            if not self.pdf:
                self.viewer.setPixmap(QtGui.QPixmap.fromImage(image))

    def stop_preview(self):
        self.page_renderer.setDocument(None)
        self.thumbnail_renderer.setDocument(None)
        self.document.close()


class CloudSlidePreview(CloudPreviewWindow):
    """A Fluent window with Preview controller rows and an independent embedded display."""
    def __init__(self, parent, item, prepared):
        super().__init__(parent)
        self.service_item, metadata = text_service_item(item, prepared)
        self.preview_stopped = False
        self.setWindowTitle(self.service_item.title)
        self.resize(1480, 900)
        self.setMinimumSize(960, 600)
        layout = QtWidgets.QVBoxLayout(self.contentWidget())
        self.theme_warning = QtWidgets.fluentqt.InfoBar(self)
        policy = self.theme_warning.sizePolicy()
        policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Policy.Expanding)
        self.theme_warning.setSizePolicy(policy)
        self.theme_warning.setIsClosable(False)
        self.theme_warning.setSeverity(QtWidgets.fluentqt.InfoBar.InfoBarSeverity.Warning)
        missing = (self.service_item.theme and self.service_item.theme not in
                   Registry().get('theme_manager').get_theme_names())
        if missing:
            self.theme_warning.setMessage(tr('The theme “{name}” is not installed. '
                                             'The preview uses its embedded design or your default theme.')
                                          .format(name=self.service_item.theme))
        self.theme_warning.setVisible(bool(missing))
        layout.addWidget(self.theme_warning)
        self.split_view = QtWidgets.SplitView(self)
        self.split_view.setDefaultSizeHint(QtCore.QSize(1400, 680))
        screen = ScreenList().current.display_geometry.size()
        self.slide_list = ListPreviewWidget(self, screen.width() / screen.height(), max_lines=None)
        self.slide_list.setDragEnabled(False)
        self.slide_list.cellClicked.connect(lambda row, column: self.change_slide(row))
        self.slide_list.keyboard_slide_changed.connect(lambda: self.change_slide(self.slide_list.currentRow()))
        self.split_view.addPane(self.slide_list)
        self.split_view.setPaneMinimumSize(0, 260)
        self.split_view.setPaneMaximumSize(0, 650)
        self.split_view.setPanePreferredSize(0, 460 if item.category in ('songs', 'custom') else 380)
        viewer = QtWidgets.QWidget(self)
        ratio = AspectRatioLayout(viewer, screen.width() / screen.height())
        ratio.margin = Spacing.Medium
        from openlp.core.display.window import DisplayWindow
        self.display = DisplayWindow(viewer, can_show_startup_screen=False, embedded=True,
                                     after_loaded_callback=self.render)
        self.display.allow_theme_transitions = False
        self.display.allow_item_transitions = False
        ratio.addWidget(self.display)
        ratio.resize.connect(self.resize_preview)
        self.split_view.addPane(viewer)
        self.split_view.setPaneMinimumSize(1, 280)
        self.split_view.setFillPaneIndex(1)
        details_scroll = MetadataView(cloud_metadata(item, metadata), self)
        self.metadata = details_scroll.fields
        self.split_view.addPane(details_scroll)
        self.split_view.setPaneMinimumSize(2, 260)
        self.split_view.setPaneMaximumSize(2, 540)
        self.split_view.setPanePreferredSize(2, 300)
        layout.addWidget(self.split_view, 1)
        close = QtWidgets.QPushButton(tr('Close'), self)
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.finished.connect(self.stop_preview)

    def render(self):
        try:
            service = self.service_item
            self.resize_preview(self.display.size())
            self.display.set_theme(service.get_theme_data(), service_item_type=service.service_item_type)
            self.display.load_verses(service.rendered_slides)
            self.slide_list.replace_service_item(service, self.slide_list.viewport().width(), 0)
            self.change_slide(0)
        except Exception:
            self.display.hide()
            QtWidgets.QMessageBox.warning(self, tr('Cloud preview'), tr('The slide preview could not be rendered.'))

    def resize_preview(self, size):
        width = ScreenList().current.display_geometry.width()
        self.display.set_scale(size.width() / max(1, width))

    def change_slide(self, row):
        if 0 <= row < self.slide_list.rowCount():
            self.slide_list.change_slide(row)
            self.display.go_to_slide(row, raise_window=False)

    def stop_preview(self):
        if self.preview_stopped:
            return
        self.preview_stopped = True
        self.display.deregister_display()
        self.display.close()


class CloudWebPreview(CloudPreviewWindow):
    """Keep a provider's permission-limited viewer inside the application."""
    def __init__(self, parent, item):
        super().__init__(parent)
        if not preview_url_allowed(item.preview_url):
            raise SyncError('This cloud item has no preview available.')
        self.setWindowTitle(item.display_name)
        self.resize(1000, 660)
        layout = QtWidgets.QVBoxLayout(self.contentWidget())
        from PySide6.QtWebEngineWidgets import QWebEngineView
        self.viewer = QWebEngineView(self)
        self.viewer.setUrl(QtCore.QUrl(item.preview_url))
        body = QtWidgets.QHBoxLayout()
        body.addWidget(self.viewer, 1)
        details = MetadataView(cloud_metadata(item), self)
        details.setFixedWidth(300)
        self.metadata = details.fields
        body.addWidget(details)
        layout.addLayout(body, 1)
        close = QtWidgets.QPushButton(tr('Close'), self)
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.finished.connect(self.viewer.stop)


def show_preview(parent, item, path, prepared=None):
    if item.category == 'presentations' and path is not None:
        return CloudPresentationPreview(parent, item, path, prepared)
    if item.category == 'media' and prepared:
        return CloudMediaPreview(parent, Path(item.name), item.display_name, kind='media',
                                 extra_metadata=cloud_metadata(item), allow_reveal=False,
                                 source_url=QtCore.QUrl(prepared), file_size=item.size)
    if isinstance(prepared, Path):
        return CloudMediaPreview(parent, Path(item.name), item.display_name,
                                 kind='presentation' if item.category == 'presentations' else 'image',
                                 extra_metadata=cloud_metadata(item), allow_reveal=False,
                                 file_size=item.size, cover_path=prepared)
    if path is None:
        return CloudWebPreview(parent, item)
    if item.category in ('songs', 'custom', 'themes'):
        return CloudSlidePreview(parent, item, prepared)
    return CloudMediaPreview(parent, path, item.display_name,
                             kind={'images': 'image', 'media': 'media', 'presentations': 'presentation'}[item.category],
                             preview_paths=prepared, extra_metadata=cloud_metadata(item), allow_reveal=False,
                             file_size=item.size)
