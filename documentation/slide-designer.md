# Slide designer

Slide Designer is an optional plugin, enabled by default. Enable or disable it
in Plugin Manager. Creating or editing an item opens directly in Slide Designer,
without restarting Opal Presenter. When disabled, songs and custom slides use their
original dialogs and basic text editors. Saved designs and their projection/export
behaviour remain intact; enabling the plugin makes those designs editable again.

On this page:

- [Workspace and saving](#workspace-and-saving)
- [Editing lyrics and slides](#editing-lyrics-and-slides)
- [Canvas, sizing and preview](#canvas-sizing-and-preview)
- [Objects, layers and properties](#objects-layers-and-properties)
- [Images and video](#images-and-video)
- [Image effects](#image-effects)
- [Preview aspect ratio](#preview-aspect-ratio)
- [Layouts and per-slide changes](#layouts-and-per-slide-changes)
- [Save and cancel](#save-and-cancel)
- [Portability](#portability)

## Workspace and saving

- **Window:** the designer opens in its own Fluent window, which can be minimised
  or maximised. The main Opal Presenter window and other library items remain
  available without replacing the draft.
- **Window title:** the item name followed by `- Opal Presenter`. Unnamed items
  use `New Song` or `New Custom Slide`.
- **Exit/Quit:** closing the main window checks each open designer for unsaved
  changes. Changed items offer **Save**, **Discard** and **Cancel** in a
  ContentDialog; unchanged items close without a prompt.
- **Cancelled exit:** Cancel or a validation failure stops quitting. Once the
  designers close, Opal Presenter continues its normal unsaved-service and
  exit-confirmation behaviour.

### Songs and Custom Slides

- **Song navigation:** a collapsible rail for Slides, Authors/Topics/Songbooks,
  Copyright/Flags/Comments and Linked Audio. Metadata controls, validation and
  saving use the existing Songs plugin.
- **Custom Slides:** a single workspace with Credits below its slide list.
- **Titles:** Title and, for songs, Alternative title are in the top command row.
- **Copyright warning:** songs without copyright information show a warning above
  the lyrics entry and a badge beside Copyright/Flags/Comments. Both clear as soon
  as copyright information is entered.
- **Verse order:** below the song split controls.
- **Theme:** in the footer below the slide preview, with Preview aspect ratio
  aligned to the right. The preview uses the assigned theme, falling back to the
  global theme. Imported theme snapshots remain until a new theme is chosen.

## Editing lyrics and slides

Edit words in the left sidebar:

- **Sections and splits:** type section headings directly. Forced splits create
  separate rows; optional splits appear as dotted lines.
- **Whole-slide selection:** Shift-click selects a range; Ctrl/Command-click
  toggles slides in the selection.
- **Text selection:** drag across rows to select text spanning slides.
- **Clipboard and deletion:** cut, copy, paste and delete work with either
  selection. The context menu can paste whole slides before or after the selection.
- **Undo/redo:** lyrics and design changes share the formatting command row's history.

### Text styles

- **Named style:** the Styles picker applies one named formatting style to each
  piece of text. Choosing another replaces the existing style on the selected text.
- **None:** removes the named style.
- **Independent formatting:** bold, italic and underline can still be combined.
- **Mixed:** appears when a selection contains different styles.
- **Across slides:** applying a style preserves section labels and split markers.

## Canvas, sizing and preview

New designs use Full HD 1920 × 1080 proportions automatically. Existing designs
retain their saved proportions. There is no separate slide-size control.
The previous preview remains visible while text, formatting, layout or aspect
ratio changes render, then switches to the completed layout once its images,
fonts and positioning are ready.

On another output size, the layout is fitted and centred proportionally. The
background still fills the screen; objects are never stretched to match the
output aspect ratio. Earlier designs retain their existing output behaviour until
edited in the designer. The XML retains normalised coordinates plus canvas
width/height, avoiding rounding loss when converting between pixel sizes.

### Theme text areas

- **Geometry:** text and footer areas use percentage sizes and offsets from their
  nearest screen edges. Boxes stay inside the display, including older themes with
  oversized or off-screen coordinates.
- **Default spacing:** main and footer areas leave a 2% margin at display edges and
  a 2% gap between them.
- **Overflow:** text stays inside its box. Lyrics retain normal slide pagination;
  long footers can use the theme's wrapping option.

### Coordinates and font scaling

- **Position and box size:** percentages of the slide canvas in both designers,
  shown with at most one decimal place.
- **Font size:** whole reference points on a 1080-high canvas, independent of the
  connected display or selected preview ratio.
- **Scaling:** saved themes record reference display dimensions. Rendering scales
  fonts, spacing, outlines and shadows with display height. A 64-point font designed
  at 1080p occupies the same proportion at 720p or 4K; preview zoom follows the same scaling.
- **Themes without reference dimensions:** saved footer bounds provide an estimate.
  A custom footer that does not reach the screen edges can make that estimate
  inaccurate. Saving the theme records explicit dimensions for future use.

## Objects, layers and properties

- **Add:** use the toolbar to add text boxes, rectangles, ellipses and images.
- **Select:** choose an element on the canvas or in Layers. Selecting a covered
  object in Layers shows an outline that can be dragged without raising the object.
- **Layer order:** the top row is the frontmost object. Drag rows, use the arrow
  buttons or use Arrange to reorder them. Slide text is a layer too; new objects
  are added at the front.
- **Resize:** drag any corner or edge handle, including those on slide text.
- **Reset properties:** modified accordions show Reset beside the chevron. Reset
  restores only that section; slide-text defaults come from the theme.
- **Properties:** controls geometry, rotation, opacity, font, alignment, colours,
  outlines and shadows. Text outlines follow letters; shape and image outlines
  follow their boundaries. Shadows have colour, horizontal/vertical offsets and blur.
- **Sidebar:** Properties starts closed. Its toolbar button toggles the whole
  sidebar, including Layers. Unavailable accordions are disabled at 65% opacity.

### Multiple selection and alignment

- **Select several objects:** Shift-, Ctrl- or Command-click on the canvas. Layers
  also supports multiple selection and Shift ranges.
- **Move and reorder:** drag selected objects together or reorder selected rows together.
- **Align:** left, centre, right, top, middle or bottom. Multiple objects use the
  selection bounds; a single object uses the whole slide.
- **Distribute:** space horizontal or vertical gaps evenly. Requires three or more objects.
- **Arrange:** controls layer order; Flip horizontal and Flip vertical mirror each
  selected object. These operations support undo.
- **Shared properties:** Properties stays available for multiple selections. Shared
  values are shown; different values leave the field empty. Entering a value applies
  it to all applicable selected objects as a single undo step.
- **Applicable controls:** font for text; fill for shapes; geometry, opacity and
  effects for every object.

### Selection and footer visibility

- **Deselect:** click the empty canvas or empty space in Layers.
- **Show footer:** available in Properties for the previewed page, including
  individual overflow pages within a verse.
- **Songs:** footer choices apply to that verse page wherever it repeats in service order.
- **Custom Slides:** footer choices follow slides when moved or deleted.
- **Persistence:** choices are saved in XML and services, and used by the basic
  editor, projection and presentation export.

### Slide backgrounds and opacity

Properties also shows the slide background: theme, colour or gradient, plus an
optional image with its own opacity and fit. Image opacity reveals the colour or
gradient underneath without fading the slide text. Select any text, shape or
image or video layer to change that object's opacity.

## Images and video

The Media picker is shared by Slide Designer and Theme Designer:

- **Browse:** library thumbnails with search and folder filters.
- **Add files:** imports images or videos into the corresponding library and retains
  a managed copy.
- **Video playback:** video objects and designed background videos, including theme
  backgrounds, loop silently using HTML5 video behind the slide text. Linked song
  audio remains independent.
- **Playback copies:** where browser codecs require them, the designer caches silent
  WebM copies with source resolution and high-quality VP9 encoding. Saved designs
  and exports retain the original media, not the playback copies.
- **Cover:** crops to fill the screen.
- **Contain:** preserves the entire frame with the theme colour around it.
- **Preview:** right-click media in the picker or selected-file field for a larger
  preview with file size, type and resolution. Videos also show frame rate, duration
  and codec.
- **Show in Finder/Explorer:** reveals the original file.
- **Theme backgrounds:** retain independent copies and friendly labels when library
  entries are deleted.

### Embedded and packaged media

- **Below 2 MiB:** original files are embedded as base64 data URIs.
- **Larger files:** use content-addressed references and are bundled once in exported
  archives, including assets in master layouts and per-slide overrides.
- **Songs:** large assets export in `.opal-song` packages containing OpenLyrics XML
  and media. The OpenLyrics importer accepts these packages.
- **Custom Slides:** `.opal-slides` archives include their XML alongside the service data.
- **Themes:** `.opal-theme` archives embed small backgrounds in JSON and bundle larger files.
- **Imports:** retain assets permanently, independently of the archive, original
  source files and library entries.

## Image effects

Effects combines blur, brightness, contrast, greyscale, hue, invert, saturation and sepia:

- **Image filters:** select an image to adjust its filters.
- **Background filters:** select the slide to filter its background without affecting text.
- **Multiple images:** can be edited together; mixed values appear blank.
- **Reset:** the reset icon in each modified accordion restores that section.
- **Saved effects:** filters are stored in the portable design and used by preview
  and live output.

### Effects in presentation exports

- **Editable PPTX effects:** blur, brightness, contrast and saturation remain editable
  in PowerPoint. Greyscale is represented by reduced saturation. Each supported image
  or background includes a lossless JPEG XR original and a rendered PNG preview.
- **PowerPoint appearance:** its correction curves can make edited effects look
  slightly different from the designer's CSS filters.
- **Baked PPTX effects:** stacks containing hue rotation, invert, sepia, a filtered
  border or a blur radius beyond PowerPoint's range are baked in full to preserve
  appearance and order.
- **ODP effects:** all filters are baked into the image pixels.
- **Both formats:** slide text remains editable; images remain separate movable objects.

## Preview aspect ratio

- **Built-in ratios:** 16:9, 16:10, ultrawide 64:27 and 4:3.
- **Display ratios:** connected displays and saved profiles show their aspect ratios.
  720p, 1080p, 1440p and 4K displays with the same ratio produce identical previews.
  The display list refreshes when the picker opens; disconnected outputs fall back to 16:9.
- **Create or edit a profile:** use the pencil button for a named ratio, such as width
  9 and height 16 for portrait. Names must be unique; components must be between
  1 and 16384. Existing profiles retain their proportions.
- **Delete a profile:** the delete button removes the selected profile. Profiles are
  saved in local application settings and available across items.
- **Change the preview:** Preview aspect ratio fits and centres the existing layout
  without resizing the slide, changing the design or adding an undo step. Dragging
  and resizing objects in another output preview preserves the slide's proportions.

## Layouts and per-slide changes

- **Theme:** the default for new slides. Locks design properties, object insertion
  and canvas manipulation; Show footer remains editable. Preview aspect ratio can
  still change without modifying the saved design.
- **Custom:** songs do not automatically offer a Custom layout, and existing saved
  formatting is preserved. Earlier shared designs in custom slide items remain
  available as Custom, which can be renamed.
- **New layout:** creates a named master from the current design for reuse on other slides.
- **Layout selector:** applies a layout to the previewed slide.
- **Local edits:** canvas and property edits customise only the current slide,
  leaving its assigned layout and other slides unchanged.
- **Rename or delete:** layouts can be renamed. Deleting one preserves its slides'
  appearance as local designs. Layouts and overrides are stored with the song/custom item.

### Reset to Theme

The toolbar Reset button changes every slide to Theme and clears local changes,
including per-slide footer overrides. It asks for confirmation and supports undo.
Saved layouts remain available to apply again. Reset is available when any slide
needs resetting, even if the currently selected slide already uses Theme.

### Pagination and repeated verses

Selecting a row or moving the text cursor selects the preview. Pagination follows
the item's base layout so changing a named master does not renumber existing slide
assignments. Repeated song verse pages share their assigned layout and local
customisations.

## Save and cancel

- **Save:** validates the complete item and writes metadata, lyrics and design together.
- **Validation errors:** keep the workspace open and select the relevant song page.
- **Cancel:** leaves the library item unchanged.
- **Save and Preview:** available when editing an item already in preview;
  explicitly saves the current draft.

## Portability

- **Songs:** store a versioned design document in the songs database. OpenLyrics XML
  exports include it in an `opal:design` extension with namespace
  `urn:net.tbcproductions.OpalPresenter:slide-design:1`.
- **OpenLP compatibility:** imports also accept the
  `https://openlp.org/ns/slide-design/1` namespace.
- **Custom items:** store the same extension in their existing XML and preserve it
  through native Opal package export and import. Service headers also retain the design.
- **Layer order:** saved with the design and used by projection. Older designs
  without explicit order retain their original text-above-decorations appearance.

### Included assets and theme snapshots

- **Media:** added images and videos retain their original formats, using embedded
  data or archive assets according to size.
- **Theme snapshot:** exports include the resolved theme and its background media.
  The receiving installation does not need the original image files or a matching named theme.
- **Design data:** includes canvas dimensions, masters, assignments, local changes
  and per-page footer choices.
- **Source theme:** exporting does not freeze the source library item's theme.
  Explicitly assigning a new theme releases an imported theme snapshot.

### Presentation export compatibility

- **Video and fonts:** local video backgrounds and objects travel with the design.
  Stream URLs and font files are not embedded; fonts must be available on the receiving computer.
- **Other OpenLyrics applications:** may ignore or reject the Opal Presenter extension.
- **PPTX objects:** preserve editable slide text, text boxes, shapes and embedded
  images in their saved layer order, including geometry, opacity, rotation, flips,
  outlines and shadows.
- **PPTX backgrounds:** static backgrounds are composited at output resolution to
  retain image opacity and gradients. Presentation applications can differ in their
  rendering of DrawingML text effects.
- **ODP objects:** preserve added image layers with opacity, rotation, flips, outlines,
  shadows and filters baked into the image pixels. Added text boxes and shapes are
  not yet preserved in ODP.

### Export to the Image library

1. Select the custom item(s), then choose **Export → Save to Image library…**.
2. Choose no folder, an existing folder or a new folder.

- **Capture:** each rendered slide uses the current output resolution, including
  its theme, custom objects, effects and footer visibility.
- **Names:** the custom item's title, followed by `(2)`, `(3)` and so on for subsequent
  slides. Numbering restarts for each item.
- **Storage:** images are stored permanently in Opal Presenter's data folder;
  repeated saves do not overwrite existing images. The original custom slides remain editable.
