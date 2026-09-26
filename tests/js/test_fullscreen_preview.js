describe("Presentation preview backgrounds", function () {
  var frame;

  afterEach(function () {
    frame.remove();
  });

  it("loads a thumbnail from an encoded library path, including after a background refresh", function (done) {
    frame = document.createElement("iframe");
    frame.onload = function () {
      var display = frame.contentWindow.Display;
      var reveal = frame.contentWindow.Reveal;
      spyOn(frame.contentWindow.history, "replaceState");
      display.init({isDisplay: false});
      reveal.addEventListener("ready", function () {
        var imageUrl = "/base/tests/js/fixtures/" + encodeURIComponent("Preview images") + "/" +
          encodeURIComponent("Slide #1 (100%) — café.svg");
        display.setStartupSplashScreen("#000", null, "contain");
        display.setFullscreenImage("#000", imageUrl);
        // Full syncs happen on layout/theme updates as well as when changing slides.
        reveal.sync();
        var background = reveal.getCurrentSlide().slideBackgroundContentElement.style.backgroundImage;
        expect(background).not.toContain("%2520");
        expect(background).not.toContain("%2523");
        var image = new frame.contentWindow.Image();
        image.onload = function () {
          expect(image.naturalWidth).toBe(160);
          expect(image.naturalHeight).toBe(90);
          done();
        };
        image.onerror = function () { done.fail("Preview background could not load: " + background); };
        // Load the actual CSS URL, not the input URL, so double encoding cannot pass unnoticed.
        image.src = background.slice(5, -2);
      });
    };
    frame.srcdoc = '<div class="reveal"><div class="slides"><section></section></div></div>' +
      '<div class="footer"></div><div id="logo-screen"></div><div id="logo-screen-image"></div>' +
      '<script src="/base/tests/js/fake_webchannel.js"></script>' +
      '<script src="/base/openlp/core/display/html/reveal.js"></script>' +
      '<script src="/base/openlp/core/display/html/display-init.js"></script>' +
      '<script src="/base/openlp/core/display/html/display.js"></script>';
    document.body.appendChild(frame);
  });

  it("replaces the rendered startup logo and refreshes subsequent slide images", function (done) {
    // Use a separate document so Reveal builds real backgrounds without shared test spies/state.
    frame = document.createElement("iframe");
    frame.onload = function () {
      var display = frame.contentWindow.Display;
      var reveal = frame.contentWindow.Reveal;
      // srcdoc has no navigable URL; history is unrelated to rendering the preview.
      spyOn(frame.contentWindow.history, "replaceState");
      display.init({isDisplay: false});
      reveal.addEventListener("ready", function () {
        try {
          display.setStartupSplashScreen("#000", "/logo.png", "contain");
          var section = reveal.getCurrentSlide();
          expect(section.slideBackgroundContentElement.style.backgroundImage).toContain("/logo.png");

          display.setFullscreenImage("#111", "/slide1.png");
          expect(reveal.getCurrentSlide()).toBe(section);
          expect(section.slideBackgroundContentElement.style.backgroundImage).toContain("/slide1.png");
          expect(section.slideBackgroundElement.style.backgroundColor).toBe("rgb(17, 17, 17)");

          display.setFullscreenImage("#222", "/slide2.png");
          expect(section.slideBackgroundContentElement.style.backgroundImage).toContain("/slide2.png");

          display.setFullscreenImageFromData("#333", "cHJldmlldw==");
          expect(section.slideBackgroundContentElement.style.backgroundImage)
            .toContain("data:image/jpeg;base64,cHJldmlldw==");
          expect(section.slideBackgroundElement.style.backgroundColor).toBe("rgb(51, 51, 51)");
          done();
        } catch (error) {
          done.fail(error);
        }
      });
    };
    frame.srcdoc = '<div class="reveal"><div class="slides"><section></section></div></div>' +
      '<div class="footer"></div><div id="logo-screen"></div><div id="logo-screen-image"></div>' +
      '<script src="/base/tests/js/fake_webchannel.js"></script>' +
      '<script src="/base/openlp/core/display/html/reveal.js"></script>' +
      '<script src="/base/openlp/core/display/html/display-init.js"></script>' +
      '<script src="/base/openlp/core/display/html/display.js"></script>';
    document.body.appendChild(frame);
  });
});
