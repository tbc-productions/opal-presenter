"""Font selection supports typing without Qt resetting the editor's Fluent inset."""
from unittest.mock import patch

from PySide6 import QtCore, QtGui, QtTest, QtWidgets

from openlp.core.widgets.fluent_inputs import FluentFontComboBox


def test_font_padding_stays_stable_on_focus_popup_selection_and_resize(qapp, qtbot):
    host = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(host)
    fonts = FluentFontComboBox()
    fonts.setCurrentFont(QtGui.QFont('Arial'))
    layout.addWidget(fonts)
    other = QtWidgets.QLineEdit()
    layout.addWidget(other)
    qtbot.addWidget(host)
    host.resize(400, 160)
    host.show()
    qtbot.waitUntil(lambda: fonts.lineEdit().width() > 0)
    geometry = fonts.lineEdit().geometry()
    assert geometry.left() == fonts._select_chrome.contentPaddingH()
    QtTest.QTest.mouseClick(fonts.lineEdit(), QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: fonts._font_list() is not None)
    assert fonts.lineEdit().hasFocus()
    assert fonts.lineEdit().geometry() == geometry
    fonts.lineEdit().selectAll()
    QtTest.QTest.keyClicks(fonts.lineEdit(), 'Courier New')
    assert fonts.currentFont().family() == 'Arial'
    QtTest.QTest.keyClick(fonts.lineEdit(), QtCore.Qt.Key.Key_Return)
    assert fonts.currentFont().family() == 'Courier New'
    other.setFocus()
    QtWidgets.QApplication.processEvents()
    assert fonts.lineEdit().geometry() == geometry
    host.resize(500, 160)
    QtWidgets.QApplication.processEvents()
    assert fonts.lineEdit().x() == geometry.x()
    assert fonts.lineEdit().width() > geometry.width()


def test_font_typing_highlights_closest_match_without_hiding_options(qapp, qtbot):
    fonts = FluentFontComboBox()
    qtbot.addWidget(fonts)
    fonts.setCurrentFont(QtGui.QFont('Arial'))
    fonts.resize(400, 32)
    fonts.show()
    fonts.showPopup()
    fonts.lineEdit().selectAll()
    QtTest.QTest.keyClicks(fonts.lineEdit(), 'Courier New')
    view = fonts._font_list()
    assert view is not None
    assert view.currentIndex().data() == 'Courier New'
    assert all(not view.isRowHidden(row) for row in range(fonts.count()))
    assert fonts.currentFont().family() == 'Arial'
    QtTest.QTest.keyClick(fonts.lineEdit(), QtCore.Qt.Key.Key_Escape)
    assert fonts.currentText() == 'Arial'
    assert fonts.currentFont().family() == 'Arial'
    fonts.showPopup()
    assert not fonts._font_list().isRowHidden(fonts.findText('Arial'))
    fonts.hidePopup()


def test_dot_prefixed_families_are_hidden_but_saved_font_is_preserved(qapp, qtbot):
    with patch('openlp.core.widgets.fluent_inputs.QtGui.QFontDatabase.families',
               return_value=['.Hidden system font', 'Arial', 'Courier New']):
        fonts = FluentFontComboBox()
    qtbot.addWidget(fonts)
    assert [fonts.itemText(row) for row in range(fonts.count())] == ['Arial', 'Courier New']
    fonts.setCurrentFont(QtGui.QFont('.Hidden system font'))
    assert fonts.currentFont().family() == '.Hidden system font'
    assert fonts.currentText() == '.Hidden system font'
    assert fonts.findText('.Hidden system font') == -1
    fonts._commit_font_name()
    assert fonts.currentFont().family() == '.Hidden system font'


def test_partial_name_and_typo_commit_the_closest_font(qapp, qtbot):
    with patch('openlp.core.widgets.fluent_inputs.QtGui.QFontDatabase.families',
               return_value=['Arial', 'Arial Narrow', 'Courier New', 'Times New Roman']):
        fonts = FluentFontComboBox()
    qtbot.addWidget(fonts)
    for typed, expected in (('Arial', 'Arial'), ('Courier', 'Courier New'), ('Arail', 'Arial'),
                            ('Roman', 'Times New Roman')):
        fonts.setCurrentText(typed)
        fonts._commit_font_name()
        assert fonts.currentFont().family() == expected
        assert fonts.currentText() == expected
    assert fonts.count() == 4
