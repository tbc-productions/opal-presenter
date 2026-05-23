# Analysis: Hide/Show Buttons and Transitions

Buttons analysed:
- **Show Presentation** (`show_screen` → `on_show_display` → `set_hide_mode(None)`)
- **Show Black** (`blank_screen` → `on_toggle_blank` → `HideMode.Blank` ↔ `None`)
- **Show Theme** (`theme_screen` → `on_toggle_theme` → `HideMode.Theme` ↔ `None`)
- **Show Logo** (`logo_screen` → `on_toggle_logo` → `HideMode.Logo` ↔ `None`)
- **Show Desktop** (`desktop_screen` → `on_toggle_desktop` → `HideMode.Screen` ↔ `None`)

Related setting: `themes/item transitions` (+ `themes/item transition speed`,
`themes/item transition type`). Toggles whether the fades used for hide / show
operations animate or happen instantly.

## Control flow

```
Toolbar action
 └── SlideController.on_toggle_*                 (slidecontroller.py)
      └── set_hide_mode(HideMode.*)
           └── Registry.execute('live_display_hide' | 'live_display_show')
                └── DisplayWindow.hide_display / show_display   (window.py)
                     └── run_in_display('toBlack'|'toTheme'|'toLogo'|'toTransparent'|'show')
                          └── Display.toBlack/toTheme/toLogo/toTransparent/show  (display.js)
```

## Layers involved in a hide/show operation

| Layer | Role |
| --- | --- |
| `body.opacity`              | 1 = display visible, 0 = Show Desktop |
| `.slides` / `.footer` opacity| 1 = content visible, 0 = hidden (Theme / Logo) |
| `#logo-screen.show`         | Logo overlay at z-index 4 |
| `.reveal .pause-overlay`    | Reveal-inserted black overlay at z-index 100 (used for Show Black) |
| `body.transition` class     | Enables CSS opacity transitions using `--item-transition-ms` / `--item-transition-easing` |
| `body.disable-transitions`  | Hard override that forces `transition: none` on all descendants (preview-window helper, and interim state during some JS operations) |

---

## Bugs / erratic behaviour identified

### 1. Show Black fade duration is hard-coded to 1 s

`Display.toBlack()` uses Reveal's built-in pause overlay for the black layer.
`reveal.css` declares `.reveal .pause-overlay { transition: all 1s ease; }`.
Because the overlay is not gated by our `body.transition` class, the fade
*always* takes one second, regardless of the user-configured transition speed
or whether item transitions are enabled at all. Every other mode honours
`--item-transition-ms`, so the Black fade looks slower and inconsistent with
the other buttons.

### 2. Show Black has a one-second fade even when item transitions are off (live)

For the **live** window we never set `body.disable-transitions` – we rely on
the absence of the `body.transition` class to keep opacity changes instant.
That works for the `body`, `.slides`, `.footer` and `#logo-screen` rules,
which are all scoped with `body.transition`. It does **not** work for the
pause overlay, whose transition comes unscoped from `reveal.css`. Net effect:
with transitions disabled, every mode snaps instantly *except* Black, which
still fades for one second.

### 3. Stale async callbacks corrupt state after rapid button presses

`Display._abortLastTransitionOperation()` only cancels:
- the last `requestAnimationFrame` handle, and
- the `transitionend` listener it stashed via `_addTransitionEndEventToBody`.

It does not cancel:
- The `transitionend` listener registered *directly* on `#logo-screen`
  in `toLogo.fadeLogoOverSlide()`.
- The 900 ms fallback `setTimeout` in `fadeLogoOverSlide()`.
- The image preloader `onload` / `onerror` in `toLogo`.

**Reproduction**: start in Show, click *Show Logo* (fade begins), and before
the logo is fully opaque click *Show Black*. The logo’s own `transitionend`
listener still fires, enters `hideSlideLayerAndResolve`, calls
`_setThemeBackgroundToLogo(…)` and sets `slidesContainer.opacity = 0`. You
end up in Black mode but with the theme background permanently overwritten
by the logo background, and `_logoBackgroundOverrideActive = true`, so the
next slide replacement thinks logo mode is active.

### 4. Logo background override leaks into Black and Desktop

`toTheme()` and `show()` call `_restoreThemeBackgroundFromLogo()` when leaving
logo mode. `toBlack()` and `toTransparent()` do not. The background overrides
applied to the root slide (`data-background-image`, `data-background-color`,
…) stay in place while the user is in Black or Desktop. When a new service
item is subsequently loaded (or when the user switches to Theme), the stale
override can re-apply itself via `_syncLogoOverrideAfterSlideReplacement()`.

### 5. Black ↔ Theme is an inconsistent hard cut (symptom of 1, 3)

`toTheme()` picks between a fade-lyrics path and an instant path based on
`wasPaused` (true when coming from Black / Logo / Desktop). Combined with
bug 1, that meant Black→Theme effectively did `slidesContainer.opacity=0
(instant)` and then waited for the 1 s pause-overlay fade. Users saw the
theme appear underneath the black overlay with a 1 s fade that does not
match any other button. With bugs 1 & 2 fixed the cross-fade timing
becomes consistent across all button combinations.

### 6. `_disable_preview_hide_transition()` asymmetry

The helper only returns `True` for preview windows. As a result live and
preview take different code paths when "item transitions" is off (live:
class-absence, preview: `disable-transitions` class). They happen to look
the same today, but the divergence is fragile.

---

## Fixes applied

### A. Correct pause-overlay transition (fixes 1, 2, 5)

`display.css` overrides `.reveal .pause-overlay` so it uses the same
`--item-transition-ms` / `--item-transition-easing` variables as the rest of
the hide/show system, *only* while `body.transition` is set, and is
cancelled by `body.disable-transitions`. The Show Black fade now matches
Show Theme / Show Logo / Show Desktop in duration and easing, and turning
the setting off produces an instant cut everywhere, consistently.

### B. Per-operation transition token (fixes 3)

`display.js` gains a monotonically-increasing `Display._transitionToken`.
Each of `toBlack`, `toTheme`, `toLogo`, `toTransparent`, `show` bumps it on
entry and captures the new value. Every async continuation (requestAnim
frame callbacks, `transitionend` handlers, `setTimeout` fallbacks and image
preloaders) checks the token before mutating state. Stale callbacks become
a no-op.

`_abortLastTransitionOperation()` now also:
- removes the logo `transitionend` listener if one is pending,
- clears the 900 ms fallback `setTimeout`,
- detaches the `onload`/`onerror` handlers from the logo image preloader.

### C. Always clear logo override when leaving Logo mode (fixes 4)

`toBlack()` and `toTransparent()` now call
`_restoreThemeBackgroundFromLogo()` at the top, the same way `toTheme()` and
`show()` already do. This guarantees the root slide's background attributes
are never left polluted by the logo override.

### D. Apply transition-disable symmetrically on live (fixes 6)

`window.py` now uses a single helper `_disable_hide_transition()` that
returns `True` whenever `themes/item transitions` is off, regardless of
live vs. preview. The JS side already honours the flag correctly for both
windows, so the only behavioural change is that the live window now also
carries the explicit `disable-transitions` class for the duration of a
transition, which brings it in line with the preview window and insulates
the behaviour from future additions of un-scoped CSS transitions.

---

## Verification

Unit tests pass (`pytest tests/openlp_core/display tests/openlp_core/ui`).
Manual regression tests performed:

1. Show ↔ Black, Show ↔ Theme, Show ↔ Logo, Show ↔ Desktop — all fade with
   the user-configured speed/easing.
2. Black ↔ Theme, Black ↔ Logo, Black ↔ Desktop, Theme ↔ Logo, Logo ↔
   Desktop — all cross-fade consistently. No flashes of previous state.
3. Rapid button tapping (5 buttons, 10 rapid clicks each) — final rendered
   state always matches the last-pressed button. No logo-background leaks.
4. Turning `themes/item transitions` off — every button now produces an
   instantaneous, consistent result.
5. Preview window behaves identically to live window in all of the above.
