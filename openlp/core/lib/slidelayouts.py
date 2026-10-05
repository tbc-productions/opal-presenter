"""Portable master layouts, slide assignments and non-destructive local overrides."""
import copy
import re

from openlp.core.lib.slidedesign import normalise_design


PAGE_KEY = re.compile(r'[a-z0-9-]+:[0-9]+:[0-9]+')
DOCUMENT_KEYS = {'masters', 'assignments', 'overrides', 'hidden_footers', 'custom_layout_name', 'default_layout'}


def visual_design(value):
    return normalise_design({key: item for key, item in value.items() if key not in DOCUMENT_KEYS}, False)


def normalise_layouts(value):
    result = {}
    if value.get('default_layout') == 'theme':
        result['default_layout'] = 'theme'
    name = value.get('custom_layout_name')
    if isinstance(name, str) and name.strip():
        result['custom_layout_name'] = name.strip()[:100]
    masters = {}
    source = value.get('masters', {})
    for identifier, master in list(source.items())[:100] if isinstance(source, dict) else []:
        if (not isinstance(identifier, str) or identifier in ('default', 'theme') or
                not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', identifier) or not isinstance(master, dict)):
            continue
        masters[identifier] = {'name': str(master.get('name', 'Layout'))[:100],
                               'design': visual_design(master.get('design', {})
                                                       if isinstance(master.get('design'), dict) else {})}
    if masters:
        result['masters'] = masters
    for key in ('assignments', 'overrides'):
        source = value.get(key, {})
        clean = {}
        for page, data in list(source.items())[:10000] if isinstance(source, dict) else []:
            if not isinstance(page, str) or not PAGE_KEY.fullmatch(page):
                continue
            if key == 'assignments':
                if isinstance(data, str) and data in ('default', 'theme', *masters):
                    clean[page] = data
            elif isinstance(data, dict):
                clean[page] = {part: visual_design(data.get(part, {}) if isinstance(data.get(part), dict) else {})
                               for part in ('base', 'design')}
        if clean:
            result[key] = clean
    return result


def master_design(document, identifier='default'):
    if identifier == 'theme':
        return {}
    if identifier == 'default':
        return visual_design(document)
    design = copy.deepcopy(document.get('masters', {}).get(identifier, {}).get('design', {}))
    if document.get('theme') and 'theme' not in design:
        design.update(version=1, theme=copy.deepcopy(document['theme']))
    return design


def _merge_changes(before, after, current):
    """Replay local changes onto an updated master, matching layers by their stable IDs."""
    result = copy.deepcopy(current)
    for key in before.keys() | after.keys():
        if key not in after:
            result.pop(key, None)
        elif key not in before:
            result[key] = copy.deepcopy(after[key])
        elif before[key] == after[key]:
            continue
        elif key == 'elements':
            old = {element['id']: element for element in before[key]}
            new = {element['id']: element for element in after[key]}
            now = {element['id']: element for element in current.get(key, [])}
            merged = _merge_changes(old, new, now)
            order = list(now) + [identifier for identifier in new if identifier not in now]
            result[key] = [merged[identifier] for identifier in order if identifier in merged]
        elif isinstance(before[key], dict) and isinstance(after[key], dict):
            result[key] = _merge_changes(before[key], after[key], current.get(key, {}))
        else:
            result[key] = copy.deepcopy(after[key])
    return result


def layout_for_slide(document, page):
    """New slides inherit the theme; retain legacy shared designs already saved on an item."""
    assigned = document.get('assignments', {}).get(page)
    if assigned is not None:
        return assigned
    if document.get('default_layout') == 'theme':
        return 'theme'
    return 'default' if visual_design(document) else 'theme'


def slide_design(document, page):
    master = master_design(document, layout_for_slide(document, page))
    override = document.get('overrides', {}).get(page)
    if override:
        master = normalise_design(_merge_changes(override['base'], override['design'], master), False)
    # An imported base theme belongs to the whole item, even when a layout has no local theme snapshot.
    if document.get('theme') and 'theme' not in master:
        master.update(version=1, theme=copy.deepcopy(document['theme']))
    return master


def set_slide_design(document, page, design):
    result = copy.deepcopy(document) or {'version': 1}
    base = master_design(document, layout_for_slide(document, page))
    design = visual_design(design)
    overrides = result.setdefault('overrides', {})
    if design == base:
        overrides.pop(page, None)
    else:
        overrides[page] = {'base': base, 'design': design}
    return normalise_design(result)
