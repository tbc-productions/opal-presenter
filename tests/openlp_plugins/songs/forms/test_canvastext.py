"""Source-preserving editing of paginated lyrics."""
import pytest

from openlp.plugins.slide_designer.forms.textediting import visible_text, replace_visible_text


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
