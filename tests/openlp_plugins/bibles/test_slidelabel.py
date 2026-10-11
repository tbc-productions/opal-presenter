# -*- coding: utf-8 -*-
##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
##########################################################################
"""Tests for Bible slide row label parsing."""
import pytest

from openlp.plugins.bibles.lib import update_reference_separators
from openlp.plugins.bibles.lib.slidelabel import (
    bible_chapter_hint_from_row_tag,
    row_label_from_raw_page_text,
)


@pytest.fixture(autouse=True)
def _reference_separators(settings):
    update_reference_separators()


def test_bible_chapter_hint_from_row_tag():
    assert bible_chapter_hint_from_row_tag('1:1-26') == 1
    assert bible_chapter_hint_from_row_tag('3:16') == 3
    assert bible_chapter_hint_from_row_tag('') is None


def test_row_label_full_chapter_verse_in_markers():
    page = '{su}1:1&nbsp;{/su}A {su}1:2&nbsp;{/su}B {su}1:3&nbsp;{/su}C'
    assert row_label_from_raw_page_text(page) == '1:1-3'


def test_row_label_verse_only_uses_default_chapter():
    hint = bible_chapter_hint_from_row_tag('1:1-26')
    page = '{su}(4)&nbsp;{/su}Four {su}(5)&nbsp;{/su}Five'
    assert row_label_from_raw_page_text(page, default_chapter=hint) == '1:4-5'


def test_row_label_round_brackets():
    page = '{su}(1:1)&nbsp;{/su}Text'
    assert row_label_from_raw_page_text(page) == '1:1'


def test_row_label_returns_none_without_sup_tags():
    assert row_label_from_raw_page_text('Plain text') is None


def test_row_label_spans_chapters():
    page = '{su}30{/su}A {su}31{/su}B {su}2:1{/su}C {su}5{/su}D'
    assert row_label_from_raw_page_text(page, default_chapter=1) == '1:30-2:5'


def test_bible_preview_preserves_superscripts_and_spacing():
    from openlp.plugins.bibles.lib.slidelabel import bible_preview_html

    assert bible_preview_html('{su}30&nbsp;{/su}A &amp; B\n{su}31&nbsp;{/su}C') == (
        '<sup>30 </sup>A &amp; B<br><sup>31 </sup>C')


def test_bible_row_strips_custom_tags_around_superscripts():
    from openlp.plugins.bibles.lib.slidelabel import bible_preview_html

    assert bible_preview_html('{cg}{su}1&nbsp;{/su}In the beginning{/cg}') == (
        '<sup>1 </sup>In the beginning')
