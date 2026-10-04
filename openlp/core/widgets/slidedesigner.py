"""Song slide canvas and inspector, independent of the theme editor."""
import copy
import uuid

from PySide6 import QtCore, QtGui
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import ThemeLevel
from openlp.core.common.i18n import translate
from openlp.core.common.mixins import RegistryProperties
from openlp.core.display.render import ThemePreviewRenderer, render_tags
from openlp.core.display.screens import ScreenList
from openlp.core.lib.slidedesign import apply_design, normalise_design, design_theme, image_to_png_uri
from openlp.core.lib.theme import Theme
from openlp.core.ui.icons import UiIcons
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
        heading = QtWidgets.QHBoxLayout()
        heading.addWidget(QtWidgets.QLabel(tr('Slide designer')))
        heading.addStretch()
        self.inspector_button = QtWidgets.QPushButton(tr('Inspector'))
        self.inspector_button.setCheckable(True)
        layout.addLayout(heading)
        theme_row = QtWidgets.QHBoxLayout()
        theme_row.addWidget(QtWidgets.QLabel(tr('Preview theme')))
        self.theme_source = QtWidgets.QComboBox()
        self.theme_source.addItems([tr('Current output'), tr('Global'), tr('Selected item theme'),
                                    tr('Current service theme')])
        self.theme_source.setToolTip(tr('Preview the global, current, or assigned theme '
                                        'without changing the shared theme.'))
        theme_row.addWidget(self.theme_source, 1)
        self.theme_name = QtWidgets.QLabel()
        theme_row.addWidget(self.theme_name)
        layout.addLayout(theme_row)
        self.tools = QtWidgets.QWidget()
        toolbar = QtWidgets.QHBoxLayout(self.tools)
        toolbar.setContentsMargins(4, 4, 4, 4)
        theme_button = self.tool_button(tr('Theme'), UiIcons().theme)
        theme_button.clicked.connect(lambda: self.source_form.designer_show_theme())
        toolbar.addWidget(theme_button)
        for caption, kind in ((tr('Text'), 'text'), (tr('Rectangle'), 'rectangle'),
                              (tr('Ellipse'), 'ellipse'), (tr('Image'), 'image')):
            icon = {'text': UiIcons().custom, 'rectangle': UiIcons().live_black,
                    'ellipse': UiIcons().add, 'image': UiIcons().blank_theme}[kind]
            button = self.tool_button(caption, icon)
            button.clicked.connect(lambda checked=False, k=kind: self.add_element(k))
            toolbar.addWidget(button)
        toolbar.addStretch()
        for caption, callback in ((tr('Undo'), self.undo_stack.undo), (tr('Redo'), self.undo_stack.redo)):
            button = self.tool_button(caption, UiIcons().arrow_left if caption == tr('Undo') else UiIcons().arrow_right)
            button.clicked.connect(callback)
            button.setEnabled(False)
            (self.undo_stack.canUndoChanged if caption == tr('Undo') else
             self.undo_stack.canRedoChanged).connect(button.setEnabled)
            toolbar.addWidget(button)
        toolbar.addWidget(self.inspector_button)
        self.inspector_button.setIcon(UiIcons().edit)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        canvas_panel = QtWidgets.QWidget()
        canvas_layout = QtWidgets.QVBoxLayout(canvas_panel)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.viewport = QtWidgets.QWidget()
        self.viewport.setMinimumSize(300, 200)
        self.viewport.setStyleSheet('background: #181b20;')
        self.viewport.installEventFilter(self)
        canvas_layout.addWidget(self.viewport, 1)
        navigation = QtWidgets.QHBoxLayout()
        previous = QtWidgets.QPushButton(tr('Previous'))
        previous.clicked.connect(lambda: self.change_page(-1))
        navigation.addWidget(previous)
        self.page_label = QtWidgets.QLabel()
        self.page_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        navigation.addWidget(self.page_label, 1)
        following = QtWidgets.QPushButton(tr('Next'))
        following.clicked.connect(lambda: self.change_page(1))
        navigation.addWidget(following)
        canvas_layout.addLayout(navigation)
        hint = QtWidgets.QLabel(tr('Select a verse to preview. Drag to move; use the corner handle to resize.\n'
                                   'Design changes apply to every slide in this item.'))
        hint.setWordWrap(True)
        canvas_layout.addWidget(hint)
        self.splitter.addWidget(canvas_panel)
        self.inspector = QtWidgets.QScrollArea()
        self.inspector.setWidgetResizable(True)
        self.inspector.setMinimumWidth(230)
        self.inspector.setMaximumWidth(320)
        content = QtWidgets.QWidget()
        self.inspector_form = QtWidgets.QFormLayout(content)
        self.inspector_form.setContentsMargins(10, 10, 10, 10)
        self.inspector_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.inspector.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.layers = QtWidgets.QComboBox()
        self.inspector_form.addRow(tr('Element'), self.layers)
        self.fields = {}
        for key, caption, low, high in (
                ('x', tr('X (%)'), 0, 100), ('y', tr('Y (%)'), 0, 100),
                ('width', tr('Width (%)'), 1, 100), ('height', tr('Height (%)'), 1, 100),
                ('rotation', tr('Rotation (°)'), -180, 180), ('opacity', tr('Opacity (%)'), 0, 100),
                ('font_size', tr('Font size (pt)'), 1, 400), ('border_width', tr('Border (px)'), 0, 40)):
            field = QtWidgets.QDoubleSpinBox()
            field.setRange(low, high)
            field.setDecimals(1)
            field.setKeyboardTracking(False)
            field.setFixedWidth(125)
            field.valueChanged.connect(lambda value, k=key: self.set_property(k, value))
            self.fields[key] = field
            self.inspector_form.addRow(caption, field)
        self.font = QtWidgets.QFontComboBox()
        self.font.setMinimumWidth(0)
        self.font.setMaximumWidth(150)
        self.font.currentFontChanged.connect(lambda font: self.set_property('font', font.family()))
        self.inspector_form.addRow(tr('Font'), self.font)
        for key, caption in (('bold', tr('Bold')), ('italic', tr('Italic'))):
            field = QtWidgets.QCheckBox()
            field.toggled.connect(lambda value, k=key: self.set_property(k, value))
            self.fields[key] = field
            self.inspector_form.addRow(caption, field)
        self.align = QtWidgets.QComboBox()
        for caption, value in ((tr('Left'), 'left'), (tr('Centre'), 'center'), (tr('Right'), 'right')):
            self.align.addItem(caption, value)
        self.align.currentIndexChanged.connect(lambda: self.set_property('align', self.align.currentData()))
        self.inspector_form.addRow(tr('Alignment'), self.align)
        colours = (('colour', tr('Text colour')), ('fill', tr('Fill')), ('border_colour', tr('Border colour')))
        for key, caption in colours:
            field = QtWidgets.QPushButton()
            field.clicked.connect(lambda checked=False, k=key: self.choose_colour(k))
            self.fields[key] = field
            self.inspector_form.addRow(caption, field)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setMaximumHeight(100)
        self.text.setMaximumWidth(150)
        self.text.setPlaceholderText(tr('Text box content'))
        self.text.textChanged.connect(self.text_changed)
        self.text_timer = QtCore.QTimer(self)
        self.text_timer.setSingleShot(True)
        self.text_timer.setInterval(350)
        self.text_timer.timeout.connect(self.commit_text)
        self.inspector_form.addRow(tr('Text'), self.text)
        self._pending_text = None
        self.delete_button = QtWidgets.QPushButton(tr('Delete element'))
        self.delete_button.clicked.connect(self.delete_element)
        self.inspector_form.addRow(self.delete_button)
        self.back_button = QtWidgets.QPushButton(tr('Send backward'))
        self.back_button.clicked.connect(lambda: self.reorder(-1))
        self.inspector_form.addRow(self.back_button)
        self.front_button = QtWidgets.QPushButton(tr('Bring forward'))
        self.front_button.clicked.connect(lambda: self.reorder(1))
        self.inspector_form.addRow(self.front_button)
        reset = QtWidgets.QPushButton(tr('Reset design'))
        reset.clicked.connect(lambda: self.commit({}, tr('Reset design')))
        self.inspector_form.addRow(reset)
        self.inspector.setWidget(content)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 1)
        self.inspector.hide()
        self.inspector_button.toggled.connect(self.inspector.setVisible)
        layout.addWidget(self.splitter, 1)
        self.layers.currentIndexChanged.connect(self.select_layer)
        self.theme_source.currentIndexChanged.connect(self.schedule_refresh)
        self.populate_inspector()

    def tool_button(self, caption, icon):
        button = QtWidgets.QToolButton()
        button.setText(caption)
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(26, 26))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setMinimumSize(72, 58)
        return button

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
        scale = min(self.viewport.width() / size.width(), self.viewport.height() / size.height())
        width, height = round(size.width() * scale), round(size.height() * scale)
        self.display.setGeometry((self.viewport.width() - width) // 2, (self.viewport.height() - height) // 2,
                                 width, height)
        self.display.set_scale(scale)

    def resolve_theme(self):
        theme_name = self.source_form.theme_combo_box.currentText()
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
        caption = tr('Slide {current} of {total}').format(current=self.page_index + 1, total=len(self.pages))
        self.page_label.setText(caption)

    def change_page(self, delta):
        self.page_index = (self.page_index + delta) % len(self.pages)
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
        self.layers.blockSignals(True)
        self.layers.clear()
        self.layers.addItem(tr('Slide text'), 'lyrics')
        labels = {'text': tr('Text'), 'rectangle': tr('Rectangle'), 'ellipse': tr('Ellipse'), 'image': tr('Image')}
        for index, element in enumerate(self.design.get('elements', []), 1):
            self.layers.addItem(f"{index}. {labels[element['kind']]}", element['id'])
        self.layers.setCurrentIndex(self.layers.findData(self.selected))
        self.layers.blockSignals(False)
        properties = self.selected_properties()
        is_text = self.selected == 'lyrics' or properties.get('kind') == 'text'
        for key, field in self.fields.items():
            field.blockSignals(True)
            if isinstance(field, QtWidgets.QDoubleSpinBox):
                field.setValue(properties.get(key, 100 if key == 'opacity' else 0))
            elif isinstance(field, QtWidgets.QCheckBox):
                field.setChecked(properties.get(key, False))
            else:
                field.setText(properties.get(key, '#315efb' if key == 'fill' else '#ffffff'))
            field.blockSignals(False)
            visible = (is_text if key in ('font_size', 'bold', 'italic', 'colour') else
                       properties.get('kind') in ('rectangle', 'ellipse') if key == 'fill' else
                       self.selected != 'lyrics' if key in ('border_width', 'border_colour') else True)
            self.inspector_form.setRowVisible(field, visible)
        for widget in (self.font, self.align, self.text):
            widget.blockSignals(True)
        self.font.setCurrentFont(QtGui.QFont(properties.get('font', 'Arial')))
        self.align.setCurrentIndex(self.align.findData(properties.get('align', 'center')))
        if not self.text_timer.isActive():
            self.text.setPlainText(properties.get('text', ''))
        for widget in (self.font, self.align, self.text):
            widget.blockSignals(False)
        self.inspector_form.setRowVisible(self.font, is_text)
        self.inspector_form.setRowVisible(self.align, is_text)
        self.inspector_form.setRowVisible(self.text, properties.get('kind') == 'text')
        for button in (self.delete_button, self.front_button, self.back_button):
            button.setEnabled(self.selected != 'lyrics')

    def select_layer(self):
        selected = self.layers.currentData() or 'lyrics'
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
        design['elements'].append(element)
        self.commit(design, tr('Add element'))
        self.inspector_button.setChecked(True)

    def delete_element(self):
        if self.selected == 'lyrics':
            return
        self.commit_text()
        design = self.editable_design()
        design['elements'] = [e for e in design['elements'] if e['id'] != self.selected]
        self.commit(design, tr('Delete element'))

    def reorder(self, delta):
        design = self.editable_design()
        elements = design['elements']
        index = next((i for i, e in enumerate(elements) if e['id'] == self.selected), None)
        if index is not None and 0 <= index + delta < len(elements):
            elements[index], elements[index + delta] = elements[index + delta], elements[index]
            self.commit(design, tr('Arrange element'))


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
        self.theme_combo_box.setMinimumWidth(140)
        self.theme_combo_box.setMaximumWidth(240)
        self.theme_combo_box.setToolTip(tr('Assign a theme to this item'))
        self.slide_designer = SlideDesigner(self)
        self.slide_designer.tools.layout().insertWidget(1, self.theme_combo_box)
        self.theme_combo_box.currentIndexChanged.connect(self.designer_theme_changed)
        self.dialog_layout.removeWidget(editor)
        self.editor_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        text_panel = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(text_panel)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self.section_combo_box = QtWidgets.QComboBox()
        self.section_combo_box.setToolTip(tr('Select the verse or slide to preview'))
        self.section_combo_box.currentIndexChanged.connect(self.designer_select_section)
        text_layout.addWidget(self.section_combo_box)
        text_layout.addWidget(editor, 1)
        self.editor_splitter.addWidget(text_panel)
        self.editor_splitter.addWidget(self.slide_designer)
        self.editor_splitter.setStretchFactor(1, 1)
        self.editor_splitter.setSizes([380, 940])
        self.dialog_layout.insertWidget(0, self.slide_designer.tools)
        self.dialog_layout.insertWidget(1, self.editor_splitter, 1)
        editor.textChanged.connect(self.designer_cursor_changed)
        editor.cursorPositionChanged.connect(self.designer_cursor_changed)
        self.resize(1320, 780)

    def exec(self):
        if hasattr(self, 'slide_designer'):
            self.theme_combo_box.blockSignals(True)
            self.theme_combo_box.clear()
            for index in range(self.design_owner.theme_combo_box.count()):
                self.theme_combo_box.addItem(self.design_owner.theme_combo_box.itemText(index))
            current = self.design_owner.theme_combo_box.currentText()
            self.theme_combo_box.setCurrentIndex(self.theme_combo_box.findText(current))
            self.theme_combo_box.blockSignals(False)
            self.slide_designer.load_design(self.design_owner.slide_design)
            self.designer_cursor_changed()
        result = super().exec()
        if result and hasattr(self, 'slide_designer'):
            self.design_owner.slide_design = self.slide_designer.serialised_design()
            self.design_owner.theme_combo_box.setCurrentText(self.theme_combo_box.currentText())
        return result

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
        self.section_combo_box.addItems([section[0] for section in sections])
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
