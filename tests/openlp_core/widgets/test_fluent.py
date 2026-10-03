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


def test_library_selector_clicks_overflow_and_accessibility(qapp):
    from PySide6 import QtTest
    from openlp.core.widgets.docks import MediaToolBox
    box = MediaToolBox()
    pages = []
    for label in ('Songs', 'Bibles', 'Presentations', 'Images', 'Media', 'Custom Slides'):
        page = QtWidgets.QWidget()
        pages.append(page)
        box.addItem(page, QtGui.QIcon(), label)
    box.show()
    for width in (160, 440, 1200, 250):
        box.resize(width, 400)
        qapp.process_events()
        selector = box._selector
        assert isinstance(selector, fluent.fluentqt.SelectorBar)
        for index in (5, 0, 5, 1, 0, 2, 3, 4, 5, 0):
            page = pages[index]
            if index in selector.hiddenItemIndexes():
                QtTest.QTest.mouseClick(selector, QtCore.Qt.MouseButton.LeftButton,
                                       pos=selector.overflowGeometry().center())
                qapp.process_events()
                action = next(action for action in box._overflow_menu.actions() if action.data() == index)
                menu = box._overflow_menu
                assert menu.rect().contains(menu.actionGeometry(action).center())
                # A short click must work immediately, without a preceding hover.
                position = menu.actionGeometry(action).center()
                QtTest.QTest.mouseClick(menu, QtCore.Qt.MouseButton.LeftButton, pos=position, delay=0)
                qapp.process_events()
            else:
                QtTest.QTest.mouseClick(selector, QtCore.Qt.MouseButton.LeftButton,
                                       pos=selector.itemGeometry(index).center())
            qapp.process_events()
            assert box.currentWidget() is page
            assert index in selector.visibleItemIndexes()
            interface = QtGui.QAccessible.queryAccessibleInterface(selector)
            centre = selector.mapToGlobal(selector.itemGeometry(index).center())
            child = interface.childAt(centre.x(), centre.y())
            assert child is not None and child.isValid()
    hidden_index = selector.hiddenItemIndexes()[-1]
    QtTest.QTest.mouseClick(selector, QtCore.Qt.MouseButton.LeftButton,
                           pos=selector.overflowGeometry().center())
    qapp.process_events()
    menu = box._overflow_menu
    menu.setActiveAction(None)
    for action in menu.actions():
        QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Down)
        if action.data() == hidden_index:
            break
    QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Return)
    qapp.process_events()
    assert box.currentIndex() == hidden_index
    box.close()


def test_library_overflow_short_clicks_trigger_once_and_respect_disabled(qapp):
    from PySide6 import QtTest
    from openlp.core.widgets.docks import FluentLibraryOverflowMenu
    menu = FluentLibraryOverflowMenu()
    first = menu.addAction('Songs')
    disabled = menu.addAction('Bibles')
    disabled.setEnabled(False)
    last = menu.addAction('Custom Slides')
    activated = []
    first.triggered.connect(lambda: activated.append('Songs'))
    disabled.triggered.connect(lambda: activated.append('Bibles'))
    last.triggered.connect(lambda: activated.append('Custom Slides'))
    for action in (last, first, last, disabled, first):
        menu.popup(QtCore.QPoint(40, 40))
        qapp.process_events()
        QtTest.QTest.mouseClick(menu, QtCore.Qt.MouseButton.LeftButton,
                               pos=menu.actionGeometry(action).center(), delay=0)
        qapp.process_events()
    assert activated == ['Custom Slides', 'Songs', 'Custom Slides', 'Songs']
    menu.popup(QtCore.QPoint(40, 40))
    qapp.process_events()
    QtTest.QTest.mousePress(menu, QtCore.Qt.MouseButton.LeftButton,
                           pos=menu.actionGeometry(first).center(), delay=0)
    QtTest.QTest.mouseRelease(menu, QtCore.Qt.MouseButton.LeftButton,
                             pos=menu.actionGeometry(last).center(), delay=0)
    assert activated == ['Custom Slides', 'Songs', 'Custom Slides', 'Songs']
    menu.close()


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



def test_commandbar_actions_keep_activation_state_and_overflow(qapp, qtbot):
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.resize(400, 200)
    parent.show()
    toolbar = OpenLPToolbar(parent)
    action = toolbar.add_toolbar_action('command', text='Run command', icon=QtGui.QIcon())
    fired = []
    action.triggered.connect(lambda: fired.append(True))
    toolbar.resize(400, 60)
    toolbar.show()
    QtWidgets.QApplication.processEvents()
    assert isinstance(toolbar._command_groups[0], fluent.fluentqt.CommandBar)
    assert toolbar._command_groups[0].primaryActions() == [action]
    qtbot.mouseClick(toolbar.widgetForAction(action), QtCore.Qt.MouseButton.LeftButton)
    assert fired == [True]
    action.setEnabled(False)
    assert not toolbar.widgetForAction(action).isEnabled()
    action.setEnabled(True)
    for index in range(5):
        toolbar.add_toolbar_action(str(index), text='Additional command ' + str(index))
    toolbar.resize(100, 60)
    QtWidgets.QApplication.processEvents()
    assert toolbar._command_groups[0].overflowedPrimaryActions()
    group = toolbar._command_groups[0]
    overflow_action = group.overflowedPrimaryActions()[0]
    overflow_fired = []
    overflow_action.triggered.connect(lambda: overflow_fired.append(True))
    group.setOverflowOpen(True)
    popup = toolbar.window().findChild(QtWidgets.QWidget, 'FluentCommandBar.OverflowPopup')
    qtbot.waitUntil(lambda: popup.testAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow))
    assert popup.isVisible()
    assert popup.parentWidget() is toolbar.window()
    rows = [widget for widget in popup.findChildren(QtWidgets.QWidget)
            if widget.objectName() == 'FluentCommandBar.OverflowRow']
    command = next(row for row in rows if row.property('commandAction') is overflow_action)
    qtbot.mouseClick(command, QtCore.Qt.MouseButton.LeftButton)
    assert overflow_fired == [True]
    qtbot.waitUntil(lambda: not group.isOverflowOpen())
    toolbar.close()


def test_commandbar_paints_disabled_icon_and_blocks_activation(qapp, qtbot):
    """Native primary and overflow commands must request the disabled icon mode."""
    parent = QtWidgets.QWidget()
    toolbar = OpenLPToolbar(parent)
    toolbar.setGeometry(0, 0, 180, 60)
    icon = QtGui.QIcon()
    for mode, colour in ((QtGui.QIcon.Mode.Normal, '#e60000'), (QtGui.QIcon.Mode.Disabled, '#0033ee')):
        pixmap = QtGui.QPixmap(20, 20)
        pixmap.fill(QtGui.QColor(colour))
        icon.addPixmap(pixmap, mode)
    action = toolbar.add_toolbar_action('disabled_rendering', text='Disabled rendering', icon=icon)
    fired = []
    action.triggered.connect(lambda: fired.append(True))
    parent.show()
    qtbot.wait(50)

    def pixels(widget, colour):
        image = widget.grab().toImage()
        return sum(image.pixelColor(x, y).name() == colour
                   for y in range(image.height()) for x in range(image.width()))

    button = toolbar.widgetForAction(action)
    assert pixels(button, '#e60000') >= 100
    action.setEnabled(False)
    assert not button.isEnabled()
    assert pixels(button, '#0033ee') >= 100
    assert pixels(button, '#e60000') == 0
    qtbot.mouseClick(button, QtCore.Qt.MouseButton.LeftButton)
    assert fired == []
    group = toolbar._command_groups[0]
    for index in range(5):
        toolbar.add_toolbar_action(str(index), text='Overflow command ' + str(index))
    toolbar.resize(60, 60)
    QtWidgets.QApplication.processEvents()
    assert group.isPrimaryActionOverflowed(action)
    group.setOverflowOpen(True)
    qtbot.wait(200)
    overflow = next(widget for widget in QtWidgets.QApplication.allWidgets()
                    if widget.isVisible() and widget.property('commandAction') is action)
    assert not overflow.isEnabled()
    assert pixels(overflow, '#0033ee') >= 100
    assert pixels(overflow, '#e60000') == 0
    group.setOverflowOpen(False)
    parent.close()


def test_commandbar_split_commands_stay_grouped_at_wide_and_narrow_widths(qapp):
    parent = QtWidgets.QWidget()
    toolbar = OpenLPToolbar(parent)
    new = toolbar.add_toolbar_action('new', text='New', icon=QtGui.QIcon())
    opened = toolbar.add_split_action('open', text='Open', icon=QtGui.QIcon())
    save = toolbar.add_toolbar_action('save', text='Save', icon=QtGui.QIcon())
    for width in (900, 400):
        toolbar.resize(width, toolbar.sizeHint().height())
        toolbar.show()
        qapp.process_events()
        new_button = toolbar.widgetForAction(new)
        open_button = toolbar.widgetForAction(opened)
        save_button = toolbar.widgetForAction(save)
        new_right = new_button.mapTo(toolbar, new_button.rect().topRight()).x()
        save_left = save_button.mapTo(toolbar, save_button.rect().topLeft()).x()
        assert 0 < open_button.x() - new_right < 24
        assert 0 < save_left - open_button.geometry().right() < 24
        assert open_button.height() == new_button.height() == save_button.height()
        assert open_button.fluentStyle() == fluent.fluentqt.Button.ButtonStyle.Subtle
    toolbar.close()


def test_commandbar_expanding_input_uses_spare_width(qapp):
    parent = QtWidgets.QWidget()
    toolbar = OpenLPToolbar(parent)
    toolbar.add_toolbar_action('play', text='Play')
    slider = fluent.QSlider()
    slider.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    wrapper = toolbar.addWidget(slider)
    toolbar.resize(800, 60)
    toolbar.show()
    qapp.process_events()
    assert slider.width() > 600
    wrapper.setVisible(False)
    qapp.process_events()
    assert toolbar._command_groups[0].width() <= toolbar._command_groups[0].sizeHint().width()
    toolbar.close()
