"""Settings sections remain stacked across dialog widths."""
from unittest.mock import patch

from openlp.core.lib.settingstab import SettingsTab
from openlp.core.widgets import fluent


def test_settings_sections_stack_at_all_widths(qapp, qtbot):
    with patch.object(SettingsTab, '_setup'):
        tab = SettingsTab(None, 'Test')
    qtbot.addWidget(tab)
    tab.setup_ui()
    left = fluent.QGroupBox('First section', tab.left_column)
    right = fluent.QGroupBox('Second section', tab.right_column)
    tab.left_layout.addWidget(left)
    tab.left_layout.addStretch()
    tab.right_layout.addWidget(right)
    tab.right_layout.addStretch()
    tab.show()
    for width in (640, 1200):
        tab.resize(width, 600)
        fluent.QApplication.processEvents()
        assert tab.left_column.x() == tab.right_column.x()
        assert tab.left_column.width() == tab.right_column.width()
        assert tab.right_column.y() >= tab.left_column.geometry().bottom()
        assert tab.left_column.width() == width - 24


def test_bible_settings_fit_without_horizontal_scrollbar(settings, qtbot):
    """Long search guidance must wrap instead of widening all settings cards."""
    from openlp.plugins.bibles.lib.biblestab import BiblesTab
    from openlp.core.ui.settingstooltips import apply_settings_tooltips

    settings.extend_default_settings({'bibles/reference format': '${bible_reference} (${copyright})'})
    tab = BiblesTab(None, 'Bibles')
    apply_settings_tooltips(tab)
    area = fluent.QScrollArea()
    qtbot.addWidget(area)
    area.setWidgetResizable(True)
    area.setWidget(tab)
    area.resize(600, 650)
    area.show()
    fluent.QApplication.processEvents()
    assert area.horizontalScrollBar().maximum() == 0
    assert tab.scripture_reference_group_box.width() <= area.viewport().width()
    help_button = tab.bible_search_while_typing_check_box.parentWidget().findChild(
        fluent.QToolButton, 'settings_help_icon')
    assert '8 characters and a space' in help_button.help_text


def test_presentations_fit_without_horizontal_scrollbar(settings, qtbot):
    """PowerPoint guidance remains readable in the settings viewport."""
    from openlp.plugins.presentations.lib.presentationtab import PresentationTab
    from openlp.core.ui.settingstooltips import apply_settings_tooltips

    with patch.object(SettingsTab, '_setup'):
        tab = PresentationTab(None, 'Presentations', None, {}, None)
    tab.setup_ui()
    tab.retranslate_ui()
    apply_settings_tooltips(tab)
    area = fluent.QScrollArea()
    qtbot.addWidget(area)
    area.setWidgetResizable(True)
    area.setWidget(tab)
    area.resize(600, 650)
    area.show()
    fluent.QApplication.processEvents()
    assert area.horizontalScrollBar().maximum() == 0
    assert tab.ppt_window_check_box.width() >= tab.ppt_window_check_box.minimumSizeHint().width()
    assert '\n' not in tab.ppt_window_check_box.text()
    for control, explanation in (
            (tab.ppt_window_check_box, 'This may fix PowerPoint scaling issues in Windows 8 and 10.'),):
        help_button = control.parentWidget().findChild(fluent.QToolButton, 'settings_help_icon')
        assert help_button.help_text == explanation
        help_button.click()
        assert help_button.teaching_tip.isOpen()
        assert help_button.help_label.text() == explanation
        help_button.teaching_tip.close()
