"""Metadata prioritises item details, wraps safely and shares Fluent styling."""
from fluentqt import FontRole, Label, ScrollBar
from PySide6 import QtCore, QtWidgets as Native
import pytest

from openlp.core.app import OpenLP
from openlp.core.widgets import fluent as QtWidgets
from openlp.core.widgets.metadataview import MetadataView


@pytest.fixture(scope='session')
def native_application():
    return Native.QApplication.instance() or Native.QApplication([])


@pytest.fixture
def qapp(native_application):
    return OpenLP()


def test_metadata_groups_prioritise_content_and_preserve_values(qtbot):
    values = {'Source': 'Google Drive', 'File size': '2 kB', 'Modified': 'Today',
              'Authors': 'Philip Percival, Simone Richardson', 'Copyright': '<b>Organisation</b>',
              'CCLI number': '7006994', 'Created': 'Yesterday', 'Modified by': 'Sam'}
    view = MetadataView(values)
    qtbot.addWidget(view)
    cards = view.findChildren(QtWidgets.Card)
    assert [card.layout().itemAt(0).widget().text() for card in cards] == ['Details', 'File', 'History']
    assert list(view.fields) == ['Authors', 'Copyright', 'CCLI number', 'File size', 'Source',
                                 'Created', 'Modified', 'Modified by']
    for key, value in values.items():
        field = view.fields[key]
        assert field.text() == value
        assert field.textFormat() == QtCore.Qt.TextFormat.PlainText
        assert field.wordWrap()
        assert field.textInteractionFlags() & QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        assert field.accessibleName() == key
    assert view.fields['Authors'].fluentTypography() == FontRole.Body
    caption = cards[0].layout().itemAt(1).widget().layout().itemAt(0).widget()
    assert caption.textColorRole() == Label.TextColorRole.Secondary
    assert not view.widget().autoFillBackground()
    assert not view.viewport().autoFillBackground()


def test_metadata_omits_empty_groups_and_scrolls_long_values(qtbot):
    words = 'A long copyright statement with multiple contributors. ' * 20
    view = MetadataView({'Copyright': words})
    qtbot.addWidget(view)
    view.resize(260, 160)
    view.show()
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)
    assert len(view.findChildren(QtWidgets.Card)) == 1
    assert view.horizontalScrollBar().maximum() == 0
    assert isinstance(view.verticalScrollBar(), ScrollBar)
    assert view.fields['Copyright'].text() == words
    assert view.fields['Copyright'].width() <= view.viewport().width()
