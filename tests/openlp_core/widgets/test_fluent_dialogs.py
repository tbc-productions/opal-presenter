"""Native dialog presentation retains application modal contracts."""
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
import fluentqt
from openlp.core.widgets import fluent


def test_preconstructed_application_forms_stay_hidden_on_startup(qapp, registry, mock_settings):
    from openlp.core.ui.aboutform import AboutForm
    from openlp.core.ui.settingsform import SettingsForm
    parent = QtWidgets.QMainWindow()
    parent.resize(1200, 900)
    forms = [AboutForm(parent), SettingsForm(parent)]
    parent.show()
    QtWidgets.QApplication.processEvents()
    assert all(form.isHidden() and not form.isVisible() for form in forms)
    assert all(form.isSmokeEnabled() for form in forms)
    parent.close()


def test_settings_exec_uses_parent_window_for_smoke(qapp, registry, mock_settings, monkeypatch):
    from openlp.core.ui.settingsform import SettingsForm
    parent = QtWidgets.QMainWindow()
    parent.resize(1200, 900)
    settings = SettingsForm(parent)
    monkeypatch.setattr(settings, '_get_ordered_tabs', lambda: [])
    parent.show()
    QtWidgets.QApplication.processEvents()
    assert not settings.isVisible()

    observed = []

    def dismiss():
        observed.append((settings.parentWidget() is parent, settings.isWindow(),
                         settings.isOpen(), settings.isSmokeEnabled(), settings.isDim()))
        settings.reject()

    QtCore.QTimer.singleShot(0, dismiss)
    assert settings.exec() == QtWidgets.QDialog.DialogCode.Rejected
    assert observed == [(True, False, True, True, True)]
    parent.close()


@pytest.mark.parametrize('factory', [fluent.QDialog, fluent.QProgressDialog, fluent.QMessageBox])
@pytest.mark.parametrize('opening_method', ['show', 'open'])
def test_startup_dialogs_stay_hidden_when_parent_is_shown(qapp, factory, opening_method):
    parent = QtWidgets.QWidget()
    parent.resize(900, 600)
    dialog = factory(parent)
    parent.show()
    QtWidgets.QApplication.processEvents()
    assert dialog.isHidden()
    assert not dialog.isVisible()
    assert not dialog.isOpen()
    parent.hide()
    parent.show()
    QtWidgets.QApplication.processEvents()
    assert not dialog.isVisible()
    getattr(dialog, opening_method)()
    QtWidgets.QApplication.processEvents()
    assert dialog.isVisible()
    if opening_method == 'open':
        assert dialog.isOpen()
    dialog.done(0)
    parent.close()


def test_dialog_parent_and_legacy_flags_keep_native_surface(qapp):
    parent = QtWidgets.QWidget()
    parent.resize(800, 600)
    parent.show()
    dialog = fluent.QDialog(parent, QtCore.Qt.WindowType.WindowTitleHint)
    assert isinstance(dialog, fluentqt.Dialog)
    assert dialog.parentWidget() is parent
    assert dialog.isSmokeEnabled()
    assert dialog.isAnimationEnabled()
    assert not dialog.graphicsEffect().isEnabled()
    assert not dialog.isWindow()
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(fluent.QLineEdit(dialog))
    finished = []
    dialog.finished.connect(finished.append)
    QtCore.QTimer.singleShot(0, dialog.accept)
    assert dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
    assert finished == [QtWidgets.QDialog.DialogCode.Accepted]
    parent.close()


def test_message_and_progress_use_native_dialogs(qapp):
    parent = QtWidgets.QWidget()
    parent.resize(800, 600)
    parent.show()
    message = fluent.QMessageBox(fluent.QMessageBox.Icon.Warning, 'Warning', 'Choose',
                                 fluent.QMessageBox.StandardButton.Cancel, parent)
    assert isinstance(message, fluentqt.Dialog)
    assert message.parentWidget() is parent
    assert message.isSmokeEnabled()
    progress = fluent.QProgressDialog(parent)
    assert isinstance(progress, fluentqt.Dialog)
    assert progress.isSmokeEnabled()
    QtCore.QTimer.singleShot(0, message.button(message.StandardButton.Cancel).click)
    assert message.exec() == message.StandardButton.Cancel
    assert message._text.text() == 'Choose'
    assert message.title() == 'Warning'
    parent.close()


@pytest.mark.parametrize('kind,accepted', [('text', True), ('int', True), ('item', True), ('text', False)])
def test_input_prompts_return_values_before_content_destruction(qapp, kind, accepted):
    def finish():
        dialogs = [widget for widget in QtWidgets.QApplication.allWidgets()
                   if isinstance(widget, fluent.QDialog) and widget.isVisible()]
        assert len(dialogs) == 1
        dialog = dialogs[0]
        if kind == 'text':
            dialog.findChild(fluent.QLineEdit).setText('Updated')
        elif kind == 'int':
            dialog.findChild(fluent.QSpinBox).setValue(12)
        else:
            dialog.findChild(fluent.QComboBox).setCurrentIndex(1)
        dialog.accept() if accepted else dialog.reject()

    QtCore.QTimer.singleShot(0, finish)
    if kind == 'text':
        value, ok = fluent.QInputDialog.getText(None, 'Rename', 'Title:', text='Original')
        assert value == ('Updated' if accepted else '')
    elif kind == 'int':
        value, ok = fluent.QInputDialog.getInt(None, 'Delay', 'Seconds:', 5, 0, 180, 1)
        assert value == 12
    else:
        value, ok = fluent.QInputDialog.getItem(None, 'Type', 'Choose:', ['First', 'Second'], editable=False)
        assert value == 'Second'
    assert ok is accepted


@pytest.mark.parametrize('parented', [False, True])
def test_single_button_message_escape_keeps_standard_result(qapp, parented):
    from PySide6 import QtTest
    parent = QtWidgets.QWidget() if parented else None
    if parent is not None:
        parent.show()
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Information, 'Title', 'Message',
                             fluent.QMessageBox.StandardButton.Ok, parent)
    QtCore.QTimer.singleShot(0, lambda: QtTest.QTest.keyClick(box, QtCore.Qt.Key.Key_Escape))
    assert box.exec() == box.StandardButton.Ok
    assert box.clickedButton() is box.button(box.StandardButton.Ok)
    if parent is not None:
        parent.close()


def test_message_content_prepared_with_hidden_parent(qapp):
    parent = QtWidgets.QWidget()
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Warning, 'Title', 'Message',
                             fluent.QMessageBox.StandardButton.Cancel, parent)
    QtCore.QTimer.singleShot(0, box.button(box.StandardButton.Cancel).click)
    assert box.exec() == box.StandardButton.Cancel
    assert box.title() == 'Title'
    assert box._text.text() == 'Message'


def test_wrapped_message_fits_native_surface(qapp):
    parent = QtWidgets.QWidget()
    parent.resize(900, 600)
    parent.show()
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Question, 'Delete item from service',
                             'Are you sure you want to delete this item from the service?',
                             fluent.QMessageBox.StandardButton.Yes | fluent.QMessageBox.StandardButton.No, parent)
    box.setAnimationEnabled(False)
    box.show()
    QtWidgets.QApplication.processEvents()
    assert box._text.height() >= box._text.heightForWidth(box._text.width())
    box.done(0)
    parent.close()


@pytest.mark.parametrize('target', [QtCore.QPoint(-300, -300), QtCore.QPoint(1200, 900)])
def test_dialog_drag_cannot_clip_surface(qapp, target):
    parent = QtWidgets.QWidget()
    parent.resize(900, 600)
    parent.show()
    dialog = fluent.QDialog(parent)
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(fluent.QLabel('Dialog content', dialog))
    dialog.setAnimationEnabled(False)
    dialog.open()
    press_position = QtCore.QPoint(20, 20)
    press = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, QtCore.QPointF(press_position),
                              QtCore.QPointF(dialog.mapToGlobal(press_position)), QtCore.Qt.MouseButton.LeftButton,
                              QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(dialog, press)
    move = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(target),
                             QtCore.QPointF(parent.mapToGlobal(target)), QtCore.Qt.MouseButton.NoButton,
                             QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(dialog, move)
    assert parent.rect().contains(dialog.geometry())
    dialog.done(0)
    parent.close()


def test_dialog_stays_inside_resized_parent(qapp):
    parent = QtWidgets.QWidget()
    parent.resize(900, 600)
    parent.show()
    dialog = fluent.QDialog(parent)
    dialog.setMinimumSize(600, 400)
    dialog.setAnimationEnabled(False)
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(fluent.QLabel('Dialog content', dialog))
    dialog.open()
    parent.resize(450, 300)
    QtWidgets.QApplication.processEvents()
    assert parent.rect().contains(dialog.geometry())
    parent.resize(900, 600)
    QtWidgets.QApplication.processEvents()
    assert dialog.size().width() >= 600
    assert dialog.size().height() >= 400
    dialog.done(0)
    parent.close()


@pytest.mark.parametrize('module_name, ui_name', [
    ('openlp.plugins.songs.forms.authorsdialog', 'Ui_AuthorsDialog'),
    ('openlp.plugins.songs.forms.topicsdialog', 'Ui_TopicsDialog'),
    ('openlp.plugins.songs.forms.songbookdialog', 'Ui_SongBookDialog'),
    ('openlp.core.ui.filerenamedialog', 'Ui_FileRenameDialog'),
    ('openlp.core.ui.firsttimelanguagedialog', 'Ui_FirstTimeLanguageDialog'),
    ('openlp.core.ui.starttimedialog', 'Ui_StartTimeDialog'),
])
def test_compact_dialogs_fit_fields_and_labels(qapp, registry, mock_settings, module_name, ui_name):
    """Old height caps must not compress fields after Fluent padding is applied."""
    from importlib import import_module
    ui = getattr(import_module(module_name), ui_name)
    dialog_type = type('CompactDialog', (fluent.FormDialog, ui), {})
    parent = QtWidgets.QWidget()
    parent.resize(1000, 800)
    parent.show()
    dialog = dialog_type(parent)
    dialog.setup_ui(dialog)
    dialog.setAnimationEnabled(False)
    dialog.open()
    QtWidgets.QApplication.processEvents()
    try:
        assert dialog.width() >= 420
        assert dialog.height() >= dialog.sizeHint().height()
        assert parent.rect().contains(dialog.geometry())
        fields = dialog.findChildren(fluentqt.LineEdit) + dialog.findChildren(fluentqt.ComboBox)
        fields += dialog.findChildren(QtWidgets.QAbstractSpinBox)
        assert fields
        for field in fields:
            assert field.height() >= 32
            if isinstance(field, fluentqt.LineEdit):
                assert field.width() >= 160
        for label in dialog.findChildren(fluentqt.Label):
            if label.isVisible():
                assert label.height() >= label.sizeHint().height()
        for form in dialog.findChildren(QtWidgets.QFormLayout):
            assert form.horizontalSpacing() >= 12
            assert form.verticalSpacing() >= 12
    finally:
        dialog.done(0)
        parent.close()


@pytest.mark.parametrize('choice', ['Save', 'Cancel', 'Discard'])
def test_content_message_visible_actions_keep_qt_results(qapp, choice):
    parent = QtWidgets.QWidget()
    parent.resize(1000, 700)
    parent.show()
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Question, 'Modified Service', 'Save the changes?',
                             fluent.QMessageBox.StandardButton.Save | fluent.QMessageBox.StandardButton.Discard |
                             fluent.QMessageBox.StandardButton.Cancel, parent)
    box.setAnimationEnabled(False)
    box.setDefaultButton(box.StandardButton.Save)
    assert isinstance(box, fluentqt.ContentDialog)
    finished = []
    clicked = []
    box.finished.connect(finished.append)
    box.buttonClicked.connect(clicked.append)

    def choose():
        assert box.title() == 'Modified Service'
        assert all(button.isHidden() for button in box.buttons())
        visible = [button for button in box.findChildren(fluentqt.Button)
                   if button.isVisible() and button.text() == box.button(expected).text()]
        assert len(visible) == 1
        visible[0].click()

    QtCore.QTimer.singleShot(0, choose)
    expected = {'Save': box.StandardButton.Save, 'Cancel': box.StandardButton.Cancel,
                'Discard': box.StandardButton.Discard}[choice]
    try:
        assert box.exec() == expected
        assert box.result() == expected
        assert finished == [expected]
        assert clicked == [box.button(expected)]
    finally:
        parent.close()


@pytest.mark.parametrize('icon', [
    fluent.QMessageBox.Icon.Information, fluent.QMessageBox.Icon.Warning,
    fluent.QMessageBox.Icon.Critical, fluent.QMessageBox.Icon.Question,
])
def test_single_action_content_message_keeps_text_without_icon(qapp, icon):
    parent = QtWidgets.QWidget()
    parent.resize(1000, 700)
    parent.show()
    box = fluent.QMessageBox(icon, 'Delete Author',
                             'This author cannot be deleted, they are currently assigned to at least one song.',
                             fluent.QMessageBox.StandardButton.Ok, parent)
    box.setInformativeText('A Thousand Hallelujahs')
    box.setAnimationEnabled(False)
    assert isinstance(box, fluentqt.ContentDialog)
    assert '_icon_label' not in box.__dict__

    def dismiss():
        assert box.title() == 'Delete Author'
        assert box._info.text() == 'A Thousand Hallelujahs'
        for label in (box._text, box._info):
            assert label.isVisible()
            assert label.height() >= label.heightForWidth(label.width())
        box._native_commands['primary'].click()

    QtCore.QTimer.singleShot(0, dismiss)
    try:
        assert box.exec() == box.StandardButton.Ok
        assert box.clickedButton() is box.button(box.StandardButton.Ok)
    finally:
        parent.close()


def test_long_content_message_has_bounded_width_and_wrapped_text(qapp):
    parent = QtWidgets.QWidget()
    parent.resize(1800, 1000)
    parent.show()
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Question, 'Re-run First Time Wizard?',
                             'Are you sure you want to re-run the First Time Wizard?',
                             fluent.QMessageBox.StandardButton.Yes | fluent.QMessageBox.StandardButton.No, parent)
    box.setInformativeText(
        'Re-running this wizard may make changes to your current Opal Presenter configuration and possibly '
        'add songs to your existing songs list and change your default theme.')
    box.setDefaultButton(box.StandardButton.No)
    box.setAnimationEnabled(False)
    box.open()
    QtWidgets.QApplication.processEvents()
    try:
        assert box.width() <= 560
        for label in (box._text, box._info):
            assert label.height() >= label.heightForWidth(label.width())
        assert parent.rect().contains(box.geometry())
        for button in box._native_commands.values():
            if button.isVisible():
                assert button.width() <= 240
    finally:
        box.done(0)
        parent.close()


@pytest.mark.parametrize('default', ['Save', 'Discard', 'Cancel'])
def test_message_command_positions_do_not_follow_default_action(qapp, default):
    buttons = fluent.QMessageBox.StandardButton
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Question, 'Save changes?', 'Choose an action',
                             buttons.Save | buttons.Discard | buttons.Cancel)
    box.setDefaultButton(getattr(buttons, default))
    box._sync_content()
    assert {slot: box.standardButton(button) for slot, button in box._content_commands.items()} == {
        'primary': buttons.Save, 'secondary': buttons.Discard, 'close': buttons.Cancel}
    assert box.defaultButton() is box.button(getattr(buttons, default))
    box.deleteLater()


def test_long_message_scrolls_without_hiding_commands(qapp, qtbot):
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.resize(1000, 700)
    parent.show()
    text = '\n'.join(('/missing/' + 'long-folder-name/' * 7 + 'presentation-number-{0}.pptx').format(index)
                     for index in range(25))
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Warning, 'Missing files', text,
                             fluent.QMessageBox.StandardButton.Ok, parent)
    box.setAnimationEnabled(False)
    box.open()
    QtWidgets.QApplication.processEvents()
    assert parent.rect().contains(box.geometry())
    assert box._content_scroll.verticalScrollBar().maximum() > 0
    button = box._native_commands['primary']
    assert box.rect().contains(QtCore.QRect(button.mapTo(box, QtCore.QPoint()), button.size()))
    parent.resize(800, 500)
    QtWidgets.QApplication.processEvents()
    assert parent.rect().contains(box.geometry())
    assert box.rect().contains(QtCore.QRect(button.mapTo(box, QtCore.QPoint()), button.size()))
    assert box._content_scroll.viewport().height() > 0
    box.done(0)


@pytest.mark.parametrize('host_size', [(1000, 700), (420, 320)])
def test_short_confirmation_fits_after_native_layout_settles(qapp, qtbot, host_size):
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.resize(*host_size)
    parent.show()
    buttons = fluent.QMessageBox.StandardButton
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Warning, 'Reset layout presets?',
                             'This will revert customisations for all layout presets.',
                             buttons.Reset | buttons.Cancel, parent)
    box.setDefaultButton(buttons.Cancel)
    box.open()
    qtbot.waitUntil(lambda: box._content_scroll.verticalScrollBar().maximum() == 0)
    assert box._text.height() >= box._text.heightForWidth(box._text.width())
    assert parent.rect().contains(box.geometry())
    assert [box._native_commands[slot].text() for slot in ('primary', 'close')] == ['Reset', 'Cancel']
    qtbot.keyClick(box, QtCore.Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: box.result() == buttons.Cancel)


def test_short_message_recovers_after_a_scrollbar_causes_extra_wrapping(qapp, qtbot):
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.resize(1000, 700)
    parent.setFont(fluentqt.font_for_role(fluentqt.FontRole.Body))
    parent.show()
    buttons = fluent.QMessageBox.StandardButton
    box = fluent.QMessageBox(fluent.QMessageBox.Icon.Warning, 'Reset layout presets?',
                             'This will revert customisations for all layout presets.\n\nDo you want to continue?',
                             buttons.Yes | buttons.No, parent)
    box.setAnimationEnabled(False)
    box.open()
    QtWidgets.QApplication.processEvents()
    box.resize(box.width(), box.height() - 20)
    QtWidgets.QApplication.processEvents()
    assert box._content_scroll.verticalScrollBar().maximum() > 0
    box._prepare_size()
    QtWidgets.QApplication.processEvents()
    assert box._content_scroll.verticalScrollBar().maximum() == 0
    assert box._text.height() >= box._text.heightForWidth(box._text.width())
    box.done(0)


def test_content_dialog_preserves_padding_typography_and_content_ownership(qapp):
    dialog = fluent.ContentDialog()
    native = fluentqt.ContentDialog()
    assert dialog.layout().contentsMargins() == native.layout().contentsMargins()
    label = fluent.QLabel('A body paragraph')
    dialog.setContent(label)
    assert label.fluentTypography() == fluentqt.FontRole.Body
    assert not label.autoFillBackground()
    replacement = fluent.QLineEdit()
    dialog.setContent(replacement)
    assert label.parentWidget() is None
    assert label.text() == 'A body paragraph'
    assert dialog.takeContent() is replacement
    assert replacement.parentWidget() is None
    assert dialog.content() is None
    dialog.deleteLater()
    native.deleteLater()
    label.deleteLater()
    replacement.deleteLater()


def test_plain_horizontal_dialog_puts_heading_above_content(qapp, qtbot):
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.resize(900, 600)
    parent.show()
    dialog = fluent.QDialog(parent)
    dialog.setWindowTitle('About Opal Presenter')
    layout = QtWidgets.QHBoxLayout(dialog)
    body = fluent.QLabel('About text')
    layout.addWidget(body)
    dialog.setAnimationEnabled(False)
    dialog.open()
    assert dialog._heading.text() == 'About Opal Presenter'
    assert dialog._heading.mapTo(dialog, QtCore.QPoint()).y() < body.mapTo(dialog, QtCore.QPoint()).y()
    dialog.setWindowTitle('Updated title')
    assert dialog._heading.text() == 'Updated title'
    dialog.done(0)


def test_folder_form_has_room_for_both_rows_and_primary_action(qapp, registry, mock_settings, qtbot):
    from openlp.core.ui.folders import AddFolderForm
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.resize(1000, 800)
    parent.show()
    dialog = AddFolderForm(parent)
    dialog.setAnimationEnabled(False)
    dialog.open()
    assert dialog.title() == 'Add folder'
    assert dialog._native_commands['primary'].text() == 'Create'
    for label, field in ((dialog.parent_folder_label, dialog.folder_combobox), (dialog.name_label, dialog.name_edit)):
        assert label.height() >= label.sizeHint().height()
        assert field.height() >= 32
    assert dialog.parent_folder_label.geometry().bottom() < dialog.name_label.geometry().top()
    dialog.done(0)


def test_planning_center_keeps_import_before_refresh(qapp, registry, mock_settings):
    from openlp.plugins.planningcenter.forms.selectplandialog import Ui_SelectPlanDialog
    dialog = type('PlanningDialog', (fluent.FormDialog, Ui_SelectPlanDialog), {})()
    dialog.setup_ui(dialog)
    dialog.setAnimationEnabled(False)
    dialog.open()
    QtWidgets.QApplication.processEvents()
    for button in dialog._native_commands.values():
        assert button.width() >= button.sizeHint().width()
    assert dialog.service_type_combo_box.width() >= 200
    assert dialog._content_commands['primary'] is dialog.import_as_new_button
    assert dialog._content_commands['secondary'] is dialog.update_existing_button
    dialog.import_as_new_button.setEnabled(False)
    assert not dialog._native_commands['primary'].isEnabled()
    dialog.import_as_new_button.setEnabled(True)
    assert dialog._native_commands['primary'].isEnabled()
    dialog.done(0)
    dialog.deleteLater()


@pytest.mark.parametrize('accept', [True, False])
def test_colour_prompt_keeps_colour_and_cancel_contract(qapp, monkeypatch, accept):
    def choose(dialog):
        picker = dialog.content()
        assert isinstance(dialog, fluent.ContentDialog)
        assert picker.alphaEnabled()
        picker.setColor(QtGui.QColor('#80402010'))
        return dialog.ResultPrimary if accept else dialog.ResultNone

    monkeypatch.setattr(fluent.ContentDialog, 'exec', choose)
    colour = fluent.QColorDialog.getColor(
        QtGui.QColor('red'), options=fluent.QColorDialog.ColorDialogOption.ShowAlphaChannel)
    assert colour.isValid() is accept
    if accept:
        assert colour.name(QtGui.QColor.NameFormat.HexArgb) == '#80402010'
