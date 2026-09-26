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
    Display._logoBackgroundOverrideActive = true;
    spyOn(Display, "_beginTransitionOperation").and.returnValue(1);
    spyOn(Display, "_restorePauseBehavior");
    spyOn(Display, "_hideLogoScreen").and.callThrough();
    spyOn(Display, "_setLogoScreenBackground");
    spyOn(Display, "_setThemeBackgroundToLogo");
  });

  afterEach(function () {
    slides.remove();
    footer.remove();
    logo.remove();
    Display._logoBackgroundOverrideActive = false;
  });

  it("keeps the cover and content hidden throughout a settings refresh", function (done) {
    var result = Display.toLogo("#123456", "updated-logo.png", "contain", false);
    // Check immediately, before a browser frame or asynchronous image load can run.
    expect(Display._hideLogoScreen).not.toHaveBeenCalled();
    expect(logo.classList.contains("show")).toBe(true);
    expect(slides.style.opacity).toBe("0");
    expect(footer.style.opacity).toBe("0");
    result.then(function () {
      expect(Display._setThemeBackgroundToLogo).toHaveBeenCalledWith("#123456", "updated-logo.png", "contain");
      done();
    });
  });
});
