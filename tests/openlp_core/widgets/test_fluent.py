"""Native Fluent adapters retain OpenLP action and item-model semantics."""
from PySide6 import QtCore, QtGui, QtWidgets
from openlp.core.widgets import fluent
from openlp.core.widgets.toolbar import OpenLPToolbar


def test_integer_numberbox_signal_and_unavailable_font(qapp):
    box = fluent.QSpinBox()
    changed = []
    box.valueChanged.connect(lambda value: changed.append((value, type(value))))
    box._field.setValue(1.5)
    assert changed == [(2, int)]
    assert box.value() == 2
    fonts = fluent.QFontComboBox()
    fonts.setCurrentFont(QtGui.QFont('OpenLP missing test font'))
    assert fonts.currentFont().family() == 'OpenLP missing test font'


def test_list_filter_controls_visible_fluent_rows(qapp):
    view = fluent.QListWidget()
    item = fluent.QListWidgetItem('Song', view)
    item.setHidden(True)
    assert view.isRowHidden(0)
    item.setHidden(False)
    assert not view.isRowHidden(0)


def test_toolbar_separator_and_removed_action_lifetime(qapp):
    parent = QtWidgets.QWidget()
    toolbar = OpenLPToolbar(parent)
    toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
    action = toolbar.add_toolbar_action('test', text='Test')
    assert toolbar.widgetForAction(action).fluentLayout() == fluent.fluentqt.Button.ButtonLayout.TextOnly
    separator = toolbar.add_toolbar_action('separator', separator=True)
    assert separator.isSeparator()
    assert separator in toolbar.actions()
    toolbar.removeAction(action)
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    action.setText('Updated after removal')


def test_unchecked_group_disables_new_children_and_restores_them(qapp):
    group = fluent.QGroupBox('Outline')
    group.setCheckable(True)
    group.setChecked(False)
    child = fluent.QLineEdit(group)
    assert not child.isEnabled()
    group.setCheckable(False)
    assert child.isEnabled()


def test_icon_buttons_and_large_menu_keep_bounded_geometry(qapp):
    button = fluent.QToolButton()
    button.setText('A long command name retained for accessibility')
    assert button.sizeHint().width() <= 48
    menu = fluent.QMenu()
    for index in range(100):
        menu.addAction('Language ' + str(index))
    assert menu.sizeHint().width() < 400
    assert menu.minimumWidth() < 400


def test_native_tabs_switch_pages_and_progress_tracks_busy_state(qapp):
    tabs = fluent.QTabWidget()
    first, second = QtWidgets.QWidget(), QtWidgets.QWidget()
    tabs.addTab(first, 'First')
    tabs.addTab(second, 'Second')
    tabs.setCurrentIndex(1)
    assert tabs.currentWidget() is second
    progress = fluent.QProgressBar()
    progress.setRange(0, 0)
    assert progress._bar.isIndeterminate()
    progress.setRange(0, 10)
    progress.setValue(4)
    assert not progress._bar.isIndeterminate()
    assert progress.text() == '40%'


def test_dialog_buttons_added_incrementally_keep_standard_roles(qapp):
    box = fluent.QDialogButtonBox()
    save = box.addButton(box.StandardButton.Save)
    assert isinstance(save, fluent.fluentqt.Button)
    assert box.button(box.StandardButton.Save) is save
    accepted = []
    box.accepted.connect(lambda: accepted.append(True))
    save.click()
    assert accepted == [True]
    box.removeButton(save)
    assert box.button(box.StandardButton.Save) is None


def test_message_box_native_commands_keep_default_and_escape_results(qapp):
    from PySide6 import QtTest
    for key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Escape):
        box = fluent.QMessageBox(fluent.QMessageBox.Icon.Question, 'Question', 'Continue?',
                                 fluent.QMessageBox.StandardButton.Yes | fluent.QMessageBox.StandardButton.No)
        box.setDefaultButton(box.StandardButton.No)
        finished = []
        box.finished.connect(finished.append)
        QtCore.QTimer.singleShot(0, lambda box=box, key=key: QtTest.QTest.keyClick(box, key))
        assert box.exec() == box.StandardButton.No
        assert box.result() == box.StandardButton.No
        assert finished == [box.StandardButton.No]
        assert isinstance(box.button(box.StandardButton.No), fluent.fluentqt.Button)


def test_message_box_custom_button_retains_identity(qapp):
    box = fluent.QMessageBox()
    box.setText('Choose')
    button = box.addButton('Keep existing', box.ButtonRole.AcceptRole)
    QtCore.QTimer.singleShot(0, button.click)
    box.exec()
    assert box.clickedButton() is button
    box.setStandardButtons(box.StandardButton.Ok)
    assert box.button(box.StandardButton.Ok) is not None


def test_adapters_use_safe_accessibility_interfaces(qapp):
    """Qt must not select native interfaces by a misleading adapter class name."""
    factories = [fluent.QTabBar, fluent.QTabWidget, fluent.QToolButton, fluent.QSplitButton,
                 fluent.QSpinBox, fluent.QGroupBox, fluent.QProgressBar, fluent.QTimeEdit,
                 fluent.QCalendarWidget, fluent.QFontComboBox, fluent.QListWidget,
                 fluent.QTreeWidget, fluent.QTableWidget]
    for factory in factories:
        widget = factory()
        assert widget.metaObject().className().startswith('Fluent')
        interface = QtGui.QAccessible.queryAccessibleInterface(widget)
        assert interface is not None
        assert interface.isValid()
        # QTabBar/QToolButton names previously selected an incompatible native
        # interface and segfaulted when macOS queried its children or actions.
        for index in range(interface.childCount()):
            child = interface.child(index)
            if child is not None:
                assert child.isValid()
        interface.actionInterface()
        widget.deleteLater()


def test_library_tab_clicks_and_accessibility_after_reflow(qapp):
    """Both rows remain accessible while actual Fluent button clicks switch pages."""
    from PySide6 import QtTest
    from openlp.core.widgets.docks import MediaToolBox
    box = MediaToolBox()
    pages = []
    for label in ('Songs', 'Bibles', 'Presentations', 'Images', 'Media', 'Custom Slides'):
        page = QtWidgets.QWidget()
        pages.append(page)
        box.addItem(page, QtGui.QIcon(), label)
    box.resize(250, 400)
    box.show()
    qapp.process_events()
    for width in (250, 1200, 250):
        box.resize(width, 400)
        qapp.process_events()
        for index, page in enumerate(pages):
            row = box._top_tab_bar if index < box._top_count else box._bottom_tab_bar
            row_index = index + 1 if row is box._top_tab_bar else index - box._top_count + 1
            button = row._items[row_index]['button']
            QtTest.QTest.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
            qapp.process_events()
            assert box.currentWidget() is page
            interface = QtGui.QAccessible.queryAccessibleInterface(row)
            assert interface.childCount() > 0
            centre = button.mapToGlobal(button.rect().center())
            child = interface.childAt(centre.x(), centre.y())
            assert child is not None and child.isValid()
    box.close()


def test_flat_lists_are_native_datagrids_with_optional_headers(qapp):
    """Column headings must be visible without changing item/selection indexes."""
    view = fluent.QListWidget()
    assert isinstance(view, fluent.fluentqt.DataGrid)
    assert not isinstance(view, fluent.fluentqt.ListView)
    assert view.horizontalHeader().isHidden()
    view.setHeaderLabel('Title')
    item = fluent.QListWidgetItem('Example', view)
    view.setCurrentRow(0)
    assert view.currentItem() is item
    header = view.horizontalHeader()
    assert not header.isHidden()
    assert header.model().headerData(0, QtCore.Qt.Orientation.Horizontal) == 'Title'
    view.clear()
    fluent.QListWidgetItem('Replacement', view)
    assert header.model().headerData(0, QtCore.Qt.Orientation.Horizontal) == 'Title'


def test_song_datagrid_headers_sorting_and_row_selection(qapp):
    from openlp.plugins.songs.lib.mediaitem import SongListWidget
    view = SongListWidget()
    assert isinstance(view, fluent.fluentqt.DataGrid)
    assert not view.header().isHidden()
    view.addTopLevelItem(view.make_item('Zebra', 'Alpha', 1))
    view.addTopLevelItem(view.make_item('Apple', 'Zulu', 2))
    view.header().setSortIndicator(1, QtCore.Qt.SortOrder.AscendingOrder)
    assert view.topLevelItem(0).text() == 'Zebra'
    view.set_secondary_header('Topic')
    assert view.model().headerData(1, QtCore.Qt.Orientation.Horizontal) == 'Topic'
    item = view.topLevelItem(1)
    view.setCurrentItem(item)
    assert view.selectedItems() == [item]


def test_hierarchy_column_labels_restore_visible_header(qapp):
    view = fluent.QTreeWidget()
    view.setColumnCount(3)
    view.setHeaderLabels(['Action', 'Shortcut', 'Alternate'])
    assert not view.header().isHidden()
    assert view.model().headerData(1, QtCore.Qt.Orientation.Horizontal) == 'Shortcut'


def test_library_columns_retain_standard_font_and_treeview(qapp):
    from openlp.core.widgets.views import TreeWidgetWithDnD
    from openlp.plugins.songs.lib.mediaitem import SongListWidget
    tree = TreeWidgetWithDnD()
    standard_tree_font = tree.font()
    for _ in range(2):
        tree.setup_columns(['Name', 'Date'])
        assert tree.font() == standard_tree_font
    assert isinstance(tree, fluent.fluentqt.TreeView)
    songs = SongListWidget()
    assert songs.font() == fluent.fluentqt.font_for_role(fluent.fluentqt.FontRole.Body)


def test_preview_live_slide_list_is_native_datagrid(settings):
    from openlp.core.widgets.views import ListPreviewWidget
    parent = QtWidgets.QWidget()
    view = ListPreviewWidget(parent, 16 / 9)
    assert isinstance(view, fluent.fluentqt.DataGrid)
    view.setRowCount(1)
    item = QtWidgets.QTableWidgetItem('Verse 1')
    view.setItem(0, 0, item)
    view.setCurrentCell(0, 0)
    assert view.currentRow() == 0
    assert view.item(0, 0) is item
    assert view.horizontalHeader().isHidden()


def test_application_menus_use_native_mac_widgets(qapp, monkeypatch):
    """macOS application menus must not use the custom Fluent menu painter."""
    parent = QtWidgets.QMainWindow()
    monkeypatch.setattr(fluent, 'is_macosx', lambda: True)
    bar = fluent.create_application_menu_bar(parent)
    menu = fluent.create_application_menu(bar)
    submenu = fluent.create_application_menu(menu)
    assert type(bar) is QtWidgets.QMenuBar
    assert type(menu) is QtWidgets.QMenu
    assert type(submenu) is QtWidgets.QMenu
    # In-window context/dropdown menus retain native Fluent controls.
    assert isinstance(fluent.QMenu(), fluent.fluentqt.FluentMenu)
    monkeypatch.setattr(fluent, 'is_macosx', lambda: False)
    assert isinstance(fluent.create_application_menu_bar(parent), fluent.fluentqt.FluentMenuBar)
    assert isinstance(fluent.create_application_menu(parent), fluent.fluentqt.FluentMenu)


def test_file_libraries_keep_native_tree_appearance(qapp):
    from openlp.core.widgets.views import TreeWidgetWithDnD
    for name in ('presentations', 'images', 'media'):
        view = TreeWidgetWithDnD(name=name)
        native = fluent.fluentqt.TreeView()
        view.setup_columns(['Name', 'Date', 'Type'])
        assert view.indentation() == native.indentation()
        assert view.rootIsDecorated() == native.rootIsDecorated()
        assert view.isAnimated() == native.isAnimated()
        assert view.selectionIndicatorVisible()
        assert not view.alternatingRowColors()
        assert view.styleSheet() == ''
        assert view.header().isHidden()
        assert view.isColumnHidden(1) and view.isColumnHidden(2)
        folder = fluent.QTreeWidgetItem(view, ['Folder'])
        child = fluent.QTreeWidgetItem(folder, ['File'])
        folder.setExpanded(True)
        assert view.isExpanded(view._item_store.indexFromItem(folder))
        assert child.parent() is folder


def test_file_tree_chevron_click_expands_and_row_click_selects(qapp, qtbot):
    from openlp.core.widgets.views import TreeWidgetWithDnD
    view = TreeWidgetWithDnD(name='images')
    view.setup_columns(['Name'])
    folder = fluent.QTreeWidgetItem(view, ['Folder'])
    child = fluent.QTreeWidgetItem(folder, ['Image'])
    view.resize(320, 180)
    view.show()
    QtWidgets.QApplication.processEvents()
    index = view._item_store.indexFromItem(folder)
    rect = view.visualRect(index)
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=QtCore.QPoint(rect.left() + 22, rect.center().y()))
    qtbot.waitUntil(lambda: view.isExpanded(index))
    qtbot.wait(250)
    child_index = view._item_store.indexFromItem(child)
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=view.visualRect(child_index).center())
    assert view.selectionModel().isSelected(child_index)
    assert view.selectedIndicatorRect().isValid()
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton,
                     pos=QtCore.QPoint(rect.left() + 22, rect.center().y()))
    qtbot.waitUntil(lambda: not view.isExpanded(index))
    view.close()
