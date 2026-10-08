Slide designer
==============

Slide Designer is an optional plugin, enabled by default. Enable or disable it
in Plugin Manager. Creating or editing an item opens directly in Slide Designer,
without restarting OpenLP+. When disabled, songs and custom slides use their
original dialogs and basic text editors. Saved designs and their projection/export
behaviour remain intact; enabling the plugin makes those designs editable again.

The designer opens in its own Fluent window, which can be minimised or maximised.
The main OpenLP+ window and other library items remain available without replacing
the draft. Its window title is the item name followed by ``- OpenLP+``, with
``New Song`` or ``New Custom Slide`` used for unnamed items. Exit/Quit and closing
the main window check each open designer for unsaved changes. Changed items offer
Save, Discard and Cancel in a ContentDialog; unchanged items close without a prompt.
Cancel or a validation failure stops quitting. Once the designers close, OpenLP+
continues its normal unsaved-service and exit-confirmation behaviour.

Songs have a collapsible navigation rail for Slides, Authors/Topics/Songbooks,
Copyright/Flags/Comments and Linked Audio. Metadata controls, validation and saving
use the existing Songs plugin. Custom Slides has a single workspace with Credits
below its slide list. Title and, for songs, Alternative title are in the top
command row. Verse order is below the song split controls. Theme is in the footer below the slide preview, with the Preview aspect-ratio
selector aligned to the right. The preview uses the assigned theme, falling back
to the global theme. Imported theme snapshots remain in use until a new theme is chosen.

Edit words in the left sidebar. Section headings can be typed directly, forced
splits create separate rows and optional splits appear as dotted lines. Shift-click
selects a range of whole slides; Ctrl/Command-click toggles slides in the selection.
Drag across rows to select text spanning slides. Cut, copy, paste and delete work
with either selection. The context menu can paste whole slides before or after the
selection. Lyrics and design changes share the formatting command row's undo/redo.

The Styles picker applies one named formatting style to each piece of text.
Choosing another replaces the existing style on the selected text; choosing
None removes it. Bold, italic and underline can still be combined independently.
The picker shows Mixed when a selection contains different styles. Applying a
style across slides preserves section labels and split markers.

New designs start with a Full HD 1920 × 1080 canvas. The preview's canvas selector
also offers 1920 × 1200 (16:10), 2560 × 1080 (ultrawide) and 1440 × 1080 (4:3).
Position and size controls use pixels on that canvas. Changing canvas size fits
and centres the whole layout, scaling positions, dimensions and fonts uniformly
so aligned edges, relative spacing and object proportions are preserved. Changes use a fixed reference
canvas, so switching aspect ratios repeatedly does not cumulatively resize or
move the objects. The reference is saved with the design. Canvas changes support undo.
The previous preview remains visible while text, formatting, layout or aspect
ratio changes render, then switches to the completed layout once its images,
fonts and positioning are ready.

On another output size, the layout is fitted and centred proportionally. The
background still fills the screen; objects are never stretched to match the
output aspect ratio. Earlier designs retain their existing output behaviour until
edited in the designer. The XML retains normalised coordinates plus canvas
width/height, avoiding rounding loss when converting between pixel sizes.

Add text boxes, rectangles, ellipses and images with the toolbar. Select an
element on the canvas or in Layers. The top row in Layers is the frontmost object;
drag rows to reorder them, or use the arrow buttons and the Arrange menu. Slide
text is a layer too, and new objects are added at the front. Selecting a covered
object in Layers shows an outline that can be dragged without raising the object.
Drag any corner or edge handle to resize its box, including the slide text.
Properties accordions show Reset beside the chevron when their values differ
from the defaults. Reset restores only that section; for slide text, defaults
come from the theme. Properties
controls geometry, rotation, opacity, font, alignment, colours, outlines and
shadows. Text outlines follow the letters; shape and image outlines follow their
boundaries. Shadows have colour, horizontal/vertical offsets and blur controls.
Properties starts closed and its toolbar button toggles the whole sidebar,
including Layers. Unavailable accordions are disabled at 65% opacity.

Shift-, Ctrl- or Command-click objects on the canvas to select more than one.
Layers also supports multiple selection and Shift ranges. Drag selected objects
together or reorder selected rows together. Align aligns left, centre, right,
top, middle or bottom, and distributes horizontal or vertical gaps evenly.
Alignment uses the selection bounds when multiple objects are selected, or the
whole slide when a single object is selected. Distribution requires three or more
selected objects. Arrange controls layer order; its Flip horizontal and Flip vertical
commands mirror each selected object. These operations support undo.
Properties stays available for multiple selections. Shared values are shown;
different values leave the field empty. Entering a value applies it to all
applicable selected objects, as a single undo step. Font controls apply to text,
fill controls to shapes, and geometry, opacity and effects to every object.

Click the empty canvas area or empty space in Layers to deselect objects.
Properties includes Show footer for the currently previewed page. This also works
for individual overflow pages within a verse. Song footer choices apply to that
verse page wherever it repeats in the service order. Custom-slide choices follow
slides when moved or deleted. Footer choices are saved in XML and services and
used by the basic editor, projection and presentation export.

Properties also shows the slide background: theme, colour or gradient, plus an
optional image with its own opacity and fit. Image opacity reveals the colour or
gradient underneath without fading the slide text. Select any text, shape or
image or video layer to change that object's opacity.

The Media picker is shared by Slide Designer and Theme Designer. It shows library
thumbnails, with search and folder filters. Add files imports images or videos into
the corresponding library and retains a managed copy. Video objects and designed
background videos, including theme backgrounds, loop silently using HTML5 video
behind the slide text. Linked song audio remains independent.
The designer caches silent WebM playback copies where required for browser codec
compatibility, fitted within Full HD. Saved designs and exports retain the original
media, not the playback copies.
Right-click media in the picker or its selected-file field to open a larger preview
with file size, type and resolution. Video previews also show frame rate, duration
and codec. Show in Finder/Explorer reveals the original file. Theme backgrounds
retain independent copies and friendly labels when library entries are deleted.

Original files smaller than 2 MiB are embedded as base64 data URIs. Larger files
use content-addressed references and are bundled once in exported archives, including
assets in master layouts and per-slide overrides. Songs with large assets export as
``.osz`` packages containing OpenLyrics XML and media; the OpenLyrics importer accepts
these packages. Custom exports include their XML alongside the service data in
``.osz`` archives. Themes retain ``.otz`` archives, embedding small backgrounds in their
JSON and bundling larger files. Imports retain assets permanently, independently of
the archive, original source files and library entries.

Effects combines blur, brightness, contrast, greyscale, hue, invert, saturation and
sepia. Select an image to adjust its filters, or select the slide to filter its
background without affecting text. Multiple selected images can be edited together;
mixed values appear blank. The reset icon in each modified accordion restores that
section. Filters are stored in the portable design and used by preview and live output.
PPTX exports preserve editable PowerPoint controls for blur, brightness, contrast
and saturation; greyscale is represented by reduced saturation. Each supported
image or background includes a lossless JPEG XR original and a rendered PNG
preview. PowerPoint uses its own correction curves when the effects are edited,
so the appearance can then differ slightly from the designer's CSS filters.
Stacks containing hue rotation, invert, sepia, a filtered border or a blur radius
beyond PowerPoint's range are baked in full to preserve their appearance and order.
ODP exports bake all filters into the image pixels. In both formats, slide text
remains editable and images remain separate movable objects.

New slides use Theme by default. Theme locks design properties, object insertion
and canvas manipulation; Show footer remains editable. Preview aspect ratios can
still be changed without modifying the saved design. Songs do not automatically
offer a Custom layout, and existing saved formatting is preserved. Earlier shared
designs in custom slide items remain available as Custom, which can be renamed.
Use New layout to create a named master
from the current design, and the Layout selector to apply it to the previewed slide.
Canvas and property edits customise only the current slide, leaving its assigned
layout and other slides unchanged. New layout captures the current design for
reuse on other slides. Layouts can be renamed; deleting one preserves its slides' appearance
as local designs. Layouts and overrides are stored with the song/custom item.

The toolbar Reset button changes every slide to Theme and clears local changes,
including per-slide footer overrides. It asks for confirmation and supports undo.
Saved layouts remain available to apply again. Reset is available when any slide
needs resetting, even if the currently selected slide already uses Theme.

Selecting a row or moving the text cursor selects the preview. Pagination follows
the item's base layout so changing a named master does not renumber existing slide
assignments. Repeated song verse pages share their assigned layout and local
customisations.

Save validates the complete item and writes metadata, lyrics and design together.
Validation errors keep the workspace open and select the relevant song page.
Cancel leaves the library item unchanged. Save and Preview is available when
editing an item already in preview and explicitly saves the current draft.

Portability
-----------

Songs store a versioned design document in the songs database. OpenLyrics XML
exports include it in an ``olp:design`` extension with namespace
``https://openlp.org/ns/slide-design/1``. Custom items store the same extension
inside their existing XML and preserve it through their existing ``.osz`` export
and import route. Service headers also retain the design.
Layer order is saved with the design and used by the projection renderer. Older
designs without an explicit order retain their original text-above-decorations
appearance.

Added images and videos retain their original formats, using embedded data or
archive assets according to their size. Exports include a snapshot of
the resolved theme, including its background media. The receiving OpenLP+
installation therefore does not need those original image files or a matching
named theme. Canvas dimensions, masters, assignments, local changes and per-page
footer choices are included too.
Exporting does not freeze the source library item's theme.
Explicitly assigning a new theme releases an imported theme snapshot.

Local video backgrounds and video objects travel with the design. Stream URLs and
font files are not embedded. Fonts still need to be available on the receiving computer. Other
OpenLyrics applications may ignore or reject the OpenLP+ extension. PPTX exports preserve editable slide text, text boxes, shapes and embedded images
in their saved layer order, including geometry, opacity, rotation, flips, outlines
and shadows. Static backgrounds are composited at output resolution to retain
image opacity and gradients. Presentation applications can differ in their
rendering of DrawingML text effects. ODP exports preserve added image layers,
including their opacity, rotation, flips, outlines, shadows and filters baked into
the image pixels. Added text boxes and shapes are not yet preserved in ODP.

Custom slides can also be saved as PNG images directly into the Image library.
Select the custom item(s), then choose ``Export > Save to Image library…``.
Choose no folder, an existing folder, or a new folder. Each rendered slide is
captured at the current output resolution, including its theme, custom objects,
effects and footer visibility. Images use the custom item's title, followed by
``(2)``, ``(3)`` and so on for subsequent slides. Numbering restarts for each item.
These images are stored permanently in OpenLP+'s data folder; repeated saves do
not overwrite existing images. The original custom slides remain editable.
