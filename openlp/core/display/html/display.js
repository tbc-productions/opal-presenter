/**
 * display.js is the main Javascript file that is used to drive the display.
 */


/**
 * Background type enumeration
 */
var BackgroundType = {
  Transparent: "transparent",
  Solid: "solid",
  Gradient: "gradient",
  Video: "video",
  Image: "image",
  Stream: "stream"
};

/**
 * Gradient type enumeration
 */
var GradientType = {
  Horizontal: "horizontal",
  LeftTop: "leftTop",
  LeftBottom: "leftBottom",
  Vertical: "vertical",
  Circular: "circular"
};

/**
 * Horizontal alignment enumeration
 */
var HorizontalAlign = {
  Left: 0,
  Right: 1,
  Center: 2,
  Justify: 3
};

/**
 * Vertical alignment enumeration
 */
var VerticalAlign = {
  Top: 0,
  Middle: 1,
  Bottom: 2
};

/**
 * Transition type enumeration
 */
var TransitionType = {
  Fade: 0,
  Slide: 1,
  Convex: 2,
  Concave: 3,
  Zoom: 4
};

/**
 * Transition speed enumeration
 */
var TransitionSpeed = {
  Normal: 0,
  Fast: 1,
  Slow: 2
};


/**
 * Transition direction enumeration
 */
var TransitionDirection = {
  Horizontal: 0,
  Vertical: 1
};

/**
 * Audio state enumeration
 */
var AudioState = {
  Playing: "playing",
  Paused: "paused",
  Stopped: "stopped"
};

/**
 * Transition state enumeration
 */
var TransitionState = {
  EntranceTransition: "entranceTransition",
  NoTransition: "noTransition",
  ExitTransition: "exitTransition"
};

/**
 * Animation state enumeration
 */
var AnimationState = {
  NoAnimation: "noAnimation",
  ScrollingText: "scrollingText",
  NonScrollingText: "noScrollingText"
};

/**
 * Alert location enumeration
 */
var AlertLocation = {
  Top: 0,
  Middle: 1,
  Bottom: 2
};

/**
 * Alert state enumeration
 */
var AlertState = {
  Displaying: "displaying",
  NotDisplaying: "notDisplaying"
};

/**
 * Alert delay enumeration
 */
var AlertDelay = {
  FiftyMilliseconds: 50,
  OneSecond: 1000,
  OnePointFiveSeconds: 1500
};

/**
 * Map of horizontal aligns to their CSS names for the text-align property
 */
var HorizontalAlignCSS = {
  [HorizontalAlign.Justify]: "justify",
  [HorizontalAlign.Center]: "center",
  [HorizontalAlign.Left]: "left",
  [HorizontalAlign.Right]: "right",
};

/**
 * Map of vertical aligns to their CSS names for the justify-content property
 */
var VerticalAlignCSS = {
  [VerticalAlign.Top]: "flex-start",
  [VerticalAlign.Middle]: "center",
  [VerticalAlign.Bottom]: "flex-end"
};

/**
 * Return an array of elements based on the selector query
 * @param {string} selector - The selector to find elements
 * @returns {array} An array of matching elements
 */
function $(selector) {
  return Array.from(document.querySelectorAll(selector));
}

/**
 * Build linear gradient CSS
 * @private
 * @param {string} direction - The direction or angle of the gradient e.g. to bottom or 90deg
 * @param {string} startColor - The starting color
 * @param {string} endColor - The ending color
 * @returns {string} A string of the gradient CSS
 */
function _buildLinearGradient(direction, startColor, endColor) {
  return "linear-gradient(" + direction + ", " + startColor + ", " + endColor + ") fixed";
}

/**
 * Build radial gradient CSS
 * @private
 * @param {string} width - Width of the gradient
 * @param {string} startColor - The starting color
 * @param {string} endColor - The ending color
 * @returns {string} A string of the gradient CSS
 */
function _buildRadialGradient(width, startColor, endColor) {
  return "radial-gradient(" + startColor + ", " + endColor + ") fixed";
}

/**
 * Build a set of text shadows to form an outline
 * @private
 * @param {number} size - The desired width of the outline
 * @param {string} color - The color of the outline
 * @returns {Array} A list of shadows to be given to "text-shadow"
 */
function _buildTextOutline(size, color) {
  let shadows = [];
  // Outlines work from -(size) to +(size)
  let from = size * -1;
  // Loop through all the possible size iterations and add them to the array
  for (let i = from; i <= size; i++) {
    for (let j = from; j <= size; j++) {
      shadows.push(color + " " + i + "pt " + j + "pt 0pt");
    }
  }
  return shadows;
}

/**
 * Build a text shadow
 * @private
 * @param {number} offset - The offset of the shadow
 * @param {number} size - The desired width of the shadow
 * @param {string} color - The color that the shadow should be
 * @param {number} blur - The blur radius of the shadow
 * @returns {Array} A list of shadows to be given to "text-shadow"
 */
function _buildTextShadow(offset, size, color, blur) {
  let shadows = [];
  let from = (size * -1) + offset;
  let to = size + offset;
  let blurRadius = (typeof blur === "number") ? blur : 0;
  for (let i = from; i <= to; i++) {
    for (let j = from; j <= to; j++) {
      shadows.push(color + " " + i + "pt " + j + "pt " + blurRadius + "pt");
    }
  }
  return shadows;
}


/**
 * Get a style value from an element (computed or manual)
 * @private
 * @param {Object} element - The element whose style we want
 * @param {string} style - The name of the style we want
 * @returns {(Number|string)} The style value (type depends on the style)
 */
function _getStyle(element, style) {
  return document.defaultView.getComputedStyle(element).getPropertyValue(style);
}

/**
 * Convert newlines to <br> tags
 * @private
 * @param {string} text - The text to parse
 * @returns {string} The text now with <br> tags
 */
function _nl2br(text) {
  return text.replace("\r\n", "\n").replace("\n", "<br>");
}

/**
 * Prepare text by creating paragraphs and calling _nl2br to convert newlines to <br> tags
 * @private
 * @param {string} text - The text to parse
 * @returns {string} The text now with <p> and <br> tags
 */
function _prepareText(text) {
  return "<p>" + _nl2br(text) + "</p>";
}

/**
 * Coerce mixed persisted values into a boolean.
 * @private
 * @param {*} value - Input value from settings or payload
 * @returns {boolean} Normalised boolean
 */
function _coerceBoolean(value) {
  if (typeof value === "string") {
    var lowered = value.trim().toLowerCase();
    if (["false", "0", "no", "off", ""].includes(lowered)) {
      return false;
    }
    if (["true", "1", "yes", "on"].includes(lowered)) {
      return true;
    }
  }
  return !!value;
}

/**
 * Change a camelCaseString to a camel-case-string
 * @private
 * @param {string} text
 * @returns {string} the Un-camel-case-ified string
 */
function _fromCamelCase(text) {
  return text.replace(/([A-Z])/g, function (match, submatch) {
    return '-' + submatch.toLowerCase();
  });
}

/**
 * Convert theme background fit to reveal.js background attributes
 * @private
 * @param {string} fit - cover, contain, stretch, repeat
 * @returns {{size: string, repeat: string, position: string}} background attributes
 */
function _resolveBackgroundFit(fit) {
  switch (fit) {
    case "contain":
      return { size: "contain", repeat: "no-repeat", position: "50% 50%", objectFit: "contain" };
    case "stretch":
      return { size: "100% 100%", repeat: "no-repeat", position: "0% 0%", objectFit: "fill" };
    case "repeat":
      return { size: "auto", repeat: "repeat", position: "0% 0%", objectFit: "cover" };
    case "cover":
    default:
      return { size: "cover", repeat: "no-repeat", position: "50% 50%", objectFit: "cover" };
  }
}

/**
 * Apply an image as a full-slide background with the requested fit.
 * @private
 * @param {HTMLElement} section - The slide section to style
 * @param {string} backgroundColor - The background color to use behind the image
 * @param {string} imageUrl - The image URL to apply
 * @param {{size: string, repeat: string, position: string}} fit - Resolved fit settings
 */
function _applyFullscreenBackgroundImage(section, backgroundColor, imageUrl, fit) {
  section.innerHTML = "";
  section.removeAttribute("style");
  section.setAttribute("data-background-image", imageUrl);
  section.setAttribute("data-background-color", backgroundColor || "#000");
  section.setAttribute("data-background-size", fit.size);
  section.setAttribute("data-background-repeat", fit.repeat);
  section.setAttribute("data-background-position", fit.position);
  section.removeAttribute("data-background");
  // Reveal copies these attributes into a separate background element during
  // sync. Reused sections need that element updated too, or the old image
  // (often the startup splash) remains visible until another sync occurs.
  var background = section.slideBackgroundElement;
  var content = section.slideBackgroundContentElement;
  if (background && content) {
    background.style.backgroundColor = backgroundColor || "#000";
    content.style.backgroundImage = imageUrl ? "url(" + JSON.stringify(imageUrl) + ")" : "";
    content.style.backgroundSize = fit.size;
    content.style.backgroundRepeat = fit.repeat;
    content.style.backgroundPosition = fit.position;
  }
}

/**
 * Populate a slide <section> with an image using the structure appropriate for
 * the requested transition effect.
 *
 * When `useNativeBackground` is true the image is applied via reveal.js
 * `data-background-image` attributes so reveal natively cross-fades the
 * background between adjacent slides. Otherwise the image is rendered as an
 * `<img>` inside the section, which lets reveal's section transition (slide
 * / zoom / convex / concave) carry the image with the section. The source
 * URL is also stored on the section via `data-slide-image` so the structure
 * can be rebuilt at runtime (e.g. when PDF transition settings change).
 *
 * @private
 * @param {HTMLElement} section - The slide section to populate
 * @param {string} imageUrl - URL of the image to render
 * @param {boolean} useNativeBackground - Use reveal background vs <img>
 * @param {{size: string, repeat: string, position: string, objectFit: string}} fit
 * @param {string} [backgroundColor] - Colour to show behind the image (default #000)
 */
function _applyImageSlideContent(section, imageUrl, useNativeBackground, fit, backgroundColor) {
  var bgColor = backgroundColor || "#000";
  section.innerHTML = "";
  section.removeAttribute("style");
  section.removeAttribute("data-background");
  section.removeAttribute("data-background-image");
  section.removeAttribute("data-background-color");
  section.removeAttribute("data-background-size");
  section.removeAttribute("data-background-repeat");
  section.removeAttribute("data-background-position");
  section.setAttribute("data-slide-image", imageUrl);
  if (useNativeBackground) {
    section.setAttribute("data-background-image", imageUrl);
    section.setAttribute("data-background-color", bgColor);
    section.setAttribute("data-background-size", fit.size);
    section.setAttribute("data-background-repeat", fit.repeat);
    section.setAttribute("data-background-position", fit.position);
  } else {
    section.setAttribute("style", "height: 100%; width: 100%; background-color: " + bgColor + ";");
    var img = document.createElement("img");
    img.src = imageUrl;
    img.setAttribute("style", "width: 100%; height: 100%; margin: 0; object-fit: " + fit.objectFit + ";");
    section.appendChild(img);
  }
}

/**
 * Ensure the layout guide overlay exists.
 * @private
 * @returns {HTMLElement} Overlay element
 */
function _ensureLayoutGuideOverlay() {
  var overlay = $("#layout-guide-overlay")[0];
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "layout-guide-overlay";
    overlay.innerHTML = '<div id="layout-guide-main"></div><div id="layout-guide-footer"></div>';
    var reveal = $(".reveal")[0] || document.body;
    reveal.appendChild(overlay);
  }
  return overlay;
}

/**
 * Apply fit styling to reveal background elements after sync.
 * @private
 * @param {{size: string, repeat: string}} fit - Resolved fit settings
 */
function _applyBackgroundFitToRenderedSlides(fit) {
  var imageBackgrounds = new Set($(".reveal section.use-background-image").map(function (section) {
    return section.slideBackgroundElement;
  }));
  $(".reveal .slide-background").forEach(function (background) {
    // Image and PDF slides already carry their own fit, independent of the theme.
    if (imageBackgrounds.has(background)) {
      return;
    }
    var backgroundContent = background.querySelector(".slide-background-content");
    if (!backgroundContent) {
      return;
    }
    backgroundContent.style.backgroundSize = fit.size;
    backgroundContent.style.backgroundRepeat = fit.repeat;
    backgroundContent.style.backgroundPosition = fit.position;
  });
  Display._applyDesignBackgroundImages();
}

/**
 * Create a CSS style
 * @private
 * @param {string} selector - The selector for this style
 * @param {Object} rules - The rules to apply to the style
 */
function _createStyle(selector, rules) {
  var style;
  var id = selector.replace("#", "").replace(" .", "-").replace(".", "-").replace(" ", "_");
  if ($("style#" + id).length != 0) {
    style = $("style#" + id)[0];
  }
  else {
    style = document.createElement("style");
    document.getElementsByTagName("head")[0].appendChild(style);
    style.type = "text/css";
    style.id = id;
  }
  var rulesString = selector + " { ";
  for (var key in rules) {
    var ruleValue = rules[key];
    var ruleKey = _fromCamelCase(key);
    rulesString += "" + ruleKey + ": " + ruleValue + ";";
  }
  rulesString += " } ";
  if (style.styleSheet) {
    style.styleSheet.cssText = rulesString;
  }
  else {
    style.appendChild(document.createTextNode(rulesString));
  }
}

/**
 * Fixes font name to match CSS names.
 * @param {string} fontName Font Name
 * @returns Fixed Font Name
 */
function _fixFontName(fontName) {
  if (!fontName || (fontName == 'Sans Serif')) {
    return 'sans-serif';
  }

  return "'" + fontName + "'";
}

/**
 * The Display object is what we use from OpenLP+
 */
var Display = {
  /** @type {HTMLElement} */
  _slidesContainer: null,
  /** @type {HTMLElement} */
  _footerContainer: null,
  /** @type {HTMLElement} */
  _backgroundsContainer: null,
  /** @type {HTMLElement} */
  _logoScreen: null,
  /** @type {HTMLImageElement} */
  _logoScreenImage: null,
  _alerts: [],
  _slides: {},
  _alertSettings: {},
  _alertState: AlertState.NotDisplaying,
  _transitionState: TransitionState.NoTransition,
  _animationState: AnimationState.NoAnimation,
  _doTransitions: false,
  _doItemTransitions: false,
  _itemTransitionSpeedSeconds: 0.8,
  _itemTransitionType: "balanced",
  _skipNextTransition: false,
  _pendingItemSnapshot: null,
  _itemTransitionAnimation: null,
  _itemTransitionTimeout: null,
  _itemTransitionVersion: 0,
  _clearAfterNativeHandoff: false,
  _displayMode: 'show',
  _isInitialised: false,
  _initialisedSlidesContainer: null,
  _themeApplied: true,
  _isDisplayOutput: false,
  _itemTransitionsEnabledSetting: false,
  _textSlideDirection: TransitionDirection.Vertical,
  _textSlideReverse: false,
  _revealConfig: {
    margin: 0.0,
    minScale: 1.0,
    maxScale: 1.0,
    controls: false,
    progress: false,
    history: false,
    keyboard: false,
    overview: false,
    center: false,
    touch: false,
    help: false,
    transition: "none",
    backgroundTransition: "none",
    viewDistance: 9999,
    width: "100%",
    height: "100%"
  },
  _lastRequestAnimationFrameHandle: null,
  _previewTransitionTimeoutHandles: [],
  /*
    Every hide/show operation bumps _transitionToken on entry. Async
    continuations (requestAnimationFrame, transitionend, setTimeout, image
    preloaders) capture the value and check it before mutating state. When
    the user presses multiple hide/show buttons in quick succession, the
    superseded callbacks become no-ops instead of corrupting state.
  */
  _transitionToken: 0,
  _modeCompletionTimeout: null,
  _transparentFallbackTimeout: null,
  _pendingLogoPreloader: null,
  _suppressRevealConfigure: false,
  _pendingRevealConfig: null,

  /**
   * Start up reveal and do any other initialisation
   * @param {object} options - The initialisation options:
   *                           * {bool} isDisplay         - Is this a real display output
   *                           * {bool} doItemTransitions - Transition between service items
   *                           * {bool} showTransparency - Show checkerboard in non-output views (default true)
   *                           * {number} itemTransitionSpeed - Transition duration between service items in seconds
   *                           * {string} itemTransitionType - Transition easing type for service item transitions
   *                           * {bool} hideMouse         - Hide the cursor when hovering on this display
   */
  init: function (options) {
    // Set defaults for undefined values
    options = options || {};
    let isDisplay = _coerceBoolean(options.isDisplay);
    let doItemTransitions = _coerceBoolean(options.doItemTransitions);
    let allowThemeTransitions = _coerceBoolean(options.allowThemeTransitions);
    let itemTransitionSpeed = Number(options.itemTransitionSpeed);
    if (!Number.isFinite(itemTransitionSpeed) || itemTransitionSpeed <= 0) {
      itemTransitionSpeed = 0.8;
    }
    let itemTransitionType = Display._normaliseItemTransitionType(options.itemTransitionType);
    let hideMouse = options.hideMouse || false;
    if (options.slideNumbersInFooter) {
      Display._revealConfig.slideNumber = Display.setFooterSlideNumbers;
    }

    // Now continue to initialisation
    document.body.classList.toggle('checkerboard', !isDisplay && options.showTransparency !== false);
    if (hideMouse) {
      document.body.classList.add('hide-mouse');
    }
    Display._slidesContainer = $(".slides")[0];
    Display._footerContainer = $(".footer")[0];
    Display._backgroundsContainer = $(".backgrounds")[0];
    Display._logoScreen = $("#logo-screen")[0];
    Display._logoScreenImage = $("#logo-screen-image")[0];
    Display._isDisplayOutput = isDisplay;
    Display._doTransitions = isDisplay || allowThemeTransitions;
    Display._itemTransitionSpeedSeconds = itemTransitionSpeed;
    Display._itemTransitionType = itemTransitionType;
    Display._itemTransitionsEnabledSetting = doItemTransitions;
    var enableItemTransitions = Display._itemTransitionsEnabledSetting && Display._doTransitions;
    // Prevent duplicate Reveal wiring on repeated init calls in the same document lifecycle.
    var isSameSlidesContainer = !!Display._slidesContainer &&
      Display._initialisedSlidesContainer === Display._slidesContainer;
    if (Display._isInitialised && isSameSlidesContainer) {
      Display.setItemTransition(enableItemTransitions, itemTransitionSpeed, itemTransitionType);
      return;
    }
    Reveal.initialize(Display._revealConfig);
    Reveal.addEventListener('slidechanged', Display._onSlideChanged);
    Display._isInitialised = true;
    Display._initialisedSlidesContainer = Display._slidesContainer;
    Display.setItemTransition(enableItemTransitions, itemTransitionSpeed, itemTransitionType);
    displayWatcher.setInitialised(true);
  },
  /**
   * Reinitialise Reveal
   */
  reinit: function () {
    Reveal.sync();
    // Python expects to be on first page after reinit
    Reveal.slide(0);
  },
  /**
   * Enable/Disable item transitions
   */
  setItemTransition: function (enable, speedSeconds, transitionType) {
    Display._doItemTransitions = enable;
    if (Number.isFinite(speedSeconds) && speedSeconds > 0) {
      Display._itemTransitionSpeedSeconds = speedSeconds;
    }
    Display._itemTransitionType = Display._normaliseItemTransitionType(transitionType || Display._itemTransitionType);
    var transitionMs = Math.round(Display._itemTransitionSpeedSeconds * 1000);
    document.body.style.setProperty('--item-transition-ms', transitionMs + 'ms');
    document.body.style.setProperty('--item-transition-easing', Display._getTransitionEasing(Display._itemTransitionType));
    var body = $("body")[0];
    if (enable) {
      body.classList.add("transition");
    } else {
      body.classList.remove("transition");
      Display._cancelItemTransition();
    }
  },

  updateItemTransitionSettings: function (enable, speedSeconds, transitionType) {
    Display._itemTransitionsEnabledSetting = _coerceBoolean(enable);
    Display.setItemTransition(
      Display._itemTransitionsEnabledSetting && Display._doTransitions,
      speedSeconds,
      transitionType
    );
  },

  setAllowThemeTransitions: function (allowThemeTransitions) {
    Display._doTransitions = Display._isDisplayOutput || _coerceBoolean(allowThemeTransitions);
    Display.setItemTransition(
      Display._itemTransitionsEnabledSetting && Display._doTransitions,
      Display._itemTransitionSpeedSeconds,
      Display._itemTransitionType
    );
    var rootSlide = Display._getRootSlideSection();
    if (Display._theme && rootSlide) {
      Display.resetTheme();
    }
  },

  _getRevealTransitionSpeed: function (speedSeconds) {
    if (speedSeconds <= 0.75) {
      return "fast";
    }
    if (speedSeconds >= 1.2) {
      return "slow";
    }
    return "default";
  },

  _normaliseItemTransitionType: function (transitionType) {
    var validTypes = ["linear", "ease", "ease-in", "ease-out", "ease-in-out", "balanced"];
    if (typeof transitionType !== "string") {
      return "balanced";
    }
    return validTypes.includes(transitionType) ? transitionType : "balanced";
  },

  _getTransitionEasing: function (transitionType) {
    if (transitionType === "balanced") {
      return "cubic-bezier(0.4, 0, 0.2, 1)";
    }
    return transitionType;
  },

  _setPresentationSlideTransition: function (enabled, speedSeconds, transitionType) {
    var body = $("body")[0];
    if (!enabled) {
      body.classList.remove("presentation-slide-transition");
      return;
    }
    var durationSeconds = Number(speedSeconds);
    if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) {
      durationSeconds = 0.8;
    }
    var easing = Display._normaliseItemTransitionType(transitionType);
    var ms = Math.round(durationSeconds * 1000) + 'ms';
    body.classList.add("presentation-slide-transition");
    body.style.setProperty('--presentation-slide-transition-ms', ms);
    body.style.setProperty('--presentation-slide-transition-easing', Display._getTransitionEasing(easing));
  },

  _getPresentationTransitionEffect: function (effect) {
    switch (effect) {
      case TransitionType.Slide:
      case "slide":
        return "slide";
      case TransitionType.Convex:
      case "convex":
        return "convex";
      case TransitionType.Concave:
      case "concave":
        return "concave";
      case TransitionType.Zoom:
      case "zoom":
        return "zoom";
      case TransitionType.Fade:
      case "fade":
      default:
        return "fade";
    }
  },

  _getPresentationTransitionName: function (effect) {
    return Display._getPresentationTransitionEffect(effect) + "-horizontal";
  },

  _normaliseThemeTransitionType: function (transitionType) {
    if (typeof transitionType === "number") {
      return transitionType;
    }
    if (typeof transitionType === "string") {
      var lowered = transitionType.toLowerCase();
      switch (lowered) {
        case "fade":
          return TransitionType.Fade;
        case "slide":
          return TransitionType.Slide;
        case "convex":
          return TransitionType.Convex;
        case "concave":
          return TransitionType.Concave;
        case "zoom":
          return TransitionType.Zoom;
      }
      var asNumber = Number(transitionType);
      if (Number.isFinite(asNumber)) {
        return asNumber;
      }
    }
    return TransitionType.Fade;
  },

  _normaliseThemeTransitionSpeed: function (transitionSpeed) {
    if (typeof transitionSpeed === "number") {
      return transitionSpeed;
    }
    if (typeof transitionSpeed === "string") {
      var lowered = transitionSpeed.toLowerCase();
      switch (lowered) {
        case "normal":
          return TransitionSpeed.Normal;
        case "fast":
          return TransitionSpeed.Fast;
        case "slow":
          return TransitionSpeed.Slow;
      }
      var asNumber = Number(transitionSpeed);
      if (Number.isFinite(asNumber)) {
        return asNumber;
      }
    }
    return TransitionSpeed.Normal;
  },

  _normaliseThemeTransitionDirection: function (transitionDirection) {
    if (typeof transitionDirection === "number") {
      return transitionDirection;
    }
    if (typeof transitionDirection === "string") {
      var lowered = transitionDirection.toLowerCase();
      switch (lowered) {
        case "horizontal":
          return TransitionDirection.Horizontal;
        case "vertical":
          return TransitionDirection.Vertical;
      }
      var asNumber = Number(transitionDirection);
      if (Number.isFinite(asNumber)) {
        return asNumber;
      }
    }
    return TransitionDirection.Horizontal;
  },

  _normaliseThemeTransitionReverse: function (isReverse) {
    if (typeof isReverse === "string") {
      return isReverse.toLowerCase() === "true";
    }
    return !!isReverse;
  },
  /**
   * Clear the current list of slides
  */
  clearSlides: function () {
    Display._slidesContainer.innerHTML = "";
    Display._clearSlidesList();
  },
  /**
   * Clear the current list of slides
  */
  _clearSlidesList: function () {
    Display._captureItemTransition();
    Display._footerContainer.innerHTML = "";
    Display._slides = {};
  },
  /**
   * Add new item/slides, replacing the old one
   * Clears current list of slides but allows time for a transition animation
   * The outgoing rendered frame is kept separately until the item fade completes.
   * @param {element} new_slides - New slides to display
   * @param {element} is_text - Used to decide if the theme main area constraints should apply
  */
  replaceSlides: function (new_slides, is_text=false) {
    Display._clearAfterNativeHandoff = false;
    Display._captureItemTransition();
    var sections = Array.isArray(new_slides) ? new_slides : [new_slides];
    Display._slidesContainer.replaceChildren(...sections);
    Display._suppressRevealConfigure = true;
    Display._pendingRevealConfig = null;
    try {
      sections.forEach(function (section) { Display.applyTheme(section, is_text); });
    } finally {
      Display._suppressRevealConfigure = false;
    }
    if (Display._pendingRevealConfig) {
      Reveal.configure(Display._pendingRevealConfig);
      Display._pendingRevealConfig = null;
    }
    Display.reinit();
    if (is_text) {
      Display._reapplyTextThemeAfterLayout(new_slides);
    }
    Display._skipNextTransition = false;
    Display._syncOutputModeAfterSlideReplacement();
    Display._playItemTransition();
  },

  /**
   * Keep the outgoing rendered item independent of Reveal's new slide layout,
   * theme and indices. Freeze visible styles so an interrupted fade can become
   * the next transition's starting frame. Hidden slides are not copied.
   */
  _captureItemTransition: function () {
    if ((Display._pendingItemSnapshot && !Display._itemTransitionAnimation) ||
        !Display._doItemTransitions || Display._skipNextTransition ||
        !Display._slidesContainer || !Display._slidesContainer.children.length) {
      return;
    }
    var reveal = Display._slidesContainer.closest('.reveal');
    if (!reveal || Reveal.isPaused() || document.body.classList.contains('is-desktop') ||
        (Display._displayMode === 'logo')) {
      return;
    }
    function copyVisible(element) {
      var style = getComputedStyle(element);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0 ||
          element.classList.contains('pause-overlay')) {
        return null;
      }
      if (element.tagName === 'AUDIO') {
        return null;
      }
      var copy;
      if (element.tagName === 'VIDEO' || element.tagName === 'CANVAS') {
        copy = document.createElement('canvas');
        copy.width = element.videoWidth || element.width || element.clientWidth;
        copy.height = element.videoHeight || element.height || element.clientHeight;
        try {
          copy.getContext('2d').drawImage(element, 0, 0, copy.width, copy.height);
        } catch (error) {
          // An undecoded video has no frame to preserve yet.
        }
      } else {
        copy = element.cloneNode(false);
      }
      copy.removeAttribute('id');
      // Reveal and theme updates select by class. A frozen frame must not
      // become another navigable deck or receive the next item's styling.
      copy.removeAttribute('class');
      // Inline the rendered frame; later theme rules must not restyle it.
      for (var property of style) {
        copy.style.setProperty(property, style.getPropertyValue(property), 'important');
      }
      copy.style.setProperty('transition', 'none', 'important');
      copy.style.setProperty('animation', 'none', 'important');
      copy.style.setProperty('pointer-events', 'none', 'important');
      Array.from(element.childNodes).forEach(function (child) {
        var childCopy = child.nodeType === Node.ELEMENT_NODE ? copyVisible(child) : child.cloneNode(true);
        if (childCopy) {
          copy.appendChild(childCopy);
        }
      });
      return copy;
    }
    var snapshot = document.createElement('div');
    snapshot.className = 'display-item-snapshot';
    snapshot.setAttribute('aria-hidden', 'true');
    Array.from(reveal.children).forEach(function (child) {
      var copy = copyVisible(child);
      if (copy) {
        snapshot.appendChild(copy);
      }
    });
    Display._cancelItemTransition();
    reveal.appendChild(snapshot);
    Display._pendingItemSnapshot = snapshot;
  },

  _cancelItemTransition: function () {
    Display._itemTransitionVersion += 1;
    clearTimeout(Display._itemTransitionTimeout);
    if (Display._itemTransitionAnimation) {
      Display._itemTransitionAnimation.cancel();
      Display._itemTransitionAnimation = null;
    }
    if (Display._pendingItemSnapshot) {
      Display._pendingItemSnapshot.remove();
      Display._pendingItemSnapshot = null;
    }
  },

  _playItemTransition: function () {
    var snapshot = Display._pendingItemSnapshot;
    if (!snapshot) {
      return;
    }
    var version = ++Display._itemTransitionVersion;
    // Selection of the requested starting slide follows replaceSlides in the
    // same event-loop turn. Start after it and after the new layout is painted.
    Display._itemTransitionTimeout = setTimeout(async function () {
      await Display._waitForSlideImages();
      if (Display._pendingItemSnapshot !== snapshot || version !== Display._itemTransitionVersion) {
        return;
      }
      var animation = snapshot.animate([{opacity: 1}, {opacity: 0}], {
        duration: Display._itemTransitionSpeedSeconds * 1000,
        easing: Display._getTransitionEasing(Display._itemTransitionType),
        fill: 'forwards'
      });
      Display._itemTransitionAnimation = animation;
      animation.onfinish = function () {
        if (Display._pendingItemSnapshot === snapshot) {
          Display._cancelItemTransition();
        }
      };
    }, 0);
  },

  _waitForSlideImages: function () {
    var slide = Reveal.getCurrentSlide();
    if (!slide) {
      return Promise.resolve();
    }
    var urls = Array.from(slide.querySelectorAll('img[src]')).map(function (image) { return image.src; });
    for (var section = slide; section && section.tagName === 'SECTION'; section = section.parentElement) {
      var url = section.getAttribute('data-background-image');
      if (url) {
        urls.push(url);
      }
    }
    return Promise.all(Array.from(new Set(urls)).map(function (url) {
      return new Promise(function (resolve) {
        var image = new Image();
        var timeout;
        function finish() {
          clearTimeout(timeout);
          image.onload = null;
          image.onerror = null;
          resolve();
        }
        // A failed or unresponsive source must not leave the old item covering
        // the output indefinitely. Ordinary local images finish on load/decode.
        timeout = setTimeout(finish, 3000);
        image.onload = function () {
          if (image.decode) {
            image.decode().then(finish, finish);
          } else {
            finish();
          }
        };
        image.onerror = finish;
        image.src = url;
      });
    }));
  },

  /**
   * Re-apply text theme styles after Reveal completes its layout pass.
   * A double requestAnimationFrame ensures we run after Reveal's own frame work.
   * @param {HTMLElement|HTMLElement[]} target - Text slide element(s) to style
   */
  _reapplyTextThemeAfterLayout: function (target) {
    var targets = target;
    if (!targets) {
      targets = Display._collectTextThemeTargets();
    }
    if (!targets || (Array.isArray(targets) && !targets.length)) {
      return;
    }

    var applyAll = function () {
      Display._suppressRevealConfigure = true;
      Display._pendingRevealConfig = null;
      try {
        if (Array.isArray(targets)) {
          targets.forEach(function (element) {
            Display.applyTheme(element, true);
          });
        } else {
          Display.applyTheme(targets, true);
        }
      } finally {
        Display._suppressRevealConfigure = false;
      }
      Display._pendingRevealConfig = null;
    };

    // Apply once immediately to avoid a first-frame flash at 0,0.
    applyAll();

    // Apply again after Reveal finishes layout/reflow frames.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        applyAll();
      });
    });
  },

  /**
   * Find all text slide theme targets currently in the deck.
   * For vertical text transitions this is the stack root (`section.text-slides`),
   * while horizontal text transitions use top-level sections.
   * @returns {HTMLElement[]} Theme targets for text slides
   */
  _collectTextThemeTargets: function () {
    var stackRoots = $("section.text-slides");
    if (stackRoots.length) {
      return stackRoots;
    }
    return $(".reveal .slides > section")
      .filter(function (section) {
        if (section.classList.contains("stack")) {
          return false;
        }
        if (section.classList.contains("use-background-image")) {
          return false;
        }
        return !!section._setImage || !!section.querySelector("p");
      });
  },

  _resolveTextSlideLayout: function () {
    var transitionDirection = TransitionDirection.Vertical;
    if (Display._theme && Display._theme.display_slide_transition_direction !== undefined &&
      Display._theme.display_slide_transition_direction !== null) {
      transitionDirection = Display._normaliseThemeTransitionDirection(Display._theme.display_slide_transition_direction);
    }
    var isReverse = Display._theme ?
      Display._normaliseThemeTransitionReverse(Display._theme.display_slide_transition_reverse) : false;
    return {
      direction: transitionDirection,
      isHorizontal: transitionDirection === TransitionDirection.Horizontal,
      isVertical: transitionDirection === TransitionDirection.Vertical,
      isReverse: isReverse
    };
  },

  _getCurrentTextSlideIndex: function () {
    var currentSlide = Reveal.getIndices();
    if (!currentSlide) {
      return 0;
    }
    return Display._textSlideDirection === TransitionDirection.Horizontal ? (currentSlide.h || 0) : (currentSlide.v || 0);
  },
  /**
   * Checks if the present slide content fits within the slide
  */
  doesContentFit: function () {
    // The theme main-area dimensions (width/height/top/left) are applied to
    // .slide-text-content by applyTheme, so measure that element directly.
    var contentEls = $(".slide-text-content");
    var target = contentEls.length > 0 ? contentEls[0] : Display._footerContainer;
    return target.clientHeight >= target.scrollHeight;
  },
  /**
   * Return render details for preview diagnostics.
   */
  getPreviewRenderState: function () {
    var currentSlide = Reveal.getCurrentSlide();
    var paragraph = currentSlide ? currentSlide.querySelector("p") : null;
    var textSample = paragraph ? (paragraph.innerText || "").slice(0, 40) : "";
    var backgroundElement = $(".reveal .slide-background.present .slide-background-content")[0];
    var backgroundImage = backgroundElement ? (backgroundElement.style.backgroundImage || "") : "";
    return {
      themeApplied: Display._themeApplied,
      backgroundImage: backgroundImage,
      textSample: textSample
    };
  },
  /**
   * Generate the OpenLP+ startup splashscreen
   * @param {string} bg_color - The background color
   * @param {string} image - Path to the splash image
   * @param {string} logo_fit - cover, contain, stretch, repeat
   */
  setStartupSplashScreen: function(bg_color, image, logo_fit) {
    Display._setPresentationSlideTransition(false);
    Display._clearSlidesList();
    var section = document.createElement("section");
    section.setAttribute("id", 0);
    section.setAttribute("data-background", bg_color || "#000");
    section.setAttribute("style", "height: 100%; width: 100%;");
    if (image) {
      var fit = _resolveBackgroundFit(logo_fit || "cover");
      _applyFullscreenBackgroundImage(section, bg_color, Display._getFileUrl(image), fit);
    }
    Display._slides['0'] = 0;
    Display.replaceSlides(section);
  },
  /**
   * Set fullscreen image from path
   * @param {string} bg_color - The background color
   * @param {string} image - Path to the image
   */
  setFullscreenImage: function(bg_color, image) {
    Display._setPresentationSlideTransition(false);
    var fit = _resolveBackgroundFit((Display._theme && Display._theme.background_fit) || "cover");
    var imageUrl = Display._getFileUrl(image);
    var existingSection = Display._getReusableFullscreenSection();
    if (existingSection) {
      existingSection.setAttribute("data-background", bg_color);
      _applyFullscreenBackgroundImage(existingSection, bg_color, imageUrl, fit);
      Reveal.syncSlide(existingSection);
      return;
    }
    Display.clearSlides();
    var section = document.createElement("section");
    section.setAttribute("id", 0);
    section.setAttribute("data-background", bg_color);
    _applyFullscreenBackgroundImage(section, bg_color, imageUrl, fit);
    Display._slides['0'] = 0;
    Display.replaceSlides(section);
  },
  /**
   * Set fullscreen image from base64 data
   * @param {string} bg_color - The background color
   * @param {string} image_data - base64 encoded image data
   */
  setFullscreenImageFromData: function(bg_color, image_data) {
    Display._setPresentationSlideTransition(false);
    var dataUri = 'data:image/jpeg;base64,' + image_data;
    var fit = _resolveBackgroundFit((Display._theme && Display._theme.background_fit) || "cover");
    var existingSection = Display._getReusableFullscreenSection();
    if (existingSection) {
      existingSection.setAttribute("data-background", bg_color);
      _applyFullscreenBackgroundImage(existingSection, bg_color, dataUri, fit);
      Reveal.syncSlide(existingSection);
      return;
    }
    Display.clearSlides();
    var section = document.createElement("section");
    section.setAttribute("id", 0);
    section.setAttribute("data-background", bg_color);
    _applyFullscreenBackgroundImage(section, bg_color, dataUri, fit);
    Display._slides['0'] = 0;
    Display.replaceSlides(section);
  },
  /**
   * Return existing fullscreen image section if current content matches expected single image layout.
   */
  _getReusableFullscreenSection: function() {
    if (!Display._slidesContainer || Display._slidesContainer.children.length !== 1) {
      return null;
    }
    if (Object.keys(Display._slides).length !== 1 || !Object.prototype.hasOwnProperty.call(Display._slides, '0')) {
      return null;
    }
    var section = Display._slidesContainer.children[0];
    if (!section || section.tagName !== 'SECTION') {
      return null;
    }
    return section;
  },
  /**
   * Display an alert. If there's an alert already showing, add this one to the queue
   * @param {string} text - The alert text
   * @param {Object} JSON object - The settings for the alert object
  */
  alert: function (text, settings) {
    if (text == "") {
      return null;
    }
    if (Display._alertState === AlertState.Displaying) {
      Display.addAlertToQueue(text, settings);
    }
    else {
      Display.showAlert(text, settings);
    }
  },
  /**
   * Show the alert on the screen
   * @param {string} text - The alert text
   * @param {Object} JSON object - The settings for the alert
  */
  showAlert: function (text, settings) {
    var alertBackground = $('#alert-background')[0];
    var alertText = $('#alert-text')[0];
    // create styles for the alerts from the settings
    _createStyle("#alert-background.settings", {
      backgroundColor: settings.backgroundColor,
      fontFamily: _fixFontName(settings.fontFace),
      fontSize: settings.fontSize.toString() + "pt",
      color: settings.fontColor
    });
    alertBackground.classList.add("settings");
    alertBackground.classList.replace("hide", "show");
    alertText.innerHTML = text;
    Display.setAlertLocation(settings.location);
    Display._transitionState = TransitionState.EntranceTransition;
    /* Check if the alert is a queued alert */
    if (Display._alertState !== AlertState.Displaying) {
      Display._alertState = AlertState.Displaying;
    }
    alertBackground.addEventListener('transitionend', Display.alertTransitionEndEvent, false);
    alertText.addEventListener('animationend', Display.alertAnimationEndEvent, false);
    /* Either scroll the alert, or make it disappear at the end of its time */
    if (settings.scroll) {
      Display._animationState = AnimationState.ScrollingText;
      alertText.classList.add('scrolling');
      alertText.classList.replace("hide", "show");
      var animationSettings = "alert-scrolling-text " + settings.timeout +
                              "s linear 0.6s " + settings.repeat + " normal";
      alertText.style.animation = animationSettings;
    }
    else {
      Display._animationState = AnimationState.NonScrollingText;
      alertText.classList.replace("hide", "show");
      setTimeout (function () {
        Display._animationState = AnimationState.NoAnimation;
        Display.hideAlert();
      }, settings.timeout * AlertDelay.OneSecond);
    }
  },
  /**
   * Hide the alert at the end
   */
  hideAlert: function () {
    var alertBackground = $('#alert-background')[0];
    var alertText = $('#alert-text')[0];
    Display._transitionState = TransitionState.ExitTransition;
    alertText.classList.replace("show", "hide");
    alertBackground.classList.replace("show", "hide");
    alertText.style.animation = "";
    Display._alertState = AlertState.NotDisplaying;
  },
  /**
   * Add an alert to the alert queue
   * @param {string} text - The alert text to be displayed
   * @param {Object} setttings - JSON object containing the settings for the alert
   */
  addAlertToQueue: function (text, settings) {
    Display._alerts.push({text: text, settings: settings});
  },
  /**
   * The alertTransitionEndEvent called after a transition has ended
   */
  alertTransitionEndEvent: function (e) {
    e.stopPropagation();
    if (Display._transitionState === TransitionState.EntranceTransition) {
      Display._transitionState = TransitionState.NoTransition;
    }
    else if (Display._transitionState === TransitionState.ExitTransition) {
      Display._transitionState = TransitionState.NoTransition;
      Display.hideAlert();
      Display.showNextAlert();
    }
  },
  /**
   * The alertAnimationEndEvent called after an animation has ended
   */
  alertAnimationEndEvent: function (e) {
    e.stopPropagation();
    Display.hideAlert();
  },
  /**
   * Set the location of the alert
   * @param {int} location - Integer number with the location of the alert on screen
   */
  setAlertLocation: function (location) {
    var alertContainer = $(".alert-container")[0];
    // Remove an existing location classes
    alertContainer.classList.remove("top");
    alertContainer.classList.remove("middle");
    alertContainer.classList.remove("bottom");
    // Apply the location class we want
    switch (location) {
      case AlertLocation.Top:
        alertContainer.classList.add("top");
        break;
      case AlertLocation.Middle:
        alertContainer.classList.add("middle");
        break;
      case AlertLocation.Bottom:
      default:
        alertContainer.classList.add("bottom");
        break;
    }
  },
  /**
  * Display the next alert in the queue
  */
  showNextAlert: function () {
    if (Display._alerts.length > 0) {
      var alertObject = Display._alerts.shift();
      Display._alertState = AlertState.DisplayingFromQueue;
      Display.showAlert(alertObject.text, alertObject.settings);
    }
    else {
      // For the tests
      return null;
    }
  },
  /**
   * Create a text slide.
   * @param {string} verse - The verse number, e.g. "v1"
   * @param {string} text - The HTML for the verse, e.g. "line1<br>line2"
   */
  _createTextSlide: function (verse, text) {
    var slide;
    var html = _prepareText(text);
    slide = document.createElement("section");
    slide.setAttribute("id", verse);
    // The "future" class is used internally by reveal, it's used here to hide newly added slides
    slide.classList.add("future");
    // Marks lyric text sections so theme main-area CSS (position/size) applies for horizontal slides too
    slide.classList.add("text-slide");
    var content = document.createElement("div");
    content.classList.add("slide-text-content");
    content.innerHTML = html;
    slide.appendChild(content);
    return slide;
  },

  _onSlideChanged: function(event) {
    Display._footerContainer.querySelectorAll('.footer-item')
      .forEach(footerItem => footerItem.classList.remove('active'));
    var currentSlideNth = parseInt(event.currentSlide.getAttribute('data-slide'));
    var newActiveFooter = Display._footerContainer.querySelector('.footer-item[data-slide="' + currentSlideNth + '"]');

    if (newActiveFooter) {
      newActiveFooter.classList.add('active');
    }

    // Reveal updates section positioning during slide changes; keep themed text positions stable.
    Display._reapplyTextThemeAfterLayout();
  },

  /**
   * Set text slides.
   * @param {Object[]} slides - A list of slides to add as JS objects: {"verse": "v1", "text": "line 1\nline2"}
   */
  setTextSlides: function (slides) {
    Display._setPresentationSlideTransition(false);
    Display._clearSlidesList();
    var layout = Display._resolveTextSlideLayout();
    Display._textSlideDirection = layout.direction;
    Display._textSlideReverse = layout.isReverse;
    var slide_html;
    var renderedSlides = slides.slice();
    if (layout.isVertical && layout.isReverse) {
      renderedSlides.reverse();
    }
    var parentSection = null;
    var topLevelSlides = [];
    if (layout.isVertical) {
      parentSection = document.createElement("section");
      parentSection.classList = "text-slides";
    }
    renderedSlides.forEach(function (slide, index) {
      slide_html = Display._createTextSlide(slide.verse, slide.text);
      slide_html._slideTheme = slide.theme || null;
      slide_html._setImage = slide.set_image || null;
      slide_html.setAttribute('data-slide', index);
      if (layout.isVertical) {
        parentSection.appendChild(slide_html);
        Display._slides[slide.verse] = index;
      } else {
        topLevelSlides.push(slide_html);
        Display._slides[slide.verse] = {h: index, v: 0};
      }
      if (slide.footer) {
        var footerSlide = document.createElement('div');
        footerSlide.classList.add('footer-item');
        footerSlide.setAttribute('data-slide', index);
        var currentSlide = Display._getCurrentTextSlideIndex();
        if (index == currentSlide) {
          footerSlide.classList.add('active');
        }
        footerSlide.innerHTML = slide.footer;
        Display._footerContainer.append(footerSlide);
      }
    });
    if (layout.isVertical) {
      Display.replaceSlides(parentSection, true);
    } else {
      Display.replaceSlides(topLevelSlides, true);
    }
  },
  /**
   * Set a single text slide. This changes the slide with no transition.
   * Prevents the need to reapply the theme if only changing content.
   * @param String slide - Text to put on the slide
   */
  setTextSlide: function (text) {
    Display._clearAfterNativeHandoff = false;
    Display._setPresentationSlideTransition(false);
    var layout = Display._resolveTextSlideLayout();
    Display._textSlideDirection = layout.direction;
    Display._textSlideReverse = layout.isReverse;
    if (Display._slides.hasOwnProperty("test-slide") && Object.keys(Display._slides).length === 1) {
      var slide = $("#" + "test-slide")[0];
      var html = _prepareText(text);
      if (slide.innerHTML != html) {
        slide.innerHTML = html;
      }
      if (!Display._themeApplied) {
        if (layout.isVertical && slide.parentElement) {
          Display.applyTheme(slide.parentElement, true);
        } else {
          Display.applyTheme(slide, true);
        }
        Display._syncOutputModeAfterSlideReplacement();
      }
    } else {
      Display._clearSlidesList();
      var slide_html;
      slide_html = Display._createTextSlide("test-slide", text);
      slide_html.setAttribute('data-slide', 0);
      Display._slides["test-slide"] = layout.isHorizontal ? {h: 0, v: 0} : 0;
      Display._slidesContainer.innerHTML = "";
      if (layout.isVertical) {
        var parentSection = document.createElement("section");
        parentSection.classList = "text-slides";
        parentSection.appendChild(slide_html);
        Display.applyTheme(parentSection, true);
        Display._slidesContainer.prepend(parentSection);
      } else {
        Display.applyTheme(slide_html, true);
        Display._slidesContainer.prepend(slide_html);
      }
      Display.reinit();
      Display._syncOutputModeAfterSlideReplacement();
    }
  },
  /**
   * Set image slides
   * @param {Object[]} slides - A list of images to add as JS objects [{"path": "url/to/file"}]
   * @param {string} imageFitMode - contain (default), cover or stretch
   * @param {string} backgroundColor - Logo background colour for image margins
   */
  setImageSlides: function (slides, imageFitMode, backgroundColor) {
    Display._clearSlidesList();
    var parentSection = document.createElement("section");
    var imageFit = _resolveBackgroundFit(
      ["contain", "cover", "stretch"].includes(imageFitMode) ? imageFitMode : "contain"
    );
    var themeTransitionType = TransitionType.Fade;
    var themeTransitionsEnabled = false;
    if (Display._theme) {
      themeTransitionType = Display._normaliseThemeTransitionType(Display._theme.display_slide_transition_type);
      themeTransitionsEnabled = !!Display._theme.display_slide_transition;
    }
    var useNativeBackgroundForImageSlides = themeTransitionsEnabled && themeTransitionType === TransitionType.Fade;
    var hasPdfBackgroundSlides = slides.some(function (slide) {
      return !!slide.use_background_image;
    });
    if (hasPdfBackgroundSlides) {
      var firstPdfSlide = slides.find(function (slide) {
        return !!slide.use_background_image;
      });
      Display._setPresentationSlideTransition(
        !!firstPdfSlide.pdf_transition_enabled,
        firstPdfSlide.pdf_transition_speed_seconds,
        firstPdfSlide.pdf_transition_easing
      );
    } else {
      Display._setPresentationSlideTransition(false);
      // The stack background stays in place while individual image sections
      // move during slide/zoom transitions, filling the exposed canvas.
      parentSection.setAttribute("data-image-canvas-color", backgroundColor || "#000");
      parentSection.setAttribute("data-background", backgroundColor || "#000");
      parentSection.setAttribute("data-background-color", backgroundColor || "#000");
    }
    slides.forEach(function (slide, index) {
      var section = document.createElement("section");
      section.setAttribute("id", index);
      section.setAttribute('data-slide', index);
      section.classList.add("use-background-image");
      var imageUrl = Display._getFileUrl(slide.path);
      if (slide.use_background_image) {
        var pdfFit = _resolveBackgroundFit((Display._theme && Display._theme.background_fit) || "cover");
        var pdfEffect = Display._getPresentationTransitionEffect(slide.pdf_transition_effect);
        var useNativeBackgroundForPdfSlides = !!slide.pdf_transition_enabled && pdfEffect === "fade";
        _applyImageSlideContent(section, imageUrl, useNativeBackgroundForPdfSlides, pdfFit);
        if (useNativeBackgroundForPdfSlides) {
          section.setAttribute("data-transition", "none");
          section.setAttribute("data-background-transition", "fade");
          section.setAttribute("data-transition-speed",
            Display._getRevealTransitionSpeed(slide.pdf_transition_speed_seconds));
        } else if (slide.pdf_transition_enabled) {
          section.setAttribute("data-transition",
            Display._getPresentationTransitionName(slide.pdf_transition_effect));
          section.setAttribute("data-transition-speed",
            Display._getRevealTransitionSpeed(slide.pdf_transition_speed_seconds));
        } else {
          section.setAttribute("data-transition", "none");
        }
      } else {
        _applyImageSlideContent(section, imageUrl, useNativeBackgroundForImageSlides, imageFit, backgroundColor);
        if (useNativeBackgroundForImageSlides) {
          section.setAttribute("data-transition", "none");
          section.setAttribute("data-background-transition", "fade");
        }
      }
      parentSection.appendChild(section);
      Display._slides[index.toString()] = index;
    });
    Display.replaceSlides(parentSection);
  },

  /**
   * Set a video
   * @param {Object} video - The video to show as a JS object: {"path": "url/to/file"}
   */
  setVideo: function (video) {
    Display._setPresentationSlideTransition(false);
    Display._clearSlidesList();
    var section = document.createElement("section");
    section.setAttribute("data-background", "#000");
    var videoElement = document.createElement("video");
    var fit = _resolveBackgroundFit((Display._theme && Display._theme.background_fit) || "cover");
    videoElement.src = video.path;
    videoElement.preload = "auto";
    videoElement.setAttribute("id", "video");
    videoElement.setAttribute("style", "height: 100%; width: 100%; object-fit: " + fit.objectFit + ";");
    videoElement.setAttribute('data-slide', 0);
    videoElement.autoplay = false;
    // All the update methods below are Python functions, hence not camelCase
    videoElement.addEventListener("durationchange", function (event) {
      mediaWatcher.update_duration(event.target.duration);
    });
    videoElement.addEventListener("timeupdate", function (event) {
      mediaWatcher.update_progress(event.target.currentTime);
    });
    videoElement.addEventListener("volumeupdate", function (event) {
      mediaWatcher.update_volume(event.target.volume);
    });
    videoElement.addEventListener("ratechange", function (event) {
      mediaWatcher.update_playback_rate(event.target.playbackRate);
    });
    videoElement.addEventListener("ended", function (event) {
      mediaWatcher.has_ended(event.target.ended);
    });
    videoElement.addEventListener("muted", function (event) {
      mediaWatcher.has_muted(event.target.muted);
    });
    section.appendChild(videoElement);
    Display.replaceSlides(section);
  },
  /**
   * Play a video
   */
  playVideo: function () {
    var videoElem = $("#video");
    if (videoElem.length == 1) {
      videoElem[0].play();
    }
  },
  /**
   * Pause a video
   */
  pauseVideo: function () {
    var videoElem = $("#video");
    if (videoElem.length == 1) {
      videoElem[0].pause();
    }
  },
  /**
   * Stop a video
   */
  stopVideo: function () {
    var videoElem = $("#video");
    if (videoElem.length == 1) {
      videoElem[0].pause();
      videoElem[0].currentTime = 0.0;
    }
  },
  /**
   * Go to a particular time in a video
   * @param seconds The position in seconds to seek to
   */
  seekVideo: function (seconds) {
    var videoElem = $("#video");
    if (videoElem.length == 1) {
      videoElem[0].currentTime = seconds;
    }
  },
  /**
   * Set the playback rate of a video
   * @param rate A Double of the rate. 1.0 => 100% speed, 0.75 => 75% speed, 1.25 => 125% speed, etc.
   */
  setPlaybackRate: function (rate) {
    var videoElem = $("#video");
    if (videoElem.length == 1) {
      videoElem[0].playbackRate = rate;
    }
  },
  /**
   * Set the volume
   * @param level The volume level from 0 to 100.
   */
  setVideoVolume: function (level) {
    var videoElem = $("#video");
    if (videoElem.length == 1) {
      videoElem[0].volume = level / 100.0;
    }
  },
  /**
   * Mute the volume
   */
  toggleVideoMute: function () {
    var videoElem = $("#video");
    if (videoElem.length == 1) {
      videoElem[0].muted = !videoElem[0].muted;
    }
  },
  /**
   * Clear the background audio playlist
   */
  clearPlaylist: function () {
    var backgroundAudoElem = $("#background-audio");
    if (backgroundAudoElem.length == 1) {
      var audio = backgroundAudoElem[0];
      /* audio.playList */
    }
  },
  /**
   * Add background audio
   * @param files The list of files as objects in an array
   */
  addBackgroundAudio: function (files) {
  },
  /**
   * Go to a slide.
   * @param slide The slide number or name, e.g. "v1", 0
   */
  goToSlide: function (slide) {
    if (Display._slides.hasOwnProperty(slide)) {
      var target = Display._slides[slide];
      if (typeof target === "object" && target !== null) {
        Reveal.slide(target.h || 0, target.v || 0);
      } else {
        Reveal.slide(0, target);
      }
    }
    else {
      if (Display._textSlideDirection === TransitionDirection.Horizontal) {
        Reveal.slide(slide, 0);
      } else {
        Reveal.slide(0, slide);
      }
    }
  },
  /**
   * Run a two-step transition demo for theme preview.
   * @param {number} initialDelayMs - Delay before moving to slide 2
   * @param {number} returnDelayMs - Delay before returning to slide 1
   */
  previewTransition: function (initialDelayMs, returnDelayMs) {
    var firstDelay = Number(initialDelayMs);
    if (!Number.isFinite(firstDelay) || firstDelay < 0) {
      firstDelay = 300;
    }
    var secondDelay = Number(returnDelayMs);
    if (!Number.isFinite(secondDelay) || secondDelay < 0) {
      secondDelay = 3500;
    }
    Display._previewTransitionTimeoutHandles.forEach(function (handle) {
      clearTimeout(handle);
    });
    Display._previewTransitionTimeoutHandles = [];
    var toSecondSlide = setTimeout(function () {
      Display.goToSlide("V2");
    }, Math.round(firstDelay));
    var backToFirstSlide = setTimeout(function () {
      Display.goToSlide("V1");
    }, Math.round(firstDelay + secondDelay));
    Display._previewTransitionTimeoutHandles.push(toSecondSlide, backToFirstSlide);
  },
  /**
   * Go to the next slide in the list
  */
  next: Reveal.nextFragment,
  /**
   * Go to the previous slide in the list
  */
  prev: Reveal.prevFragment,
  /** Change output modes without changing any slide's theme/background data. */
  _setOutputMode: function (mode, disableTransitions, logo) {
    // Auto-unblank also sends Show for already visible items. It must not
    // cancel the item fade that has just started.
    if (mode === 'show' && Display._displayMode === 'show' && !Display._pendingLogoPreloader &&
        document.body.style.opacity !== '0' && Display._slidesContainer.style.opacity !== '0') {
      return Promise.resolve();
    }
    return new Promise(function (resolve) {
      var token = Display._beginTransitionOperation();
      var body = document.body;
      var previousMode = Display._displayMode || 'show';
      var immediate = !!disableTransitions || !Display._doItemTransitions;
      function apply() {
        if (!Display._isCurrentTransition(token)) {
          return;
        }
        var fromDesktop = previousMode === 'desktop' || Number(getComputedStyle(body).opacity) === 0;
        var wasPaused = Reveal.isPaused();
        Display._displayMode = mode;
        body.classList.toggle('disable-transitions', immediate || fromDesktop);
        Display._restorePauseBehavior();
        if (mode === 'logo') {
          Display._setLogoScreenBackground(logo.bg_color, logo.image, logo.logo_fit);
          // Black is above Logo. Keep Logo opaque underneath it while Black
          // fades away so the slide cannot flash between these two covers.
          if (wasPaused || previousMode === 'logo' || fromDesktop) {
            Display._setOpacityImmediately(Display._logoScreen, 1);
          }
          Display._logoScreen.classList.add('show');
          Display._logoScreen.style.removeProperty('opacity');
        } else if (mode !== 'black') {
          Display._hideLogoScreen();
        }
        if (mode === 'show' || mode === 'theme') {
          var opacity = mode === 'show' ? 1 : 0;
          var covered = previousMode === 'black' || previousMode === 'logo' || fromDesktop;
          [Display._slidesContainer, Display._footerContainer].forEach(function (element) {
            if (covered) {
              Display._setOpacityImmediately(element, opacity);
            } else {
              element.style.opacity = opacity;
            }
          });
        }
        body.classList.toggle('show-theme', mode === 'theme');
        Array.from(document.querySelectorAll('.image-slide-background')).forEach(function (background) {
          background.style.setProperty('transition', immediate ? 'none' :
            'opacity ' + Display._itemTransitionSpeedSeconds + 's ' +
              Display._getTransitionEasing(Display._itemTransitionType), 'important');
        });
        if (Reveal.isPaused() !== (mode === 'black')) {
          Reveal.togglePause();
        }
        // Commit the prepared state while still transparent before fading a
        // previously hidden native window back in.
        if (fromDesktop) {
          void body.offsetHeight;
          body.classList.toggle('disable-transitions', immediate);
        }
        body.style.opacity = 1;
        void body.offsetHeight;
        var finish = function () {
          if (!Display._isCurrentTransition(token)) {
            return;
          }
          if (mode === 'logo') {
            Display._setOpacityImmediately(Display._slidesContainer, 0);
            Display._setOpacityImmediately(Display._footerContainer, 0);
          } else if (mode === 'black') {
            // Keep Logo in place until the black cover is fully opaque.
            Display._setOpacityImmediately(Display._logoScreen, 0);
            Display._hideLogoScreen();
          }
          body.classList.remove('disable-transitions');
          Array.from(document.querySelectorAll('.image-slide-background')).forEach(function (background) {
            background.style.removeProperty('transition');
          });
          resolve();
        };
        if (immediate) {
          Display._requestAnimationFrameExclusive(finish);
        } else {
          Display._modeCompletionTimeout = setTimeout(finish,
            Math.round(Display._itemTransitionSpeedSeconds * 1000) + 50);
        }
      }
      if (mode !== 'logo' || !logo.image) {
        apply();
        return;
      }
      var preloader = new Image();
      Display._pendingLogoPreloader = preloader;
      preloader.onload = function () {
        Display._pendingLogoPreloader = null;
        apply();
      };
      preloader.onerror = function () {
        Display._pendingLogoPreloader = null;
        logo.image = null;
        apply();
      };
      preloader.src = logo.image;
    });
  },

  _setOpacityImmediately: function (element, opacity) {
    if (!element) {
      return;
    }
    var transition = element.style.getPropertyValue('transition');
    var priority = element.style.getPropertyPriority('transition');
    element.style.setProperty('transition', 'none', 'important');
    element.style.opacity = opacity;
    void element.offsetHeight;
    element.style.removeProperty('transition');
    if (transition) {
      element.style.setProperty('transition', transition, priority);
    }
  },

  toBlack: function (disableTransitions) {
    return Display._setOutputMode('black', disableTransitions);
  },

  toTheme: function (disableTransitions) {
    return Display._setOutputMode('theme', disableTransitions);
  },

  /**
   * Hide everything (CAUTION: Causes a invisible mouse barrier)
  */
  toTransparent: function (disableTransitions) {
    return new Promise((resolve) => {
      var token = Display._beginTransitionOperation();
      var body = document.body;
      var immediate = !!disableTransitions || !Display._doItemTransitions;
      Display._displayMode = 'desktop';
      body.classList.toggle('disable-transitions', immediate);
      var alreadyTransparent = Number(getComputedStyle(body).opacity) === 0;
      // Fade the currently visible composition, including Black or Logo. Do
      // not reveal a different layer underneath while fading to the desktop.
      body.style.opacity = 0;
      function finish() {
        if (!Display._isCurrentTransition(token)) {
          return;
        }
        Display._removeTransitionEndEventToBody();
        clearTimeout(Display._transparentFallbackTimeout);
        body.classList.add('disable-transitions', 'is-desktop');
        Display._slidesContainer.style.opacity = 0;
        Display._footerContainer.style.opacity = 0;
        if (Display._clearAfterNativeHandoff) {
          Display.setTextSlide('');
        }
        displayWatcher.pleaseRepaint();
        Display._requestAnimationFrameExclusive(function () {
          if (Display._isCurrentTransition(token)) {
            resolve();
          }
        });
      }
      if (immediate || alreadyTransparent) {
        finish();
        return;
      }
      Display._addTransitionEndEventToBody(function (event) {
        if (event.target === body && event.propertyName === 'opacity') {
          finish();
        }
      });
      // Hidden/minimised WebEngine windows may never deliver transitionend.
      Display._transparentFallbackTimeout = setTimeout(finish,
        Math.round(Display._itemTransitionSpeedSeconds * 1000) + 100);
    });
  },
  /**
   * Hide all but the configured logo background.
   * @param {string} bg_color - The logo screen background color
   * @param {string} image - Path to the logo image
   * @param {string} logo_fit - cover, contain, stretch, repeat
  */
  toLogo: function (bg_color, image, logo_fit, disableTransitions) {
    return Display._setOutputMode('logo', disableTransitions,
      {bg_color: bg_color, image: image, logo_fit: logo_fit});
  },

  show: function (disableTransitions) {
    return Display._setOutputMode('show', disableTransitions);
  },

  _hideLogoScreen: function() {
    if (Display._logoScreen) {
      Display._logoScreen.style.removeProperty("opacity");
      Display._logoScreen.classList.remove("show");
    }
  },

  _setLogoScreenBackground: function(bg_color, image, logo_fit) {
    if (!Display._logoScreen) {
      return;
    }
    var fit = _resolveBackgroundFit(logo_fit || "cover");
    Display._logoScreen.style.backgroundColor = bg_color || "#000";
    Display._logoScreen.style.backgroundSize = fit.size;
    Display._logoScreen.style.backgroundRepeat = fit.repeat;
    Display._logoScreen.style.backgroundPosition = fit.position;
    if (image) {
      Display._logoScreen.style.backgroundImage = 'url("' + image.replace(/"/g, '\\"') + '")';
    }
    else {
      Display._logoScreen.style.backgroundImage = "none";
    }
    if (Display._logoScreenImage) {
      Display._logoScreenImage.onload = null;
      Display._logoScreenImage.onerror = null;
      Display._logoScreenImage.removeAttribute("src");
      Display._logoScreenImage.style.display = "none";
    }
  },

  _getRootSlideSection: function() {
    return $(".slides > section")[0];
  },

  _syncOutputModeAfterSlideReplacement: function () {
    if ((Display._displayMode === 'logo')) {
      Display._setOpacityImmediately(Display._slidesContainer, 0);
      Display._setOpacityImmediately(Display._footerContainer, 0);
    }
    // Image/PDF backgrounds are slide content, unlike a song's theme image.
    Array.from(Display._slidesContainer.querySelectorAll('.use-background-image')).forEach(function (slide) {
      if (slide.slideBackgroundElement) {
        slide.slideBackgroundElement.classList.add('image-slide-background');
      }
    });
  },

  /**
   * Shows again the Reveal's black pause overlay that was
   * hidden before Webview was hidden
   */
  _restorePauseBehavior: function() {
    document.body.classList.remove('is-desktop');
  },

  /**
   * Cancels previous requested animationFrame.
   * Last animationFrame should be aborted to avoid race condition bugs when
   * the user changes the view modes too quickly, for example.
   */
  _requestAnimationFrameExclusive: function(callback) {
    cancelAnimationFrame(Display._lastRequestAnimationFrameHandle);
    Display._lastRequestAnimationFrameHandle = requestAnimationFrame(callback);
  },

  /**
   * Aborts last body's transitionend and requestAnimationFrame's events, to avoid
   * race condition bugs. Also tears down mode completion timers and logo
   * image preloaders so they can't mutate state
   * after a different hide/show operation has taken over.
   */
  _abortLastTransitionOperation: function() {
    Display._removeTransitionEndEventToBody();
    clearTimeout(Display._transparentFallbackTimeout);
    clearTimeout(Display._modeCompletionTimeout);
    cancelAnimationFrame(Display._lastRequestAnimationFrameHandle);
    if (Display._pendingLogoPreloader) {
      Display._pendingLogoPreloader.onload = null;
      Display._pendingLogoPreloader.onerror = null;
      Display._pendingLogoPreloader = null;
    }
  },

  /**
   * Claim a new transition token. Any async callback registered during this
   * operation should capture the returned value and verify it is still the
   * current token before mutating state.
   */
  _beginTransitionOperation: function() {
    Display._abortLastTransitionOperation();
    Display._cancelItemTransition();
    Display._transitionToken += 1;
    return Display._transitionToken;
  },

  /**
   * Whether the given token is still the most recent transition token.
   */
  _isCurrentTransition: function(token) {
    return token === Display._transitionToken;
  },

  /**
   * Intercepts the addEventListener call and stores it, so that it acts
   * like the ontransitionend GlobalEventHandler.
   */
  _addTransitionEndEventToBody: function(listener) {
    Display._lastTransitionEndBodyEvent = listener;
    document.body.addEventListener('transitionend', listener);
  },

  _removeTransitionEndEventToBody: function() {
    document.body.removeEventListener('transitionend', Display._lastTransitionEndBodyEvent);
  },

  /**
   * Figure out how many lines can fit on a slide given the font size
   * @param fontSize The font size in pts
   */
  calculateLineCount: function (fontSize) {
    var p = $(".slides > section > section > p, .slides > section > p");
    if (p.length == 0) {
      Display.addSlide("v1", "Arky arky");
      p = $(".slides > section > section > p, .slides > section > p");
    }
    p = p[0];
    p.style.fontSize = "" + fontSize + "pt";
    var d = Reveal.getCurrentSlide() || $(".slides > section")[0];
    var lh = parseFloat(_getStyle(p, "line-height"));
    var dh = parseFloat(_getStyle(d, "height"));
    return Math.floor(dh / lh);
  },
  /** Render song-local decorations in each text slide, so normal blanking and transitions include them. */
  _applySongDesign: function (slide) {
    slide.querySelectorAll('.song-design-element').forEach(node => node.remove());
    var design = Display._theme.song_design || {};
    var content = slide.querySelector('.slide-text-content');
    if (!content) return;
    slide.style.width = '100%';
    slide.style.height = '100%';
    if (slide.parentElement && slide.parentElement.classList.contains('text-slides')) {
      slide.parentElement.style.height = '100%';
    }
    var lyrics = design.lyrics || {};
    content.dataset.designId = 'lyrics';
    content.style.transform = Display._designTransform(lyrics);
    content.style.opacity = (lyrics.opacity === undefined ? 100 : lyrics.opacity) / 100;
    Display._applyDesignEffects(content, lyrics, 'lyrics');
    var defaultOrder = (design.elements || []).map(element => element.id).concat('lyrics');
    var order = (Array.isArray(design.order) ? design.order : []).filter((id, index, ids) =>
      defaultOrder.includes(id) && ids.indexOf(id) === index);
    order = order.concat(defaultOrder.filter(id => !order.includes(id)));
    content.style.zIndex = String(order.indexOf('lyrics') + 1);
    (design.elements || []).forEach(element => {
      var node = document.createElement(element.kind === 'image' ? 'img' : 'div');
      node.className = 'song-design-element';
      node.dataset.designId = element.id;
      Object.assign(node.style, {
        position: 'absolute', boxSizing: 'border-box', margin: '0', padding: '0',
        left: `${element.x}%`, top: `${element.y}%`, width: `${element.width}%`, height: `${element.height}%`,
        zIndex: String(order.indexOf(element.id) + 1), transform: Display._designTransform(element),
        opacity: (element.opacity === undefined ? 100 : element.opacity) / 100,
        border: `${element.border_width || 0}px solid ${element.border_colour || '#ffffff'}`,
        maxWidth: 'none', maxHeight: 'none', boxShadow: 'none', textShadow: 'none',
        overflow: 'hidden', borderRadius: element.kind === 'ellipse' ? '50%' : '0'
      });
      if (element.kind === 'image') {
        // Only embedded raster images are allowed, never HTML, SVG, file or remote URLs.
        if (/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(element.src || '')) node.src = element.src;
        node.style.objectFit = 'contain';
        node.draggable = false;
      } else if (element.kind === 'text') {
        node.textContent = element.text || '';
        Object.assign(node.style, {
          whiteSpace: 'pre-wrap', fontFamily: element.font || 'Arial', color: element.colour || '#ffffff',
          fontSize: `${(element.font_size || 40) * (Display._theme.song_design_output_height || 1080) /
            (design.canvas_height || 1080)}pt`,
          fontWeight: element.bold ? 'bold' : 'normal', fontStyle: element.italic ? 'italic' : 'normal',
          textAlign: element.align || 'center', lineHeight: '1.15'
        });
      } else {
        node.style.backgroundColor = element.fill || '#315efb';
      }
      Display._applyDesignEffects(node, element, element.kind);
      slide.appendChild(node);
    });
    Display._bindDesignEditor(slide);
  },

  _designTransform: function (properties) {
    return `rotate(${properties.rotation || 0}deg) scale(${properties.flip_horizontal ? -1 : 1}, ` +
      `${properties.flip_vertical ? -1 : 1})`;
  },

  _designFilters: function (filters) {
    var scale = (Display._theme.song_design_output_height || 1080) /
      ((Display._theme.song_design || {}).canvas_height || 1080);
    var ranges = {blur: [0, 100, 'px'], brightness: [0, 200, '%'], contrast: [0, 200, '%'],
      grayscale: [0, 100, '%'], 'hue-rotate': [-180, 180, 'deg'], invert: [0, 100, '%'],
      saturate: [0, 200, '%'], sepia: [0, 100, '%']};
    return Object.keys(ranges).filter(key => filters && typeof filters[key] === 'number' &&
      Number.isFinite(filters[key])).map(key => {
      var range = ranges[key];
      var value = Math.max(range[0], Math.min(range[1], filters[key]));
      return `${key}(${key === 'blur' ? value * scale : value}${range[2]})`;
    }).join(' ');
  },

  /** Effects use design pixels, scaled to the output; text outlines follow glyphs, not the text box. */
  _applyDesignEffects: function (node, properties, kind) {
    var scale = (Display._theme.song_design_output_height || 1080) /
      ((Display._theme.song_design || {}).canvas_height || 1080);
    if (properties.outline === undefined && properties.border_width && kind !== 'text' && kind !== 'lyrics') {
      properties = Object.assign({outline: true, outline_width: properties.border_width,
        outline_colour: properties.border_colour || '#ffffff'}, properties);
    }
    var theme = Display._theme;
    var inherited = kind === 'lyrics';
    var defaults = inherited ? {
      outline: theme.font_main_outline, outline_width: (theme.font_main_outline_size || 0) * 4 / 3 / scale,
      outline_colour: theme.font_main_outline_color, shadow: theme.font_main_shadow,
      shadow_x: (theme.font_main_shadow_size || 0) * 4 / 3 / scale,
      shadow_y: (theme.font_main_shadow_size || 0) * 4 / 3 / scale,
      shadow_blur: (theme.font_main_shadow_blur || 0) * 4 / 3 / scale, shadow_colour: theme.font_main_shadow_color
    } : {};
    var effect = Object.assign({outline_width: 2, outline_colour: '#000000', shadow_x: 4,
      shadow_y: 4, shadow_blur: 4, shadow_colour: '#000000'}, defaults, properties);
    var shadow = `${(effect.shadow_x || 0) * scale}px ${(effect.shadow_y || 0) * scale}px ` +
      `${(effect.shadow_blur || 0) * scale}px ${effect.shadow_colour || '#000000'}`;
    if (inherited || kind === 'text') {
      // Preserve the original theme effect exactly unless this text has an explicit override.
      if (inherited && !Object.keys(properties).some(key => key.startsWith('outline') || key.startsWith('shadow'))) return;
      var shadows = [];
      if (effect.outline && effect.outline_width > 0) {
        var radius = effect.outline_width * scale;
        var steps = Math.max(8, Math.ceil(2 * Math.PI * radius));
        for (var index = 0; index < steps; index++) {
          var angle = index * 2 * Math.PI / steps;
          shadows.push(`${Math.cos(angle) * radius}px ${Math.sin(angle) * radius}px 0px ` +
            `${effect.outline_colour || '#000000'}`);
        }
      }
      if (effect.shadow) shadows.push(shadow);
      node.style.textShadow = shadows.length ? shadows.join(', ') : 'none';
      if (kind === 'text') node.style.overflow = 'visible';
    } else {
      // Use a border on shapes/images so ellipse outlines follow their contour.
      if (effect.outline !== undefined) {
        node.style.border = `${effect.outline ? effect.outline_width * scale : 0}px solid ` +
          `${effect.outline_colour || '#000000'}`;
      }
      var filters = kind === 'image' ? Display._designFilters(properties.filters) : '';
      node.style.filter = [filters, effect.shadow ? `drop-shadow(${shadow})` : ''].filter(Boolean).join(' ') || 'none';
    }
  },

  /** Report a completed designer frame without exposing intermediate formatting passes. */
  waitForDesignPreview: async function (revision) {
    // Qt keeps the previous preview over the browser until assets and Reveal's deferred layout settle.
    await Promise.all([Display._waitForSlideImages(), document.fonts.ready]);
    await new Promise(function (resolve) {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          requestAnimationFrame(resolve);
        });
      });
    });
    return revision;
  },

  /** Enable editing only inside the designer's own display window. Accept one id or a selection. */
  setDesignEditor: function (selected) {
    Display._designEditor = selected !== null;
    Display._designSelection = Array.isArray(selected) ? selected.slice() : selected ? [selected] : [];
    Display._designSelected = Display._designSelection[Display._designSelection.length - 1] || null;
    document.querySelectorAll('.text-slide').forEach(Display._bindDesignEditor);
  },

  /** Plain source text for the current designer page; never enabled on a live display. */
  setDesignTextSources: function (sources) {
    Display._designTextSources = sources;
    document.querySelectorAll('.text-slide').forEach(Display._bindDesignEditor);
  },

  _startDesignTextEdit: function (event, node) {
    event.stopPropagation();
    if (Display._designTextEdit) return;
    var source = (Display._designTextSources || {})[node.dataset.designId];
    if (typeof source !== 'string') return;
    var target = node.querySelector('p') || node;
    Display._designTextEdit = {node, target, html: target.innerHTML, style: target.getAttribute('style'),
      id: node.dataset.designId, before: source};
    node.parentElement.querySelectorAll('.design-selection-outline').forEach(outline => outline.remove());
    // Retain inline formatting whenever the rendered text matches the editable source.
    // Transformed text (for example uppercase lyrics) is edited in its original case.
    if (target.innerText !== source) target.textContent = source;
    target.contentEditable = 'plaintext-only';
    target.style.whiteSpace = 'pre-wrap';
    target.style.minHeight = '1em';
    node.style.userSelect = 'text';
    node.style.cursor = 'text';
    node.onpointerdown = pointer => pointer.stopPropagation();
    target.onkeydown = key => {
      key.stopPropagation();
      if (key.key === 'Escape' || (key.key === 'Enter' && (key.ctrlKey || key.metaKey))) {
        key.preventDefault();
        Display.finishDesignTextEdit(key.key === 'Escape');
      }
    };
    target.onblur = () => Display.finishDesignTextEdit(false);
    window.addEventListener('blur', target.onblur);
    target.focus();
    var caret = document.caretRangeFromPoint(event.clientX, event.clientY);
    if (caret && target.contains(caret.startContainer)) {
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(caret);
    }
    displayWatcher.dispatchEvent('songDesignTextEditing', true);
  },

  /** Also called synchronously by Qt before saving or switching pages. */
  finishDesignTextEdit: function (cancelled, notify = true) {
    var edit = Display._designTextEdit;
    if (!edit) return null;
    Display._designTextEdit = null;
    var result = {id: edit.id, text: cancelled ? edit.before : edit.target.innerText,
      before: edit.before, cancelled: !!cancelled};
    window.removeEventListener('blur', edit.target.onblur);
    edit.target.onblur = null;
    edit.target.onkeydown = null;
    edit.target.removeAttribute('contenteditable');
    edit.target.innerHTML = edit.html;
    if (edit.style === null) edit.target.removeAttribute('style');
    else edit.target.setAttribute('style', edit.style);
    Display._bindDesignEditor(edit.node.parentElement);
    if (notify) displayWatcher.dispatchEvent('songDesignTextChanged', result);
    return result;
  },

  _bindDesignEditor: function (slide) {
    slide.onpointerdown = Display._designEditor ? event => {
      if (event.button !== 0) return;
      event.stopPropagation();
      Display.setDesignEditor('');
      displayWatcher.dispatchEvent('songDesignChanged', {id: null, ids: [], changed: false});
    } : null;
    slide.querySelectorAll('.design-selection-outline').forEach(node => node.remove());
    var selection = Display._designSelection || [];
    var zoom = slide.getBoundingClientRect().width / slide.offsetWidth || 1;
    var handleSize = 8 / zoom, borderSize = 1 / zoom;
    slide.querySelectorAll('[data-design-id]').forEach(node => {
      if (Display._designTextEdit && Display._designTextEdit.node === node) return;
      node.style.outline = '';
      node.style.cursor = '';
      node.style.userSelect = '';
      node.onpointerdown = null;
      var editableText = typeof (Display._designTextSources || {})[node.dataset.designId] === 'string';
      node.ondblclick = editableText ? event => Display._startDesignTextEdit(event, node) : null;
      if (!Display._designEditor) return;
      node.style.cursor = 'move';
      node.style.userSelect = 'none';
      if (selection.includes(node.dataset.designId)) {
        // Selection chrome lives above the layers, but its interior never intercepts other objects.
        var outline = document.createElement('div');
        outline.className = 'design-selection-outline';
        outline.dataset.selectionId = node.dataset.designId;
        Object.assign(outline.style, {
          position: 'absolute', left: `${node.offsetLeft}px`, top: `${node.offsetTop}px`,
          width: `${node.offsetWidth}px`, height: `${node.offsetHeight}px`, boxSizing: 'border-box',
          transform: `rotate(${Display._designRotation(node)}deg)`, outline: `${borderSize}px solid #51a7ff`, zIndex: '201',
          cursor: 'move', pointerEvents: 'none'
        });
        [{left: '-8px', top: '-8px', width: 'calc(100% + 16px)', height: '16px'},
          {left: '-8px', bottom: '-8px', width: 'calc(100% + 16px)', height: '16px'},
          {left: '-8px', top: '8px', width: '16px', height: 'calc(100% - 16px)'},
          {right: '-8px', top: '8px', width: '16px', height: 'calc(100% - 16px)'}].forEach(edge => {
          var grip = document.createElement('div');
          Object.assign(grip.style, {position: 'absolute', pointerEvents: 'auto'}, edge);
          outline.appendChild(grip);
        });
        slide.appendChild(outline);
        outline.onpointerdown = event => Display._startDesignDrag(event, node, false);
        if (selection.length === 1) {
          // Handles are siblings of the object, so images and slide text have identical controls.
          [['nw', 0, 0], ['n', 50, 0], ['ne', 100, 0], ['e', 100, 50],
            ['se', 100, 100], ['s', 50, 100], ['sw', 0, 100], ['w', 0, 50]].forEach(([edge, x, y]) => {
            var handle = document.createElement('div');
            handle.className = 'design-resize-handle';
            handle.dataset.edge = edge;
            Object.assign(handle.style, {
              position: 'absolute', width: `${handleSize}px`, height: `${handleSize}px`, background: '#ffffff',
              border: `${borderSize}px solid #217aff`, boxSizing: 'border-box', pointerEvents: 'auto',
              cursor: `${edge}-resize`, left: `calc(${x}% - ${handleSize / 2}px)`,
              top: `calc(${y}% - ${handleSize / 2}px)`
            });
            outline.appendChild(handle);
            handle.onpointerdown = event => Display._startDesignDrag(event, node, edge);
          });
        }
      }
      node.onpointerdown = event => Display._startDesignDrag(event, node, false);
    });
  },

  _designRotation: function (node) {
    var match = /rotate\(([-\d.]+)deg\)/.exec(node.style.transform);
    return match ? Number(match[1]) : 0;
  },

  /** Keep the image in Reveal's background plane, including when text is blanked. */
  _applyDesignBackgroundImages: function () {
    document.querySelectorAll('.reveal .slides section').forEach(section => {
      var background = section.slideBackgroundElement;
      var content = background && typeof background.querySelector === 'function' &&
        background.querySelector('.slide-background-content');
      if (!content) return;
      background.style.filter = section.dataset.designBackgroundFilters || 'none';
      content.querySelectorAll('.song-design-background-image').forEach(node => node.remove());
      var source = section.dataset.designBackgroundImage;
      if (!/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(source || '')) return;
      var fit = _resolveBackgroundFit(section.dataset.designBackgroundFit || 'cover');
      var image = document.createElement('div');
      image.className = 'song-design-background-image';
      Object.assign(image.style, {
        position: 'absolute', inset: '0', pointerEvents: 'none',
        backgroundImage: `url("${source}")`, backgroundSize: fit.size,
        backgroundRepeat: fit.repeat, backgroundPosition: fit.position,
        opacity: String(Math.max(0, Math.min(100, Number(section.dataset.designBackgroundOpacity))) / 100)
      });
      content.appendChild(image);
    });
  },

  _startDesignDrag: function (event, node, resizing) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    var id = node.dataset.designId;
    var lastClick = Display._lastDesignClick;
    Display._lastDesignClick = null;
    // Pointer capture retargets clicks from nested text spans to their box and can
    // suppress the browser's dblclick. Recognise two completed clicks as well.
    if (!resizing && !event.shiftKey && !event.ctrlKey && !event.metaKey && lastClick &&
        lastClick.node === node && performance.now() - lastClick.time < 500 &&
        Math.hypot(event.clientX - lastClick.x, event.clientY - lastClick.y) < 6 &&
        typeof (Display._designTextSources || {})[id] === 'string') {
      Display._startDesignTextEdit(event, node);
      return;
    }
    var selection = (Display._designSelection || []).slice();
    var modified = event.shiftKey || event.ctrlKey || event.metaKey;
    if (modified && !resizing) {
      selection = selection.includes(id) ? selection.filter(value => value !== id) : selection.concat(id);
      Display.setDesignEditor(selection);
      displayWatcher.dispatchEvent('songDesignChanged', {id: selection[selection.length - 1] || null,
        ids: selection, changed: false});
      return;
    }
    if (!selection.includes(id) || resizing) selection = [id];
    Display._designSelection = selection;
    Display._designSelected = id;
    var slide = node.parentElement;
    var bounds = slide.getBoundingClientRect();
    var width = slide.clientWidth;
    var height = slide.clientHeight;
    if (!width || !height || !bounds.width || !bounds.height) return;
    var nodes = Array.from(slide.querySelectorAll('[data-design-id]')).filter(item =>
      selection.includes(item.dataset.designId));
    var starts = {}, changed = {};
    nodes.forEach(item => {
      var style = getComputedStyle(item);
      starts[item.dataset.designId] = {x: parseFloat(style.left) / width * 100, y: parseFloat(style.top) / height * 100,
        width: parseFloat(style.width) / width * 100, height: parseFloat(style.height) / height * 100};
      changed[item.dataset.designId] = Object.assign({}, starts[item.dataset.designId]);
    });
    var start = starts[id];
    var clientX = event.clientX, clientY = event.clientY;
    var target = event.currentTarget;
    if (target === node) Display._bindDesignEditor(slide);
    target.setPointerCapture(event.pointerId);
    var clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    var paint = geometries => {
      nodes.forEach(item => {
        var geometry = geometries[item.dataset.designId];
        ['x', 'y', 'width', 'height'].forEach(key => {
          item.style.setProperty(({x: 'left', y: 'top'})[key] || key, `${geometry[key]}%`, 'important');
        });
        var outline = Array.from(slide.querySelectorAll('.design-selection-outline')).find(chrome =>
          chrome.dataset.selectionId === item.dataset.designId);
        if (outline) Object.assign(outline.style, {
          left: `${item.offsetLeft}px`, top: `${item.offsetTop}px`,
          width: `${item.offsetWidth}px`, height: `${item.offsetHeight}px`
        });
      });
    };
    target.onpointermove = move => {
      var dx = (move.clientX - clientX) / bounds.width * 100;
      var dy = (move.clientY - clientY) / bounds.height * 100;
      if (resizing) {
        var edge = resizing === true ? 'se' : resizing;
        var radians = Display._designRotation(node) * Math.PI / 180;
        var cos = Math.cos(radians), sin = Math.sin(radians);
        // Work in local output pixels so rotated boxes resize along their visible axes.
        var localX = (dx * width / 100 * cos + dy * height / 100 * sin) / width * 100;
        var localY = (-dx * width / 100 * sin + dy * height / 100 * cos) / height * 100;
        var next = changed[id];
        next.width = clamp(start.width + (edge.includes('e') ? localX : edge.includes('w') ? -localX : 0), 100 / width, 100);
        next.height = clamp(start.height + (edge.includes('s') ? localY : edge.includes('n') ? -localY : 0), 100 / height, 100);
        var offsetX = (next.width - start.width) * width / 200 * (edge.includes('w') ? -1 : 1);
        var offsetY = (next.height - start.height) * height / 200 * (edge.includes('n') ? -1 : 1);
        next.x = start.x + (start.width - next.width) / 2 + (offsetX * cos - offsetY * sin) / width * 100;
        next.y = start.y + (start.height - next.height) / 2 + (offsetX * sin + offsetY * cos) / height * 100;
        next.x = clamp(next.x, 0, 100 - next.width);
        next.y = clamp(next.y, 0, 100 - next.height);
      } else {
        var boxes = Object.values(starts);
        dx = clamp(dx, -Math.min(...boxes.map(box => box.x)), 100 - Math.max(...boxes.map(box => box.x + box.width)));
        dy = clamp(dy, -Math.min(...boxes.map(box => box.y)), 100 - Math.max(...boxes.map(box => box.y + box.height)));
        nodes.forEach(item => {
          var key = item.dataset.designId;
          changed[key].x = starts[key].x + dx;
          changed[key].y = starts[key].y + dy;
        });
      }
      Display._snapDesignGeometry(slide, changed, starts, resizing, id, move.altKey);
      paint(changed);
    };
    var finish = cancelled => {
      if (cancelled) paint(starts);
      target.onpointermove = null;
      target.onpointerup = null;
      target.onpointercancel = null;
      slide.querySelectorAll('.design-snap-guide').forEach(guide => guide.remove());
      var hasChanged = JSON.stringify(changed) !== JSON.stringify(starts);
      Display._lastDesignClick = !cancelled && !resizing && !hasChanged ?
        {node, x: clientX, y: clientY, time: performance.now()} : null;
      Display._bindDesignEditor(slide);
      displayWatcher.dispatchEvent('songDesignChanged', {
        id: id, ids: selection, geometry: cancelled ? starts[id] : changed[id],
        geometries: cancelled ? starts : changed,
        changed: !cancelled && hasChanged
      });
    };
    target.onpointerup = () => finish(false);
    target.onpointercancel = () => finish(true);
  },

  /** Snap in preview pixels, so the attraction distance stays consistent at any zoom. */
  _snapDesignGeometry: function (slide, changed, starts, resizing, id, bypass) {
    slide.querySelectorAll('.design-snap-guide').forEach(guide => guide.remove());
    if (bypass) return;
    var bounds = slide.getBoundingClientRect();
    var targets = {x: [0, 50, 100], y: [0, 50, 100]};
    slide.querySelectorAll('[data-design-id]').forEach(node => {
      if (starts[node.dataset.designId] || Display._designRotation(node)) return;
      var style = getComputedStyle(node);
      var x = parseFloat(style.left) / slide.clientWidth * 100;
      var y = parseFloat(style.top) / slide.clientHeight * 100;
      var width = parseFloat(style.width) / slide.clientWidth * 100;
      var height = parseFloat(style.height) / slide.clientHeight * 100;
      targets.x.push(x, x + width / 2, x + width);
      targets.y.push(y, y + height / 2, y + height);
    });
    if (resizing && Display._designRotation(Array.from(slide.querySelectorAll('[data-design-id]'))
      .find(node => node.dataset.designId === id))) return;
    var boxes = Object.values(changed);
    ['x', 'y'].forEach(axis => {
      var size = axis === 'x' ? 'width' : 'height';
      var low = Math.min(...boxes.map(box => box[axis]));
      var high = Math.max(...boxes.map(box => box[axis] + box[size]));
      var edge = resizing === true ? 'se' : resizing;
      var leading = edge && edge.includes(axis === 'x' ? 'w' : 'n');
      var trailing = edge && edge.includes(axis === 'x' ? 'e' : 's');
      if (resizing && !leading && !trailing) return;
      var anchors = resizing ? [leading ? low : high] : [low, (low + high) / 2, high];
      var nearest = null, distance = 6 / bounds[size] * 100;
      anchors.forEach(anchor => targets[axis].forEach(target => {
        var delta = target - anchor;
        if (Math.abs(delta) > distance) return;
        if (resizing) {
          var length = changed[id][size] + (leading ? -delta : delta);
          if (length < 100 / (axis === 'x' ? slide.clientWidth : slide.clientHeight) ||
              low + (leading ? delta : 0) < 0 || high + (trailing ? delta : 0) > 100) return;
        } else if (low + delta < 0 || high + delta > 100) return;
        distance = Math.abs(delta);
        nearest = {delta, target};
      }));
      if (!nearest) return;
      if (resizing) {
        changed[id][size] += leading ? -nearest.delta : nearest.delta;
        if (leading) changed[id][axis] += nearest.delta;
      } else boxes.forEach(box => { box[axis] += nearest.delta; });
      var guide = document.createElement('div');
      guide.className = 'design-snap-guide';
      Object.assign(guide.style, {position: 'absolute', pointerEvents: 'none', zIndex: '202',
        background: '#ef5da8', left: axis === 'x' ? `${nearest.target}%` : '0',
        top: axis === 'y' ? `${nearest.target}%` : '0',
        width: axis === 'x' ? `${slide.clientWidth / bounds.width}px` : '100%',
        height: axis === 'y' ? `${slide.clientHeight / bounds.height}px` : '100%'});
      slide.appendChild(guide);
    });
  },

  /**
   * Prepare the theme for the next item to be added
   * @param theme The theme to be used
   */
  setTheme: function (theme) {
    if (Display._theme != theme) {
      Display._themeApplied = false;
      Display._theme = theme;
    }
  },
  /**
   * Set background image, replaced when theme is updated/applied
   * @param image_path Image path
   */
  setBackgroundImage: function (image_path) {
    var targetElement = $(".slides > section")[0];
    targetElement.setAttribute("data-background-image", image_path);
    targetElement.removeAttribute("data-background");
    var fit = _resolveBackgroundFit((Display._theme && Display._theme.background_fit) || "cover");
    targetElement.setAttribute("data-background-color", "#000");
    targetElement.setAttribute("data-background-size", fit.size);
    targetElement.setAttribute("data-background-repeat", fit.repeat);
    targetElement.setAttribute("data-background-position", fit.position);
    Reveal.sync();
    _applyBackgroundFitToRenderedSlides(fit);
  },
  /**
   * Show layout guide rectangles on the current preview.
   * @param {{main: Object, footer: Object}} guideRects - Main and footer rectangles in theme pixels
   */
  setLayoutGuide: function (guideRects) {
    var overlay = _ensureLayoutGuideOverlay();
    var main = $("#layout-guide-main")[0];
    var footer = $("#layout-guide-footer")[0];
    if (!main || !footer) {
      return;
    }
    [
      { element: main, rect: guideRects.main, color: "#1f78ff" },
      { element: footer, rect: guideRects.footer, color: "#ff4d4f" }
    ].forEach(function (entry) {
      var rect = entry.rect || {};
      entry.element.style.left = (rect.x || 0) + "px";
      entry.element.style.top = (rect.y || 0) + "px";
      entry.element.style.width = Math.max(rect.width || 0, 0) + "px";
      entry.element.style.height = Math.max(rect.height || 0, 0) + "px";
      entry.element.style.borderColor = entry.color;
    });
    overlay.classList.add("show-guides");
  },
  /**
   * Hide layout guide rectangles.
   */
  clearLayoutGuide: function () {
    var overlay = $("#layout-guide-overlay")[0];
    if (overlay) {
      overlay.classList.remove("show-guides");
    }
  },
  /**
   * Reset/reapply the theme
   */
  resetTheme: function () {
    var targetElement = $(".slides > section")[0];
    if (!targetElement) {
      console.warn("Couldn't reset theme: No slides exist");
      return;
    }
    Display._suppressRevealConfigure = true;
    Display._pendingRevealConfig = null;
    try {
      Array.from(Display._slidesContainer.children).forEach(function (section) {
        Display.applyTheme(section, section.classList.contains('text-slides') ||
          section.classList.contains('text-slide'));
      });
    } finally {
      Display._suppressRevealConfigure = false;
    }
    if (Display._pendingRevealConfig) {
      Reveal.configure(Display._pendingRevealConfig);
      Display._pendingRevealConfig = null;
    }
    Reveal.sync();
    Display._syncOutputModeAfterSlideReplacement();
  },
  /**
   * Apply the theme to the provided element
   * @param targetElement The target element to apply the theme (expected to be a `<section>` in the slides container)
   * @param is_text Used to decide if the main area constraints should be applied
   */
  applyTheme: function (targetElement, is_text=true) {
    var previous = Display._theme;
    try {
      if (targetElement._slideTheme) Display._theme = targetElement._slideTheme;
      Display._applyTheme(targetElement, is_text);
      if (targetElement.matches('section.text-slides')) {
        Array.from(targetElement.children).forEach(function (slide) {
          if (slide._slideTheme) Display.applyTheme(slide, is_text);
        });
      }
    } finally {
      Display._theme = previous;
    }
  },

  _applyTheme: function (targetElement, is_text=true) {
    Display._themeApplied = true;
    if (!Display._theme) {
      return;
    }
    // Set slide transitions
    var reveal_transition_type = "none",
      slide_transition_type = "none",
      new_transition_speed = "default";
    if (!!Display._theme.display_slide_transition && Display._doTransitions) {
      var themeTransitionType = Display._normaliseThemeTransitionType(Display._theme.display_slide_transition_type);
      var themeTransitionSpeed = Display._normaliseThemeTransitionSpeed(Display._theme.display_slide_transition_speed);
      var slideDuration = themeTransitionSpeed === TransitionSpeed.Fast ? 400 :
        (themeTransitionSpeed === TransitionSpeed.Slow ? 1200 : 800);
      document.body.style.setProperty('--slide-transition-ms', slideDuration + 'ms');
      var themeTransitionDirection = Display._normaliseThemeTransitionDirection(
        Display._theme.display_slide_transition_direction);
      var themeTransitionReverse = Display._normaliseThemeTransitionReverse(Display._theme.display_slide_transition_reverse);
      switch (themeTransitionType) {
        case TransitionType.Fade:
          reveal_transition_type = "fade";
          break;
        case TransitionType.Slide:
          reveal_transition_type = "slide";
          break;
        case TransitionType.Convex:
          reveal_transition_type = "convex";
          break;
        case TransitionType.Concave:
          reveal_transition_type = "concave";
          break;
        case TransitionType.Zoom:
          reveal_transition_type = "zoom";
          break;
        default:
          reveal_transition_type = "fade";
      }
      slide_transition_type = reveal_transition_type;
      switch (themeTransitionSpeed) {
        case TransitionSpeed.Normal:
          new_transition_speed = "default";
          break;
        case TransitionSpeed.Fast:
          new_transition_speed = "fast";
          break;
        case TransitionSpeed.Slow:
          new_transition_speed = "slow";
          break;
        default:
          new_transition_speed = "default";
      }
      var revealRtl = themeTransitionDirection === TransitionDirection.Horizontal && themeTransitionReverse;
      // Reveal's global transition setting must be one of: none/fade/slide/convex/concave/zoom.
      var enabledConfig = {"transition": reveal_transition_type, "transitionSpeed": new_transition_speed, "rtl": revealRtl, "backgroundTransition": "fade"};
      if (!Display._suppressRevealConfigure) {
        Reveal.configure(enabledConfig);
      } else {
        Display._pendingRevealConfig = enabledConfig;
      }
    } else {
      var disabledConfig = {"transition": "none", "transitionSpeed": "default", "rtl": false, "backgroundTransition": "none"};
      if (!Display._suppressRevealConfigure) {
        Reveal.configure(disabledConfig);
      } else {
        Display._pendingRevealConfig = disabledConfig;
      }
    }
    if (targetElement && targetElement.tagName === "SECTION" && !targetElement.classList.contains("use-background-image")) {
      targetElement.setAttribute("data-transition", reveal_transition_type);
      targetElement.setAttribute("data-transition-speed", new_transition_speed);
    }
    var slides = targetElement.querySelectorAll("section");
    for (var i = 0; i < slides.length; i++) {
      if (slides[i].classList.contains("use-background-image")) {
        continue;
      }
      slides[i].setAttribute("data-transition", slide_transition_type);
      slides[i].setAttribute("data-transition-speed", new_transition_speed);
    }
    // Set images must travel with their section for convex/slide/zoom transitions.
    // Reveal backgrounds animate separately and only support a fade.
    if (targetElement._setImage) {
      var imageFit = _resolveBackgroundFit(Display._theme.background_fit || 'contain');
      var imageColour = Display._theme.background_border_color || '#000';
      var imageKey = JSON.stringify([targetElement._setImage, imageFit, imageColour]);
      if (targetElement._setImageContentKey !== imageKey) {
        _applyImageSlideContent(targetElement, targetElement._setImage, false, imageFit, imageColour);
        targetElement._setImageContentKey = imageKey;
      }
      return;
    }
    // Set the background
    var backgroundContent = "";
    var backgroundHtml = "";
    var designBackground = is_text && Display._theme.song_design && Display._theme.song_design.background;
    targetElement.dataset.designBackgroundFilters = is_text ?
      Display._designFilters((Display._theme.song_design || {}).background_filters) : '';
    ['image', 'opacity', 'fit'].forEach(key => targetElement.removeAttribute(`data-design-background-${key}`));
    if (designBackground) {
      targetElement.removeAttribute('data-background-image');
      targetElement.removeAttribute('data-background-color');
      if (designBackground.image) {
        targetElement.dataset.designBackgroundImage = designBackground.image;
        targetElement.dataset.designBackgroundOpacity = designBackground.image_opacity;
        targetElement.dataset.designBackgroundFit = designBackground.fit;
      }
    }
    var fit = _resolveBackgroundFit(Display._theme.background_fit || "cover");
    switch (Display._theme.background_type) {
      case BackgroundType.Transparent:
        backgroundContent = "transparent";
        break;
      case BackgroundType.Solid:
        backgroundContent = Display._theme.background_color;
        break;
      case BackgroundType.Gradient:
        switch (Display._theme.background_direction) {
          case GradientType.Horizontal:
            backgroundContent = _buildLinearGradient("to right",
                                                                 Display._theme.background_start_color,
                                                                 Display._theme.background_end_color);
            break;
          case GradientType.Vertical:
            backgroundContent = _buildLinearGradient("to bottom",
                                                                 Display._theme.background_start_color,
                                                                 Display._theme.background_end_color);
            break;
          case GradientType.LeftTop:
            backgroundContent = _buildLinearGradient("to right bottom",
                                                                 Display._theme.background_start_color,
                                                                 Display._theme.background_end_color);
            break;
          case GradientType.LeftBottom:
            backgroundContent = _buildLinearGradient("to top right",
                                                                 Display._theme.background_start_color,
                                                                 Display._theme.background_end_color);
            break;
          case GradientType.Circular:
            backgroundContent = _buildRadialGradient(window.innerWidth / 2, Display._theme.background_start_color,
                                                                 Display._theme.background_end_color);
            break;
          default:
            backgroundContent = "#000";
        }
        break;
      case BackgroundType.Image:
        backgroundContent = Display._getFileUrl(Display._theme.background_filename);
        targetElement.setAttribute("data-background-image", backgroundContent);
        targetElement.setAttribute("data-background-color", Display._theme.background_border_color || "#000");
        targetElement.removeAttribute("data-background");
        break;
      case BackgroundType.Stream:
      case BackgroundType.Video:
        // never actually used since background type is overridden from video to transparent in window.py
        backgroundContent = Display._theme.background_border_color;
        backgroundHtml = "<video loop autoplay muted><source src='" + Display._getFileUrl(Display._theme.background_filename) + "'></video>";
        break;
      default:
        backgroundContent = "#000";
    }
    targetElement.style.cssText = "";
    var imageCanvasColor = targetElement.getAttribute("data-image-canvas-color");
    if (imageCanvasColor) {
      targetElement.removeAttribute("data-background-image");
      targetElement.setAttribute("data-background-color", imageCanvasColor);
      targetElement.setAttribute("data-background", imageCanvasColor);
    } else if (Display._theme.background_type !== BackgroundType.Image) {
      targetElement.setAttribute("data-background", backgroundContent);
    }
    targetElement.setAttribute("data-background-size", fit.size);
    targetElement.setAttribute("data-background-repeat", fit.repeat);
    targetElement.setAttribute("data-background-position", fit.position);
    requestAnimationFrame(function () {
      _applyBackgroundFitToRenderedSlides(fit);
      // Per-slide layouts carry their own image fit, independent of the last layout styled.
      document.querySelectorAll('.text-slide').forEach(function (slide) {
        if (!slide._slideTheme || !slide.slideBackgroundContentElement) return;
        var localFit = _resolveBackgroundFit(slide._slideTheme.background_fit);
        Object.assign(slide.slideBackgroundContentElement.style, {
          backgroundSize: localFit.size, backgroundRepeat: localFit.repeat, backgroundPosition: localFit.position
        });
      });
    });

    // set up the main area
    if (!is_text) {
      // only transition and background for non text slides
      return;
    }

    var mainFontSizePt = Number(Display._theme.font_main_size) || 0;
    var footerFontSizePt = Number(Display._theme.font_footer_size) || 0;
    var mainFontSizeCss = `${mainFontSizePt}pt`;
    var footerFontSizeCss = `${footerFontSizePt}pt`;
    var mainPaddingBottomCss = `${mainFontSizePt / 8}px`;

    var mainStyle = {
      position: "absolute",
      display: "flex",
      "flex-direction": "column",
      "box-sizing": "border-box",
      margin: "0",
      padding: "0",
      width: `${Display._theme.font_main_width}px`,
      height: `${Display._theme.font_main_height}px`,
      top: `${Display._theme.font_main_y}px`,
      left: `${Display._theme.font_main_x}px`,
      color: Display._theme.font_main_color,
      "font-family": Display._theme.font_main_name,
      "font-size": mainFontSizeCss,
      "font-style": Display._theme.font_main_italics ? "italic" : "",
      "font-weight": Display._theme.font_main_weight || (Display._theme.font_main_bold ? "bold" : "normal"),
      "line-height": `${100 + Display._theme.font_main_line_adjustment}%`,
      "letter-spacing": `${Display._theme.font_main_letter_adjustment}px`,

      "text-align":
        HorizontalAlignCSS[Display._theme.display_horizontal_align] ||
        HorizontalAlignCSS[HorizontalAlign.Center],

      "justify-content":
        VerticalAlignCSS[Display._theme.display_vertical_align] ||
        VerticalAlignCSS[HorizontalAlign.Center],

      "padding-bottom":
        Display._theme.display_vertical_align === VerticalAlign.Bottom ?
        mainPaddingBottomCss : "",

      // This section draws the font outline. Previously we used the proprietary -webkit-text-stroke property
      // but it draws the outline INSIDE the text, instead of OUTSIDE, so we had to go back to the old way
      // of using multiple text-shadow rules to fake an outline.
      "text-shadow": [
        ...(
          Display._theme.font_main_outline ?
          _buildTextOutline(Display._theme.font_main_outline_size, Display._theme.font_main_outline_color) :
          []
        ),
        ...(
          Display._theme.font_main_shadow ?
          _buildTextShadow(Display._theme.font_main_shadow_size, Display._theme.font_main_outline_size || 0,
            Display._theme.font_main_shadow_color, Display._theme.font_main_shadow_blur || 0) :
          []
        )
      ].join(", ")
    };

    var textTargets = targetElement.matches("section.text-slides") ? Array.from(targetElement.children) : [targetElement];
    Array.from(textTargets).forEach(function (slideElement) {
      if (slideElement._setImage) return;
      var contentElement = slideElement.querySelector(".slide-text-content") || slideElement;
      contentElement.style.cssText = "";
      for (var mainKey in mainStyle) {
        if (mainStyle.hasOwnProperty(mainKey)) {
          var priority = (mainKey === "top" || mainKey === "left") ? "important" : "";
          contentElement.style.setProperty(mainKey, mainStyle[mainKey], priority);
        }
      }
      Display._applySongDesign(slideElement);
    });

    // Set up the footer
    var footerStyle = {
      position: "absolute",
      display: "flex",
      "flex-direction": "column",
      "box-sizing": "border-box",
      margin: "0",
      padding: "0",
      width: `${Display._theme.font_footer_width}px`,
      height: `${Display._theme.font_footer_height}px`,
      top: `${Display._theme.font_footer_y}px`,
      left: `${Display._theme.font_footer_x}px`,
      color: Display._theme.font_footer_color,
      "font-family": Display._theme.font_footer_name,
      "font-size": footerFontSizeCss,
      "font-style": Display._theme.font_footer_italics ? "italic" : "",
      "font-weight": Display._theme.font_footer_weight || (Display._theme.font_footer_bold ? "bold" : "normal"),
      "line-height": `${100 + Display._theme.font_footer_line_adjustment}%`,
      "letter-spacing": `${Display._theme.font_footer_letter_adjustment}px`,
      "white-space": Display._theme.font_footer_wrap ? "normal" : "nowrap",

      "text-align":
        HorizontalAlignCSS[Display._theme.display_horizontal_align_footer] ||
        HorizontalAlignCSS[HorizontalAlign.Left],

      "justify-content":
        VerticalAlignCSS[Display._theme.display_vertical_align_footer] ||
        VerticalAlignCSS[HorizontalAlign.Top],

      "padding-bottom":
        Display._theme.display_vertical_align_footer === VerticalAlign.Bottom ?
        mainPaddingBottomCss : "",

      "text-shadow": [
        ...(
          Display._theme.font_footer_outline ?
          _buildTextOutline(Display._theme.font_footer_outline_size, Display._theme.font_footer_outline_color) :
          []
        ),
        ...(
          Display._theme.font_footer_shadow ?
          _buildTextShadow(Display._theme.font_footer_shadow_size, Display._theme.font_footer_outline_size || 0,
            Display._theme.font_footer_shadow_color, Display._theme.font_footer_shadow_blur || 0) :
          []
        )
      ].join(", ")
    };

    var footerTarget = Display._footerContainer;
    if (document.querySelector('.text-slide') &&
        Array.from(document.querySelectorAll('.text-slide')).some(slide => slide._slideTheme)) {
      footerTarget.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%';
      footerTarget = Display._footerContainer.querySelector(
        '.footer-item[data-slide="' + targetElement.getAttribute('data-slide') + '"]');
    }
    for (var footerKey in footerStyle) {
      if (footerStyle.hasOwnProperty(footerKey)) {
        if (footerTarget && (footerTarget === Display._footerContainer || footerKey !== 'display')) {
          footerTarget.style.setProperty(footerKey, footerStyle[footerKey]);
        }
      }
    }
  },
  /**
   * Called whenever openlp wants to finish completely with the current text/image slides
   * because a different window (eg presentation or media is going to be displaying the next item
   * and we don't want any flashbacks to the current slide contents
   */
  finishWithCurrentItem: function () {
    Display._skipNextTransition = true;
    // Media/native presentations reveal their own window via toTransparent.
    // Keep the outgoing picture until that fade ends, then clear it while
    // invisible so it cannot flash when this display is shown again.
    Display._clearAfterNativeHandoff = true;
    if (Number(getComputedStyle(document.body).opacity) === 0) {
      Display.setTextSlide('');
    }
    displayWatcher.pleaseRepaint();
  },
  /**
   * Return the video types supported by the video tag
   */
  getVideoTypes: function () {
    var videoElement = document.createElement('video');
    var videoTypes = [];
    if (videoElement.canPlayType('video/mp4; codecs="mp4v.20.8"') == "probably" ||
        videoElement.canPlayType('video/mp4; codecs="avc1.42E01E"') == "pobably" ||
        videoElement.canPlayType('video/mp4; codecs="avc1.42E01E, mp4a.40.2"') == "probably") {
      videoTypes.push(['video/mp4', '*.mp4']);
    }
    if (videoElement.canPlayType('video/ogg; codecs="theora"') == "probably") {
      videoTypes.push(['video/ogg', '*.ogv']);
    }
    if (videoElement.canPlayType('video/webm; codecs="vp8, vorbis"') == "probably") {
      videoTypes.push(['video/webm', '*.webm']);
    }
    return videoTypes;
  },
  /**
   * Sets the scale of the page - used to make preview widgets scale
   */
  setScale: function(scale) {
    document.body.style.zoom = scale+"%";
  },
  /**
   * In order to check if a font exists, we need a container to do
   * calculations on. This method creates that container and caches
   * some width values so that we don't have to do this step every
   * time we check if a font exists.
   */
  _prepareFontContainer: function() {
    Display._fontContainer = document.createElement("span");
    Display._fontContainer.id = "does-font-exist";
    Display._fontContainer.innerHTML = Array(100).join("wi");
    Display._fontContainer.style.cssText = [
      "position: absolute",
      "width: auto",
      "font-size: 128px",
      "left: -999999px"
    ].join(" !important;");
    document.body.appendChild(Display._fontContainer);
  },
  /**
   * Prepare the slide number (slide x/y) for insertion into the Reveal footer
   * This is a callback function which Reveal calls to get the values
   * Fixes https://gitlab.com/openlp/openlp/-/issues/942
   */
  setFooterSlideNumbers: function (slide) {
    let value = ['', '', ''];
    // Reveal does call this function passing undefined
    if (typeof slide === 'undefined') {
      return value;
    }
    value[0] = Reveal.getSlidePastCount(slide) + 1;
    value[1] = '/';
    value[2] = Object.keys(Display._slides).length;
    return value;
  },
  /**
   * Translates file:// protocol URLs to openlp-library://local-file/ scheme
   */
  _getFileUrl: function(url) {
    if (url && (url.indexOf('file://') === 0)) {
      return url.replace('file://', 'openlp-library://local-file/');
    }
    return url;
  },
};

Display._handleNativeCall = (action, ...values) => {
  if (Display[action]) {
    return Display[action](...values);
  }
};

initCommunicationBridge();
communicationBridge.setDisplayTarget(Display);
