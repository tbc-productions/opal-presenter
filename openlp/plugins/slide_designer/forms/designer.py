"""Song slide canvas and inspector, independent of the theme editor."""
import copy
import math
import uuid

import fluentqt

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.display.render import ThemePreviewRenderer, render_tags
from openlp.core.display.screens import ScreenList
from openlp.core.lib.slidedesign import (
    apply_design, normalise_design, design_theme, image_to_png_uri, layer_order, remap_custom_footers, FILTER_RANGES
)
from openlp.core.lib.theme import Theme
from openlp.core.lib.slidelayouts import layout_for_slide, master_design, slide_design, set_slide_design, visual_design
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.fluenticons import fluent_icon
from openlp.core.widgets.dialogs import FileDialog
from .textediting import visible_text, replace_visible_text


def tr(text):
    return translate('SongsPlugin.SlideDesigner', text)


class CommandSurface(fluentqt.FluentWidget):
    """One Fluent surface for both command rows."""
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self.theme_tokens().colors.bgLayer)


class PreviewFooter(QtWidgets.QWidget):
    """Keep each label with its picker and wrap the preview group when space is tight."""
    def __init__(self, combo, parent):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.theme_group = None
        self.preview_group = self.group(QtWidgets.QLabel(tr('Preview')), combo)
        self.reflow(1000)

    def group(self, label, combo):
        group = QtWidgets.QWidget(self)
        row = QtWidgets.QHBoxLayout(group)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(label)
        row.addWidget(combo)
        return group

    def set_theme(self, label, combo):
        self.theme_group = self.group(label, combo)
        self.reflow(self.width())

    def reflow(self, width):
        layout = self.layout()
        wrapped = self.theme_group is not None and width < (
            self.theme_group.sizeHint().width() + self.preview_group.sizeHint().width() + layout.spacing())
        layout.removeWidget(self.preview_group)
        if self.theme_group is not None:
            layout.removeWidget(self.theme_group)
            layout.addWidget(self.theme_group, 0, 0, 1, 2 if wrapped else 1,
                             QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.preview_group, 1 if wrapped else 0, 0 if wrapped else 1, 1, 2 if wrapped else 1,
                         QtCore.Qt.AlignmentFlag.AlignRight)
        layout.setColumnStretch(0, 1)
        return layout.sizeHint().height()


class PropertyDrawer(fluentqt.Expander):
    """A section reset occupies the header's trailing action slot."""
    def __init__(self, caption, expanded=False):
        super().__init__(headerText=caption, expanded=expanded)
        self.setAccessibleName(caption)
        header = self.findChild(QtWidgets.QWidget, 'fluentExpanderHeader')
        self.reset_button = QtWidgets.QPushButton(header)
        self.reset_button.setIcon(fluent_icon('ic_fluent_arrow_reset_24_regular'))
        self.reset_button.setAccessibleName(tr('Reset {section}').format(section=caption))
        self.reset_button.setToolTip(self.reset_button.accessibleName())
        self.reset_button.setFluentSize(fluentqt.Button.ButtonSize.Small)
        self.reset_button.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)
        header.layout().insertWidget(header.layout().count() - 1, self.reset_button)
        self.reset_button.hide()
        self.disabled_opacity = QtWidgets.QGraphicsOpacityEffect(self)
        self.disabled_opacity.setOpacity(0.65)
        self.setGraphicsEffect(self.disabled_opacity)
        self.disabled_opacity.setEnabled(not self.isEnabled())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.EnabledChange and hasattr(self, 'disabled_opacity'):
            self.disabled_opacity.setEnabled(not self.isEnabled())


class PaneHandle(QtWidgets.QSplitterHandle):
    """A visible pane boundary with the splitter's native drag interaction."""
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._theme_host = fluentqt.FluentWidget(self)
        self._theme_host.hide()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setPen(QtGui.QPen(self._theme_host.theme_tokens().colors.strokeStrong, 1))
        if self.orientation() == QtCore.Qt.Orientation.Horizontal:
            painter.drawLine(self.width() // 2, 0, self.width() // 2, self.height())
        else:
            painter.drawLine(0, self.height() // 2, self.width(), self.height() // 2)


class PaneSplitter(QtWidgets.QSplitter):
    def createHandle(self):
        return PaneHandle(self.orientation(), self)


class PreviewBorder(fluentqt.FluentWidget):
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setPen(QtGui.QPen(self.theme_tokens().colors.strokeStrong, 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))


class DesignCommand(QtGui.QUndoCommand):
    """An entire gesture is one undo step; cancelling the song dialog never saves it."""
    def __init__(self, editor, before, after, caption):
        super().__init__(caption)
        self.editor, self.before, self.after = editor, before, after

    def undo(self):
        self.editor.restore(self.before)

    def redo(self):
        self.editor.restore(self.after)


class LayerList(QtWidgets.QListView):
    """Fluent layers list with an explicit, undoable internal move contract."""
    orderChanged = QtCore.Signal(list)
    selectionCleared = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setModel(QtGui.QStandardItemModel(self))
        self.setAccessibleName(tr('Layers'))
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setMinimumHeight(108)

    def mousePressEvent(self, event):
        empty = not self.indexAt(event.position().toPoint()).isValid()
        super().mousePressEvent(event)
        if empty:
            self.selectionCleared.emit()

    def identifiers(self):
        return [self.model().index(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
                for row in range(self.model().rowCount())]

    def startDrag(self, actions):
        drag = QtGui.QDrag(self)
        drag.setMimeData(self.model().mimeData(self.selectionModel().selectedRows()))
        drag.exec(QtCore.Qt.DropAction.MoveAction)

    def move_row(self, source, boundary):
        order = self.identifiers()
        if not 0 <= source < len(order):
            return
        selected = {index.data(QtCore.Qt.ItemDataRole.UserRole)
                    for index in self.selectionModel().selectedRows()}
        moving = [identifier for identifier in order if identifier in selected] if order[source] in selected \
            else [order[source]]
        destination = boundary - sum(identifier in moving for identifier in order[:boundary])
        order = [identifier for identifier in order if identifier not in moving]
        order[destination:destination] = moving
        if order != self.identifiers():
            self.orderChanged.emit(list(reversed(order)))

    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        index = self.indexAt(event.position().toPoint())
        boundary = self.model().rowCount()
        if index.isValid():
            boundary = index.row() + (event.position().y() > self.visualRect(index).center().y())
        self.move_row(self.currentIndex().row(), boundary)
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()


class SlideDesigner(QtWidgets.QWidget, RegistryProperties):
    """Theme-aware preview with song-local, portable design overrides."""
    def __init__(self, source_form):
        super().__init__(source_form)
        self.source_form = source_form
        self.design = {}
        self.document = {}
        self._canvas_size = QtCore.QSize(1920, 1080)
        self.selected = None
        self.base_theme = None
        self._background_image_cache = {}
        self.display = None
        self._creating_display = False
        self.pages = ['']
        self.page_index = 0
        self._refreshing = False
        self._canvas_editing = False
        self._canvas_text_context = None
        self._preview_revision = 0
        self._display_canvas_size = None
        self._capturing_preview = False
        self.undo_stack = QtGui.QUndoStack(self)
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(180)
        self.refresh_timer.timeout.connect(self.refresh)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tools = CommandSurface()
        toolbar = QtWidgets.QHBoxLayout(self.tools)
        toolbar.setContentsMargins(8, 4, 8, 2)
        toolbar.setSpacing(4)
        toolbar.addWidget(QtWidgets.QLabel(tr('Theme')))
        # The assigned-theme picker is inserted here by the owning dialog.
        toolbar.addSpacing(12)
        self.insert_object_buttons = []
        for caption, kind, icon in ((tr('Text'), 'text', fluent_icon('ic_fluent_textbox_24_regular')),
                                    (tr('Image'), 'image', UiIcons().blank_theme)):
            button = self.tool_button(caption, icon)
            button.clicked.connect(lambda checked=False, k=kind: self.add_element(k))
            toolbar.addWidget(button)
            self.insert_object_buttons.append(button)
        self.shape_button = self.tool_button(tr('Shape'), fluent_icon('ic_fluent_shapes_24_regular'))
        shape_menu = QtWidgets.QMenu(self.shape_button)
        for caption, kind in ((tr('Rectangle'), 'rectangle'), (tr('Ellipse'), 'ellipse')):
            action = shape_menu.addAction(caption)
            action.triggered.connect(lambda checked=False, k=kind: self.add_element(k))
        self.shape_button.setMenu(shape_menu)
        self.shape_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.insertWidget(3, self.shape_button)
        self.arrange_button = self.tool_button(tr('Arrange'), fluent_icon('ic_fluent_layer_24_regular'))
        arrange_menu = QtWidgets.QMenu(self.arrange_button)
        self.arrange_actions = {}
        for caption, direction, icon in (
                (tr('Bring to front'), 'front', 'position_to_front'),
                (tr('Bring forward'), 'forward', 'position_forward'),
                (tr('Send backward'), 'backward', 'position_backward'),
                (tr('Send to back'), 'back', 'position_to_back')):
            action = arrange_menu.addAction(fluent_icon(f'ic_fluent_{icon}_24_regular'), caption)
            action.triggered.connect(lambda checked=False, d=direction: self.arrange(d))
            self.arrange_actions[direction] = action
        arrange_menu.addSeparator()
        self.flip_actions = []
        for caption, axis in ((tr('Flip horizontal'), 'horizontal'), (tr('Flip vertical'), 'vertical')):
            action = arrange_menu.addAction(fluent_icon(f'ic_fluent_flip_{axis}_24_regular'), caption)
            action.triggered.connect(lambda checked=False, axis=axis: self.flip_objects(axis))
            self.flip_actions.append(action)
        self.arrange_button.setMenu(arrange_menu)
        self.arrange_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(self.arrange_button)
        self.align_button = self.tool_button(tr('Align'), fluent_icon('ic_fluent_align_left_24_regular'))
        align_menu = QtWidgets.QMenu(self.align_button)
        self.alignment_actions = {}
        for caption, operation, icon in (
                (tr('Align left'), 'left', 'align_left'),
                (tr('Align centre'), 'center', 'align_center_horizontal'),
                (tr('Align right'), 'right', 'align_right'),
                (tr('Align top'), 'top', 'align_top'),
                (tr('Align middle'), 'middle', 'align_center_vertical'),
                (tr('Align bottom'), 'bottom', 'align_bottom'),
                (tr('Distribute horizontally'), 'horizontal', 'align_space_evenly_horizontal'),
                (tr('Distribute vertically'), 'vertical', 'align_space_evenly_vertical')):
            if operation in ('top', 'horizontal'):
                align_menu.addSeparator()
            action = align_menu.addAction(fluent_icon(f'ic_fluent_{icon}_24_regular'), caption)
            action.triggered.connect(lambda checked=False, op=operation: self.align_objects(op))
            self.alignment_actions[operation] = action
        self.align_button.setMenu(align_menu)
        self.align_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(self.align_button)
        toolbar.addStretch()
        self.history_shortcuts = []
        self.history_actions = []
        for caption, icon, callback, signal in (
                (tr('Undo'), UiIcons().undo, self.undo_stack.undo, self.undo_stack.canUndoChanged),
                (tr('Redo'), UiIcons().redo, self.undo_stack.redo, self.undo_stack.canRedoChanged)):
            action = QtGui.QAction(icon, caption, self)
            action.triggered.connect(callback)
            action.setEnabled(False)
            signal.connect(action.setEnabled)
            self.history_actions.append(action)
            key = QtGui.QKeySequence.StandardKey.Undo if caption == tr('Undo') else QtGui.QKeySequence.StandardKey.Redo
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.history_shortcuts.append(shortcut)
        toolbar.addSpacing(8)
        self.inspector_button = self.tool_button(tr('Properties'), fluent_icon('ic_fluent_panel_right_24_regular'))
        self.inspector_button.setCheckable(True)
        self.inspector_button.setChecked(False)
        toolbar.addWidget(self.inspector_button)
        self.reset_button = self.tool_button(tr('Reset'), fluent_icon('ic_fluent_arrow_reset_24_regular'))
        self.reset_button.setToolTip(tr('Reset all slides to Theme'))
        self.reset_button.clicked.connect(lambda: self.reset_design(all_slides=True))
        toolbar.addWidget(self.reset_button)

        self.splitter = PaneSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        canvas_panel = QtWidgets.QWidget()
        canvas_layout = QtWidgets.QVBoxLayout(canvas_panel)
        canvas_layout.setContentsMargins(12, 6, 12, 12)
        canvas_layout.setSpacing(8)
        self.canvas_combo = QtWidgets.QComboBox()
        for caption, dimensions in ((tr('Full HD · 16:9'), (1920, 1080)),
                                    ('16:10 · 1920 × 1200', (1920, 1200)),
                                    ('21:9 · 2560 × 1080', (2560, 1080)),
                                    ('4:3 · 1440 × 1080', (1440, 1080))):
            self.canvas_combo.addItem(caption, dimensions)
        self.canvas_combo.setAccessibleName(tr('Canvas size'))
        self.canvas_combo.setFixedWidth(185)
        self.canvas_combo.currentIndexChanged.connect(self.change_canvas)
        layout_row = self.layout_row = QtWidgets.QHBoxLayout()
        layout_row.addWidget(self.heading(tr('Layout')))
        self.layout_combo = QtWidgets.QComboBox()
        self.layout_combo.setAccessibleName(tr('Master layout'))
        self.layout_combo.currentIndexChanged.connect(self.assign_layout)
        self.layout_combo.setFixedWidth(220)
        layout_row.addWidget(self.layout_combo)
        self.new_layout_button = self.tool_button(tr('New layout'), UiIcons().new, icon_only=True)
        self.new_layout_button.clicked.connect(self.new_layout)
        layout_row.addWidget(self.new_layout_button)
        self.rename_layout_button = self.tool_button(tr('Rename layout'), UiIcons().edit, icon_only=True)
        self.rename_layout_button.clicked.connect(self.rename_layout)
        layout_row.addWidget(self.rename_layout_button)
        self.delete_layout_button = self.tool_button(tr('Delete layout'), UiIcons().delete, icon_only=True)
        self.delete_layout_button.clicked.connect(self.delete_layout)
        layout_row.addWidget(self.delete_layout_button)
        layout_row.addStretch()
        canvas_layout.addLayout(layout_row)
        self.viewport = QtWidgets.QWidget()
        self.viewport.setMinimumSize(280, 180)
        self.preview_border = PreviewBorder(self.viewport)
        self.preview_border.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.preview_border.hide()
        self.viewport.installEventFilter(self)
        self.preview_cover = QtWidgets.QLabel(self.viewport)
        self.preview_cover.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_cover.hide()
        self.preview_timeout = QtCore.QTimer(self)
        self.preview_timeout.setSingleShot(True)
        self.preview_timeout.setInterval(5000)
        self.preview_timeout.timeout.connect(self.clear_preview_cover)
        self.preview_footer = PreviewFooter(self.canvas_combo, self.viewport)
        canvas_layout.addWidget(self.viewport, 1)
        self.splitter.addWidget(canvas_panel)
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setMinimumWidth(260)
        pane_layout = QtWidgets.QVBoxLayout(self.sidebar)
        pane_layout.setContentsMargins(12, 6, 12, 12)
        pane_layout.setSpacing(8)
        self.properties_heading = self.heading(tr('Properties'))
        pane_layout.addWidget(self.properties_heading)
        self.sidebar_scroll = QtWidgets.QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.sidebar_scroll.setAutoFillBackground(False)
        self.sidebar_scroll.viewport().setAutoFillBackground(False)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pane_layout.addWidget(self.sidebar_scroll, 1)
        sidebar_content = QtWidgets.QWidget()
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar_content)
        sidebar_layout.setContentsMargins(0, 0, 4, 0)
        sidebar_layout.setSpacing(8)
        self.build_layers()
        self.build_inspector()
        sidebar_layout.addWidget(self.inspector)
        sidebar_layout.addWidget(self.layers_panel)
        sidebar_layout.addStretch()
        self.sidebar_scroll.setWidget(sidebar_content)
        sidebar_content.setAutoFillBackground(False)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([700, 280])
        self.inspector_button.toggled.connect(self.update_sidebar)
        self.update_sidebar()
        layout.addWidget(self.splitter, 1)
        self.layers.selectionModel().selectionChanged.connect(self.select_layer)
        self.layers.orderChanged.connect(self.reorder_layers)
        self.layers.selectionCleared.connect(self.clear_selection)
        self.populate_inspector()

    @staticmethod
    def heading(caption):
        label = QtWidgets.QLabel(caption)
        label.setFluentTypography(fluentqt.FontRole.BodyStrong)
        label.setMinimumHeight(32)
        return label

    @staticmethod
    def tool_button(caption, icon, icon_only=False):
        button = QtWidgets.QToolButton()
        button.setText(caption)
        button.setAccessibleName(caption)
        button.setToolTip(caption)
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(18, 18))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly if icon_only else
                                  QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAutoRaise(True)
        button.setFixedHeight(32)
        if icon_only:
            button.setFixedWidth(32)
        return button

    def inspector_section(self, caption, expanded=False):
        drawer = PropertyDrawer(caption, expanded)
        drawer.setAccessibleName(caption)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        drawer.setOwnedContentWidget(content)
        self.properties_accordion.addOwnedItem(drawer)
        return drawer, layout

    def labelled_field(self, caption, field):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QtWidgets.QLabel(caption)
        label.setBuddy(field)
        field.setAccessibleName(caption)
        layout.addWidget(label)
        layout.addWidget(field)
        return container

    def update_sidebar(self):
        self.sidebar.setVisible(self.inspector_button.isChecked())

    def build_layers(self):
        self.layers_panel = PropertyDrawer(tr('Layers'), expanded=True)
        self.layers_panel.setAccessibleName(tr('Layers'))
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.layers = LayerList()
        layout.addWidget(self.layers, 1)
        controls = QtWidgets.QHBoxLayout()
        self.front_button = self.tool_button(tr('Bring forward'), UiIcons().arrow_up, icon_only=True)
        self.front_button.clicked.connect(lambda: self.arrange('forward'))
        self.back_button = self.tool_button(tr('Send backward'), UiIcons().arrow_down, icon_only=True)
        self.back_button.clicked.connect(lambda: self.arrange('backward'))
        controls.addWidget(self.front_button)
        controls.addWidget(self.back_button)
        controls.addStretch()
        self.delete_button = self.tool_button(tr('Delete layer'), UiIcons().delete, icon_only=True)
        self.delete_button.clicked.connect(self.delete_element)
        controls.addWidget(self.delete_button)
        layout.addLayout(controls)
        self.layers_panel.setOwnedContentWidget(content)

    def reset_design(self, all_slides=False):
        dialog = fluentqt.ContentDialog(self.window())
        dialog.setTitle(tr('Reset all slides?') if all_slides else tr('Reset slide?'))
        message = (tr('Change all slides to the Theme layout and clear their customisations?') if all_slides else
                   tr('Reset this slide to its assigned master layout?'))
        label = QtWidgets.QLabel(message)
        label.setWordWrap(True)
        dialog.setContent(label)
        dialog.setPrimaryButtonText(tr('Reset'))
        dialog.setCloseButtonText(tr('Cancel'))
        dialog.setDefaultButton(fluentqt.ContentDialogButton.Close)
        accepted = dialog.exec() == dialog.ResultPrimary
        dialog.deleteLater()
        if not accepted:
            return
        self.commit_text()
        document = copy.deepcopy(self.document)
        if all_slides:
            document['default_layout'] = 'theme'
            document.pop('assignments', None)
            document.pop('overrides', None)
            document.pop('hidden_footers', None)
        else:
            document.get('overrides', {}).pop(self.footer_key(), None)
            document['hidden_footers'] = [key for key in document.get('hidden_footers', [])
                                          if key != self.footer_key()]
        self.commit_document(document, tr('Reset all slides') if all_slides else tr('Reset slide'))

    def active_layout(self):
        identifier = layout_for_slide(self.document, self.footer_key())
        if identifier == 'default' and self.source_form.design_kind == 'song':
            return 'theme'
        return identifier

    def design_editable(self):
        return self.active_layout() != 'theme'

    def switch_design_context(self):
        self.commit_text()
        self.design = slide_design(self.document, self.footer_key())
        if self.document.get('hidden_footers'):
            self.design.update(version=1, hidden_footers=copy.deepcopy(self.document['hidden_footers']))
        self.sync_canvas()
        self.populate_inspector()
        self.schedule_refresh()

    def populate_layouts(self):
        with QtCore.QSignalBlocker(self.layout_combo):
            self.layout_combo.clear()
            self.layout_combo.addItem(tr('Theme'), 'theme')
            if self.source_form.design_kind != 'song' and (
                    visual_design(self.document) or 'default' in self.document.get('assignments', {}).values()):
                self.layout_combo.addItem(self.document.get('custom_layout_name', tr('Custom')), 'default')
            for identifier, master in self.document.get('masters', {}).items():
                self.layout_combo.addItem(master['name'], identifier)
            self.layout_combo.setCurrentIndex(self.layout_combo.findData(self.active_layout()))
        named = self.active_layout() not in ('default', 'theme')
        self.rename_layout_button.setEnabled(self.active_layout() != 'theme')
        self.delete_layout_button.setEnabled(named)

    def assign_layout(self):
        identifier = self.layout_combo.currentData()
        if identifier is None or identifier == self.active_layout():
            return
        self.commit_text()
        document = copy.deepcopy(self.document) or {'version': 1}
        document.setdefault('assignments', {})[self.footer_key()] = identifier
        if identifier == 'theme':
            document.get('overrides', {}).pop(self.footer_key(), None)
        self.commit_document(document, tr('Apply master layout'))

    def prompt_layout_name(self, title, name=''):
        dialog = fluentqt.ContentDialog(self.window())
        dialog.setObjectName('layout_name_dialog')
        dialog.setTitle(title)
        dialog.graphicsEffect().setEnabled(False)
        dialog.setSmokeEnabled(True)
        dialog.setDragEnabled(False)
        dialog.setMinimumWidth(420)
        dialog.setMaximumWidth(560)
        field = QtWidgets.QLineEdit()
        field.setObjectName('layout_name_edit')
        field.setAccessibleName(tr('Layout name'))
        field.setPlaceholderText(tr('Name'))
        field.setText(name)
        field.selectAll()
        dialog.setContent(field)
        caption = tr('Rename') if name else tr('Create')
        dialog.setPrimaryButtonText(caption)
        dialog.setCloseButtonText(tr('Cancel'))
        dialog.setDefaultButton(fluentqt.ContentDialogButton.Primary)
        primary = next(button for button in dialog.findChildren(fluentqt.Button) if button.text() == caption)
        field.textChanged.connect(lambda text: primary.setEnabled(bool(text.strip())))
        primary.setEnabled(bool(name.strip()))
        QtCore.QTimer.singleShot(0, field, field.setFocus)
        try:
            accepted = dialog.exec() == dialog.ResultPrimary
            return field.text().strip(), accepted
        finally:
            dialog.deleteLater()

    def new_layout(self):
        name, accepted = self.prompt_layout_name(tr('New layout'))
        if not accepted or not name.strip():
            return
        self.commit_text()
        identifier = str(uuid.uuid4())
        document = copy.deepcopy(self.document) or {'version': 1}
        document.setdefault('masters', {})[identifier] = {'name': name.strip(), 'design': visual_design(self.design)}
        document.setdefault('assignments', {})[self.footer_key()] = identifier
        document.get('overrides', {}).pop(self.footer_key(), None)
        self.commit_document(document, tr('Create master layout'))

    def rename_layout(self):
        identifier = self.active_layout()
        master = self.document.get('masters', {}).get(identifier)
        if identifier != 'default' and not master:
            return
        current_name = (self.document.get('custom_layout_name', tr('Custom'))
                        if identifier == 'default' else master['name'])
        name, accepted = self.prompt_layout_name(tr('Rename layout'), current_name)
        if accepted and name.strip():
            document = copy.deepcopy(self.document)
            if identifier == 'default':
                document['custom_layout_name'] = name.strip()
            else:
                document['masters'][identifier]['name'] = name.strip()
            self.commit_document(document, tr('Rename master layout'))

    def delete_layout(self):
        identifier = self.active_layout()
        if identifier not in self.document.get('masters', {}):
            return
        document = copy.deepcopy(self.document)
        # Preserve the appearance of every slide using a deleted layout as a local design.
        pages = [key for key, layout in document.get('assignments', {}).items() if layout == identifier]
        designs = {key: slide_design(document, key) for key in pages}
        del document['masters'][identifier]
        for key in pages:
            document.get('assignments', {}).pop(key, None)
            document = set_slide_design(document, key, designs[key])
        self.commit_document(document, tr('Delete master layout'))

    def build_inspector(self):
        self.inspector = QtWidgets.QWidget()
        self.inspector_layout = QtWidgets.QVBoxLayout(self.inspector)
        self.inspector_layout.setContentsMargins(0, 0, 0, 0)
        self.inspector_layout.setSpacing(8)
        self.selected_label = self.heading(tr('Slide text'))
        self.selected_label.hide()
        self.properties_accordion = fluentqt.Accordion()
        self.properties_accordion.setExpansionMode(fluentqt.Accordion.ExpansionMode.Multiple)
        self.inspector_layout.addWidget(self.properties_accordion)
        self.build_background_properties()
        self.fields = {}
        self.field_rows = {}
        for key, caption, low, high in (
                ('x', tr('X (px)'), 0, 16384), ('y', tr('Y (px)'), 0, 16384),
                ('width', tr('Width (px)'), 1, 16384), ('height', tr('Height (px)'), 1, 16384),
                ('rotation', tr('Rotation (°)'), -180, 180), ('opacity', tr('Opacity (%)'), 0, 100),
                ('font_size', tr('Size (pt)'), 1, 400)):
            field = fluentqt.NumberBox()
            field.setRange(low, high)
            field.setDisplayPrecision(0)
            field.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
            field.setMinimumWidth(0)
            field.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
            field.valueChanged.connect(lambda value, k=key: self.set_field_property(k, value))
            self.fields[key] = field
            self.field_rows[key] = self.labelled_field(caption, field)
        self.position_section, position_layout = self.inspector_section(tr('Position'))
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)
        for index, key in enumerate(('x', 'y', 'width', 'height', 'rotation')):
            grid.addWidget(self.field_rows[key], index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        position_layout.addLayout(grid)

        self.text_section, text_layout = self.inspector_section(tr('Typography'))
        self.font = QtWidgets.QFontComboBox()
        self.font.setMinimumWidth(0)
        self.font.setAccessibleName(tr('Font'))
        self.font.currentFontChanged.connect(lambda font: self.set_property('font', font.family()))
        text_layout.addWidget(self.font)
        style_row = QtWidgets.QHBoxLayout()
        style_row.addWidget(self.field_rows['font_size'], 1)
        for key, caption, icon in (('bold', tr('Bold'), UiIcons().bold),
                                   ('italic', tr('Italic'), UiIcons().italic)):
            field = self.tool_button(caption, icon, icon_only=True)
            field.setCheckable(True)
            field.toggled.connect(lambda value, k=key: self.set_property(k, value))
            self.fields[key] = field
            style_row.addWidget(field, 0, QtCore.Qt.AlignmentFlag.AlignBottom)
        text_layout.addLayout(style_row)
        self.align = QtWidgets.QComboBox()
        self.align.setAccessibleName(tr('Text alignment'))
        for caption, value in ((tr('Align left'), 'left'), (tr('Centre'), 'center'), (tr('Align right'), 'right')):
            self.align.addItem(caption, value)
        self.align.currentIndexChanged.connect(lambda: self.set_property('align', self.align.currentData()))
        text_layout.addWidget(self.align)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setFixedHeight(76)
        self.text.setAccessibleName(tr('Text box content'))
        self.text.textChanged.connect(self.text_changed)
        self.text_timer = QtCore.QTimer(self)
        self.text_timer.setSingleShot(True)
        self.text_timer.setInterval(350)
        self.text_timer.timeout.connect(self.commit_text)
        text_layout.addWidget(self.text)
        self._pending_text = None

        self.appearance_section, appearance_layout = self.inspector_section(tr('Appearance'))
        appearance_layout.addWidget(self.field_rows['opacity'])
        for key, caption in (('colour', tr('Text colour')), ('fill', tr('Fill'))):
            field = QtWidgets.QPushButton()
            field.setFluentSize(fluentqt.Button.ButtonSize.Small)
            field.setAccessibleName(caption)
            field.clicked.connect(lambda checked=False, k=key: self.choose_colour(k))
            self.fields[key] = field
            self.field_rows[key] = self.labelled_field(caption, field)
            appearance_layout.addWidget(self.field_rows[key])
        self.effect_sections = []
        for effect, caption in (('outline', tr('Outline')), ('shadow', tr('Shadow'))):
            section, effect_layout = self.inspector_section(caption)
            self.effect_sections.append(section)
            enabled = QtWidgets.QCheckBox(tr('Enabled'))
            enabled.setAccessibleName(caption)
            enabled.checkStateChanged.connect(
                lambda state, k=effect: self.set_property(k, state == QtCore.Qt.CheckState.Checked)
                if state != QtCore.Qt.CheckState.PartiallyChecked else None)
            self.fields[effect] = enabled
            effect_layout.addWidget(enabled)
            key = effect + '_colour'
            colour = QtWidgets.QPushButton()
            colour.setFluentSize(fluentqt.Button.ButtonSize.Small)
            colour.clicked.connect(lambda checked=False, k=key: self.choose_colour(k))
            self.fields[key] = colour
            self.field_rows[key] = self.labelled_field(tr('Colour'), colour)
            effect_layout.addWidget(self.field_rows[key])
            grid = QtWidgets.QGridLayout()
            grid.setSpacing(8)
            effect_layout.addLayout(grid)
            parameters = (('outline_width', tr('Width (px)'), 0, 40),) if effect == 'outline' else (
                ('shadow_x', tr('Offset X (px)'), -100, 100), ('shadow_y', tr('Offset Y (px)'), -100, 100),
                ('shadow_blur', tr('Blur (px)'), 0, 100))
            for index, (key, label, low, high) in enumerate(parameters):
                field = fluentqt.NumberBox()
                field.setRange(low, high)
                field.setDisplayPrecision(0)
                field.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
                field.setMinimumWidth(0)
                field.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
                field.valueChanged.connect(lambda value, k=key: self.set_property(k, value))
                self.fields[key] = field
                self.field_rows[key] = self.labelled_field(label, field)
                grid.addWidget(self.field_rows[key], index // 2, index % 2)

        self.build_filter_properties()
        self.reset_sections = {
            'effects': (self.filters_section, ()),
            'slide': (self.slide_section, ()),
            'background': (self.background_section, ('type', 'colour', 'end_colour', 'direction',
                                                     'image', 'image_opacity', 'fit')),
            'position': (self.position_section, ('x', 'y', 'width', 'height', 'rotation',
                                                 'flip_horizontal', 'flip_vertical')),
            'typography': (self.text_section, ('font', 'font_size', 'bold', 'italic', 'align')),
            'appearance': (self.appearance_section, ('opacity', 'colour', 'fill')),
            'outline': (self.effect_sections[0], ('outline', 'outline_width', 'outline_colour')),
            'shadow': (self.effect_sections[1], ('shadow', 'shadow_x', 'shadow_y', 'shadow_blur', 'shadow_colour')),
            'layers': (self.layers_panel, ())}
        for key, (drawer, _) in self.reset_sections.items():
            drawer.reset_button.clicked.connect(lambda checked=False, key=key: self.reset_section(key))

    def build_filter_properties(self):
        self.filters_section, layout = self.inspector_section(tr('Effects'))
        self.filter_fields = {}
        captions = {'blur': tr('Blur (px)'), 'brightness': tr('Brightness (%)'), 'contrast': tr('Contrast (%)'),
                    'grayscale': tr('Greyscale (%)'), 'hue-rotate': tr('Hue (°)'), 'invert': tr('Invert (%)'),
                    'saturate': tr('Saturation (%)'), 'sepia': tr('Sepia (%)')}
        for key, (default, low, high) in FILTER_RANGES.items():
            field = fluentqt.NumberBox()
            field.setRange(low, high)
            field.setDisplayPrecision(0)
            field.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
            field.setValue(default)
            field.setAccessibleName(captions[key])
            field.valueChanged.connect(lambda value, key=key: self.set_filter(key, value))
            layout.addWidget(self.labelled_field(captions[key], field))
            self.filter_fields[key] = field

    def filter_targets(self, design):
        if not self.selection:
            return [design]
        return [element for element in design.get('elements', [])
                if element['id'] in self.selection and element['kind'] == 'image']

    def populate_filters(self):
        targets = self.filter_targets(self.design)
        self.filters_section.setEnabled(bool(targets))
        property_name = 'filters' if self.selection else 'background_filters'
        for key, field in self.filter_fields.items():
            values = [target.get(property_name, {}).get(key, FILTER_RANGES[key][0]) for target in targets]
            common = values[0] if values and all(value == values[0] for value in values) else float('nan')
            with QtCore.QSignalBlocker(field):
                field.setValue(common)

    def set_filter(self, key, value):
        if not math.isfinite(value):
            return
        design = self.editable_design()
        property_name = 'filters' if self.selection else 'background_filters'
        for target in self.filter_targets(design):
            target.setdefault(property_name, {})[key] = value
        self.commit(design, tr('Change effects'))

    def build_background_properties(self):
        self.slide_section, slide_layout = self.inspector_section(tr('Slide'))
        self.show_footer = QtWidgets.QCheckBox(tr('Show footer'))
        self.show_footer.toggled.connect(self.set_footer_visible)
        slide_layout.addWidget(self.show_footer)
        self.background_section, layout = self.inspector_section(tr('Background'))
        self.background_type = QtWidgets.QComboBox()
        for caption, value in ((tr('Theme'), 'theme'), (tr('Colour'), 'solid'), (tr('Gradient'), 'gradient')):
            self.background_type.addItem(caption, value)
        self.background_type.setAccessibleName(tr('Background fill'))
        self.background_type.currentIndexChanged.connect(self.background_type_changed)
        layout.addWidget(self.background_type)
        colour_row = QtWidgets.QHBoxLayout()
        colour_row.setSpacing(8)
        layout.addLayout(colour_row)
        self.background_colours = {}
        self.background_rows = {}
        for key, caption in (('colour', tr('Colour')), ('end_colour', tr('End colour'))):
            button = QtWidgets.QPushButton()
            button.setFluentSize(fluentqt.Button.ButtonSize.Small)
            button.clicked.connect(lambda checked=False, k=key: self.choose_background_colour(k))
            self.background_colours[key] = button
            self.background_rows[key] = self.labelled_field(caption, button)
            colour_row.addWidget(self.background_rows[key], 1)
        self.background_direction = QtWidgets.QComboBox()
        for caption, value in ((tr('Top to bottom'), 'vertical'), (tr('Left to right'), 'horizontal'),
                               (tr('Top left to bottom right'), 'leftTop'),
                               (tr('Bottom left to top right'), 'leftBottom'), (tr('Radial'), 'circular')):
            self.background_direction.addItem(caption, value)
        self.background_direction.currentIndexChanged.connect(
            lambda: self.set_background_property('direction', self.background_direction.currentData()))
        self.background_rows['direction'] = self.labelled_field(tr('Direction'), self.background_direction)
        layout.addWidget(self.background_rows['direction'])
        layout.addWidget(fluentqt.Divider(QtCore.Qt.Orientation.Horizontal))
        image_layout = layout
        row = QtWidgets.QHBoxLayout()
        self.background_image_button = self.tool_button(tr('Choose image'), UiIcons().blank_theme)
        self.background_image_button.clicked.connect(self.choose_background_image)
        row.addWidget(self.background_image_button)
        self.remove_background_image = self.tool_button(tr('Remove image'), UiIcons().delete, icon_only=True)
        self.remove_background_image.clicked.connect(lambda: self.set_background_property('image', None))
        row.addWidget(self.remove_background_image)
        image_layout.addLayout(row)
        self.background_image_opacity = fluentqt.NumberBox()
        self.background_image_opacity.setRange(0, 100)
        self.background_image_opacity.setDisplayPrecision(0)
        self.background_image_opacity.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
        self.background_image_opacity.valueChanged.connect(
            lambda value: self.set_background_property('image_opacity', value))
        image_layout.addWidget(self.labelled_field(tr('Image opacity (%)'), self.background_image_opacity))
        self.background_fit = QtWidgets.QComboBox()
        for caption, value in ((tr('Fill'), 'cover'), (tr('Fit'), 'contain'), (tr('Stretch'), 'stretch'),
                               (tr('Tile'), 'repeat')):
            self.background_fit.addItem(caption, value)
        self.background_fit.currentIndexChanged.connect(
            lambda: self.set_background_property('fit', self.background_fit.currentData()))
        image_layout.addWidget(self.labelled_field(tr('Image size'), self.background_fit))

    def background_properties(self, defaults=False):
        if not defaults and self.design.get('background'):
            return copy.deepcopy(self.design['background'])
        theme = self.base_theme or self.resolve_theme()
        result = {'type': 'solid', 'colour': '#000000', 'end_colour': '#ffffff',
                  'direction': 'vertical', 'image_opacity': 100, 'fit': 'cover'}
        if isinstance(theme, Theme):
            gradient = theme.background_type == 'gradient'
            result.update(type='gradient' if gradient else 'solid',
                          colour=theme.background_start_color if gradient else theme.background_color,
                          end_colour=theme.background_end_color, direction=theme.background_direction,
                          fit=theme.background_fit)
            if theme.background_type == 'image' and theme.background_filename:
                result['colour'] = theme.background_border_color
                source = str(theme.background_filename)
                if source not in self._background_image_cache:
                    try:
                        self._background_image_cache[source] = (source if source.startswith('data:image/png;base64,')
                                                                else image_to_png_uri(theme.background_filename)[0])
                    except ValueError:
                        self._background_image_cache[source] = None
                if self._background_image_cache[source]:
                    result['image'] = self._background_image_cache[source]
        return result

    def populate_background(self):
        background = self.background_properties()
        kind = background['type'] if self.design.get('background') else 'theme'
        for field, value in ((self.background_type, kind), (self.background_direction, background['direction']),
                             (self.background_fit, background['fit'])):
            blocker = QtCore.QSignalBlocker(field)
            field.setCurrentIndex(field.findData(value))
            del blocker
        for key, button in self.background_colours.items():
            colour = background[key]
            button.setText(colour.upper())
            swatch = QtGui.QPixmap(16, 16)
            swatch.fill(QtGui.QColor(colour))
            button.setIcon(QtGui.QIcon(swatch))
        self.background_rows['colour'].setVisible(kind != 'theme')
        for key in ('end_colour', 'direction'):
            self.background_rows[key].setVisible(kind == 'gradient')
        blocker = QtCore.QSignalBlocker(self.background_image_opacity)
        self.background_image_opacity.setValue(background['image_opacity'])
        del blocker
        has_image = bool(background.get('image'))
        self.background_image_button.setText(tr('Replace image') if has_image else tr('Choose image'))
        self.background_image_opacity.setEnabled(has_image)
        self.background_fit.setEnabled(has_image)
        self.remove_background_image.setEnabled(has_image)

    def background_type_changed(self):
        kind = self.background_type.currentData()
        if kind == 'theme':
            design = self.editable_design()
            design.pop('background', None)
            self.commit(design, tr('Use theme background'))
        else:
            self.set_background_property('type', kind)

    def set_background_property(self, key, value):
        design = self.editable_design()
        background = self.background_properties()
        if value is None:
            background.pop(key, None)
        else:
            background[key] = value
        design['background'] = background
        self.commit(design, tr('Change slide background'))

    def choose_background_colour(self, key):
        colour = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.background_properties()[key]), self)
        if colour.isValid():
            self.set_background_property(key, colour.name())

    def choose_background_image(self):
        path, _ = FileDialog.getOpenFileName(
            self, tr('Background image'), filter=tr('Images (*.png *.jpg *.jpeg *.webp)'))
        if not path:
            return
        try:
            uri, _ = image_to_png_uri(path)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, tr('Background image'), tr('This image could not be embedded.'))
            return
        self.set_background_property('image', uri)

    def canvas_size(self):
        return self._canvas_size

    def change_canvas(self):
        dimensions = self.canvas_combo.currentData()
        if not dimensions or tuple(dimensions) == (self.canvas_size().width(), self.canvas_size().height()):
            return
        self.commit_text()
        if not self.design_editable():
            self._canvas_size = QtCore.QSize(*dimensions)
            self.fit_canvas()
            self.schedule_refresh()
            return
        old = self.canvas_size()
        width, height = dimensions
        design = self.editable_design()
        reference_width = design.setdefault('reference_width', old.width())
        reference_height = design.setdefault('reference_height', old.height())
        old_scale = min(old.width() / reference_width, old.height() / reference_height)
        scale = min(width / reference_width, height / reference_height) / old_scale
        # Fit the entire layout around the canvas centre. Moving each object's centre independently
        # would break aligned edges and even spacing when objects have different dimensions.
        design['lyrics'] = self.selected_properties('lyrics')
        for element in [design['lyrics']] + design['elements']:
            for axis, extent, previous, current in (('x', 'width', old.width(), width),
                                                    ('y', 'height', old.height(), height)):
                position = element[axis] / 100 * previous
                element[axis] = ((position - previous / 2) * scale + current / 2) / current * 100
                element[extent] *= previous * scale / current
            for key in ('font_size', 'outline_width', 'shadow_x', 'shadow_y', 'shadow_blur', 'border_width'):
                if key in element:
                    element[key] *= scale
        design.update(canvas_width=width, canvas_height=height)
        self.commit(design, tr('Resize canvas'))

    def sync_canvas(self):
        if self.design.get('canvas_width'):
            self._canvas_size = QtCore.QSize(round(self.design['canvas_width']), round(self.design['canvas_height']))
        dimensions = (self.canvas_size().width(), self.canvas_size().height())
        with QtCore.QSignalBlocker(self.canvas_combo):
            index = next((i for i in range(self.canvas_combo.count())
                          if tuple(self.canvas_combo.itemData(i)) == dimensions), -1)
            if index < 0:
                self.canvas_combo.addItem(f'{dimensions[0]} × {dimensions[1]}', dimensions)
                index = self.canvas_combo.count() - 1
            self.canvas_combo.setCurrentIndex(index)
        self.fit_canvas()

    def set_field_property(self, key, value):
        if key in ('x', 'width', 'y', 'height'):
            dimension = self.canvas_size().width() if key in ('x', 'width') else self.canvas_size().height()
            value = value / dimension * 100
        self.set_property(key, value)

    def showEvent(self, event):
        super().showEvent(event)
        # Deferred creation avoids a WebEngine process for song import/maintenance dialogs.
        if self._creating_display:
            return
        if self.display is None:
            # WebEngine startup processes native events and can re-enter showEvent before
            # the constructor returns. A second renderer would obscure the preview.
            self._creating_display = True
            try:
                if isinstance(self.resolve_theme(), Theme):
                    self.display = ThemePreviewRenderer(self.viewport, embedded=True, can_show_startup_screen=False,
                                                        after_loaded_callback=self.schedule_refresh)
                    self.display.allow_theme_transitions = False
                    self.display.allow_item_transitions = False
                    self.display.webview.setToolTip(tr('Double-click lyrics or a text box to edit. '
                                                       'Hold Alt while dragging to bypass snapping.'))
                    self.display.display_watcher.register_event_listener(
                        'songDesignChanged', self.canvas_changed, False)
                    self.display.display_watcher.register_event_listener(
                        'designPreviewReady', self.preview_ready, False)
                    self.display.display_watcher.register_event_listener(
                        'songDesignTextEditing', self.canvas_text_editing, False)
                    self.display.display_watcher.register_event_listener(
                        'songDesignTextChanged', self.canvas_text_changed, False)
                    self.display.show()
                    self.fit_canvas()
            finally:
                self._creating_display = False
        self.schedule_refresh()

    def hideEvent(self, event):
        self.refresh_timer.stop()
        self.text_timer.stop()
        self.clear_preview_cover()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.viewport and event.type() == QtCore.QEvent.Type.Resize:
            self.fit_canvas()
        if watched is self.viewport and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self.clear_selection()
        return super().eventFilter(watched, event)

    def fit_canvas(self):
        if self.display is None or self._capturing_preview:
            return
        size = self.canvas_size()
        if self._display_canvas_size is not None and size != self._display_canvas_size:
            self.freeze_preview()
        self._display_canvas_size = QtCore.QSize(size)
        footer_height = self.preview_footer.reflow(max(1, self.viewport.width() - 24))
        gap = 10
        total_footer_space = footer_height + gap
        avail_h = max(1, self.viewport.height() - 24 - total_footer_space)
        scale = min(max(1, self.viewport.width() - 24) / size.width(),
                    avail_h / size.height())
        width, height = round(size.width() * scale), round(size.height() * scale)
        wrapped_height = self.preview_footer.reflow(width)
        if wrapped_height != footer_height:
            footer_height = wrapped_height
            total_footer_space = footer_height + gap
            scale = min(max(1, self.viewport.width() - 24) / size.width(),
                        max(1, self.viewport.height() - 24 - total_footer_space) / size.height())
            width, height = round(size.width() * scale), round(size.height() * scale)
        left = (self.viewport.width() - width) // 2
        top = max(4, (self.viewport.height() - (height + total_footer_space)) // 2)
        self.display.setGeometry(left, top, width, height)
        self.display.set_scale(scale)
        self.preview_border.setGeometry(left - 1, top - 1, width + 2, height + 2)
        self.preview_border.show()
        self.preview_border.raise_()
        self.preview_footer.setGeometry(left, top + height + gap, width, footer_height)
        self.preview_footer.raise_()
        self.preview_cover.setGeometry(self.viewport.rect())
        if not self.preview_cover.isHidden():
            self.preview_cover.raise_()

    def freeze_preview(self):
        if not self.display or not self.display._is_initialised or not self.isVisible():
            return
        self._preview_revision += 1
        self.preview_timeout.stop()
        # Keep the first completed frame during rapid switches, never capture an intermediate render.
        if self.preview_cover.isHidden():
            # QWidget.grab() can synchronously deliver pending resize events.
            self._capturing_preview = True
            try:
                snapshot = self.viewport.grab()
            finally:
                self._capturing_preview = False
            self.preview_cover.setPixmap(snapshot)
            self.preview_cover.setGeometry(self.viewport.rect())
            self.preview_cover.show()
            self.preview_cover.raise_()
            self.preview_cover.repaint()

    def clear_preview_cover(self):
        self._preview_revision += 1
        self.preview_timeout.stop()
        self.preview_cover.hide()
        self.preview_cover.clear()

    def preview_ready(self, revision):
        if revision == self._preview_revision:
            self.clear_preview_cover()

    def resolve_theme(self):
        theme_name = self.source_form.designer_theme_name()
        manager = self.theme_manager
        if not manager:
            return None
        global_name = manager.global_theme
        names = manager.get_theme_names()
        if theme_name not in names:
            theme_name = global_name
        return manager.get_theme_data(theme_name)

    def schedule_refresh(self, *args):
        if not self.preview_cover.isHidden():
            self._preview_revision += 1
            self.preview_timeout.stop()
        if not self._refreshing:
            self.refresh_timer.start()

    def refresh(self):
        if (not self.display or not self.display._is_initialised or not self.isVisible()
                or self._refreshing or self._canvas_editing):
            return
        self._refreshing = True
        revision = self._preview_revision
        try:
            # Pagination temporarily resets the theme and slide content in the browser.
            # Cover that work for text/style changes as well as canvas-size changes.
            self.freeze_preview()
            revision = self._preview_revision
            self.base_theme = copy.deepcopy(self.resolve_theme())
            output = ScreenList().current.display_geometry.size()
            canvas = self.canvas_size()
            for part in ('main', 'footer'):
                for key, previous, current in (('x', output.width(), canvas.width()),
                                               ('width', output.width(), canvas.width()),
                                               ('y', output.height(), canvas.height()),
                                               ('height', output.height(), canvas.height())):
                    attr = 'font_' + part + '_' + key
                    setattr(self.base_theme, attr, getattr(self.base_theme, attr) * current / previous)
            preview_design = copy.deepcopy(self.design)
            self.base_theme = design_theme(self.base_theme, preview_design, self.canvas_size())
            theme = apply_design(self.base_theme, preview_design, self.canvas_size())
            self.display.run_in_display('setDesignEditor', None)
            # Keep page identities stable when a master or local text box is customised.
            pagination_theme = apply_design(
                self.base_theme, master_design(self.document, self.document.get('default_layout', 'default')),
                self.canvas_size())
            self.display.set_theme(pagination_theme, is_sync=True)
            text = self.source_form.designer_text()
            self.pages = []
            self.page_keys = []
            for split_index, section in enumerate(text.split('[--}{--]')):
                pages = self.display.format_slide(section.lstrip('\n'), None) or ['']
                self.pages.extend(pages)
                self.page_keys.extend((split_index, index) for index in range(len(pages)))
            self.pages = self.pages or ['']
            if hasattr(self.source_form, '_preview_split'):
                split = self.source_form._preview_split
                self.page_index = next((i for i, key in enumerate(self.page_keys) if key[0] == split), 0)
                del self.source_form._preview_split
            self.page_index = min(self.page_index, len(self.pages) - 1)
            self.display.set_theme(theme, is_sync=True)
            self.show_page()
            self.populate_inspector()
            if not self.preview_cover.isHidden() and revision == self._preview_revision:
                self.preview_timeout.start()
                self.display.run_in_display('waitForDesignPreview', revision, return_event_name='designPreviewReady')
        except Exception:
            self.clear_preview_cover()
            raise
        finally:
            self._refreshing = False
            if revision != self._preview_revision and not self.preview_cover.isHidden():
                self.schedule_refresh()

    def footer_key(self):
        section = self.source_form.designer_section_key()
        split, page = (self.page_keys[self.page_index] if getattr(self, 'page_keys', [])
                       else (getattr(self.source_form, '_preview_split', 0), 0))
        return f'{section}:{split}:{page}'

    def set_footer_visible(self, visible):
        document = copy.deepcopy(self.document) or {'version': 1}
        hidden = set(document.get('hidden_footers', []))
        hidden.discard(self.footer_key()) if visible else hidden.add(self.footer_key())
        document['hidden_footers'] = sorted(hidden)
        self.commit_document(document, tr('Change slide footer'))

    def show_page(self):
        if not self.display or not self.display._is_initialised:
            return
        self.display.load_verses([{'verse': 'designer', 'text': render_tags(self.pages[self.page_index]),
                                   'footer': '' if self.footer_key() in self.design.get('hidden_footers', [])
                                   else self.source_form.designer_footer()}])
        self.display.go_to_slide('designer', raise_window=False)
        self.display.run_in_display('setDesignEditor', (self.selection or '') if self.design_editable() else None)
        self.prepare_canvas_text()

    def prepare_canvas_text(self):
        """Map this rendered page to its source, including automatic pagination and repeated lines."""
        from .slidegrid import slide_rows
        source = self.source_form.design_text_editor.toPlainText()
        section = max(0, self.source_form.section_combo_box.currentIndex())
        split = self.page_keys[self.page_index][0] if getattr(self, 'page_keys', []) else 0
        row = next((row for row in slide_rows(source, self.source_form.design_kind)
                    if row.section == section and row.split == split), None)
        sources = {}
        self._canvas_text_context = None
        if row:
            plain, spans = visible_text(source[row.start:row.end])
            offset = 0
            for index, page in enumerate(self.pages):
                if getattr(self, 'page_keys', []) and self.page_keys[index][0] != split:
                    continue
                text = visible_text(page)[0].strip('\n')
                start = plain.find(text, offset)
                if start < 0:
                    break
                offset = start + len(text)
                if index == self.page_index:
                    sources['lyrics'] = text
                    self._canvas_text_context = (source, text,
                                                 [(a + row.start, b + row.start) for a, b in
                                                  spans[start:offset]], row.start)
                    break
        if self.design_editable():
            sources.update({element['id']: element.get('text', '') for element in self.design.get('elements', [])
                            if element['kind'] == 'text'})
        self.display.run_in_display('setDesignTextSources', sources)

    def canvas_text_editing(self, editing):
        self._canvas_editing = bool(editing)
        if editing:
            self.refresh_timer.stop()
        # Chromium owns normal text undo/redo until the editing session is committed.
        for shortcut in self.history_shortcuts:
            shortcut.setEnabled(not editing)

    def canvas_text_changed(self, value):
        if hasattr(value, 'toVariant'):
            value = value.toVariant()
        self.canvas_text_editing(False)
        if not isinstance(value, dict) or value.get('cancelled') or value.get('text') == value.get('before'):
            return
        identifier, text = value.get('id'), value.get('text')
        if not isinstance(text, str):
            return
        if identifier == 'lyrics' and self._canvas_text_context:
            from .slidegrid import qt_length
            source, before, spans, empty_position = self._canvas_text_context
            editor = self.source_form.design_text_editor
            if source != editor.toPlainText() or before != value.get('before'):
                self.schedule_refresh()
                return
            if spans:
                updated = replace_visible_text(source, spans, before, text)
            else:
                import html
                updated = source[:empty_position] + html.escape(text, quote=False) + source[empty_position:]
            # One source edit produces one shared undo command and updates the Lyrics/Slides sidebar.
            prefix = 0
            while prefix < min(len(source), len(updated)) and source[prefix] == updated[prefix]:
                prefix += 1
            suffix = 0
            while (suffix < min(len(source), len(updated)) - prefix
                   and source[len(source) - suffix - 1] == updated[len(updated) - suffix - 1]):
                suffix += 1
            with QtCore.QSignalBlocker(editor):
                cursor = editor.textCursor()
                cursor.setPosition(qt_length(source[:prefix]))
                cursor.setPosition(qt_length(source[:len(source) - suffix]), QtGui.QTextCursor.MoveMode.KeepAnchor)
                cursor.insertText(updated[prefix:len(updated) - suffix])
                editor.setTextCursor(cursor)
            editor.textChanged.emit()
        elif self.design_editable():
            design = self.editable_design()
            target = self.design_target(design, identifier)
            if target and target.get('kind') == 'text' and target.get('text', '') == value.get('before'):
                target['text'] = text
                self.commit(design, tr('Edit text box'))
        self.schedule_refresh()

    def change_page(self, delta):
        self.commit_text()
        self.page_index = max(0, min(self.page_index + delta, len(self.pages) - 1))
        self.switch_design_context()

    def load_design(self, value):
        if self._canvas_editing and self.display and self.display._is_initialised:
            self.display.run_in_display('finishDesignTextEdit', True, False, is_sync=True)
        self.canvas_text_editing(False)
        self._canvas_text_context = None
        self.text_timer.stop()
        self._pending_text = None
        self.selected = None
        self.page_index = 0
        self.page_keys = []
        self.document = normalise_design(value)
        self.design = slide_design(self.document, self.footer_key())
        if self.document.get('hidden_footers'):
            self.design.update(version=1, hidden_footers=copy.deepcopy(self.document['hidden_footers']))
        self._canvas_size = (ScreenList().current.display_geometry.size() if self.design and
                             'canvas_width' not in self.design else QtCore.QSize(1920, 1080))
        self._legacy_canvas_size = self._canvas_size
        self.sync_canvas()
        self._background_image_cache.clear()
        self.undo_stack.clear()
        self.populate_inspector()
        self.schedule_refresh()

    def serialised_design(self):
        self.commit_text()
        return normalise_design(self.document)

    def restore(self, design):
        self.document = copy.deepcopy(design)
        self._canvas_size = (getattr(self, '_legacy_canvas_size', QtCore.QSize(1920, 1080))
                             if design and 'canvas_width' not in design else QtCore.QSize(1920, 1080))
        self.switch_design_context()

    def commit(self, design, caption):
        if not self.design_editable():
            return
        document = copy.deepcopy(self.document) or {'version': 1}
        document = set_slide_design(document, self.footer_key(), design)
        if design.get('hidden_footers'):
            document['hidden_footers'] = copy.deepcopy(design['hidden_footers'])
        else:
            document.pop('hidden_footers', None)
        if document:
            document['version'] = 1
        self.commit_document(document, caption)

    def commit_document(self, document, caption):
        document = normalise_design(document)
        if document != self.document:
            self.undo_stack.push(DesignCommand(self, copy.deepcopy(self.document), document, caption))

    def editable_design(self):
        design = copy.deepcopy(self.design) or {'version': 1, 'lyrics': {}, 'elements': []}
        design.setdefault('canvas_width', self.canvas_size().width())
        design.setdefault('canvas_height', self.canvas_size().height())
        return design

    @property
    def selected(self):
        return self.selection[-1] if self.selection else None

    @selected.setter
    def selected(self, identifier):
        self.selection = [identifier] if identifier else []

    def selected_properties(self, identifier=None, defaults=False):
        identifier = identifier or self.selected
        if identifier == 'lyrics':
            theme = self.base_theme
            properties = {'x': 5, 'y': 5, 'width': 90, 'height': 85, 'font_size': 40, 'font': 'Arial'}
            if isinstance(theme, Theme):
                size = self.canvas_size()
                for key, dimension in (('x', size.width()), ('width', size.width()),
                                       ('y', size.height()), ('height', size.height())):
                    properties[key] = getattr(theme, 'font_main_' + key) / dimension * 100
                properties.update(font=theme.font_main_name, colour=theme.font_main_color,
                                  font_size=theme.font_main_size, bold=theme.font_main_bold,
                                  italic=theme.font_main_italics,
                                  align=('left', 'right', 'center', 'left')[theme.display_horizontal_align],
                                  outline=theme.font_main_outline, outline_width=theme.font_main_outline_size * 4 / 3,
                                  outline_colour=theme.font_main_outline_color, shadow=theme.font_main_shadow,
                                  shadow_x=theme.font_main_shadow_size * 4 / 3,
                                  shadow_y=theme.font_main_shadow_size * 4 / 3,
                                  shadow_blur=theme.font_main_shadow_blur * 4 / 3,
                                  shadow_colour=theme.font_main_shadow_color)
            if not defaults:
                properties.update(self.design.get('lyrics', {}))
            return properties
        properties = dict(next((e for e in self.design.get('elements', []) if e['id'] == identifier), {}))
        if properties.get('kind') in ('rectangle', 'ellipse', 'image') and properties.get('border_width'):
            properties.setdefault('outline', True)
            properties.setdefault('outline_width', properties['border_width'])
            properties.setdefault('outline_colour', properties.get('border_colour', '#ffffff'))
        return properties

    def populate_inspector(self, rebuild_layers=True):
        self.populate_layouts()
        self.selection = [identifier for identifier in self.selection if identifier in layer_order(self.design)]
        multiple = len(self.selection) > 1
        if rebuild_layers:
            selection = self.layers.selectionModel()
            selection.blockSignals(True)
            model = self.layers.model()
            model.clear()
            labels = {'text': tr('Text'), 'rectangle': tr('Rectangle'), 'ellipse': tr('Ellipse'), 'image': tr('Image')}
            elements = {element['id']: element for element in self.design.get('elements', [])}
            for identifier in reversed(layer_order(self.design)):
                element = elements.get(identifier)
                label = tr('Slide text') if element is None else labels[element['kind']]
                if element and element['kind'] == 'text' and element.get('text', '').strip():
                    label = element['text'].strip().splitlines()[0][:60]
                icon = (UiIcons().blank_theme if element and element['kind'] == 'image' else
                        fluent_icon('ic_fluent_shapes_24_regular')
                        if element and element['kind'] in ('rectangle', 'ellipse')
                        else fluent_icon('ic_fluent_textbox_24_regular'))
                item = QtGui.QStandardItem(icon, label)
                item.setData(identifier, QtCore.Qt.ItemDataRole.UserRole)
                item.setToolTip(label)
                item.setDropEnabled(False)
                model.appendRow(item)
                if identifier in self.selection:
                    selection.select(item.index(), QtCore.QItemSelectionModel.SelectionFlag.Select)
                    if identifier == self.selected:
                        selection.setCurrentIndex(item.index(), QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)
                        self.selected_label.setText(label)
            selection.blockSignals(False)
            self.layers.setFixedHeight(max(108, min(240, model.rowCount() * 40 + 8)))
        order = layer_order(self.design)
        can_forward = any(identifier in self.selection and order[index + 1] not in self.selection
                          for index, identifier in enumerate(order[:-1]))
        can_back = any(identifier in self.selection and order[index - 1] not in self.selection
                       for index, identifier in enumerate(order) if index)
        self.front_button.setEnabled(can_forward)
        self.back_button.setEnabled(can_back)
        for direction, action in self.arrange_actions.items():
            action.setEnabled(can_forward if direction in ('front', 'forward') else can_back)
        for operation, action in self.alignment_actions.items():
            minimum = 3 if operation in ('horizontal', 'vertical') else 1
            action.setEnabled(len(self.selection) >= minimum)
        for action in self.flip_actions:
            action.setEnabled(bool(self.selection))
        self.delete_button.setEnabled(any(identifier != 'lyrics' for identifier in self.selection))
        selected = [self.selected_properties(identifier) for identifier in self.selection]
        has_text = any(self.supports_property(identifier, 'font') for identifier in self.selection)
        self.position_section.setEnabled(bool(self.selection))
        self.appearance_section.setEnabled(bool(self.selection))
        for section in self.effect_sections:
            section.setEnabled(bool(self.selection))
        if self.selected is not None:
            for index in range(self.layers.model().rowCount()):
                item = self.layers.model().item(index)
                if item.data(QtCore.Qt.ItemDataRole.UserRole) == self.selected:
                    self.selected_label.setText(item.text())
                    break
        if multiple:
            self.selected_label.setText(tr('{count} objects').format(count=len(self.selection)))
        with QtCore.QSignalBlocker(self.show_footer):
            self.show_footer.setChecked(self.footer_key() not in self.design.get('hidden_footers', []))
        self.populate_background()
        self.populate_filters()
        if self.selected is None:
            self.layers.clearSelection()
            self.selected_label.setText(tr('Slide'))
        defaults = {'opacity': 100, 'outline_width': 2, 'shadow_x': 4, 'shadow_y': 4, 'shadow_blur': 4,
                    'font_size': 40, 'font': 'Arial', 'align': 'center', 'text': '', 'fill': '#315efb',
                    'colour': '#ffffff', 'outline_colour': '#000000', 'shadow_colour': '#000000'}

        def common_value(key):
            values = [properties.get(key, defaults.get(key, 0))
                      for identifier, properties in zip(self.selection, selected)
                      if self.supports_property(identifier, key)]
            return values[0] if values and all(value == values[0] for value in values) else None

        for key, field in self.fields.items():
            field.blockSignals(True)
            value = common_value(key)
            if isinstance(field, fluentqt.NumberBox):
                if key in ('x', 'width', 'y', 'height'):
                    dimension = self.canvas_size().width() if key in ('x', 'width') else self.canvas_size().height()
                    field.setRange(0 if key in ('x', 'y') else 1, dimension)
                    if value is not None:
                        value *= dimension / 100
                field.setValue(value if value is not None else float('nan'))
            elif key in ('outline', 'shadow'):
                field.setTristate(value is None)
                field.setCheckState(QtCore.Qt.CheckState.PartiallyChecked if value is None else
                                    QtCore.Qt.CheckState.Checked if value else QtCore.Qt.CheckState.Unchecked)
            elif key in ('bold', 'italic'):
                field.setChecked(bool(value))
            else:
                field.setText(value.upper() if value is not None else '')
                swatch = QtGui.QPixmap(16, 16)
                swatch.fill(QtGui.QColor(value) if value is not None else QtCore.Qt.GlobalColor.transparent)
                field.setIcon(QtGui.QIcon(swatch) if value is not None else QtGui.QIcon())
            field.blockSignals(False)
            visible = any(self.supports_property(identifier, key) for identifier in self.selection)
            field.setEnabled(visible)
            if key in self.field_rows:
                self.field_rows[key].setEnabled(visible)
            if key.startswith(('outline_', 'shadow_')):
                enabled = common_value(key.split('_')[0])
                field.setEnabled(visible and (enabled is None or bool(enabled)))
        for widget in (self.font, self.align, self.text):
            widget.blockSignals(True)
        font = common_value('font')
        if font is None:
            self.font.setCurrentIndex(-1)
        else:
            self.font.setCurrentFont(QtGui.QFont(font))
        self.align.setCurrentIndex(self.align.findData(common_value('align')))
        if not self.text_timer.isActive():
            self.text.setPlainText(common_value('text') or '')
        for widget in (self.font, self.align, self.text):
            widget.blockSignals(False)
        self.text_section.setEnabled(has_text)
        self.text.setEnabled(any(properties.get('kind') == 'text' for properties in selected))
        for key, (drawer, _) in self.reset_sections.items():
            drawer.reset_button.setVisible(self.section_modified(key))
        editable = self.design_editable()
        self.background_section.setEnabled(editable)
        self.layers_panel.setEnabled(editable)
        self.reset_button.setEnabled(bool(
            self.document.get('overrides') or self.document.get('hidden_footers') or
            any(layout != 'theme' for layout in self.document.get('assignments', {}).values()) or
            layout_for_slide(self.document, '') != 'theme'))
        for button in [*self.insert_object_buttons, self.shape_button, self.arrange_button, self.align_button]:
            button.setEnabled(editable)
        if not editable:
            for key, (drawer, _) in self.reset_sections.items():
                if key != 'slide':
                    drawer.setEnabled(False)

    def property_defaults(self, identifier):
        defaults = {'x': 10, 'y': 10, 'width': 35, 'height': 20, 'rotation': 0, 'opacity': 100,
                    'font_size': 40, 'font': 'Arial', 'align': 'center', 'bold': False, 'italic': False,
                    'colour': '#ffffff', 'fill': '#315efb', 'flip_horizontal': False, 'flip_vertical': False,
                    'outline': False, 'outline_width': 2, 'outline_colour': '#000000',
                    'shadow': False, 'shadow_x': 4, 'shadow_y': 4, 'shadow_blur': 4, 'shadow_colour': '#000000'}
        if identifier == 'lyrics':
            defaults.update(self.selected_properties(identifier, defaults=True))
        return defaults

    def section_modified(self, section):
        if section == 'effects':
            key = 'filters' if self.selection else 'background_filters'
            return any(target.get(key) for target in self.filter_targets(self.design))
        if section == 'slide':
            return self.footer_key() in self.design.get('hidden_footers', [])
        if section == 'layers':
            return layer_order(self.design) != layer_order({**self.design, 'order': []})
        keys = self.reset_sections[section][1]
        if section == 'background':
            current, defaults = self.background_properties(), self.background_properties(defaults=True)
            return any(current.get(key) != defaults.get(key) for key in keys)
        for identifier in self.selection:
            current, defaults = self.selected_properties(identifier), self.property_defaults(identifier)
            if any(self.supports_property(identifier, key) and current.get(key, defaults[key]) != defaults[key]
                   for key in keys):
                return True
        return False

    def reset_section(self, section):
        if section == 'slide':
            self.set_footer_visible(True)
            return
        self.commit_text()
        design = self.editable_design()
        keys = self.reset_sections[section][1]
        if section == 'effects':
            key = 'filters' if self.selection else 'background_filters'
            for target in self.filter_targets(design):
                target.pop(key, None)
        elif section == 'slide':
            design['hidden_footers'] = [key for key in design.get('hidden_footers', []) if key != self.footer_key()]
        elif section == 'layers':
            design.pop('order', None)
        elif section == 'background':
            background, defaults = self.background_properties(), self.background_properties(defaults=True)
            for key in keys:
                if key in defaults:
                    background[key] = defaults[key]
                else:
                    background.pop(key, None)
            if background == defaults:
                design.pop('background', None)
            else:
                design['background'] = background
        else:
            for identifier in self.selection:
                target = self.design_target(design, identifier)
                defaults = self.property_defaults(identifier)
                for key in keys:
                    if self.supports_property(identifier, key):
                        if identifier == 'lyrics':
                            target.pop(key, None)
                        else:
                            target[key] = defaults[key]
                if section == 'outline':
                    target.pop('border_width', None)
                    target.pop('border_colour', None)
        self.commit(design, tr('Reset {section}').format(section=self.reset_sections[section][0].headerText()))

    def select_layer(self, current, previous):
        identifiers = [index.data(QtCore.Qt.ItemDataRole.UserRole)
                       for index in self.layers.selectionModel().selectedRows()]
        self.select_objects(identifiers, rebuild=False)

    def select_objects(self, identifiers, rebuild=True):
        self.commit_text()
        self.selection = list(dict.fromkeys(identifier for identifier in identifiers
                                            if identifier in layer_order(self.design)))
        # Do not rebuild the model during a native selection gesture (Shift/Ctrl/Command).
        self.populate_inspector(rebuild_layers=rebuild)
        if self.display and self.display._is_initialised:
            self.display.run_in_display('setDesignEditor', (self.selection or '') if self.design_editable() else None)

    def select_object(self, identifier):
        self.select_objects([identifier] if identifier else [])

    def clear_selection(self):
        self.select_object(None)

    def reset_slide_text(self):
        self.commit_text()
        design = self.editable_design()
        design['lyrics'] = {}
        self.commit(design, tr('Reset slide text to theme'))

    @staticmethod
    def design_target(design, identifier):
        return design['lyrics'] if identifier == 'lyrics' else next(
            (element for element in design['elements'] if element['id'] == identifier), None)

    def set_property(self, key, value):
        if value is None or isinstance(value, float) and not math.isfinite(value):
            return
        if key == 'font' and not value:
            return
        design = self.editable_design()
        for identifier in self.selection:
            target = self.design_target(design, identifier)
            if target is not None and self.supports_property(identifier, key):
                target[key] = value
        self.commit(design, tr('Change element'))

    def supports_property(self, identifier, key):
        kind = 'lyrics' if identifier == 'lyrics' else self.selected_properties(identifier).get('kind')
        if key == 'text':
            return kind == 'text'
        if key in ('font', 'font_size', 'bold', 'italic', 'colour', 'align'):
            return kind in ('lyrics', 'text')
        if key == 'fill':
            return kind in ('rectangle', 'ellipse')
        return True

    def choose_colour(self, key):
        colour = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.selected_properties().get(key, '#ffffff')), self)
        if colour.isValid():
            self.set_property(key, colour.name())

    def text_changed(self):
        identifiers = [identifier for identifier in self.selection if self.supports_property(identifier, 'text')]
        self._pending_text = (identifiers, self.text.toPlainText())
        self.text_timer.start()

    def commit_text(self):
        if self._canvas_editing and self.display and self.display._is_initialised:
            value = self.display.run_in_display('finishDesignTextEdit', False, False, is_sync=True)
            self.canvas_text_changed(value)
        self.text_timer.stop()
        if self._pending_text:
            identifiers, text = self._pending_text
            self._pending_text = None
            design = self.editable_design()
            for element in design['elements']:
                if element['id'] in identifiers:
                    element['text'] = text
            self.commit(design, tr('Edit text box'))

    def canvas_changed(self, value):
        if not self.design_editable():
            return
        if hasattr(value, 'toVariant'):
            value = value.toVariant()
        self.commit_text()
        self.selection = value.get('ids', [value['id']] if value.get('id') else [])
        if value.get('changed'):
            design = self.editable_design()
            geometries = value.get('geometries', {value.get('id'): value.get('geometry', {})})
            for identifier, geometry in geometries.items():
                target = self.design_target(design, identifier)
                if target is not None:
                    target.update(geometry)
            self.commit(design, tr('Move or resize elements'))
        self.populate_inspector()
        if self.display and self.display._is_initialised:
            self.display.run_in_display('setDesignEditor', (self.selection or '') if self.design_editable() else None)

    def add_element(self, kind):
        if not self.design_editable():
            return
        self.commit_text()
        design = self.editable_design()
        if len(design['elements']) >= 100:
            QtWidgets.QMessageBox.information(self, tr('Slide designer'),
                                              tr('A design can contain up to 100 elements.'))
            return
        element = {'id': str(uuid.uuid4()), 'kind': kind, 'x': 10, 'y': 10, 'width': 35, 'height': 20,
                   'rotation': 0, 'opacity': 100, 'font_size': 40, 'colour': '#ffffff', 'fill': '#315efb',
                   'font': 'Arial', 'text': tr('Text box') if kind == 'text' else ''}
        if kind == 'image':
            path, _ = FileDialog.getOpenFileName(self, tr('Add image'), filter=tr('Images (*.png *.jpg *.jpeg *.webp)'))
            if not path:
                return
            try:
                element['src'], image_size = image_to_png_uri(path)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, tr('Add image'), tr('This image could not be embedded. '
                                                                        'Please choose a smaller, valid image.'))
                return
            size = self.canvas_size()
            aspect = size.width() / size.height() * image_size.height() / image_size.width()
            element['height'] = min(80, element['width'] * aspect)
        self.selected = element['id']
        design['order'] = layer_order(design) + [element['id']]
        design['elements'].append(element)
        self.commit(design, tr('Add element'))
        self.inspector_button.setChecked(True)

    def delete_element(self):
        if not any(identifier != 'lyrics' for identifier in self.selection):
            return
        self.commit_text()
        design = self.editable_design()
        design['elements'] = [e for e in design['elements'] if e['id'] not in self.selection]
        self.commit(design, tr('Delete element'))

    def reorder_layers(self, order):
        self.commit_text()
        if len(order) != len(layer_order(self.design)) or set(order) != set(layer_order(self.design)):
            return
        design = self.editable_design()
        design['order'] = order
        self.commit(design, tr('Arrange layers'))

    def arrange(self, direction):
        order = layer_order(self.design)
        selected = set(self.selection)
        if direction in ('front', 'back'):
            moving = [identifier for identifier in order if identifier in selected]
            remaining = [identifier for identifier in order if identifier not in selected]
            order = remaining + moving if direction == 'front' else moving + remaining
        else:
            indices = range(len(order) - 2, -1, -1) if direction == 'forward' else range(1, len(order))
            step = 1 if direction == 'forward' else -1
            for index in indices:
                if order[index] in selected and order[index + step] not in selected:
                    order[index], order[index + step] = order[index + step], order[index]
        self.reorder_layers(order)

    def align_objects(self, operation):
        if not self.selection:
            return
        self.commit_text()
        design = self.editable_design()
        boxes = [(identifier, self.selected_properties(identifier)) for identifier in self.selection]
        horizontal = operation in ('left', 'center', 'right', 'horizontal')
        axis, extent = ('x', 'width') if horizontal else ('y', 'height')
        to_slide = len(boxes) == 1
        start = 0 if to_slide else min(box[axis] for _, box in boxes)
        end = 100 if to_slide else max(box[axis] + box[extent] for _, box in boxes)
        if operation in ('horizontal', 'vertical'):
            if len(boxes) < 3:
                return
            boxes.sort(key=lambda item: item[1][axis])
            gap = (end - start - sum(box[extent] for _, box in boxes)) / (len(boxes) - 1)
            position = start
            for identifier, box in boxes:
                self.design_target(design, identifier)[axis] = position
                position += box[extent] + gap
        else:
            for identifier, box in boxes:
                position = start if operation in ('left', 'top') else end - box[extent] \
                    if operation in ('right', 'bottom') else (start + end - box[extent]) / 2
                self.design_target(design, identifier)[axis] = position
        self.commit(design, tr('Align objects'))

    def flip_objects(self, axis):
        self.commit_text()
        design = self.editable_design()
        key = 'flip_' + axis
        for identifier in self.selection:
            target = self.design_target(design, identifier)
            target[key] = not target.get(key, False)
        self.commit(design, tr('Flip objects'))

    def reorder(self, delta):
        self.arrange('forward' if delta > 0 else 'backward')


def designer_dialog_parent(owner):
    """An editing canvas needs the main window's space, not the smaller list dialog's bounds."""
    return owner.parentWidget() if owner is not None and hasattr(owner, 'slide_design') else owner


class SlideDesignerDialogMixin:
    def draft_state(self):
        """Compare persisted content, excluding selection, preview size and other view state."""
        self.slide_designer.commit_text()
        return {'text': self.design_text_editor.toPlainText(), 'theme': self.designer_theme_name(),
                'design': self.slide_designer.serialised_design()}

    def accept(self):
        if hasattr(self, 'slide_designer'):
            self.slide_designer.commit_text()
        return super().accept()

    def mark_saved(self):
        self._saved_draft = copy.deepcopy(self.draft_state())

    def has_unsaved_changes(self):
        return self.draft_state() != self._saved_draft

    """Install the designer only in Edit/Edit All dialogs; list windows hold draft data only."""
    def setup_slide_designer(self, owner, editor, kind):
        self.design_owner = owner
        if owner is None or not hasattr(owner, 'slide_design'):
            return
        owner.destroyed.connect(self.deleteLater)
        self.design_kind = kind
        self.design_text_editor = editor
        self.theme_combo_box = QtWidgets.QComboBox(self)
        self.theme_combo_box.setFixedWidth(180)
        self.theme_combo_box.setAccessibleName(tr('Item theme'))
        self.theme_combo_box.setToolTip(tr('Assign a theme to this item'))
        self.slide_designer = SlideDesigner(self)
        self.slide_designer.tools.layout().insertWidget(1, self.theme_combo_box)
        self.theme_combo_box.currentIndexChanged.connect(self.designer_theme_changed)
        self.dialog_layout.setSpacing(12)
        self.dialog_layout.removeWidget(editor)
        self.editor_splitter = PaneSplitter(QtCore.Qt.Orientation.Horizontal)
        self.editor_splitter.setChildrenCollapsible(False)
        self.editor_splitter.setHandleWidth(12)
        text_panel = QtWidgets.QWidget()
        text_panel.setMinimumWidth(300)
        text_layout = QtWidgets.QVBoxLayout(text_panel)
        text_layout.setContentsMargins(12, 6, 12, 12)
        text_layout.setSpacing(8)
        self.section_combo_box = QtWidgets.QComboBox(self)
        self.section_combo_box.setToolTip(tr('Select the verse or slide to preview'))
        self.section_combo_box.currentIndexChanged.connect(self.designer_select_section)
        text_header = QtWidgets.QHBoxLayout()
        text_header.addWidget(self.slide_designer.heading(tr('Lyrics') if kind == 'song' else tr('Slides')))
        self.section_combo_box.hide()
        text_layout.addLayout(text_header)
        from openlp.plugins.slide_designer.forms.slidegrid import SlideGrid
        editor.hide()
        self.slide_grid = SlideGrid(self, editor, kind)
        text_layout.addWidget(self.slide_grid, 1)
        self.designer_text_controls(text_layout, kind)
        split_buttons = ((self.insert_button, self.split_button) if kind == 'custom' else
                         (self.insert_button, self.forced_split_button, self.overflow_split_button))
        for button in split_buttons:
            button.clicked.connect(lambda: self.slide_grid.cell_editor.setFocus())
        self.editor_splitter.addWidget(text_panel)
        self.editor_splitter.addWidget(self.slide_designer)
        self.editor_splitter.setStretchFactor(1, 1)
        self.editor_splitter.setSizes([520, 800])
        self.command_rows = QtWidgets.QVBoxLayout()
        self.command_rows.setSpacing(0)
        self.command_rows.setContentsMargins(0, 0, 0, 0)
        self.command_rows.addWidget(self.slide_designer.tools)
        self.command_rows.addWidget(self.slide_grid.formatting_bar)
        self.slide_grid.formatting_bar.background_role = 'bgLayer'
        self.command_surface = CommandSurface()
        self.command_surface.setLayout(self.command_rows)
        self.dialog_layout.insertWidget(0, self.command_surface)
        self.dialog_layout.insertWidget(1, self.editor_splitter, 1)
        editor.textChanged.connect(self.designer_cursor_changed)
        editor.cursorPositionChanged.connect(self.designer_cursor_changed)
        primary = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Save if kind == 'custom' else
                                         QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if primary:
            primary.setText(tr('Save'))
            primary.setFluentStyle(fluentqt.Button.ButtonStyle.Accent)
        self.resize(1320, 820)

    def designer_text_controls(self, layout, kind):
        """Keep lyrics/slide commands with their editor, leaving only Save/Cancel below the canvas."""
        split_row = QtWidgets.QHBoxLayout()
        split_row.setSpacing(4)
        if kind == 'custom':
            for button in (self.insert_button, self.split_button):
                self.button_box.removeButton(button)
                split_row.addWidget(button)
                button.show()
        else:
            self.dialog_layout.removeItem(self.verse_type_layout)
            # Empty the former full-dialog action row before reusing its controls.
            while self.verse_type_layout.count():
                self.verse_type_layout.takeAt(0)
            for button in (self.forced_split_button, self.overflow_split_button):
                split_row.addWidget(button)
            verse_row = QtWidgets.QHBoxLayout()
            verse_row.setSpacing(4)
            self.verse_type_label.hide()
            self.verse_type_combo_box.setAccessibleName(tr('Verse type'))
            self.verse_number_box.setAccessibleName(tr('Verse number'))
            verse_row.addWidget(self.verse_type_combo_box, 1)
            verse_row.addWidget(self.verse_number_box)
            verse_row.addWidget(self.insert_button)
            layout.addLayout(verse_row)
            self.dialog_layout.removeWidget(self.transpose_widget)
            # Legacy set_verse() may show this when chords are enabled. Keep it
            # under the hidden source editor so it cannot reappear in the designer.
            self.transpose_widget.setParent(self.design_text_editor)
            self.transpose_widget.hide()
        split_row.addStretch()
        layout.addLayout(split_row)
        for index in range(split_row.count()):
            button = split_row.itemAt(index).widget()
            if button:
                button.setFluentSize(fluentqt.Button.ButtonSize.Small)
                button.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)

    def exec(self):
        if hasattr(self, 'slide_designer'):
            self.theme_combo_box.blockSignals(True)
            self.theme_combo_box.clear()
            for index in range(self.design_owner.theme_combo_box.count()):
                name = self.design_owner.theme_combo_box.itemText(index)
                self.theme_combo_box.addItem(name or tr('Default theme'), name)
            current = self.design_owner.theme_combo_box.currentText()
            self.theme_combo_box.setCurrentIndex(self.theme_combo_box.findData(current))
            self.theme_combo_box.blockSignals(False)
            self.slide_designer.load_design(self.design_owner.slide_design)
            self.slide_grid.record_history = True
            self.slide_grid.reload()
            self._footer_sections = [section[1] for section in self.designer_sections()]
            self.designer_cursor_changed()
        if hasattr(self, 'slide_designer'):
            from openlp.plugins.slide_designer.forms.window import exec_designer_window
            result = exec_designer_window(self)
        else:
            result = super().exec()
        if result and hasattr(self, 'slide_designer'):
            self.design_owner.slide_design = self.slide_designer.serialised_design()
            self.design_owner.theme_combo_box.setCurrentText(self.designer_theme_name())
        if hasattr(self, 'slide_grid'):
            self.slide_grid.record_history = False
        return result

    def designer_theme_name(self):
        name = self.theme_combo_box.currentData()
        return self.theme_combo_box.currentText() if name is None else name

    def designer_theme_changed(self):
        # Explicitly assigning a new theme releases an imported theme snapshot.
        design = copy.deepcopy(self.slide_designer.document)
        design.pop('theme', None)
        for master in design.get('masters', {}).values():
            master['design'].pop('theme', None)
        for override in design.get('overrides', {}).values():
            for part in ('base', 'design'):
                override[part].pop('theme', None)
        self.slide_designer.commit_document(design, tr('Change base theme'))
        self.slide_designer.schedule_refresh()

    def designer_sections(self):
        """Map section labels/split markers to the editable text, retaining cursor positions."""
        import re
        text = self.design_text_editor.toPlainText()
        pattern = (r'(?m)^[ \t]*---\[([^\n]+?)\]---[ \t]*\n?' if self.design_kind == 'song'
                   else r'(?m)^[ \t]*\[===\][ \t]*\n?')
        matches = list(re.finditer(pattern, text))
        sections = []
        if not matches or text[:matches[0].start()].strip():
            end = matches[0].start() if matches else len(text)
            sections.append((tr('Slide 1'), text[:end].strip('\n'), 0, 0))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            label = (match.group(1) if self.design_kind == 'song' else
                     tr('Slide {number}').format(number=len(sections) + 1))
            sections.append((label, text[match.end():end].strip('\n'), match.start(), match.end()))
        return sections

    def designer_cursor_changed(self):
        if not hasattr(self, 'slide_designer'):
            return
        from openlp.plugins.slide_designer.forms.slidegrid import qt_length
        self.slide_designer.commit_text()
        sections = self.designer_sections()
        texts = [section[1] for section in sections]
        if self.design_kind == 'custom' and hasattr(self, '_footer_sections'):
            design = remap_custom_footers(self.slide_designer.document, self._footer_sections, texts,
                                          getattr(self, 'designer_slide_offset', 0))
            self.slide_designer.document = design
            for index in range(self.slide_designer.undo_stack.count()):
                command = self.slide_designer.undo_stack.command(index)
                if not isinstance(command, DesignCommand):
                    continue
                for attribute in ('before', 'after'):
                    setattr(command, attribute, remap_custom_footers(
                        getattr(command, attribute), self._footer_sections, texts,
                        getattr(self, 'designer_slide_offset', 0)))
        self._footer_sections = texts
        position = self.design_text_editor.textCursor().position()
        source = self.design_text_editor.toPlainText()
        index = max((i for i, section in enumerate(sections)
                     if qt_length(source[:section[2]]) <= position), default=0)
        self.section_combo_box.blockSignals(True)
        self.section_combo_box.clear()
        self.section_combo_box.addItems([section[0].replace(':', ' ') for section in sections])
        self.section_combo_box.setCurrentIndex(index)
        self.section_combo_box.blockSignals(False)
        self.slide_designer.page_index = 0
        self.slide_designer.page_keys = []
        if hasattr(self, 'slide_grid') and self.slide_grid.rows:
            self._preview_split = self.slide_grid.rows[self.slide_grid.active_row].split
        self.slide_designer.switch_design_context()

    def designer_select_section(self, index):
        from openlp.plugins.slide_designer.forms.slidegrid import qt_length
        sections = self.designer_sections()
        if 0 <= index < len(sections):
            cursor = self.design_text_editor.textCursor()
            cursor.setPosition(qt_length(self.design_text_editor.toPlainText()[:sections[index][3]]))
            self.design_text_editor.setTextCursor(cursor)
            self.design_text_editor.setFocus()

    def designer_section_key(self):
        if not hasattr(self, 'section_combo_box'):
            return 'v1' if self.design_kind == 'song' else 'custom-1'
        index = max(0, self.section_combo_box.currentIndex())
        if self.design_kind == 'custom':
            return 'custom-' + str(getattr(self, 'designer_slide_offset', 0) + index + 1)
        from openlp.plugins.songs.lib import VerseType
        sections = self.designer_sections()
        label = sections[index][0]
        if ':' in label:
            kind, number = label.rsplit(':', 1)
            verse_type = VerseType.from_translated_string(kind)
            if verse_type is None:
                verse_type = VerseType.from_string(kind, 0)
            return VerseType.tags[verse_type] + number.strip()
        return VerseType.tags[self.verse_type_combo_box.currentIndex()] + str(self.verse_number_box.value())

    def designer_text(self):
        sections = self.designer_sections()
        index = max(0, self.section_combo_box.currentIndex())
        text = sections[index][1]
        settings = self.slide_designer.settings
        if self.design_kind == 'song' and settings.value('songs/uppercase songs'):
            return '{uc}' + text + '{/uc}'
        return text

    def designer_show_theme(self):
        self.theme_combo_box.setFocus()
        self.theme_combo_box.showPopup()

    def designer_footer(self):
        return self.design_owner.designer_footer()
