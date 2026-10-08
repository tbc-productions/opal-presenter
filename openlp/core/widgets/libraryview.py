"""Thumbnail browsing over the file library's existing tree and selection."""
from PySide6 import QtCore, QtGui, QtWidgets as NativeWidgets
from fluentqt import Breadcrumb, BreadcrumbItem, Button, CommandBar, FluentWidget, GridView
from fluentqt.design import Spacing

from openlp.core.common.i18n import translate
from openlp.core.widgets.views import handle_mime_data_urls
from openlp.core.widgets.dnd import ItemDragData, execute_drag
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.fluent_tree import LIBRARY_FOLDER_ROLE, library_folder_icon
from openlp.core.widgets.fluent_commands import SpacedCommandBar
from openlp.core.widgets.fluent_collections import ListItemsMixin
from openlp.core.widgets.libraryfooter import LibraryFooter

LIBRARY_THUMBNAIL_ROLE = QtCore.Qt.ItemDataRole.UserRole + 102


def tr(text):
    return translate('OpenLP.LibraryView', text)


class LibraryViewPreferences(QtCore.QObject):
    """One saved view and thumbnail scale for all three file libraries."""
    view_changed = QtCore.Signal(int)
    thumbnail_size_changed = QtCore.Signal(int)

    def __init__(self, settings, plugin_name):
        super().__init__(settings)
        self.settings = settings
        if not settings.contains('advanced/library view'):
            # Retain an existing library choice when adopting shared preferences.
            names = [plugin_name] + [name for name in ('images', 'media', 'presentations') if name != plugin_name]
            for name in names:
                key = f'{name}/library view'
                if settings.contains(key):
                    settings.setValue('advanced/library view', settings.value(key))
                    break
        self.mode = 1 if settings.value('advanced/library view') == 'grid' else 0
        self.size = max(50, min(200, settings.value('advanced/library thumbnail size')))

    def set_view(self, mode):
        if self.mode != mode:
            self.mode = mode
            self.settings.setValue('advanced/library view', 'grid' if mode else 'list')
            self.view_changed.emit(mode)

    def set_thumbnail_size(self, size):
        if self.size != size:
            self.size = size
            self.settings.setValue('advanced/library thumbnail size', size)
            self.thumbnail_size_changed.emit(size)


class LibraryTileDelegate(NativeWidgets.QStyledItemDelegate):
    """Use the designer picker's thumbnail and caption proportions."""
    def __init__(self, view):
        super().__init__(view)
        self.theme = FluentWidget(view)
        self.theme.hide()

    def paint(self, painter, option, index):
        colors = self.theme.theme_tokens().colors
        selected = bool(option.state & NativeWidgets.QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & NativeWidgets.QStyle.StateFlag.State_MouseOver)
        rect = option.rect.adjusted(2, 2, -2, -2)
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        focused = bool(option.state & NativeWidgets.QStyle.StateFlag.State_HasFocus)
        painter.setPen(QtGui.QPen(colors.accentDefault if selected or focused else colors.strokeCard, 1))
        painter.setBrush(colors.subtleSecondary if selected or hovered else QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)
        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        image_rect = QtCore.QRect(rect.left() + 4, rect.top() + 4, rect.width() - 8,
                                  self.parent().iconSize().height())
        if isinstance(icon, QtGui.QIcon):
            if index.data(LIBRARY_FOLDER_ROLE):
                icon = library_folder_icon(colors)
                extent = min(52, image_rect.height())
                folder_rect = QtCore.QRect(0, 0, extent, extent)
                folder_rect.moveCenter(image_rect.center())
                icon.paint(painter, folder_rect)
            else:
                icon.paint(painter, image_rect)
        painter.setFont(option.font)
        painter.setPen(colors.textPrimary)
        text = option.fontMetrics.elidedText(str(index.data() or ''), QtCore.Qt.TextElideMode.ElideRight,
                                             image_rect.width())
        alignment = (QtCore.Qt.AlignmentFlag.AlignRight if option.direction == QtCore.Qt.LayoutDirection.RightToLeft
                     else QtCore.Qt.AlignmentFlag.AlignLeft)
        painter.drawText(rect.adjusted(4, image_rect.height() + 8, -4, -4),
                         alignment | QtCore.Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()


class LibraryGrid(ListItemsMixin, GridView):
    """Native Fluent grid retaining the file libraries' item and drag APIs."""
    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setViewMode(NativeWidgets.QListView.ViewMode.IconMode)
        self.setResizeMode(NativeWidgets.QListView.ResizeMode.Adjust)
        self.setMovement(NativeWidgets.QListView.Movement.Static)
        self.setCellSize(QtCore.QSize(160, 116))
        self.setHorizontalSpacing(6)
        self.setVerticalSpacing(6)
        self.setBorderVisible(False)
        self.setBackgroundVisible(False)
        self.setIconSize(QtCore.QSize(148, 84))
        self.setUniformItemSizes(True)
        self.setWordWrap(False)
        self.setMouseTracking(True)
        self.setItemDelegate(LibraryTileDelegate(self))
        self.setFrameShape(NativeWidgets.QFrame.Shape.NoFrame)
        self.setSelectionMode(browser.tree.selectionMode())
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._drag_start_pos = None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def tree_item(self, tile):
        index = tile.data(QtCore.Qt.ItemDataRole.UserRole) if tile else None
        return self.browser.tree.itemFromIndex(QtCore.QModelIndex(index)) if index and index.isValid() else None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self.dragEnabled() and event.buttons() & QtCore.Qt.MouseButton.LeftButton
                and self._drag_start_pos is not None and self.indexAt(self._drag_start_pos).isValid()
                and self.selectedItems() and (event.position().toPoint() - self._drag_start_pos).manhattanLength()
                >= QtWidgets.QApplication.startDragDistance()):
            self._drag_start_pos = None
            self.startDrag(QtCore.Qt.DropAction.CopyAction)
            return
        super().mouseMoveEvent(event)

    def startDrag(self, actions):
        self.browser.select_tree_items()
        if self.selectedItems():
            execute_drag(self, ItemDragData(library=self.browser.library))

    def dragEnterEvent(self, event):
        if (event.mimeData().hasUrls()
                or (isinstance(event.mimeData(), ItemDragData)
                    and event.mimeData().library is self.browser.library)):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        target = self.tree_item(self.itemAt(event.position().toPoint())) or self.browser.folder_item()
        if event.mimeData().hasUrls():
            self.browser.library.handle_mime_data({'file_paths': handle_mime_data_urls(event.mimeData()),
                                                   'target': target})
        elif (isinstance(event.mimeData(), ItemDragData)
              and event.mimeData().library is self.browser.library):
            rows = [self.browser.tree.itemFromIndex(QtCore.QModelIndex(index)) for index in event.mimeData().indexes
                    if index.isValid()]
            self.browser.library.dnd_move_internal(target, items=rows)
        else:
            event.ignore()
            return
        event.setDropAction(QtCore.Qt.DropAction.CopyAction)
        event.accept()


class LibraryView(QtWidgets.QWidget):
    """Keep both presentations of the library tied to one tree model."""
    def __init__(self, library):
        super().__init__(library)
        self.library = library
        settings = library.settings
        if not hasattr(settings, '_library_view_preferences'):
            settings._library_view_preferences = LibraryViewPreferences(settings, library.plugin.name)
        self.preferences = settings._library_view_preferences
        self.tree = library.list_view
        self.tree.setFont(QtWidgets.fluentqt.font_for_role(QtWidgets.fluentqt.FontRole.Body))
        self.folder = QtCore.QPersistentModelIndex()
        self.syncing = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.navigation = QtWidgets.QWidget(self)
        self.navigation.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        navigation_layout = QtWidgets.QHBoxLayout(self.navigation)
        navigation_layout.setContentsMargins(8, 0, 8, 0)
        self.navigation_commands = SpacedCommandBar(self.navigation)
        self.navigation_commands.setBackgroundVisible(False)
        self.navigation_commands.setDynamicOverflowEnabled(False)
        self.navigation_commands.setLabelPosition(CommandBar.LabelPosition.Right)
        self.navigation_commands.setFixedHeight(Spacing.ControlHeight.Large)
        self.navigation_commands.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum,
                                               QtWidgets.QSizePolicy.Policy.Fixed)
        self.up_action = QtGui.QAction(UiIcons().arrow_turn_left_up, tr('Up'), self)
        self.up_action.triggered.connect(self.go_up)
        self.navigation_commands.addPrimaryAction(self.up_action)
        navigation_layout.addWidget(self.navigation_commands)
        self.breadcrumbs = Breadcrumb(self.navigation)
        self.breadcrumbs.setAutoTruncateOnItemClick(False)
        self.breadcrumbs.setOverflowMode(Breadcrumb.OverflowMode.Middle)
        self.breadcrumbs.itemActivated.connect(self.activate_breadcrumb)
        navigation_layout.addWidget(self.breadcrumbs, 1)
        layout.addWidget(self.navigation)
        layout.addWidget(self.tree, 1)
        self.grid = LibraryGrid(self)
        self.grid.setFontRole(QtWidgets.fluentqt.FontRole.Body)
        layout.addWidget(self.grid, 1)
        self.footer = LibraryFooter(self)
        footer_layout = self.footer.layout()
        self.count_label = self.footer.count_label
        self.thumbnail_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal, self.footer,
                                                  show_value_tooltip=False)
        self.thumbnail_slider.setObjectName('library_thumbnail_size')
        self.thumbnail_slider.setRange(50, 200)
        self.thumbnail_slider.setSingleStep(10)
        self.thumbnail_slider.setPageStep(25)
        self.thumbnail_slider.setMinimumWidth(48)
        self.thumbnail_slider.setMaximumWidth(100)
        self.thumbnail_slider.setAccessibleName(tr('Thumbnail size'))
        self.thumbnail_slider.installEventFilter(self)
        self.thumbnail_slider.valueChanged.connect(self.preferences.set_thumbnail_size)
        footer_layout.addWidget(self.thumbnail_slider)
        self.view_buttons = QtWidgets.QButtonGroup(self)
        self.list_button = QtWidgets.QPushButton(tr('List'))
        self.grid_button = QtWidgets.QPushButton(tr('Grid'))
        for index, (button, icon) in enumerate(((self.list_button, UiIcons().view_list),
                                               (self.grid_button, UiIcons().view_grid))):
            button.setIcon(icon)
            button.setFluentSize(Button.ButtonSize.Small)
            button.setFluentStyle(Button.ButtonStyle.Subtle)
            button.setCheckable(True)
            self.view_buttons.addButton(button, index)
            footer_layout.addWidget(button)
        layout.addWidget(self.footer)
        self.view_buttons.idClicked.connect(self.set_view)
        self.grid.itemSelectionChanged.connect(self.select_tree_items)
        self.tree.itemSelectionChanged.connect(self.select_tiles)
        self.grid.itemDoubleClicked.connect(self.activate_tile)
        self.grid.customContextMenuRequested.connect(library.context_menu)
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.refresh)
        model = self.tree.model()
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset, model.dataChanged,
                       model.layoutChanged, model.rowsMoved):
            signal.connect(self.schedule_refresh)
        self.preferences.view_changed.connect(self.apply_view)
        self.preferences.thumbnail_size_changed.connect(self.apply_thumbnail_size)
        self.apply_thumbnail_size(self.preferences.size)
        self.apply_view(self.preferences.mode)

    def schedule_refresh(self, *args):
        self.refresh_timer.start(0)

    def eventFilter(self, watched, event):
        if watched is self.thumbnail_slider and event.type() == QtCore.QEvent.Type.MouseButtonDblClick \
                and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.thumbnail_slider.setValue(100)
            self.thumbnail_slider.setSliderDown(False)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def handle_mime_data(self, data):
        self.library.handle_mime_data(data)

    def dnd_move_internal(self, target):
        self.library.dnd_move_internal(target)

    def folder_item(self):
        return self.tree.itemFromIndex(QtCore.QModelIndex(self.folder)) if self.folder.isValid() else None

    def set_view(self, mode):
        self.preferences.set_view(mode)

    def apply_view(self, mode):
        if mode:
            current = self.tree.currentItem()
            if current:
                data = current.data(0, QtCore.Qt.ItemDataRole.UserRole)
                folder = current if isinstance(data, self.library.folder_class) else current.parent()
                self.folder = QtCore.QPersistentModelIndex(self.tree.indexFromItem(folder))
        self.grid.setVisible(bool(mode))
        self.tree.setVisible(not mode)
        self.navigation.setVisible(bool(mode))
        self.view_buttons.button(mode).setChecked(True)
        self.refresh()

    def apply_thumbnail_size(self, size):
        with QtCore.QSignalBlocker(self.thumbnail_slider):
            self.thumbnail_slider.setValue(size)
        self.grid.setIconSize(QtCore.QSize(round(148 * size / 100), round(84 * size / 100)))
        self.grid.setCellSize(self.tile_size())
        self.refresh()

    def tile_size(self):
        return self.grid.iconSize() + QtCore.QSize(12, 32)

    def apply_list_thumbnail_size(self):
        size = QtCore.QSize(round(64 * self.preferences.size / 100), round(36 * self.preferences.size / 100))
        if self.tree.iconSize() != size:
            self.tree.setIconSize(size)
            self.tree.doItemsLayout()

    def refresh(self):
        self.apply_list_thumbnail_size()
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        count = 0
        while iterator.value():
            count += isinstance(iterator.value().data(0, QtCore.Qt.ItemDataRole.UserRole), self.library.item_class)
            iterator += 1
        self.footer.set_count(count)
        if not self.grid_button.isChecked():
            return
        parent = self.folder_item() or self.tree.invisibleRootItem()
        self.up_action.setEnabled(self.folder.isValid())
        crumbs = []
        folder = self.folder_item()
        while folder:
            crumbs.insert(0, BreadcrumbItem(folder.data(0, QtCore.Qt.ItemDataRole.UserRole).name,
                                            QtCore.QPersistentModelIndex(self.tree.indexFromItem(folder))))
            folder = folder.parent()
        self.breadcrumbs.setItems([BreadcrumbItem(tr('Library'), QtCore.QPersistentModelIndex())] + crumbs)
        scroll_position = self.grid.verticalScrollBar().value()
        with QtCore.QSignalBlocker(self.grid):
            self.grid.clear()
            self.grid.setSelectionMode(self.tree.selectionMode())
            for row in range(parent.childCount()):
                item = parent.child(row)
                if item.isHidden():
                    continue
                tile = NativeWidgets.QListWidgetItem(self.thumbnail_icon(item), item.text(0), self.grid._item_store)
                tile.setSizeHint(self.tile_size())
                tile.setData(LIBRARY_FOLDER_ROLE,
                             isinstance(item.data(0, QtCore.Qt.ItemDataRole.UserRole), self.library.folder_class))
                tile.setToolTip(item.toolTip(0) or item.text(0))
                tile.setData(QtCore.Qt.ItemDataRole.UserRole,
                             QtCore.QPersistentModelIndex(self.tree.indexFromItem(item)))
        self.select_tiles()
        self.grid.doItemsLayout()
        self.grid.verticalScrollBar().setValue(scroll_position)

    def thumbnail_icon(self, item):
        data = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(data, self.library.folder_class):
            return UiIcons().fluent_folder
        if not isinstance(data, self.library.item_class):
            return item.icon(0)
        path = item.data(0, LIBRARY_THUMBNAIL_ROLE)
        if self.library.plugin.name == 'images':
            path = data.file_path
        elif self.library.plugin.name == 'media' and hasattr(self.library, 'generate_thumbnail_path'):
            path = self.library.generate_thumbnail_path(data)
        if path:
            reader = QtGui.QImageReader(str(path))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(self.grid.iconSize(), QtCore.Qt.AspectRatioMode.KeepAspectRatio))
                image = reader.read()
                if not image.isNull():
                    return QtGui.QIcon(QtGui.QPixmap.fromImage(image))
        return item.icon(0)

    def select_tree_items(self):
        if self.syncing:
            return
        self.syncing = True
        try:
            with QtCore.QSignalBlocker(self.tree):
                self.tree.clearSelection()
                current = self.grid.tree_item(self.grid.currentItem())
                if current:
                    self.tree.setCurrentItem(current, 0, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)
                for tile in self.grid.selectedItems():
                    item = self.grid.tree_item(tile)
                    if item:
                        item.setSelected(True)
            self.tree.itemSelectionChanged.emit()
        finally:
            self.syncing = False

    def select_tiles(self):
        if self.syncing:
            return
        with QtCore.QSignalBlocker(self.grid):
            for row in range(self.grid.count()):
                tile = self.grid.item(row)
                item = self.grid.tree_item(tile)
                tile.setSelected(bool(item and item.isSelected()))
                if item and item is self.tree.currentItem():
                    self.grid.setCurrentItem(tile, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)

    def activate_tile(self, tile):
        item = self.grid.tree_item(tile)
        if not item:
            return
        if isinstance(item.data(0, QtCore.Qt.ItemDataRole.UserRole), self.library.folder_class):
            self.folder = QtCore.QPersistentModelIndex(self.tree.indexFromItem(item))
            item.setExpanded(True)
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)
            self.refresh()
        else:
            self.library.on_double_clicked(self.tree.indexFromItem(item))

    def go_up(self):
        self.folder = QtCore.QPersistentModelIndex(self.folder.parent())
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
        self.refresh()

    def activate_breadcrumb(self, index, item):
        self.folder = QtCore.QPersistentModelIndex(item.data)
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
        self.refresh()
