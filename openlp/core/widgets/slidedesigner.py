"""Song slide canvas and inspector, independent of the theme editor."""
import copy
import uuid

import fluentqt

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import ThemeLevel
from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.display.render import ThemePreviewRenderer, render_tags
from openlp.core.display.screens import ScreenList
from openlp.core.lib.slidedesign import apply_design, normalise_design, design_theme, image_to_png_uri, layer_order
from openlp.core.lib.theme import Theme
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.fluenticons import fluent_icon
from openlp.core.widgets.dialogs import FileDialog


def tr(text):
    return translate('SongsPlugin.SlideDesigner', text)


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

    def __init__(self):
        super().__init__()
        self.setModel(QtGui.QStandardItemModel(self))
        self.setAccessibleName(tr('Layers'))
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setMinimumHeight(108)

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
        identifier = order.pop(source)
        destination = max(0, min(boundary - (source < boundary), len(order)))
        order.insert(destination, identifier)
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
        self.selected = 'lyrics'
        self.base_theme = None
        self.display = None
        self.pages = ['']
        self.page_index = 0
        self._refreshing = False
        self.undo_stack = QtGui.QUndoStack(self)
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(180)
        self.refresh_timer.timeout.connect(self.refresh)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tools = QtWidgets.Card()
        toolbar = QtWidgets.QHBoxLayout(self.tools)
        toolbar.setContentsMargins(8, 6, 8, 6)
        toolbar.setSpacing(4)
        toolbar.addWidget(QtWidgets.QLabel(tr('Theme')))
        # The assigned-theme picker is inserted here by the owning dialog.
        toolbar.addSpacing(12)
        for caption, kind, icon in ((tr('Text'), 'text', fluent_icon('ic_fluent_textbox_24_regular')),
                                    (tr('Image'), 'image', UiIcons().blank_theme)):
            button = self.tool_button(caption, icon)
            button.clicked.connect(lambda checked=False, k=kind: self.add_element(k))
            toolbar.addWidget(button)
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
        for caption, direction in ((tr('Bring to front'), 'front'), (tr('Bring forward'), 'forward'),
                                   (tr('Send backward'), 'backward'), (tr('Send to back'), 'back')):
            action = arrange_menu.addAction(caption)
            action.triggered.connect(lambda checked=False, d=direction: self.arrange(d))
            self.arrange_actions[direction] = action
        self.arrange_button.setMenu(arrange_menu)
        self.arrange_button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(self.arrange_button)
        toolbar.addStretch()
        for caption, icon, callback, signal in (
                (tr('Undo'), UiIcons().undo, self.undo_stack.undo, self.undo_stack.canUndoChanged),
                (tr('Redo'), UiIcons().redo, self.undo_stack.redo, self.undo_stack.canRedoChanged)):
            button = self.tool_button(caption, icon, icon_only=True)
            button.clicked.connect(callback)
            button.setEnabled(False)
            signal.connect(button.setEnabled)
            toolbar.addWidget(button)
        toolbar.addSpacing(8)
        self.layers_button = self.tool_button(tr('Layers'), fluent_icon('ic_fluent_layer_24_regular'))
        self.layers_button.setCheckable(True)
        self.layers_button.setChecked(True)
        toolbar.addWidget(self.layers_button)
        self.inspector_button = self.tool_button(tr('Properties'), fluent_icon('ic_fluent_panel_right_24_regular'))
        self.inspector_button.setCheckable(True)
        toolbar.addWidget(self.inspector_button)
        self.reset_button = self.tool_button(tr('Reset design'), UiIcons().undo)
        self.reset_button.clicked.connect(self.reset_design)
        toolbar.addWidget(self.reset_button)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        canvas_panel = QtWidgets.QWidget()
        canvas_layout = QtWidgets.QVBoxLayout(canvas_panel)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(8)
        theme_row = QtWidgets.QHBoxLayout()
        theme_row.setSpacing(8)
        theme_row.addWidget(self.heading(tr('Preview')))
        self.theme_source = QtWidgets.QComboBox()
        self.theme_source.addItems([tr('Current output'), tr('Global theme'), tr('Item theme'), tr('Service theme')])
        self.theme_source.setAccessibleName(tr('Preview theme'))
        self.theme_source.setFixedWidth(170)
        theme_row.addStretch()
        theme_row.addWidget(self.theme_source)
        canvas_layout.addLayout(theme_row)
        self.theme_name = QtWidgets.QLabel()
        self.theme_name.setMaximumWidth(230)
        self.viewport = QtWidgets.QWidget()
        self.viewport.setMinimumSize(280, 180)
        self.viewport.setStyleSheet('background: #181b20; border-radius: 8px;')
        self.viewport.installEventFilter(self)
        canvas_layout.addWidget(self.viewport, 1)
        navigation = QtWidgets.QHBoxLayout()
        navigation.setSpacing(4)
        navigation.addWidget(self.theme_name)
        navigation.addStretch()
        self.previous_button = self.tool_button(tr('Previous slide'), UiIcons().arrow_left, icon_only=True)
        self.previous_button.clicked.connect(lambda: self.change_page(-1))
        navigation.addWidget(self.previous_button)
        self.page_label = QtWidgets.QLabel(tr('1 / 1'))
        self.page_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(64)
        navigation.addWidget(self.page_label)
        self.next_button = self.tool_button(tr('Next slide'), UiIcons().arrow_right, icon_only=True)
        self.next_button.clicked.connect(lambda: self.change_page(1))
        navigation.addWidget(self.next_button)
        canvas_layout.addLayout(navigation)
        self.splitter.addWidget(canvas_panel)
        self.sidebar = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.sidebar.setFixedWidth(280)
        self.sidebar.setChildrenCollapsible(False)
        self.sidebar.setHandleWidth(8)
        self.build_layers()
        self.build_inspector()
        self.sidebar.addWidget(self.inspector)
        self.sidebar.addWidget(self.layers_panel)
        self.sidebar.setStretchFactor(0, 1)
        self.sidebar.setSizes([470, 230])
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 1)
        self.inspector.hide()
        self.inspector_button.toggled.connect(self.update_sidebar)
        self.layers_button.toggled.connect(self.update_sidebar)
        layout.addWidget(self.splitter, 1)
        self.layers.selectionModel().currentChanged.connect(self.select_layer)
        self.layers.orderChanged.connect(self.reorder_layers)
        self.theme_source.currentIndexChanged.connect(self.schedule_refresh)
        self.populate_inspector()

    @staticmethod
    def heading(caption):
        label = QtWidgets.QLabel(caption)
        label.setFluentTypography(fluentqt.FontRole.BodyStrong)
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

    def inspector_section(self, caption):
        card = QtWidgets.Card()
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.heading(caption))
        self.inspector_layout.addWidget(card)
        return card, layout

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
        self.layers_panel.setVisible(self.layers_button.isChecked())
        self.inspector.setVisible(self.inspector_button.isChecked())
        self.sidebar.setVisible(self.layers_button.isChecked() or self.inspector_button.isChecked())

    def build_layers(self):
        self.layers_panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.layers_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(self.heading(tr('Layers')))
        header.addStretch()
        close = self.tool_button(tr('Close layers'), UiIcons().close, icon_only=True)
        close.clicked.connect(lambda: self.layers_button.setChecked(False))
        header.addWidget(close)
        layout.addLayout(header)
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

    def reset_design(self):
        self.commit_text()
        self.commit({}, tr('Reset design'))

    def build_inspector(self):
        self.inspector = QtWidgets.QScrollArea()
        self.inspector.setWidgetResizable(True)
        self.inspector.setFixedWidth(280)
        self.inspector.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.inspector.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QtWidgets.QWidget()
        self.inspector_layout = QtWidgets.QVBoxLayout(content)
        self.inspector_layout.setContentsMargins(0, 0, 4, 0)
        self.inspector_layout.setSpacing(8)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(self.heading(tr('Properties')))
        header.addStretch()
        close = self.tool_button(tr('Close properties'), UiIcons().close, icon_only=True)
        close.clicked.connect(lambda: self.inspector_button.setChecked(False))
        header.addWidget(close)
        self.inspector_layout.addLayout(header)
        self.selected_label = self.heading(tr('Slide text'))
        self.inspector_layout.addWidget(self.selected_label)
        self.fields = {}
        self.field_rows = {}
        for key, caption, low, high in (
                ('x', tr('X (%)'), 0, 100), ('y', tr('Y (%)'), 0, 100),
                ('width', tr('Width (%)'), 1, 100), ('height', tr('Height (%)'), 1, 100),
                ('rotation', tr('Rotation (°)'), -180, 180), ('opacity', tr('Opacity (%)'), 0, 100),
                ('font_size', tr('Size (pt)'), 1, 400), ('border_width', tr('Width (px)'), 0, 40)):
            field = fluentqt.NumberBox()
            field.setRange(low, high)
            field.setDisplayPrecision(1)
            field.setSpinButtonPlacementMode(fluentqt.NumberBox.SpinButtonPlacementMode.Compact)
            field.setMinimumWidth(0)
            field.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
            field.valueChanged.connect(lambda value, k=key: self.set_property(k, value))
            self.fields[key] = field
            self.field_rows[key] = self.labelled_field(caption, field)
        _, position_layout = self.inspector_section(tr('Position'))
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)
        for index, key in enumerate(('x', 'y', 'width', 'height', 'rotation', 'opacity')):
            grid.addWidget(self.field_rows[key], index // 2, index % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        position_layout.addLayout(grid)

        self.text_section, text_layout = self.inspector_section(tr('Text'))
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
        for key, caption in (('colour', tr('Text colour')), ('fill', tr('Fill')), ('border_colour', tr('Border'))):
            field = QtWidgets.QPushButton()
            field.setFluentSize(fluentqt.Button.ButtonSize.Small)
            field.setAccessibleName(caption)
            field.clicked.connect(lambda checked=False, k=key: self.choose_colour(k))
            self.fields[key] = field
            self.field_rows[key] = self.labelled_field(caption, field)
            appearance_layout.addWidget(self.field_rows[key])
        appearance_layout.addWidget(self.field_rows['border_width'])
        self.inspector_layout.addStretch()
        self.inspector.setWidget(content)

    def canvas_size(self):
        return ScreenList().current.display_geometry.size()

    def showEvent(self, event):
        super().showEvent(event)
        # Deferred creation avoids a WebEngine process for song import/maintenance dialogs.
        if self.display is None and isinstance(self.resolve_theme(), Theme):
            self.display = ThemePreviewRenderer(self.viewport, embedded=True, can_show_startup_screen=False,
                                                after_loaded_callback=self.schedule_refresh)
            self.display.allow_theme_transitions = False
            self.display.allow_item_transitions = False
            self.display.display_watcher.register_event_listener('songDesignChanged', self.canvas_changed, False)
            self.display.show()
            self.fit_canvas()
        self.schedule_refresh()

    def hideEvent(self, event):
        self.refresh_timer.stop()
        self.text_timer.stop()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.viewport and event.type() == QtCore.QEvent.Type.Resize:
            self.fit_canvas()
        return super().eventFilter(watched, event)

    def fit_canvas(self):
        if self.display is None:
            return
        size = self.canvas_size()
        scale = min(max(1, self.viewport.width() - 32) / size.width(),
                    max(1, self.viewport.height() - 32) / size.height())
        width, height = round(size.width() * scale), round(size.height() * scale)
        self.display.setGeometry((self.viewport.width() - width) // 2, (self.viewport.height() - height) // 2,
                                 width, height)
        self.display.set_scale(scale)

    def resolve_theme(self):
        theme_name = self.source_form.designer_theme_name()
        manager = self.theme_manager
        if not manager:
            return None
        global_name = manager.global_theme
        names = manager.get_theme_names()
        if theme_name not in names:
            theme_name = global_name
        mode = self.theme_source.currentIndex()
        if mode == 3:
            theme_name = self.settings.value('servicemanager/service theme') or global_name
        if mode == 1 or (mode == 0 and self.settings.value('themes/theme level') != ThemeLevel.Song):
            theme_name = global_name
        self.theme_name.setText(str(theme_name))
        return manager.get_theme_data(theme_name)

    def schedule_refresh(self, *args):
        if not self._refreshing:
            self.refresh_timer.start()

    def refresh(self):
        if not self.display or not self.display._is_initialised or not self.isVisible() or self._refreshing:
            return
        self._refreshing = True
        try:
            self.base_theme = self.resolve_theme()
            preview_design = copy.deepcopy(self.design)
            if self.theme_source.currentIndex() != 0:
                preview_design.pop('theme', None)
            self.base_theme = design_theme(self.base_theme, preview_design, self.canvas_size())
            if preview_design.get('theme'):
                self.theme_name.setText(tr('Embedded theme'))
            theme = apply_design(self.base_theme, preview_design, self.canvas_size())
            self.display.run_in_display('setDesignEditor', None)
            self.display.set_theme(theme, is_sync=True)
            text = self.source_form.designer_text()
            self.pages = []
            for section in text.split('[--}{--]\n'):
                self.pages.extend(self.display.format_slide(section, None))
            self.pages = self.pages or ['']
            self.page_index = min(self.page_index, len(self.pages) - 1)
            self.show_page()
            self.populate_inspector()
        finally:
            self._refreshing = False

    def show_page(self):
        if not self.display or not self.display._is_initialised:
            return
        self.display.load_verses([{'verse': 'designer', 'text': render_tags(self.pages[self.page_index]),
                                   'footer': self.source_form.designer_footer()}])
        self.display.go_to_slide('designer', raise_window=False)
        self.display.run_in_display('setDesignEditor', self.selected)
        caption = f'{self.page_index + 1} / {len(self.pages)}'
        self.page_label.setText(caption)
        self.previous_button.setEnabled(self.page_index > 0)
        self.next_button.setEnabled(self.page_index < len(self.pages) - 1)

    def change_page(self, delta):
        self.page_index = max(0, min(self.page_index + delta, len(self.pages) - 1))
        self.show_page()

    def load_design(self, value):
        self.text_timer.stop()
        self._pending_text = None
        self.selected = 'lyrics'
        self.page_index = 0
        self.design = normalise_design(value)
        self.undo_stack.clear()
        self.populate_inspector()
        self.schedule_refresh()

    def serialised_design(self):
        self.commit_text()
        return normalise_design(self.design)

    def restore(self, design):
        self.design = copy.deepcopy(design)
        self.populate_inspector()
        self.schedule_refresh()

    def commit(self, design, caption):
        design = normalise_design(design)
        if design != self.design:
            self.undo_stack.push(DesignCommand(self, copy.deepcopy(self.design), design, caption))

    def editable_design(self):
        return copy.deepcopy(self.design) or {
            'version': 1, 'canvas_height': self.canvas_size().height(), 'lyrics': {}, 'elements': []}

    def selected_properties(self):
        if self.selected == 'lyrics':
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
                                  align=('left', 'right', 'center', 'left')[theme.display_horizontal_align])
            properties.update(self.design.get('lyrics', {}))
            return properties
        return next((e for e in self.design.get('elements', []) if e['id'] == self.selected), {})

    def populate_inspector(self):
        if self.selected != 'lyrics' and not any(e['id'] == self.selected for e in self.design.get('elements', [])):
            self.selected = 'lyrics'
        selection = self.layers.selectionModel()
        blocker = QtCore.QSignalBlocker(selection)
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
            if identifier == self.selected:
                self.layers.setCurrentIndex(item.index())
                self.selected_label.setText(label)
        del blocker
        order = layer_order(self.design)
        index = order.index(self.selected)
        self.front_button.setEnabled(index < len(order) - 1)
        self.back_button.setEnabled(index > 0)
        for direction, action in self.arrange_actions.items():
            action.setEnabled(index < len(order) - 1 if direction in ('front', 'forward') else index > 0)
        self.delete_button.setEnabled(self.selected != 'lyrics')
        properties = self.selected_properties()
        is_text = self.selected == 'lyrics' or properties.get('kind') == 'text'
        for key, field in self.fields.items():
            field.blockSignals(True)
            if isinstance(field, fluentqt.NumberBox):
                field.setValue(properties.get(key, 100 if key == 'opacity' else 0))
            elif key in ('bold', 'italic'):
                field.setChecked(properties.get(key, False))
            else:
                colour = properties.get(key, '#315efb' if key == 'fill' else '#ffffff')
                field.setText(colour.upper())
                swatch = QtGui.QPixmap(16, 16)
                swatch.fill(QtGui.QColor(colour))
                field.setIcon(QtGui.QIcon(swatch))
            field.blockSignals(False)
            visible = (is_text if key in ('font_size', 'bold', 'italic', 'colour') else
                       properties.get('kind') in ('rectangle', 'ellipse') if key == 'fill' else
                       self.selected != 'lyrics' if key in ('border_width', 'border_colour') else True)
            if key in self.field_rows:
                self.field_rows[key].setVisible(visible)
        for widget in (self.font, self.align, self.text):
            widget.blockSignals(True)
        self.font.setCurrentFont(QtGui.QFont(properties.get('font', 'Arial')))
        self.align.setCurrentIndex(self.align.findData(properties.get('align', 'center')))
        if not self.text_timer.isActive():
            self.text.setPlainText(properties.get('text', ''))
        for widget in (self.font, self.align, self.text):
            widget.blockSignals(False)
        self.text_section.setVisible(is_text)
        self.text.setVisible(properties.get('kind') == 'text')

    def select_layer(self, current, previous):
        selected = current.data(QtCore.Qt.ItemDataRole.UserRole)
        if not selected:
            return
        self.commit_text()
        self.selected = selected
        self.populate_inspector()
        if self.display:
            self.display.run_in_display('setDesignEditor', self.selected)

    def set_property(self, key, value):
        design = self.editable_design()
        target = design['lyrics'] if self.selected == 'lyrics' else next(
            (e for e in design['elements'] if e['id'] == self.selected), None)
        if target is not None:
            target[key] = value
            self.commit(design, tr('Change element'))

    def choose_colour(self, key):
        colour = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.selected_properties().get(key, '#ffffff')), self)
        if colour.isValid():
            self.set_property(key, colour.name())

    def text_changed(self):
        self._pending_text = (self.selected, self.text.toPlainText())
        self.text_timer.start()

    def commit_text(self):
        self.text_timer.stop()
        if self._pending_text:
            identifier, text = self._pending_text
            self._pending_text = None
            design = self.editable_design()
            for element in design['elements']:
                if element['id'] == identifier:
                    element['text'] = text
            self.commit(design, tr('Edit text box'))

    def canvas_changed(self, value):
        if hasattr(value, 'toVariant'):
            value = value.toVariant()
        self.commit_text()
        self.selected = value['id']
        if value.get('changed'):
            design = self.editable_design()
            target = design['lyrics'] if self.selected == 'lyrics' else next(
                (e for e in design['elements'] if e['id'] == self.selected), None)
            if target is not None:
                target.update(value['geometry'])
                self.commit(design, tr('Move or resize element'))
        self.populate_inspector()
        if self.display:
            self.display.run_in_display('setDesignEditor', self.selected)

    def add_element(self, kind):
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
        self.layers_button.setChecked(True)
        self.inspector_button.setChecked(True)

    def delete_element(self):
        if self.selected == 'lyrics':
            return
        self.commit_text()
        design = self.editable_design()
        design['elements'] = [e for e in design['elements'] if e['id'] != self.selected]
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
        index = order.index(self.selected)
        destination = {'front': len(order) - 1, 'forward': min(index + 1, len(order) - 1),
                       'backward': max(index - 1, 0), 'back': 0}[direction]
        if destination != index:
            order.insert(destination, order.pop(index))
            self.reorder_layers(order)

    def reorder(self, delta):
        self.arrange('forward' if delta > 0 else 'backward')


def designer_dialog_parent(owner):
    """An editing canvas needs the main window's space, not the smaller list dialog's bounds."""
    return owner.parentWidget() if owner is not None and hasattr(owner, 'slide_design') else owner


class SlideDesignerDialogMixin:
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
        self.editor_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.editor_splitter.setChildrenCollapsible(False)
        self.editor_splitter.setHandleWidth(12)
        text_panel = QtWidgets.QWidget()
        text_panel.setMinimumWidth(300)
        text_layout = QtWidgets.QVBoxLayout(text_panel)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self.section_combo_box = QtWidgets.QComboBox()
        self.section_combo_box.setToolTip(tr('Select the verse or slide to preview'))
        self.section_combo_box.currentIndexChanged.connect(self.designer_select_section)
        text_header = QtWidgets.QHBoxLayout()
        text_header.addWidget(self.slide_designer.heading(tr('Lyrics') if kind == 'song' else tr('Slides')))
        text_header.addStretch()
        self.section_combo_box.setMinimumWidth(160)
        text_header.addWidget(self.section_combo_box)
        text_layout.addLayout(text_header)
        if editor._toolbar:
            formatting_row = QtWidgets.QHBoxLayout()
            formatting_row.setSpacing(8)
            # Keep the native command bar wide enough for direct formatting commands.
            for action in list(editor._toolbar.actions()):
                widget = editor._toolbar.widgetForAction(action)
                if isinstance(action, QtWidgets.QWidgetAction) and widget is not None:
                    editor._toolbar.removeAction(action)
                    formatting_row.addWidget(widget)
                    widget.show()
            editor._toolbar.layout().setStretch(editor._toolbar.layout().count() - 1, 0)
            editor._custom_formatting_combo.setMinimumWidth(0)
            editor._custom_formatting_combo.setMaximumWidth(16777215)
            editor._custom_formatting_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                                          QtWidgets.QSizePolicy.Policy.Fixed)
            text_layout.addLayout(formatting_row)
        text_layout.addWidget(editor, 1)
        self.designer_text_controls(text_layout, kind)
        self.editor_splitter.addWidget(text_panel)
        self.editor_splitter.addWidget(self.slide_designer)
        self.editor_splitter.setStretchFactor(1, 1)
        self.editor_splitter.setSizes([340, 980])
        self.dialog_layout.insertWidget(0, self.slide_designer.tools)
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
            self.transpose_layout.setContentsMargins(0, 0, 0, 0)
            for button in (self.transpose_up_button, self.transpose_down_button):
                button.setToolTip(button.text())
                button.setAccessibleName(button.text())
                button.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly)
                button.setFixedSize(32, 32)
            self.transpose_layout.addStretch()
            layout.addWidget(self.transpose_widget)
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
            self.designer_cursor_changed()
        result = super().exec()
        if result and hasattr(self, 'slide_designer'):
            self.design_owner.slide_design = self.slide_designer.serialised_design()
            self.design_owner.theme_combo_box.setCurrentText(self.designer_theme_name())
        return result

    def designer_theme_name(self):
        name = self.theme_combo_box.currentData()
        return self.theme_combo_box.currentText() if name is None else name

    def designer_theme_changed(self):
        # Explicitly assigning a new theme releases an imported theme snapshot.
        design = copy.deepcopy(self.slide_designer.design)
        design.pop('theme', None)
        self.slide_designer.commit(design, tr('Change base theme'))
        self.slide_designer.theme_source.setCurrentIndex(2)
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
        sections = self.designer_sections()
        position = self.design_text_editor.textCursor().position()
        index = max((i for i, section in enumerate(sections) if section[2] <= position), default=0)
        self.section_combo_box.blockSignals(True)
        self.section_combo_box.clear()
        self.section_combo_box.addItems([section[0].replace(':', ' ') for section in sections])
        self.section_combo_box.setCurrentIndex(index)
        self.section_combo_box.blockSignals(False)
        self.slide_designer.page_index = 0
        self.slide_designer.schedule_refresh()

    def designer_select_section(self, index):
        sections = self.designer_sections()
        if 0 <= index < len(sections):
            cursor = self.design_text_editor.textCursor()
            cursor.setPosition(sections[index][3])
            self.design_text_editor.setTextCursor(cursor)
            self.design_text_editor.setFocus()

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
