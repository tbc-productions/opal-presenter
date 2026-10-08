"""Exercise real wrapping tiles, model changes and shared tree selection."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import fluentqt
from fluentqt import Breadcrumb, Button, CommandBar, GridView
from fluentqt.design import Spacing
from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.app import OpenLP
from openlp.core.common.settings import Settings
from openlp.core.ui.icons import UiIcons
from openlp.core.widgets.libraryview import LibraryView
from openlp.core.widgets.fluent_tree import LIBRARY_FOLDER_ROLE
from openlp.core.widgets.views import TreeWidgetWithDnD
from openlp.plugins.images.lib.db import Folder, Item


@pytest.fixture(scope='session')
def native_application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def qapp(native_application):
    return OpenLP()


@pytest.fixture(params=['images', 'media', 'presentations'])
def browser(qtbot, settings, request):
    library = QtWidgets.QWidget()
    qtbot.addWidget(library)
    library.plugin = SimpleNamespace(name=request.param)
    library.settings = settings
    library.item_class = Item
    library.folder_class = Folder
    library.context_menu = MagicMock()
    library.on_double_clicked = MagicMock()
    library.handle_mime_data = MagicMock()
    library.dnd_move_internal = MagicMock()
    library.list_view = TreeWidgetWithDnD(library, request.param)
    library.list_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    image = QtGui.QPixmap(160, 90)
    image.fill(QtGui.QColor('#df8133'))
    folder = QtWidgets.QTreeWidgetItem(['Backgrounds'])
    folder.setData(0, QtCore.Qt.ItemDataRole.UserRole, Folder(id=1, name='Backgrounds'))
    folder.setData(0, LIBRARY_FOLDER_ROLE, True)
    library.list_view.addTopLevelItem(folder)
    for index in range(7):
        item = QtWidgets.QTreeWidgetItem([f'Image {index}'])
        item.setData(0, QtCore.Qt.ItemDataRole.UserRole, Item(id=index + 1, file_path=f'{index}.png'))
        item.setIcon(0, QtGui.QIcon(image))
        if index == 6:
            folder.addChild(item)
        else:
            library.list_view.addTopLevelItem(item)
    view = LibraryView(library)
    view.setParent(None)
    qtbot.addWidget(view)
    view.resize(570, 450)
    view.show()
    return view


def test_footer_count_tracks_nested_imports_and_deletes(qtbot, browser):
    assert browser.count_label.text() == '7 items'
    folder = browser.tree.topLevelItem(0)
    folder.takeChild(0)
    qtbot.waitUntil(lambda: browser.count_label.text() == '6 items')
    browser.tree.clear()
    qtbot.waitUntil(lambda: browser.count_label.text() == '0 items')


def test_grid_wraps_and_retains_multiple_selection(qtbot, browser):
    browser.grid_button.click()
    qtbot.wait(20)
    assert browser.grid.count() == 7
    assert browser.tree.isHidden()
    grid = browser.grid
    qtbot.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=grid.visualItemRect(grid.item(1)).center())
    qtbot.mouseClick(grid.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     stateKey=QtCore.Qt.KeyboardModifier.ControlModifier,
                     pos=grid.visualItemRect(grid.item(2)).center())
    assert len(browser.tree.selectedItems()) == 2
    browser.list_button.click()
    assert len(browser.tree.selectedItems()) == 2
    browser.grid_button.click()
    assert len(grid.selectedItems()) == 2
    wide = grid.visualItemRect(grid.item(4)).top()
    browser.resize(380, 450)
    qtbot.wait(20)
    assert grid.visualItemRect(grid.item(4)).top() > wide
    assert browser.library.settings.value('advanced/library view') == 'grid'


def test_thumbnail_slider_resizes_list_rows_and_grid_cards(browser):
    tree = browser.tree
    tree.setCurrentItem(tree.topLevelItem(1))
    browser.grid_button.click()
    browser.thumbnail_slider.setValue(200)
    assert browser.grid.iconSize() == QtCore.QSize(296, 168)
    assert browser.grid.item(1).sizeHint() == QtCore.QSize(308, 200)
    assert tree.selectedItems() == [tree.topLevelItem(1)]
    browser.list_button.click()
    assert tree.iconSize() == QtCore.QSize(128, 72)
    delegate = tree.itemDelegate()
    option = QtWidgets.QStyleOptionViewItem()
    assert delegate.sizeHint(option, tree.indexFromItem(tree.topLevelItem(1))).height() == 84
    assert delegate.iconSize(option, tree.indexFromItem(tree.topLevelItem(0))) == QtCore.QSize(34, 34)
    assert delegate.sizeHint(option, tree.indexFromItem(tree.topLevelItem(0))).height() == 46
    browser.thumbnail_slider.setValue(50)
    assert tree.iconSize() == QtCore.QSize(32, 18)
    assert delegate.sizeHint(option, tree.indexFromItem(tree.topLevelItem(1))).height() == 36
    assert delegate.iconSize(option, tree.indexFromItem(tree.topLevelItem(0))) == QtCore.QSize(34, 34)


def test_thumbnail_slider_double_click_resets_without_tooltips(qtbot, browser):
    slider = browser.thumbnail_slider
    slider.setValue(175)
    assert not slider.toolTip()
    qtbot.mousePress(slider, QtCore.Qt.MouseButton.LeftButton, pos=slider.rect().center())
    assert not slider._value_tooltip or not slider._value_tooltip.isVisible()
    qtbot.mouseMove(slider, slider.rect().center() + QtCore.QPoint(3, 0))
    assert not slider._value_tooltip or not slider._value_tooltip.isVisible()
    qtbot.mouseRelease(slider, QtCore.Qt.MouseButton.LeftButton, pos=slider.rect().center())
    qtbot.mouseDClick(slider, QtCore.Qt.MouseButton.LeftButton, pos=slider.rect().center())
    assert slider.value() == 100
    assert browser.preferences.size == 100
    assert browser.library.settings.value('advanced/library thumbnail size') == 100


def test_list_thumbnail_scales_small_cached_images_to_selected_size(qtbot, browser):
    image = QtGui.QPixmap(88, 50)
    image.fill(QtGui.QColor('#df8133'))
    image.setDevicePixelRatio(2)
    browser.tree.topLevelItem(1).setIcon(0, QtGui.QIcon(image))
    browser.thumbnail_slider.setValue(200)
    qtbot.wait(10)
    rendered = browser.tree.viewport().grab().toImage()
    widest = max(sum(rendered.pixelColor(x, y).name() == '#df8133' for x in range(rendered.width()))
                 for y in range(rendered.height()))
    assert 125 <= widest <= 128


def test_preferences_sync_across_libraries_and_restore_from_disk(qtbot, settings):
    views = [browser.__wrapped__(qtbot, settings, SimpleNamespace(param=name))
             for name in ('images', 'media', 'presentations')]
    views[0].grid_button.click()
    views[0].thumbnail_slider.setValue(150)
    assert all(view.grid_button.isChecked() and view.thumbnail_slider.value() == 150 for view in views)
    assert all(view.grid.iconSize() == QtCore.QSize(222, 126) for view in views)
    views[1].list_button.click()
    assert all(view.list_button.isChecked() for view in views)
    views[2].grid_button.click()
    settings.sync()
    restored_settings = Settings()
    restored = browser.__wrapped__(qtbot, restored_settings, SimpleNamespace(param='media'))
    assert restored.grid_button.isChecked()
    assert restored.thumbnail_slider.value() == 150
    assert restored.tree.iconSize() == QtCore.QSize(96, 54)


def test_existing_view_choice_migrates_to_shared_setting(qtbot, settings):
    settings.setValue('presentations/library view', 'grid')
    view = browser.__wrapped__(qtbot, settings, SimpleNamespace(param='images'))
    assert view.grid_button.isChecked()
    assert settings.value('advanced/library view') == 'grid'


def test_grid_folders_use_scalable_fluent_folder_icon(browser):
    browser.grid_button.click()
    assert browser.grid.item(0).icon().cacheKey() == UiIcons().fluent_folder.cacheKey()
    browser.thumbnail_slider.setValue(200)
    assert browser.grid.item(0).icon().cacheKey() == UiIcons().fluent_folder.cacheKey()


def test_grid_folder_navigation_and_deleted_folder_return_to_root(qtbot, browser):
    browser.grid_button.click()
    browser.activate_tile(browser.grid.item(0))
    assert browser.grid.count() == 1
    assert [item.text for item in browser.breadcrumbs.items()] == ['Library', 'Backgrounds']
    browser.grid.setCurrentRow(0)
    browser.activate_tile(browser.grid.item(0))
    browser.library.on_double_clicked.assert_called_once_with(
        browser.tree.indexFromItem(browser.folder_item().child(0)))
    browser.go_up()
    assert browser.grid.count() == 7
    browser.activate_tile(browser.grid.item(0))
    browser.tree.takeTopLevelItem(0)
    qtbot.waitUntil(lambda: browser.grid.count() == 6)
    assert not browser.up_action.isEnabled()


def test_grid_navigation_uses_commands_and_clickable_fluent_breadcrumbs(qtbot, browser):
    folder = browser.tree.topLevelItem(0)
    nested = QtWidgets.QTreeWidgetItem(['Nested'])
    nested.setData(0, QtCore.Qt.ItemDataRole.UserRole, Folder(id=2, name='Nested'))
    nested.setData(0, LIBRARY_FOLDER_ROLE, True)
    folder.addChild(nested)
    browser.grid_button.click()
    browser.activate_tile(browser.grid.item(0))
    browser.activate_tile(browser.grid.item(1))
    assert isinstance(browser.navigation_commands, CommandBar)
    assert browser.navigation_commands.primaryActions() == [browser.up_action]
    assert browser.up_action.icon().name() == 'ic_fluent_arrow_turn_left_up_20_regular'
    assert isinstance(browser.breadcrumbs, Breadcrumb)
    assert [item.text for item in browser.breadcrumbs.items()] == ['Library', 'Backgrounds', 'Nested']
    qtbot.mouseClick(browser.breadcrumbs, QtCore.Qt.MouseButton.LeftButton,
                     pos=browser.breadcrumbs.itemGeometry(1).center())
    assert browser.folder_item() is folder
    browser.up_action.trigger()
    assert browser.folder_item() is None
    browser.activate_tile(browser.grid.item(0))
    qtbot.mouseClick(browser.breadcrumbs, QtCore.Qt.MouseButton.LeftButton,
                     pos=browser.breadcrumbs.itemGeometry(0).center())
    assert browser.folder_item() is None


def test_navigation_row_removes_padding_without_clipping_fluent_commands(qtbot, browser):
    browser.grid_button.click()
    for height in (450, 900):
        browser.resize(570, height)
        qtbot.wait(10)
        assert browser.navigation.height() == Spacing.ControlHeight.Large
        assert browser.navigation_commands.y() == browser.breadcrumbs.y() == 0
        command = next(button for button in browser.navigation_commands.findChildren(Button)
                       if button.isVisible() and button.property('commandAction') == browser.up_action)
        assert browser.navigation_commands.rect().contains(command.geometry())
        assert browser.grid.y() == browser.navigation.height()


def test_view_buttons_are_small_subtle_fluent_controls(browser):
    for button in (browser.list_button, browser.grid_button):
        assert button.fluentSize() == Button.ButtonSize.Small
        assert button.fluentStyle() == Button.ButtonStyle.Subtle
    browser.grid_button.click()
    assert browser.grid_button.isChecked()
    assert not browser.list_button.isChecked()


def test_tree_group_spacing_tracks_the_last_visible_child(browser):
    tree = browser.tree
    folder = tree.topLevelItem(0)
    first = folder.child(0)
    last = tree.takeTopLevelItem(1)
    folder.addChild(last)
    tree.expandAll()
    delegate = tree.itemDelegate()
    assert tree.indentation() == 40
    assert delegate.group_spacing(tree.indexFromItem(first)) == 0
    assert delegate.group_spacing(tree.indexFromItem(last)) == 8
    assert delegate.group_spacing(tree.indexFromItem(tree.topLevelItem(1))) == 0
    last.setHidden(True)
    assert delegate.group_spacing(tree.indexFromItem(first)) == 8


def test_grid_uses_fluent_card_stroke_for_unselected_tiles(browser):
    grid = browser.grid
    assert isinstance(grid, GridView)
    assert grid.horizontalSpacing() == grid.verticalSpacing() == 6
    assert grid.cellSize() == grid.iconSize() + QtCore.QSize(12, 32)
    option = QtWidgets.QStyleOptionViewItem()
    option.rect = QtCore.QRect(0, 0, 160, 116)
    option.font = grid.font()
    option.fontMetrics = QtGui.QFontMetrics(option.font)
    browser.grid_button.click()
    canvas = QtGui.QImage(160, 116, QtGui.QImage.Format.Format_ARGB32)
    canvas.fill(QtGui.QColor('magenta'))
    painter = QtGui.QPainter(canvas)
    index = grid.model().index(1, 0)
    grid.itemDelegate().paint(painter, option, index)
    unselected = canvas.pixelColor(10, 2)
    reference = QtGui.QImage(canvas.size(), canvas.format())
    reference.fill(QtGui.QColor('magenta'))
    reference_painter = QtGui.QPainter(reference)
    reference_painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    reference_painter.setPen(QtGui.QPen(grid.itemDelegate().theme.theme_tokens().colors.strokeCard, 1))
    reference_painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    reference_painter.drawRoundedRect(option.rect.adjusted(2, 2, -2, -2), 4, 4)
    reference_painter.end()
    assert unselected == reference.pixelColor(10, 2)
    assert unselected != QtGui.QColor('magenta')
    option.state |= QtWidgets.QStyle.StateFlag.State_Selected
    grid.itemDelegate().paint(painter, option, index)
    painter.end()
    assert canvas.pixelColor(10, 2) != unselected


@pytest.mark.parametrize('theme', [fluentqt.Theme.Light, fluentqt.Theme.Dark])
def test_folder_icons_use_theme_chart7_without_hierarchy_guides(browser, theme):
    previous = fluentqt.current_theme()
    try:
        fluentqt.set_theme(theme)
        tree = browser.tree
        delegate = tree.itemDelegate()
        option = QtWidgets.QStyleOptionViewItem()
        option.rect = QtCore.QRect(0, 0, 400, 46)
        option.state = QtWidgets.QStyle.StateFlag.State_Enabled
        painter = MagicMock()
        delegate.paint(painter, option, tree.indexFromItem(tree.topLevelItem(0)))
        painter.drawLine.assert_not_called()
        pixmap = painter.drawPixmap.call_args.args[1]
        image = pixmap.toImage()
        chart7 = delegate._theme_host.theme_tokens().colors.charts[6]
        assert any(image.pixelColor(x, y) == chart7 for x in range(image.width()) for y in range(image.height()))
        browser.grid_button.click()
        grid = browser.grid
        option.rect.setSize(grid.cellSize())
        canvas = QtGui.QImage(grid.cellSize(), QtGui.QImage.Format.Format_ARGB32)
        canvas.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(canvas)
        grid.itemDelegate().paint(painter, option, grid.model().index(0, 0))
        painter.end()
        assert any(canvas.pixelColor(x, y) == chart7 for x in range(canvas.width()) for y in range(canvas.height()))
    finally:
        fluentqt.set_theme(previous)


def test_grid_drag_uses_library_mime_and_import_target(browser):
    browser.grid_button.click()
    browser.grid.setCurrentRow(1)
    with patch('openlp.core.widgets.libraryview.QtGui.QDrag') as drag:
        browser.grid.startDrag(QtCore.Qt.DropAction.CopyAction)
    mime = drag.return_value.setMimeData.call_args.args[0]
    assert mime.text() == browser.library.plugin.name
    assert bytes(mime.data('application/x-openlp-item-title')) == b'Image 0'
    folder = browser.tree.topLevelItem(0)
    browser.activate_tile(browser.grid.item(0))
    drop = MagicMock()
    urls = QtCore.QMimeData()
    urls.setUrls([QtCore.QUrl.fromLocalFile('/tmp/new.png')])
    drop.mimeData.return_value = urls
    drop.position.return_value = QtCore.QPointF(500, 400)
    browser.grid.dropEvent(drop)
    assert browser.library.handle_mime_data.call_args.args[0]['target'] is folder
