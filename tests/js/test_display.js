function _createDiv(attrs, inElement) {
    var div = document.createElement("div");
    for (key in attrs) {
        div.setAttribute(key, attrs[key]);
    }
    if (inElement) {
      inElement.appendChild(div);
    } else {
      document.body.appendChild(div);
    }
    return div;
}

describe("The enumeration object", function () {
  it("BackgroundType should exist", function () {
    expect(BackgroundType).toBeDefined();
  });

  it("GradientType should exist", function () {
    expect(GradientType).toBeDefined();
  });

  it("HorizontalAlign should exist", function () {
    expect(HorizontalAlign).toBeDefined();
  });

  it("VerticalAlign should exist", function () {
    expect(VerticalAlign).toBeDefined();
  });

  it("AudioState should exist", function () {
    expect(AudioState).toBeDefined();
  });

  it("TransitionState should exist", function(){
    expect(TransitionState).toBeDefined();
  });

  it("AnimationState should exist", function(){
    expect(AnimationState).toBeDefined();
  });
});

describe("The function", function () {
  it("$() should return the right element", function () {
    var div = _createDiv({"id": "dollar-test"});
    expect($("#dollar-test")[0]).toBe(div);
  });

  it("_buildLinearGradient() should build the correct string", function () {
    var gradient = _buildLinearGradient("to bottom", "#000", "#fff");
    expect(gradient).toBe("linear-gradient(to bottom, #000, #fff) fixed");
  });

  it("_buildRadialGradient() should build the correct string", function () {
    var gradient = _buildRadialGradient(10, "#000", "#fff");
    expect(gradient).toBe("radial-gradient(#000, #fff) fixed");
  });

  it("_buildTextOutline should return an array of text-shadow values", function () {
    let shadows = _buildTextOutline(2, "#fff");
    expect(shadows).toEqual([
      "#fff -2pt -2pt 0pt",
      "#fff -2pt -1pt 0pt",
      "#fff -2pt 0pt 0pt",
      "#fff -2pt 1pt 0pt",
      "#fff -2pt 2pt 0pt",
      "#fff -1pt -2pt 0pt",
      "#fff -1pt -1pt 0pt",
      "#fff -1pt 0pt 0pt",
      "#fff -1pt 1pt 0pt",
      "#fff -1pt 2pt 0pt",
      "#fff 0pt -2pt 0pt",
      "#fff 0pt -1pt 0pt",
      "#fff 0pt 0pt 0pt",
      "#fff 0pt 1pt 0pt",
      "#fff 0pt 2pt 0pt",
      "#fff 1pt -2pt 0pt",
      "#fff 1pt -1pt 0pt",
      "#fff 1pt 0pt 0pt",
      "#fff 1pt 1pt 0pt",
      "#fff 1pt 2pt 0pt",
      "#fff 2pt -2pt 0pt",
      "#fff 2pt -1pt 0pt",
      "#fff 2pt 0pt 0pt",
      "#fff 2pt 1pt 0pt",
      "#fff 2pt 2pt 0pt"
    ]);
  });

  it("_buildTextShadow should return an array of text-shadow values", function () {
    let shadow = _buildTextShadow(2, 2, "#acf");
    expect(shadow).toEqual([
      "#acf 0pt 0pt 0pt",
      "#acf 0pt 1pt 0pt",
      "#acf 0pt 2pt 0pt",
      "#acf 0pt 3pt 0pt",
      "#acf 0pt 4pt 0pt",
      "#acf 1pt 0pt 0pt",
      "#acf 1pt 1pt 0pt",
      "#acf 1pt 2pt 0pt",
      "#acf 1pt 3pt 0pt",
      "#acf 1pt 4pt 0pt",
      "#acf 2pt 0pt 0pt",
      "#acf 2pt 1pt 0pt",
      "#acf 2pt 2pt 0pt",
      "#acf 2pt 3pt 0pt",
      "#acf 2pt 4pt 0pt",
      "#acf 3pt 0pt 0pt",
      "#acf 3pt 1pt 0pt",
      "#acf 3pt 2pt 0pt",
      "#acf 3pt 3pt 0pt",
      "#acf 3pt 4pt 0pt",
      "#acf 4pt 0pt 0pt",
      "#acf 4pt 1pt 0pt",
      "#acf 4pt 2pt 0pt",
      "#acf 4pt 3pt 0pt",
      "#acf 4pt 4pt 0pt"
    ]);
  });

  it("_getStyle should return the correct style on an element", function () {
    var div = _createDiv({"id": "style-test"});
    div.style.setProperty("width", "100px");
    expect(_getStyle($("#style-test")[0], "width")).toBe("100px");
  });

  it("_nl2br should turn UNIX newlines into <br> tags", function () {
    var text = "Amazing grace, how sweet the sound\nThat saved a wretch like me";
    expect(_nl2br(text)).toEqual("Amazing grace, how sweet the sound<br>That saved a wretch like me");
  });

  it("_nl2br should turn Windows newlines into <br> tags", function () {
    var text = "Amazing grace, how sweet the sound\r\nThat saved a wretch like me";
    expect(_nl2br(text)).toEqual("Amazing grace, how sweet the sound<br>That saved a wretch like me");
  });

  it("_prepareText should turn verse text into a paragraph", function () {
    var text = "Amazing grace, how sweet the sound\nThat saved a wretch like me";
    expect(_prepareText(text)).toEqual("<p>Amazing grace, how sweet the sound<br>That saved a wretch like me</p>");
  });
});

describe("The Display object", function () {

  it("should start with a blank _slides object", function () {
    expect(Display._slides).toEqual({});
  });

  it("should have the correct Reveal config", function () {
    expect(Display._revealConfig).toEqual({
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
    });
  });

  it("should have an init() method", function () {
    expect(Display.init).toBeDefined();
  });

  it("should initialise Reveal when init is called", function () {
    spyOn(Reveal, "initialize");
    spyOn(Reveal, "addEventListener");
    document.body.innerHTML = "";
    Display.init();
    expect(Reveal.initialize).toHaveBeenCalled();
  });

  it("should not initialise Reveal twice on repeated init for same display DOM", function () {
    spyOn(Reveal, "initialize");
    spyOn(Reveal, "addEventListener");
    document.body.innerHTML = "";
    _createDiv({"class": "slides"});
    _createDiv({"class": "footer"});
    Display._isInitialised = false;

    Display.init();
    Display.init();

    expect(Reveal.initialize).toHaveBeenCalledTimes(1);
    expect(Reveal.addEventListener).toHaveBeenCalledTimes(1);
    Display._isInitialised = false;
  });

  it("should have checkerboard class when init is called when not display", function () {
    spyOn(Reveal, "initialize");
    spyOn(Reveal, "addEventListener");
    document.body.innerHTML = "";
    document.body.classList = "";
    Display.init({isDisplay: false});
    expect(document.body.classList.contains('checkerboard')).toEqual(true);
  });

  it("should not have checkerboard class when init is called when is a display", function () {
    spyOn(Reveal, "initialize");
    spyOn(Reveal, "addEventListener");
    document.body.innerHTML = "";
    document.body.classList = "";
    Display.init({isDisplay: true});
    expect(document.body.classList.contains('checkerboard')).toEqual(false);
  });

  it("should have a reinit() method", function () {
    expect(Display.reinit).toBeDefined();
  });

  it("should sync Reveal and set to first slide when reinit is called", function () {
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");
    Display.reinit();
    expect(Reveal.sync).toHaveBeenCalled();
    expect(Reveal.slide).toHaveBeenCalledWith(0);
  });

  it("should have a setItemTransition() method", function () {
    expect(Display.setItemTransition).toBeDefined();
  });

  it("should register _onSlideChanged event for slide change", function () {
    spyOn(Reveal, "initialize");
    spyOn(Reveal, "addEventListener");
    document.body.innerHTML = "";
    Display.init();
    expect(Reveal.addEventListener).toHaveBeenCalledWith('slidechanged', Display._onSlideChanged);
  });

  it("should disable item transitions when passed string false values", function () {
    spyOn(Reveal, "configure");
    document.body.innerHTML = "";
    _createDiv({"class": "slides"});
    _createDiv({"class": "footer"});
    _createDiv({"class": "backgrounds"});
    _createDiv({"id": "logo-screen"});
    _createDiv({"id": "logo-screen-image"});
    Display._isInitialised = false;

    Display.init({isDisplay: "true", doItemTransitions: "false", allowThemeTransitions: "false"});

    expect(Display._doItemTransitions).toEqual(false);
    expect(document.body.classList.contains("transition")).toEqual(false);
  });

  it("should apply updated item transition settings without reinit", function () {
    document.body.innerHTML = "";
    _createDiv({"class": "slides"});
    _createDiv({"class": "footer"});
    _createDiv({"class": "backgrounds"});
    _createDiv({"id": "logo-screen"});
    _createDiv({"id": "logo-screen-image"});
    Display._isInitialised = false;

    Display.init({isDisplay: true, doItemTransitions: false, allowThemeTransitions: true});
    Display.updateItemTransitionSettings(true, 1.5, "ease-in-out");

    expect(Display._doItemTransitions).toEqual(true);
    expect(document.body.classList.contains("transition")).toEqual(true);
    expect(document.body.style.getPropertyValue('--item-transition-ms')).toEqual('1500ms');
    expect(document.body.style.getPropertyValue('--item-transition-easing')).toEqual('ease-in-out');
  });

  it("should have a correctly functioning clearSlides() method", function () {
    expect(Display.clearSlides).toBeDefined();

    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><p></p></section>";
    Display._slidesContainer = slidesDiv;
    var footerDiv = _createDiv({"class": "footer"});
    Display._footerContainer = footerDiv;

    Display.clearSlides();
    expect($(".slides")[0].innerHTML).toEqual("");
    expect(Display._slides).toEqual({});
  });

  it("should have a correct goToSlide() method", function () {
    spyOn(Reveal, "slide");
    spyOn(Display, "_slides");
    Display._slides["v1"] = 0;

    Display.goToSlide("v1");
    expect(Reveal.slide).toHaveBeenCalledWith(0, 0);
  });

  it("should navigate horizontal text slides using Reveal's horizontal axis", function () {
    spyOn(Reveal, "slide");
    spyOn(Display, "_slides");
    Display._textSlideDirection = TransitionDirection.Horizontal;
    Display._slides["v1"] = {h: 1, v: 0};

    Display.goToSlide("v1");

    expect(Reveal.slide).toHaveBeenCalledWith(1, 0);
  });

  it("should have an alert() method", function () {
    expect(Display.alert).toBeDefined();
  });

  it("should run preview transition between V1 and V2", function () {
    spyOn(window, "setTimeout").and.callFake(function (handler) {
      handler();
      return 1;
    });
    spyOn(window, "clearTimeout");
    spyOn(Display, "goToSlide");
    Display._previewTransitionTimeoutHandles = [];

    Display.previewTransition(250, 1000);

    expect(Display.goToSlide).toHaveBeenCalledWith("V2");
    expect(Display.goToSlide).toHaveBeenCalledWith("V1");
    expect(window.setTimeout).toHaveBeenCalledWith(jasmine.any(Function), 250);
    expect(window.setTimeout).toHaveBeenCalledWith(jasmine.any(Function), 1250);
  });

});

describe("Transitions", function () {
  beforeEach(function() {
    document.body.innerHTML = "";
    _createDiv({"class": "slides"});
    _createDiv({"class": "footer"});
    Display._slides = {};
  });
  afterEach(function() {
    // Reset theme
    Display._theme = null;
  });

  it("should have a correctly functioning setItemTransition() method", function () {
    spyOn(Reveal, "configure");
    Display.setItemTransition(true);
    expect(Reveal.configure).toHaveBeenCalledWith({"backgroundTransition": "fade", "transitionSpeed": "default"});
  });

  it("should apply custom transition speed when setItemTransition() is called", function () {
    spyOn(Reveal, "configure");
    Display.setItemTransition(true, 2.0);
    expect(Reveal.configure).toHaveBeenCalledWith({"backgroundTransition": "fade", "transitionSpeed": "slow"});
    expect(document.body.style.getPropertyValue('--item-transition-ms')).toEqual('2000ms');
    expect(document.body.style.getPropertyValue('--item-transition-easing')).toEqual('cubic-bezier(0.4, 0, 0.2, 1)');
  });

  it("should have enabled transitions when _doTransitions is true and applyTheme is run", function () {
    Display._doTransitions = true;
    var theme = {
      "display_slide_transition": true,
      "display_slide_transition_type": TransitionType.Slide,
      "display_slide_transition_speed": TransitionSpeed.Fast
    }
    Display.setTheme(theme);
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><section><p></p></section></section>";
    Display._slidesContainer = slidesDiv;

    Display.applyTheme(Display._slidesContainer.children[0])

    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition")).toEqual("slide-horizontal");
    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition-speed")).toEqual("fast");
  });

  it("should have not enabled transitions when init() with no transitions and setTheme is run", function () {
    Display._doTransitions = false;
    var theme = {
      "display_slide_transition": true,
      "display_slide_transition_type": TransitionType.Slide,
      "display_slide_transition_speed": TransitionSpeed.Fast,
    }
    Display.setTheme(theme);
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><section><p></p></section></section>";
    Display._slidesContainer = slidesDiv;

    Display.applyTheme(Display._slidesContainer.children[0])

    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition")).toEqual("none");
  });

  it("should have enabled transitions in the correct direction", function () {
    Display._doTransitions = true;
    var theme = {
      "display_slide_transition": true,
      "display_slide_transition_type": TransitionType.Convex,
      "display_slide_transition_speed": TransitionSpeed.Slow,
      "display_slide_transition_direction": TransitionDirection.Vertical,
      "display_slide_transition_reverse": true,
    }
    Display.setTheme(theme);
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><section><p></p></section></section>";
    Display._slidesContainer = slidesDiv;

    Display.applyTheme(Display._slidesContainer.children[0])

    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition")).toEqual("convex");
    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition-speed")).toEqual("slow");
  });

  it("should keep fade transitions Reveal.js-compatible", function () {
    Display._doTransitions = true;
    var theme = {
      "display_slide_transition": true,
      "display_slide_transition_type": TransitionType.Fade,
      "display_slide_transition_speed": TransitionSpeed.Normal,
      "display_slide_transition_direction": TransitionDirection.Vertical,
      "display_slide_transition_reverse": true,
    }
    Display.setTheme(theme);
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><section><p></p></section></section>";
    Display._slidesContainer = slidesDiv;

    Display.applyTheme(Display._slidesContainer.children[0])

    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition")).toEqual("fade");
    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition-speed")).toEqual("default");
  });

  it("should support string-encoded non-fade transition values", function () {
    Display._doTransitions = true;
    var theme = {
      "display_slide_transition": true,
      "display_slide_transition_type": "convex",
      "display_slide_transition_speed": "slow",
      "display_slide_transition_direction": "vertical",
      "display_slide_transition_reverse": "true",
    }
    Display.setTheme(theme);
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><section><p></p></section></section>";
    Display._slidesContainer = slidesDiv;

    Display.applyTheme(Display._slidesContainer.children[0])

    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition")).toEqual("convex");
    expect(Display._slidesContainer.children[0].children[0].getAttribute("data-transition-speed")).toEqual("slow");
  });

  it("should configure Reveal rtl for reversed horizontal theme transitions", function () {
    Display._doTransitions = true;
    spyOn(Reveal, "configure");
    var theme = {
      "display_slide_transition": true,
      "display_slide_transition_type": TransitionType.Slide,
      "display_slide_transition_speed": TransitionSpeed.Fast,
      "display_slide_transition_direction": TransitionDirection.Horizontal,
      "display_slide_transition_reverse": true,
    }
    Display.setTheme(theme);
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><p></p></section>";
    Display._slidesContainer = slidesDiv;

    Display.applyTheme(Display._slidesContainer.children[0], true)

    expect(Reveal.configure).toHaveBeenCalledWith({"transition": "slide", "transitionSpeed": "fast", "rtl": true});
  });

  it("should apply background fit attributes to an image background slide", function () {
    Display._doTransitions = false;
    var theme = {
      "background_type": BackgroundType.Image,
      "background_filename": "/file/path",
      "background_fit": "stretch"
    };
    Display.setTheme(theme);
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section></section>";
    Display._slidesContainer = slidesDiv;

    Display.applyTheme(Display._slidesContainer.children[0], false);

    expect(Display._slidesContainer.children[0].getAttribute("data-background-image")).toEqual("/file/path");
    expect(Display._slidesContainer.children[0].getAttribute("data-background-color")).toEqual("#000");
    expect(Display._slidesContainer.children[0].getAttribute("data-background-size")).toEqual("100% 100%");
    expect(Display._slidesContainer.children[0].getAttribute("data-background-repeat")).toEqual("no-repeat");
    expect(Display._slidesContainer.children[0].getAttribute("data-background-position")).toEqual("0% 0%");
  });

  it("should use item transition speed for item replacement transition timing", function () {
    spyOn(Display, "reinit");
    spyOn(Display, "applyTheme");
    spyOn(Display, "_removeLastSection");
    spyOn(window, "setTimeout");
    spyOn(Reveal, "getIndices").and.returnValue({h: 0, v: 0});
    spyOn(Reveal, "slide");

    Display._doItemTransitions = true;
    Display._itemTransitionSpeedSeconds = 2.0;
    var slidesDiv = _createDiv({"class": "slides"});
    slidesDiv.innerHTML = "<section><section><p></p></section></section>";
    Display._slidesContainer = slidesDiv;
    var newSlides = document.createElement("section");
    newSlides.innerHTML = "<section><p></p></section>";

    Display.replaceSlides(newSlides);

    expect(window.setTimeout).toHaveBeenCalledWith(Display._removeLastSection, 2100);
    expect(newSlides.getAttribute("data-transition-speed")).toEqual("slow");
  });

  it("should apply selected transition type easing when setItemTransition() is called", function () {
    spyOn(Reveal, "configure");
    Display.setItemTransition(true, 0.8, "linear");
    expect(document.body.style.getPropertyValue('--item-transition-easing')).toEqual('linear');

    Display.setItemTransition(true, 0.8, "balanced");
    expect(document.body.style.getPropertyValue('--item-transition-easing')).toEqual('cubic-bezier(0.4, 0, 0.2, 1)');
  });
});

describe("Display.alert", function () {
  var alertContainer, alertBackground, alertText, settings, text;

  beforeEach(function () {
    document.body.innerHTML = "";
    alertContainer = _createDiv({"class": "alert-container"});
    alertBackground = _createDiv({"id": "alert-background", "class": "hide"});
    alertText = _createDiv({"id": "alert-text", "class": "hide"});
    settings = {
      "location": 1,
      "fontFace": "sans-serif",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    };
    text = "Display.alert";
  });

  it("should return null if called without any text", function () {
    expect(Display.alert("", settings)).toBeNull();
  });

  it("should set the correct alert text", function () {
    spyOn(Display, "showAlert");

    Display.alert(text, settings);

    expect(Display.showAlert).toHaveBeenCalled();
  });

  it("should call the addAlertToQueue method if an alert is displaying", function () {
    spyOn(Display, "addAlertToQueue");
    Display._alerts = [];
    Display._alertState = AlertState.Displaying;

    Display.alert(text, settings);

    expect(Display.addAlertToQueue).toHaveBeenCalledWith(text, settings);
  });
});

describe("Display.showAlert", function () {
  var alertContainer, alertBackground, alertText, settings;

  beforeEach(function () {
    document.body.innerHTML = "";
    alertContainer = _createDiv({"class": "alert-container"});
    alertBackground = _createDiv({"id": "alert-background", "class": "hide"});
    alertText = _createDiv({"id": "alert-text", "class": "hide"});
    settings = {
      "location": 1,
      "fontFace": "sans-serif",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    };
  });

  it("should create a stylesheet for the settings", function () {
    spyOn(window, "_createStyle");
    Display.showAlert("Test Display.showAlert - stylesheet", settings);

    expect(_createStyle).toHaveBeenCalledWith("#alert-background.settings", {
      backgroundColor: settings["backgroundColor"],
      fontFamily: "'" + settings["fontFace"] + "'",
      fontSize: settings["fontSize"] + 'pt',
      color: settings["fontColor"]
    });
  });

  it("should change fontFace to 'sans-serif' if no font face is provided", function () {
    spyOn(window, "_createStyle");
    Display.showAlert("Test Display.showAlert - fontFace fix", {
      "location": 1,
      "fontFace": "",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    });

    expect(_createStyle).toHaveBeenCalledWith("#alert-background.settings", {
      backgroundColor: settings["backgroundColor"],
      fontFamily: "sans-serif",
      fontSize: settings["fontSize"] + 'pt',
      color: settings["fontColor"]
    });
  });

  it("should change fontFace to 'sans-serif' if 'Sans Serif' is provided", function () {
    spyOn(window, "_createStyle");
    Display.showAlert("Test Display.showAlert - fontFace fix", {
      "location": 1,
      "fontFace": "Sans Serif",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    });

    expect(_createStyle).toHaveBeenCalledWith("#alert-background.settings", {
      backgroundColor: settings["backgroundColor"],
      fontFamily: "sans-serif",
      fontSize: settings["fontSize"] + 'pt',
      color: settings["fontColor"]
    });
  });

  it("should set the alert state to AlertState.Displaying", function () {
    Display.showAlert("Test Display.showAlert - state", settings);

    expect(Display._alertState).toEqual(AlertState.Displaying);
  });

  it("should remove the 'hide' classes and add the 'show' classes", function () {
    Display.showAlert("Test Display.showAlert - classes", settings);

    expect($("#alert-background")[0].classList.contains("hide")).toEqual(false);
    expect($("#alert-background")[0].classList.contains("show")).toEqual(true);
    expect($("#alert-text")[0].classList.contains("hide")).toEqual(false);
    expect($("#alert-text")[0].classList.contains("show")).toEqual(true);
  });
});

describe("Display.hideAlert", function () {
  var alertContainer, alertBackground, alertText, settings;

  beforeEach(function () {
    document.body.innerHTML = "";
    alertContainer = _createDiv({"class": "alert-container"});
    alertBackground = _createDiv({"id": "alert-background", "class": "hide"});
    alertText = _createDiv({"id": "alert-text", "class": "hide"});
    settings = {
      "location": 1,
      "fontFace": "sans-serif",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    };
  });

  it("should set the alert state to AlertState.NotDisplaying", function () {
    Display.showAlert("test", settings);

    Display.hideAlert();

    expect(Display._alertState).toEqual(AlertState.NotDisplaying);
  });

  it("should hide the alert divs when called", function() {
    Display.showAlert("test", settings);

    Display.hideAlert();

    expect(Display._transitionState).toEqual(TransitionState.ExitTransition);
    expect(alertBackground.classList.contains("hide")).toEqual(true);
    expect(alertBackground.classList.contains("show")).toEqual(false);
    expect(alertText.classList.contains("hide")).toEqual(true);
    expect(alertText.classList.contains("show")).toEqual(false);
  });
});

describe("Display.setAlertLocation", function() {
  var alertContainer, alertBackground, alertText, settings;

  beforeEach(function () {
    document.body.innerHTML = "";
    alertContainer = _createDiv({"class": "alert-container"});
    alertBackground = _createDiv({"id": "alert-background", "class": "hide"});
    alertText = _createDiv({"id": "alert-text", "class": "hide"});
    settings = {
      "location": 1,
      "fontFace": "sans-serif",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    };
  });

  it("should set the correct class when location is top of the page", function () {
    Display.setAlertLocation(0);

    expect(alertContainer.className).toEqual("alert-container top");
  });

  it("should set the correct class when location is middle of the page", function () {
    Display.setAlertLocation(1);

    expect(alertContainer.className).toEqual("alert-container middle");
  });

  it("should set the correct class when location is bottom of the page", function () {
    Display.setAlertLocation(2);

    expect(alertContainer.className).toEqual("alert-container bottom");
  });
});

describe("Display.addAlertToQueue", function () {
  var alertContainer, alertBackground, alertText, settings;

  beforeEach(function () {
    document.body.innerHTML = "";
    alertContainer = _createDiv({"class": "alert-container"});
    alertBackground = _createDiv({"id": "alert-background", "class": "hide"});
    alertText = _createDiv({"id": "alert-text", "class": "hide"});
    settings = {
      "location": 1,
      "fontFace": "sans-serif",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    };
  });

  it("should add an alert to the queue if one is displaying already", function() {
    Display._alerts = [];
    Display._alertState = AlertState.Displaying;
    var alertObject = {text: "Testing alert queue", settings: settings};

    Display.addAlertToQueue("Testing alert queue", settings);

    expect(Display._alerts.length).toEqual(1);
    expect(Display._alerts[0]).toEqual(alertObject);
  });
});

describe("Display.showNextAlert", function () {
  var alertContainer, alertBackground, alertText, settings;

  beforeEach(function () {
    document.body.innerHTML = "";
    alertContainer = _createDiv({"class": "alert-container"});
    alertBackground = _createDiv({"id": "alert-background", "class": "hide"});
    alertText = _createDiv({"id": "alert-text", "class": "hide"});
    settings = {
      "location": 1,
      "fontFace": "sans-serif",
      "fontSize": 40,
      "fontColor": "#ffffff",
      "backgroundColor": "#660000",
      "timeout": 5,
      "repeat": 1,
      "scroll": true
    };
  });

  it("should return null if there are no alerts in the queue", function () {
    Display._alerts = [];
    Display.showNextAlert();

    expect(Display.showNextAlert()).toBeNull();
  });

  it("should call the alert function correctly if there is an alert in the queue", function () {
    Display._alerts.push({text: "Queued Alert", settings: settings});
    spyOn(Display, "showAlert");
    Display.showNextAlert();

    expect(Display.showAlert).toHaveBeenCalled();
    expect(Display.showAlert).toHaveBeenCalledWith("Queued Alert", settings);
  });
});

describe("Display.alertTransitionEndEvent", function() {
  var e = { stopPropagation: function () { } };

  it("should call event.stopPropagation()", function () {
    spyOn(e, "stopPropagation");

    Display.alertTransitionEndEvent(e);

    expect(e.stopPropagation).toHaveBeenCalled();
  });

  it("should set the correct state after EntranceTransition", function() {
    Display._transitionState = TransitionState.EntranceTransition;

    Display.alertTransitionEndEvent(e);

    expect(Display._transitionState).toEqual(TransitionState.NoTransition);
  });

  it("should set the correct state after ExitTransition, call hideAlert() and showNextAlert()", function() {
    spyOn(Display, "hideAlert");
    spyOn(Display, "showNextAlert");
    Display._transitionState = TransitionState.ExitTransition;

    Display.alertTransitionEndEvent(e);

    expect(Display._transitionState).toEqual(TransitionState.NoTransition);
    expect(Display.hideAlert).toHaveBeenCalled();
    expect(Display.showNextAlert).toHaveBeenCalled();
  });
});

describe("Display.alertAnimationEndEvent", function () {
  var e = { stopPropagation: function () { } };

  it("should call the hideAlert method", function() {
    spyOn(Display, "hideAlert");

    Display.alertAnimationEndEvent(e);

    expect(Display.hideAlert).toHaveBeenCalled();
  });
});

describe("Display.setTextSlide", function () {
  beforeEach(function() {
    document.body.innerHTML = "";
    var slides_container = _createDiv({"class": "slides"});
    var footer_container = _createDiv({"class": "footer"});
    Display._slidesContainer = slides_container;
    Display._footerContainer = footer_container;
    Display._slides = {};
  });

  it("should add a new slide", function () {
    var text = "Amazing grace,\nhow sweet the sound";
    spyOn(Display, "reinit");

    Display.setTextSlide(text);

    expect(Display._slides["test-slide"]).toEqual(0);
    expect($(".slides > section > section").length).toEqual(1);
    expect($(".slides > section > section")[0].innerHTML).toEqual(_prepareText(text));
    expect(Display.reinit).toHaveBeenCalled();
  });

  it("should update an existing slide", function () {
    var text = "That saved a wretch\nlike me";
    spyOn(Display, "reinit");
    Display.setTextSlide("Amazing grace,\nhow sweet the sound");

    Display.setTextSlide(text);

    expect(Display._slides["test-slide"]).toEqual(0);
    expect($(".slides > section > section").length).toEqual(1);
    expect($(".slides > section > section")[0].innerHTML).toEqual(_prepareText(text));
    expect(Display.reinit).toHaveBeenCalledTimes(1); // only called once for the first setTextSlide
  });

  it("should give the new slide the future class", function () {
    var text = "That saved a wretch\nlike me";
    spyOn(Display, "reinit");
    Display.setTextSlide("Amazing grace,\nhow sweet the sound");

    Display.setTextSlide(text);

    expect($(".slides > section > section")[0].classList.contains("future")).toEqual(true);
  });
});

describe("Display.doesContentFit", function () {
  beforeEach(function () {
    document.body.innerHTML = "";
    var slidesContainer = _createDiv({"class": "slides"});
    var footerContainer = _createDiv({"class": "footer"});
    Display._slidesContainer = slidesContainer;
    Display._footerContainer = footerContainer;
    Display._slides = {};
    Display._theme = null;
    Display._themeApplied = true;
  });

  function _buildSlideWithContent(clientHeight, scrollHeight, wrapInSlides) {
    var wrapper = document.createElement("section");
    wrapper.classList.add("text-slides");
    var slide = document.createElement("section");
    slide.classList.add("text-slide");
    var content = document.createElement("div");
    content.classList.add("slide-text-content");
    Object.defineProperty(content, "clientHeight", {value: clientHeight, configurable: true});
    Object.defineProperty(content, "scrollHeight", {value: scrollHeight, configurable: true});
    slide.appendChild(content);
    if (wrapInSlides) {
      wrapper.appendChild(slide);
      Display._slidesContainer.appendChild(wrapper);
    } else {
      Display._slidesContainer.appendChild(slide);
    }
    return content;
  }

  it("reports overflow on vertical layouts", function () {
    _buildSlideWithContent(100, 200, true);
    expect(Display.doesContentFit()).toBe(false);
  });

  it("reports overflow on horizontal layouts", function () {
    _buildSlideWithContent(100, 500, false);
    expect(Display.doesContentFit()).toBe(false);
  });

  it("reports fit when content fits within the main area", function () {
    _buildSlideWithContent(500, 100, false);
    expect(Display.doesContentFit()).toBe(true);
  });

  it("falls back to the footer when no slide content element exists", function () {
    Object.defineProperty(Display._footerContainer, "clientHeight", {value: 100, configurable: true});
    Object.defineProperty(Display._footerContainer, "scrollHeight", {value: 100, configurable: true});
    expect(Display.doesContentFit()).toBe(true);
  });
});

describe("Display.setTextSlides", function () {
  var textSlides;

  beforeEach(function() {
    document.body.innerHTML = "";
    var revealContainer = Display._revealContainer = _createDiv({"class": "reveal"})
    var slides_container = _createDiv({"class": "slides"}, revealContainer);
    var footer_container = _createDiv({"class": "footer"}, revealContainer);
    Display._slidesContainer = slides_container;
    Display._footerContainer = footer_container;
    Display._slides = {};
    textSlides = [
      {
        "verse": "v1",
        "text": "Amazing grace, how sweet the sound\nThat saved a wretch like me\n" +
                "I once was lost, but now I'm found\nWas blind but now I see",
        "footer": "Public Domain"
      },
      {
        "verse": "v2",
        "text": "'twas Grace that taught, my heart to fear\nAnd grace, my fears relieved.\n" +
                "How precious did that grace appear,\nthe hour I first believed.",
        "footer": "Public Domain"
      }
    ];
  });

  it("should add a list of slides", function () {
    var slides = textSlides;
    spyOn(Display, "clearSlides");
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTextSlides(slides);

    expect(Display.clearSlides).toHaveBeenCalledTimes(0);
    expect(Display._slides["v1"]).toEqual(0);
    expect(Display._slides["v2"]).toEqual(1);
    expect($(".slides > section > section").length).toEqual(2);
    expect(Reveal.sync).toHaveBeenCalledTimes(1);
  });

  it("should correctly set outline width", function () {
    const slides = [textSlides[0]];
    const theme = {
      'font_main_color': 'yellow',
      'font_main_outline': true,
      'font_main_outline_size': 42,
      'font_main_outline_color': 'red'
    };
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTheme(theme);
    Display.setTextSlides(slides);

    const mainSection = document.querySelector('.slides section.text-slide');
    expect(mainSection.style['text-shadow']).toEqual(_buildTextOutline(42, 'red').join(', '));
  })

  it("should correctly set text alignment,\
      (check the order of alignments in the emuns are the same in both js and python)", function () {
    const slides = [textSlides[0]];
    //
    const theme = {
      'display_horizontal_align': 3,
      'display_vertical_align': 1,
      'display_horizontal_align_footer': 2,
      'display_vertical_align_footer': 0
    };
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTheme(theme);
    Display.setTextSlides(slides);

    const mainSection = document.querySelector('.slides section.text-slide');
    expect(mainSection.style['text-align']).toEqual('justify');
    expect(mainSection.style['justify-content']).toEqual('center');
    const footerDiv = $(".footer")[0];
    expect(footerDiv.style['text-align']).toEqual('center');
    expect(footerDiv.style['justify-content']).toEqual('flex-start');
  })

  it("should enable shadows", function () {
    const slides = [textSlides[0]];
    //
    const theme = {
      'font_main_shadow': true,
      'font_main_shadow_color': "#000",
      'font_main_shadow_size': 5
    };
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTheme(theme);
    Display.setTextSlides(slides);

    const mainSection = document.querySelector('.slides section.text-slide');
    expect(mainSection.style['text-shadow']).not.toEqual('');
  })

  it("should not enable shadows", function () {
    const slides = [textSlides[0]];
    //
    const theme = {
      'font_main_shadow': false,
      'font_main_shadow_color': "#000",
      'font_main_shadow_size': 5
    };
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTheme(theme);
    Display.setTextSlides(slides);

    const mainSection = document.querySelector('.slides section.text-slide');
    expect(mainSection.style['text-shadow']).toEqual('');
  })

  it("should correctly set slide size position to theme size when adding a text slide", function () {
    const slides = [textSlides[0]];
    //
    const theme = {
      'font_main_y': 789,
      'font_main_x': 1000,
      'font_main_width': 1230,
      'font_main_height': 4560
    };
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTheme(theme);
    Display.setTextSlides(slides);

    const mainSection = document.querySelector('.slides section.text-slide');
    expect(mainSection.style.getPropertyValue('--theme-main-top')).toEqual('789px');
    expect(mainSection.style.getPropertyValue('--theme-main-left')).toEqual('1000px');
    expect(mainSection.style.getPropertyValue('--theme-main-width')).toEqual('1230px');
    expect(mainSection.style.getPropertyValue('--theme-main-height')).toEqual('4560px');
    expect(window.getComputedStyle(mainSection).top).toEqual('789px');
    expect(window.getComputedStyle(mainSection).left).toEqual('1000px');
    expect(window.getComputedStyle(mainSection).width).toEqual('1230px');
    expect(window.getComputedStyle(mainSection).height).toEqual('4560px');
  })

  it("should work correctly with different footer contents per slide", function () {
    var slides = textSlides;
    spyOn(Display, "clearSlides");
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTextSlides(slides);

    expect(Display.clearSlides).toHaveBeenCalledTimes(0);
    expect($(".footer > .footer-item").length).toEqual(2);
    expect(document.querySelectorAll(".footer > .footer-item")[0].innerHTML).toEqual(slides[0].footer);
    expect(document.querySelectorAll(".footer > .footer-item")[1].innerHTML).toEqual(slides[1].footer);
  });

  it("should select correct footer index when resetting text", function () {
    var slides = textSlides;
    slides[1]['footer'] = 'Public Domain, Second Test';

    Display.init({isDisplay: false});
    Display.setTextSlides(slides);
    spyOn(Reveal, 'getIndices').and.returnValue({v: 1, h: 0});
    slides[1]['footer'] = 'Second Slide';
    Display.setTextSlides(slides);

    expect(document.querySelectorAll(".footer > .footer-item")[1].classList.contains('active')).toBeTruthy();
  });

  it("should build horizontal theme text slides as sibling sections", function () {
    var slides = textSlides;
    var theme = {
      'display_slide_transition_direction': TransitionDirection.Horizontal
    };
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setTheme(theme);
    Display.setTextSlides(slides);

    expect($(".slides > section").length).toEqual(2);
    expect($(".slides > section > section").length).toEqual(0);
    expect(Display._slides["v1"]).toEqual({h: 0, v: 0});
    expect(Display._slides["v2"]).toEqual({h: 1, v: 0});
  });
});

describe("Display.setImageSlides", function () {
  beforeEach(function() {
    document.body.innerHTML = "";
    var slides_container = _createDiv({"class": "slides"});
    var footer_container = _createDiv({"class": "footer"});
    Display._slidesContainer = slides_container;
    Display._footerContainer = footer_container;
    Display._slides = {};
  });

  it("should add a list of images", function () {
    var slides = [{"path": "openlp-library://local-file//openlp1.jpg"}, {"path": "openlp-library://local-file//openlp2.jpg"}];
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setImageSlides(slides);

    expect(Display._slides["0"]).toEqual(0);
    expect(Display._slides["1"]).toEqual(1);
    expect($(".slides > section > section").length).toEqual(2);
    expect($(".slides > section > section > img").length).toEqual(2);
    expect($(".slides > section > section > img")[0].getAttribute("src")).toEqual("openlp-library://local-file//openlp1.jpg");
    expect($(".slides > section > section > img")[0].getAttribute("style")).toEqual("width: 100%; height: 100%; margin: 0; object-fit: contain;");
    expect($(".slides > section > section > img")[1].getAttribute("src")).toEqual("openlp-library://local-file//openlp2.jpg");
    expect($(".slides > section > section > img")[1].getAttribute("style")).toEqual("width: 100%; height: 100%; margin: 0; object-fit: contain;");
    expect(Reveal.sync).toHaveBeenCalledTimes(1);
  });

  it("should use native backgrounds for image slides when fade transitions are enabled", function () {
    var slides = [{"path": "openlp-library://local-file//openlp1.jpg"}];
    Display._theme = {
      "display_slide_transition": true,
      "display_slide_transition_type": TransitionType.Fade
    };
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setImageSlides(slides);

    expect($(".slides > section > section > img").length).toEqual(0);
    expect($(".slides > section > section")[0].getAttribute("data-background-image"))
      .toEqual("openlp-library://local-file//openlp1.jpg");
    expect($(".slides > section > section")[0].getAttribute("data-background-size")).toEqual("contain");
    expect($(".slides > section > section")[0].getAttribute("data-background-repeat")).toEqual("no-repeat");
    expect($(".slides > section > section")[0].getAttribute("data-background-position")).toEqual("50% 50%");
    expect($(".slides > section > section")[0].getAttribute("data-transition")).toEqual("none");
    expect($(".slides > section > section")[0].getAttribute("data-background-transition")).toEqual("fade");
  });

  it("should use reveal background image mode when requested", function () {
    var slides = [{
      "path": "openlp-library://local-file//openlp1.jpg",
      "use_background_image": true,
      "pdf_transition_enabled": true,
      "pdf_transition_effect": TransitionType.Fade,
      "pdf_transition_speed_seconds": 0.8,
      "pdf_transition_easing": "balanced"
    }];
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setImageSlides(slides);

    expect($(".slides > section > section > img").length).toEqual(0);
    expect($(".slides > section > section")[0].classList.contains("use-background-image")).toBeTrue();
    expect($(".slides > section > section")[0].getAttribute("data-background-image"))
      .toEqual("openlp-library://local-file//openlp1.jpg");
    expect($(".slides > section > section")[0].getAttribute("data-background-size")).toEqual("cover");
    expect($(".slides > section > section")[0].getAttribute("data-background-repeat")).toEqual("no-repeat");
    expect($(".slides > section > section")[0].getAttribute("data-background-position")).toEqual("50% 50%");
    expect($(".slides > section > section")[0].getAttribute("data-transition")).toEqual("none");
    expect($(".slides > section > section")[0].getAttribute("data-background-transition")).toEqual("fade");
    expect($(".slides > section > section")[0].getAttribute("data-transition-speed")).toEqual("default");
    expect($("body")[0].classList.contains("presentation-slide-transition")).toBeTrue();
    expect($("body")[0].style.getPropertyValue("--presentation-slide-transition-ms")).toEqual("800ms");
    expect($("body")[0].style.getPropertyValue("--presentation-slide-transition-easing")).toEqual("cubic-bezier(0.4, 0, 0.2, 1)");
    expect(Reveal.sync).toHaveBeenCalledTimes(1);
  });

  it("should disable transitions for PDF background slides when disabled in settings", function () {
    var slides = [{
      "path": "openlp-library://local-file//openlp1.jpg",
      "use_background_image": true,
      "pdf_transition_enabled": false,
      "pdf_transition_effect": TransitionType.Zoom,
      "pdf_transition_speed_seconds": 1.2,
      "pdf_transition_easing": "ease-out"
    }];
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setImageSlides(slides);

    expect($(".slides > section > section")[0].getAttribute("data-transition")).toEqual("none");
    expect($(".slides > section > section")[0].getAttribute("data-background-transition")).toBeNull();
    expect($("body")[0].classList.contains("presentation-slide-transition")).toBeFalse();
  });

  it("should keep non-fade transitions on image slide content", function () {
    var slides = [{"path": "openlp-library://local-file//openlp1.jpg"}];
    Display._theme = {"display_slide_transition_type": TransitionType.Slide};
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setImageSlides(slides);

    expect($(".slides > section > section > img").length).toEqual(1);
    expect($(".slides > section > section")[0].getAttribute("data-background-image")).toBeNull();
    expect($(".slides > section > section > img")[0].getAttribute("src")).toEqual("openlp-library://local-file//openlp1.jpg");
  });
});

describe("Display background fit mapping", function () {
  it("should map background fit modes to the expected CSS properties", function () {
    expect(_resolveBackgroundFit("cover")).toEqual({size: "cover", repeat: "no-repeat", position: "50% 50%", objectFit: "cover"});
    expect(_resolveBackgroundFit("contain")).toEqual({size: "contain", repeat: "no-repeat", position: "50% 50%", objectFit: "contain"});
    expect(_resolveBackgroundFit("stretch")).toEqual({size: "100% 100%", repeat: "no-repeat", position: "0% 0%", objectFit: "fill"});
    expect(_resolveBackgroundFit("repeat")).toEqual({size: "auto", repeat: "repeat", position: "0% 0%", objectFit: "cover"});
  });
});

describe("Display.setFullscreenImage", function () {
  beforeEach(function() {
    document.body.innerHTML = "";
    var slides_container = _createDiv({"class": "slides"});
    var footer_container = _createDiv({"class": "footer"});
    Display._slidesContainer = slides_container;
    Display._footerContainer = footer_container;
    Display._slides = {};
  });

  it("should set a fullscreen image", function () {
    var image = "file:///openlp1.jpg";
    let bg_color = "#000";
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setFullscreenImage(bg_color, image);

    expect($(".slides > section > img").length).toEqual(0);
    expect($(".slides > section")[0].getAttribute("data-background-image")).toEqual("openlp-library://local-file//openlp1.jpg");
    expect($(".slides > section")[0].getAttribute("data-background-color")).toEqual("#000");
    expect($(".slides > section")[0].getAttribute("data-background-size")).toEqual("cover");
    expect($(".slides > section")[0].getAttribute("data-background-repeat")).toEqual("no-repeat");
    expect($(".slides > section")[0].getAttribute("data-background-position")).toEqual("50% 50%");
    expect(Reveal.sync).toHaveBeenCalledTimes(1);
  });

  it("should update existing fullscreen image without calling Reveal sync/slide", function () {
    var image = "file:///openlp2.jpg";
    let bg_color = "#111";
    var section = document.createElement("section");
    section.setAttribute("id", 0);
    section.setAttribute("data-background", "#000");
    var img = document.createElement("img");
    img.src = "file:///openlp1.jpg";
    section.appendChild(img);
    section.slideBackgroundElement = document.createElement("div");
    section.slideBackgroundContentElement = document.createElement("div");
    Display._slidesContainer.appendChild(section);
    Display._slides = {'0': 0};

    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setFullscreenImage(bg_color, image);

    expect($(".slides > section > img").length).toEqual(0);
    expect($(".slides > section")[0].getAttribute("data-background-image")).toEqual("openlp-library://local-file//openlp2.jpg");
    expect($(".slides > section")[0].getAttribute("data-background-color")).toEqual("#111");
    expect(section.slideBackgroundContentElement.style.backgroundImage).toContain("openlp-library://local-file//openlp2.jpg");
    expect(section.slideBackgroundElement.style.backgroundColor).toEqual("rgb(17, 17, 17)");
    expect(Reveal.sync).not.toHaveBeenCalled();
    expect(Reveal.slide).not.toHaveBeenCalled();
  });
});

describe("Display.setFullscreenImageFromData", function () {
  beforeEach(function() {
    document.body.innerHTML = "";
    var slides_container = _createDiv({"class": "slides"});
    var footer_container = _createDiv({"class": "footer"});
    Display._slidesContainer = slides_container;
    Display._footerContainer = footer_container;
    Display._slides = {};
  });

  it("should set fullscreen image from data using replaceSlides path", function () {
    spyOn(Display, "replaceSlides");
    var image_data = "abc123";

    Display.setFullscreenImageFromData("#000", image_data);

    expect(Display.replaceSlides).toHaveBeenCalledTimes(1);
    expect(Display._slides['0']).toEqual(0);
  });

  it("should update existing fullscreen image data without replaceSlides", function () {
    var section = document.createElement("section");
    section.setAttribute("id", 0);
    section.setAttribute("data-background", "#000");
    var img = document.createElement("img");
    img.src = "data:image/jpeg;base64,old";
    section.appendChild(img);
    section.slideBackgroundElement = document.createElement("div");
    section.slideBackgroundContentElement = document.createElement("div");
    Display._slidesContainer.appendChild(section);
    Display._slides = {'0': 0};
    spyOn(Display, "replaceSlides");

    Display.setFullscreenImageFromData("#222", "new-data");

    expect(Display.replaceSlides).not.toHaveBeenCalled();
    expect($(".slides > section > img").length).toEqual(0);
    expect($(".slides > section")[0].getAttribute("data-background-image")).toEqual("data:image/jpeg;base64,new-data");
    expect($(".slides > section")[0].getAttribute("data-background-color")).toEqual("#222");
    expect($(".slides > section")[0].getAttribute("data-background-position")).toEqual("50% 50%");
    expect(section.slideBackgroundContentElement.style.backgroundImage).toContain("data:image/jpeg;base64,new-data");
  });
});

describe("Display.setBackgroundImage and Display.resetTheme", function () {
  beforeEach(function() {
    document.body.innerHTML = "";
    var slides_container = _createDiv({"class": "slides"});
    Display._slidesContainer = slides_container;
    var section = document.createElement("section");
    Display._slidesContainer.appendChild(section);
  });

  it("should set the background image data and call sync once for set slides and again for set background", function () {
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setBackgroundImage("/file/path");

    expect($(".slides > section")[0].getAttribute("data-background-image")).toEqual("/file/path");
    expect($(".slides > section")[0].getAttribute("data-background-color")).toEqual("#000");
    expect($(".slides > section")[0].getAttribute("data-background-size")).toEqual("cover");
    expect($(".slides > section")[0].getAttribute("data-background-repeat")).toEqual("no-repeat");
    expect($(".slides > section")[0].getAttribute("data-background-position")).toEqual("50% 50%");
    expect(Reveal.sync).toHaveBeenCalledTimes(1);
  });

  it("should restore the background image to the theme", function () {
    Display._theme = {
      'background_type': BackgroundType.Image,
      'background_filename': '/another/path'
    };
    $(".slides > section")[0].setAttribute("data-background", "/file/path");
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.resetTheme();

    expect($(".slides > section")[0].getAttribute("data-background-image")).toEqual("/another/path");
    expect($(".slides > section")[0].getAttribute("data-background-size")).toEqual("cover");
    expect($(".slides > section")[0].getAttribute("data-background-position")).toEqual("50% 50%");
    expect(Reveal.sync).toHaveBeenCalledTimes(1);
  });
});

describe("Display.setVideo", function () {
  beforeEach(function() {
    document.body.innerHTML = "";
    var slides_container = _createDiv({"class": "slides"});
    Display._slidesContainer = slides_container;
    Display._slides = {};
  });

  it("should add a video to the page", function () {
    var video = {"path": "file:///video.mp4"};
    spyOn(Reveal, "sync");
    spyOn(Reveal, "slide");

    Display.setVideo(video);

    expect($(".slides > section").length).toEqual(1);
    expect($(".slides > section > video").length).toEqual(1);
    expect($(".slides > section > video")[0].src).toEqual("file:///video.mp4")
    expect(Reveal.sync).toHaveBeenCalledTimes(1);
  });
});

describe("Display.playVideo", function () {
  var playCalled = false,
      mockVideo = {
        play: function () {
          playCalled = true;
        }
      };

  beforeEach(function () {
    spyOn(window, "$").and.returnValue([mockVideo]);
  });

  it("should play the video when called", function () {
    Display.playVideo();
    expect(playCalled).toEqual(true);
  });
});

describe("Display.pauseVideo", function () {
  var pauseCalled = false,
      mockVideo = {
        pause: function () {
          pauseCalled = true;
        }
      };

  beforeEach(function () {
    spyOn(window, "$").and.returnValue([mockVideo]);
  });

  it("should pause the video when called", function () {
    Display.pauseVideo();
    expect(pauseCalled).toEqual(true);
  });
});

describe("Display.stopVideo", function () {
  var pauseCalled = false,
      mockVideo = {
        pause: function () {
          pauseCalled = true;
        },
        currentTime: 10.0
      };

  beforeEach(function () {
    spyOn(window, "$").and.returnValue([mockVideo]);
  });

  it("should play the video when called", function () {
    Display.stopVideo();
    expect(pauseCalled).toEqual(true);
    expect(mockVideo.currentTime).toEqual(0.0);
  });
});

describe("Display.seekVideo", function () {
  var mockVideo = {
        currentTime: 1.0
      };

  beforeEach(function () {
    spyOn(window, "$").and.returnValue([mockVideo]);
  });

  it("should seek to the specified position within the video when called", function () {
    Display.seekVideo(7.34);
    expect(mockVideo.currentTime).toEqual(7.34);
  });
});

describe("Display.setPlaybackRate", function () {
  var mockVideo = {
        playbackRate: 1.0
      };

  beforeEach(function () {
    spyOn(window, "$").and.returnValue([mockVideo]);
  });

  it("should set the playback rate of the video when called", function () {
    // Let's sound like chipmunks!
    Display.setPlaybackRate(1.25);
    expect(mockVideo.playbackRate).toEqual(1.25);
  });
});

describe("Display.setVideoVolume", function () {
  var mockVideo = {
        volume: 1.0
      };

  beforeEach(function () {
    spyOn(window, "$").and.returnValue([mockVideo]);
  });

  it("should set the correct volume of the video when called", function () {
    // Make it quiet
    Display.setVideoVolume(30);
    expect(mockVideo.volume).toEqual(0.3);
  });
});

describe("Display.toggleVideoMute", function () {
  var mockVideo = {
        muted: false
      };

  beforeEach(function () {
    spyOn(window, "$").and.returnValue([mockVideo]);
  });

  it("should mute the video when called", function () {
    mockVideo.muted = false;
    Display.toggleVideoMute();
    expect(mockVideo.muted).toEqual(true);
  });

  it("should unmute the video when called", function () {
    mockVideo.muted = true;
    Display.toggleVideoMute();
    expect(mockVideo.muted).toEqual(false);
  });
});

describe("localFile", function() {
  it('should translate file:// protocol to openlp-library://local-file/ scheme', function() {
    const fileUrl = 'file:///home/path/to/image.png';
    const resultFile = Display._getFileUrl(fileUrl);
    expect(resultFile).toEqual('openlp-library://local-file//home/path/to/image.png');
  })
})

describe("Reveal slidechanged event", function () {
  it("should swap footer content", function (done) {
    var slides = [
      {
        "verse": "v1",
        "text": "Amazing grace, how sweet the sound\nThat saved a wretch like me\n" +
                "I once was lost, but now I'm found\nWas blind but now I see",
        "footer": "Public Domain"
      },
      {
        "verse": "v2",
        "text": "'twas Grace that taught, my heart to fear\nAnd grace, my fears relieved.\n" +
                "How precious did that grace appear,\nthe hour I first believed.",
        "footer": "Public Domain, Second Test"
      }
    ];

    document.body.innerHTML = '';
    var revealContainer = Display._revealContainer = _createDiv({"class": "reveal"});

    var slidesDiv = _createDiv({"class": "slides"}, revealContainer);
    slidesDiv.innerHTML = "<section><p></p></section>";
    Display._slidesContainer = slidesDiv;
    var footerDiv = _createDiv({"class": "footer"}, revealContainer);
    Display._footerContainer = footerDiv;

    Display.init({isDisplay: false, doItemTransitions: false});
    var oldDisplaySlideChanged = Display._onSlideChanged; 
    Display._onSlideChanged = function(event) {
      oldDisplaySlideChanged(event);
      expect(document.querySelector(".footer > .footer-item.active").getAttribute('data-slide')).toEqual('1');
      done();
    }
    Display.setTextSlides(slides);

    var currentSlide = Display._slidesContainer.querySelector('*:nth-child(2)');
    currentSlide.id = '1';
    Display._onSlideChanged({currentSlide: currentSlide});
  });
});
