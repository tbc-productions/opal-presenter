"""Package-level checks for editable presentation export."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from PySide6 import QtGui

from openlp.core.common.enum import ServiceItemType
from openlp.core.display import render as render_module
from openlp.core.lib.formattingtags import FormattingTags
from openlp.core.lib.presentationexport import PresentationPage, _styled_lines, _write_odp, _write_pptx, \
    service_pages, _base_text_style
from openlp.core.ui.servicemanager import ServiceManager
from openlp.core.widgets.dialogs import FileDialog
from tests.openlp_core.ui.test_mainwindow import main_window_reduced as _main_window_reduced


presentation_main_window = _main_window_reduced


def _theme():
    values = dict(background_type='solid', background_color='#123456',
                  display_vertical_align=1, display_horizontal_align=2,
                  display_vertical_align_footer=0, display_horizontal_align_footer=0)
    for part, y, size in (('main', 80, 40), ('footer', 680, 12)):
        values.update({f'font_{part}_x': 20, f'font_{part}_y': y,
                       f'font_{part}_width': 984, f'font_{part}_height': 70,
                       f'font_{part}_name': 'Arial', f'font_{part}_size': size,
                       f'font_{part}_color': '#ffffff', f'font_{part}_bold': False,
                       f'font_{part}_italics': False})
    return SimpleNamespace(**values)


def test_pptx_has_editable_text_and_theme_geometry(tmp_path):
    from pptx import Presentation

    target = tmp_path / 'service.pptx'
    _write_pptx([PresentationPage(theme=_theme(), text='First line\nSecond line', footer='Credits')],
                target, 1024, 768)
    presentation = Presentation(str(target))
    assert len(presentation.slides) == 1
    assert [shape.text for shape in presentation.slides[0].shapes] == ['First line\nSecond line', 'Credits']
    assert presentation.slides[0].shapes[0].text_frame.paragraphs[0].runs[0].font.name == 'Arial'


def test_odp_has_editable_text_and_master_page(tmp_path):
    target = tmp_path / 'service.odp'
    _write_odp([PresentationPage(theme=_theme(), text='Lyrics', footer='Credits')], target, 1024, 768)
    with ZipFile(target) as package:
        content = package.read('content.xml').decode('utf-8')
        styles = package.read('styles.xml').decode('utf-8')
        assert 'Lyrics' in content
        assert 'Credits' in content
        assert 'OpenLPMaster0' in content
        assert 'OpenLPMaster0' in styles


def test_service_pages_end_each_section_with_logo():
    theme = _theme()

    def item(title, lines):
        return SimpleNamespace(
            service_item_type=ServiceItemType.Text, title=title,
            get_theme_data=lambda: theme,
            rendered_slides=[{'text': '<strong>' + line + '</strong>',
                              'footer': '<b>Credits</b>'} for line in lines],
            display_slides=[{'text': line} for line in lines])

    pages = service_pages([item('First', ['Verse one', 'Verse two']),
                           item('Second', ['Another'])], insert_logo=True)
    assert [page.text for page in pages] == ['Verse one', 'Verse two', '', 'Another', '']
    assert [page.logo for page in pages] == [False, False, True, False, True]
    assert [page.section_name for page in pages] == ['First'] * 3 + ['Second'] * 2
    assert [page.section_index for page in pages] == [0, 0, 0, 1, 1]
    assert pages[0].footer == 'Credits'
    assert pages[0].html_text == '<strong>Verse one</strong>'


def test_service_sections_are_exported_to_pptx_and_odp(tmp_path, monkeypatch):
    from lxml import etree

    theme = _theme()

    def item(title):
        return SimpleNamespace(service_item_type=ServiceItemType.Text, title=title,
                               get_theme_data=lambda: theme,
                               rendered_slides=[{'text': title, 'footer': ''}],
                               display_slides=[{'text': title}])

    monkeypatch.setattr('openlp.core.lib.presentationexport._background',
                        lambda theme, width, height, logo: ('#000000', None))
    pages = service_pages([item('Pre-Service'), item('How Great Thou Art'),
                           item('How Great Thou Art')], insert_logo=True)
    pptx = tmp_path / 'sections.pptx'
    odp = tmp_path / 'sections.odp'
    _write_pptx(pages, pptx, 1024, 768)
    _write_odp(pages, odp, 1024, 768)

    pptx_ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
               'p14': 'http://schemas.microsoft.com/office/powerpoint/2010/main'}
    with ZipFile(pptx) as package:
        root = etree.fromstring(package.read('ppt/presentation.xml'))
    slide_ids = root.xpath('./p:sldIdLst/p:sldId/@id', namespaces=pptx_ns)
    sections = root.xpath('./p:extLst/p:ext/p14:sectionLst/p14:section', namespaces=pptx_ns)
    assert [section.get('name') for section in sections] == [
        'Pre-Service', 'How Great Thou Art', 'How Great Thou Art']
    assert [[slide_id.get('id') for slide_id in section.xpath(
        './p14:sldIdLst/p14:sldId', namespaces=pptx_ns)]
            for section in sections] == [slide_ids[0:2], slide_ids[2:4], slide_ids[4:6]]
    assert len({section.get('id') for section in sections}) == 3

    odp_ns = {'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
              'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
              'loext': 'urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0'}
    with ZipFile(odp) as package:
        root = etree.fromstring(package.read('content.xml'))
    slide_names = root.xpath('./office:body/office:presentation/draw:page/@draw:name', namespaces=odp_ns)
    sections = root.xpath('./office:body/office:presentation/loext:section-list/loext:section',
                          namespaces=odp_ns)
    assert [section.get(f'{{{odp_ns["loext"]}}}name') for section in sections] == [
        'Pre-Service', 'How Great Thou Art', 'How Great Thou Art']
    assert [[slide.get(f'{{{odp_ns["loext"]}}}name') for slide in section]
            for section in sections] == [slide_names[0:2], slide_names[2:4], slide_names[4:6]]


def test_logo_slide_is_packaged_in_both_formats(tmp_path, monkeypatch):
    from pptx import Presentation

    logo = tmp_path / 'logo.png'
    image = QtGui.QImage(16, 16, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('#ff0000'))
    assert image.save(str(logo))
    settings = SimpleNamespace(value=lambda key: {
        'core/logo background color': '#000000',
        'core/logo file': logo,
        'core/logo fit': 'contain'}[key])
    monkeypatch.setattr('openlp.core.lib.presentationexport.Registry',
                        lambda: SimpleNamespace(get=lambda key: settings))
    pages = [PresentationPage(theme=_theme(), text='First'), PresentationPage(logo=True),
             PresentationPage(theme=_theme(), text='Second')]
    pptx = tmp_path / 'with-logo.pptx'
    odp = tmp_path / 'with-logo.odp'
    _write_pptx(pages, pptx, 1024, 768)
    _write_odp(pages, odp, 1024, 768)
    assert len(Presentation(str(pptx)).slides) == 3
    with ZipFile(odp) as package:
        assert package.read('content.xml').count(b'draw:page ') == 3
        assert any(name.startswith('Pictures/') for name in package.namelist())


def test_formatting_tags_become_editable_runs_in_both_formats(tmp_path):
    from pptx import Presentation

    markup = ('<strong>Bold</strong> '
              '<span style="-webkit-text-fill-color:red">Red</span><br>'
              '<span style="font-size:150%; font-family:Georgia; text-decoration:underline">Large</span>'
              '<sup>2</sup>')
    page = PresentationPage(theme=_theme(), text='Bold Red\nLarge2', html_text=markup,
                            footer='Credits', html_footer='<span style="color:blue">Credits</span>')
    lines = _styled_lines(markup, _base_text_style(page.theme, 'main'))
    assert [[value for value, _ in line] for line in lines] == [['Bold', ' ', 'Red'], ['Large', '2']]
    pptx = tmp_path / 'formatted.pptx'
    odp = tmp_path / 'formatted.odp'
    _write_pptx([page], pptx, 1024, 768)
    _write_odp([page], odp, 1024, 768)
    shapes = Presentation(str(pptx)).slides[0].shapes
    paragraphs = shapes[0].text_frame.paragraphs
    assert paragraphs[0].runs[0].font.bold
    assert paragraphs[0].runs[2].font.color.rgb == (255, 0, 0)
    assert paragraphs[1].runs[0].font.name == 'Georgia'
    assert paragraphs[1].runs[0].font.underline
    assert paragraphs[1].runs[0].font.size > paragraphs[0].runs[0].font.size
    assert paragraphs[1].runs[1]._r.get_or_add_rPr().get('baseline') == '30000'
    assert shapes[1].text_frame.paragraphs[0].runs[0].font.color.rgb == (0, 0, 255)
    with ZipFile(odp) as package:
        content = package.read('content.xml').decode('utf-8')
        assert 'font-family="Georgia"' in content
        assert 'text-underline-style="solid"' in content
        assert 'color="#ff0000"' in content
        assert 'text-position="super 58%"' in content


def test_openlp_and_custom_formatting_tags_are_expanded(monkeypatch):
    tags = [
        {'start tag': '{st}', 'end tag': '{/st}', 'start html': '<strong>', 'end html': '</strong>'},
        {'start tag': '{r}', 'end tag': '{/r}',
         'start html': '<span style="-webkit-text-fill-color:red">', 'end html': '</span>'},
        {'start tag': '{large}', 'end tag': '{/large}',
         'start html': '<span style="font-size:150%; font-family:Georgia">', 'end html': '</span>'},
    ]
    monkeypatch.setattr(FormattingTags, 'get_html_tags', lambda: tags)
    monkeypatch.setattr(render_module, 'remove_chords', lambda value: value)
    markup = render_module.render_tags('{st}Bold{/st} {r}Red{/r} {large}Large{/large}')
    runs = _styled_lines(markup, _base_text_style(_theme(), 'main'))[0]
    assert runs[0][1].bold
    assert runs[2][1].color == '#ff0000'
    assert runs[4][1].family == 'Georgia'
    assert runs[4][1].size == 60


def test_presentation_metadata_identifies_openlp(tmp_path):
    from pptx import Presentation

    page = PresentationPage(theme=_theme(), text='Lyrics')
    pptx = tmp_path / 'Sunday.pptx'
    odp = tmp_path / 'Sunday.odp'
    _write_pptx([page], pptx, 1024, 768)
    _write_odp([page], odp, 1024, 768)
    properties = Presentation(str(pptx)).core_properties
    assert properties.title == 'Sunday'
    assert properties.comments == 'Exported from OpenLP+'
    assert properties.author == 'OpenLP+'
    assert properties.last_modified_by == 'OpenLP+'
    with ZipFile(pptx) as package:
        assert b'generated using python-pptx' not in package.read('docProps/core.xml')
    with ZipFile(odp) as package:
        metadata = package.read('meta.xml')
        assert b'Exported from OpenLP+' in metadata


def test_presentation_filename_matches_saved_service():
    manager = SimpleNamespace(file_name=lambda: Path('/services/Sunday Evening.oszl'))
    assert ServiceManager.suggested_presentation_file_path(manager, '.pptx') == \
        Path('/services/Sunday Evening.pptx')


def test_presentation_filename_uses_service_name_pattern(monkeypatch, tmp_path):
    class FixedDatetime:
        @staticmethod
        def now():
            return datetime(2026, 9, 23, 10, 0)

    monkeypatch.setattr('openlp.core.ui.servicemanager.datetime', FixedDatetime)
    values = {'advanced/default service enabled': True,
              'advanced/default service day': 7,
              'advanced/default service name': 'Service %Y-%m-%d %H-%M',
              'servicemanager/last directory': tmp_path}
    manager = SimpleNamespace(file_name=lambda: None,
                              settings=SimpleNamespace(value=lambda key: values[key]))
    manager._default_service_file_path = lambda: ServiceManager._default_service_file_path(manager)
    assert ServiceManager.suggested_presentation_file_path(manager, '.odp') == \
        tmp_path / 'Service 2026-09-23 10-00.odp'


def test_presentation_filename_without_default_name_uses_service_label(tmp_path):
    values = {'advanced/default service enabled': False,
              'servicemanager/last directory': tmp_path}
    manager = SimpleNamespace(file_name=lambda: None,
                              settings=SimpleNamespace(value=lambda key: values[key]))
    assert ServiceManager.suggested_presentation_file_path(manager, '.pptx') == tmp_path / 'Service.pptx'


def test_export_dialog_uses_requested_format_and_suggested_path(monkeypatch, tmp_path):
    from openlp.core.lib import presentationexport

    saved = []
    dialogs = []
    suggested = tmp_path / 'Service 2026-09-23.odp'

    def choose_file(*args):
        dialogs.append(args)
        return suggested, ''

    monkeypatch.setattr(FileDialog, 'getSaveFileName', choose_file)
    monkeypatch.setattr(presentationexport, 'export_presentation',
                        lambda items, path, insert_logo: saved.append((path, insert_logo)))
    presentationexport.export_items_dialog(None, [SimpleNamespace(title='Song')], '.odp', suggested)
    assert saved == [(suggested, False)]
    assert dialogs[0][2] == suggested
    assert dialogs[0][3] == 'OpenDocument Presentation (*.odp)'


def test_export_menu_has_separate_presentation_formats(request):
    main_window = request.getfixturevalue('presentation_main_window')
    menu = main_window.export_presentation_menu
    assert menu.title() == '&Presentation'
    assert [action.text() for action in menu.actions()] == ['PowerPoint (pptx)', 'OpenDocument (odp)']
    assert menu.menuAction() in main_window.file_export_menu.actions()
    main_window.export_powerpoint_item.trigger()
    main_window.export_opendocument_item.trigger()
    calls = main_window.service_manager_contents.on_export_presentation.call_args_list
    assert [call.args[0] for call in calls] == ['.pptx', '.odp']
