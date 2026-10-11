"""Generated slides are owned by the library, including duplicate-looking slides."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from openlp.plugins.images.lib.db import Base, Folder, Item
from openlp.plugins.images.lib.mediaitem import ImageMediaItem


@pytest.mark.parametrize('folder_kind', ['none', 'existing', 'new'])
def test_generated_images_survive_source_cleanup_and_keep_names(tmp_path, folder_kind):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        folder = None if folder_kind == 'none' else Folder(name='Welcome slides')
        if folder_kind == 'existing':
            session.add(folder)
            session.commit()

        def save(items):
            session.add_all(items)
            session.commit()
            return True

        library = SimpleNamespace(settings_section='images', manager=SimpleNamespace(save_objects=save),
                                  _insert_saved_items=MagicMock())
        source = tmp_path / 'Welcome.png'
        source.write_bytes(b'identical image bytes')
        with patch('openlp.plugins.images.lib.mediaitem.AppLocation.get_section_data_path', return_value=tmp_path):
            # Identical content is intentional; numbering represents the slide sequence.
            ImageMediaItem.add_generated_images(library, [(source, 'Welcome.png'), (source, 'Welcome (2).png')], folder)
            ImageMediaItem.add_generated_images(library, [(source, 'Welcome.png')], folder)
        source.unlink()
        items = session.query(Item).order_by(Item.id).all()
        assert [item.name for item in items] == ['Welcome.png', 'Welcome (2).png', 'Welcome.png']
        assert len({item.file_path for item in items}) == 3
        assert all(Path(item.file_path).read_bytes() == b'identical image bytes' for item in items)
        assert all(item.folder_id == (folder.id if folder else None) for item in items)
        assert session.query(Folder).count() == (1 if folder else 0)
        assert library._insert_saved_items.call_count == 2


def test_database_failure_removes_generated_files(tmp_path):
    source = tmp_path / 'Welcome.png'
    source.write_bytes(b'image')
    library = SimpleNamespace(settings_section='images', manager=MagicMock(), _insert_saved_items=MagicMock())
    library.manager.save_objects.return_value = False
    with patch('openlp.plugins.images.lib.mediaitem.AppLocation.get_section_data_path', return_value=tmp_path):
        with pytest.raises(OSError, match='save the images'):
            ImageMediaItem.add_generated_images(library, [(source, 'Welcome.png')])
    assert list((tmp_path / 'library').iterdir()) == []
    assert source.exists()
    library._insert_saved_items.assert_not_called()
