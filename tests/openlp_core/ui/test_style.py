from unittest.mock import MagicMock, patch

import pytest

from PySide6 import QtCore, QtGui
from opal.core.widgets import fluent as QtWidgets

from opal.core.ui.style import (UiThemes, get_application_stylesheet, get_library_stylesheet,
                                  is_ui_theme_dark, set_default_theme)

import opal.core.ui.style
import fluentqt


@patch('opal.core.ui.style.HAS_DARK_THEME', False)
@patch('opal.core.ui.style.is_system_darkmode')
def test_is_ui_theme_automatic_dark_when_system_dark(mocked_is_system_darkmode, mock_settings):
    """Test that the Automatic UI Theme is Dark on System Dark Theme"""
    # GIVEN: UI theme is Automatic and System Theme is Dark
    mock_settings.value.return_value = UiThemes.Automatic
    mocked_is_system_darkmode.return_value = True

    # WHEN: is_ui_theme_dark() is called
    result = is_ui_theme_dark()

    # THEN: the result should be true
    assert result is True


@patch('opal.core.ui.style.HAS_DARK_THEME', False)
@patch('opal.core.ui.style.is_system_darkmode')
def test_is_ui_theme_dark_automatic_light_when_system_light(mocked_is_system_darkmode, mock_settings):
    """Test that the Automatic UI Theme is not Dark on System Light Theme"""
    # GIVEN: UI theme is Automatic and System Theme is Light
    mocked_is_system_darkmode.return_value = False
    mock_settings.value.return_value = UiThemes.Automatic

    # WHEN: is_ui_theme_dark() is called
    result = is_ui_theme_dark()

    # THEN: the result should be false
    assert result is False


@patch('opal.core.ui.style.HAS_DARK_THEME', False)
def test_is_ui_theme_dark_defaultlight_not_dark(mock_settings):
    """Test that the DefaultLight UI Theme is not Dark"""
    # GIVEN: UI theme is DefaultLight
    mock_settings.value.return_value = UiThemes.DefaultLight

    # WHEN: is_ui_theme_dark() is called
    result = is_ui_theme_dark()

    # THEN: the result should be false
    assert result is False


@patch('opal.core.ui.style.HAS_DARK_THEME', False)
def test_is_ui_theme_dark_defaultdark_dark(mock_settings):
    """Test that the DefaultDark UI Theme is Dark"""
    # GIVEN: UI theme is DefaultDark
    mock_settings.value.return_value = UiThemes.DefaultDark

    # WHEN: is_ui_theme_dark() is called
    result = is_ui_theme_dark()

    # THEN: the result should be true
    assert result is True


@pytest.mark.skipif(not hasattr(opal.core.ui.style, 'qdarkstyle'), reason='qdarkstyle is not installed')
@patch('opal.core.ui.style.HAS_DARK_THEME', True)
def test_is_ui_theme_dark_qdarkstyle_dark(mock_settings):
    """Test that the QDarkStyle UI Theme is Dark"""
    # GIVEN: UI theme is DefaultDark
    mock_settings.value.return_value = UiThemes.QDarkStyle

    # WHEN: is_ui_theme_dark() is called
    result = is_ui_theme_dark()

    # THEN: the result should be true
    assert result is True


@patch('opal.core.ui.style.is_macosx', return_value=True)
def test_set_default_lightmode_on_macos_uses_fusion_and_standard_palette(_mock_is_macosx):
    """Test that explicit light mode uses Fusion styling and sets a palette on macOS."""
    from opal.core.ui.style import set_default_lightmode

    mock_app = MagicMock()
    set_default_lightmode(mock_app)

    mock_app.setStyle.assert_called_once_with('Fusion')
    mock_app.setPalette.assert_called_once()


@patch('opal.core.ui.style.is_macosx', return_value=True)
def test_set_default_darkmode_on_macos_uses_fusion_and_sets_palette(_mock_is_macosx):
    """Test that explicit dark mode uses Fusion and applies dark palette on macOS."""
    from opal.core.ui.style import set_default_darkmode

    mock_app = MagicMock()
    set_default_darkmode(mock_app)

    mock_app.setStyle.assert_called_once_with('Fusion')
    mock_app.setPalette.assert_called_once()


@pytest.mark.parametrize('scheme, dark', [(QtCore.Qt.ColorScheme.Dark, True),
                                          (QtCore.Qt.ColorScheme.Light, False),
                                          (QtCore.Qt.ColorScheme.Unknown, False)])
def test_linux_system_colour_scheme(scheme, dark):
    """Auto follows Qt's system colour scheme on platforms without a native probe."""
    with patch('opal.core.ui.style.IS_SYSTEM_DARKMODE', None), \
            patch('opal.core.ui.style.is_win', return_value=False), \
            patch('opal.core.ui.style.is_macosx', return_value=False), \
            patch('opal.core.ui.style.QtWidgets.QApplication.instance') as app:
        app.return_value.styleHints.return_value.colorScheme.return_value = scheme
        assert opal.core.ui.style.is_system_darkmode() is dark


@pytest.mark.parametrize('scheme, expected', [
    (UiThemes.DefaultDark, fluentqt.Theme.Dark), (UiThemes.QDarkStyle, fluentqt.Theme.Dark),
    (UiThemes.DefaultLight, fluentqt.Theme.Light)])
def test_native_theme_and_palette(settings, scheme, expected):
    settings.setValue('advanced/ui_theme_name', scheme)
    app = QtWidgets.QApplication.instance()
    set_default_theme(app)
    assert fluentqt.current_theme() == expected
    dark = app.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128
    assert dark == (expected == fluentqt.Theme.Dark)
    assert app.font() == fluentqt.font_for_role(fluentqt.FontRole.Body)


def test_stylesheet_does_not_replace_native_controls(settings):
    stylesheet = get_application_stylesheet()
    assert 'QCheckBox {' not in stylesheet
    assert 'QPushButton {' not in stylesheet
    assert get_library_stylesheet() == ''
