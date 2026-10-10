"""Integrated editing keeps the existing metadata, validation and fallback contracts."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore

from openlp.core.common.registry import Registry
from openlp.core.widgets import fluent as QtWidgets
from openlp.plugins.songs.forms.editsongform import EditSongForm
from openlp.plugins.custom.forms.editcustomform import EditCustomForm
from openlp.plugins.slide_designer.forms.itemeditor import SongItemDesigner, CustomItemDesigner


@pytest.fixture(autouse=True)
def section_settings(settings):
    from openlp.plugins.songs.lib.sectioncolors import DEFAULT_SECTION_COLORS
    settings.extend_default_settings({'songs/section color ' + key: colour
                                      for key, colour in DEFAULT_SECTION_COLORS.items()})
    settings.extend_default_settings({'songs/section background opacity minimum': 10,
                                      'songs/section background opacity maximum': 60})


@pytest.fixture(params=['song', 'custom'])
def integrated(settings, request):
    Registry().register('theme_manager', MagicMock())
    song = request.param == 'song'
    owner = (EditSongForm if song else EditCustomForm)(MagicMock(), None, MagicMock())
    owner.title_edit.setText('Draft title')
    owner.theme_combo_box.clear()
    owner.theme_combo_box.addItems(['', 'Ocean'])
    owner.theme_combo_box.setCurrentText('Ocean')
    owner.slide_design = {'version': 1, 'canvas_width': 1920, 'canvas_height': 1080,
                          'background': {'type': 'solid', 'colour': '#123456'}}
    if song:
        owner.set_verse_text('---[Verse:1]---\nFirst\n[--}{--]\nSecond\n---[Chorus:1]---\nChorus')
        owner.alternative_edit.setText('Alternative')
        owner.verse_order_edit.setText('V1 C1 V1')
    else:
        owner.slide_list_view.addItems(['First', 'Second'])
        owner.credit_edit.setText('Credit')
    editor = (SongItemDesigner if song else CustomItemDesigner)(owner)
    yield owner, editor
    editor.restore_controls()
    editor.slide_designer.refresh_timer.stop()
    editor.deleteLater()
    owner.deleteLater()


def test_integrated_controls_and_metadata_navigation(integrated):
    owner, editor = integrated
    assert editor.slide_designer.tools.layout().itemAt(0).widget() is owner.title_edit
    footer = editor.slide_designer.preview_footer
    assert editor.theme_combo_box.parentWidget() is footer.theme_group
    assert editor.slide_designer.canvas_combo.parentWidget() is footer.preview_group
    wide_height = footer.reflow(700)
    narrow_height = footer.reflow(300)
    assert narrow_height > wide_height
    assert footer.layout().getItemPosition(footer.layout().indexOf(footer.preview_group))[0] == 1
    footer.reflow(700)
    assert footer.layout().getItemPosition(footer.layout().indexOf(footer.preview_group))[0] == 0
    assert not editor.slide_designer.inspector_button.isChecked()
    if editor.design_kind == 'song':
        assert editor.alternative_field is owner.alternative_edit
        assert len(editor.slide_grid.rows) == 3
        assert 'V1 C1 V1' == owner.verse_order_edit.text()
        assert owner.verse_order_edit.parentWidget() is editor.editor_splitter.widget(0)
        editor.select_page(2)
        assert owner.song_tab_widget.currentIndex() == 2
        assert editor.navigation.contentHost().currentIndex() == 2
        owner.song_tab_widget.setCurrentIndex(1)
        assert editor.navigation.contentHost().currentIndex() == 1
        assert editor.metadata_pages[0][1].isAncestorOf(owner.authors_list_view)
    else:
        assert hasattr(editor, 'navigation')
        assert not hasattr(editor, 'copyright_warning')
        assert editor.navigation.contentHost().currentIndex() == 0
        assert owner.credit_edit.parentWidget() is editor.editor_splitter.widget(0)


@pytest.mark.parametrize('copyright', ['', ' \n\t ', '© 2026 Songwriter'])
def test_copyright_warning_tracks_initial_and_edited_draft(settings, copyright):
    import fluentqt

    Registry().register('theme_manager', MagicMock())
    owner = EditSongForm(MagicMock(), None, MagicMock())
    owner.copyright_edit.setPlainText(copyright)
    editor = SongItemDesigner(owner)
    try:
        warning = editor.copyright_warning
        button = editor.navigation_buttons[2]
        assert warning.isHidden() == bool(copyright.strip())
        assert button.badge.isHidden() == warning.isHidden()
        assert isinstance(button.badge, fluentqt.InfoBadge)
        assert button.badge.status() == fluentqt.InfoBadge.InfoBadgeStatus.Critical
        assert warning.severity() == fluentqt.InfoBar.InfoBarSeverity.Warning
        assert warning.message() == ''
        assert warning.title() == 'Missing copyright information'
        assert warning.actionWidget() is None
        assert not warning.isClosable()
        layout = editor.editor_splitter.widget(0).layout()
        assert layout.indexOf(warning) < layout.indexOf(editor.text_editor_stack)
        for text in ('© 2026 Songwriter', '', '   ', 'Public domain'):
            owner.copyright_edit.setPlainText(text)
            assert warning.isHidden() == bool(text.strip())
            assert button.badge.isHidden() == warning.isHidden()
            assert bool(button.accessibleDescription()) == (not text.strip())
    finally:
        editor.restore_controls()
        editor.slide_designer.refresh_timer.stop()
        editor.deleteLater()
        owner.deleteLater()


@pytest.mark.parametrize('keyboard', [False, True])
def test_copyright_badge_fits_navigation_and_preserves_activation(integrated, qtbot, keyboard):
    from openlp.plugins.slide_designer.forms.window import DesignerWindow

    owner, editor = integrated
    if editor.design_kind != 'song':
        return
    window = DesignerWindow(editor)
    qtbot.addWidget(window)
    try:
        with patch.object(editor.slide_designer, 'refresh'):
            if keyboard:
                editor.navigation_buttons[2].setAccessibleName('Copyright, Flags & Comments ' * 3)
                editor.toggle_navigation()
            window.show()
            window.activateWindow()
            QtWidgets.QApplication.processEvents()
            button = editor.navigation_buttons[2]
            assert button.rect().contains(button.badge.geometry())
            assert button.badge.testAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            if keyboard:
                assert button.text().endswith('…')
                assert button.contentPaintRect(button.rect()).right() < button.badge.x()
                button.setFocus()
                qtbot.keyClick(button, QtCore.Qt.Key.Key_Space)
            else:
                qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
            assert editor.navigation.contentHost().currentIndex() == 2
            assert owner.song_tab_widget.currentIndex() == 2
            assert editor.navigation_buttons[2].isChecked()
    finally:
        editor.setLayout(window.host.layout())


def test_save_flushes_inline_lyrics_before_syncing_owner(integrated):
    owner, editor = integrated
    designer = editor.slide_designer
    editor.designer_select_section(0)
    designer.display = MagicMock(_is_initialised=True)
    designer.pages = ['First']
    designer.page_keys = [(0, 0)]
    designer.prepare_canvas_text()
    designer.canvas_text_editing(True)
    designer.display.run_in_display.return_value = {'id': 'lyrics', 'before': 'First', 'text': 'Canvas edit'}
    with patch.object(owner, 'accept') as save:
        editor.accept()
        save.assert_called_once()
    assert 'Canvas edit' in editor.design_text_editor.toPlainText()
    if editor.design_kind == 'song':
        assert owner.verse_list_widget.item(0, 0).text() == 'Canvas edit\n[--}{--]\nSecond'
    else:
        assert owner.slide_list_view.item(0).text() == 'Canvas edit'
        assert owner.slide_list_view.item(1).text() == 'Second'


def test_save_syncs_content_design_and_theme_before_existing_validation(integrated):
    owner, editor = integrated
    editor.slide_grid.source_action.trigger()
    editor.theme_combo_box.addItem('Ocean', 'Ocean')
    editor.slide_designer.load_design(owner.slide_design)
    editor.title_field.setText('Edited title')
    editor.design_text_editor.selectAll()
    editor.design_text_editor.insertPlainText('---[Verse:2]---\nEdited' if editor.design_kind == 'song' else 'Edited')
    finished = MagicMock()
    editor.finished.connect(finished)
    with patch.object(owner, 'accept') as accept:
        editor.accept()
        accept.assert_called_once()
    finished.assert_not_called()  # Failed validation must leave the workspace open.
    assert owner.slide_design['background']['colour'] == '#123456'
    assert owner.theme_combo_box.currentText() == 'Ocean'
    if editor.design_kind == 'song':
        assert owner.verse_list_widget.item(0, 0).text() == 'Edited'
        assert owner.verse_list_widget.item(0, 0).data(QtCore.Qt.ItemDataRole.UserRole) == 'v2'
    else:
        assert owner.slide_list_view.item(0).text() == 'Edited'
    owner.accepted.emit()
    finished.assert_called_once_with(QtWidgets.QDialog.DialogCode.Accepted)


def test_dirty_state_compares_content_metadata_design_and_undo(integrated):
    owner, editor = integrated
    editor.mark_saved()
    assert not editor.has_unsaved_changes()
    title = owner.title_edit.text()
    owner.title_edit.setText('Changed')
    assert editor.has_unsaved_changes()
    owner.title_edit.setText(title)
    assert not editor.has_unsaved_changes()
    editor.slide_designer.set_footer_visible(False)
    assert editor.has_unsaved_changes()
    editor.slide_designer.undo_stack.undo()
    assert not editor.has_unsaved_changes()
    editor.slide_designer.canvas_combo.setCurrentIndex(2)
    assert not editor.has_unsaved_changes()  # Theme preview aspect ratio is view state.
    if editor.design_kind == 'song':
        owner.comments_edit.setPlainText('Notes')
        assert editor.has_unsaved_changes()
        owner.comments_edit.clear()
        editor.mark_saved()
        item = QtWidgets.QListWidgetItem('An author')
        item.setData(QtCore.Qt.ItemDataRole.UserRole, [4, 'words'])
        owner.authors_list_view.addItem(item)
        assert editor.has_unsaved_changes()
    else:
        owner.credit_edit.setText('Changed credits')
        assert editor.has_unsaved_changes()


@pytest.mark.parametrize('choice,save_succeeds', [
    ('unchanged', True), ('cancel', True), ('discard', True), ('save', True), ('save', False)])
def test_exit_prompt_respects_save_discard_cancel_and_validation(integrated, qtbot, choice, save_succeeds):
    import fluentqt
    from openlp.plugins.slide_designer.forms.window import DesignerWindow
    owner, editor = integrated
    window = DesignerWindow(editor)
    qtbot.addWidget(window)
    if choice != 'unchanged':
        owner.title_edit.setText('Unsaved item')
    prompts = []

    def inspect(dialog):
        prompts.append(dialog)
        assert dialog.parentWidget() is window
        assert dialog.title() == ('Save Song?' if editor.design_kind == 'song' else 'Save Custom Slides?')
        assert dialog.primaryButtonText() == 'Save'
        assert dialog.secondaryButtonText() == 'Discard'
        assert dialog.closeButtonText() == 'Cancel'
        return {'save': dialog.ResultPrimary, 'discard': dialog.ResultSecondary,
                'cancel': dialog.ResultNone}[choice]

    def accept():
        if save_succeeds:
            owner.accepted.emit()

    try:
        with patch.object(fluentqt.ContentDialog, 'exec', inspect), \
                patch.object(owner, 'accept', side_effect=accept) as save, patch.object(editor, 'reject') as discard:
            assert window.request_close_for_exit() == (choice in ('unchanged', 'discard') or
                                                       choice == 'save' and save_succeeds)
            assert len(prompts) == (choice != 'unchanged')
            assert save.call_count == (choice == 'save')
            assert discard.call_count == (choice in ('unchanged', 'discard'))
    finally:
        editor.setLayout(window.host.layout())


@pytest.mark.parametrize('success', [True, False])
def test_save_and_preview_marks_clean_only_after_success(integrated, success):
    owner, editor = integrated
    editor.mark_saved()
    owner.title_edit.setText('Updated')
    if editor.design_kind == 'song':
        with patch.object(owner, '_validate_song', return_value=success), patch.object(owner, 'on_preview'):
            editor.save_and_preview()
    else:
        with patch.object(owner, 'on_preview_button_clicked', return_value=success):
            editor.save_and_preview()
    assert editor.has_unsaved_changes() == (not success)


@pytest.mark.parametrize('kind', ['song', 'custom'])
def test_cancel_restores_original_editor_widgets_without_saving(settings, kind):
    Registry().register('theme_manager', MagicMock())
    owner = (EditSongForm if kind == 'song' else EditCustomForm)(MagicMock(), None, MagicMock())
    parent = owner.title_edit.parentWidget()
    theme_parent = owner.theme_combo_box.parentWidget()
    layout = owner.authors_tab.layout() if kind == 'song' else None
    with patch('openlp.plugins.slide_designer.forms.window.exec_designer_window', return_value=0), \
            patch.object(owner, 'accept') as save:
        assert owner.exec() == 0
    save.assert_not_called()
    owner.manager.save_object.assert_not_called()
    assert owner.title_edit.parentWidget() is parent
    assert owner.theme_combo_box.parentWidget() is theme_parent
    assert parent.layout().indexOf(owner.title_edit) >= 0 or kind == 'custom'
    if kind == 'song':
        assert owner.authors_tab.layout() is layout
        assert owner.theme_group_box.isHidden() is False
    owner.deleteLater()


def test_existing_save_contract_closes_only_after_success(integrated):
    owner, editor = integrated
    finished = MagicMock()
    editor.finished.connect(finished)
    if editor.design_kind == 'song':
        with patch.object(owner, '_validate_song', return_value=False), patch.object(owner, 'save_song') as save:
            editor.accept()
            save.assert_not_called()
            finished.assert_not_called()
        owner.song = MagicMock()
        with patch.object(owner, '_validate_song', return_value=True), patch.object(owner, 'save_song') as save:
            editor.accept()
            save.assert_called_once()
    else:
        with patch.object(owner, 'save_custom', side_effect=[False, True]) as save:
            editor.accept()
            finished.assert_not_called()
            editor.accept()
            assert save.call_count == 2
    finished.assert_called_once_with(QtWidgets.QDialog.DialogCode.Accepted)


def test_owner_cancellation_closes_the_independent_window(integrated):
    owner, editor = integrated
    with patch.object(editor.slide_designer, 'refresh'):
        QtCore.QTimer.singleShot(0, owner.reject)
        assert editor.exec() == QtWidgets.QDialog.DialogCode.Rejected
    assert owner._designer_open is False
    assert editor.designer_window is None


def test_chord_validation_is_preserved_in_integrated_song_editor(integrated):
    owner, editor = integrated
    if editor.design_kind != 'song':
        return
    editor.select_page(2)
    with patch.object(editor, 'validate_verse', return_value=False), patch.object(owner, 'accept') as save:
        editor.accept()
        save.assert_not_called()
        assert editor.navigation.contentHost().currentIndex() == 0


def test_missing_title_message_is_visible_in_designer_window(integrated):
    """Real validation must present its ContentDialog over this draft, not the main window."""
    from openlp.core.widgets.fluent_dialogs import FluentMessageBox

    owner, editor = integrated
    owner.title_edit.clear()
    main_window = MagicMock()
    Registry().register('main_window', main_window)
    observed = []
    original_exec = FluentMessageBox.exec

    def message_exec(message):
        def dismiss():
            observed.append((message.parentWidget() is editor.designer_window, message.isVisible()))
            message.accept()
        QtCore.QTimer.singleShot(0, dismiss)
        return original_exec(message)

    def save():
        editor.accept()
        editor.reject()

    with patch.object(FluentMessageBox, 'exec', message_exec), patch.object(editor.slide_designer, 'refresh'):
        QtCore.QTimer.singleShot(0, save)
        assert editor.exec() == QtWidgets.QDialog.DialogCode.Rejected
    assert observed == [(True, True)]
    main_window.error_message.assert_not_called()
    owner.manager.save_object.assert_not_called()
    assert not hasattr(owner, '_fluent_dialog_host')
    assert not hasattr(editor, '_fluent_dialog_host')
