# -*- coding: utf-8 -*-
##########################################################################
# OpenLP - Open Source Lyrics Projection                                 #
# ---------------------------------------------------------------------- #
# Copyright (c) 2008 OpenLP Developers                                   #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
##########################################################################
"""
Derive Slide Controller row labels for Bible display slides from raw page text.
"""
from html import escape, unescape
import re

from openlp.plugins.bibles.lib import get_reference_match, get_reference_separator

_SUP_BLOCKS = re.compile(r'\{su\}(.*?)\{/su\}', re.DOTALL)


def bible_chapter_hint_from_row_tag(tag):
    """
    First integer in the row tag (e.g. ``1`` from ``1:1-26``) is used as the
    chapter when a page only shows verse-only superscripts.
    """
    if not tag:
        return None
    parts = re.findall(r'\d+', str(tag))
    return int(parts[0]) if parts else None


def _strip_sup_inner(raw):
    s = raw.replace('&nbsp;', ' ').replace('\xa0', ' ').strip()
    for open_b, close_b in ('(', ')'), ('[', ']'), ('{', '}'):
        if s.startswith(open_b) and s.endswith(close_b):
            s = s[len(open_b):-len(close_b)].strip()
    return s.strip()


def _parse_sup_inner_to_cv(inner, current_chapter):
    cleaned = _strip_sup_inner(inner)
    if not cleaned:
        return None
    rm = get_reference_match('range')
    m = rm.match(cleaned)
    if m:
        fc = m.group('from_chapter')
        fv = m.group('from_verse')
        ch = int(fc) if fc else current_chapter
        vs = int(fv)
        if ch is None:
            return None
        return (ch, vs)
    nums = re.findall(r'\d+', cleaned)
    if len(nums) == 1 and current_chapter is not None:
        return (current_chapter, int(nums[0]))
    if len(nums) >= 2:
        return (int(nums[0]), int(nums[1]))
    return None


def _format_ref_span(refs):
    vsep = get_reference_separator('sep_v_display')
    rsep = get_reference_separator('sep_r_display')
    first, last = refs[0], refs[-1]
    start = f'{first[0]}{vsep}{first[1]}'
    if first == last:
        return start
    end = str(last[1]) if first[0] == last[0] else f'{last[0]}{vsep}{last[1]}'
    return f'{start}{rsep}{end}'


def row_label_from_raw_page_text(page, default_chapter=None):
    """
    Build a ``chapter`` + verse-sep + verse[/range] label for one paginated
    slide, using ``{su}…{/su}`` markers in the raw slide text.

    :param page: One page string from :func:`ThemePreviewRenderer.format_slide`.
    :param default_chapter: Chapter to use for verse-only markers (same as
        :func:`bible_chapter_hint_from_row_tag` on the raw slide's row tag).
    :return: Label string, or ``None`` if no markers could be parsed.
    """
    refs = page_verse_references(page, default_chapter)
    return _format_ref_span(refs) if refs else None


def page_verse_references(page, default_chapter=None):
    """Parse page markers in order, carrying the chapter through verse-only markers."""
    if not page or '{su}' not in page:
        return []
    matches = _SUP_BLOCKS.findall(page)
    if not matches:
        return []
    current_chapter = default_chapter
    refs = []
    for inner in matches:
        cv = _parse_sup_inner_to_cv(inner, current_chapter)
        if cv is None:
            continue
        current_chapter = cv[0]
        refs.append(cv)
    return refs


def bible_preview_html(page):
    """Keep only superscript formatting in escaped slide-list text."""
    from openlp.core.display.render import RE_HTML_STRIP, remove_tags, remove_unknown_tags

    def plain(text):
        return escape(unescape(RE_HTML_STRIP.sub('', remove_tags(text, can_remove_chords=True)))).replace('\n', '<br>')

    parts = []
    offset = 0
    for match in _SUP_BLOCKS.finditer(page):
        parts.append(plain(page[offset:match.start()]))
        parts.append('<sup>' + plain(match.group(1)) + '</sup>')
        offset = match.end()
    parts.append(plain(page[offset:]))
    return remove_unknown_tags(''.join(parts))
