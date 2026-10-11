"""Source-preserving editing of paginated lyrics."""
import pytest

from opal.plugins.slide_designer.forms.textediting import visible_text, replace_visible_text, source_selection


@pytest.mark.parametrize('source,before,after,expected', [
    ('{st}Hello{/st} world', 'Hello world', 'Hi world', '{st}Hi{/st} world'),
    ('{r}Hello{/r}', 'Hello', '', '{r}{/r}'),
    ('{r}Hello{/r}', 'Hello', 'Hello there', '{r}Hello there{/r}'),
    ('A\n[---]\nB', 'A\nB', 'A\nC', 'A\n[---]\nC'),
    ('[C]Hello 😀', 'Hello 😀', 'Hello 🌏', '[C]Hello 🌏'),
    ('[hello]', '[hello]', '[hallo]', '[hallo]'),
    ('A &amp; B', 'A & B', 'A <b> & B', 'A &lt;b&gt; &amp; B'),
    ('{st}One\nTwo{/st}', 'One\nTwo', 'One\nNew\nTwo', '{st}One\nNew\nTwo{/st}'),
])
def test_replace_visible_lyrics(settings, source, before, after, expected):
    plain, spans = visible_text(source)
    assert plain == before
    assert replace_visible_text(source, spans, before, after) == expected


@pytest.mark.parametrize('source,selection,expected', [
    ('{st}Hello{/st} world', {'anchor': 0, 'position': 5}, (4, 9)),
    ('[C]Hello 😀', {'anchor': 8, 'position': 6}, (10, 9)),
    ('First\n{it}Second{/it}', {'anchor': 8, 'position': 3}, (12, 3)),
    ('A &amp; B', {'anchor': 2, 'position': 3}, (2, 7)),
    ('{st}Hello{/st}', {'anchor': 5, 'position': 5}, (9, 9)),
    ('', {'anchor': 0, 'position': 0}, (0, 0)),
    ('Hello', {'anchor': -1, 'position': 3}, None),
    ('Hello', {'anchor': 0, 'position': 6}, None),
    ('Hello', {'anchor': '0', 'position': 3}, None),
])
def test_source_selection(settings, source, selection, expected):
    assert source_selection(source, selection) == expected
