"""Native cloud previews using the same slide renderer and media inspector as Library."""
import html
from pathlib import Path

from fluentqt import Spacing

from PySide6 import QtCore

from openlp.core.common.i18n import translate
from openlp.core.common.registry import Registry
from openlp.core.display.screens import ScreenList
from openlp.core.lib import ItemCapabilities
from openlp.core.lib.itemexport import xml_design
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.layouts import AspectRatioLayout
from openlp.core.widgets.mediapreview import MediaPreview
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
    return {'Source': item.provider_name or tr('Cloud Library'), 'Item type': tr(CATEGORIES[item.category]),
            'File size': QtCore.QLocale().formattedDataSize(
                item.size, 1, QtCore.QLocale.DataSizeFormat.DataSizeTraditionalFormat),
            'Access': tr('View, edit') if item.can_edit else tr('View'), **(details or {}),
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
    service.raw_footer = [html.escape(value) for value in [service.title, *metadata.values()] if value]
    for index, (tag, text) in enumerate(verses):
        section = tag if item.category == 'songs' else f'custom-{index + 1}'
        service.add_from_text(text, tag.upper(), metadata={'design_section': section})
    return service, {key: value for key, value in metadata.items() if value}


class CloudSlidePreview(QtWidgets.QDialog):
    """A Fluent window with Preview controller rows and an independent embedded display."""
    def __init__(self, parent, item, prepared):
        super().__init__(parent)
        self.service_item, metadata = text_service_item(item, prepared)
        self.preview_stopped = False
        self.setWindowTitle(self.service_item.title)
        self.resize(1480, 900)
        self.setMinimumSize(960, 600)
        layout = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QLabel(self.service_item.title)
        heading.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        heading.setFluentTypography(QtWidgets.fluentqt.FontRole.Title)
        layout.addWidget(heading)
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
        self.split_view = QtWidgets.fluentqt.SplitView(self)
        self.split_view.setDefaultSizeHint(QtCore.QSize(1400, 680))
        screen = ScreenList().current.display_geometry.size()
        self.slide_list = ListPreviewWidget(self, screen.width() / screen.height(), max_lines=None)
        self.slide_list.setDragEnabled(False)
        self.slide_list.cellClicked.connect(lambda row, column: self.change_slide(row))
        self.slide_list.keyboard_slide_changed.connect(lambda: self.change_slide(self.slide_list.currentRow()))
        self.split_view.addPane(self.slide_list)
        self.split_view.setPaneMinimumSize(0, 260)
        self.split_view.setPaneMaximumSize(0, 650)
        self.split_view.setPanePreferredSize(0, 380)
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
        details = QtWidgets.QWidget(self)
        fields = QtWidgets.QFormLayout(details)
        fields.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.metadata = {}
        for key, value in cloud_metadata(item, metadata).items():
            label = QtWidgets.QLabel(value)
            label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            self.metadata[key] = label
            fields.addRow(tr(key), label)
        details_scroll = QtWidgets.QScrollArea(self)
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        details_scroll.setWidget(details)
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


class CloudWebPreview(QtWidgets.QDialog):
    """Keep a provider's permission-limited viewer inside the application."""
    def __init__(self, parent, item):
        super().__init__(parent)
        if not preview_url_allowed(item.preview_url):
            raise SyncError('This cloud item has no preview available.')
        self.setWindowTitle(item.display_name)
        self.resize(1000, 660)
        layout = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QLabel(item.display_name)
        heading.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        heading.setFluentTypography(QtWidgets.fluentqt.FontRole.Title)
        layout.addWidget(heading)
        metadata = QtWidgets.QLabel(' · '.join(cloud_metadata(item).values()), self)
        metadata.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        metadata.setWordWrap(True)
        layout.addWidget(metadata)
        from PySide6.QtWebEngineWidgets import QWebEngineView
        self.viewer = QWebEngineView(self)
        self.viewer.setUrl(QtCore.QUrl(item.preview_url))
        layout.addWidget(self.viewer, 1)
        close = QtWidgets.QPushButton(tr('Close'), self)
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.finished.connect(self.viewer.stop)


def show_preview(parent, item, path, prepared=None):
    if item.category == 'media' and prepared:
        return MediaPreview(parent, Path(item.name), item.display_name, kind='media',
                            extra_metadata=cloud_metadata(item), allow_reveal=False,
                            source_url=QtCore.QUrl(prepared), file_size=item.size)
    if isinstance(prepared, Path):
        return MediaPreview(parent, Path(item.name), item.display_name,
                            kind='presentation' if item.category == 'presentations' else 'image',
                            extra_metadata=cloud_metadata(item), allow_reveal=False,
                            file_size=item.size, cover_path=prepared)
    if path is None:
        return CloudWebPreview(parent, item)
    if item.category in ('songs', 'custom', 'themes'):
        return CloudSlidePreview(parent, item, prepared)
    return MediaPreview(parent, path, item.display_name,
                        kind={'images': 'image', 'media': 'media', 'presentations': 'presentation'}[item.category],
                        preview_paths=prepared, extra_metadata=cloud_metadata(item), allow_reveal=False,
                        file_size=item.size)
