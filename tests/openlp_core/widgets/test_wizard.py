"""Fluent wizard pages keep Qt validation and navigation accessible on smaller hosts."""
from PySide6 import QtCore, QtTest
from opal.core.widgets import fluent as QtWidgets


def test_wizard_scrolls_long_content_and_keeps_footer_order(qapp, qtbot):
    wizard = QtWidgets.QWizard()
    qtbot.addWidget(wizard)
    page = QtWidgets.QWizardPage()
    page.setTitle('Configure your presentation workspace')
    page.setSubTitle('Choose your options. You can change them later.')
    layout = QtWidgets.QVBoxLayout(page)
    for _ in range(20):
        label = QtWidgets.QLabel('A long explanation which wraps in a narrow wizard. ' * 4)
        label.setWordWrap(True)
        layout.addWidget(label)
    wizard.addPage(page)
    wizard.setOption(wizard.WizardOption.HaveHelpButton)
    wizard.resize(460, 380)
    wizard.show()
    qtbot.waitUntil(lambda: page.scroll_area.verticalScrollBar().maximum() > 0)
    assert page.title() == 'Configure your presentation workspace'
    assert page.heading.isVisible()
    assert page.description.isVisible()
    finish = wizard.button(wizard.WizardButton.FinishButton)
    help_button = wizard.button(wizard.WizardButton.HelpButton)
    cancel = wizard.button(wizard.WizardButton.CancelButton)
    assert cancel.x() < help_button.x() < finish.x()
    assert finish.isVisible() and cancel.isVisible()
    for role in (wizard.WizardButton.CustomButton1, wizard.WizardButton.CustomButton2,
                 wizard.WizardButton.CustomButton3):
        assert not wizard.button(role).isVisible()
    assert page.scroll_area.width() <= wizard.width()
    assert wizard.height() == 380
    heading_position = page.heading.mapTo(wizard, QtCore.QPoint())
    scrollbar = page.scroll_area.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    assert page.heading.mapTo(wizard, QtCore.QPoint()) == heading_position
    assert page.heading.parentWidget() is page
    wizard.setOption(wizard.WizardOption.HaveHelpButton, False)
    assert not help_button.isVisible()


def test_wizard_enter_respects_validation_and_help_keeps_page_open(qapp, qtbot):
    class RequiredPage(QtWidgets.QWizardPage):
        def validatePage(self):
            return bool(self.field.text().strip())

    wizard = QtWidgets.QWizard()
    qtbot.addWidget(wizard)
    page = RequiredPage()
    page.setTitle('Enter a name')
    layout = QtWidgets.QVBoxLayout(page)
    page.field = QtWidgets.QLineEdit(page)
    layout.addWidget(page.field)
    wizard.addPage(page)
    wizard.addPage(QtWidgets.QWizardPage())
    wizard.setOption(wizard.WizardOption.HaveHelpButton)
    wizard.show()
    next_button = wizard.button(wizard.WizardButton.NextButton)
    next_button.setFocus()
    QtTest.QTest.keyClick(next_button, QtCore.Qt.Key.Key_Return)
    assert wizard.currentId() == 0
    QtTest.QTest.mouseClick(wizard.button(wizard.WizardButton.HelpButton), QtCore.Qt.MouseButton.LeftButton)
    assert wizard.currentId() == 0 and wizard.isVisible()
    page.field.setText('Workspace')
    QtTest.QTest.keyClick(next_button, QtCore.Qt.Key.Key_Return)
    assert wizard.currentId() == 1
    back_button = wizard.button(wizard.WizardButton.BackButton)
    finish_button = wizard.button(wizard.WizardButton.FinishButton)
    cancel_button = wizard.button(wizard.WizardButton.CancelButton)
    assert cancel_button.x() < back_button.x() < finish_button.x()
    QtTest.QTest.keyClick(wizard, QtCore.Qt.Key.Key_Escape)
    assert not wizard.isVisible()


def test_song_import_layouts_own_their_spacers(settings, registry, qtbot):
    """Sharing a spacer across format layouts double-deletes it when the wizard closes."""
    from unittest.mock import MagicMock
    from opal.plugins.songs.forms.songimportform import SongImportForm
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.clipboard = MagicMock()
    registry.register('main_window', parent)
    wizard = SongImportForm(parent, MagicMock())
    qtbot.addWidget(wizard)
    spacers = []
    for layout in wizard.findChildren(QtWidgets.QVBoxLayout):
        spacers.extend(item for index in range(layout.count())
                       if (item := layout.itemAt(index).spacerItem()) is not None)
    assert len(spacers) > 1
    assert len({id(spacer) for spacer in spacers}) == len(spacers)
    wizard.restart()
    wizard.show()
    wizard.next()
    assert wizard.currentPage() is wizard.source_page
    wizard.reject()
