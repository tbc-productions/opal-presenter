function createCoverTestDiv(attrs) {
  var div = document.createElement("div");
  Object.keys(attrs).forEach(function (key) { div.setAttribute(key, attrs[key]); });
  document.body.appendChild(div);
  return div;
}

describe("Refreshing an active logo", function () {
  var slides, footer, logo;

  beforeEach(function () {
    slides = createCoverTestDiv({"class": "slides"});
    footer = createCoverTestDiv({"class": "footer"});
    logo = createCoverTestDiv({"id": "logo-screen", "class": "show"});
    slides.style.opacity = "0";
    footer.style.opacity = "0";
    Display._slidesContainer = slides;
    Display._footerContainer = footer;
    Display._logoScreen = logo;
    spyOn(Display, "_beginTransitionOperation").and.returnValue(1);
    spyOn(Display, "_isCurrentTransition").and.returnValue(true);
    spyOn(Display, "_restorePauseBehavior");
    spyOn(Display, "_hideLogoScreen").and.callThrough();
    spyOn(Display, "_setLogoScreenBackground");
    Display._displayMode = 'logo';
    Display._doItemTransitions = false;
    spyOn(Reveal, "isPaused").and.returnValue(false);
    spyOn(Display, "_requestAnimationFrameExclusive").and.callFake(function (callback) { callback(); });
  });

  afterEach(function () {
    slides.remove();
    footer.remove();
    logo.remove();
    Display._displayMode = 'show';
  });

  it("keeps the cover and content hidden throughout a settings refresh", function (done) {
    var result = Display.toLogo("#123456", null, "contain", false);
    // Check immediately, before a browser frame or asynchronous image load can run.
    expect(Display._hideLogoScreen).not.toHaveBeenCalled();
    expect(logo.classList.contains("show")).toBe(true);
    expect(slides.style.opacity).toBe("0");
    expect(footer.style.opacity).toBe("0");
    result.then(function () {
      expect(Display._setLogoScreenBackground).toHaveBeenCalledWith("#123456", null, "contain");
      done();
    });
  });
});
