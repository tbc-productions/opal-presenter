"""Plugin-owned item workspace, reusing the song/custom draft and save contracts."""
from PySide6 import QtCore
import fluentqt

from opal.core.widgets import fluent as QtWidgets
from opal.core.ui.fluenticons import fluent_icon
from opal.core.widgets.fluent_navigation import LayoutPresetButton
from opal.plugins.slide_designer.forms import SongSlideDesigner, CustomSlideDesigner
from opal.plugins.slide_designer.forms.designer import tr
from opal.plugins.songs.lib import VerseType


class CopyrightNavigationButton(LayoutPresetButton):
    """Keep the missing-copyright badge beside the compact icon or expanded text."""

    def __init__(self, caption):
        super().__init__(caption)
        self.badge = fluentqt.InfoBadge(self)
        self.badge.setDisplayMode(fluentqt.InfoBadge.InfoBadgeDisplayMode.Dot)
        self.badge.setStatus(fluentqt.InfoBadge.InfoBadgeStatus.Critical)
        self.badge.setBeaconDiameter(8)
        self.badge.setAccessibleName(tr('Missing copyright information'))
        self.badge.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.badge.setFixedSize(self.badge.sizeHint())
        self.fluentLayoutChanged.connect(self.update_caption)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.badge.move(self.width() - self.badge.width() - 1, (self.height() - self.badge.height()) // 2)
        self.update_caption()

    def update_caption(self):
        """Keep the full caption accessible when the visible label needs an ellipsis."""
        caption = self.accessibleName()
        if self.fluentLayout() != fluentqt.Button.ButtonLayout.IconOnly:
            width = self.width() - self.iconPixelSize() - 16
            if not self.badge.isHidden():
                width -= self.badge.width() + 4
            caption = self.fontMetrics().elidedText(caption, QtCore.Qt.TextElideMode.ElideRight, max(0, width))
        fluentqt.Button.setText(self, caption)

    def contentPaintRect(self, surface_rect):
        rect = super().contentPaintRect(surface_rect)
        if not self.badge.isHidden() and self.fluentLayout() != fluentqt.Button.ButtonLayout.IconOnly:
            rect.setRight(min(rect.right(), self.width() - self.badge.width() - 8))
        return rect


class ItemEditorMixin:
    """Borrow draft controls for one editing session and return them on every exit path."""

    def setup_item_editor(self):
        self.borrowed = []
        self.metadata_pages = []
        owner = self.design_owner
        tools = self.slide_designer.tools.layout()
        theme_label = tools.takeAt(0).widget()
        tools.removeWidget(self.theme_combo_box)
        self.slide_designer.preview_footer.set_theme(theme_label, self.theme_combo_box)
        self.title_field = self.borrow(owner.title_edit)
        self.title_field.setPlaceholderText(tr('Title'))
        self.title_field.setAccessibleName(tr('Title'))
        self.title_field.setMaximumWidth(280)
        tools.insertWidget(0, self.title_field)
        if self.design_kind == 'song':
            self.alternative_field = self.borrow(owner.alternative_edit)
            self.alternative_field.setPlaceholderText(tr('Alternative title'))
            self.alternative_field.setAccessibleName(tr('Alternative title'))
            self.alternative_field.setMaximumWidth(220)
            tools.insertWidget(1, self.alternative_field)
            tools.insertSpacing(2, 12)
            lyrics_layout = self.editor_splitter.widget(0).layout()
            self.copyright_warning = fluentqt.InfoBar(self.editor_splitter.widget(0))
            self.copyright_warning.setSeverity(fluentqt.InfoBar.InfoBarSeverity.Warning)
            self.copyright_warning.setIsClosable(False)
            self.copyright_warning.setSingleLine(False)
            self.copyright_warning.setMultiLineMinHeight(50)
            self.copyright_warning.setTitle(tr('Missing copyright information'))
            self.copyright_warning.setAccessibleName(self.copyright_warning.title())
            lyrics_layout.insertWidget(1, self.copyright_warning)
            order = QtWidgets.QHBoxLayout()
            order.addWidget(QtWidgets.QLabel(tr('Verse order')))
            order.addWidget(self.borrow(owner.verse_order_edit), 1)
            lyrics_layout.addLayout(order)
            lyrics_layout.addWidget(self.borrow(owner.warning_label))
            self.setup_navigation()
            owner.copyright_edit.textChanged.connect(self.update_copyright_warning)
            self.update_copyright_warning()
            self.lyrics_timer = QtCore.QTimer(self)
            self.lyrics_timer.setSingleShot(True)
            self.lyrics_timer.setInterval(180)
            self.lyrics_timer.timeout.connect(self.sync_lyrics)
            self.design_text_editor.textChanged.connect(self.lyrics_timer.start)
        else:
            tools.insertSpacing(1, 12)
            footer = self.editor_splitter.widget(0).layout()
            footer.addWidget(QtWidgets.QLabel(tr('Credits')))
            footer.addWidget(self.borrow(owner.credit_edit))
            self.setup_navigation()
        self.title_field.textChanged.connect(self.update_title)
        self.title_field.textChanged.connect(self.slide_designer.schedule_refresh)
        if self.design_kind == 'custom':
            owner.credit_edit.textChanged.connect(self.slide_designer.schedule_refresh)
        owner.accepted.connect(self.saved)
        owner.rejected.connect(self.reject)
        self.preview_button = QtWidgets.QPushButton(tr('Save and Preview'))
        self.button_box.addButton(self.preview_button, QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.preview_button.setVisible(not owner.preview_button.isHidden())
        self.preview_button.clicked.connect(self.save_and_preview)

    def borrow(self, widget):
        parent = widget.parentWidget()
        layout = parent.layout()
        placeholder = QtWidgets.QWidget(parent)
        placeholder.hide()
        item = layout.replaceWidget(widget, placeholder)
        if item is None:
            raise RuntimeError(f'Cannot relocate {widget.objectName()}')
        self.borrowed.append((widget, parent, layout, placeholder, widget.isHidden()))
        return widget

    def setup_navigation(self):
        owner = self.design_owner
        self.navigation = fluentqt.NavigationView()
        self.navigation.setDisplayMode(fluentqt.NavigationView.DisplayMode.LeftCompact)
        self.navigation.setCompactPaneWidth(48)
        self.navigation.setExpandedPaneWidth(260)
        self.navigation.setTopBarHeight(0)
        self.navigation.setAnimationEnabled(False)
        self.navigation.setPaneOpen(False)
        pane = QtWidgets.QWidget()
        buttons = QtWidgets.QVBoxLayout(pane)
        buttons.setContentsMargins(4, 4, 4, 4)
        buttons.setSpacing(4)
        toggle = QtWidgets.QPushButton()
        toggle.setIcon(fluent_icon('ic_fluent_line_horizontal_3_24_regular'))
        toggle.setToolTip(tr('Navigation'))
        toggle.setAccessibleName(tr('Navigation'))
        toggle.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)
        toggle.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly)
        toggle.setFixedWidth(40)
        toggle.clicked.connect(self.toggle_navigation)
        buttons.addWidget(toggle, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        self.navigation_buttons = []
        if self.design_kind == 'song':
            entries = ((tr('Slides'), 'slide_text'),
                       (tr('Authors, Topics & Songbooks'), 'people'),
                       (tr('Copyright, Flags & Comments'), 'info'),
                       (tr('Linked Audio'), 'music_note_2'))
        else:
            entries = ((tr('Slides'), 'slide_text'),)
        for index, (caption, icon) in enumerate(entries):
            button = (CopyrightNavigationButton if icon == 'info' else LayoutPresetButton)(caption.replace('&', '&&'))
            button.setIcon(fluent_icon(f'ic_fluent_{icon}_24_regular'))
            button.setToolTip(caption)
            button.setAccessibleName(caption)
            button.setCheckable(True)
            button.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)
            button.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly)
            button.clicked.connect(lambda checked=False, index=index: self.select_page(index))
            buttons.addWidget(button)
            self.navigation_buttons.append(button)
        buttons.addStretch()
        self.navigation.setOwnedMainChromeWidget(pane)
        # Move editor splitter and toolbars into a unified Slides page
        self.dialog_layout.removeWidget(self.editor_splitter)
        self.slides_page = QtWidgets.QWidget(self)
        slides_layout = QtWidgets.QVBoxLayout(self.slides_page)
        slides_layout.setContentsMargins(0, 0, 0, 0)
        slides_layout.setSpacing(0)
        self.dialog_layout.removeWidget(self.command_surface)
        slides_layout.addWidget(self.command_surface)
        slides_layout.addWidget(self.editor_splitter, 1)
        host = self.navigation.contentHost()
        host.addOwnedPage(self.slides_page)
        # Move layouts, retaining the original tabs and their indexes for validation.
        if self.design_kind == 'song':
            for tab in (owner.authors_tab, owner.theme_tab, owner.audio_tab):
                page = QtWidgets.QWidget()
                tab_layout = tab.layout()
                if tab_layout:
                    tab_layout.setContentsMargins(12, 12, 12, 12)
                page.setLayout(tab_layout)
                self.metadata_pages.append((tab, page))
                host.addOwnedPage(page)
            owner.theme_group_box.hide()  # The assigned theme lives beside Layout.
            owner.song_tab_widget.currentChanged.connect(self.select_page)
        self.dialog_layout.insertWidget(0, self.navigation, 1)
        self.select_page(0)

    def toggle_navigation(self):
        expanded = self.navigation.displayMode() == fluentqt.NavigationView.DisplayMode.LeftCompact
        self.navigation.setDisplayMode(fluentqt.NavigationView.DisplayMode.Left if expanded
                                       else fluentqt.NavigationView.DisplayMode.LeftCompact)
        self.navigation.setPaneOpen(expanded)
        for button in self.navigation_buttons:
            button.setFluentLayout(fluentqt.Button.ButtonLayout.IconBefore if expanded
                                   else fluentqt.Button.ButtonLayout.IconOnly)

    def select_page(self, index):
        if self.design_kind == 'song' and index and self.lyrics_timer.isActive():
            self.sync_lyrics()
        self.navigation.contentHost().setCurrentIndex(index, animated=False)
        for i, button in enumerate(self.navigation_buttons):
            button.setChecked(i == index)
        if self.design_kind == 'song':
            with QtCore.QSignalBlocker(self.design_owner.song_tab_widget):
                self.design_owner.song_tab_widget.setCurrentIndex(index)
        if index == 0:
            self.slide_designer.schedule_refresh()

    def sync_lyrics(self):
        self.lyrics_timer.stop()
        self.design_owner.set_verse_text(self.get_all_verses())

    def update_copyright_warning(self):
        missing = not self.design_owner.copyright_edit.toPlainText().strip()
        self.copyright_warning.setVisible(missing)
        button = self.navigation_buttons[2]
        button.badge.setVisible(missing)
        message = self.copyright_warning.title() if missing else ''
        button.setAccessibleDescription(message)
        button.setToolTip(f'{button.accessibleName()}\n{message}' if missing else button.accessibleName())
        button.update_caption()

    def draft_state(self):
        state = super().draft_state()
        owner = self.design_owner
        state['title'] = owner.title_edit.text()
        if self.design_kind == 'custom':
            state['credits'] = owner.credit_edit.text()
        else:
            for key in ('alternative_edit', 'verse_order_edit', 'ccli_number_edit'):
                state[key] = getattr(owner, key).text()
            for key in ('copyright_edit', 'comments_edit'):
                state[key] = getattr(owner, key).toPlainText()
            state['favourite'] = owner.favourite_checkbox.isChecked()
            for key in ('authors_list_view', 'topics_list_view', 'songbooks_list_view', 'audio_list_widget'):
                widget = getattr(owner, key)
                state[key] = [(widget.item(row).text(), widget.item(row).data(QtCore.Qt.ItemDataRole.UserRole))
                              for row in range(widget.count())]
        return state

    def sync_draft(self):
        self.slide_designer.commit_text()
        owner = self.design_owner
        if self.design_kind == 'song':
            self.sync_lyrics()
        else:
            owner.slide_list_view.clear()
            if self.design_text_editor.toPlainText().strip():
                owner.slide_list_view.addItems(self.get_text())
        owner.slide_design = self.slide_designer.serialised_design()
        owner.theme_combo_box.setCurrentText(self.designer_theme_name())

    def accept(self):
        self.slide_designer.commit_text()
        if self.design_kind == 'song' and not self.validate_verse():
            self.select_page(0)
            return
        self.sync_draft()
        self.design_owner.accept()  # Only emits accepted after validation and persistence succeed.

    def saved(self):
        self.done(QtWidgets.QDialog.DialogCode.Accepted)

    def save_and_preview(self):
        self.slide_designer.commit_text()
        if self.design_kind == 'song' and not self.validate_verse():
            self.select_page(0)
            return
        self.sync_draft()
        owner = self.design_owner
        if self.design_kind == 'song':
            if owner._validate_song():
                owner.on_preview(owner.preview_button)
                self.mark_saved()
        else:
            if owner.on_preview_button_clicked():
                self.mark_saved()

    def update_title(self):
        window = getattr(self, 'designer_window', None)
        if window:
            window.update_item_title()

    def restore_controls(self):
        owner = self.design_owner
        owner.accepted.disconnect(self.saved)
        owner.rejected.disconnect(self.reject)
        self.title_field.setMaximumWidth(16777215)
        if hasattr(self, 'alternative_field'):
            self.alternative_field.setMaximumWidth(16777215)
        self.title_field.textChanged.disconnect(self.update_title)
        self.title_field.textChanged.disconnect(self.slide_designer.schedule_refresh)
        if self.design_kind == 'song':
            self.lyrics_timer.stop()
            owner.copyright_edit.textChanged.disconnect(self.update_copyright_warning)
            owner.song_tab_widget.currentChanged.disconnect(self.select_page)
            for tab, page in self.metadata_pages:
                tab.setLayout(page.layout())
            owner.theme_group_box.show()
        else:
            owner.credit_edit.textChanged.disconnect(self.slide_designer.schedule_refresh)
        for widget, parent, layout, placeholder, hidden in reversed(self.borrowed):
            widget.setParent(parent)
            layout.replaceWidget(placeholder, widget)
            widget.setVisible(not hidden)
            placeholder.deleteLater()


class SongItemDesigner(ItemEditorMixin, SongSlideDesigner):
    def __init__(self, owner):
        super().__init__(owner)
        text = []
        for row in range(owner.verse_list_widget.rowCount()):
            item = owner.verse_list_widget.item(row, 0)
            tag = item.data(QtCore.Qt.ItemDataRole.UserRole)
            text.append(f'---[{VerseType.translated_name(tag[0])}:{tag[1:]}]---\n{item.text()}')
        self.set_verse('\n'.join(text))
        self.setup_item_editor()


class CustomItemDesigner(ItemEditorMixin, CustomSlideDesigner):
    def __init__(self, owner):
        super().__init__(owner)
        self.set_text('\n[===]\n'.join(owner.slide_list_view.item(row).text()
                                       for row in range(owner.slide_list_view.count())))
        self.setup_item_editor()


def exec_item_designer(owner, kind):
    editor = (SongItemDesigner if kind == 'song' else CustomItemDesigner)(owner)
    try:
        result = editor.exec()
        if not result:
            owner.reject()
        return result
    finally:
        editor.restore_controls()
        editor.slide_designer.refresh_timer.stop()
        editor.deleteLater()
