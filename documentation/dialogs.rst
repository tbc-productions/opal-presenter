Dialog design pattern
=====================

Construct operator UI through ``opal.core.widgets.fluent``. Its shared dialog
adapters keep native Fluent presentation, same-window modal behaviour and the
existing Qt result contracts. Do not construct ``fluentqt.ContentDialog`` or
native Qt message/input dialogs directly in application code.

Choosing a surface
------------------

Use ``ContentDialog`` for a compact prompt, confirmation or short selection.
Use ``FormDialog`` when a form already has a QDialogButtonBox, validation in
``accept()`` or custom button handlers. Put the form's root layout on
``dialog.content_widget``, not on the dialog itself. ``create_button_box()``
registers it automatically; manually built boxes need ``setButtonBox(box)``.

Keep larger editors, Settings, About, browser/media previews and multi-step
wizards on their existing specialised surfaces. The shared ``QDialog`` adapter
adds a visible heading from ``setWindowTitle()``. System file and print pickers
retain their platform implementation.

Actions and wording
-------------------

For prompts and forms, the primary action is on the left, secondary in the
middle and Cancel or Close on the right. Wizards use the navigation order
described below. If the footer cannot fit these captions in a row, stack the
actions in primary, secondary, Cancel/Close order with their full captions visible.
Return to a row when the host is wide enough. The default action changes keyboard
activation and accent emphasis, not position. Destructive confirmations default
to Cancel.
Use concrete verbs: Save, Rename, Copy, Create, Select, Apply, Export or Delete.
Use Discard consistently for abandoning unsaved changes. Instructions must
match the visible button caption; avoid references to an old OK/Yes label.

FormDialog maps AcceptRole/YesRole to primary, ApplyRole to the next available
action, HelpRole/DestructiveRole to secondary and RejectRole/NoRole to close.
For two affirmative commands, use AcceptRole for the main action and ApplyRole
for the alternative, as in Planning Center's Import New/Refresh Service pair.
Additional utility commands stay in the form body.

Validation and results
----------------------

FormDialog forwards native footer clicks through the original button box.
Keep existing validation, error handling and clicked/accepted/rejected handlers;
do not connect another unconditional ``accept()`` or ``done()`` to the same
action. Failed validation and Help keep the form open. A cancelled confirmation
must also leave its parent form open and avoid writes.

ContentDialog uses ResultPrimary, ResultSecondary and ResultNone. FormDialog
retains QDialog's Accepted/Rejected contract through the original handlers.
The QMessageBox adapter retains its StandardButton results.

For required text, disable the primary button for empty or whitespace-only
values, and trim the accepted value. Enter goes through the checked default
button; do not connect ``returnPressed`` directly to ``done()``. Field updates
such as ``editingFinished`` must run before saving. Destructive copy must
describe exactly which records will be deleted, including inclusive dates.

Presentation and accessibility
------------------------------

Use the native title slot for the heading. Use FontRole.Body for explanatory
paragraphs and enable word wrapping; routine field labels use Caption.
Associate labels with fields via ``setBuddy()`` and provide accessible names
when a field has no visible label. Related controls need distinct labels;
date ranges use two compact CalendarDatePicker fields labelled From and To.
Omit trailing colons from control labels. Centre single-line labels vertically
beside their fields and match input height to adjacent command buttons. Keep
labels for multiline editors aligned with the top of their content.

The adapters preserve ContentDialog's native padding, give fields at least
32 px height, disable the problematic opacity effect on macOS and constrain
the surface to its host. Expand the dialog to fit its content before scrolling.
Only scroll when the content cannot fit within the available host space and
the dialog's width limit; keep footer actions visible. Recalculate when the host
is resized, expanding and removing scrollbars when the content fits again.
Content is measured again after native fonts and scrollbar geometry settle.
Floating workspace panes are temporarily hidden while a prompt occupies
the main window, then restored without changing their saved dock placement.
Do not add outer padding a second time or cap height before layout measurement.
Normal compact dialogs start at 420 px wide and cap at 560 px. A form needing
wider controls can explicitly raise its maximum width (the media time grid does
this); it still fits its host and can scroll when the host is smaller. Footer
width also accounts for the longest button caption. In form layouts, prefer
AllNonFixedFieldsGrow so Fluent controls with Preferred size policies fill their
fields. ContentDialog forms wrap labels above fields when a row cannot fit.
Avoid fixed widths on descriptive text.
Wrap user-supplied names displayed as text, including Bible translation and
unmatched book names. Remeasure open dialogs when their body changes. Confirmation
lists grow to show their items; the dialog body scrolls when the host is too small.

Read accepted values before calling ``deleteLater()`` on temporary dialogs.
Content ownership follows FluentQt: replacing or taking content detaches it;
installed content is destroyed with its dialog.

Verification
------------

Inspect rendered light/dark dialogs for clipping, extra gaps and button order.
Standalone visual probes must call ``fluentqt.initialize_resources()`` as the
application does, so icons and typography render correctly.
Exercise Enter, Escape, disabled actions, failed validation, Help and cancelled
confirmations. Check long messages and a resized host: content must remain
reachable and footer commands visible. The main regression suite is
``tests/openlp_core/widgets/test_fluent_dialogs.py``; form-specific tests cover
validation, song-usage deletion boundaries and network field updates.

Wizard presentation
-------------------

Keep multi-step workflows on ``QtWidgets.QWizard`` and ``QtWidgets.QWizardPage``
from ``opal.core.widgets.fluent``. The shared adapters retain Qt's page IDs,
registered fields, completion checks, validation and result contracts. Set page
headings with ``setTitle()`` and instructions with ``setSubTitle()``; these use
Fluent Title and Body typography with a step caption rather than Qt's banner.
Page headings, step captions and short subtitles remain visible above the
scrolling body. Put long instructions in the body. Footer actions remain
visible. Use an initial size rather than a fixed window size.

Place Cancel at the far left and group Back and Next (or Commit/Finish) at
the bottom right. Next, Commit and Finish retain their accent style and default
keyboard action. Custom actions follow Cancel on the left. Enable optional actions
through the corresponding wizard options so unused buttons remain hidden.
Existing welcome pages use the same typography without decorative side images.
Cloud Library retains its provider-specific step count and validation. Operator
dialogs and wizards do not expose Help buttons or links to OpenLP's manual.
Settings tooltips continue to explain fields locally. Validation prompts belong
to the active wizard and disable its navigation until dismissed.

First-time setup configures plugins and displays locally and can restore a
settings backup or copy an existing data folder into a separate Opal library.
The final import page defaults to None, with no import cards. Opal Presenter shows
Library and Settings only cards; OpenLP shows only Library. Each card contains its
folder or backup picker. Shared radio buttons make the Opal imports mutually
exclusive, with Library selected initially. Only the selected card's input and
browse button are enabled. Finish setup requires an existing folder for Library
or an existing file for Settings only; None allows setup to finish immediately.
Hidden and unselected fields are
ignored. The plugin and display choices
made in the wizard take priority over an imported settings backup. A successful
import shows a confirmation before setup closes; failed imports show a ContentDialog
and leave setup open for corrections.
Library import copies songs, Bibles, custom slides, themes, designer assets and
stored image, media and presentation files, preserving both the original and
current libraries. Close the source application before importing. Linked external
files are copied into the imported library, including image and song audio
references and theme backgrounds. Settings-only imports copy linked media and
presentation files into current Opal storage without
switching libraries. Missing files stop the import. Settings backups use the separate field
on the same page. Failed copies are removed and leave setup open. On re-running
setup, the data folder switches only after plugins close, and the application
requests a restart through its normal save
and close flow. It does not contact OpenLP servers or download songs, Bibles,
themes, thumbnails or the web remote. Built-in themes are installed from local
files on first startup. Re-running setup preserves the current theme unless a
settings backup changes it. Opal Presenter is independent and is not endorsed by OpenLP.

The Bible import wizard refreshes translation lists only on request and disables
sources whose lists cannot be retrieved, marking them with `` - unavailable``.
Before advancing with a web translation,
it uses that source's existing extractors to retrieve its book list and the first
chapter of its first book, requiring non-empty verse text. Failed checks keep the
source page open and allow retrying or choosing a local Bible file. This is a
current sample check; it cannot guarantee every chapter or future availability.
Web Bibles still retrieve uncached chapters on demand. Translation refreshes and
web Bible imports use indeterminate progress rings; local imports retain their
progress bars. Network waits keep GUI animations running, with clicks deferred
until the request completes.

Wizard regressions are covered by ``tests/openlp_core/widgets/test_wizard.py``,
``tests/openlp_core/ui/test_firsttimeform.py`` and the Bible and Cloud Library
wizard tests. Check light/dark rendering, long instructions, narrow windows,
Enter/Escape, mouse clicks, failed validation and Help.
