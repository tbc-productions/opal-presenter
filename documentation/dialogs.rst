Dialog design pattern
=====================

Construct operator UI through ``openlp.core.widgets.fluent``. Its shared dialog
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

The primary action is always on the left, secondary in the middle and Cancel
or Close on the right. The default action changes keyboard activation and
accent emphasis, not position. Destructive confirmations default to Cancel.
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

The adapters preserve ContentDialog's native padding, give fields at least
32 px height, disable the problematic opacity effect on macOS and constrain
the surface to its host. The body scrolls while footer actions remain visible.
Short content is measured again after native fonts and scrollbar geometry
settle. Floating workspace panes are temporarily hidden while a prompt occupies
the main window, then restored without changing their saved dock placement.
Do not add outer padding a second time or cap height before layout measurement.
Normal compact dialogs start at 420 px wide and cap at 560 px. A form needing
wider controls can explicitly raise its maximum width (the media time grid does
this); it still fits its host and can scroll when the host is smaller. Footer
width also accounts for the longest button caption. In form layouts, prefer
AllNonFixedFieldsGrow so Fluent controls with Preferred size policies fill their
fields. Avoid fixed widths on descriptive text.

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
