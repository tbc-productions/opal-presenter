"""Service sets retain image content and each custom slide's own design."""
import json
import base64
from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtGui

from openlp.core.common.enum import ServiceItemType
from openlp.core.lib import ItemCapabilities
from openlp.core.lib.mediamanageritem import MediaManagerItem
from openlp.core.lib.serviceitem import ServiceItem
from openlp.core.lib.theme import Theme, TransitionSpeed, TransitionType
from openlp.core.ui.serviceitemeditform import ServiceItemEditForm
from openlp.core.ui.servicemanager import ServiceManager
from openlp.core.widgets import fluent as QtWidgets


@pytest.fixture
def set_env(settings, registry, state):
    with patch('openlp.core.lib.theme.ScreenList') as theme_screens, \
            patch('openlp.core.lib.slidedesign.ScreenList') as design_screens, \
            patch('openlp.core.lib.slideset.ScreenList') as set_screens:
        for screens in (theme_screens, design_screens, set_screens):
            screens.return_value.current.display_geometry = QtCore.QRect(0, 0, 1920, 1080)
        theme = Theme()
        theme.background_type = 'solid'
        manager = MagicMock()
        manager.get_theme_data.return_value = theme
        registry.register('theme_manager', manager)
        renderer = MagicMock()
        renderer.format_slide.side_effect = lambda text, item: text.split('[---]')
        registry.register('renderer', renderer)
        yield renderer


def custom(text='Welcome', title='Custom', design=None):
    item = ServiceItem()
    item.name = 'custom'
    item.title = title
    item.slide_design = design or {}
    item.raw_footer = [f'{title} credits']
    item.add_from_text(text)
    return item


def image(tmp_path):
    path = tmp_path / 'welcome.png'
    picture = QtGui.QImage(80, 45, QtGui.QImage.Format.Format_RGB32)
    picture.fill(QtGui.QColor('red'))
    picture.save(str(path))
    item = ServiceItem()
    item.name = 'images'
    item.title = 'Announcements'
    item.add_from_image(path, 'Welcome image')
    return item


@pytest.mark.parametrize('first', ['image', 'custom'])
@pytest.mark.parametrize('lite', [True, False])
def test_mixed_set_survives_save_load_without_original_image(set_env, tmp_path, first, lite):
    pictures, text = image(tmp_path), custom()
    original_image = (tmp_path / 'welcome.png').read_bytes()
    target, addition = (pictures, text) if first == 'image' else (text, pictures)
    original_title = target.title
    target.append_to_set([addition])
    saved = json.loads(json.dumps({'serviceitem': target.get_service_repr(lite)}))
    (tmp_path / 'welcome.png').unlink()
    restored = ServiceItem()
    restored.set_from_service(saved, None if lite else tmp_path, version=3)

    assert restored.title == original_title
    assert restored.is_slide_set and restored.is_text() and restored.is_valid
    assert not restored.uses_file()
    assert [slide['title'] for slide in restored.slides] == [slide['title'] for slide in target.slides]
    assert restored.rendered_slides == target.rendered_slides
    image_frame = next(slide for slide in restored.rendered_slides if slide['theme']['background_type'] == 'image')
    assert image_frame['theme']['background_filename'].startswith('data:image/png;base64,')
    assert base64.b64decode(image_frame['theme']['background_filename'].split(',', 1)[1]) == original_image
    assert image_frame['footer'] == ''
    text_frame = next(slide for slide in restored.rendered_slides if slide['text'])
    assert text_frame['text'] == 'Welcome' and text_frame['footer'] == 'Custom credits'


def test_custom_only_set_keeps_design_assignments_and_split_footers(set_env):
    first = custom('First')
    second = custom('Second[---]More', design={
        'version': 1, 'lyrics': {'font_size': 60},
        'hidden_footers': ['custom-1:0:1'],
        'masters': {'large': {'name': 'Large', 'design': {'version': 1, 'lyrics': {'font_size': 90}}}},
        'assignments': {'custom-1:0:0': 'large'}
    })
    before = deepcopy(second.slides), deepcopy(second.slide_design)
    first.append_to_set([second])
    frames = first.rendered_slides

    assert [slide['text'] for slide in frames] == ['First', 'Second', 'More']
    assert [slide['verse'] for slide in frames] == [0, 1, 2]
    assert frames[1]['theme']['font_main_size'] == 90
    assert frames[2]['theme']['font_main_size'] == 60
    assert frames[2]['footer'] == ''
    assert (second.slides, second.slide_design) == before
    assert first.is_capable(ItemCapabilities.CanMaintain)
    assert not first.is_capable(ItemCapabilities.CanEdit)


def test_reordering_retains_original_custom_slide_design_key(set_env):
    source = custom('First', design={
        'version': 1, 'lyrics': {'font_size': 40},
        'hidden_footers': ['custom-2:0:0']
    })
    source.add_from_text('Second')
    source.append_to_set([custom('Last')])
    source.slides.reverse()
    source._clear_slides_cache()

    assert [frame['text'] for frame in source.rendered_slides] == ['Last', 'Second', 'First']
    assert source.rendered_slides[1]['footer'] == ''
    assert source.rendered_slides[2]['footer'] == 'Custom credits'


def test_failed_image_conversion_does_not_mutate_target(set_env, tmp_path):
    target = custom()
    bad = image(tmp_path)
    (tmp_path / 'welcome.png').unlink()
    before = deepcopy(target.slides)
    with pytest.raises((OSError, ValueError)):
        target.append_to_set([bad])
    assert target.slides == before
    assert not target.is_slide_set
    assert target.name == 'custom'


def test_only_image_and_custom_library_items_can_form_sets(set_env):
    target = custom()
    assert target.can_append_plugin('images')
    assert target.can_append_plugin('custom')
    assert not target.can_append_plugin('songs')
    presentation = ServiceItem()
    presentation.name = 'presentations'
    presentation.service_item_type = ServiceItemType.Image
    assert not presentation.can_append_plugin('custom')


def test_adding_more_images_to_an_existing_mixed_set(set_env, tmp_path):
    target = image(tmp_path)
    target.append_to_set([custom('Welcome')])
    target.append_to_set([image(tmp_path), custom('Goodbye')])
    assert target.title == 'Announcements'
    assert [slide['text'] for slide in target.display_slides] == [
        'Welcome image', 'Welcome', 'Welcome image', 'Goodbye'
    ]


@pytest.mark.parametrize('plugin', ['images', 'custom'])
def test_library_add_to_selected_item_builds_a_mixed_set(set_env, registry, tmp_path, plugin):
    target = image(tmp_path) if plugin == 'custom' else custom()
    additions = [custom('First'), custom('Second')] if plugin == 'custom' else [image(tmp_path)]
    manager = MagicMock()
    manager.find_service_item.return_value = (0, -1)
    manager.get_service_item.return_value = target
    registry.register('service_manager', manager)
    with patch.object(MediaManagerItem, '_setup'):
        library = MediaManagerItem(None, MagicMock())
    library.plugin.name = plugin
    library.remote_triggered = False
    library.list_view = MagicMock()
    library.list_view.selectedItems.return_value = [MagicMock() for _ in additions]
    library.build_service_item = MagicMock(side_effect=additions)

    library.on_add_edit_click()

    assert target.is_slide_set
    assert len(target.slides) == len(additions) + 1
    manager.add_service_item.assert_called_once_with(target, replace=0)
    if plugin == 'custom':
        assert [slide['text'] for slide in target.slides[1:]] == ['First', 'Second']


def test_set_editor_reorders_and_deletes_both_slide_kinds(set_env, registry, tmp_path):
    registry.register('main_window', None)
    target = image(tmp_path)
    target.append_to_set([custom('First'), custom('Second')])
    original_frames = deepcopy(target.rendered_slides)
    form = ServiceItemEditForm()
    form.set_service_item(target)
    form.item_grid.selectRow(0)
    form.on_down_button_clicked()
    form.item_grid.selectRow(2)
    form.on_delete_button_clicked()
    edited = form.get_service_item()

    assert [slide['title'] for slide in edited.slides] == ['First', 'Welcome image']
    assert edited.rendered_slides[0]['theme'] == original_frames[1]['theme']
    assert edited.rendered_slides[1]['theme'] == original_frames[0]['theme']
    assert len(edited.print_slides) == 2
    assert edited.print_slides[1]['text'] == 'Welcome image'


@pytest.mark.parametrize('effect', [
    TransitionType.Fade, TransitionType.Slide, TransitionType.Convex, TransitionType.Concave, TransitionType.Zoom
])
def test_set_transitions_apply_to_all_slide_types_and_survive_save(set_env, tmp_path, effect):
    target = image(tmp_path)
    target.slide_transition_settings = {'enabled': True, 'type': effect, 'speed': TransitionSpeed.Fast}
    target.append_to_set([custom('First[---]Second')])
    assert ServiceManager._service_item_supports_transition(target)
    assert len(target.rendered_slides) == 3
    for slide in target.rendered_slides:
        assert slide['theme']['display_slide_transition'] is True
        assert slide['theme']['display_slide_transition_type'] == effect
        assert slide['theme']['display_slide_transition_speed'] == TransitionSpeed.Fast
    saved = json.loads(json.dumps({'serviceitem': target.get_service_repr(False)}))
    restored = ServiceItem()
    restored.set_from_service(saved, version=3)
    assert restored.rendered_slides == target.rendered_slides


def test_set_labels_are_local_and_remain_attached_after_reordering_and_save(set_env, registry, tmp_path):
    registry.register('main_window', None)
    target = image(tmp_path)
    target.append_to_set([custom('Projected words')])
    form = ServiceItemEditForm()
    form.set_service_item(target)
    form.item_grid.selectRow(1)
    with patch('openlp.core.ui.serviceitemeditform.RenameDialog.get_text',
               return_value=(' Sermon introduction ', True)):
        form.on_rename_button_clicked()
    assert target.slides[1]['title'] == 'Projected words'
    form.on_up_button_clicked()
    edited = form.get_service_item()
    assert edited.slides[0]['title'] == 'Sermon introduction'
    assert edited.rendered_slides[0]['text'] == 'Projected words'
    assert edited.rendered_slides[0]['footer'] == 'Custom credits'
    saved = json.loads(json.dumps({'serviceitem': edited.get_service_repr(False)}))
    restored = ServiceItem()
    restored.set_from_service(saved, version=3)
    assert restored.display_slides[0]['title'] == 'Sermon introduction'
    assert restored.is_capable(ItemCapabilities.HasDisplayTitle)


@pytest.fixture
def set_manager(set_env, registry):
    registry.register('main_window', MagicMock())
    registry.register('live_controller', MagicMock())
    registry.register('preview_controller', MagicMock())
    registry.register('plugin_manager', MagicMock())
    manager = ServiceManager()
    manager.find_service_item = MagicMock(return_value=(0, -1))
    manager.repaint_service_list = MagicMock()
    manager.set_modified = MagicMock()
    return manager


@pytest.mark.parametrize('enabled', [True, False])
def test_transition_dialog_refreshes_already_rendered_set(set_manager, set_env, tmp_path, enabled):
    target = image(tmp_path)
    target.append_to_set([custom()])
    target.slide_transition_settings = {'enabled': not enabled, 'type': TransitionType.Zoom,
                                        'speed': TransitionSpeed.Normal}
    original = deepcopy(target.rendered_slides)
    set_manager.service_items = [{'service_item': target}]

    def accept(dialog):
        choices = dialog.findChildren(QtWidgets.QComboBox)
        choices[0].setCurrentIndex(choices[0].findData(TransitionType.Slide) if enabled else 0)
        choices[1].setCurrentIndex(choices[1].findData(TransitionSpeed.Slow))
        return QtWidgets.QDialog.DialogCode.Accepted

    with patch('openlp.core.ui.servicemanager.QtWidgets.FormDialog.exec', accept):
        set_manager.on_service_item_transition_form()
    assert target.rendered_slides != original
    for frame in target.rendered_slides:
        assert frame['theme']['display_slide_transition'] is enabled
        if enabled:
            assert frame['theme']['display_slide_transition_type'] == TransitionType.Slide
            assert frame['theme']['display_slide_transition_speed'] == TransitionSpeed.Slow
    set_manager.preview_controller.replace_service_manager_item.assert_called_once_with(target, 0)
    set_manager.live_controller.replace_service_manager_item.assert_called_once_with(target, 0)
    set_manager.set_modified.assert_called_once_with()


def test_renaming_a_split_page_renames_its_source_slide(set_manager, set_env, tmp_path):
    target = image(tmp_path)
    target.append_to_set([custom('First[---]Second')])
    set_manager.service_items = [{'service_item': target}]
    set_manager.find_service_item.return_value = (0, 2)
    with patch('openlp.core.ui.servicemanager.RenameDialog.get_text',
               return_value=('New label', True)):
        set_manager.on_service_item_rename()
    assert target.title == 'Announcements'
    assert target.slides[1]['title'] == 'New label'
    assert [slide['title'] for slide in target.display_slides] == ['Welcome image', 'New label', 'New label']
    assert [slide['text'] for slide in target.rendered_slides] == ['', 'First', 'Second']


def test_set_thumbnails_survive_source_removal_and_follow_reordering(set_env, registry, tmp_path):
    from openlp.core.lib.slideset import set_thumbnail
    target = image(tmp_path)
    target.append_to_set([custom('Welcome[---]Second page')])
    (tmp_path / 'welcome.png').unlink()
    custom_preview = QtGui.QPixmap(248, 140)
    custom_preview.fill(QtGui.QColor('blue'))
    custom_preview.setDevicePixelRatio(2)
    set_env.generate_slide_preview.return_value = custom_preview
    picture = set_thumbnail(target, 0)
    assert picture.toImage().pixelColor(picture.width() // 2, picture.height() // 2) == QtGui.QColor('red')
    assert not set_thumbnail(target, 1).isNull()
    assert set_thumbnail(target, 1).devicePixelRatio() == 1
    assert not set_thumbnail(target, 2).isNull()
    assert set_env.generate_slide_preview.call_count == 2
    set_thumbnail(target, 1)
    assert set_env.generate_slide_preview.call_count == 2
    registry.register('main_window', None)
    form = ServiceItemEditForm()
    form.set_service_item(target)
    assert all(not form.item_grid.item(i, 0).icon().isNull() for i in range(2))
    form.item_grid.selectRow(1)
    form.on_up_button_clicked()
    assert form.item_grid.item(0, 0).icon().pixmap(124, 70).toImage().pixelColor(60, 30) == QtGui.QColor('blue')
    changed = form.get_service_item()
    assert changed._set_thumbnails == {}
    assert 'thumbnail' not in changed.slides[0]
    form.deleteLater()


def test_service_tree_uses_mixed_set_thumbnails(set_env, tmp_path):
    target = image(tmp_path)
    target.append_to_set([custom()])
    child = QtWidgets.QTreeWidgetItem()
    ServiceManager._set_child_thumbnail(None, child, target, target.display_slides[0])
    pixels = child.icon(0).pixmap(64, 48).toImage()
    assert pixels.pixelColor(32, 24) == QtGui.QColor('red')
