"""Helpers for exporting an individual library item."""
import json
import zipfile
from contextlib import contextmanager
from shutil import copyfile
from pathlib import Path
from tempfile import NamedTemporaryFile

from openlp.core.widgets import fluent as QtWidgets

from openlp.core.common import clean_filename
from openlp.core.common.i18n import translate
from openlp.core.common.json import OpenLPJSONEncoder
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
def export_archive(path):
    """Replace the destination only after all referenced media has been written."""
    with NamedTemporaryFile(dir=path.parent, suffix='.osz', delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            yield archive
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_item_service(path, service_item, xml=None, xml_name='item.xml'):
    """Package a text item in a service that OpenLP+ can reopen."""
    service = [
        {'openlp_core': {'lite-service': False, 'service-theme': '', 'openlp-servicefile-version': 3}},
        {'serviceitem': service_item.get_service_repr(False)},
    ]
    with export_archive(path) as archive:
        archive.writestr('service_data.osj', json.dumps(service, cls=OpenLPJSONEncoder))
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
    element = root.find('{https://openlp.org/ns/slide-design/1}design')
    return normalise_design(element.text if element is not None else None)


def write_xml_package(path, xml, service_item=None):
    """Write plain XML or a portable XML/media archive, according to the chosen extension."""
    from openlp.core.lib.designmedia import media_references, resolve_media, write_media
    design = xml_design(xml)
    if path.suffix.lower() == '.osz':
        if service_item is not None:
            write_item_service(path, service_item, xml, 'song.xml')
        else:
            with export_archive(path) as archive:
                archive.writestr('song.xml', xml)
                write_media(archive, design)
    else:
        for reference in media_references(design):
            destination = path.parent / reference
            destination.parent.mkdir(parents=True, exist_ok=True)
            copyfile(resolve_media(reference), destination)
        path.write_bytes(xml.encode('utf-8') if isinstance(xml, str) else xml)
