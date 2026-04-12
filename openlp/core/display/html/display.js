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
 * @returns {Array} A list of shadows to be given to "text-shadow"
 */
function _buildTextShadow(offset, size, color) {
  let shadows = [];
  let from = (size * -1) + offset;
  let to = size + offset;
  for (let i = from; i <= to; i++) {
    for (let j = from; j <= to; j++) {
      shadows.push(color + " " + i + "pt " + j + "pt 0pt");
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
  $(".reveal .slide-background").forEach(function (background) {
    var backgroundContent = background.querySelector(".slide-background-content");
    if (!backgroundContent) {
      return;
    }
    backgroundContent.style.backgroundSize = fit.size;
    backgroundContent.style.backgroundRepeat = fit.repeat;
    backgroundContent.style.backgroundPosition = fit.position;
  });
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
 * The Display object is what we use from OpenLP
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
  _isInitialised: false,
  _initialisedSlidesContainer: null,
  _themeApplied: true,
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
  _logoBackgroundOverrideActive: false,
  _savedBackgroundAttributes: null,

  /**
   * Start up reveal and do any other initialisation
   * @param {object} options - The initialisation options:
   *                           * {bool} isDisplay         - Is this a real display output
   *                           * {bool} doItemTransitions - Transition between service items
   *                           * {number} itemTransitionSpeed - Transition duration between service items in seconds
   *                           * {string} itemTransitionType - Transition easing type for service item transitions
   *                           * {bool} hideMouse         - Hide the cursor when hovering on this display
   */
  init: function (options) {
    // Set defaults for undefined values
    options = options || {};
    let isDisplay = options.isDisplay || false;
    let doItemTransitions = options.doItemTransitions || false;
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
    if (!isDisplay) {
      document.body.classList.add('checkerboard');
    }
    if (hideMouse) {
      document.body.classList.add('hide-mouse');
    }
    Display._slidesContainer = $(".slides")[0];
    Display._footerContainer = $(".footer")[0];
    Display._backgroundsContainer = $(".backgrounds")[0];
    Display._logoScreen = $("#logo-screen")[0];
    Display._logoScreenImage = $("#logo-screen-image")[0];
    Display._doTransitions = isDisplay || !!(options.allowThemeTransitions);
    Display._itemTransitionSpeedSeconds = itemTransitionSpeed;
    Display._itemTransitionType = itemTransitionType;
    // Prevent duplicate Reveal wiring on repeated init calls in the same document lifecycle.
    var isSameSlidesContainer = !!Display._slidesContainer &&
      Display._initialisedSlidesContainer === Display._slidesContainer;
    if (Display._isInitialised && isSameSlidesContainer) {
      Display.setItemTransition(doItemTransitions && isDisplay, itemTransitionSpeed, itemTransitionType);
      return;
    }
    Reveal.initialize(Display._revealConfig);
    Reveal.addEventListener('slidechanged', Display._onSlideChanged);
    Display._isInitialised = true;
    Display._initialisedSlidesContainer = Display._slidesContainer;
    Display.setItemTransition(doItemTransitions && isDisplay, itemTransitionSpeed, itemTransitionType);
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
    var transitionSpeedName = Display._getRevealTransitionSpeed(Display._itemTransitionSpeedSeconds);
    var transitionMs = Math.round(Display._itemTransitionSpeedSeconds * 1000);
    document.body.style.setProperty('--item-transition-ms', transitionMs + 'ms');
    document.body.style.setProperty('--item-transition-easing', Display._getTransitionEasing(Display._itemTransitionType));
    var body = $("body")[0];
    if (enable) {
      body.classList.add("transition");
      Reveal.configure({"backgroundTransition": "fade", "transitionSpeed": transitionSpeedName});
    } else {
      body.classList.remove("transition");
      Reveal.configure({"backgroundTransition": "none"});
    }
  },

  _getRevealTransitionSpeed: function (speedSeconds) {
    if (speedSeconds <= 0.75) {
      return "fast";
    }
    if (speedSeconds >= 1.5) {
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
    body.classList.add("presentation-slide-transition");
    body.style.setProperty('--presentation-slide-transition-ms', Math.round(durationSeconds * 1000) + 'ms');
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
    Display._footerContainer.innerHTML = "";
    Display._slides = {};
  },
  /**
   * Add new item/slides, replacing the old one
   * Clears current list of slides but allows time for a transition animation
   * Items are ordered newest to oldest in the slides container
   * @param {element} new_slides - New slides to display
   * @param {element} is_text - Used to decide if the theme main area constraints should apply
  */
  replaceSlides: function (new_slides, is_text=false) {
    if (Array.isArray(new_slides)) {
      Display._slidesContainer.innerHTML = "";
      new_slides.forEach(function (slide) {
        if (Display._doItemTransitions) {
          slide.setAttribute('data-transition', "fade");
          slide.setAttribute('data-transition-speed', Display._getRevealTransitionSpeed(Display._itemTransitionSpeedSeconds));
        }
        slide.classList.add("future");
        Display.applyTheme(slide, is_text);
        Display._slidesContainer.appendChild(slide);
      });
      Display.reinit();
      if (is_text) {
        Display._reapplyTextThemeAfterLayout(new_slides);
      }
      Display._skipNextTransition = false;
      return;
    }
    if (Display._doItemTransitions) {
      new_slides.setAttribute('data-transition', "fade");
      new_slides.setAttribute('data-transition-speed', Display._getRevealTransitionSpeed(Display._itemTransitionSpeedSeconds));
    }
    new_slides.classList.add("future");
    Display.applyTheme(new_slides, is_text);
    Display._slidesContainer.prepend(new_slides);
    var currentSlide = Reveal.getIndices();
    if (Display._doItemTransitions && Display._slidesContainer.children.length >= 2 && !Display._skipNextTransition) {
      // Set the slide one section ahead so we'll stay on the old slide after reinit
      Reveal.slide(1, currentSlide.v);
      Display.reinit();
      if (is_text) {
        Display._reapplyTextThemeAfterLayout(new_slides);
      }
      // Timeout to allow time to transition before deleting the old slides
      setTimeout(Display._removeLastSection, Math.round(Display._itemTransitionSpeedSeconds * 1000) + 100);
    } else {
      Reveal.slide(0, currentSlide.v);
      Reveal.sync();
      if (is_text) {
        Display._reapplyTextThemeAfterLayout(new_slides);
      }
      Display._removeLastSection();
      Display._skipNextTransition = false;
    }
  },
  /**
   * Removes the last slides item if there are more than one
  */
  _removeLastSection: function () {
    if (Display._slidesContainer.children.length > 1) {
      Display._slidesContainer.lastChild.remove();
    }
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

    // Apply once immediately to avoid a first-frame flash at 0,0.
    if (Array.isArray(targets)) {
      targets.forEach(function (element) {
        Display.applyTheme(element, true);
      });
    } else {
      Display.applyTheme(targets, true);
    }

    // Apply again after Reveal finishes layout/reflow frames.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        if (Array.isArray(targets)) {
          targets.forEach(function (element) {
            Display.applyTheme(element, true);
          });
        } else {
          Display.applyTheme(targets, true);
        }
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
        return !!section.querySelector("p");
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
    var currSlide = $("section.text-slides");
    if (currSlide.length === 0) {
      currSlide = Display._footerContainer;
    } else {
      currSlide = currSlide[0];
    }
    return currSlide.clientHeight >= currSlide.scrollHeight;
  },
  /**
   * Generate the OpenLP startup splashscreen
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
    var existingSection = Display._getReusableFullscreenSection();
    if (existingSection) {
      existingSection.setAttribute("data-background", bg_color);
      _applyFullscreenBackgroundImage(existingSection, bg_color, image, fit);
      return;
    }
    Display.clearSlides();
    var section = document.createElement("section");
    section.setAttribute("id", 0);
    section.setAttribute("data-background", bg_color);
    _applyFullscreenBackgroundImage(section, bg_color, image, fit);
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

  _logTransitionDebug: function (reason) {
    try {
      var revealConfig = (typeof Reveal !== "undefined" && Reveal.getConfig) ? Reveal.getConfig() : {};
      var indices = (typeof Reveal !== "undefined" && Reveal.getIndices) ? Reveal.getIndices() : {};
      var currentSlide = (typeof Reveal !== "undefined" && Reveal.getCurrentSlide) ? Reveal.getCurrentSlide() : null;
      var wrapper = document.querySelector('.reveal');
      var currentTransition = currentSlide ? currentSlide.getAttribute("data-transition") : "";
      var currentTransitionSpeed = currentSlide ? currentSlide.getAttribute("data-transition-speed") : "";
      var pastSlide = document.querySelector('.reveal .slides > section > section.past, .reveal .slides > section.past');
      var futureSlide = document.querySelector('.reveal .slides > section > section.future, .reveal .slides > section.future');
      var currentStyle = currentSlide ? window.getComputedStyle(currentSlide) : null;
      var pastStyle = pastSlide ? window.getComputedStyle(pastSlide) : null;
      var futureStyle = futureSlide ? window.getComputedStyle(futureSlide) : null;
      var payload = {
        reason: reason || "unknown",
        revealTransition: revealConfig.transition || "",
        revealTransitionSpeed: revealConfig.transitionSpeed || "",
        revealClassList: wrapper ? wrapper.className : "",
        indexH: (indices && indices.h !== undefined ? indices.h : null),
        indexV: (indices && indices.v !== undefined ? indices.v : null),
        slideTransition: currentTransition || "",
        slideTransitionSpeed: currentTransitionSpeed || "",
        currentClassList: currentSlide ? currentSlide.className : "",
        currentComputedTransform: currentStyle ? currentStyle.transform : "",
        currentComputedOpacity: currentStyle ? currentStyle.opacity : "",
        pastTransition: pastSlide ? (pastSlide.getAttribute('data-transition') || "") : "",
        pastClassList: pastSlide ? pastSlide.className : "",
        pastComputedTransform: pastStyle ? pastStyle.transform : "",
        pastComputedOpacity: pastStyle ? pastStyle.opacity : "",
        futureTransition: futureSlide ? (futureSlide.getAttribute('data-transition') || "") : "",
        futureClassList: futureSlide ? futureSlide.className : "",
        futureComputedTransform: futureStyle ? futureStyle.transform : "",
        futureComputedOpacity: futureStyle ? futureStyle.opacity : ""
      };
      if (window.displayWatcher && window.displayWatcher.dispatchEvent) {
        window.displayWatcher.dispatchEvent('transition_debug', payload);
      } else {
        console.warn("transition-debug", payload);
      }
    } catch (error) {
      if (window.displayWatcher && window.displayWatcher.dispatchEvent) {
        window.displayWatcher.dispatchEvent('transition_debug', {reason: 'error', message: String(error)});
      } else {
        console.warn("transition-debug error=" + error);
      }
    }
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
    }
  },
  /**
   * Set image slides
   * @param {Object[]} slides - A list of images to add as JS objects [{"path": "url/to/file"}]
   */
  setImageSlides: function (slides) {
    Display._clearSlidesList();
    var parentSection = document.createElement("section");
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
    }
    slides.forEach(function (slide, index) {
      var section = document.createElement("section");
      section.setAttribute("id", index);
      section.setAttribute("style", "height: 100%; width: 100%;");
      section.setAttribute('data-slide', index);
      if (slide.use_background_image) {
        section.classList.add("use-background-image");
        var pdfFit = _resolveBackgroundFit((Display._theme && Display._theme.background_fit) || "cover");
        section.style.backgroundColor = "#000";
        section.style.backgroundImage = "url('" + Display._getFileUrl(slide.path) + "')";
        section.style.backgroundPosition = pdfFit.position;
        section.style.backgroundSize = pdfFit.size;
        section.style.backgroundRepeat = pdfFit.repeat;
        if (slide.pdf_transition_enabled) {
          section.setAttribute("data-transition", Display._getPresentationTransitionName(slide.pdf_transition_effect));
          section.setAttribute("data-transition-speed", Display._getRevealTransitionSpeed(slide.pdf_transition_speed_seconds));
        } else {
          section.setAttribute("data-transition", "none");
        }
      } else {
        var img = document.createElement('img');
        img.src = Display._getFileUrl(slide.path);
        img.setAttribute("style", "width: 100%; height: 100%; margin: 0; object-fit: contain;");
        img.setAttribute('data-slide', index);
        section.appendChild(img);
      }
      parentSection.appendChild(section);
      Display._slides[index.toString()] = index;
    });
    Display.replaceSlides(parentSection);
  },

  updatePdfSlideTransitions: function (settings) {
    settings = settings || {};
    var enabled = !!settings.enabled;
    var speedSeconds = Number(settings.speedSeconds);
    var easing = settings.easing;
    var effect = settings.effect;
    Display._setPresentationSlideTransition(enabled, speedSeconds, easing);
    $(".slides > section > section.use-background-image").forEach(function (section) {
      if (enabled) {
        section.setAttribute("data-transition", Display._getPresentationTransitionName(effect));
        section.setAttribute("data-transition-speed", Display._getRevealTransitionSpeed(speedSeconds));
      } else {
        section.setAttribute("data-transition", "none");
        section.removeAttribute("data-transition-speed");
      }
    });
    Reveal.sync();
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
   * Go to the next slide in the list
  */
  next: Reveal.nextFragment,
  /**
   * Go to the previous slide in the list
  */
  prev: Reveal.prevFragment,
  /**
   * Blank the screen
  */
  toBlack: function () {
    return new Promise((resolve, reject) => {
      /* Avoid race conditions where display goes to transparent and quickly goes to black */
      Display._abortLastTransitionOperation();
      /*
        Reveal's black overlay should be shown before the transitions are
        restored, to avoid screen flashes
      */
      Display._restorePauseBehavior();
      Display._requestAnimationFrameExclusive(function() {
        if (!Reveal.isPaused()) {
          Reveal.togglePause();
        }
        // Hide logo only after black mode is active to avoid flashing slide content.
        Display._hideLogoScreen();
        Display._reenableGlobalTransitions(function() {
          var documentBody = $("body")[0];
          documentBody.style.opacity = 1;
          resolve();
        });
      });
    });
  },
  /**
   * Hide all but theme background
  */
  toTheme: function () {
    return new Promise((resolve, reject) => {
      Display._abortLastTransitionOperation();
      Display._hideLogoScreen();
      Display._restoreThemeBackgroundFromLogo();
      /*
        Reveal's black overlay should be shown before the transitions are
        restored, to avoid screen flashes
      */
      Display._restorePauseBehavior();
      var documentBody = $("body")[0];
      documentBody.style.opacity = 1;
      Display._slidesContainer.style.opacity = 0;
      Display._footerContainer.style.opacity = 0;
      if (Reveal.isPaused()) {
        Reveal.togglePause();
      }
      Display._reenableGlobalTransitions(function() {
        resolve();
      });
    });
  },
  /**
   * Hide everything (CAUTION: Causes a invisible mouse barrier)
  */
  toTransparent: function () {
    return new Promise((resolve, reject) => {
      Display._abortLastTransitionOperation();
      Display._hideLogoScreen();
      var documentBody = $("body")[0];
      documentBody.style.opacity = 0;
      if (!Reveal.isPaused()) {
        /*
          Removing previously the overlay if it's not paused, to avoid a
          content flash while going from black screen to transparent
        */
        document.body.classList.add('is-desktop');
        Reveal.togglePause();
      }
      /*
        Waiting for body transition to happen, now it would be safe to
        hide the Webview (as other transitions were suppressed)
      */
      Display._abortLastTransitionOperation();
      Display._addTransitionEndEventToBody(transitionEndEvent);
      function transitionEndEvent(e) {
        // Targeting only body
        if (e.target != documentBody) {
          return;
        }
        /*
          Disabling all transitions (except body) to allow the Webview to attain the
          transparent state before it gets hidden by Qt.
        */
        document.body.classList.add('disable-transitions');
        document.body.classList.add('is-desktop');
        Display._slidesContainer.style.opacity = 0;
        Display._footerContainer.style.opacity = 0;
        /*
          Repainting before hiding the Webview to avoid flashes when
          showing it again.
        */
        displayWatcher.pleaseRepaint();
        /* Waiting for repaint to happen before saying that it's done. */
        Display._requestAnimationFrameExclusive(function() {
          /* We're transparent now, aborting any transition event between */
          Display._abortLastTransitionOperation();
          resolve();
        });
      }
    });
  },
  /**
   * Hide all but the configured logo background.
   * @param {string} bg_color - The logo screen background color
   * @param {string} image - Path to the logo image
   * @param {string} logo_fit - cover, contain, stretch, repeat
  */
  toLogo: function (bg_color, image, logo_fit) {
    return new Promise((resolve, reject) => {
      Display._abortLastTransitionOperation();
      Display._restorePauseBehavior();
      var documentBody = $("body")[0];
      var wasSlideLayerVisible = parseFloat(getComputedStyle(Display._slidesContainer).opacity || "1") > 0.01;
      documentBody.style.opacity = 1;
      Display._hideLogoScreen();
      if (wasSlideLayerVisible) {
        Display._slidesContainer.style.opacity = 1;
        Display._footerContainer.style.opacity = 1;
      }
      if (Reveal.isPaused()) {
        Reveal.togglePause();
      }
      Display._setLogoScreenBackground(bg_color, null, logo_fit);

      function hideSlideLayerAndResolve() {
        Display._slidesContainer.style.opacity = 0;
        Display._footerContainer.style.opacity = 0;
        Display._setThemeBackgroundToLogo(bg_color, image, logo_fit);
        resolve();
      }

      function fadeLogoOverSlide() {
        Display._requestAnimationFrameExclusive(function() {
          if (!Display._logoScreen) {
            hideSlideLayerAndResolve();
            return;
          }
          Display._logoScreen.classList.add("show");
          var logoScreenStyle = getComputedStyle(Display._logoScreen);
          var hasOpacityTransition =
            document.body.classList.contains("transition") &&
            logoScreenStyle.transitionDuration !== "0s";
          if (!hasOpacityTransition) {
            hideSlideLayerAndResolve();
            return;
          }
          var transitionDone = false;
          var onTransitionEnd = function(event) {
            if (event.target !== Display._logoScreen || event.propertyName !== "opacity") {
              return;
            }
            transitionDone = true;
            Display._logoScreen.removeEventListener("transitionend", onTransitionEnd);
            hideSlideLayerAndResolve();
          };
          Display._logoScreen.addEventListener("transitionend", onTransitionEnd);
          // Safety fallback in case transitionend is skipped by the browser.
          setTimeout(function() {
            if (!transitionDone) {
              Display._logoScreen.removeEventListener("transitionend", onTransitionEnd);
              hideSlideLayerAndResolve();
            }
          }, 900);
        });
      }

      Display._reenableGlobalTransitions(function() {
        if (!image) {
          fadeLogoOverSlide();
          return;
        }
        var preloader = new Image();
        preloader.onload = function() {
          Display._setLogoScreenBackground(bg_color, image, logo_fit);
          fadeLogoOverSlide();
        };
        preloader.onerror = function() {
          Display._setLogoScreenBackground(bg_color, null, logo_fit);
          fadeLogoOverSlide();
        };
        preloader.src = image;
      });
    });
  },
  /**
   * Show the screen
  */
  show: function () {
    return new Promise((resolve, reject) => {
      var documentBody = $("body")[0];
      /*
        Removing transitionend event, avoids the content being hidden if the user
        tries to show content again before toTransparent() transitionend event
        happens
      */
      Display._abortLastTransitionOperation();
      Display._hideLogoScreen();
      Display._restoreThemeBackgroundFromLogo();

      Display._slidesContainer.style.opacity = 1;
      Display._footerContainer.style.opacity = 1;
      if (Reveal.isPaused()) {
        Reveal.togglePause();
      }
      Display._restorePauseBehavior();
      Display._reenableGlobalTransitions(function() {
        documentBody.style.opacity = 1;
        resolve();
      });
    });
  },

  _hideLogoScreen: function() {
    if (Display._logoScreen) {
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

  _setThemeBackgroundToLogo: function(bg_color, image, logo_fit) {
    var rootSlide = Display._getRootSlideSection();
    if (!rootSlide) {
      return;
    }
    if (!Display._logoBackgroundOverrideActive) {
      Display._savedBackgroundAttributes = {
        background: rootSlide.getAttribute("data-background"),
        image: rootSlide.getAttribute("data-background-image"),
        color: rootSlide.getAttribute("data-background-color"),
        size: rootSlide.getAttribute("data-background-size"),
        repeat: rootSlide.getAttribute("data-background-repeat"),
        position: rootSlide.getAttribute("data-background-position")
      };
    }
    var fit = _resolveBackgroundFit(logo_fit || "cover");
    rootSlide.setAttribute("data-background-color", bg_color || "#000");
    if (image) {
      rootSlide.setAttribute("data-background-image", image);
      rootSlide.removeAttribute("data-background");
      rootSlide.setAttribute("data-background-size", fit.size);
      rootSlide.setAttribute("data-background-repeat", fit.repeat);
      rootSlide.setAttribute("data-background-position", fit.position);
    }
    else {
      rootSlide.setAttribute("data-background", bg_color || "#000");
      rootSlide.removeAttribute("data-background-image");
      rootSlide.removeAttribute("data-background-size");
      rootSlide.removeAttribute("data-background-repeat");
      rootSlide.removeAttribute("data-background-position");
    }
    Display._logoBackgroundOverrideActive = true;
    Reveal.sync();
  },

  _restoreThemeBackgroundFromLogo: function() {
    if (!Display._logoBackgroundOverrideActive) {
      return;
    }
    var rootSlide = Display._getRootSlideSection();
    if (!rootSlide) {
      Display._logoBackgroundOverrideActive = false;
      Display._savedBackgroundAttributes = null;
      return;
    }
    var saved = Display._savedBackgroundAttributes || {};
    if (saved.background) {
      rootSlide.setAttribute("data-background", saved.background);
    }
    else {
      rootSlide.removeAttribute("data-background");
    }
    if (saved.image) {
      rootSlide.setAttribute("data-background-image", saved.image);
    }
    else {
      rootSlide.removeAttribute("data-background-image");
    }
    if (saved.color) {
      rootSlide.setAttribute("data-background-color", saved.color);
    }
    else {
      rootSlide.removeAttribute("data-background-color");
    }
    if (saved.size) {
      rootSlide.setAttribute("data-background-size", saved.size);
    }
    else {
      rootSlide.removeAttribute("data-background-size");
    }
    if (saved.repeat) {
      rootSlide.setAttribute("data-background-repeat", saved.repeat);
    }
    else {
      rootSlide.removeAttribute("data-background-repeat");
    }
    if (saved.position) {
      rootSlide.setAttribute("data-background-position", saved.position);
    }
    else {
      rootSlide.removeAttribute("data-background-position");
    }
    Display._logoBackgroundOverrideActive = false;
    Display._savedBackgroundAttributes = null;
    Reveal.sync();
  },

  _reenableGlobalTransitions: function(afterCallback) {
    Display._requestAnimationFrameExclusive(function() {
      /*
        Waiting for the previous opacity + unpause operations to complete
        to restore the transitions behavior
      */
      document.body.classList.remove('disable-transitions');
      if (typeof afterCallback === 'function') {
        afterCallback();
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
   * race condition bugs.
   */
  _abortLastTransitionOperation: function() {
    Display._removeTransitionEndEventToBody();
    cancelAnimationFrame(Display._lastRequestAnimationFrameHandle);
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
    Display.applyTheme(targetElement, targetElement.classList.contains("text-slides"));
    Reveal.sync();
  },
  /**
   * Apply the theme to the provided element
   * @param targetElement The target element to apply the theme (expected to be a `<section>` in the slides container)
   * @param is_text Used to decide if the main area constraints should be applied
   */
  applyTheme: function (targetElement, is_text=true) {
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
      Reveal.configure({"transition": reveal_transition_type, "transitionSpeed": new_transition_speed, "rtl": revealRtl});
    } else {
      Reveal.configure({"transition": "none", "transitionSpeed": "default", "rtl": false});
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
    // Set the background
    var backgroundContent = "";
    var backgroundHtml = "";
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
    if (Display._theme.background_type !== BackgroundType.Image) {
      targetElement.setAttribute("data-background", backgroundContent);
    }
    targetElement.setAttribute("data-background-size", fit.size);
    targetElement.setAttribute("data-background-repeat", fit.repeat);
    targetElement.setAttribute("data-background-position", fit.position);
    requestAnimationFrame(function () {
      _applyBackgroundFitToRenderedSlides(fit);
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
      "font-weight": Display._theme.font_main_bold ? "bold" : "",
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
          _buildTextShadow(Display._theme.font_main_shadow_size, Display._theme.main_outline_size || 0, Display._theme.font_main_shadow_color) :
          []
        )
      ].join(", ")
    };

    var textTargets = targetElement.matches("section.text-slides") ? Array.from(targetElement.children) : [targetElement];
    Array.from(textTargets).forEach(function (slideElement) {
      var contentElement = slideElement.querySelector(".slide-text-content") || slideElement;
      contentElement.style.cssText = "";
      for (var mainKey in mainStyle) {
        if (mainStyle.hasOwnProperty(mainKey)) {
          var priority = (mainKey === "top" || mainKey === "left") ? "important" : "";
          contentElement.style.setProperty(mainKey, mainStyle[mainKey], priority);
        }
      }
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
      "font-weight": Display._theme.font_footer_bold ? "bold" : "",
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
            Display._theme.font_footer_shadow_color) :
          []
        )
      ].join(", ")
    };

    for (var footerKey in footerStyle) {
      if (footerStyle.hasOwnProperty(footerKey)) {
        Display._footerContainer.style.setProperty(footerKey, footerStyle[footerKey]);
      }
    }
  },
  /**
   * Called whenever openlp wants to finish completely with the current text/image slides
   * because a different window (eg presentation or media is going to be displaying the next item
   * and we don't want any flashbacks to the current slide contents
   */
  finishWithCurrentItem: function () {
    Display.setTextSlide('');
    var documentBody = $("body")[0];
    documentBody.style.opacity = 1;
    Display._skipNextTransition = true;
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
