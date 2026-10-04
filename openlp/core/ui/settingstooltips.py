"""Contextual help for settings whose labels need more explanation."""
import fluentqt
from PySide6 import QtCore
from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common.i18n import translate
from openlp.core.ui.icons import UiIcons


class SettingsHelpButton(QtWidgets.QToolButton):
    """Open persistent, dismissible setting guidance in an anchored TeachingTip."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.help_text = text
        self.teaching_tip = None
        self.setObjectName('settings_help_icon')
        self.setIcon(UiIcons().help)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setFixedSize(20, 20)
        self.setAutoRaise(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(translate('OpenLP.SettingsTooltips', 'Setting help'))
        self.setAccessibleDescription(text)
        self.clicked.connect(self.show_help)

    def show_help(self):
        if self.teaching_tip is not None and self.teaching_tip.isOpen():
            self.teaching_tip.close()
            return
        for tip in self.window().findChildren(fluentqt.TeachingTip, 'settings_teaching_tip'):
            tip.close()
        if self.teaching_tip is None:
            self.teaching_tip = fluentqt.TeachingTip(self.window())
            self.teaching_tip.setObjectName('settings_teaching_tip')
            self.teaching_tip.setLightDismissEnabled(True)
            self.teaching_tip.setClosePolicy(fluentqt.Popup.CloseFlag.CloseOnPressOutside |
                                             fluentqt.Popup.CloseFlag.CloseOnEscape)
            host = self.teaching_tip.contentHost()
            layout = QtWidgets.QVBoxLayout(host)
            layout.setContentsMargins(16, 12, 16, 16)
            content = QtWidgets.QHBoxLayout()
            content.setSpacing(8)
            self.help_label = QtWidgets.QLabel(self.help_text, host)
            self.help_label.setWordWrap(True)
            self.help_label.setTextFormat(QtCore.Qt.TextFormat.RichText)
            content.addWidget(self.help_label)
            close_button = fluentqt.Button(host)
            close_button.setObjectName('settings_teaching_tip_close')
            close_button.setFluentLayout(fluentqt.Button.ButtonLayout.IconOnly)
            close_button.setFluentStyle(fluentqt.Button.ButtonStyle.Subtle)
            close_button.setIcon(UiIcons().backspace)
            close_button.setIconSize(QtCore.QSize(16, 16))
            close_button.setFixedSize(30, 30)
            close_button.setAccessibleName(translate('OpenLP.SettingsTooltips', 'Close help'))
            close_button.clicked.connect(lambda: self.teaching_tip.closeWithReason(
                fluentqt.TeachingTip.CloseReason.CloseButton))
            content.addWidget(close_button, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
            layout.addLayout(content)
        width = min(420, max(240, self.window().width() - 32))
        self.help_label.setFixedWidth(width - 32 - 30 - 8)
        self.teaching_tip.setCardSize(QtCore.QSize(width, self.teaching_tip.contentHost().layout().sizeHint().height()))
        self.teaching_tip.showAt(self)

    def hideEvent(self, event):
        if self.teaching_tip is not None:
            self.teaching_tip.close()
        super().hideEvent(event)


def _add_help_icon(control, label, tip):
    """Put a separate, keyboard reachable help icon immediately after a setting label."""
    if label.property('settings_help_icon_added'):
        return
    parent = label.parentWidget()
    wrapper = QtWidgets.QWidget(parent)
    wrapper.setObjectName('settings_help_wrapper')
    layout = parent.layout() if parent is not None else None
    while layout is None and parent is not None:
        parent = parent.parentWidget()
        layout = parent.layout() if parent is not None else None
    if layout is None or layout.replaceWidget(label, wrapper) is None:
        wrapper.deleteLater()
        return
    row = QtWidgets.QHBoxLayout(wrapper)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(5)
    row.addWidget(label)
    help_icon = SettingsHelpButton(tip, wrapper)
    row.addWidget(help_icon)
    row.addStretch()
    label.setProperty('settings_help_icon_added', True)
    control.setToolTip('')
    label.setToolTip('')


def apply_settings_tooltips(tab):
    """Add help icons only where the hint supplies information absent from the label."""
    separator_tip = translate(
        'OpenLP.SettingsTooltips',
        'Separate alternative markers with |. Leave the field empty to use the default marker.')
    hints = {
        'ServiceTab': [
            ('service_name_edit', 'service_name_label', translate(
                'OpenLP.SettingsTooltips',
                'Use ordinary text with these date and time codes:<br/><br/>'
                '<b>Year:</b> %Y (four digits), %y (two digits)<br/>'
                '<b>Month:</b> %m (number), %b (short name), %B (full name)<br/>'
                '<b>Day:</b> %d (day of month), %a (short weekday), %A (full weekday)<br/>'
                '<b>Time:</b> %H (24-hour), %I (12-hour), %M (minute), %S (second), %p (AM/PM)<br/><br/>'
                '<b>Example:</b> Service %Y-%m-%d %H-%M<br/>'
                '<b>Note:</b> Codes use the selected day and time, or the current date and time when Now is '
                'selected. Use hyphens instead of colons in filenames.')),
            ('wrap_slide_radio_button', None, translate(
                'OpenLP.SettingsTooltips',
                'Wrap from the last slide of an item to its first slide, and back.')),
        ],
        'AdvancedTab': [
            ('data_directory_protect_check_box', None, translate(
                'OpenLP.SettingsTooltips',
                'Prevent multiple OpenLP+ instances from using the data directory at once.')),
            ('copy_library_files_check_box', None, translate(
                'OpenLP.SettingsTooltips',
                'Copy imported library files into the OpenLP+ data directory.')),
            ('x11_bypass_check_box', None, translate(
                'OpenLP.SettingsTooltips',
                'Try this on X11 if the display window disappears or draws incorrectly.')),
        ],
        'ScreensTab': [
            ('display_on_monitor_check', None, translate(
                'OpenLP.SettingsTooltips',
                'Show output in a separate window when only one screen is available.')),
        ],
        'ThemesTab': [
            ('song_level_radio_button', None, translate(
                'OpenLP.SettingsTooltips',
                'Prefer a song theme, then a service theme, then the global theme.')),
            ('service_level_radio_button', None, translate(
                'OpenLP.SettingsTooltips',
                'Use the service theme in preference to song themes.')),
        ],
        'ApiTab': [
            ('address_edit', 'address_label', translate(
                'OpenLP.SettingsTooltips',
                'Use 0.0.0.0 to let the web remote listen on all network interfaces.')),
        ],
        'SongsTab': [
            ('update_on_edit_check_box', None, translate(
                'OpenLP.SettingsTooltips',
                'Also update copies of the song already in the Service.')),
            ('uppercase_check_box', None, translate(
                'OpenLP.SettingsTooltips',
                'Change how lyrics appear without changing the saved song text.')),
            ('first_slide_mode_combobox', 'first_slide_mode_label', translate(
                'OpenLP.SettingsTooltips',
                'Choose whether songbook details appear on the first song slide.')),
        ],
        'BiblesTab': [
            ('bible_search_while_typing_check_box', None, translate(
                'BiblesPlugin.BiblesTab',
                'Text searches require at least {count} characters and a space for performance reasons.').format(
                    count='8')),
            ('layout_style_combo_box', 'layout_style_label', translate(
                'OpenLP.SettingsTooltips',
                '<b>Verse Per Slide:</b> Show one verse on each slide.<br/>'
                '<b>Verse Per Line:</b> Start each verse on a new line until the slide is full.<br/>'
                '<b>Continuous:</b> Run verses together, separated by verse numbers and chapter numbers '
                'when shown.<br/>'
                '<b>Continuous (whole verses):</b> Run verses together, but start a new slide if the next '
                'verse will not fit in full.<br/><br/>'
                '<b>Note:</b> Changes do not affect verses already in the Service.')),
            ('bible_theme_combo_box', 'bible_theme_label', translate(
                'OpenLP.SettingsTooltips',
                'Use this theme when song-level themes are selected.')),
            ('verse_separator_line_edit', 'verse_separator_check_box', separator_tip),
            ('range_separator_line_edit', 'range_separator_check_box', separator_tip),
            ('list_separator_line_edit', 'list_separator_check_box', separator_tip),
            ('end_separator_line_edit', 'end_separator_check_box', separator_tip),
            ('reference_format_text_edit', 'reference_format_label', translate(
                'OpenLP.SettingsTooltips',
                'Use Mako variables such as ${bible_reference}, ${version}, ${copyright}, and ${permission}.')),
        ],
        'CustomTab': [
            ('display_footer_check_box', None, translate(
                'OpenLP.SettingsTooltips',
                'Credits still appear in the footer when they are present.')),
        ],
        'PresentationTab': [
            ('ppt_window_check_box', None, translate(
                'PresentationPlugin.PresentationTab',
                'This may fix PowerPoint scaling issues in Windows 8 and 10.')),
        ],
    }.get(type(tab).__name__, ())
    for control_name, label_name, tip in hints:
        control = getattr(tab, control_name, None)
        label = getattr(tab, label_name, None) if label_name else control
        if isinstance(control, QtWidgets.QWidget) and isinstance(label, QtWidgets.QWidget):
            _add_help_icon(control, label, tip)
