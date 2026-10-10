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
The :mod:`~openlp.core.widgets.edits` module contains all the customised edit widgets used in OpenLP
"""
import logging
import re
from pathlib import Path

from PySide6 import QtCore, QtGui
import fluentqt
from fluentqt import Spacing
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.toolbar import OpenLPToolbar

from openlp.core.common import CONTROL_CHARS
from openlp.core.common.i18n import UiStrings, translate
from openlp.core.common.path import path_to_str, str_to_path
from openlp.core.common.registry import Registry
from openlp.core.lib.formattingtags import FormattingTags
from openlp.core.lib.ui import create_action, create_widget_action
from openlp.core.ui.formattingtagform import FormattingTagForm
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets.dialogs import FileDialog
from openlp.core.widgets.enums import PathEditType


try:
    import enchant
    from enchant import DictNotFoundError
    from enchant.errors import Error
    ENCHANT_AVAILABLE = True
except ImportError:
    ENCHANT_AVAILABLE = False

log = logging.getLogger(__name__)


class SearchEdit(QtWidgets.QLineEdit):
    """
    A Fluent LineEdit with a search-type selector and native clearing.
    """
    searchTypeChanged = QtCore.Signal(int)

    def __init__(self, parent, settings_section):
        """
        Constructor.
        """
        super().__init__(parent)
        self.settings_section = settings_section
        self._current_search_type = -1
        self._search_button_gap = 4
        self.settings = Registry().get('settings')
        self.setAcceptDrops(False)

    def resizeEvent(self, event):
        """Keep the selector on the left, away from the native clear button."""
        super().resizeEvent(event)
        if hasattr(self, 'menu_button'):
            self._position_menu_button()

    def _position_menu_button(self):
        x = self._search_button_gap
        self.menu_button.move(x, (self.height() - self.menu_button.height()) // 2)

    def current_search_type(self):
        """
        Readonly property to return the current search type.
        """
        return self._current_search_type

    def set_current_search_type(self, identifier):
        """
        Set a new current search type.

        :param identifier: The search type identifier (int).
        """
        menu = self.menu_button.menu()
        for action in menu.actions():
            if identifier == action.data():
                self.setPlaceholderText(action.placeholder_text)
                self.menu_button.setDefaultAction(action)
                self._current_search_type = identifier
                self.settings.setValue('{section}/last used search type'.
                                       format(section=self.settings_section), identifier)
                self.searchTypeChanged.emit(identifier)
                return True

    def set_search_types(self, items):
        """
        A list of tuples to be used in the search type menu. The first item in the list will be preselected as the
        default.

         :param items:     The list of tuples to use. The tuples should contain an integer identifier, an icon (QIcon
             instance or string) and a title for the item in the menu. In short, they should look like this::

                    (<identifier>, <icon>, <title>, <place holder text>)

                For instance::

                    (1, <QIcon instance>, "Titles", "Search Song Titles...")

                Or::

                    (2, ":/songs/authors.png", "Authors", "Search Authors...")
        """
        menu = QtWidgets.QMenu(self)
        for identifier, icon, title, placeholder in items:
            action = create_widget_action(
                menu, text=title, icon=icon, data=identifier, triggers=self._on_menu_action_triggered)
            action.placeholder_text = placeholder
        if not hasattr(self, 'menu_button'):
            self.menu_button = QtWidgets.QToolButton(self)
            self.menu_button.setIcon(UiIcons().shortcuts)
            self.menu_button.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.menu_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            self.menu_button.setAutoRaise(True)
            self.menu_button.resize(40, self.menu_button.sizeHint().height())
            margins = self.contentMargins()
            margins.setLeft(margins.left() + self.menu_button.width() + self._search_button_gap)
            self.setContentMargins(margins)
        self.menu_button.setMenu(menu)
        self.set_current_search_type(
            self.settings.value('{section}/last used search type'.format(section=self.settings_section)))
        self.menu_button.show()
        self._position_menu_button()

    def _on_menu_action_triggered(self):
        """
        Internally implemented slot to react to the select of one of the search types in the menu. Once it has set the
        correct action on the button, and set the current search type (using the list of identifiers provided by the
        developer), the ``searchTypeChanged(int)`` signal is emitted with the identifier.
        """
        for action in self.menu_button.menu().actions():
            # Why is this needed?
            action.setChecked(False)
        self.set_current_search_type(self.sender().data())


class PathEdit(QtWidgets.QWidget):
    """
    The :class:`~openlp.core.widgets.edits.PathEdit` class subclasses QWidget to create a custom widget for use when
    a file or directory needs to be selected.
    """
    pathChanged = QtCore.Signal(Path)

    def __init__(self, parent=None, path_type=PathEditType.Files, default_path=None, dialog_caption=None,
                 show_revert=True):
        """
        Initialise the PathEdit widget

        :param QtWidget.QWidget | None: The parent of the widget. This is just passed to the super method.
        :param str dialog_caption: Used to customise the caption in the QFileDialog.
        :param Path default_path: The default path. This is set as the path when the revert
            button is clicked
        :param bool show_revert: Used to determine if the 'revert button' should be visible.
        :rtype: None
        """
        super().__init__(parent)
        self.default_path = default_path
        self.dialog_caption = dialog_caption
        self._path_type = path_type
        self._path = None
        self.filters = '{all_files} (*)'.format(all_files=UiStrings().AllFiles)
        self._setup(show_revert)

    def _setup(self, show_revert):
        """
        Set up the widget
        :param bool show_revert: Show or hide the revert button
        :rtype: None
        """
        widget_layout = QtWidgets.QHBoxLayout()
        widget_layout.setContentsMargins(0, 0, 0, 0)
        self.line_edit = QtWidgets.QLineEdit(self)
        widget_layout.addWidget(self.line_edit)
        self.browse_button = QtWidgets.QToolButton(self)
        self.browse_button.setIcon(UiIcons().open)
        self.line_edit.setMinimumHeight(self.browse_button.sizeHint().height())
        widget_layout.addWidget(self.browse_button)
        self.revert_button = QtWidgets.QToolButton(self)
        self.revert_button.setIcon(UiIcons().undo)
        self.revert_button.setVisible(show_revert)
        widget_layout.addWidget(self.revert_button)
        self.setLayout(widget_layout)
        # Signals and Slots
        self.browse_button.clicked.connect(self.on_browse_button_clicked)
        self.revert_button.clicked.connect(self.on_revert_button_clicked)
        self.line_edit.editingFinished.connect(self.on_line_edit_editing_finished)
        self.update_button_tool_tips()

    @QtCore.Property(Path)
    def path(self):
        """
        A property getter method to return the selected path.

        :return: The selected path
        :rtype: Path
        """
        return self._path

    @path.setter
    def path(self, path):
        """
        A Property setter method to set the selected path

        :param Path path: The path to set the widget to
        :rtype: None
        """
        if path:
            self._path = Path(path)
            text = path_to_str(self._path)
            self.line_edit.setText(text)
            self.line_edit.setToolTip(text)

    @QtCore.Property(PathEditType)
    def path_type(self):
        """
        A property getter method to return the path_type. Path type allows you to sepecify if the user is restricted to
        selecting a file or directory.

        :return: The type selected
        :rtype: PathType
        """
        return self._path_type

    @path_type.setter
    def path_type(self, path_type):
        """
        A Property setter method to set the path type

        :param PathType path_type: The type of path to select
        :rtype: None
        """
        self._path_type = path_type
        self.update_button_tool_tips()

    def update_button_tool_tips(self):
        """
        Called to update the tooltips on the buttons. This is changing path types, and when the widget is initalised

        :rtype: None
        """
        if self._path_type == PathEditType.Directories:
            self.browse_button.setToolTip(translate('OpenLP.PathEdit', 'Browse for directory.'))
            self.revert_button.setToolTip(translate('OpenLP.PathEdit', 'Revert to default directory.'))
        else:
            self.browse_button.setToolTip(translate('OpenLP.PathEdit', 'Browse for file.'))
            self.revert_button.setToolTip(translate('OpenLP.PathEdit', 'Revert to default file.'))

    def on_browse_button_clicked(self):
        """
        A handler to handle a click on the browse button.

        Show the QFileDialog and process the input from the user

        :rtype: None
        """
        caption = self.dialog_caption
        path = None
        if self._path_type == PathEditType.Directories:
            if not caption:
                caption = translate('OpenLP.PathEdit', 'Select Directory')
            path = FileDialog.getExistingDirectory(self, caption, self._path, FileDialog.Option.ShowDirsOnly)
        elif self._path_type == PathEditType.Files:
            if not caption:
                caption = self.dialog_caption = translate('OpenLP.PathEdit', 'Select File')
            path, filter_used = FileDialog.getOpenFileName(self, caption, self._path, self.filters)
        if path:
            self.on_new_path(path)

    def on_revert_button_clicked(self):
        """
        A handler to handle a click on the revert button.

        Set the new path to the value of the default_path instance variable.

        :rtype: None
        """
        self.on_new_path(self.default_path)

    def on_line_edit_editing_finished(self):
        """
        A handler to handle when the line edit has finished being edited.

        :rtype: None
        """
        path = str_to_path(self.line_edit.text())
        self.on_new_path(path)

    def on_new_path(self, path):
        """
        A method called to validate and set a new path.

        Emits the pathChanged Signal

        :param Path path: The new path
        :rtype: None
        """
        if path and self._path != path:
            self.path = path
            self.pathChanged.emit(path)


class FormattingTagDelegate(QtWidgets.QStyledItemDelegate):
    """
    Item delegate that renders formatting tag syntax visually using HTML,
    suitable for read-only list/table views that display lyrics or slides.
    """

    HORIZONTAL_PADDING = 2 * Spacing.Small
    VERTICAL_PADDING = Spacing.Small

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme_host = fluentqt.FluentWidget(parent)
        self._theme_host.hide()

    def _paint_separator(self, painter, option, index):
        """Separate neighbouring slides across the full text column."""
        if index.row() >= index.model().rowCount(index.parent()) - 1:
            return
        painter.save()
        painter.setPen(QtGui.QPen(self._theme_host.theme_tokens().colors.strokeDivider, 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()

    @staticmethod
    def _tags_to_html(text):
        """
        Convert formatting tag tokens in *text* to HTML for styled display.
        HTML special characters in the source text are escaped first so that
        ampersands and angle brackets in lyrics are not mis-interpreted.
        """
        tags = FormattingTags.get_html_tags()
        known_tokens = {tag[key] for tag in tags for key in ('start tag', 'end tag')}
        # Unregistered tags still belong in the stored source, but read-only
        # previews must show their content without leaking the marker syntax.
        text = re.sub(r'\{/?[^{}\s]+\}',
                      lambda match: match.group(0) if match.group(0) in known_tokens else '', text)
        html = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        for tag in tags:
            start_html = tag['start html'].replace('-webkit-text-fill-color', 'color')
            end_html = tag['end html']
            html = html.replace(tag['start tag'], start_html)
            html = html.replace(tag['end tag'], end_html)
        return html

    @classmethod
    def _segments(cls, text):
        """
        Split *text* into ``(kind, payload)`` segments where *kind* is
        ``'text'`` or ``'marker'`` (e.g. ``[---]``).
        """
        segments = []
        buffer = []

        def flush_buffer():
            if buffer:
                segments.append(('text', '\n'.join(buffer)))
                buffer.clear()

        for line in text.split('\n'):
            if SpellTextEdit.split_marker_style_for_text(line) is not None:
                flush_buffer()
                segments.append(('marker', line.strip()))
            else:
                buffer.append(line)
        flush_buffer()
        return segments

    @classmethod
    def _build_text_document(cls, font, text_run, available_width):
        """
        Build a QTextDocument for a non-marker text segment.
        """
        doc = QtGui.QTextDocument()
        doc.setDefaultFont(font)
        doc.setDocumentMargin(0)
        doc.setHtml(cls._tags_to_html(text_run).replace('\n', '<br>'))
        if available_width > 0:
            doc.setTextWidth(available_width)
        return doc

    @classmethod
    def _marker_line_height(cls, font):
        """
        Return the vertical space reserved for a split marker line.
        """
        return QtGui.QFontMetrics(font).height()

    def _paint_marker(self, painter, marker_text, y_top, rect, base_color):
        """
        Draw a horizontal rule for *marker_text* centred within its reserved row.
        """
        pen_style = SpellTextEdit.split_marker_style_for_text(marker_text)
        if not pen_style:
            return
        color = QtGui.QColor(base_color)
        if marker_text == '[---]':
            color.setAlphaF(0.5)
        pen = QtGui.QPen(color, SpellTextEdit.split_marker_width_for_text(marker_text), pen_style)
        painter.save()
        painter.setPen(pen)
        y = int(y_top + self._marker_line_height(painter.font()) / 2)
        painter.drawLine(rect.left(), y, rect.right(), y)
        painter.restore()

    def paint(self, painter, option, index):
        text = index.data(QtCore.Qt.ItemDataRole.DisplayRole)
        if text is None or text == '':
            super().paint(painter, option, index)
            self._paint_separator(painter, option, index)
            return
        painter.save()
        style = option.widget.style() if option.widget else QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)

        available_width = max(0, option.rect.width() - 2 * self.HORIZONTAL_PADDING)
        x = option.rect.left() + self.HORIZONTAL_PADDING
        y = option.rect.top() + self.VERTICAL_PADDING
        base_color = option.palette.color(QtGui.QPalette.ColorRole.Text)
        font = option.font
        marker_height = self._marker_line_height(font)

        for kind, payload in self._segments(text):
            if kind == 'marker':
                marker_rect = QtCore.QRect(x, y, available_width, marker_height)
                self._paint_marker(painter, payload, y, marker_rect, base_color)
                y += marker_height
            else:
                doc = self._build_text_document(font, payload, available_width)
                painter.save()
                painter.translate(x, y)
                doc.drawContents(painter, QtCore.QRectF(0, 0, available_width, doc.size().height()))
                painter.restore()
                y += int(doc.size().height())
        painter.restore()
        self._paint_separator(painter, option, index)

    def sizeHint(self, option, index):
        text = index.data(QtCore.Qt.ItemDataRole.DisplayRole)
        if text is None or text == '':
            return super().sizeHint(option, index)
        width = option.rect.width()
        # QTableView asks for row hints with an empty rect. Measure using the
        # visible column, otherwise lyrics wrap to a narrow fallback width and
        # leave oversized rows when painted across the full editor.
        view = self.parent()
        if width <= 0 and isinstance(view, QtWidgets.QTableView):
            width = view.columnWidth(index.column())
        if width <= 0:
            width = 200
        available_width = max(0, width - 2 * self.HORIZONTAL_PADDING)
        font = option.font
        marker_height = self._marker_line_height(font)

        total_height = 0
        ideal_width = 0
        for kind, payload in self._segments(text):
            if kind == 'marker':
                total_height += marker_height
            else:
                doc = self._build_text_document(font, payload, available_width)
                total_height += int(doc.size().height())
                ideal_width = max(ideal_width, int(doc.idealWidth()))
        return QtCore.QSize(ideal_width + 2 * self.HORIZONTAL_PADDING, total_height + 2 * self.VERTICAL_PADDING)


class FormattingToolbar(OpenLPToolbar):
    """Extend the native CommandBar surface behind its adjacent input controls."""
    def __init__(self, parent):
        super().__init__(parent)
        self._theme_host = fluentqt.FluentWidget(self)
        self.background_role = 'bgCanvas'
        self._theme_host.hide()
        self.layout().setContentsMargins(0, 0, 12, 0)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), getattr(self._theme_host.theme_tokens().colors, self.background_role))


class FormattingStyleComboBox(QtWidgets.QComboBox):
    """A single-choice Fluent style picker with readable format previews."""
    popupOpened = QtCore.Signal()

    def showPopup(self):
        super().showPopup()
        self.popupOpened.emit()


class FormattingStyleDelegate(QtWidgets.QStyledItemDelegate):
    """Show a style's font and colour without the multi-selection checkboxes."""
    def __init__(self, combo, parent):
        super().__init__(parent)
        self.combo = combo
        self._theme_host = fluentqt.FluentWidget(parent)
        self._theme_host.hide()

    @staticmethod
    def contrast_ratio(first, second):
        def luminance(colour):
            channels = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                        for value in (colour.redF(), colour.greenF(), colour.blueF())]
            return sum(value * weight for value, weight in zip(channels, (0.2126, 0.7152, 0.0722)))
        light, dark = sorted((luminance(first), luminance(second)), reverse=True)
        return (light + 0.05) / (dark + 0.05)

    @classmethod
    def preview_background(cls, foreground, background):
        if cls.contrast_ratio(foreground, background) >= 4:
            return None
        return max((QtGui.QColor('#202020'), QtGui.QColor('#ffffff')),
                   key=lambda colour: cls.contrast_ratio(foreground, colour))

    def paint(self, painter, option, index):
        """Keep the preview's own text colour when the row is selected."""
        styled = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        style = styled.widget.style() if styled.widget else QtWidgets.QApplication.style()
        painter.save()
        style.drawPrimitive(QtWidgets.QStyle.PrimitiveElement.PE_PanelItemViewItem, styled, painter, styled.widget)
        text_rect = styled.rect.adjusted(16, 0, -12, 0)
        foreground = index.data(QtCore.Qt.ItemDataRole.ForegroundRole)
        colour = foreground.color() if foreground is not None else styled.palette.color(QtGui.QPalette.ColorRole.Text)
        painter.setFont(styled.font)
        text = QtGui.QFontMetrics(styled.font).elidedText(
            styled.text, QtCore.Qt.TextElideMode.ElideRight, max(0, text_rect.width()))
        background = self.preview_background(colour, self._theme_host.theme_tokens().colors.bgLayerOverlay)
        if background is not None:
            metrics = QtGui.QFontMetrics(styled.font)
            patch = QtCore.QRectF(text_rect.left() - 4, text_rect.center().y() - metrics.height() / 2 - 2,
                                  min(text_rect.width(), metrics.horizontalAdvance(text)) + 8, metrics.height() + 4)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(patch, 3, 3)
        painter.setPen(colour)
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft, text)
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QtCore.QSize(size.width() + 28, max(36, size.height() + 8))


class SpellTextEdit(QtWidgets.QWidget):
    """
    Fluent TextEdit with OpenLP's tagged-source formatting and spell checking.

    Based on code from http://john.nachtimwald.com/2009/08/22/qplaintextedit-with-in-line-spell-check
    """
    TEXT_INSET = 10
    BOTTOM_PADDING = Spacing.Small
    LABEL_PADDING = Spacing.Small // 2
    LABEL_MARGIN = Spacing.Small
    SECTION_BOUNDARY_LINE_REGEX = re.compile(
        r'(?m)^\s*(?:\[(?:---|===|--}\{--)\]|---\[(?:.+?)(?::.*)?\]---)\s*$')

    def __init__(self, parent=None, formatting_tags_allowed=True, visual_mode_only=False):
        """
        Constructor.
        """
        global ENCHANT_AVAILABLE
        super(SpellTextEdit, self).__init__(parent)
        self._toolbar = None
        self._input = fluentqt.TextEdit(self, contentMargins=QtCore.QMargins(0, 0, 0, 0))
        self._editor = self._input.findChild(QtWidgets.QTextEdit)
        # Fluent's automatic line-height pass would overwrite section spacing
        # and create extra undo commands. This adapter owns those block formats
        # and sizes the control to the resizable editor area instead.
        self._editor.textChanged.disconnect()
        QtCore.QObject.disconnect(
            self._editor.document().documentLayout(),
            QtCore.SIGNAL('documentSizeChanged(QSizeF)'), self._input, None)
        self._editor.textChanged.connect(self._input.update)
        self._viewport = self._editor.viewport()
        self._editor.setAcceptRichText(False)
        self._editor.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._editor.installEventFilter(self)
        self._editor.viewport().installEventFilter(self)
        self._input.installEventFilter(self)
        self._input.verticalScrollBar().installEventFilter(self)
        self._input.setMinimumHeight(0)
        self._input.setMaximumHeight(16777215)
        self._editor.verticalScrollBar().rangeChanged.connect(self._sync_vertical_scrollbar)
        self.setFocusProxy(self._editor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.formatting_tags_allowed = formatting_tags_allowed
        self.visual_mode_only = visual_mode_only
        self.rich_text_mode = formatting_tags_allowed
        self._visual_line_overrides = {}
        self._updating_block_formats = False
        self.document().setDocumentMargin(0)
        self._refresh_block_formats()
        self.document().clearUndoRedoStacks()
        self.highlighter = Highlighter(self.document(), formatting_tags_allowed=self.formatting_tags_allowed)
        self.highlighter.set_rich_text_mode(self.rich_text_mode)
        self._mode_switch = None
        self._tag_actions = {}       # maps start tag token → QAction for toolbar state tracking
        self._color_tags = []
        self._updating_custom_formatting = False
        self._color_action_ends = {}  # maps start_tag → end_tag for color toggle logic
        self._formatting_tag_form = None
        if self.formatting_tags_allowed:
            self._setup_formatting_toolbar()
        self._refresh_block_formats()
        self.document().clearUndoRedoStacks()
        self.textChanged.connect(self._refresh_block_formats)
        # Default dictionary based on the current locale.
        if ENCHANT_AVAILABLE:
            try:
                self.dictionary = enchant.Dict()
                self.highlighter.spelling_dictionary = self.dictionary
            except (Error, DictNotFoundError):
                ENCHANT_AVAILABLE = False
                log.debug('Could not load default dictionary')

    def __getattr__(self, name):
        editor = self.__dict__.get('_editor')
        if editor is not None:
            return getattr(editor, name)
        raise AttributeError(name)

    def sizeHint(self):
        return QtCore.QSize(600, 320)

    def minimumSizeHint(self):
        return QtCore.QSize(200, 120)

    def viewportMargins(self):
        return QtCore.QMargins(0, self._toolbar.sizeHint().height() + 2 if self._toolbar else 0, 0, 0)

    def frameWidth(self):
        return 1

    def verticalScrollBar(self):
        return self._input.verticalScrollBar()

    def _sync_vertical_scrollbar(self, *args):
        native = self._editor.verticalScrollBar()
        scrollbar = self._input.verticalScrollBar()
        scrollbar.setRange(native.minimum(), native.maximum())
        scrollbar.setPageStep(native.pageStep())
        scrollbar.setValue(native.value())
        scrollbar.setVisible(native.maximum() > native.minimum())
        if scrollbar.isVisible():
            scrollbar.setOpacity(1.0)

    def setPlainText(self, text):
        self._editor.setPlainText(text)
        self._refresh_block_formats()
        self.document().clearUndoRedoStacks()

    def blockBoundingRect(self, block):
        if self.document().textWidth() <= 0:
            self.document().setTextWidth(max(1, self._editor.viewport().width()))
        self.document().documentLayout().documentSize()
        rect = self.document().documentLayout().blockBoundingRect(block)
        if block.blockFormat().lineHeightType() == QtGui.QTextBlockFormat.LineHeightTypes.FixedHeight.value:
            rect.setHeight(max(rect.height(), block.blockFormat().lineHeight()))
        rect.setHeight(rect.height() + block.blockFormat().topMargin() + block.blockFormat().bottomMargin())
        return rect

    def _refresh_block_formats(self):
        """Keep presentation formatting in the same undo step as the source edit."""
        if self._updating_block_formats:
            return
        self._updating_block_formats = True
        document = self.document()
        cursor = QtGui.QTextCursor(document)
        cursor.joinPreviousEditBlock()
        block = document.begin()
        try:
            while block.isValid():
                fmt = block.blockFormat()
                desired = QtGui.QTextBlockFormat(fmt)
                desired.setLeftMargin(self.TEXT_INSET)
                desired.setRightMargin(self.TEXT_INSET)
                # Section spacing is presentation shared by visual and source
                # modes, so switching modes never changes the undo history.
                label = bool(re.fullmatch(r'\s*---\[.+?\]---\s*', block.text()))
                desired.setNonBreakableLines(label)
                desired.setTopMargin(self.LABEL_MARGIN if label and block.blockNumber() else 0)
                desired.setBottomMargin(0)
                if label:
                    desired.setLineHeight(self._editor.fontMetrics().lineSpacing() + 2 * self.LABEL_PADDING,
                                          QtGui.QTextBlockFormat.LineHeightTypes.FixedHeight.value)
                else:
                    desired.setLineHeight(100, QtGui.QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                if fmt != desired:
                    cursor.setPosition(block.position())
                    cursor.setBlockFormat(desired)
                block = block.next()
        finally:
            cursor.endEditBlock()
            self._updating_block_formats = False

    def keyPressEvent(self, event):
        if getattr(self, '_forwarding_key_event', False):
            return super().keyPressEvent(event)
        self._forwarding_key_event = True
        try:
            QtWidgets.QApplication.sendEvent(self._editor, event)
        finally:
            self._forwarding_key_event = False

    def paste(self):
        self.insertFromMimeData(QtWidgets.QApplication.clipboard().mimeData())

    def createStandardContextMenu(self):
        menu = self._editor.createStandardContextMenu()
        for action in menu.actions():
            if action.objectName() == 'edit-paste':
                action.triggered.disconnect()
                action.triggered.connect(self.paste)
        return menu

    def eventFilter(self, watched, event):
        if watched == self._input.verticalScrollBar() and event.type() == QtCore.QEvent.Type.Paint:
            # Fluent fades its rail after scrolling or leaving the field. It has
            # no persistent-visibility setting, so keep the overflowing rail
            # opaque and stop its fade animation before it is painted.
            for animation in watched.findChildren(QtCore.QPropertyAnimation):
                if animation.targetObject() == watched and animation.propertyName() == b'opacity':
                    animation.stop()
            if watched.opacity() != 1.0:
                watched.setOpacity(1.0)
        if watched == self._editor and event.type() == QtCore.QEvent.Type.Resize:
            QtWidgets.QTextEdit.resizeEvent(self._editor, event)
            self._editor.setViewportMargins(0, 0, 0, 0)
            return True
        if watched == self._editor and event.type() == QtCore.QEvent.Type.Show:
            QtWidgets.QTextEdit.showEvent(self._editor, event)
            self._editor.setViewportMargins(0, 0, 0, 0)
            return True
        if watched == self._input and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show):
            # The surrounding dialog supplies the height, rather than Fluent's
            # automatic line-count sizing. Keep its editor and native rail.
            self._layout_text_input()
            if self._input.maximumHeight() != 16777215:
                # Theme refreshes reapply Fluent's fixed line-count height.
                # Restore the container geometry after that refresh finishes.
                QtCore.QTimer.singleShot(0, self._position_formatting_toolbar)
            return True
        if watched == self._viewport and event.type() == QtCore.QEvent.Type.Paint:
            QtWidgets.QTextEdit.paintEvent(self._editor, event)
            self._paint_visual_markers(event)
            return True
        if watched == self._editor and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.matches(QtGui.QKeySequence.StandardKey.Paste):
                self.insertFromMimeData(QtWidgets.QApplication.clipboard().mimeData())
                return True
            for key, tag in ((QtGui.QKeySequence.StandardKey.Bold, 'st'),
                             (QtGui.QKeySequence.StandardKey.Italic, 'it'),
                             (QtGui.QKeySequence.StandardKey.Underline, 'u')):
                if event.matches(key):
                    if self.formatting_tags_allowed:
                        self._apply_formatting_by_tag(tag)
                    return True
        if watched == self._viewport and event.type() == QtCore.QEvent.Type.ContextMenu:
            self.contextMenuEvent(event)
            return True
        return super().eventFilter(watched, event)

    @staticmethod
    def split_marker_style_for_text(text):
        """
        Return the pen style that should be used for a split marker line.
        """
        text = text.strip()
        if text == '[---]':
            return QtCore.Qt.PenStyle.DotLine
        if text == '[--}{--]' or text == '[===]':
            return QtCore.Qt.PenStyle.SolidLine
        return None

    @staticmethod
    def split_marker_width_for_text(text):
        """
        Return the pen width that should be used for a split marker line.
        """
        return 2.5 if text.strip() == '[===]' else 1.0

    def _setup_formatting_toolbar(self):
        """
        Create a lightweight formatting toolbar docked at the top of the editor.
        """
        self._toolbar = FormattingToolbar(self)
        self._toolbar.setIconSize(QtCore.QSize(20, 20))
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)
        self._toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._undo_action = self._toolbar.addAction(translate('OpenLP.SpellTextEdit', 'Undo'))
        self._undo_action.setIcon(UiIcons().undo)
        self._undo_action.setToolTip(translate('OpenLP.SpellTextEdit', 'Undo last edit.'))
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self.undo)

        self._redo_action = self._toolbar.addAction(translate('OpenLP.SpellTextEdit', 'Redo'))
        self._redo_action.setIcon(UiIcons().redo)
        self._redo_action.setToolTip(translate('OpenLP.SpellTextEdit', 'Redo last undone edit.'))
        self._redo_action.setEnabled(False)
        self._redo_action.triggered.connect(self.redo)

        self.undoAvailable.connect(lambda available: self._undo_action.setEnabled(available))
        self.redoAvailable.connect(lambda available: self._redo_action.setEnabled(available))

        button_definitions = [
            ('', 'st', translate('OpenLP.SpellTextEdit', 'Bold'),
             UiIcons().bold, True),
            ('', 'it', translate('OpenLP.SpellTextEdit', 'Italic'),
             UiIcons().italic, True),
            ('', 'u', translate('OpenLP.SpellTextEdit', 'Underline'),
             UiIcons().underline, True),
            ('', 'sb', translate('OpenLP.SpellTextEdit', 'Subscript'), UiIcons().subscript, True),
            ('', 'su', translate('OpenLP.SpellTextEdit', 'Superscript'), UiIcons().superscript, True),
            ('', 'uc', translate('OpenLP.SpellTextEdit', 'Uppercase'),
             UiIcons().uppercase, True)
        ]
        for caption, tag, tooltip, icon, icon_only in button_definitions:
            action = self._toolbar.addAction(caption or tooltip)
            if icon:
                action.setIcon(icon)
            action.setToolTip(tooltip)
            action.setCheckable(True)
            self._tag_actions[tag] = action
            action.triggered.connect(lambda checked=False, start_tag=tag: self._apply_formatting_by_tag(start_tag))

        self._toolbar.addSeparator()
        remove_action = self._toolbar.addAction(translate('OpenLP.SpellTextEdit', 'Clear formatting'))
        remove_action.setIcon(UiIcons().clear_formatting)
        remove_action.setToolTip(translate('OpenLP.SpellTextEdit', 'Clear formatting'))
        remove_action.triggered.connect(self.remove_formatting)

        remove_unused_action = self._toolbar.addAction(
            translate('OpenLP.SpellTextEdit', 'Remove invalid formatting tags'))
        remove_unused_action.setIcon(UiIcons().remove_formatting)
        remove_unused_action.setToolTip(translate('OpenLP.SpellTextEdit', 'Remove invalid formatting tags'))
        remove_unused_action.triggered.connect(self.remove_unused_tags)

        edit_tags_action = self._toolbar.addAction(translate('OpenLP.SpellTextEdit', 'Edit formatting styles'))
        edit_tags_action.setIcon(UiIcons().palette)
        edit_tags_action.triggered.connect(self._edit_formatting_tags)
        self._edit_tags_action = edit_tags_action

        # Keep every action in one native CommandBar. Custom inputs sit alongside it.
        self._formatting_command_bar = self._toolbar.findChild(fluentqt.CommandBar)
        self._formatting_command_bar.setBackgroundVisible(True)
        self._formatting_command_bar.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                                   QtWidgets.QSizePolicy.Policy.Fixed)
        self._toolbar.layout().setStretch(self._toolbar.layout().indexOf(self._formatting_command_bar), 1)

        self._custom_formatting_combo = FormattingStyleComboBox(self._toolbar)
        self._custom_formatting_combo.setPlaceholderText(translate('OpenLP.SpellTextEdit', 'Styles'))
        self._custom_formatting_combo.setToolTip(translate('OpenLP.SpellTextEdit', 'Styles'))
        self._custom_formatting_combo.setAccessibleName(translate('OpenLP.SpellTextEdit', 'Styles'))
        self._custom_formatting_combo.setMaxVisibleItems(10)
        self._custom_formatting_combo.setFixedWidth(190)
        self._color_model = QtGui.QStandardItemModel(self._custom_formatting_combo)
        self._custom_formatting_combo.setModel(self._color_model)
        self._custom_formatting_combo.popupOpened.connect(self._install_formatting_preview_delegate)
        self._populate_color_menu()
        self._custom_formatting_combo.activated.connect(self._on_custom_formatting_changed)
        self._toolbar.addWidget(self._custom_formatting_combo)

        self._mode_switch = fluentqt.ToggleSwitch(self._toolbar)
        self._mode_switch.setObjectName('source_switch')
        self._mode_switch.toggled.connect(lambda checked: self.set_rich_text_mode(not checked))
        source_container = QtWidgets.QWidget(self._toolbar)
        source_layout = QtWidgets.QHBoxLayout(source_container)
        source_layout.setContentsMargins(12, 0, 0, 0)
        source_layout.addWidget(self._mode_switch)
        source_container.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self._toolbar.addWidget(source_container)
        self._toolbar.layout().setStretch(self._toolbar.layout().count() - 1, 0)
        self._update_mode_switch()

        self._position_formatting_toolbar()
        self.cursorPositionChanged.connect(self._update_toolbar_state)

    def _update_mode_switch(self):
        """
        Synchronise the Source switch with the current editing mode.
        """
        if not self._mode_switch:
            return
        caption = translate('OpenLP.SpellTextEdit', 'Source')
        self._mode_switch.setOnContent(caption)
        self._mode_switch.setOffContent(caption)
        self._mode_switch.setAccessibleName(caption)
        blocker = QtCore.QSignalBlocker(self._mode_switch)
        self._mode_switch.setIsOn(not self.rich_text_mode)
        del blocker
        self._mode_switch.setToolTip(translate('OpenLP.SpellTextEdit', 'Show formatting tags in the source text'))

    def _populate_color_menu(self):
        """Populate named style previews; tag tokens remain internal model data."""
        blocker = QtCore.QSignalBlocker(self._custom_formatting_combo)
        self._color_model.clear()
        self._color_tags.clear()
        self._color_action_ends.clear()
        self._color_model.appendRow(QtGui.QStandardItem(translate('OpenLP.SpellTextEdit', 'None')))
        try:
            html_tags = FormattingTags.get_html_tags()
        except Exception:
            html_tags = []
        for html in html_tags:
            start_tag = html.get('start tag')
            end_tag = html.get('end tag')
            start_html = html.get('start html', '')
            if not start_tag or not end_tag:
                continue
            has_colour = re.search(r'(?:-webkit-text-fill-color|color)\s*:', start_html, flags=re.IGNORECASE)
            if not has_colour and html.get('protected', True):
                continue
            desc = html.get('desc', start_tag)
            item = QtGui.QStandardItem(desc)
            item.setData(start_tag, QtCore.Qt.ItemDataRole.UserRole)
            item.setToolTip(desc)
            preview_format = self.highlighter._format_from_start_html(start_html)
            item.setFont(preview_format.font().resolve(self.font()))
            if preview_format.foreground().style() != QtCore.Qt.BrushStyle.NoBrush:
                item.setForeground(preview_format.foreground())
            self._color_model.appendRow(item)
            self._color_tags.append(start_tag)
            self._color_action_ends[start_tag] = end_tag
        del blocker

    def _install_formatting_preview_delegate(self):
        for view in self.window().findChildren(QtWidgets.QAbstractItemView, 'ComboBoxPopupListView'):
            if view.model() is self._color_model:
                if not isinstance(view.itemDelegate(), FormattingStyleDelegate):
                    view.setItemDelegate(FormattingStyleDelegate(self._custom_formatting_combo, view))
                view.viewport().update()
                break

    def _on_custom_formatting_changed(self, row):
        """Replace the selected text's named style in one undoable action."""
        if self._updating_custom_formatting:
            return
        start_tag = self._color_tags[row - 1] if row > 0 else None
        self._updating_custom_formatting = True
        cursor = self.textCursor()
        selected = cursor.hasSelection()
        original_position = cursor.position()
        if not selected:
            cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
            self.setTextCursor(cursor)
        offset = original_position - cursor.selectionStart()
        cursor.beginEditBlock()
        try:
            self._replace_custom_style(start_tag)
            self._balance_formatting_tags()
        finally:
            cursor.endEditBlock()
            self._updating_custom_formatting = False
        if not selected and self.textCursor().hasSelection():
            result = self.textCursor()
            result.setPosition(min(result.selectionEnd(), result.selectionStart() + max(0, offset)))
            self.setTextCursor(result)
        self._update_toolbar_state()
        self.setFocus()

    def _balance_formatting_tags(self):
        """Keep emphasis spanning a style boundary valid when converted to HTML."""
        pairs = {tag['start tag']: tag['end tag'] for tag in FormattingTags.get_html_tags()
                 if tag.get('start tag') and tag.get('end tag')}
        if not pairs:
            return
        ends = {end: start for start, end in pairs.items()}
        tokens = sorted(set(pairs) | set(ends), key=len, reverse=True)
        pattern = re.compile('|'.join(re.escape(token) for token in tokens))
        stack, changes = [], []
        for match in pattern.finditer(self.toPlainText()):
            token = match.group()
            if token in pairs:
                stack.append(token)
            elif ends[token] in stack:
                position = len(stack) - 1 - stack[::-1].index(ends[token])
                nested = stack[position + 1:]
                if nested:
                    replacement = ''.join(pairs[start] for start in reversed(nested)) + token + ''.join(nested)
                    changes.append((match.start(), match.end(), replacement))
                del stack[position]
        cursor = self.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        for left, right, replacement in reversed(changes):
            delta = len(replacement) - (right - left)
            if start >= right:
                start += delta
            if end >= right:
                end += delta
            edit = QtGui.QTextCursor(self.document())
            edit.setPosition(left)
            edit.setPosition(right, QtGui.QTextCursor.MoveMode.KeepAnchor)
            edit.insertText(replacement)
        cursor.setPosition(start)
        cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    def _replace_custom_style(self, start_tag):
        """Keep named styles exclusive without formatting section markers."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            ranges = self._selection_section_ranges(self.toPlainText(), start, end)
            if not ranges:
                return
            if ranges != [(start, end)]:
                delta = 0
                selections = []
                for section_start, section_end in ranges:
                    section_cursor = QtGui.QTextCursor(self.document())
                    section_cursor.setPosition(section_start + delta)
                    section_cursor.setPosition(section_end + delta, QtGui.QTextCursor.MoveMode.KeepAnchor)
                    self.setTextCursor(section_cursor)
                    previous_length = len(self.toPlainText())
                    self._replace_custom_style(start_tag)
                    delta += len(self.toPlainText()) - previous_length
                    result = self.textCursor()
                    selections.append((result.selectionStart(), result.selectionEnd()))
                cursor = self.textCursor()
                cursor.setPosition(selections[0][0])
                cursor.setPosition(selections[-1][1], QtGui.QTextCursor.MoveMode.KeepAnchor)
                self.setTextCursor(cursor)
                return
        for previous in self._color_tags:
            self._remove_specific_tag_at_cursor(previous, self._color_action_ends[previous])
        if start_tag:
            self._apply_formatting_tokens(start_tag, self._color_action_ends[start_tag])

    def _edit_formatting_tags(self):
        """
        Open the formatting tag dialog and refresh the color dropdown if tags were saved.
        """
        if self._formatting_tag_form is None:
            parent = self.window() or Registry().get('main_window')
            self._formatting_tag_form = FormattingTagForm(parent)
        if self._formatting_tag_form.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._populate_color_menu()
            self._update_toolbar_state()

    def resizeEvent(self, event):
        """
        Keep the formatting toolbar positioned above the editable viewport.
        """
        super().resizeEvent(event)
        self._position_formatting_toolbar()

    def _position_formatting_toolbar(self):
        """Reserve the full header row while keeping the scrollbar below it."""
        toolbar_height = self._toolbar.sizeHint().height() + 2 if self._toolbar else 0
        rect = self.contentsRect()
        if self._toolbar:
            self._toolbar.setGeometry(rect.x(), rect.y(), rect.width(), toolbar_height - 2)
            self._toolbar.raise_()
        height = max(1, rect.height() - toolbar_height)
        self._input.setMinimumHeight(0)
        self._input.setMaximumHeight(16777215)
        self._input.setGeometry(rect.x(), rect.y() + toolbar_height, rect.width(), height)
        self._layout_text_input()

    def _layout_text_input(self):
        """Keep text and section backgrounds inside the Fluent border with bottom breathing room."""
        border = self.frameWidth()
        self._editor.setGeometry(self._input.rect().adjusted(
            border, border, -border, -border - self.BOTTOM_PADDING))
        scrollbar = self._input.verticalScrollBar()
        width = scrollbar.sizeHint().width()
        scrollbar.setGeometry(self._input.width() - width - border, border,
                              width, max(1, self._input.height() - 2 * border))
        self._sync_vertical_scrollbar()

    def set_rich_text_mode(self, enabled):
        """
        Toggle between plain text and rich text visual mode.
        """
        self.rich_text_mode = bool(enabled)
        self.highlighter.set_rich_text_mode(self.rich_text_mode)
        self._update_mode_switch()
        self._update_toolbar_state()
        self.viewport().update()
        self.highlighter.rehighlight()
        self._refresh_block_formats()

    def set_visual_line_overrides(self, overrides):
        """
        Set optional display text overrides keyed by block number.

        :param overrides: Dict[int, str] where key is the document block number.
        """
        self._visual_line_overrides = overrides if isinstance(overrides, dict) else {}
        self._refresh_block_formats()
        self.viewport().update()

    def reset_undo_redo_history(self):
        """
        Clear the document's undo/redo history after loading content programmatically.
        """
        self.document().clearUndoRedoStacks()
        self.undoAvailable.emit(False)
        self.redoAvailable.emit(False)

    @staticmethod
    def _tag_token_pair(start_tag_token):
        """
        Build a token pair (start/end) for a start tag name like ``st``.
        """
        return '{{{tag}}}'.format(tag=start_tag_token), '{{/{tag}}}'.format(tag=start_tag_token)

    @staticmethod
    def _iter_matching_tag_regions(text, start_tag, end_tag):
        """
        Yield balanced regions for a specific formatting tag pair.

        This is depth-aware for nested occurrences of the same tag pair so the
        returned start/end positions always refer to the matching closing tag.
        """
        search_start = 0
        start_len = len(start_tag)
        end_len = len(end_tag)
        while True:
            start_pos = text.find(start_tag, search_start)
            if start_pos == -1:
                return
            depth = 1
            scan_pos = start_pos + start_len
            while depth > 0:
                next_start = text.find(start_tag, scan_pos)
                next_end = text.find(end_tag, scan_pos)
                if next_end == -1:
                    return
                if next_start != -1 and next_start < next_end:
                    depth += 1
                    scan_pos = next_start + start_len
                else:
                    depth -= 1
                    end_pos = next_end
                    scan_pos = next_end + end_len
            yield {
                'start_token_start': start_pos,
                'start_token_length': start_len,
                'end_token_start': end_pos,
                'end_token_length': end_len
            }
            search_start = scan_pos

    @staticmethod
    def _selection_section_ranges(text, selection_start, selection_end):
        """
        Split a selected text range into sub-ranges separated by slide markers.

        The separator itself is excluded from the returned ranges so formatting
        actions can be applied to each slide section independently.
        """
        if selection_start >= selection_end:
            return []
        selected_text = text[selection_start:selection_end]
        separator_regex = SpellTextEdit.SECTION_BOUNDARY_LINE_REGEX
        ranges = []
        chunk_start = 0
        for match in separator_regex.finditer(selected_text):
            chunk_end = match.start()
            # Do not include the newline directly before a marker line.
            if chunk_end > chunk_start and selected_text[chunk_end - 1] == '\n':
                chunk_end -= 1
                if chunk_end > chunk_start and selected_text[chunk_end - 1] == '\r':
                    chunk_end -= 1
            if chunk_end > chunk_start:
                ranges.append((selection_start + chunk_start, selection_start + chunk_end))
            chunk_start = match.end()
            # Do not include the newline directly after a marker line.
            if chunk_start < len(selected_text) and selected_text[chunk_start] == '\r':
                chunk_start += 1
            if chunk_start < len(selected_text) and selected_text[chunk_start] == '\n':
                chunk_start += 1
        if chunk_start < len(selected_text):
            ranges.append((selection_start + chunk_start, selection_start + len(selected_text)))
        return [(start, end) for start, end in ranges if start < end]

    @staticmethod
    def _is_section_boundary_line(text):
        """
        Return True when *text* is a known section boundary line.
        """
        return bool(SpellTextEdit.SECTION_BOUNDARY_LINE_REGEX.match(text.strip()))

    def _known_tag_tokens(self):
        """
        Return all known formatting tag tokens for this install.
        """
        known_tokens = set()
        for html in FormattingTags.get_html_tags():
            start_tag = html.get('start tag')
            end_tag = html.get('end tag')
            if start_tag:
                known_tokens.add(start_tag)
            if end_tag:
                known_tokens.add(end_tag)
        return known_tokens

    def _toggle_color_tag(self, start_tag, end_tag):
        """
        Toggle a color formatting tag on/off at the current cursor position.
        """
        cursor = self.textCursor()
        if cursor.hasSelection():
            sel_start = cursor.selectionStart()
            sel_end = cursor.selectionEnd()
            full_text = self.toPlainText()
            selected_text = cursor.selectedText().replace('\u2029', '\n').replace('\u2028', '\n')
            selected_normalized = selected_text.rstrip('\n')
            full_normalized = full_text.rstrip('\n')
            full_selection = ((sel_start == 0 and sel_end >= max(0, len(full_text) - 1)) or
                              selected_text == full_text or
                              selected_normalized == full_normalized)
            if full_selection:
                known_tokens = sorted(self._known_tag_tokens(), key=len, reverse=True)
                if known_tokens:
                    token_regex = re.compile('|'.join(re.escape(token) for token in known_tokens))
                    cleaned = token_regex.sub('', full_text)
                    if cleaned != full_text:
                        self.setPlainText(cleaned)
                return
            # First remove any known tokens that are explicitly inside the selection.
            # This handles malformed/unbalanced tag sequences robustly.
            self._remove_known_tokens_in_selection()
            cursor = self.textCursor()
            text = self.toPlainText()
            ranges = self._selection_section_ranges(text, cursor.selectionStart(), cursor.selectionEnd())
            if len(ranges) > 1:
                for start, end in reversed(ranges):
                    section_cursor = QtGui.QTextCursor(self.document())
                    section_cursor.setPosition(start)
                    section_cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
                    self.setTextCursor(section_cursor)
                    self._toggle_color_tag(start_tag, end_tag)
                self._collapse_redundant_formatting_boundaries()
                return
        if self._is_tag_active_at_cursor(start_tag, end_tag):
            self._remove_specific_tag_at_cursor(start_tag, end_tag)
        else:
            self._apply_formatting_tokens(start_tag, end_tag)

    def _apply_formatting_by_tag(self, start_tag_token):
        """
        Toggle a formatting tag on/off for the current selection or word.

        When the cursor is already inside a region wrapped by this tag the tag
        tokens are removed (word-processor toggle-off behaviour).  Otherwise
        the tag is applied around the selection or word.
        """
        start_tag, end_tag = self._tag_token_pair(start_tag_token)
        if start_tag in self._color_tags:
            self._on_custom_formatting_changed(self._color_tags.index(start_tag) + 1)
            return
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = self.toPlainText()
            selection_start = cursor.selectionStart()
            selection_end = cursor.selectionEnd()
            ranges = self._selection_section_ranges(text, selection_start, selection_end)
            if not ranges:
                return
            if len(ranges) > 1 or ranges[0] != (selection_start, selection_end):
                cumulative_delta = 0
                section_selections = []
                for start, end in ranges:
                    adjusted_start = start + cumulative_delta
                    adjusted_end = end + cumulative_delta
                    section_cursor = QtGui.QTextCursor(self.document())
                    section_cursor.setPosition(adjusted_start)
                    section_cursor.setPosition(adjusted_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
                    self.setTextCursor(section_cursor)
                    before_len = len(self.toPlainText())
                    self._apply_formatting_by_tag(start_tag_token)
                    after_len = len(self.toPlainText())
                    cumulative_delta += after_len - before_len
                    result_cursor = self.textCursor()
                    if result_cursor.hasSelection():
                        section_selections.append((result_cursor.selectionStart(), result_cursor.selectionEnd()))
                self._collapse_redundant_formatting_boundaries()
                if section_selections:
                    final_cursor = QtGui.QTextCursor(self.document())
                    final_cursor.setPosition(section_selections[0][0])
                    final_cursor.setPosition(section_selections[-1][1], QtGui.QTextCursor.MoveMode.KeepAnchor)
                    self.setTextCursor(final_cursor)
                return
        if self._is_tag_active_at_cursor(start_tag, end_tag):
            self._remove_specific_tag_at_cursor(start_tag, end_tag)
        else:
            self._apply_formatting_tokens(start_tag, end_tag)

    def _is_tag_active_at_cursor(self, start_tag, end_tag):
        """
        Return True when the cursor (or selection start) sits inside a region
        wrapped by *start_tag* / *end_tag*.
        """
        cursor = self.textCursor()
        pos = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        text = self.toPlainText()
        for region in Highlighter._iter_tag_regions(
                text, [{'start tag': start_tag, 'end tag': end_tag, 'start html': ''}]):
            r_start = region['start_token_start']
            r_end = region['end_token_start'] + region['end_token_length']
            if r_start <= pos < r_end:
                return True
        return False

    def _remove_specific_tag_at_cursor(self, start_tag, end_tag):
        """
        Remove the start/end tokens of any regions matching *start_tag* / *end_tag*
        that contain or overlap the current cursor position or selection.
        """
        cursor = self.textCursor()
        text = self.toPlainText()
        sel_start = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        sel_end = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()

        if cursor.hasSelection():
            matching_regions = [region for region in self._iter_matching_tag_regions(text, start_tag, end_tag)
                                if region['start_token_start'] < sel_end and
                                region['end_token_start'] + region['end_token_length'] > sel_start]
            if not matching_regions:
                return
            edit_cursor = QtGui.QTextCursor(self.document())
            edit_cursor.beginEditBlock()
            new_start, new_end = sel_start, sel_end
            for region in reversed(matching_regions):
                edit_start = region['start_token_start']
                edit_end = region['end_token_start'] + region['end_token_length']
                content_start = edit_start + len(start_tag)
                content_end = edit_end - len(end_tag)
                if sel_end <= content_start or sel_start >= content_end:
                    continue
                left = text[content_start:min(sel_start, content_end)]
                middle = text[max(sel_start, content_start):min(sel_end, content_end)]
                right = text[max(sel_end, content_start):content_end]
                # Keep the unselected text styled, including independently styled regions.
                left = start_tag + left + end_tag if re.sub(r'\{/?\w+\}', '', left) else left
                right = start_tag + right + end_tag if re.sub(r'\{/?\w+\}', '', right) else right
                middle = middle.replace(start_tag, '').replace(end_tag, '')
                replacement = left + middle + right
                delta = len(replacement) - (edit_end - edit_start)
                if new_start >= edit_start:
                    new_start = edit_start + len(left)
                if new_end >= edit_end:
                    new_end += delta
                else:
                    new_end = edit_start + len(left) + len(middle)
                edit_cursor.setPosition(edit_start)
                edit_cursor.setPosition(edit_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
                edit_cursor.insertText(replacement)
            edit_cursor.endEditBlock()
            edit_cursor.setPosition(new_start)
            edit_cursor.setPosition(new_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(edit_cursor)
            return

        # Collect the widest edit range from all overlapping regions.
        edit_start = sel_start
        edit_end = sel_end
        found = False
        for region in self._iter_matching_tag_regions(text, start_tag, end_tag):
            r_start = region['start_token_start']
            r_end = region['end_token_start'] + region['end_token_length']
            if r_start <= sel_end and r_end >= sel_start:
                edit_start = min(edit_start, r_start)
                edit_end = max(edit_end, r_end)
                found = True
        if not found:
            return

        segment = text[edit_start:edit_end]
        cleaned = segment.replace(start_tag, '').replace(end_tag, '')
        if cleaned == segment:
            return
        # Calculate the new cursor offset within the cleaned segment.
        offset = sel_start - edit_start
        offset_cleaned = len(re.sub(
            re.escape(start_tag) + '|' + re.escape(end_tag), '', segment[:offset]))

        edit_cursor = QtGui.QTextCursor(self.document())
        edit_cursor.setPosition(edit_start)
        edit_cursor.setPosition(edit_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
        edit_cursor.beginEditBlock()
        edit_cursor.removeSelectedText()
        edit_cursor.insertText(cleaned)
        edit_cursor.endEditBlock()
        edit_cursor.setPosition(edit_start + offset_cleaned)
        self.setTextCursor(edit_cursor)

    def _update_toolbar_state(self):
        """
        Reflect the formatting state at the cursor position in the toolbar buttons.

        Each tracked button is checked when the cursor (or selection start) is
        inside a region wrapped by that button's tag, mirroring the word-processor
        convention where Bold is highlighted while the caret is in bold text.
        """
        if not self._tag_actions:
            return
        if not self.rich_text_mode:
            for action in self._tag_actions.values():
                action.blockSignals(True)
                action.setChecked(False)
                action.blockSignals(False)
            self._sync_custom_formatting()
            return
        text = self.toPlainText()
        cursor = self.textCursor()
        pos = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        for tag_token, action in self._tag_actions.items():
            start_tag, end_tag = self._tag_token_pair(tag_token)
            active = False
            for region in self._iter_matching_tag_regions(text, start_tag, end_tag):
                r_start = region['start_token_start']
                r_end = region['end_token_start'] + region['end_token_length']
                if r_start <= pos < r_end:
                    active = True
                    break
            action.blockSignals(True)
            action.setChecked(active)
            action.blockSignals(False)
        self._sync_custom_formatting()

    def _sync_custom_formatting(self):
        """Reflect cursor formatting without modifying the document."""
        if self._updating_custom_formatting:
            return
        text, cursor = self.toPlainText(), self.textCursor()
        regions = []
        for row, start_tag in enumerate(self._color_tags, 1):
            for region in self._iter_matching_tag_regions(text, start_tag, self._color_action_ends[start_tag]):
                regions.append((region['start_token_start'],
                                region['end_token_start'] + region['end_token_length'], row))
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        boundaries = {start, end}
        boundaries.update(position for left, right, _ in regions for position in (left, right)
                          if start < position < end)
        states = set()
        points = sorted(boundaries)
        segments = list(zip(points, points[1:])) if cursor.hasSelection() else [(start, start + 1)]
        token_pattern = re.compile(r'\{/?\w+\}')
        for left, right in segments:
            if cursor.hasSelection():
                content = token_pattern.sub('', text[left:right]).strip()
                if not content or self._is_section_boundary_line(content):
                    continue
            active = [(region_start, row) for region_start, region_end, row in regions
                      if region_start <= left < region_end]
            states.add(max(active)[1] if active and self.rich_text_mode else 0)
        mixed = len(states) > 1
        blocker = QtCore.QSignalBlocker(self._custom_formatting_combo)
        self._custom_formatting_combo.setPlaceholderText(translate('OpenLP.SpellTextEdit', 'Mixed') if mixed else
                                                         translate('OpenLP.SpellTextEdit', 'Styles'))
        self._custom_formatting_combo.setCurrentIndex(-1 if mixed else next(iter(states), 0))
        del blocker

    def _apply_formatting_tokens(self, start_tag, end_tag):
        """
        Apply explicit start/end formatting tokens around the current selection or word.

        The cursor (or selection) is restored to the same logical content position
        after the tags are inserted so the caret does not jump unexpectedly.
        """
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if cursor.hasSelection():
            sel_start = cursor.selectionStart()
            sel_end = cursor.selectionEnd()
            selected_text = cursor.selectedText()
            full_text = self.toPlainText()
            if not self._selection_section_ranges(full_text, sel_start, sel_end):
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self.setFocus()
                return
            prefix = full_text[:sel_start]
            suffix = full_text[sel_end:]
            if prefix.endswith(end_tag) and suffix.startswith(start_tag):
                selection_start = sel_start - len(end_tag)
                selection_end = selection_start + len(selected_text)
                cursor.setPosition(selection_start)
                cursor.setPosition(sel_start, QtGui.QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.setPosition(selection_end)
                cursor.setPosition(selection_end + len(start_tag), QtGui.QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.setPosition(selection_start)
                cursor.setPosition(selection_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self.setFocus()
                return
            cursor.removeSelectedText()
            cursor.insertText('{start}{text}{end}'.format(start=start_tag, text=selected_text, end=end_tag))
            # Restore selection over the content region (between the tokens).
            cursor.setPosition(sel_start + len(start_tag))
            cursor.setPosition(sel_start + len(start_tag) + len(selected_text),
                               QtGui.QTextCursor.MoveMode.KeepAnchor)
        else:
            if self._is_section_boundary_line(cursor.block().text()):
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                self.setFocus()
                return
            original_pos = cursor.position()
            word_cursor = QtGui.QTextCursor(cursor)
            word_cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
            if word_cursor.hasSelection():
                word_start = word_cursor.selectionStart()
                selected_text = word_cursor.selectedText()
                word_cursor.removeSelectedText()
                word_cursor.insertText('{start}{text}{end}'.format(start=start_tag, text=selected_text, end=end_tag))
                cursor = word_cursor
                # Restore cursor at the same relative position within the word content.
                cursor.setPosition(word_start + len(start_tag) + (original_pos - word_start))
            else:
                insert_text = '{start}{end}'.format(start=start_tag, end=end_tag)
                cursor.insertText(insert_text)
                for _ in range(len(end_tag)):
                    cursor.movePosition(QtGui.QTextCursor.MoveOperation.Left)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.setFocus()

    def _collapse_redundant_formatting_boundaries(self):
        """
        Collapse adjacent closing/opening pairs of the same formatting tag.

        This is useful after a slide section is removed and two sections that
        used to be separated by a marker become adjacent again.
        """
        text = self.toPlainText()
        remove_ranges = []
        for html in FormattingTags.get_html_tags():
            start_tag = html.get('start tag')
            end_tag = html.get('end tag')
            if not start_tag or not end_tag:
                continue
            pair = end_tag + start_tag
            pair_length = len(pair)
            search_start = 0
            while True:
                pos = text.find(pair, search_start)
                if pos == -1:
                    break
                remove_ranges.append((pos, pos + pair_length))
                search_start = pos + pair_length
        if not remove_ranges:
            return

        remove_ranges = sorted(remove_ranges)
        merged_ranges = [remove_ranges[0]]
        for start, end in remove_ranges[1:]:
            last_start, last_end = merged_ranges[-1]
            if start <= last_end:
                merged_ranges[-1] = (last_start, max(last_end, end))
            else:
                merged_ranges.append((start, end))

        cursor = self.textCursor()
        position = cursor.position()
        anchor = cursor.anchor()

        def shifted_position(original_position):
            removed_before = 0
            for start, end in merged_ranges:
                if end <= original_position:
                    removed_before += end - start
                elif start < original_position:
                    removed_before += original_position - start
            return original_position - removed_before

        edit_cursor = QtGui.QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        for start, end in reversed(merged_ranges):
            edit_cursor.setPosition(start)
            edit_cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            edit_cursor.removeSelectedText()
        edit_cursor.endEditBlock()

        new_cursor = self.textCursor()
        new_cursor.setPosition(max(0, shifted_position(position)))
        if anchor != position:
            new_cursor.setPosition(max(0, shifted_position(anchor)), QtGui.QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(new_cursor)

    def _remove_known_tokens_in_selection(self):
        """
        Remove any known formatting tokens that still remain inside the active selection.

        This is a safety net for malformed or unbalanced tag sequences that are not
        fully removed by pair-aware logic.
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()
        full_text = self.toPlainText()
        selected_text = full_text[sel_start:sel_end]
        known_tokens = sorted(self._known_tag_tokens(), key=len, reverse=True)
        if not known_tokens:
            return
        token_regex = re.compile('|'.join(re.escape(token) for token in known_tokens))
        remove_ranges = [(sel_start + match.start(), sel_start + match.end())
                         for match in token_regex.finditer(selected_text)]
        if not remove_ranges:
            return

        def shifted_position(position):
            removed_before = 0
            for start, end in remove_ranges:
                if end <= position:
                    removed_before += end - start
                elif start < position:
                    removed_before += position - start
            return position - removed_before

        edit_cursor = QtGui.QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        for start, end in reversed(remove_ranges):
            edit_cursor.setPosition(start)
            edit_cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            edit_cursor.removeSelectedText()
        edit_cursor.endEditBlock()
        edit_cursor.setPosition(shifted_position(sel_start))
        edit_cursor.setPosition(shifted_position(sel_end), QtGui.QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(edit_cursor)

    def _remove_known_tokens_in_range(self, start, end):
        """
        Remove known formatting tokens in an explicit document range.
        """
        full_text = self.toPlainText()
        start = max(0, min(start, len(full_text)))
        end = max(start, min(end, len(full_text)))
        if start >= end:
            return
        known_tokens = sorted(self._known_tag_tokens(), key=len, reverse=True)
        if not known_tokens:
            return
        token_regex = re.compile('|'.join(re.escape(token) for token in known_tokens))
        segment = full_text[start:end]
        remove_ranges = [(start + match.start(), start + match.end())
                         for match in token_regex.finditer(segment)]
        if not remove_ranges:
            return
        edit_cursor = QtGui.QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        for remove_start, remove_end in reversed(remove_ranges):
            edit_cursor.setPosition(remove_start)
            edit_cursor.setPosition(remove_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            edit_cursor.removeSelectedText()
        edit_cursor.endEditBlock()

    def _remove_known_tokens_in_ranges(self, ranges):
        """
        Remove known formatting tokens across multiple explicit ranges.
        """
        for start, end in reversed(ranges):
            self._remove_known_tokens_in_range(start, end)

    def remove_formatting(self):
        """
        Remove inline formatting tags from the selected text or current word.

        Any known formatting region that overlaps the active selection has both
        its opening and closing tokens removed, leaving the content intact.
        """
        cursor = self.textCursor()
        if cursor.hasSelection():
            text = self.toPlainText()
            ranges = self._selection_section_ranges(text, cursor.selectionStart(), cursor.selectionEnd())
            if len(ranges) > 1:
                union_start = ranges[0][0]
                union_end = ranges[-1][1]
                for start, end in reversed(ranges):
                    section_cursor = QtGui.QTextCursor(self.document())
                    section_cursor.setPosition(start)
                    section_cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
                    self.setTextCursor(section_cursor)
                    self.remove_formatting()
                self._collapse_redundant_formatting_boundaries()
                self._remove_known_tokens_in_ranges(ranges)
                current_length = len(self.toPlainText())
                final_cursor = QtGui.QTextCursor(self.document())
                final_cursor.setPosition(min(union_start, current_length))
                final_cursor.setPosition(min(union_end, current_length), QtGui.QTextCursor.MoveMode.KeepAnchor)
                self.setTextCursor(final_cursor)
                self._remove_known_tokens_in_selection()
                return
            try:
                html_tags = FormattingTags.get_html_tags()
            except Exception:
                html_tags = []
            for html in html_tags:
                start_tag = html.get('start tag')
                end_tag = html.get('end tag')
                if start_tag and end_tag:
                    self._remove_specific_tag_at_cursor(start_tag, end_tag)
            self._remove_known_tokens_in_selection()
            return
        if not cursor.hasSelection():
            cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        if not cursor.hasSelection():
            return
        full_text = self.toPlainText()
        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()
        try:
            html_tags = FormattingTags.get_html_tags()
        except Exception:
            html_tags = []
        remove_ranges = []
        for region in Highlighter._iter_tag_regions(full_text, html_tags):
            region_start = region['start_token_start']
            region_end = region['end_token_start'] + region['end_token_length']
            if region_start < sel_end and region_end > sel_start:
                remove_ranges.append((region['start_token_start'],
                                      region['start_token_start'] + region['start_token_length']))
                remove_ranges.append((region['end_token_start'],
                                      region['end_token_start'] + region['end_token_length']))
        if not remove_ranges:
            return

        remove_ranges = sorted(remove_ranges)
        merged_ranges = [remove_ranges[0]]
        for start, end in remove_ranges[1:]:
            last_start, last_end = merged_ranges[-1]
            if start <= last_end:
                merged_ranges[-1] = (last_start, max(last_end, end))
            else:
                merged_ranges.append((start, end))

        def shifted_position(position):
            removed_before = 0
            for start, end in merged_ranges:
                if end <= position:
                    removed_before += end - start
                elif start < position:
                    removed_before += position - start
            return position - removed_before

        edit_cursor = QtGui.QTextCursor(self.document())
        edit_cursor.beginEditBlock()
        for start, end in reversed(merged_ranges):
            edit_cursor.setPosition(start)
            edit_cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
            edit_cursor.removeSelectedText()
        edit_cursor.endEditBlock()
        edit_cursor.setPosition(shifted_position(sel_start))
        edit_cursor.setPosition(shifted_position(sel_end), QtGui.QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(edit_cursor)

    def remove_unused_tags(self):
        """
        Remove formatting tags that are not known in this OpenLP installation.
        """
        known_tokens = self._known_tag_tokens()
        text = self.toPlainText()
        cleaned_text = re.sub(r'\{/?[^\}\s]+\}',
                              lambda match: match.group(0) if match.group(0) in known_tokens else '',
                              text)
        if cleaned_text != text:
            self.setPlainText(cleaned_text)

    def _paint_visual_markers(self, event):
        """
        Draw visual split lines for split markers while keeping raw marker text in the document.
        """
        if not self.rich_text_mode:
            return
        painter = QtGui.QPainter(self.viewport())
        pen_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
        block = self.document().begin()
        offset = QtCore.QPointF(-self.horizontalScrollBar().value(), -self.verticalScrollBar().value())
        cursor = self.textCursor()
        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()
        while block.isValid():
            geometry = self.document().documentLayout().blockBoundingRect(block).translated(offset)
            top = geometry.top()
            bottom = geometry.bottom()
            if top > event.rect().bottom():
                break
            if bottom >= event.rect().top():
                pen_style = self.split_marker_style_for_text(block.text())
                if pen_style:
                    color = QtGui.QColor(pen_color)
                    if block.text().strip() == '[---]':
                        color.setAlphaF(0.5)
                    pen = QtGui.QPen(color, self.split_marker_width_for_text(block.text()), pen_style)
                    painter.setPen(pen)
                    y = int(top + (self.fontMetrics().height() / 2))
                    painter.drawLine(6, y, self.viewport().width() - 6, y)
                override = self._visual_line_overrides.get(block.blockNumber())
                if override:
                    # Check if this block is selected. If so, skip the nice label and show raw text.
                    block_start = block.position()
                    block_end = block.position() + block.length() - 1
                    is_block_selected = (sel_start < block_end and sel_end > block_start)
                    if is_block_selected:
                        # Skip visual override for selected blocks to show raw marker text
                        block = block.next()
                        continue
                    if isinstance(override, dict):
                        override_text = override.get('text', '')
                        override_color = override.get('background')
                    else:
                        override_text = str(override)
                        override_color = None
                    if not isinstance(override_color, QtGui.QColor) or not override_color.isValid():
                        override_color = self.palette().color(QtGui.QPalette.ColorRole.Base)
                    height = max(geometry.height(), block.blockFormat().lineHeight())
                    painter.fillRect(QtCore.QRectF(0, top, self.viewport().width(), height),
                                     self.palette().brush(QtGui.QPalette.ColorRole.Base))
                    row_rect = QtCore.QRectF(0, top, self.viewport().width(), height)
                    painter.fillRect(row_rect, QtGui.QBrush(override_color))
                    font = QtGui.QFont(self.font())
                    font.setBold(True)
                    painter.setFont(font)
                    painter.setPen(QtGui.QPen(pen_color))
                    text_rect = row_rect.adjusted(self.TEXT_INSET, 0, -self.TEXT_INSET, 0)
                    alignment = QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft
                    painter.drawText(text_rect, alignment, override_text)
            block = block.next()

    def mousePressEvent(self, event):
        """
        Handle mouse clicks within the text edit region.
        """
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            # Rewrite the mouse event to a left button event so the cursor is moved to the location of the pointer.
            event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress,
                                      event.pos(),
                                      QtCore.Qt.MouseButton.LeftButton,
                                      QtCore.Qt.MouseButton.LeftButton,
                                      QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QTextEdit.mousePressEvent(self._editor, event)

    def contextMenuEvent(self, event):
        """
        Provide the context menu for the text edit region.
        """
        popup_menu = self.createStandardContextMenu()
        # Select the word under the cursor.
        cursor = self.textCursor()
        # only select text if not already selected
        if not cursor.hasSelection():
            cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        self.setTextCursor(cursor)
        # Add menu with available languages.
        if ENCHANT_AVAILABLE:
            lang_menu = QtWidgets.QMenu(translate('OpenLP.SpellTextEdit', 'Language'))
            for lang in enchant.list_languages():
                action = create_action(lang_menu, lang, text=lang, checked=lang == self.dictionary.tag)
                lang_menu.addAction(action)
            popup_menu.insertSeparator(popup_menu.actions()[0])
            popup_menu.insertMenu(popup_menu.actions()[0], lang_menu)
            lang_menu.triggered.connect(self.set_language)
        # Check if the selected word is misspelled and offer spelling suggestions if it is.
        if ENCHANT_AVAILABLE and self.textCursor().hasSelection():
            text = self.textCursor().selectedText()
            if not self.dictionary.check(text):
                spell_menu = QtWidgets.QMenu(translate('OpenLP.SpellTextEdit', 'Spelling Suggestions'))
                for word in self.dictionary.suggest(text):
                    action = SpellAction(word, spell_menu)
                    action.correct.connect(self.correct_word)
                    spell_menu.addAction(action)
                # Only add the spelling suggests to the menu if there are suggestions.
                if spell_menu.actions():
                    popup_menu.insertMenu(popup_menu.actions()[0], spell_menu)
        tag_menu = QtWidgets.QMenu(translate('OpenLP.SpellTextEdit', 'Formatting styles'))
        if self.formatting_tags_allowed:
            for html in FormattingTags.get_html_tags():
                action = SpellAction(html['desc'], tag_menu)
                action.correct.connect(self.html_tag)
                tag_menu.addAction(action)
            popup_menu.insertSeparator(popup_menu.actions()[0])
            popup_menu.insertMenu(popup_menu.actions()[0], tag_menu)
        popup_menu.exec(event.globalPos())

    def set_language(self, action):
        """
        Changes the language for this spelltextedit.

        :param action: The action.
        """
        self.dictionary = enchant.Dict(action.text())
        self.highlighter.spelling_dictionary = self.dictionary
        self.highlighter.highlightBlock(self.toPlainText())
        self.highlighter.rehighlight()

    def correct_word(self, word):
        """
        Replaces the selected text with word.
        """
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(word)
        cursor.endEditBlock()

    def html_tag(self, tag):
        """
        Replaces the selected text with word.
        """
        tag = tag.replace('&', '')
        for html in FormattingTags.get_html_tags():
            if tag == html['desc']:
                if html['start tag'] in self._color_tags:
                    self._on_custom_formatting_changed(self._color_tags.index(html['start tag']) + 1)
                    return
                cursor = self.textCursor()
                if self.textCursor().hasSelection():
                    text = cursor.selectedText()
                    cursor.beginEditBlock()
                    cursor.removeSelectedText()
                    cursor.insertText(html['start tag'])
                    cursor.insertText(text)
                    cursor.insertText(html['end tag'])
                    cursor.endEditBlock()
                else:
                    cursor = self.textCursor()
                    cursor.insertText(html['start tag'])
                    cursor.insertText(html['end tag'])

    def insertFromMimeData(self, source):
        """
        Reimplement `insertFromMimeData` so that we can remove any control characters

        :param QtCore.QMimeData source: The mime data to insert
        :rtype: None
        """
        self.insertPlainText(CONTROL_CHARS.sub('', source.text()))


class Highlighter(QtGui.QSyntaxHighlighter):
    """
    Provides a text highlighter for pointing out spelling errors in text.
    """
    WORDS = r'(?i)[\w\']+'

    def __init__(self, *args, formatting_tags_allowed=True):
        """
        Constructor
        """
        super(Highlighter, self).__init__(*args)
        self.spelling_dictionary = None
        self.formatting_tags_allowed = formatting_tags_allowed
        self.rich_text_mode = formatting_tags_allowed
        self._format_cache = {}

    def set_rich_text_mode(self, enabled):
        """
        Toggle rich text visual highlighting mode.
        """
        self.rich_text_mode = bool(enabled)

    def _format_from_start_html(self, start_html):
        """
        Build a best-effort character format from a formatting tag's start html.
        """
        if start_html in self._format_cache:
            return self._format_cache[start_html]
        text_format = QtGui.QTextCharFormat()
        lower_html = start_html.lower()
        if '<strong' in lower_html or '<b>' in lower_html:
            text_format.setFontWeight(QtGui.QFont.Weight.Bold)
        if '<em' in lower_html or '<i>' in lower_html:
            text_format.setFontItalic(True)
        if '<u>' in lower_html or re.search(r'text-decoration\s*:\s*[^;]*underline', lower_html):
            text_format.setFontUnderline(True)
        if re.search(r'font-style\s*:\s*italic', lower_html):
            text_format.setFontItalic(True)
        if re.search(r'text-transform\s*:\s*uppercase', lower_html):
            text_format.setFontCapitalization(QtGui.QFont.Capitalization.AllUppercase)
        if '<sup' in lower_html:
            text_format.setVerticalAlignment(QtGui.QTextCharFormat.VerticalAlignment.AlignSuperScript)
        if '<sub' in lower_html:
            text_format.setVerticalAlignment(QtGui.QTextCharFormat.VerticalAlignment.AlignSubScript)

        color_match = re.search(r'(?:-webkit-text-fill-color|color)\s*:\s*([^;"\']+)', start_html,
                                flags=re.IGNORECASE)
        if color_match:
            color = QtGui.QColor(color_match.group(1).strip())
            if color.isValid():
                text_format.setForeground(color)

        font_size_match = re.search(r'font-size\s*:\s*([0-9]*\.?[0-9]+)\s*(%|pt|px)?', start_html,
                                    flags=re.IGNORECASE)
        if font_size_match:
            value = float(font_size_match.group(1))
            unit = (font_size_match.group(2) or 'pt').lower()
            base_size = self.document().defaultFont().pointSizeF()
            if base_size <= 0:
                base_size = 12.0
            if unit == '%':
                text_format.setFontPointSize(base_size * value / 100.0)
            elif unit == 'px':
                text_format.setFontPointSize(value * 0.75)
            else:
                text_format.setFontPointSize(value)

        weight_match = re.search(r'font-weight\s*:\s*(\d{3})', start_html, flags=re.IGNORECASE)
        if weight_match:
            weight_value = int(weight_match.group(1))
            text_format.setFontWeight(QtGui.QFont.Weight.Bold if weight_value >= 600 else QtGui.QFont.Weight.Normal)

        opacity_match = re.search(r'opacity\s*:\s*([0-9]*\.?[0-9]+)', start_html, flags=re.IGNORECASE)
        if opacity_match:
            opacity = max(0.0, min(1.0, float(opacity_match.group(1))))
            if text_format.foreground().style() == QtCore.Qt.BrushStyle.NoBrush:
                color = QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.Text)
            else:
                color = text_format.foreground().color()
            if color.isValid():
                color.setAlphaF(opacity)
                text_format.setForeground(color)

        self._format_cache[start_html] = text_format
        return text_format

    @staticmethod
    def _iter_tag_regions(text, html_tags):
        """
        Yield exact start-tag, content and end-tag ranges for known tags in a block.
        """
        for html in html_tags:
            start_tag = html.get('start tag')
            end_tag = html.get('end tag')
            if not start_tag or not end_tag:
                continue
            start_index = 0
            while True:
                start_pos = text.find(start_tag, start_index)
                if start_pos == -1:
                    break
                end_pos = text.find(end_tag, start_pos + len(start_tag))
                if end_pos == -1:
                    break
                content_start = start_pos + len(start_tag)
                yield {
                    'html': html,
                    'start_token_start': start_pos,
                    'start_token_length': len(start_tag),
                    'content_start': content_start,
                    'content_length': end_pos - content_start,
                    'end_token_start': end_pos,
                    'end_token_length': len(end_tag)
                }
                start_index = end_pos + len(end_tag)

    @staticmethod
    def _unknown_token_format():
        """
        Return the format used for unknown formatting tag tokens.
        """
        unknown_token_format = QtGui.QTextCharFormat()
        unknown_color = QtGui.QColor(QtCore.Qt.GlobalColor.red)
        unknown_token_format.setForeground(unknown_color)
        return unknown_token_format

    @staticmethod
    def _hidden_token_format():
        """
        Return the format used to hide marker/tag tokens in rich text mode.
        """
        hidden_token_format = QtGui.QTextCharFormat()
        transparent = QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.Text)
        transparent.setAlpha(0)
        hidden_token_format.setForeground(transparent)
        # Collapse advance width to effectively zero:
        # - 0.001pt makes the glyph height near-zero
        # - stretch=1 compresses horizontal glyph metrics to 1% of normal width,
        #   overcoming Qt's minimum font-size clamping
        # - AbsoluteSpacing(0) ensures no inter-character gap is added on top
        hidden_token_format.setFontPointSize(0.001)
        hidden_token_format.setFontStretch(1)
        hidden_token_format.setFontLetterSpacingType(QtGui.QFont.SpacingType.AbsoluteSpacing)
        hidden_token_format.setFontLetterSpacing(0)
        return hidden_token_format

    @staticmethod
    def _merged_char_format(base_format, overlay_format):
        """
        Merge a formatting overlay onto an existing character format.

        This allows nested/stacked tags (for example bold + italic) to be
        rendered together rather than whichever tag was applied last.
        """
        merged = QtGui.QTextCharFormat(base_format)
        if overlay_format.fontWeight() != QtGui.QFont.Weight.Normal:
            merged.setFontWeight(overlay_format.fontWeight())
        if overlay_format.fontItalic():
            merged.setFontItalic(True)
        if overlay_format.fontUnderline():
            merged.setFontUnderline(True)
        if overlay_format.verticalAlignment() != QtGui.QTextCharFormat.VerticalAlignment.AlignNormal:
            merged.setVerticalAlignment(overlay_format.verticalAlignment())
        if overlay_format.fontCapitalization() != QtGui.QFont.Capitalization.MixedCase:
            merged.setFontCapitalization(overlay_format.fontCapitalization())
        if overlay_format.fontPointSize() > 0:
            merged.setFontPointSize(overlay_format.fontPointSize())
        if overlay_format.foreground().style() != QtCore.Qt.BrushStyle.NoBrush and \
                overlay_format.foreground().color().isValid():
            merged.setForeground(overlay_format.foreground())
        return merged

    def _apply_format_overlay(self, start, length, overlay_format):
        """
        Apply an overlay format while preserving existing character properties.
        """
        if length <= 0:
            return
        # Merge per character so pre-existing styles (e.g. an outer tag) remain
        # active when an inner tag adds additional formatting.
        run_start = start
        run_format = None
        for pos in range(start, start + length):
            merged = self._merged_char_format(self.format(pos), overlay_format)
            if run_format is None:
                run_format = merged
                run_start = pos
            elif merged != run_format:
                self.setFormat(run_start, pos - run_start, run_format)
                run_start = pos
                run_format = merged
        if run_format is not None:
            self.setFormat(run_start, start + length - run_start, run_format)

    def highlightBlock(self, text):
        """
        Highlight mis spelt words in a block of text.

        Note, this is a Qt hook.
        """
        if not self.spelling_dictionary:
            self._highlight_visual_tags(str(text))
            return
        text = str(text)
        char_format = QtGui.QTextCharFormat()
        char_format.setUnderlineColor(QtCore.Qt.GlobalColor.red)
        char_format.setUnderlineStyle(QtGui.QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        for word_object in re.finditer(self.WORDS, text):
            if not self.spelling_dictionary.check(word_object.group()):
                self.setFormat(word_object.start(), word_object.end() - word_object.start(), char_format)
        self._highlight_visual_tags(text)

    @staticmethod
    def _find_closing_tag_depth_aware(text, start_tag, end_tag, start_pos=0, start_depth=1):
        """
        Find the position of *end_tag* that balances *start_depth* open levels,
        scanning *text* from *start_pos*.  Nested occurrences of *start_tag*
        increment the depth counter so the returned position is the true outer
        close, not the first `end_tag` found.

        Returns -1 if no balanced close exists within *text*.
        """
        depth = start_depth
        pos = start_pos
        st_len = len(start_tag)
        et_len = len(end_tag)
        while pos < len(text):
            next_open = text.find(start_tag, pos)
            next_close = text.find(end_tag, pos)
            if next_close == -1:
                return -1
            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open + st_len
            else:
                depth -= 1
                if depth == 0:
                    return next_close
                pos = next_close + et_len
        return -1

    def _highlight_visual_tags(self, text):
        """
        Highlight formatting tags and split markers for a richer editing experience.

        Multi-line tags are handled via Qt's block-state mechanism:
          - state 0  : block ends outside any tag span (default / clean).
          - state N>0: block ends inside the span of html_tags[N-1].
        Each call sets ``currentBlockState`` so the next block can resume
        mid-span formatting through ``previousBlockState``.
        """
        if not self.rich_text_mode:
            self.setCurrentBlockState(0)
            return

        if not text:
            previous = self.previousBlockState()
            self.setCurrentBlockState(previous if previous > 0 else 0)
            return

        split_style = SpellTextEdit.split_marker_style_for_text(text)
        if split_style:
            self.setFormat(0, len(text), self._hidden_token_format())
            # Propagate the incoming span state through split-marker blocks so
            # formatting tags that straddle a split continue on the far side.
            prev = self.previousBlockState()
            self.setCurrentBlockState(prev if prev > 0 else 0)
            return

        if not self.formatting_tags_allowed:
            self.setCurrentBlockState(0)
            return

        try:
            html_tags = FormattingTags.get_html_tags()
        except Exception:
            html_tags = []

        known_tokens = set()
        for html in html_tags:
            if html.get('start tag'):
                known_tokens.add(html['start tag'])
            if html.get('end tag'):
                known_tokens.add(html['end tag'])

        hidden_fmt = self._hidden_token_format()
        unknown_fmt = self._unknown_token_format()
        start_map = {}
        end_map = {}
        token_set = set()
        for index, html in enumerate(html_tags):
            start_tag = html.get('start tag')
            end_tag = html.get('end tag')
            if start_tag and end_tag:
                start_map[start_tag] = index
                end_map[end_tag] = index
                token_set.add(start_tag)
                token_set.add(end_tag)

        token_regex = None
        if token_set:
            token_regex = re.compile('|'.join(re.escape(token) for token in sorted(token_set, key=len, reverse=True)))

        active_mask = self.previousBlockState()
        if active_mask < 0:
            active_mask = 0

        def apply_active_styles(start, length, mask):
            if length <= 0 or mask == 0:
                return
            for i, html in enumerate(html_tags):
                if mask & (1 << i):
                    tag_fmt = self._format_from_start_html(html.get('start html', ''))
                    self._apply_format_overlay(start, length, tag_fmt)

        pos = 0
        while pos < len(text):
            next_known = token_regex.search(text, pos) if token_regex else None
            nbsp_pos = text.find('&nbsp;', pos)

            next_pos = len(text)
            hit_type = None
            if next_known:
                next_pos = next_known.start()
                hit_type = 'known'
            if nbsp_pos != -1 and nbsp_pos < next_pos:
                next_pos = nbsp_pos
                hit_type = 'nbsp'

            if next_pos > pos:
                apply_active_styles(pos, next_pos - pos, active_mask)
                pos = next_pos

            if hit_type == 'known' and next_known:
                token = next_known.group(0)
                token_start = next_known.start()
                token_length = len(token)
                self.setFormat(token_start, token_length, hidden_fmt)
                if token in start_map:
                    active_mask |= (1 << start_map[token])
                elif token in end_map:
                    active_mask &= ~(1 << end_map[token])
                pos = token_start + token_length
            elif hit_type == 'nbsp':
                self.setFormat(pos, 6, hidden_fmt)
                pos += 6
            else:
                break

        self.setCurrentBlockState(active_mask)

        # ------------------------------------------------------------------
        # Final pass: ensure all inline tokens are hidden or flagged, and
        # &nbsp; entities are invisible.
        # ------------------------------------------------------------------
        for m in re.finditer(r'\{/?[^\}\s]+\}', text):
            tok = m.group(0)
            self.setFormat(m.start(), len(tok),
                           hidden_fmt if tok in known_tokens else unknown_fmt)
        for m in re.finditer(r'&nbsp;', text):
            self.setFormat(m.start(), 6, hidden_fmt)


class SpellAction(QtGui.QAction):
    """
    A special QAction that returns the text in a signal.
    """
    correct = QtCore.Signal(str)

    def __init__(self, *args):
        """
        Constructor
        """
        super(SpellAction, self).__init__(*args)
        self.triggered.connect(lambda x: self.correct.emit(self.text()))


class HistoryComboBox(QtWidgets.QComboBox):
    """
    The :class:`~openlp.core.common.historycombobox.HistoryComboBox` widget emulates the QLineEdit ``returnPressed``
    signal for when the :kbd:`Enter` or :kbd:`Return` keys are pressed, and saves anything that is typed into the edit
    box into its list.
    """
    returnPressed = QtCore.Signal()

    def __init__(self, parent=None):
        """
        Initialise the combo box, setting duplicates to False and the insert policy to insert items at the top.

        :param parent: The parent widget
        """
        super().__init__(parent)
        self.setDuplicatesEnabled(False)
        self.setEditable(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.InsertAtTop)

    def keyPressEvent(self, event):
        """
        Override the inherited keyPressEvent method to emit the ``returnPressed`` signal and to save the current text to
        the dropdown list.

        :param event: The keyboard event
        """
        # Handle Enter and Return ourselves
        if event.key() == QtCore.Qt.Key.Key_Enter or event.key() == QtCore.Qt.Key.Key_Return:
            # Emit the returnPressed signal
            self.returnPressed.emit()
            # Save the current text to the dropdown list
            if self.currentText() and self.findText(self.currentText()) == -1:
                self.insertItem(0, self.currentText())
        # Let the parent handle any keypress events
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        """
        Override the inherited focusOutEvent to save the current text to the dropdown list.

        :param event: The focus event
        """
        # Save the current text to the dropdown list
        if self.currentText() and self.findText(self.currentText()) == -1:
            self.insertItem(0, self.currentText())
        # Let the parent handle any keypress events
        super().focusOutEvent(event)

    def getItems(self):
        """
        Get all the items from the history

        :return: A list of strings
        """
        return [self.itemText(i) for i in range(self.count())]
