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
The :mod:`listpreviewwidget` is a widget that lists the slides in the slide controller.
It is based on a QTableWidget but represents its contents in list form.
"""
import re
from collections import Counter
from pathlib import Path

from fluentqt import Spacing
from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import UiStrings
from openlp.core.common.mixins import RegistryProperties
from openlp.core.common.platform import is_win
from openlp.core.common.registry import Registry
from openlp.core.lib.serviceitem import ItemCapabilities, ServiceItem
from openlp.core.ui.style import use_alternate_rows
from openlp.core.widgets.layouts import AspectRatioLayout


SONG_SECTION_DEFAULT_COLORS = {
    'intro': '#4ADE80',
    'verse': '#60A5FA',
    'pre_chorus': '#FBBF24',
    'chorus': '#F87171',
    'bridge': '#C084FC',
    'ending': '#94A3B8',
    'other': '#E2E8F0'
}

SONG_SECTION_COLOR_KEYS = {
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


def handle_mime_data_urls(mime_data):
    """
    Process the data from a drag and drop operation.

    :param QtCore.QMimeData mime_data: The mime data from the drag and drop opperation.
    :return: A list of file paths that were dropped
    :rtype: list[Path]
    """
    file_paths = []
    for url in mime_data.urls():
        local_path = Path(url.toLocalFile())
        if local_path.is_file():
            file_paths.append(local_path)
        elif local_path.is_dir():
            for path in local_path.iterdir():
                file_paths.append(path)
    return file_paths


def remove_url_prefix(filename):
    """
    Remove the "file://" URL prefix

    :param str filename: The filename that may have a file URL prefix
    :returns str: The file name without the file URL prefix
    """
    return filename.replace('file://', '')


SLIDE_ROW_MAX_LINES = 4
SLIDE_TEXT_HTML_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1


class _SlideBackgroundModel(QtCore.QIdentityProxyModel):
    """Let the Fluent delegate paint row chrome without its single-line text."""
    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return ''
        return super().data(index, role)


class SlidePreviewDelegate(QtWidgets.QStyledItemDelegate):
    """Paint the first four wrapped lines of slide text inside Fluent rows."""
    def __init__(self, view):
        super().__init__(view)
        self._view = view
        self._native_delegate = view.itemDelegate()
        self._background_model = _SlideBackgroundModel(self)
        self._background_model.setSourceModel(view.model())

    def _document(self, option, index):
        document = QtGui.QTextDocument()
        document.setDocumentMargin(0)
        document.setDefaultFont(option.font)
        text_option = document.defaultTextOption()
        text_option.setWrapMode(QtGui.QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(text_option)
        html = index.data(SLIDE_TEXT_HTML_ROLE)
        if html:
            document.setHtml(html)
        else:
            document.setPlainText(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or '')
        document.setTextWidth(max(1, self._view.columnWidth(index.column()) - 4 * Spacing.Small))
        # Measure the wrapped layout before trimming so the limit follows the panel width.
        document.size()
        block = document.begin()
        line_count = 0
        while block.isValid():
            layout = block.layout()
            for line_index in range(layout.lineCount()):
                line_count += 1
                if line_count == SLIDE_ROW_MAX_LINES:
                    line = layout.lineAt(line_index)
                    end = block.position() + line.textStart() + line.textLength()
                    if end >= document.characterCount() - 1:
                        return document
                    cursor = QtGui.QTextCursor(document)
                    cursor.setPosition(end)
                    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End,
                                        QtGui.QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                    while cursor.position() and document.characterAt(cursor.position() - 1).isspace():
                        cursor.deletePreviousChar()
                    ellipsis_format = cursor.charFormat()
                    ellipsis_format.setVerticalAlignment(QtGui.QTextCharFormat.VerticalAlignment.AlignNormal)
                    cursor.insertText('…', ellipsis_format)
                    cursor.movePosition(QtGui.QTextCursor.MoveOperation.PreviousCharacter)
                    # Make room for the ellipsis without wrapping it onto a fifth line.
                    document.size()
                    while document.lineCount() > SLIDE_ROW_MAX_LINES and cursor.position():
                        cursor.deletePreviousChar()
                        document.size()
                    return document
            block = block.next()
        return document

    def paint(self, painter, option, index):
        if not self._view.service_item.is_text():
            self._native_delegate.paint(painter, option, index)
            return
        self._native_delegate.paint(painter, option, self._background_model.mapFromSource(index))
        document = self._document(option, index)
        context = QtGui.QAbstractTextDocumentLayout.PaintContext()
        context.palette = option.palette
        painter.save()
        painter.setClipRect(option.rect)
        painter.translate(option.rect.left() + 2 * Spacing.Small,
                          option.rect.top() + (option.rect.height() - document.size().height()) / 2)
        document.documentLayout().draw(painter, context)
        painter.restore()

    def sizeHint(self, option, index):
        hint = self._native_delegate.sizeHint(option, index)
        if self._view.service_item.is_text():
            hint.setHeight(int(self._document(option, index).size().height() + 2 * Spacing.Small))
        return hint


class ListPreviewWidget(QtWidgets.DataGrid, RegistryProperties):
    """
    A special type of QTableWidget which lists the slides in the slide controller

    :param parent:
    :param screen_ratio:
    """
    resize_event = QtCore.Signal()
    keyboard_slide_changed = QtCore.Signal()

    def __init__(self, parent, screen_ratio):
        """
        Initializes the widget to default state.

        An empty ``ServiceItem`` is used by default. replace_service_manager_item() needs to be called to make this
        widget display something.
        """
        super().__init__(parent)
        self._setup(screen_ratio)

    def _setup(self, screen_ratio):
        """
        Set up the widget
        """
        self.setColumnCount(1)
        self.horizontalHeader().setVisible(False)
        vertical_header = self.verticalHeader()
        # Keep row height under explicit control; ResizeToContents can grow rows to full image height.
        vertical_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        vertical_header.setStyleSheet('QHeaderView::section { padding-left: 2px; padding-right: 2px; }')
        vertical_header.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        target_width = int((self.fontMetrics().horizontalAdvance('W99') + 16) * 0.6)
        vertical_header.setMinimumWidth(max(20, target_width))
        self.setColumnWidth(0, self.parent().width())
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setWordWrap(True)
        self.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scrollbar = self.verticalFluentScrollBar()
        # Fluent animates its overlay independently of Qt's scrollbar policy.
        # Keep the native thumb visible so slide-list progress is always available.
        for animation in scrollbar.findChildren(QtCore.QPropertyAnimation):
            if animation.targetObject() == scrollbar and bytes(animation.propertyName()) == b'opacity':
                animation.valueChanged.connect(lambda value, bar=scrollbar: bar.setOpacity(1.0))
        scrollbar.setOpacity(1.0)
        self.setAlternatingRowColors(use_alternate_rows())
        # Initialize variables.
        self.service_item = ServiceItem()
        self.setItemDelegate(SlidePreviewDelegate(self))
        self.screen_ratio = screen_ratio
        self.auto_row_height = 100
        # Connect signals
        self.verticalHeader().sectionResized.connect(self.row_resized)

    def _resolve_song_section_color(self, verse_tag):
        section_key = SONG_SECTION_COLOR_KEYS.get(str(verse_tag).lower()[:1], 'other')
        default_color = SONG_SECTION_DEFAULT_COLORS[section_key]
        color_value = self.settings.value('songs/section color {key}'.format(key=section_key))
        color_value = str(color_value).strip().upper() if color_value is not None else default_color
        if not color_value.startswith('#'):
            color_value = '#{value}'.format(value=color_value)
        if RGBA_HEX_REGEX.match(color_value):
            color_value = color_value[:7]
        if not RGB_HEX_REGEX.match(color_value):
            color_value = default_color
        return QtGui.QColor(color_value)

    @staticmethod
    def _resolve_verse_number(verse_text):
        match = re.search(r'(\d+)', str(verse_text))
        if not match:
            return 1
        try:
            return max(1, int(match.group(1)))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _custom_page_suffix(page_number):
        """Return a, b, ..., z, aa, ... for a one-based page number."""
        suffix = ''
        while page_number:
            page_number, letter = divmod(page_number - 1, 26)
            suffix = chr(ord('a') + letter) + suffix
        return suffix

    def _resolve_opacity(self, verse_number):
        """Resolve opacity from verse number using settings for min/max values."""
        minimum = int(self.settings.value('songs/section background opacity minimum'))
        maximum = int(self.settings.value('songs/section background opacity maximum'))
        opacity_percent = min(maximum, minimum + ((verse_number - 1) * 10))
        return opacity_percent / 100.0

    def _sync_vertical_header_width_from_labels(self, labels):
        """
        Widen the row header column when labels are long (e.g. Bible ``1:22-23``).
        """
        vh = self.verticalHeader()
        if not labels:
            vh.setMinimumWidth(0)
            return
        fm = vh.fontMetrics()
        margin = self.style().pixelMetric(QtWidgets.QStyle.PixelMetric.PM_HeaderMargin, None, vh)
        margin = max(16, margin * 2 + 8)
        max_line = 0
        for lab in labels:
            for line in str(lab).split('\n'):
                max_line = max(max_line, fm.horizontalAdvance(line))
        target_width = max_line + margin
        vh.setMinimumWidth(target_width)

    def resizeEvent(self, event):
        """
        Overloaded method from QTableWidget. Will recalculate the layout.
        """
        super().resizeEvent(event)
        self.__recalculate_layout()
        self.resize_event.emit()

    def __recalculate_layout(self):
        """
        Recalculates the layout of the table widget. It will set height and width
        of the table cells. QTableWidget does not adapt the cells to the widget size on its own.
        """
        self.setColumnWidth(0, self.viewport().width())
        if self.service_item:
            # Sort out songs, bibles, etc.
            if self.service_item.is_text():
                self.resizeRowsToContents()
            # Sort out image heights.
            else:
                height = self.viewport().width() // self.screen_ratio
                self.auto_row_height = max(self.viewport().height() / 4, 100)
                height = min(height, self.auto_row_height)
                # Apply new height to slides
                for slide_index in range(len(self.service_item.slides)):
                    self.setRowHeight(slide_index, int(height))

    def row_resized(self, row, old_height, new_height):
        """
        Will scale non-image slides.
        """
        if self.service_item.is_text():
            return
        # Get and validate label widget containing slide & adjust max width
        try:
            self.cellWidget(row, 0).children()[1].setMaximumWidth(new_height * self.screen_ratio)
        except Exception:
            return

    def screen_size_changed(self, screen_ratio):
        """
        This method is called whenever the live screen size changes, which then makes a layout recalculation necessary

        :param screen_ratio: The new screen ratio
        """
        self.screen_ratio = screen_ratio
        self.__recalculate_layout()

    def clear_list(self):
        """
        Clear the preview list
        :return:
        """
        self.setRowCount(0)
        self.clear()
        self.verticalHeader().setMinimumWidth(0)

    def replace_service_item(self, service_item, width, slide_number):
        """
        Replace the current preview items with the ones in service_item and display the given slide

        :param service_item: The service item to insert
        :param width: The width of the column
        :param slide_number: The slide number to pre-select
        """
        self.service_item = service_item
        self.setRowCount(0)
        self.clear_list()
        row = 0
        text = []
        header_colors = []
        slides = self.service_item.display_slides if self.service_item.is_text() else self.service_item.slides
        custom_page_counts = Counter(slide['verse'] for slide in slides) if self.service_item.name == 'custom' else {}
        custom_page_positions = Counter()
        for slide_index, slide in enumerate(slides):
            self.setRowCount(self.slide_count() + 1)
            item = QtWidgets.QTableWidgetItem()
            slide_height = 0
            if self.service_item.is_text():
                collection = getattr(self.service_item, 'is_slide_set', False) is True
                if collection:
                    row = str(slide['verse'])
                    header_colors.append(None)
                elif self.service_item.name == 'custom':
                    # Split pages share a source slide tag, so append a letter only when needed.
                    verse = slide['verse']
                    row = str(verse)
                    if custom_page_counts[verse] > 1:
                        custom_page_positions[verse] += 1
                        row += self._custom_page_suffix(custom_page_positions[verse])
                    header_colors.append(None)
                elif slide['verse']:
                    if self.service_item.name == 'bibles':
                        # Bible slide tags are chapter/verse references, not song section letters.
                        row = str(slide['verse'])
                        header_colors.append(None)
                    else:
                        # These tags are already translated.
                        verse_def = slide['verse']
                        verse_def = '%s%s' % (verse_def[0], verse_def[1:])
                        row = verse_def
                        color = self._resolve_song_section_color(verse_def[0])
                        color.setAlphaF(self._resolve_opacity(self._resolve_verse_number(verse_def[1:])))
                        header_colors.append(color)
                else:
                    row += 1
                    header_colors.append(None)
                item.setText(slide['title'] if collection else slide['text'])
                if not collection and isinstance(slide.get('text_html'), str):
                    item.setData(SLIDE_TEXT_HTML_ROLE, slide['text_html'])
            else:
                label = QtWidgets.QLabel()
                label.setContentsMargins(4, 4, 4, 4)
                label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                if not self.service_item.is_media():
                    label.setScaledContents(True)
                if self.service_item.is_command():
                    if self.service_item.is_capable(ItemCapabilities.HasThumbnails):
                        pixmap = QtGui.QPixmap(str(slide['thumbnail']))
                    else:
                        if isinstance(slide['image'], QtGui.QIcon):
                            pixmap = slide['image'].pixmap(QtCore.QSize(32, 32))
                        else:
                            pixmap = QtGui.QPixmap(str(slide['image']))
                else:
                    pixmap = QtGui.QPixmap(str(slide['path']))
                if pixmap.height() > 0:
                    pixmap_ratio = pixmap.width() / pixmap.height()
                else:
                    pixmap_ratio = 1
                label.setPixmap(pixmap)
                container = QtWidgets.QWidget()
                layout = AspectRatioLayout(container, pixmap_ratio)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(label)
                container.setLayout(layout)
                slide_height = width // self.screen_ratio
                self.auto_row_height = max(self.viewport().height() / 4, 100)
                slide_height = min(slide_height, self.auto_row_height)
                self.setCellWidget(slide_index, 0, container)
                row += 1
                header_colors.append(None)
            text.append(str(row))
            self.setItem(slide_index, 0, item)
            if slide_height:
                # First set the height to 1 and then to the right height. This makes the item display correctly.
                # If this is not done, sometimes the image item is displayed as blank.
                self.setRowHeight(slide_index, 1)
                self.setRowHeight(slide_index, int(slide_height))
        self.setVerticalHeaderLabels(text)
        for row in range(self.rowCount()):
            header_item = self.verticalHeaderItem(row)
            if header_item:
                header_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._sync_vertical_header_width_from_labels(text)
        for row, color in enumerate(header_colors):
            if color is None:
                continue
            header_item = self.verticalHeaderItem(row)
            if header_item:
                header_item.setBackground(QtGui.QBrush(color))
        self.setColumnWidth(0, self.viewport().width())
        if self.service_item.is_text():
            self.resizeRowsToContents()
        self.change_slide(slide_number)

    def change_slide(self, slide):
        """
        Switches to the given row.
        """
        self.selectRow(slide)
        item = self.item(slide, 0)
        if item is not None:
            self.scrollToItem(item, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)

    def keyPressEvent(self, event):
        """
        Update the displayed Preview slide when keyboard navigation changes the selected row.
        """
        previous_row = self.currentRow()
        super().keyPressEvent(event)
        if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down) and self.currentRow() != previous_row:
            self.keyboard_slide_changed.emit()

    def current_slide_number(self):
        """
        Returns the position of the currently active item. Will return -1 if the widget is empty.
        """
        return super(ListPreviewWidget, self).currentRow()

    def slide_count(self):
        """
        Returns the number of slides this widget holds.
        """
        return super(ListPreviewWidget, self).rowCount()


class ListWidgetWithDnD(QtWidgets.QListWidget):
    """
    Provide a list widget to store objects and handle drag and drop events
    """
    def __init__(self, parent=None, name=''):
        """
        Initialise the list widget
        """
        super().__init__(parent)
        self.mime_data_text = name
        self.no_results_text = UiStrings().NoResults
        palette = self.palette()
        highlight = palette.color(QtGui.QPalette.ColorRole.Highlight).name()
        highlighted_text = palette.color(QtGui.QPalette.ColorRole.HighlightedText).name()
        inactive_highlight = QtGui.QColor(palette.color(QtGui.QPalette.ColorRole.Highlight))
        inactive_highlight.setAlpha(110)
        inactive_highlight_name = inactive_highlight.name(QtGui.QColor.NameFormat.HexArgb)
        self.setStyleSheet(
            'QListWidget { outline: 0; }'
            'QListWidget::item { padding: 4px 2px; border: 0; }'
            f'QListWidget::item:selected:active {{ background: {highlight}; color: {highlighted_text}; }}'
            f'QListWidget::item:selected:!active {{ background: {inactive_highlight_name}; color: palette(text); }}'
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(use_alternate_rows())
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._drag_start_pos = None

    def activateDnD(self):
        """
        Activate DnD of widget
        """
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        Registry().register_function(('%s_dnd' % self.mime_data_text), self.parent().handle_mime_data)

    def clear(self, search_while_typing=False):
        """
        Re-implement clear, so that we can customise feedback when using 'Search as you type'

        :param search_while_typing: True if we want to display the customised message
        :return: None
        """
        if search_while_typing:
            self.no_results_text = UiStrings().ShortResults
        else:
            self.no_results_text = UiStrings().NoResults
        super().clear()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Drag and drop event does not care what data is selected as the recipient will use events to request the data
        move just tell it what plugin to call
        """
        if event.buttons() != QtCore.Qt.MouseButton.LeftButton:
            event.ignore()
            return
        if not self.selectedItems():
            event.ignore()
            return
        if self._drag_start_pos is None or \
                (event.pos() - self._drag_start_pos).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            event.ignore()
            return
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        drag.setMimeData(mime_data)
        mime_data.setText(self.mime_data_text)
        selected = self.selectedItems()
        if selected:
            mime_data.setData('application/x-openlp-item-title',
                              selected[0].text().encode('utf-8'))
        drag.exec(QtCore.Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        """
        When something is dragged into this object, check if you should be able to drop it in here.
        """
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """
        Make an object droppable, and set it to copy the contents of the object, not move it.
        """
        if event.mimeData().hasUrls():
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """
        Receive drop event check if it is a file and process it if it is.

        :param event:  Handle of the event pint passed
        """
        if event.mimeData().hasUrls():
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            file_paths = handle_mime_data_urls(event.mimeData())
            Registry().execute('{mime_data}_dnd'.format(mime_data=self.mime_data_text),
                               {'file_paths': file_paths})
        else:
            event.ignore()

    def allItems(self):
        """
        An generator to list all the items in the widget

        :return: a generator
        """
        for row in range(self.count()):
            yield self.item(row)

    def paintEvent(self, event):
        """
        Re-implement paintEvent so that we can add 'No Results' text when the listWidget is empty.

        :param event: A QPaintEvent
        :return: None
        """
        super().paintEvent(event)
        if not self.count():
            viewport = self.viewport()
            painter = QtGui.QPainter(viewport)
            font = QtGui.QFont()
            font.setItalic(True)
            painter.setFont(font)
            padded_rect = QtCore.QRect(0, 0, viewport.width(), viewport.height()).adjusted(8, 8, -8, -8)
            painter.drawText(padded_rect,
                             (QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.TextFlag.TextWordWrap),
                             self.no_results_text)


class FileTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    """
    A QTreeWidgetItem that supports numeric sorting for file metadata columns
    (size, date). Call set_sort_data(column, raw_value) to store a numeric sort
    key alongside the display text; columns without a sort key fall back to the
    default string comparison.
    """
    _SORT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 100

    def set_sort_data(self, column: int, value) -> None:
        self.setData(column, FileTreeWidgetItem._SORT_ROLE, value)

    def __lt__(self, other):
        col = self.treeWidget().sortColumn() if self.treeWidget() else 0
        my_val = self.data(col, FileTreeWidgetItem._SORT_ROLE)
        other_val = other.data(col, FileTreeWidgetItem._SORT_ROLE)
        if my_val is not None and other_val is not None:
            return my_val < other_val
        # Fall back to plain string comparison — avoids PySide6 recursion via super().__lt__
        return self.text(col) < other.text(col)


class TreeWidgetDnDMixin:
    """
    Provide a tree widget to store objects and handle drag and drop events
    """
    first_column_min_ratio = 0.7

    def __init__(self, parent=None, name=''):
        """
        Initialise the tree widget
        """
        super().__init__(parent)
        self.mime_data_text = name
        self.allow_internal_dnd = False
        self._resizing_columns = False
        self.header().close()
        self.header().sectionResized.connect(self._on_section_resized)
        self.default_indentation = self.indentation()
        self._drag_start_pos = None
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        if name in ('presentations', 'images', 'media'):
            from openlp.core.widgets.fluent_tree import FluentLibraryTreeDelegate
            self._library_delegate = FluentLibraryTreeDelegate(self)
            self.setItemDelegate(self._library_delegate)
            self.setSelectionIndicatorVisible(True)

    def setup_columns(self, labels: list):
        """
        Enable a column header with the given labels. The first column stretches to fill available space;
        remaining columns resize to their content. Retain the standard Fluent body font.

        :param labels: List of column header strings, e.g. ['Name', 'Type', 'Size']
        """
        self.setColumnCount(len(labels))
        self.setHeaderLabels(labels)
        self.header().show()
        self.header().setStretchLastSection(False)
        for i in range(len(labels)):
            self.header().setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.Interactive)
        for i in range(1, len(labels)):
            self.header().resizeSection(i, 130)
        self._ensure_first_column_width()
        self.setSortingEnabled(True)
        self.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
        if self.mime_data_text in ('presentations', 'images', 'media'):
            # File libraries are a hierarchy, not a visible metadata table.
            # Keep metadata in the model for sorting, tooltips and plugins.
            for column in range(1, len(labels)):
                self.setColumnHidden(column, True)
            self.header().setStretchLastSection(True)
            self.setHeaderHidden(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._ensure_first_column_width()

    def _on_section_resized(self, section, old_size, new_size):
        """Keep the first column readable if interactive resizing makes it too small."""
        if old_size == new_size or self._resizing_columns:
            return
        self._ensure_first_column_width()

    def _ensure_first_column_width(self):
        """Keep the first column visible and proportional to the viewport width."""
        if self.header().isHidden() or self.columnCount() < 2 or self._resizing_columns:
            return
        available_width = self.viewport().width()
        if available_width <= 0:
            return
        minimum_width = int(available_width * self.first_column_min_ratio)
        # Keep metadata columns readable, but ensure the name column still tracks overall viewport changes.
        trailing_width = sum(self.columnWidth(i) for i in range(1, self.columnCount()))
        target_width = max(minimum_width, available_width - trailing_width)
        if self.columnWidth(0) == target_width:
            return
        self._resizing_columns = True
        try:
            self.header().resizeSection(0, target_width)
        finally:
            self._resizing_columns = False

    def activateDnD(self):
        """
        Activate DnD of widget
        """
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        Registry().register_function(('%s_dnd' % self.mime_data_text), self.parent().handle_mime_data)
        Registry().register_function(('%s_dnd_internal' % self.mime_data_text), self.parent().dnd_move_internal)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Drag and drop event does not care what data is selected as the recipient will use events to request the data
        move just tell it what plugin to call

        :param event: The event that occurred
        """
        if event.buttons() != QtCore.Qt.MouseButton.LeftButton:
            event.ignore()
            return
        if not self.selectedItems():
            event.ignore()
            return
        if self._drag_start_pos is None or \
                (event.pos() - self._drag_start_pos).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            event.ignore()
            return
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        drag.setMimeData(mime_data)
        mime_data.setText(self.mime_data_text)
        selected = self.selectedItems()
        if selected:
            mime_data.setData('application/x-openlp-item-title',
                              selected[0].text(0).encode('utf-8'))
        drag.exec(QtCore.Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        """
        Receive drag enter event, check if it is a file or internal object and allow it if it is.

        :param event:  The event that occurred
        """
        if event.mimeData().hasUrls():
            event.accept()
        elif self.allow_internal_dnd:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """
        Receive drag move event, check if it is a file or internal object and allow it if it is.

        :param event: The event that occurred
        """
        super().dragMoveEvent(event)
        if event.mimeData().hasUrls():
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        elif self.allow_internal_dnd:
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """
        Receive drop event, check if it is a file or internal object and process it if it is.

        :param event: Handle of the event pint passed
        """
        # If we are on Windows, OpenLP window will not be set on top. For example, user can drag images to Library and
        # the folder stays on top of the group creation box. This piece of code fixes this issue.
        if is_win():
            self.setWindowState(self.windowState() & ~QtCore.Qt.WindowState.WindowMinimized |
                                QtCore.Qt.WindowState.WindowActive)
            self.setWindowState(QtCore.Qt.WindowState.WindowNoState)
        if event.mimeData().hasUrls():
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            file_paths = handle_mime_data_urls(event.mimeData())
            Registry().execute('%s_dnd' % self.mime_data_text,
                               {'file_paths': file_paths, 'target': self.itemAt(event.pos())})
        elif self.allow_internal_dnd:
            event.setDropAction(QtCore.Qt.DropAction.CopyAction)
            event.accept()
            Registry().execute('%s_dnd_internal' % self.mime_data_text, self.itemAt(event.pos()))
        else:
            event.ignore()

    # Convenience methods for emulating a QListWidget. This helps keeping MediaManagerItem simple.
    def addItem(self, item):
        self.addTopLevelItem(item)

    def count(self):
        return self.topLevelItemCount()

    def item(self, index):
        return self.topLevelItem(index)


class TreeWidgetWithDnD(TreeWidgetDnDMixin, QtWidgets.QTreeWidget):
    """Folder hierarchy with the shared media drag-and-drop behaviour."""


class DataGridWithDnD(TreeWidgetDnDMixin, QtWidgets.QTreeDataGrid):
    """Flat media records with native Fluent DataGrid columns."""
