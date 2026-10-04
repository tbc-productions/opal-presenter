"""Status messages and progress share the padded footer without overlapping."""
from PySide6 import QtCore, QtGui, QtWidgets
from fluentqt.design import Spacing

from openlp.core.widgets.fluent import QProgressBar
from openlp.core.widgets.statusbar import FooterStatusBar


def test_footer_message_and_progress_layout(qapp, qtbot):
    window = QtWidgets.QMainWindow()
    qtbot.addWidget(window)
    footer = FooterStatusBar(window)
    window.setStatusBar(footer)
    progress = QProgressBar(footer)
    footer.add_left_widget(progress, 1)
    theme = QtWidgets.QLabel('Default Theme: Default', footer)
    footer.add_right_widget(theme)
    usage = QtWidgets.QToolButton(footer)
    usage.setText('Tracking')
    footer.add_right_widget(usage, before=True)
    footer.showMessage('Loading Sunday service')
    progress.setValue(100)
    window.show()
    for width in (700, 1200):
        window.resize(width, 150)
        QtWidgets.QApplication.processEvents()
        label = footer.message_label
        assert label.mapTo(footer, QtCore.QPoint()).x() >= Spacing.Large
        assert label.geometry().right() < progress.x()
        assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
        assert progress.mapTo(footer, progress.rect().topRight()).x() < usage.mapTo(footer, QtCore.QPoint()).x()
        assert usage.geometry().right() < theme.x()
        assert theme.mapTo(footer, theme.rect().topRight()).x() < footer.width() - Spacing.Large
        right_positions = (usage.mapTo(footer, QtCore.QPoint()).x(), theme.mapTo(footer, QtCore.QPoint()).x())
        for message, show_progress in (('Ready', False), ('', False), ('Loading Sunday service', True)):
            footer.showMessage(message)
            progress.setVisible(show_progress)
            QtWidgets.QApplication.processEvents()
            assert right_positions == (usage.mapTo(footer, QtCore.QPoint()).x(),
                                       theme.mapTo(footer, QtCore.QPoint()).x())
            if message:
                assert label.mapTo(footer, QtCore.QPoint()).x() >= Spacing.Large
                assert label.mapTo(footer, QtCore.QPoint()).x() < 40
        usage.hide()
        QtWidgets.QApplication.processEvents()
        qtbot.waitUntil(lambda: theme.mapTo(footer, QtCore.QPoint()).x() == right_positions[1])
        usage.show()
        QtWidgets.QApplication.processEvents()
        QtWidgets.QApplication.processEvents()
    footer.showMessage('A very long loading message ' * 40)
    QtWidgets.QApplication.processEvents()
    assert footer.message_label.width() <= footer.contentsRect().width() // 3
    assert footer.message_label.geometry().right() < progress.x()


def test_footer_message_timeout_and_clear(qapp, qtbot):
    footer = FooterStatusBar()
    qtbot.addWidget(footer)
    with qtbot.waitSignal(footer.messageChanged) as changed:
        footer.showMessage('Loading', 50)
    assert changed.args == ['Loading']
    assert footer.currentMessage() == 'Loading'
    qtbot.waitUntil(lambda: footer.currentMessage() == '')
    assert footer.message_label.isHidden()
    footer.showMessage('Ready')
    footer.clearMessage()
    assert footer.currentMessage() == ''


def test_footer_routes_status_tips_into_left_message_label(qapp, qtbot):
    window = QtWidgets.QMainWindow()
    qtbot.addWidget(window)
    footer = FooterStatusBar(window)
    window.setStatusBar(footer)
    QtWidgets.QApplication.sendEvent(window, QtGui.QStatusTipEvent('Toggle song usage tracking'))
    assert footer.currentMessage() == 'Toggle song usage tracking'
    assert footer.message_label.text() == 'Toggle song usage tracking'
    assert QtWidgets.QStatusBar.currentMessage(footer) == ''
    QtWidgets.QApplication.sendEvent(window, QtGui.QStatusTipEvent(''))
    assert footer.message_label.isHidden()
