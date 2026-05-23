# Investigation: Song → Image/Presentation Transition Missing on Output Display

## User-reported symptom

> "Transitions seems to not work when switching from a song to an image or
> presentation (I do not have transitions enabled for songs). If I spam click
> the 'Go live' button (4-5 times), it starts to work properly."

Observations:

- **Preview window**: transition works correctly on first click.
- **Output display**: transition is **missing on the first click**, appears
  only after the user spam-clicks 4-5 times.
- Song theme has `display_slide_transition = false`; image/presentation has
  `display_slide_transition = true` (fade).

This is the **remaining unresolved bug**. Everything below captures the
state of the investigation so a future session can pick it up.

---

## What has been changed already (and why)

All changes live on branch `stability-fixes`. These three files are dirty:

| File | Scope |
| --- | --- |
| [openlp/core/display/html/display.js](../openlp/core/display/html/display.js) | Transitions + hide/show fixes + diagnostic logging |
| [openlp/core/display/html/display.css](../openlp/core/display/html/display.css) | Pause-overlay transition override |
| [openlp/core/display/window.py](../openlp/core/display/window.py) | `_disable_hide_transition()` + `handle_transition_debug` prefix |

The hide/show fixes (transition tokens, pause-overlay CSS, symmetric
`_disable_hide_transition`) are captured in
[hide_button_analysis.md](./hide_button_analysis.md). What follows is
only the song→image/presentation bug.

### Transition-system changes (landed, may help the bug)

1. **[display.js:496](../openlp/core/display/html/display.js#L496)** — Reveal's
   init config now sets `backgroundTransition: "fade"` (previously `"none"`).
   Without this, reveal's internal `config.backgroundTransition` is "none"
   at init, which means the CSS rule
   `.reveal[data-background-transition=none] > .backgrounds .slide-background
   { transition: none; }` nukes per-slide fades across the board.
2. **`setItemTransition()` no longer calls `Reveal.configure`** for
   `backgroundTransition` — the inter-item toggle is decoupled from the
   intra-item cross-fade.
3. **`_applyImageSlideContent()` helper** unifies how image and PDF slides
   are rendered. When the theme has fade enabled we use reveal's native
   `data-background-image` so reveal cross-fades the background between
   slides. Otherwise we render an `<img>` inside the `<section>` so
   reveal's section transition (slide/zoom/convex/concave) carries the
   image.
4. **`updatePdfSlideTransitions()`** now rebuilds the section structure
   when the fade effect toggles, using `data-slide-image` to remember the
   source URL. Previously toggling the transition couldn't swap between
   `<img>` and `data-background-image` structures.

### Diagnostic logging (landed, still active)

These were added to capture the output-display race. They should be
**removed** once the bug is fixed.

| Location | Emits |
| --- | --- |
| [display.js:2348](../openlp/core/display/html/display.js#L2348) `setTheme` | theme arrival: `dst`, `dstType`, `isDisplay` |
| [display.js:1424](../openlp/core/display/html/display.js#L1424) `setImageSlides.pre` | pre-render decisions: `themeSet`, `dst`, `useNativeBgImages`, `doTransitions`, `hasPdfBg` |
| [display.js:1432](../openlp/core/display/html/display.js#L1432) `setImageSlides.post` | post-render mark |
| [display.js:2470](../openlp/core/display/html/display.js#L2470) `applyTheme.configure` | enabled branch + effect |
| [display.js:2473](../openlp/core/display/html/display.js#L2473) `applyTheme.configure` | disabled branch |
| [display.js:~1218](../openlp/core/display/html/display.js#L1218) `_logTransitionDebug` | reveal config, wrapper `data-background-transition`, per-slide backgrounds summary, slide section count |
| [window.py:616](../openlp/core/display/window.py#L616) `handle_transition_debug` | Prefixes every log line with `[DISPLAY]` or `[preview]` |

---

## How the flow actually runs (verified)

### Python side ([slidecontroller.py](../openlp/core/ui/slidecontroller.py))

In `_process_item()` when switching items:

```
slidecontroller.py:1190  self._set_theme(self.service_item)            # async
slidecontroller.py:1234  self.preview_display.load_images(...)          # async
slidecontroller.py:1236  display.load_images(self.service_item.slides)  # async (output)
```

`_set_theme` → `display.set_theme(...)` → `run_in_display('setTheme', is_sync=False)`.

`load_images` → `run_in_display('setImageSlides', imagesr)` with the
default `is_sync=False`.

### Bridge ([window.py:568](../openlp/core/display/window.py#L568))

```python
wait_for(lambda: getattr(self, '_DisplayWindow__script_done', True))
if is_sync: ...                         # blocks with event loop
else:
    self.webview.page().runJavaScript(script)   # fire-and-forget
```

Two `is_sync=False` calls are fire-and-forget. Qt serialises them in
script submission order, **but** the async path does not block on the
previous script's `__script_done` completion — the `wait_for` on line 579
short-circuits because `__script_done` is never flipped to `False` for
async scripts. So the ordering guarantee comes from `QWebEnginePage`
serialising `runJavaScript` on the page's JS thread.

### JS side

- **setTheme** ([display.js:2343](../openlp/core/display/html/display.js#L2343))
  - Stores `Display._theme = theme` (reference compare always true for
    freshly-parsed payloads → always stores)
  - Sets `_themeApplied = false`
  - Does **not** trigger reveal reconfigure — that happens later in
    `applyTheme`
- **setImageSlides** ([display.js:1360](../openlp/core/display/html/display.js#L1360))
  - Reads `Display._theme.display_slide_transition` **at render time**
  - `useNativeBackgroundForImageSlides = themeTransitionsEnabled &&
    themeTransitionType === TransitionType.Fade`
  - If true → section gets `data-background-image` + `data-background-transition="fade"`
  - If false → section gets `<img>` child (no data-background-transition)
  - Calls `replaceSlides(parentSection)`
- **replaceSlides** ([display.js:788](../openlp/core/display/html/display.js#L788))
  - Calls `applyTheme(new_slides, false)` **once** on the wrapper section
  - Then `Reveal.slide(...)` + `Reveal.sync()` to regenerate backgrounds
- **applyTheme** ([display.js:2419](../openlp/core/display/html/display.js#L2419))
  - Calls `Reveal.configure({transition, transitionSpeed, rtl})` based
    on `Display._theme.display_slide_transition` (song = disabled,
    image = enabled)
  - Every `Reveal.configure()` rewrites `dom.wrapper.data-background-transition`
    from the internal config (still `"fade"` since init default)

---

## Working hypotheses (ranked)

### H1 — Reveal background sync race (most likely)

The image item's per-slide `data-background-transition="fade"` is set
on the `<section>` before `replaceSlides` runs. `replaceSlides` appends
the section to `_slidesContainer` and calls `Reveal.sync()`.

Reveal's `syncBackground()` ([reveal.js:1157](../openlp/core/display/html/reveal.js#L1157))
builds the corresponding `.slide-background` wrapper element by cloning
attributes from the section. But if the **previous item (song)** left
the `.backgrounds` container with `<div>` background nodes that don't
carry `data-background-transition`, and reveal's internal
`backgroundsById` map is stale, Reveal might not regenerate them on the
first sync — especially if `Reveal.slide(currentSlide.h, currentSlide.v)`
is invoked before the new sections are fully wired.

On spam-click, each re-invocation of `load_images` re-runs
`setImageSlides` → `replaceSlides` → `Reveal.sync()`, eventually forcing
a full rebuild.

**Why only on output**: the output display is initialised with
`isDisplay=true` → `_doTransitions=true` unconditionally. The preview
takes the `allowThemeTransitions` path and its
`setAllowThemeTransitions` handler ([display.js:613](../openlp/core/display/html/display.js#L613))
calls `applyTheme` on the root slide again after each item switch — a
double application that the output doesn't perform.

**Next step**: compare `[DISPLAY]` vs `[preview]` logs — specifically
the `backgrounds:` field of `_logTransitionDebug` right after
`setImageSlides.post`. If the output shows `bgt=` empty for slides that
should be fading, this is confirmed.

### H2 — `Display._theme` not yet populated when `setImageSlides` runs

Qt serialises `runJavaScript` calls in submission order, so this should
be impossible in theory. But the `setTheme` handler runs in the JS
event loop, and there's a world where `setImageSlides` fires before the
`setTheme` microtask completes. The `setImageSlides.pre` log will prove
or disprove this:

- `themeSet=false` or `dst=null` → H2 confirmed
- `themeSet=true, dst=true` → H2 ruled out

**Fix if confirmed**: call `set_theme` with `is_sync=True` on the output
display path in slidecontroller.py, OR make `setImageSlides` a no-op
that queues until `Display._theme` is populated.

### H3 — Image load latency swallowing the transition

When a section with `data-background-image` is first shown, reveal's
background element loads the image async. If reveal kicks off the
opacity transition before the `<img>` has decoded, the fade happens
against an empty background (invisible). On spam-click the image is
cached and decodes synchronously from cache.

This would explain the "first click only" behaviour and why output
(full-resolution, potentially 4K images) is affected more than preview
(thumbnail-sized).

**Fix if confirmed**: preload the image in Python (send thumbnail first,
or preload via `<link rel="preload">`) before calling `setImageSlides`,
or wait one `requestAnimationFrame` after image decode before
triggering the transition.

### H4 — Reveal internal config drift on output only

Reveal's `configure()` rewrites `dom.wrapper.data-background-transition`
from `config.backgroundTransition`. Since the default was changed to
`"fade"` and `setItemTransition` no longer touches it, this should now
stay `"fade"` forever. **But** if any legacy code path still calls
`Reveal.configure({backgroundTransition: "none"})` — e.g. a leftover in
`updateItemTransitionSettings` or a plugin — the output wrapper could
get "none" while the preview doesn't.

The `_logTransitionDebug` enhancement shows both the reveal config
`backgroundTransition` value and the wrapper attribute. Compare
`[DISPLAY]` vs `[preview]` at the same step — divergence confirms H4.

---

## What the logs need to show (not yet collected)

The user was running the instrumented build but log output has not been
shared in this conversation. Ask the user to reproduce the bug (song →
image, one click only) with the Qt log console open, then paste every
line containing `transition debug`. The expected sequence:

```
[preview] setTheme dst=false type=0        <- song arrives (preview)
[DISPLAY] setTheme dst=false type=0        <- song arrives (output)
[preview] setImageSlides.pre themeSet=...  <- shouldn't appear for song (text)
...
(user clicks "Go live" on the image)
[preview] setTheme dst=true type=0
[DISPLAY] setTheme dst=true type=0
[preview] setImageSlides.pre themeSet=true dst=true useNativeBgImages=true ...
[preview] setImageSlides.post
[preview] applyTheme.configure enabled effect=none    <- note: "none" because image's reveal_transition is "none" with per-slide fade
[DISPLAY] setImageSlides.pre themeSet=??? dst=??? useNativeBgImages=???
[DISPLAY] setImageSlides.post
[DISPLAY] applyTheme.configure ...
```

Then compare the backgrounds summary in `_logTransitionDebug` between
preview and display for the key differences:

- `revealBackgroundTransition` — should be `"fade"` on both
- `wrapperBgTransitionAttr` — should be `"fade"` on both
- `backgrounds` — each entry should end with `bgt=fade`; an empty
  `bgt=` means reveal hasn't synced that slide background

---

## Suggested fix sketches (contingent on log evidence)

### If H1 (sync race)

Force a second `Reveal.sync()` one animation frame after `replaceSlides`
on the output display. Or call `Reveal.syncBackground()` explicitly for
each newly-appended section before `Reveal.slide()`.

```js
// in replaceSlides, after Reveal.slide/Reveal.sync:
requestAnimationFrame(function () {
  Reveal.sync();
});
```

### If H2 (theme-state race)

In [slidecontroller.py:1019](../openlp/core/ui/slidecontroller.py#L1019)
`_set_theme`, call the display with `is_sync=True` when it is the live
output:

```python
display.set_theme(theme_data,
                  is_sync=True if self.is_live else False,
                  service_item_type=...)
```

This blocks the Python side until the JS `setTheme` has run, guaranteeing
`Display._theme` is populated before `load_images` is submitted.
Trade-off: latency on item switch, but this is a single-frame cost.

### If H3 (image preload)

Send a preload hint before the slide data:

```js
// new display.js entry point
preloadSlideImages: function (paths) {
  paths.forEach(function (p) {
    var img = new Image();
    img.src = p;
  });
}
```

Call from Python before `load_images`; give it one `requestAnimationFrame`
on the JS side before `replaceSlides` runs.

### If H4 (config drift)

Grep for all `Reveal.configure` calls in display.js and ensure none
passes `backgroundTransition: "none"`. Add a unit test that asserts
the wrapper's `data-background-transition` attribute stays `"fade"`
across a song→image switch.

---

## Test plan once fixed

Manual reproduction:

1. Start OpenLP+ with a two-monitor setup.
2. Load a service with: song → image → song → image → PDF presentation.
3. Set the song theme transition to **off**; set image/PDF transitions to
   **fade**.
4. Go live on song #1, then click once on image #1. Observe the output
   monitor: fade should cross-fade from song's theme background to the
   image. **Must work on first click.**
5. Repeat with PDF: song → PDF. First click must cross-fade.
6. Repeat with preview pane visible; it should look identical to what
   worked before these changes.
7. Toggle `themes/item transitions` off globally — every switch must
   be an instant cut, no fade.
8. Run automated suite: `pytest tests/openlp_core/display
   tests/openlp_core/ui` (expected: 750 green).

Then **remove the diagnostic logging**:

- `Display._logTransitionDebug` calls added in `setTheme`,
  `setImageSlides.pre`, `setImageSlides.post`, `applyTheme.configure`
- The backgrounds/wrapper/config fields added to
  `_logTransitionDebug`'s payload (the base payload is fine to keep)
- `[DISPLAY]`/`[preview]` prefix in `handle_transition_debug` — decide
  whether to keep; useful for future debugging, low cost

---

## Open questions for the user

1. **Can you share the actual log output** from a reproduction run?
   Without the `[DISPLAY]` vs `[preview]` comparison we're triangulating
   blind.
2. When the bug occurs, does the output display show the image
   *instantly* (no fade) or does it show the song's last slide briefly
   before snapping to the image?
3. Does the bug reproduce for song → PDF the same way as song → image,
   or only for one of them?
4. Spam-click count: exactly 4-5, or variable? Consistent count points
   to a specific frame boundary; variable points to paint/image-load
   timing.

---

## Evidence from real repro log (`/Users/tyler/Downloads/openlp.log`)

User provided a reproduction log. Filtered to `[DISPLAY]` lines around
the song→image transition, key observations:

### First song→image click (DISPLAY)

| Line | Reason | rv | bgt | wrap | sc | revCls |
|-----:|--------|----|----|------|----|--------|
| 350 | `setTheme dst=true type=0` | **none** | fade | fade | 7 | `…has-dark-background none` |
| 353 | `setImageSlides.pre doTransitions=true useNativeBgImages=true` | **none** | fade | fade | 7 | `…has-dark-background none` |
| 354 | `applyTheme.configure enabled effect=fade` | **fade** | fade | fade | 7 | `…has-dark-background fade` |
| 385 | `setImageSlides.post` | fade | fade | fade | **8** | `…has-vertical-slides fade` |

### Second setImageSlides on DISPLAY (later)

| Line | Reason | rv | bgt | wrap | sc |
|-----:|--------|----|----|------|----|
| 479 | `setTheme dst=true type=0` | fade | fade | fade | 7 |
| 482 | `setImageSlides.pre` | fade | fade | fade | 7 |

### Critical finding: backgrounds count off by one

Line 385 (`setImageSlides.post`) reports `slideSectionCount: 8` but only
**7** `.backgrounds > .slide-background` entries. For 8 top-level
`<section>` elements there should be 8 backgrounds. Reveal.js's
`createBackgrounds()` (reveal.js:1069) is supposed to rebuild on every
`Reveal.sync()`, but the observed state is a single-element shortage
immediately after `replaceSlides` returns.

### Most likely root cause: `no-transition` race in Reveal.sync

Reveal.js `createBackgrounds()` (reveal.js:1069-1117):

```js
function createBackgrounds() {
  dom.background.innerHTML = '';               // wipe all
  dom.background.classList.add( 'no-transition' );  // suppress fade
  // …build backgrounds…
}
```

Then `updateBackground(true)` at the end (reveal.js:3713-3716) schedules:

```js
setTimeout( function() {
  dom.background.classList.remove( 'no-transition' );
}, 1 );
```

Our `Display.reinit()` runs:

```js
Reveal.sync();      // adds no-transition, schedules setTimeout(remove, 1)
Reveal.slide(0);    // fires BEFORE the 1ms setTimeout elapses
```

So the slide(0) change happens while `.backgrounds` still carries
`.no-transition`, which (via `reveal.css`
`.reveal .backgrounds.no-transition .slide-background { transition: none; }`)
forces the cross-fade to snap.

On subsequent clicks, something about the DOM state (likely the stale
section still present from the prior `_removeLastSection` setTimeout, or
the user's click timing relative to the 1ms setTimeout) lets the fade
through — consistent with the "spam click 4-5 times" workaround.

### Suggested fix (targeted)

In `display.js:replaceSlides`, the non-array branch should defer the
final `Reveal.slide(0)` until AFTER Reveal's own `setTimeout(1)` has
had a chance to clear `no-transition`:

```js
// current
Reveal.slide(1, currentSlide.v);
Display.reinit();                 // Reveal.sync() + Reveal.slide(0)
setTimeout(Display._removeLastSection, …);

// proposed
Reveal.slide(1, currentSlide.v);
Reveal.sync();
// Wait one task so Reveal's setTimeout(remove no-transition, 1) fires.
setTimeout(function () {
  Reveal.slide(0);
  setTimeout(Display._removeLastSection, …);
}, 16);  // next paint frame
```

Alternative (cheaper but same effect): explicitly remove the class
right before `Reveal.slide(0)`:

```js
Reveal.sync();
var backgrounds = document.querySelector('.reveal .backgrounds');
if (backgrounds) { backgrounds.classList.remove('no-transition'); }
Reveal.slide(0);
```

The second form is the minimal change and the one to try first.

### Next steps

1. Apply the targeted fix in `replaceSlides` (non-array branch).
2. Re-run the same reproduction and capture a fresh log.
3. Confirm `setImageSlides.post` now shows `slideSectionCount` ===
   backgrounds count AND the transition plays visually on the FIRST
   click after a song.
4. If backgrounds-count discrepancy persists, investigate whether the
   stale song `<section>` is being counted but not synced — may need
   to call `Display._removeLastSection()` *before* `Reveal.slide(0)`
   instead of on a setTimeout.
