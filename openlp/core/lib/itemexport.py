"""Helpers for exporting an individual library item."""
import json
import zipfile
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import clean_filename
from openlp.core.common.i18n import translate
from openlp.core.common.json import OpenLPJSONEncoder
from openlp.core.lib.nativefile import design_element, write_manifest
from openlp.core.widgets.dialogs import FileDialog


def suggested_item_export_path(service_manager, title, suffix):
    """Name an export after its library item in the usual service directory."""
    directory = service_manager.suggested_presentation_file_path(suffix).parent
    filename = clean_filename(title).strip(' .') or translate('OpenLP.ItemExport', 'Item')
    return Path(directory) / f'{filename}{suffix}'


def export_item_dialog(parent, default_path, suffix, file_filter, writer):
    """Choose a native export file and report write errors."""
    path, _ = FileDialog.getSaveFileName(
        parent, translate('OpenLP.ItemExport', 'Export item'), default_path, file_filter)
    if not path:
        return
    if path.suffix.lower() != suffix:
        path = path.with_suffix(suffix)
    try:
        writer(path)
    except (OSError, ValueError, RuntimeError) as error:
        QtWidgets.QMessageBox.critical(parent, translate('OpenLP.ItemExport', 'Export failed'), str(error))


@contextmanager
def export_archive(path, file_type=None, payload=None):
    """Replace the destination only after all referenced media has been written."""
    with NamedTemporaryFile(dir=path.parent, suffix=path.suffix, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            if file_type:
                write_manifest(archive, file_type, payload)
            yield archive
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_item_service(path, service_item, xml=None, xml_name='item.xml'):
    """Package a text item in a service that Opal Presenter can reopen."""
    service = [
        {'openlp_core': {'lite-service': False, 'service-theme': '', 'openlp-servicefile-version': 3}},
        {'serviceitem': service_item.get_service_repr(False)},
    ]
    file_type = 'song' if path.suffix.lower() == '.opal-song' else 'slides'
    payload = xml_name if xml is not None else 'service.json'
    with export_archive(path, file_type, payload) as archive:
        archive.writestr('service.json', json.dumps(service, cls=OpenLPJSONEncoder))
        from openlp.core.lib.designmedia import write_media
        write_media(archive, service)
        if xml is not None:
            archive.writestr(xml_name, xml)
            write_media(archive, xml_design(xml))


def xml_design(xml):
    """Read the shared optional design extension without altering ordinary lyrics."""
    from lxml import etree
    from openlp.core.lib.slidedesign import normalise_design
    root = etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)
    element = design_element(root)
    return normalise_design(element.text if element is not None else None)


def write_xml_package(path, xml, service_item=None):
    """Write plain XML or a portable XML/media archive, according to the chosen extension."""
    from openlp.core.lib.designmedia import write_media
    design = xml_design(xml)
    if path.suffix.lower() in ('.opal-song', '.opal-slides'):
        if service_item is not None:
            write_item_service(path, service_item, xml, 'song.xml' if path.suffix.lower() == '.opal-song' else 'slides.xml')
        else:
            file_type = 'song' if path.suffix.lower() == '.opal-song' else 'slides'
            payload = file_type + '.xml'
            with export_archive(path, file_type, payload) as archive:
                archive.writestr(payload, xml)
                write_media(archive, design)
    else:
        # Plain OpenLyrics is an interchange export, so omit application-specific extensions.
        from lxml import etree
        root = etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)
        for child in list(root):
            if child.tag.startswith(('{urn:net.tbcproductions.OpalPresenter:', '{https://openlp.org/ns/')):
                root.remove(child)
        etree.cleanup_namespaces(root)
        xml = etree.tostring(root, encoding='utf-8', xml_declaration=True, pretty_print=True)
        temporary = None
        try:
            with NamedTemporaryFile(dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(xml)
            temporary.replace(path)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


def read_xml_package(path, file_type=None):
    """Validate song/slide metadata before retaining verified packaged media."""
    from lxml import etree
    from openlp.core.lib.nativefile import read_manifest
    from openlp.core.lib.designmedia import restore_media
    expected = {'.opal-song': 'song', '.opal-slides': 'slides'}.get(path.suffix.lower())
    if file_type and expected and expected != file_type:
        raise ValueError('The package extension does not match this importer.')
    file_type = file_type or expected
    limit = 8 * 1024 * 1024

    def parse(data):
        if len(data) > limit or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ValueError('The XML is unsafe or exceeds the supported size.')
        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                                 remove_blank_text=True, remove_pis=True)
        root = etree.fromstring(data, parser)
        kind = 'song' if root.tag == '{http://openlyrics.info/namespace/2009/song}song' else 'slides'
        if (file_type and kind != file_type or kind == 'slides' and
                (root.tag != 'song' or root.find('lyrics') is None)):
            raise ValueError('This package contains the wrong kind of XML document.')
        return root, etree.tostring(root, encoding='unicode')

    if path.suffix.lower() in ('.opal-song', '.opal-slides', '.osz'):
        with zipfile.ZipFile(path) as archive:
            manifest = read_manifest(archive, file_type or ('song', 'slides'),
                                     required=path.suffix.lower().startswith('.opal-'))
            members = archive.infolist()
            payloads = [manifest['payload']] if manifest else [member.filename for member in members
                                                              if member.filename.lower().endswith('.xml')]
            if len(payloads) != 1 or archive.getinfo(payloads[0]).file_size > limit:
                raise ValueError('The package must contain one small XML payload.')
            root, text = parse(archive.read(payloads[0]))
            restore_media(xml_design(text), archive=archive)
            return root, text
    if path.stat().st_size > limit:
        raise ValueError('The XML exceeds the supported size.')
    root, text = parse(path.read_bytes())
    restore_media(xml_design(text), directory=path.parent)
    return root, text
