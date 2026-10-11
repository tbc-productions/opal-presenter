# Dialog design pattern

Construct operator UI through `opal.core.widgets.fluent`. Its shared dialog
adapters keep native Fluent presentation, same-window modal behaviour and the
existing Qt result contracts. Do not construct `fluentqt.ContentDialog` or
native Qt message/input dialogs directly in application code.

On this page:

- [Choosing a surface](#choosing-a-surface)
- [Actions and wording](#actions-and-wording)
- [Validation and results](#validation-and-results)
- [Presentation and accessibility](#presentation-and-accessibility)
- [Verification](#verification)
- [Wizard presentation](#wizard-presentation)

## Choosing a surface

- Use `ContentDialog` for a compact prompt, confirmation or short selection.
- Use `FormDialog` when a form already has a QDialogButtonBox, validation in
  `accept()` or custom button handlers.

Put the form's root layout on
`dialog.content_widget`, not on the dialog itself. `create_button_box()`
registers it automatically; manually built boxes need `setButtonBox(box)`.

Keep larger editors, Settings, About, browser/media previews and multi-step
wizards on their existing specialised surfaces. The shared `QDialog` adapter
adds a visible heading from `setWindowTitle()`. System file and print pickers
retain their platform implementation.

## Actions and wording

For prompts and forms, keep this action order:

1. Primary action on the left.
2. Secondary action in the middle.
3. Cancel or Close on the right.

Wizards use the navigation order described below.

- **Narrow hosts:** stack actions in primary, secondary, Cancel/Close order with
  full captions visible. Return to a row when the host is wide enough.
- **Default action:** changes keyboard activation and accent emphasis, not position.
  Destructive confirmations default to Cancel.
- **Action wording:** use concrete verbs: Save, Rename, Copy, Create, Select, Apply,
  Export or Delete. Use Discard consistently for abandoning unsaved changes.
- **Instructions:** match the visible button caption; avoid references to an old OK/Yes label.

### Button roles

| Button-box role | FormDialog action |
| --- | --- |
| `AcceptRole` / `YesRole` | Primary |
| `ApplyRole` | Next available action |
| `HelpRole` / `DestructiveRole` | Secondary |
| `RejectRole` / `NoRole` | Close |

For two affirmative commands, use AcceptRole for the main action and ApplyRole
for the alternative, as in Planning Center's Import New/Refresh Service pair.
Additional utility commands stay in the form body.

## Validation and results

FormDialog forwards native footer clicks through the original button box.
Keep existing validation, error handling and clicked/accepted/rejected handlers;
do not connect another unconditional `accept()` or `done()` to the same
action. Failed validation and Help keep the form open. A cancelled confirmation
must also leave its parent form open and avoid writes.

### Result contracts

- ContentDialog uses `ResultPrimary`, `ResultSecondary` and `ResultNone`.
- FormDialog retains QDialog's `Accepted`/`Rejected` contract through the original handlers.
- The QMessageBox adapter retains its `StandardButton` results.

### Text validation and keyboard submission

For required text, disable the primary button for empty or whitespace-only
values, and trim the accepted value. Enter goes through the checked default
button; do not connect `returnPressed` directly to `done()`. Field updates
such as `editingFinished` must run before saving. Destructive copy must
describe exactly which records will be deleted, including inclusive dates.

## Presentation and accessibility

- **Heading:** use the native title slot.
- **Explanatory text:** use `FontRole.Body` and enable word wrapping. Routine field
  labels use Caption.
- **Field labels:** use `setBuddy()` and provide accessible names for fields without
  a visible label. Related controls need distinct labels; omit trailing colons.
- **Date ranges:** use two compact CalendarDatePicker fields labelled From and To.
- **Alignment:** centre single-line labels vertically beside their fields. Match
  input height to adjacent command buttons; align multiline-editor labels with the
  top of their content.

### Sizing and scrolling

- **Native padding:** preserve ContentDialog's padding. Adapters give fields at least
  32 px height, disable the problematic opacity effect on macOS and constrain the
  surface to its host. Do not add outer padding a second time.
- **Expand before scrolling:** fit the content before scrolling. Scroll only when
  content cannot fit within the host space and dialog width limit; keep footer
  actions visible. Do not cap height before layout measurement.
- **Host resizing:** recalculate size, expanding and removing scrollbars when content
  fits again. Measure again after native fonts and scrollbar geometry settle.
- **Floating panes:** temporarily hide floating workspace panes while a prompt occupies
  the main window, then restore them without changing their saved dock placement.
- **Compact width:** start at 420 px and cap at 560 px. Footer width also accounts for
  the longest button caption. Forms needing wider controls can explicitly raise
  their maximum width, as the media time grid does; they still fit and scroll in smaller hosts.
- **Growing fields:** prefer `AllNonFixedFieldsGrow` in form layouts so Fluent controls
  with Preferred size policies fill their fields. ContentDialog forms wrap labels
  above fields when a row cannot fit.
- **Long text:** avoid fixed widths on descriptions. Wrap user-supplied names,
  including Bible translation and unmatched book names.
- **Changing content:** remeasure open dialogs when their body changes. Confirmation
  lists grow to show their items; the body scrolls when the host is too small.

### Content ownership

Read accepted values before calling `deleteLater()` on temporary dialogs.
Content ownership follows FluentQt: replacing or taking content detaches it;
installed content is destroyed with its dialog.

## Verification

Check changed dialogs with the following checklist:

- Inspect rendered light/dark dialogs for clipping, extra gaps and button order.
- Exercise Enter, Escape, disabled actions, failed validation, Help and cancelled
  confirmations.
- Check long messages and a resized host: content must remain reachable and footer
  commands visible.

Standalone visual probes must call `fluentqt.initialize_resources()` as the
application does, so icons and typography render correctly.
The main regression suite is
`tests/openlp_core/widgets/test_fluent_dialogs.py`; form-specific tests cover
validation, song-usage deletion boundaries and network field updates.

## Wizard presentation

Keep multi-step workflows on `QtWidgets.QWizard` and `QtWidgets.QWizardPage` from
`opal.core.widgets.fluent`. The shared adapters retain Qt's page IDs, registered
fields, completion checks, validation and result contracts.

- **Headings:** use `setTitle()` and `setSubTitle()`. Fluent Title and Body typography
  use a step caption rather than Qt's banner. Page headings, step captions and short
  subtitles remain above the scrolling body; put long instructions in the body.
- **Size:** use an initial size rather than a fixed window size. Keep footer actions visible.
- **Navigation:** Cancel at the far left; Back and Next (or Commit/Finish) at the
  bottom right. Next, Commit and Finish retain accent styling and the default keyboard action.
- **Custom actions:** follow Cancel on the left. Enable optional actions with the
  corresponding wizard options so unused buttons remain hidden.
- **Welcome pages:** use the same typography without decorative side images.
- **Cloud Library:** retains its provider-specific step count and validation.
- **Help:** operator dialogs and wizards do not expose Help buttons or links to
  OpenLP's manual. Settings tooltips continue to explain fields locally.
- **Validation prompts:** belong to the active wizard and disable navigation until dismissed.

### First-time setup

First-time setup configures plugins and displays locally. It can restore a settings
backup or copy an existing data folder into a separate Opal library.

- **Default:** the final import page starts at None, with no import cards.
- **Import cards:** Opal Presenter shows Library and Settings only; OpenLP shows
  Library. Each card contains its folder or backup picker. Shared radio buttons
  make Opal imports mutually exclusive, with Library selected initially. Only the
  selected card's input and browse button are enabled.
- **Required input:** Library requires an existing folder; Settings only requires an
  existing file. None allows setup to finish immediately. Hidden and unselected
  fields are ignored.
- **Settings priority:** plugin and display choices made in the wizard take priority
  over an imported settings backup.
- **Success and failure:** successful imports show a confirmation before setup closes.
  Failed imports show a ContentDialog and leave setup open for corrections.
- **Library import:** copies songs, Bibles, custom slides, themes, designer assets and
  stored image, media and presentation files. Both source and current libraries are
  preserved. Close the source application before importing.
- **Linked files:** copy linked external files into the imported library, including
  image and song audio references and theme backgrounds.
- **Settings-only import:** copies linked media and presentations into current Opal
  storage without switching libraries. Settings backups use the separate field on
  the same page.
- **Copy failures:** missing files stop the import. Failed copies are removed and
  leave setup open.
- **Re-running setup:** the data folder switches only after plugins close. The
  application requests a restart through its normal save and close flow. The current
  theme is preserved unless a settings backup changes it.
- **Local setup:** does not contact OpenLP servers or download songs, Bibles, themes,
  thumbnails or the web remote. Built-in themes install from local files on first startup.

Opal Presenter is independent and is not endorsed by OpenLP.

### Bible imports

- **Translation lists:** refresh only on request. Sources whose lists cannot be
  retrieved are disabled and marked ` - unavailable`.
- **Web validation:** before advancing, the source's existing extractors retrieve
  its book list and the first chapter of its first book, requiring non-empty verse text.
- **Failed checks:** keep the source page open so the user can retry or choose a local file.
- **Scope of the check:** a current sample cannot guarantee every chapter or future
  availability. Web Bibles retrieve uncached chapters on demand.
- **Progress:** translation refreshes and web imports use indeterminate progress
  rings; local imports retain progress bars. Network waits keep GUI animations
  running, with clicks deferred until completion.

### Wizard verification

Wizard regressions are covered by `tests/openlp_core/widgets/test_wizard.py`,
`tests/openlp_core/ui/test_firsttimeform.py` and the Bible and Cloud Library
wizard tests. Check light/dark rendering, long instructions, narrow windows,
Enter/Escape, mouse clicks, failed validation and Help.
