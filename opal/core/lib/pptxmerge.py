"""Copy original PowerPoint slides and their OPC dependency graphs into an export."""
from copy import deepcopy
from functools import cached_property
from io import BytesIO
from pathlib import PurePosixPath
import posixpath
from urllib.parse import unquote
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree


P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'


def _xml(blob):
    return etree.fromstring(blob, parser=etree.XMLParser(resolve_entities=False, no_network=True))


def _serialise(element):
    return etree.tostring(element, xml_declaration=True, encoding='UTF-8', standalone=True)


def _rels_name(part):
    path = PurePosixPath(part)
    return str(path.parent / '_rels' / (path.name + '.rels'))


def _target(part, target):
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), unquote(target))).lstrip('/')


class PptxSource:
    """Read native slide order and dimensions independently of cached thumbnails."""

    def __init__(self, path):
        self.path = path
        try:
            with ZipFile(path) as archive:
                manifest = {name: archive.read(name) for name in
                            ('ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels', '[Content_Types].xml')}
            self._read_manifest(manifest)
        except (KeyError, TypeError, ValueError, etree.XMLSyntaxError) as error:
            raise ValueError(f'Unable to read the PowerPoint presentation {path}: {error}') from error

    @cached_property
    def parts(self):
        # Read large media payloads only when the export writer needs them, off the GUI thread.
        with ZipFile(self.path) as archive:
            return {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}

    def _read_manifest(self, manifest):
        self.presentation = _xml(manifest['ppt/presentation.xml'])
        self.relationships = _xml(manifest['ppt/_rels/presentation.xml.rels'])
        targets = {rel.get('Id'): _target('ppt/presentation.xml', rel.get('Target'))
                   for rel in self.relationships if rel.get('TargetMode') != 'External'}
        self.slides = [targets[slide.get(f'{{{R}}}id')]
                       for slide in self.presentation.findall(f'{{{P}}}sldIdLst/{{{P}}}sldId')]
        size = self.presentation.find(f'{{{P}}}sldSz')
        if size is None:
            raise ValueError('The presentation has no slide dimensions')
        self.size = int(size.get('cx')), int(size.get('cy'))
        if min(self.size) <= 0:
            raise ValueError('The slide dimensions must be positive')
        content_types = _xml(manifest['[Content_Types].xml'])
        self.defaults = {entry.get('Extension'): entry.get('ContentType')
                         for entry in content_types.findall(f'{{{CT}}}Default')}
        self.overrides = {entry.get('PartName').lstrip('/'): entry.get('ContentType')
                          for entry in content_types.findall(f'{{{CT}}}Override')}

    def content_type(self, part):
        content_type = self.overrides.get(part) or self.defaults.get(part.rsplit('.', 1)[-1])
        if not content_type:
            raise ValueError(f'The source PowerPoint presentation has no content type for: {part}')
        return content_type


class PptxSlideImporter:
    """Preserve slide XML, relationships and original assets, including cyclic dependencies.

    Each occurrence of a service presentation gets its own mapping so internal slide links
    stay within that occurrence. Relationship IDs within copied parts remain unchanged.
    """

    def __init__(self, generated):
        with ZipFile(BytesIO(generated)) as archive:
            self.parts = {name: archive.read(name) for name in archive.namelist()}
        self.presentation = _xml(self.parts['ppt/presentation.xml'])
        self.relationships = _xml(self.parts['ppt/_rels/presentation.xml.rels'])
        self.content_types = _xml(self.parts['[Content_Types].xml'])
        self.overrides = {entry.get('PartName'): entry for entry in self.content_types
                          if entry.tag == f'{{{CT}}}Override'}
        size = self.presentation.find(f'{{{P}}}sldSz')
        self.size = int(size.get('cx')), int(size.get('cy'))
        targets = {rel.get('Id'): _target('ppt/presentation.xml', rel.get('Target'))
                   for rel in self.relationships}
        self.slides = [targets[slide.get(f'{{{R}}}id')]
                       for slide in self.presentation.findall(f'{{{P}}}sldIdLst/{{{P}}}sldId')]
        # Master and layout identifiers share a presentation-wide identifier space.
        ids = [int(node.get('id')) for node in self.presentation.findall(f'{{{P}}}sldMasterIdLst/{{{P}}}sldMasterId')]
        for name, blob in self.parts.items():
            if name.startswith('ppt/slideMasters/') and name.endswith('.xml'):
                layouts = _xml(blob).findall(f'{{{P}}}sldLayoutIdLst/{{{P}}}sldLayoutId')
                ids.extend(int(node.get('id')) for node in layouts)
        self.master_id = max(ids + [2147483647])

    def _next_master_id(self):
        self.master_id += 1
        return str(self.master_id)

    def _relate(self, target, kind):
        ids = {rel.get('Id') for rel in self.relationships}
        index = 1
        while f'rId{index}' in ids:
            index += 1
        rid = f'rId{index}'
        etree.SubElement(self.relationships, f'{{{REL}}}Relationship',
                         Id=rid, Type=R + '/' + kind, Target=posixpath.relpath(target, 'ppt'))
        return rid

    def _register_master(self, target, kind):
        tag, child_tag = (('sldMasterIdLst', 'sldMasterId') if kind == 'slideMaster'
                          else ('notesMasterIdLst', 'notesMasterId'))
        listing = self.presentation.find(f'{{{P}}}{tag}')
        if listing is not None and kind == 'notesMaster':
            return
        if listing is None:
            listing = etree.Element(f'{{{P}}}{tag}')
            position = 0 if kind == 'slideMaster' else 1
            self.presentation.insert(position, listing)
        child = etree.SubElement(listing, f'{{{P}}}{child_tag}')
        if kind == 'slideMaster':
            child.set('id', self._next_master_id())
        child.set(f'{{{R}}}id', self._relate(target, kind))

    def import_slides(self, source, indices, occurrence):
        """Import (source index, output index) pairs without flattening any slide content."""
        mapping = {source.slides[src]: self.slides[dest] for src, dest in indices}
        copied = set()

        def copy_part(part):
            if part not in mapping:
                mapping[part] = f'ppt/imported{occurrence}/{part}'
            target = mapping[part]
            if part in copied:
                return target
            copied.add(part)
            content_type = source.content_type(part)
            if part not in source.parts:
                raise ValueError(f'The source PowerPoint presentation is missing a required part: {part}')
            self.parts[target] = source.parts[part]
            override = self.overrides.get('/' + target)
            if override is None:
                override = etree.SubElement(self.content_types, f'{{{CT}}}Override', PartName='/' + target)
                self.overrides['/' + target] = override
            override.set('ContentType', content_type)
            if source.size != self.size and content_type.endswith(('.slide+xml', '.slideLayout+xml',
                                                                   '.slideMaster+xml', '.theme+xml')):
                self.parts[target] = _scale_xml(self.parts[target], source.size, self.size)
            rel_name = _rels_name(part)
            target_rels = _rels_name(target)
            if rel_name in source.parts:
                relationships = _xml(source.parts[rel_name])
                for rel in relationships:
                    if rel.get('TargetMode') != 'External':
                        dependency = copy_part(_target(part, rel.get('Target')))
                        rel.set('Target', posixpath.relpath(dependency, posixpath.dirname(target)))
                self.parts[target_rels] = _serialise(relationships)
            else:
                self.parts.pop(target_rels, None)
            if content_type.endswith('.slideMaster+xml'):
                master = _xml(self.parts[target])
                for layout in master.findall(f'{{{P}}}sldLayoutIdLst/{{{P}}}sldLayoutId'):
                    layout.set('id', self._next_master_id())
                self.parts[target] = _serialise(master)
                self._register_master(target, 'slideMaster')
            elif content_type.endswith('.notesMaster+xml'):
                self._register_master(target, 'notesMaster')
            return target

        for source_index, _ in indices:
            copy_part(source.slides[source_index])
        # Embedded fonts belong to the presentation rather than to individual slides.
        source_fonts = source.presentation.find(f'{{{P}}}embeddedFontLst')
        if source_fonts is not None:
            fonts = self.presentation.find(f'{{{P}}}embeddedFontLst')
            if fonts is None:
                fonts = etree.Element(f'{{{P}}}embeddedFontLst')
                successor = next((node for node in self.presentation if etree.QName(node).localname in
                                  ('custShowLst', 'photoAlbum', 'custDataLst', 'kinsoku',
                                   'defaultTextStyle', 'modifyVerifier', 'extLst')), None)
                if successor is None:
                    self.presentation.append(fonts)
                else:
                    successor.addprevious(fonts)
            relations = {rel.get('Id'): rel for rel in source.relationships}
            for font in source_fonts:
                clone = deepcopy(font)
                for node in clone.iter():
                    rid = node.get(f'{{{R}}}id')
                    if rid:
                        part = copy_part(_target('ppt/presentation.xml', relations[rid].get('Target')))
                        node.set(f'{{{R}}}id', self._relate(part, 'font'))
                fonts.append(clone)

    def save(self, destination):
        self.parts['ppt/presentation.xml'] = _serialise(self.presentation)
        self.parts['ppt/_rels/presentation.xml.rels'] = _serialise(self.relationships)
        self.parts['[Content_Types].xml'] = _serialise(self.content_types)
        with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
            for name, blob in self.parts.items():
                archive.writestr(name, blob)


def _scale_xml(blob, source_size, target_size):
    """Fit editable DrawingML content from another slide size onto the export canvas."""
    root = _xml(blob)
    scale = min(target_size[0] / source_size[0], target_size[1] / source_size[1])
    offsets = ((target_size[0] - source_size[0] * scale) / 2,
               (target_size[1] - source_size[1] * scale) / 2)
    for node in root.iter():
        name = etree.QName(node).localname
        namespace = etree.QName(node).namespace
        if namespace != A:
            continue
        if name in ('off', 'chOff', 'ext', 'chExt') and etree.QName(node.getparent()).localname == 'xfrm':
            owner = node.getparent().getparent()
            if etree.QName(owner).localname in ('spPr', 'grpSpPr'):
                owner = owner.getparent()
            if owner.tag == f'{{{P}}}spTree':
                continue
            for attr in ('x', 'y', 'cx', 'cy'):
                if node.get(attr) is not None:
                    node.set(attr, str(round(int(node.get(attr)) * scale)))
            # Nested groups scale their own coordinate system; centre only top-level shapes.
            if name == 'off' and owner.getparent().tag == f'{{{P}}}spTree':
                for attr, offset in zip(('x', 'y'), offsets):
                    node.set(attr, str(round(int(node.get(attr, '0')) + offset)))
        for attr in ('sz', 'marL', 'marR', 'indent', 'lIns', 'rIns', 'tIns', 'bIns'):
            if node.get(attr) is not None:
                node.set(attr, str(round(int(node.get(attr)) * scale)))
        if name in ('gridCol', 'tr', 'ln', 'spcPts'):
            attr = {'gridCol': 'w', 'tr': 'h', 'ln': 'w', 'spcPts': 'val'}[name]
            if node.get(attr) is not None:
                node.set(attr, str(round(int(node.get(attr)) * scale)))
    return _serialise(root)
