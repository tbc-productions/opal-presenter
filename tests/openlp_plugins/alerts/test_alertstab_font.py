"""Alert font selection for existing installations."""
import pytest

from openlp.core.common.settings import get_default_alert_font
from openlp.plugins.alerts.lib.alertstab import AlertsTab


@pytest.mark.parametrize('saved_font', ['', '   '])
def test_empty_saved_font_selects_default(registry, settings, saved_font):
    """A blank saved font selects the same fallback in settings and the preview."""
    settings.setValue('alerts/font face', saved_font)
    expected = get_default_alert_font()

    alerts_tab = AlertsTab(None, 'alerts', 'Alerts', ':/icon/openlp-logo.svg')

    assert settings.value('alerts/font face') == expected
    assert alerts_tab.font_combo_box.currentText() == expected
    assert alerts_tab.font_preview.font().family() == expected
    settings.beginGroup('alerts')
    try:
        assert settings.value('font face') == expected
    finally:
        settings.endGroup()
    alerts_tab.save()
    assert settings.value('alerts/font face') == expected
