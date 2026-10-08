"""Qt mnemonic labels stay readable in native Fluent painters."""
from PySide6 import QtGui, QtWidgets
from openlp.core.widgets import fluent


def test_command_mnemonics_and_literal_ampersands(qapp):
    button = fluent.QPushButton('&Add')
    assert button.text() == 'Add'
    assert button.shortcut() == QtGui.QKeySequence.mnemonic('&Add')
    assert fluent.QPushButton('Save && Preview').text() == 'Save & Preview'
    button.setText('Save && Preview')
    assert button.text() == 'Save & Preview'
    assert button.shortcut().isEmpty()
    for factory in (fluent.QToolButton, fluent.QSplitButton):
        action = QtGui.QAction('Ed&it All')
        control = factory()
        control.setDefaultAction(action)
        assert control.text() == 'Edit All'
        assert control.shortcut() == QtGui.QKeySequence.mnemonic('Ed&it All')
        action.setText('Rock && Roll')
        assert control.text() == 'Rock & Roll'
        assert control.shortcut().isEmpty()


def test_tab_labels_decode_ampersands_after_updates_and_removal(qapp):
    tabs = fluent.QTabWidget()
    tabs.addTab(QtWidgets.QWidget(), 'Title && Lyrics')
    tabs.addTab(QtWidgets.QWidget(), '&Audio')
    assert tabs._tabs.tabAt(0).text == 'Title & Lyrics'
    assert tabs._tabs.tabAt(1).text == 'Audio'
    tabs.setTabText(1, 'Authors && Topics')
    tabs.removeTab(0)
    assert tabs.tabText(0) == 'Authors && Topics'
    assert tabs._tabs.tabAt(0).text == 'Authors & Topics'
    tabs.setTabPosition(tabs.TabPosition.West)
    assert tabs._rail_buttons[0].text() == 'Authors & Topics'

    bar = fluent.QTabBar()
    bar.addTab('&First && Second')
    assert bar._tabs.tabAt(0).text == 'First & Second'
    bar.setTabText(0, 'Theme && Copyright')
    bar.setTabEnabled(0, False)
    assert bar._tabs.tabAt(0).text == 'Theme & Copyright'


def test_verse_rows_fit_visible_lyrics_on_first_show(qapp, qtbot, settings):
    """Loading a hidden editor must not reserve space for narrow, wrapped lyrics."""
    from openlp.core.ui import SingleColumnTableWidget
    from openlp.core.widgets.edits import FormattingTagDelegate

    widget = SingleColumnTableWidget(None)
    qtbot.addWidget(widget)
    widget.setItemDelegate(FormattingTagDelegate(widget))
    widget.resize(800, 500)
    widget.setRowCount(1)
    lyrics = ('Now there is grace awaiting me, awaiting me\n' * 5).rstrip('\n')
    widget.setItem(0, 0, QtWidgets.QTableWidgetItem(lyrics))
    widget.resizeRowsToContents()
    widget.show()
    QtWidgets.QApplication.processEvents()

    delegate = widget.itemDelegate()
    document = delegate._build_text_document(widget.font(), lyrics,
                                             widget.columnWidth(0) - 2 * delegate.HORIZONTAL_PADDING)
    padded_height = int(document.size().height()) + 2 * delegate.VERTICAL_PADDING
    assert abs(widget.rowHeight(0) - padded_height) <= 1
    assert widget.columnWidth(0) == widget.viewport().width()

    widget.resize(300, 500)
    QtWidgets.QApplication.processEvents()
    assert widget.rowHeight(0) > padded_height


def test_selection_control_mnemonics(qapp):
    for factory in (fluent.QCheckBox, fluent.QRadioButton):
        control = factory('F&ull screen')
        assert control.text() == 'Full screen'
        assert control.shortcut() == QtGui.QKeySequence.mnemonic('F&ull screen')
        control.setText('Custom &geometry')
        assert control.text() == 'Custom geometry'
        assert control.shortcut() == QtGui.QKeySequence.mnemonic('Custom &geometry')
        control.setText('Rock && Roll')
        assert control.text() == 'Rock & Roll'
        assert control.shortcut().isEmpty()
    group = fluent.QGroupBox('Theme && &Copyright')
    group.setCheckable(True)
    assert group.title() == 'Theme & Copyright'
    assert group._toggle.text() == 'Theme & Copyright'
    assert group._toggle.shortcut() == QtGui.QKeySequence.mnemonic('Theme && &Copyright')


def test_routine_labels_use_caption_but_context_menus_use_body(qapp, qtbot):
    role = fluent.fluentqt.FontRole
    label = fluent.QLabel('Search:')
    qtbot.addWidget(label)
    assert label.font() == fluent.fluentqt.font_for_role(role.Caption)
    heading = fluent.QLabel('Service item', fluentTypography=role.BodyStrong)
    qtbot.addWidget(heading)
    assert heading.font() == fluent.fluentqt.font_for_role(role.BodyStrong)
    menu = fluent.QMenu(label)
    menu.addAction('Inspect item')
    assert menu.font() == fluent.fluentqt.font_for_role(role.Body)
