"""Exercise item identity, native drag feedback and controller transfers."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from openlp.core.common.registry import Registry
from openlp.core.lib import ServiceItemContext
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.ui.fluenticons import service_icon
from openlp.core.ui.icons import UiIcons
from openlp.core.ui.slidecontroller import SlideController
from openlp.core.widgets.dnd import ItemDragData, ThemeDragData, execute_drag
from openlp.core.widgets.fluent_tooltips import FluentToolTip, install_fluent_tooltips
from openlp.core.widgets.views import ListWidgetWithDnD

pytestmark = pytest.mark.usefixtures('qapp')


def song(title='Song'):
    item = ServiceItem(SimpleNamespace(name='songs'))
    item.title = title
    item.add_from_text('First slide')
    item.add_icon()
    return item


@pytest.fixture()
def library(qtbot, settings):
    widget = QtWidgets.QWidget()
    qtbot.addWidget(widget)
    widget.plugin = SimpleNamespace(name='songs')
    widget.single_service_item = False
    widget.can_preview = widget.can_make_live = widget.can_add_to_service = True
    widget.get_library_tab_icon = lambda: service_icon(UiIcons().music, 'songs')
    widget.list_view = ListWidgetWithDnD(widget, 'songs')
    for label in ('A', 'B', 'C'):
        widget.list_view.addItem(label)
    widget.list_view.item(0).setSelected(True)
    widget.list_view.item(1).setSelected(True)
    widget.build_service_item = MagicMock(side_effect=lambda item, context: song(item.text()))
    return widget


def test_library_drag_keeps_original_rows_after_selection_changes(library):
    mime = ItemDragData(library=library)
    library.list_view.clearSelection()
    library.list_view.item(2).setSelected(True)
    assert [item.title for item in mime.service_items()] == ['A', 'B']
    assert mime.can_drop('service')
    assert not mime.can_drop('live')  # A controller can load one song at a time.


def test_deleted_library_row_invalidates_drag(library):
    mime = ItemDragData(library=library)
    library.list_view.takeItem(0)
    assert not mime.can_drop('service')
    assert mime.service_items() == []
    library.build_service_item.assert_not_called()


def test_grouped_library_drag_builds_one_item_with_all_captured_rows(library):
    library.single_service_item = True
    library.build_service_item.side_effect = lambda item, context: song('Group')
    mime = ItemDragData(library=library)
    library.list_view.clearSelection()
    assert mime.can_drop('preview')
    assert len(mime.service_items(ServiceItemContext.Preview)) == 1
    assert [row.text() for row in library.build_service_item.call_args.kwargs['item']] == ['A', 'B']


@pytest.mark.parametrize('name,icon', [
    ('songs', 'music'), ('custom', 'custom'), ('images', 'picture'),
    ('media', 'video'), ('presentations', 'presentation')])
def test_all_library_drags_paint_the_coloured_icon_and_use_a_plain_cursor(library, name, icon):
    library.plugin.name = name
    library.get_library_tab_icon = lambda: service_icon(getattr(UiIcons(), icon), name)
    mime = ItemDragData(library=library)
    with patch('openlp.core.widgets.dnd.QtGui.QDrag') as drag:
        execute_drag(library.list_view, mime)
    pixmap = drag.return_value.setPixmap.call_args.args[0]
    image = pixmap.toImage()
    expected = mime.icon.pixmap(40, 40).toImage()
    expected_colors = {expected.pixelColor(x, y).name() for x in range(expected.width())
                       for y in range(expected.height()) if expected.pixelColor(x, y).alpha() == 255}
    ratio = pixmap.devicePixelRatio()
    assert any(image.pixelColor(x, y).name() in expected_colors
               for x in range(int(8 * ratio), int(48 * ratio))
               for y in range(int(8 * ratio), int(48 * ratio)))
    cursors = drag.return_value.setDragCursor.call_args_list
    assert [call.args[1] for call in cursors] == [QtCore.Qt.DropAction.CopyAction, QtCore.Qt.DropAction.MoveAction]
    cursor_image = cursors[0].args[0].toImage()
    assert all(color.red() == color.green() == color.blue()
               for x in range(cursor_image.width()) for y in range(cursor_image.height())
               if (color := cursor_image.pixelColor(x, y)).alpha())


@pytest.mark.parametrize('result', [QtCore.Qt.DropAction.CopyAction, QtCore.Qt.DropAction.IgnoreAction, RuntimeError])
def test_drag_clears_hover_feedback_on_drop_cancel_and_failure(library, result):
    view = library.list_view
    view.show()
    viewport = view.viewport()
    tooltip_filter = install_fluent_tooltips(QtWidgets.QApplication.instance())
    view.item(0).setToolTip('Old label')
    view.item(2).setToolTip('Fresh label')
    point = view.visualItemRect(view.item(0)).center()
    FluentToolTip.showText(viewport.mapToGlobal(point), 'Old label', viewport)
    view.setState(QtWidgets.QAbstractItemView.State.DraggingState)

    def native_drag(*args):
        assert not FluentToolTip.isVisible()
        event = QtGui.QHelpEvent(QtCore.QEvent.Type.ToolTip, point, viewport.mapToGlobal(point))
        QtWidgets.QApplication.sendEvent(viewport, event)
        FluentToolTip.showText(viewport.mapToGlobal(point), 'Old label', viewport)
        assert not FluentToolTip.isVisible()
        if result is RuntimeError:
            raise RuntimeError('Drag failed')
        return result

    with patch('openlp.core.widgets.dnd.QtGui.QDrag') as drag:
        drag.return_value.exec.side_effect = native_drag
        if result is RuntimeError:
            with pytest.raises(RuntimeError, match='Drag failed'):
                execute_drag(view, ItemDragData(library=library))
        else:
            assert execute_drag(view, ItemDragData(library=library)) == result
    QtWidgets.QApplication.sendEvent(viewport, QtGui.QEnterEvent(
        QtCore.QPointF(point), QtCore.QPointF(point), QtCore.QPointF(viewport.mapToGlobal(point))))
    assert not FluentToolTip.isVisible()
    assert not tooltip_filter.drag_active
    assert view.state() == QtWidgets.QAbstractItemView.State.NoState
    point = view.visualItemRect(view.item(2)).center()
    event = QtGui.QHelpEvent(QtCore.QEvent.Type.ToolTip, point, viewport.mapToGlobal(point))
    QtWidgets.QApplication.sendEvent(viewport, event)
    assert FluentToolTip.text() == 'Fresh label'
    FluentToolTip.hideText()


@pytest.fixture()
def controller(qtbot, settings, registry):
    manager = MagicMock(service_items=[])
    registry.register('service_manager', manager)
    controller = SlideController()
    qtbot.addWidget(controller)
    controller.panel = QtWidgets.QWidget()
    qtbot.addWidget(controller.panel)
    controller.panel.resize(400, 400)
    controller.preview_display = QtWidgets.QWidget(controller.panel)
    controller.preview_widget = QtWidgets.QTableWidget(controller.panel)
    controller.preview_widget.current_slide_number = lambda: 2
    controller.service_item = song()
    controller.add_service_manager_item = MagicMock()
    controller._setup_item_drag_drop()
    controller.panel.show()
    return controller


@pytest.mark.parametrize('live', [False, True])
@pytest.mark.parametrize('surface', ['preview_widget', 'preview_display'])
def test_controller_drop_loads_captured_slide_only_on_release(controller, live, surface):
    controller.is_live = live
    item = song()
    mime = ItemDragData(item=item, slide_no=2)
    target = getattr(controller, surface)
    enter = QtGui.QDragEnterEvent(
        QtCore.QPoint(30, 30), QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    controller.eventFilter(target, enter)
    assert enter.isAccepted() and controller._drop_hint.isVisible()
    controller.add_service_manager_item.assert_not_called()
    drop = QtGui.QDropEvent(
        QtCore.QPointF(30, 30), QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    controller.eventFilter(target, drop)
    assert drop.isAccepted() and not controller._drop_hint.isVisible()
    controller.add_service_manager_item.assert_called_once_with(item, 2, service_list_index=None)


def test_controller_rejects_self_drop_and_external_text(controller):
    for mime in (ItemDragData(item=controller.service_item, controller=controller), QtCore.QMimeData()):
        event = QtGui.QDragEnterEvent(
            QtCore.QPoint(10, 10), QtCore.Qt.DropAction.CopyAction, mime,
            QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        controller.eventFilter(controller.panel, event)
        assert not event.isAccepted()
    controller.add_service_manager_item.assert_not_called()


def test_controller_registers_late_display_children_as_drop_targets(controller):
    surface = QtWidgets.QWidget(controller.preview_display)
    surface.ensurePolished()
    assert surface.acceptDrops()
    mime = ItemDragData(item=song())
    event = QtGui.QDragEnterEvent(
        QtCore.QPoint(10, 10), QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(surface, event)
    assert event.isAccepted()


def test_controller_filter_handles_teardown_after_display_is_deleted(controller):
    controller.preview_display.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    controller.eventFilter(controller.panel, QtCore.QEvent(QtCore.QEvent.Type.Hide))


def test_live_service_drop_uses_existing_live_action_and_selected_slide(controller):
    controller.is_live = True
    item = song()
    item.from_service = True
    controller.service_manager.service_items = [{'service_item': item}]
    assert controller.drop_item(ItemDragData(item=item, slide_no=2))
    controller.service_manager.preview_live.assert_called_once_with(item.unique_identifier, 2)
    controller.add_service_manager_item.assert_not_called()


def test_preview_media_is_stopped_when_dropped_live(controller):
    controller.is_live = True
    item = song()
    item.is_command = lambda: True
    item.is_media = lambda: True
    source = MagicMock(is_live=False)
    with patch.object(Registry(), 'execute') as execute:
        assert controller.drop_item(ItemDragData(item=item, controller=source))
    execute.assert_called_once_with('songs_stop', [item, False])
    source.on_media_close.assert_called_once()


@pytest.fixture()
def theme_drag(qtbot):
    view = QtWidgets.QListWidget()
    qtbot.addWidget(view)
    view.addItems(['Ocean (default)', 'Warm'])
    view.item(0).setData(QtCore.Qt.ItemDataRole.UserRole, 'Ocean')
    view.item(1).setData(QtCore.Qt.ItemDataRole.UserRole, 'Warm')
    view.setCurrentRow(0)
    manager = SimpleNamespace(get_theme_names=lambda: ['Ocean', 'Warm'])
    return view, ThemeDragData(manager, view.selectedIndexes())


@pytest.mark.parametrize('name,accepted', [
    ('songs', True), ('custom', True), ('bibles', True), ('images', False),
    ('media', False), ('presentations', False)])
def test_theme_payload_accepts_only_supported_text_items(theme_drag, name, accepted):
    view, mime = theme_drag
    item = song()
    item.name = name
    view.setCurrentRow(1)
    assert mime.title == 'Ocean'
    assert mime.can_drop(item) is accepted
    assert not mime.can_drop(None)
    item.is_valid = False
    assert not mime.can_drop(item)


@pytest.mark.parametrize('change', ['deleted', 'renamed', 'unloaded', 'multiple'])
def test_theme_payload_rejects_stale_or_multiple_themes(theme_drag, change):
    view, mime = theme_drag
    if change == 'deleted':
        view.takeItem(0)
    elif change == 'renamed':
        view.item(0).setData(QtCore.Qt.ItemDataRole.UserRole, 'Renamed')
    elif change == 'unloaded':
        mime.manager.get_theme_names = lambda: ['Warm']
    else:
        view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        view.item(1).setSelected(True)
        mime = ThemeDragData(mime.manager, view.selectedIndexes())
    assert not mime.can_drop(song())


@pytest.mark.parametrize('live', [False, True])
@pytest.mark.parametrize('surface', ['panel', 'preview_widget', 'preview_display'])
def test_controller_theme_drop_updates_current_item_only_on_release(controller, theme_drag, live, surface):
    controller.is_live = live
    _, mime = theme_drag
    target = getattr(controller, surface)
    item = controller.service_item
    enter = QtGui.QDragEnterEvent(
        QtCore.QPoint(30, 30), QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    controller.eventFilter(target, enter)
    assert enter.isAccepted() and controller._drop_hint.isVisible()
    assert controller._drop_hint.text() == 'Drop to apply theme'
    controller.service_manager.apply_theme_to_item.assert_not_called()
    drop = QtGui.QDropEvent(
        QtCore.QPointF(30, 30), QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    controller.eventFilter(target, drop)
    assert drop.isAccepted() and not controller._drop_hint.isVisible()
    controller.service_manager.apply_theme_to_item.assert_called_once_with(item, 'Ocean')
    controller.add_service_manager_item.assert_not_called()


@pytest.mark.parametrize('live', [False, True])
@pytest.mark.parametrize('name', [None, 'images', 'presentations', 'media'])
def test_controller_rejects_theme_without_supported_current_item(controller, theme_drag, live, name):
    controller.is_live = live
    controller.service_item = song() if name else None
    if name:
        controller.service_item.name = name
    _, mime = theme_drag
    enter = QtGui.QDragEnterEvent(
        QtCore.QPoint(30, 30), QtCore.Qt.DropAction.CopyAction, mime,
        QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    controller.eventFilter(controller.panel, enter)
    assert not enter.isAccepted() and not controller._drop_hint.isVisible()
    assert not controller.drop_item(mime)
    controller.service_manager.apply_theme_to_item.assert_not_called()


def test_service_batch_drag_captures_items_and_rejects_controller_drop():
    items = [song('First'), song('Second')]
    mime = ItemDragData(items=items)
    items.clear()
    assert [item.title for item in mime.service_items()] == ['First', 'Second']
    assert mime.can_drop('service')
    assert not mime.can_drop('preview')
    assert not mime.can_drop('live')
    mime.items[1].is_valid = False
    assert not mime.can_drop('service')


@pytest.mark.parametrize('dark', [False, True])
def test_drag_card_uses_shared_theme_and_font_despite_source_styling(library, dark):
    import fluentqt
    previous = fluentqt.current_theme()
    fluentqt.set_theme(fluentqt.Theme.Dark if dark else fluentqt.Theme.Light)
    try:
        mime = ItemDragData(library=library)
        mime.title = 'A very long label ' * 20
        with patch('openlp.core.widgets.dnd.QtGui.QDrag') as drag:
            execute_drag(library.list_view, mime)
            first = drag.return_value.setPixmap.call_args.args[0].toImage()
            font = library.list_view.font()
            font.setPointSize(28)
            library.list_view.setFont(font)
            palette = library.list_view.palette()
            palette.setColor(QtGui.QPalette.ColorRole.Base, QtCore.Qt.GlobalColor.red)
            library.list_view.setPalette(palette)
            execute_drag(library.list_view, mime)
            second = drag.return_value.setPixmap.call_args.args[0].toImage()
        assert first == second
        host = fluentqt.FluentWidget()
        assert first.pixelColor(4, 28) == host.theme_tokens().colors.bgSolid
        host.deleteLater()
    finally:
        fluentqt.set_theme(previous)
