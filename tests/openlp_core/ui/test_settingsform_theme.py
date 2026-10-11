"""Interface theme changes require an explicit restart reminder after saving."""
from unittest.mock import patch

import pytest
from opal.core.widgets import fluent as QtWidgets

from opal.core.ui.generaltab import GeneralTab
from opal.core.ui.settingsform import SettingsForm
from opal.core.ui.style import UiThemes


@pytest.fixture()
def form(settings, qtbot):
    form = SettingsForm()
    qtbot.addWidget(form)
    return form


@pytest.mark.parametrize('index', [1, 2])
def test_changed_theme_prompts_after_saving(settings, form, index):
    tab = GeneralTab(form)
    form.insert_tab(tab)
    tab.ui_theme_style_combo_box.setCurrentIndex(index)

    def check_saved_theme(*args):
        assert form.result() == QtWidgets.QDialog.DialogCode.Accepted
        assert settings.value('advanced/ui_theme_name') == GeneralTab.get_ui_theme_name(index)
        assert settings.value('advanced/interface style') == 'modern'

    with patch('opal.core.ui.settingsform.show_restart_message', side_effect=check_saved_theme) as reminder:
        form.accept()

    reminder.assert_called_once_with(
        form, 'Restart required', 'Your interface theme has been saved. Restart Opal Presenter to apply it.')


def test_unchanged_theme_does_not_prompt(settings, form):
    tab = GeneralTab(form)
    form.insert_tab(tab)
    tab.ui_theme_style_combo_box.setCurrentIndex(1)
    tab.ui_theme_style_combo_box.setCurrentIndex(0)
    tab.number_edit.setText('12345')

    with patch('opal.core.ui.settingsform.show_restart_message') as reminder:
        form.accept()

    assert settings.value('core/ccli number') == '12345'
    reminder.assert_not_called()


def test_cancelled_theme_change_does_not_prompt_or_save(settings, form):
    tab = GeneralTab(form)
    form.insert_tab(tab)
    tab.ui_theme_style_combo_box.setCurrentIndex(1)

    with patch('opal.core.ui.settingsform.show_restart_message') as reminder:
        form.reject()

    assert settings.value('advanced/interface style') == 'modern'
    assert settings.value('advanced/ui_theme_name') == UiThemes.Automatic
    reminder.assert_not_called()
