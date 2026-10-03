"""Preferences help icons provide guidance without covering settings controls."""
from unittest.mock import patch

from openlp.core.widgets import fluent as QtWidgets

from openlp.core.ui.generaltab import GeneralTab
from openlp.core.ui.servicetab import ServiceTab
from openlp.core.ui.settingsform import SettingsForm
from openlp.plugins.bibles.lib.biblestab import BiblesTab
from openlp.plugins.songs.lib.songstab import SongsTab
from openlp.plugins.songs.songsplugin import song_footer


def test_general_settings_show_help_only_for_useful_hints(settings):
    form = SettingsForm()
    general_tab = GeneralTab(form)

    form.insert_tab(general_tab)

    assert form.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Help) is None
    assert 'OpenLP+' in general_tab.check_for_updates_check_box.text()
    assert 'OpenLP+' in general_tab.check_for_remote_updates_check_box.text()
    assert not general_tab.autoscroll_combo_box.toolTip()
    autoscroll_help = general_tab.autoscroll_label.parentWidget().findChild(QtWidgets.QToolButton,
                                                                            'settings_help_icon')
    assert 'slide controller' in autoscroll_help.help_text
    assert autoscroll_help.text() == ''
    assert not autoscroll_help.icon().isNull()
    row = autoscroll_help.parentWidget().layout()
    assert row.itemAt(0).widget() is general_tab.autoscroll_label
    assert row.itemAt(1).widget() is autoscroll_help
    assert not general_tab.auto_open_check_box.property('settings_help_icon_added')
    assert not general_tab.single_click_preview_check_box.property('settings_help_icon_added')

    # Reopening Settings must reuse the same icon, rather than nesting wrappers.
    icon_count = len(general_tab.findChildren(QtWidgets.QToolButton, 'settings_help_icon'))
    form.insert_tab(general_tab)
    assert len(general_tab.findChildren(QtWidgets.QToolButton, 'settings_help_icon')) == icon_count


def test_song_settings_show_help_icon(settings):
    settings.extend_default_settings(song_footer)
    form = SettingsForm()
    songs_tab = SongsTab(form, 'songs', 'Songs', ':/plugins/plugin_songs.png')

    form.insert_tab(songs_tab)

    assert form.setting_list_widget.count() == 1
    assert form.setting_list_widget.item(0).text() == 'Songs'
    assert not songs_tab.update_on_edit_check_box.toolTip()
    help_icon = songs_tab.update_on_edit_check_box.parentWidget().findChild(QtWidgets.QToolButton,
                                                                            'settings_help_icon')
    assert 'Service' in help_icon.help_text


def test_default_service_name_help_lists_date_and_time_codes(settings):
    form = SettingsForm()
    service_tab = ServiceTab(form)

    form.insert_tab(service_tab)

    assert not service_tab.service_name_edit.toolTip()
    help_icon = service_tab.service_name_label.parentWidget().findChild(QtWidgets.QToolButton,
                                                                        'settings_help_icon')
    tip = help_icon.help_text
    for code in ('%Y', '%y', '%m', '%b', '%B', '%d', '%a', '%A', '%H', '%I', '%M', '%S', '%p'):
        assert code in tip
    assert '<b>Year:</b>' in tip
    assert '<br/>' in tip
    assert 'when Now is selected' in tip


def test_bible_reference_hint_moves_to_help_icon(settings):
    settings.extend_default_settings({
        'bibles/verse separator': ':',
        'bibles/range separator': '-',
        'bibles/list separator': ',',
        'bibles/end separator': '',
        'bibles/reference format': '${bible_reference}'
    })
    form = SettingsForm()
    bibles_tab = BiblesTab(form, 'bibles', 'Bibles', ':/plugins/plugin_bibles.png')

    form.insert_tab(bibles_tab)

    assert not bibles_tab.verse_separator_line_edit.toolTip()
    assert not bibles_tab.verse_separator_check_box.toolTip()
    help_icon = bibles_tab.verse_separator_check_box.parentWidget().findChild(QtWidgets.QToolButton,
                                                                              'settings_help_icon')
    assert '|' in help_icon.help_text
    assert bibles_tab.reference_format_label.text() == 'Footer reference template:'
    assert not bibles_tab.reference_format_label.wordWrap()
    reference_row = bibles_tab.reference_format_label.parentWidget().layout()
    assert reference_row.itemAt(0).widget() is bibles_tab.reference_format_label
    assert reference_row.itemAt(1).widget().objectName() == 'settings_help_icon'
    layout_style_help = bibles_tab.layout_style_label.parentWidget().findChild(QtWidgets.QToolButton,
                                                                               'settings_help_icon')
    for style in ('Verse Per Slide', 'Verse Per Line', 'Continuous', 'Continuous (whole verses)'):
        assert style in layout_style_help.help_text
    assert 'already in the Service' in layout_style_help.help_text


def test_help_icon_error_does_not_hide_settings_section(settings):
    form = SettingsForm()
    general_tab = GeneralTab(form)

    with patch('openlp.core.ui.settingsform.apply_settings_tooltips', side_effect=RuntimeError('help failed')):
        form.insert_tab(general_tab)

    assert form.setting_list_widget.count() == 1
    assert form.setting_list_widget.item(0).text() == general_tab.tab_title_visible


def test_help_button_opens_teaching_tip_from_keyboard(settings, qtbot):
    from PySide6 import QtCore, QtTest
    import fluentqt
    from openlp.core.ui.settingstooltips import SettingsHelpButton

    window = QtWidgets.QWidget()
    qtbot.addWidget(window)
    window.resize(600, 400)
    button = SettingsHelpButton('Guidance for this setting.', window)
    button.move(200, 100)
    window.show()
    button.setFocus()
    QtTest.QTest.keyClick(button, QtCore.Qt.Key.Key_Space)

    tip = button.teaching_tip
    assert isinstance(tip, fluentqt.TeachingTip)
    assert tip.isOpen()
    assert tip.target() == button
    assert button.help_label.text() == button.help_text
    assert button.toolTip() == ''
    QtTest.QTest.keyClick(tip, QtCore.Qt.Key.Key_Escape)
    assert not tip.isOpen()
    button.click()
    assert button.teaching_tip is tip
    assert tip.isOpen()
    close_button = tip.findChild(QtWidgets.QToolButton)
    close_button.click()
    assert not tip.isOpen()


def test_help_tip_dismisses_when_clicking_outside_or_hiding_setting(settings, qtbot):
    from PySide6 import QtCore, QtTest
    from openlp.core.ui.settingstooltips import SettingsHelpButton

    window = QtWidgets.QWidget()
    qtbot.addWidget(window)
    window.resize(600, 400)
    button = SettingsHelpButton('First hint', window)
    button.move(200, 100)
    other = SettingsHelpButton('Second hint', window)
    other.move(200, 150)
    window.show()
    button.click()
    tip = button.teaching_tip
    tip.setAnimationEnabled(False)
    QtTest.QTest.mouseClick(window, QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(10, 10))
    assert not tip.isOpen()
    button.click()
    other.click()
    assert not tip.isOpen()
    assert other.teaching_tip.isOpen()
    other.hide()
    assert not other.teaching_tip.isOpen()


def test_service_name_teaching_tip_fits_formatted_guidance(settings, qtbot):
    form = SettingsForm()
    qtbot.addWidget(form)
    service_tab = ServiceTab(form)
    form.insert_tab(service_tab)
    form.resize(1000, 700)
    form.show()
    help_icon = service_tab.service_name_label.parentWidget().findChild(QtWidgets.QToolButton,
                                                                       'settings_help_icon')
    help_icon.click()
    tip = help_icon.teaching_tip
    tip.setAnimationEnabled(False)
    QtWidgets.QApplication.processEvents()
    assert tip.isOpen()
    assert help_icon.help_label.text() == help_icon.help_text
    label = help_icon.help_label
    assert label.height() >= label.heightForWidth(label.width())
    assert tip.contentHost().rect().contains(label.geometry())
