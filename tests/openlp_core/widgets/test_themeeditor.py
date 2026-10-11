"""Canvas interaction uses slide coordinates at any preview size."""
from PySide6 import QtCore
import pytest

from openlp.core.widgets.themeeditor import ThemeAreaOverlay


@pytest.fixture
def overlay(qapp, qtbot):
    widget = ThemeAreaOverlay()
    widget.resize(960, 540)
    widget.set_areas(QtCore.QSize(1920, 1080), {
        'main': QtCore.QRect(100, 100, 600, 300), 'footer': QtCore.QRect(100, 900, 600, 100)})
    widget.show()
    qtbot.addWidget(widget)
    return widget


def test_drag_snaps_to_slide_centre(qapp, qtbot, overlay):
    """A scaled pointer drag snaps the area's centre to the slide centre."""
    changed = []
    overlay.areaChanged.connect(lambda area, rect: changed.append((area, rect)))
    qtbot.mousePress(overlay, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(200, 125))
    qtbot.mouseMove(overlay, QtCore.QPoint(477, 268))
    qtbot.mouseRelease(overlay, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(477, 268))
    assert changed[-1] == ('main', QtCore.QRect(660, 390, 600, 300))
    assert overlay._gesture is None
    assert overlay._snap_lines == []


def test_snap_disabled_retains_free_position(overlay):
    overlay._gesture = ('move', QtCore.QPointF(400, 250), QtCore.QRectF(100, 100, 600, 300))
    assert overlay.gesture_rect(QtCore.QPointF(477, 268), snap=False) == QtCore.QRect(654, 386, 600, 300)


def test_snap_to_other_area_edge(overlay):
    rect = overlay.snap_rect(QtCore.QRectF(107, 450, 600, 300), 'move')
    assert rect.x() == 100
    assert ('x', 100) in overlay._snap_lines


@pytest.mark.parametrize('handle, point, expected', [
    ('se', (400, 250), (100, 100, 700, 400)),
    ('nw', (0, 0), (0, 0, 700, 400)),
    ('e', (2000, 150), (100, 100, 1820, 300)),
    ('s', (300, -100), (100, 100, 600, 1)),
])
def test_resize_preserves_opposite_edges_and_slide_bounds(overlay, handle, point, expected):
    rect = overlay.areas['main']
    start = overlay.slide_point(overlay.handles(overlay.view_rect(rect))[handle])
    overlay._gesture = (handle, start, QtCore.QRectF(rect))
    result = overlay.gesture_rect(QtCore.QPointF(*point), snap=False)
    assert result == QtCore.QRect(*expected)


def test_footer_selection_and_keyboard_nudge(qapp, qtbot, overlay):
    selected = []
    overlay.areaSelected.connect(selected.append)
    qtbot.mouseClick(overlay, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(200, 475))
    assert selected == ['footer']
    qtbot.keyClick(overlay, QtCore.Qt.Key.Key_Right)
    assert overlay.areas['footer'].x() == 101
    qtbot.keyClick(overlay, QtCore.Qt.Key.Key_Down, modifier=QtCore.Qt.KeyboardModifier.ShiftModifier)
    assert overlay.areas['footer'].y() == 910


def test_escape_restores_gesture(qapp, qtbot, overlay):
    qtbot.mousePress(overlay, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(200, 125))
    qtbot.mouseMove(overlay, QtCore.QPoint(477, 268))
    qtbot.keyClick(overlay, QtCore.Qt.Key.Key_Escape)
    assert overlay.areas['main'] == QtCore.QRectF(100, 100, 600, 300)
    assert overlay._gesture is None


def test_click_selects_without_changing_geometry(qapp, qtbot, overlay):
    changed = []
    overlay.areaChanged.connect(lambda area, rect: changed.append(rect))
    qtbot.mouseClick(overlay, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(200, 125))
    assert changed == []
    assert overlay.areas['main'] == QtCore.QRectF(100, 100, 600, 300)
