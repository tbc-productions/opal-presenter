"""Installed font weights and synthetic bold fallback in the theme controls."""
from unittest.mock import patch

from opal.core.pages.fontselect import FontSelectPage


def test_supported_weights_deduplicate_font_faces(settings):
    with patch('opal.core.pages.fontselect.QtGui.QFontDatabase.styles',
               return_value=['Regular', 'Italic', 'Medium', 'Medium Italic', 'Black']), \
            patch('opal.core.pages.fontselect.QtGui.QFontDatabase.weight',
                  side_effect=lambda family, style: {'Regular': 400, 'Italic': 400, 'Medium': 500,
                                                     'Medium Italic': 500, 'Black': 900}[style]):
        assert FontSelectPage.supported_weights('Example') == [400, 500, 900]


def test_font_weight_choices_and_single_weight_fallback(settings):
    with patch.object(FontSelectPage, 'supported_weights', return_value=[300, 400, 600, 900]):
        page = FontSelectPage()
        assert [page.font_weight_combo.itemData(i)
                for i in range(page.font_weight_combo.count())] == [300, 400, 600, 900]
        assert page.style_bold_button.isHidden()
        assert not page.font_weight_combo.isHidden()
        changes = []
        page.font_weight_changed.connect(changes.append)
        page.font_weight_combo.setCurrentIndex(2)
        assert page.font_weight == 600
        assert changes == [600]
    with patch.object(FontSelectPage, 'supported_weights', return_value=[400]):
        page._on_font_name_changed('Single face')
        assert not page.style_bold_button.isHidden()
        assert page.font_weight_combo.isHidden()
        page.style_bold_button.click()
        assert page.font_weight == 400
        page.style_bold_button.click()
        assert page.font_weight == 700
    with patch.object(FontSelectPage, 'supported_weights', return_value=[300, 400, 500]):
        page._on_font_name_changed('Another family')
        assert page.font_weight == 500
        assert page.font_weight_combo.currentData() == 500
