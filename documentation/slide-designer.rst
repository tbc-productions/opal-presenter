Slide designer
==============

Slide Designer is an optional plugin, enabled by default. Enable or disable it
in Plugin Manager. The next Edit or Edit All dialog uses the selected editor,
without restarting OpenLP+. When disabled, songs and custom slides use their
original basic text editors. Saved designs and their projection/export behaviour
remain intact; enabling the plugin makes those designs editable again.

Open a song or custom item, then choose Edit or Edit All. The designer replaces
that inner text-editing dialog. The outer Song Editor and Custom Slides windows
retain their read-only lists and do not show the canvas or design panes.
The designer opens in its own Fluent window, which can be minimised or maximised.
The outer editor is hidden while its draft is open, allowing the main OpenLP+
window and other library items to be used without replacing the draft.
Its window title is the item name followed by ``- OpenLP+``, with ``New Song`` or
``New Custom Slide`` used for unnamed items.

Edit words on the left and select a section to preview it. The centre canvas
uses the projection renderer and its pagination. Preview the current output,
global, assigned item or current service theme. The Theme selector assigns an
item theme, subject to OpenLP+'s existing theme-level setting.

New designs start with a Full HD 1920 × 1080 canvas. The preview's canvas selector
also offers 1920 × 1200 (16:10), 2560 × 1080 (ultrawide) and 1440 × 1080 (4:3).
Position and size controls use pixels on that canvas. Changing canvas size fits
and centres the whole layout, scaling positions, dimensions and fonts uniformly
so aligned edges, relative spacing and object proportions are preserved. Changes use a fixed reference
canvas, so switching aspect ratios repeatedly does not cumulatively resize or
move the objects. The reference is saved with the design. Canvas changes support undo.
The previous preview remains visible while the new aspect ratio renders, then
switches to the completed layout once its images, fonts and positioning are ready.

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
For slide text, Reset to theme in Properties restores the theme position, size,
font and effects without changing the other layers or background. Properties
controls geometry, rotation, opacity, font, alignment, colours, outlines and
shadows. Text outlines follow the letters; shape and image outlines follow their
boundaries. Shadows have colour, horizontal/vertical offsets and blur controls. Layers and Properties can be shown
independently. Undo and redo operate on the design.

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
image layer to change that object's opacity. Background images are embedded in
the saved design, using the same portable PNG format as image objects.

Existing designs become the Shared layout. Use New layout to create a named master
from the current design, and the Layout selector to apply it to the previewed slide.
Edit layout toggles between editing that master and making changes to the current
slide. Master changes reach all slides using it, while properties changed locally
remain local. Masters can be renamed; deleting one preserves its slides' appearance
as local designs. Layouts and overrides are stored with the song/custom item.

Reset is a split button: Reset slide clears the current slide's local changes and
restores its assigned master; Reset all slides clears local changes throughout the
item. Both ask for confirmation, preserve master layouts and assignments, and can
be undone. Per-slide footer overrides are reset too.

In Edit All, the section selector and text cursor select the preview. Previous and
Next move between overflow pages. Pagination follows the Shared layout so changing
a named master does not renumber existing slide assignments. Repeated song verse
pages share their assigned layout and local customisations.

Accepting an inner editor updates the outer dialog's draft. Cancelling the inner
editor discards its changes; cancelling the outer dialog leaves the library
unchanged. Saving writes the design along with the lyrics.

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

Added images are decoded and embedded as PNG data URIs. Large images are scaled
to fit 1920 x 1080, with an 8 MB encoded-image limit. Exports include a snapshot of
the resolved static theme, including its background image. The receiving OpenLP+
installation therefore does not need those original image files or a matching
named theme. Canvas dimensions, masters, assignments, local changes and per-page
footer choices are included too.
Exporting does not freeze the source library item's theme.
Explicitly assigning a new theme releases an imported theme snapshot.

This is a static design format: video/stream backgrounds and font files are not
embedded. Fonts still need to be available on the receiving computer. Other
OpenLyrics applications may ignore or reject the OpenLP+ extension. PPTX exports preserve editable slide text, text boxes, shapes and embedded images
in their saved layer order, including geometry, opacity, rotation, flips, outlines
and shadows. Static backgrounds are composited at output resolution to retain
image opacity and gradients. Presentation applications can differ in their
rendering of DrawingML text effects. ODP export does not yet preserve added
design objects.
