"""Helpers for exporting an individual library item."""
import json
import zipfile
from pathlib import Path

from PySide6 import QtWidgets

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


def write_item_service(path, service_item):
    """Package a text item in a service that OpenLP+ can reopen."""
    service = [
        {'openlp_core': {'lite-service': False, 'service-theme': '', 'openlp-servicefile-version': 3}},
        {'serviceitem': service_item.get_service_repr(False)},
    ]
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('service_data.osj', json.dumps(service, cls=OpenLPJSONEncoder))
