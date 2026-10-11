describe("Image collection fades", function () {
  var frame;

  afterEach(function () {
    frame.remove();
  });

  function loadCollection(options, ready, themeOverrides) {
    frame = document.createElement("iframe");
    frame.onload = function () {
      var win = frame.contentWindow;
      spyOn(win.history, "replaceState");
      win.Display.init(options);
      win.Reveal.addEventListener("ready", function () {
        win.Display.setTheme(Object.assign({
          display_slide_transition: true,
          display_slide_transition_type: win.TransitionType.Fade,
          display_slide_transition_speed: win.TransitionSpeed.Normal,
          background_type: win.BackgroundType.Solid,
          background_color: "#000"
        }, themeOverrides));
        var imageUrl = "/base/tests/js/fixtures/" + encodeURIComponent("Preview images") + "/" +
          encodeURIComponent("Slide #1 (100%) — café.svg");
        win.Display.setImageSlides([{path: imageUrl + "?one"}, {path: imageUrl + "?two"}], "contain", "#fff");
        // Let slide replacement and Reveal's initial no-transition guard settle.
        setTimeout(function () { ready(win); }, 1000);
      });
    };
    frame.srcdoc = '<link rel="stylesheet" href="/base/opal/core/display/html/reveal.css">' +
      '<link rel="stylesheet" href="/base/opal/core/display/html/display.css">' +
      '<div class="reveal"><div class="slides"><section></section></div><div class="footer"></div></div>' +
      '<div id="logo-screen"></div><div id="logo-screen-image"></div>' +
      '<script src="/base/tests/js/fake_webchannel.js"></script>' +
      '<script src="/base/opal/core/display/html/reveal.js"></script>' +
      '<script src="/base/opal/core/display/html/display-init.js"></script>' +
      '<script src="/base/opal/core/display/html/display.js"></script>';
    document.body.appendChild(frame);
  }

  [false, true].forEach(function (isDisplay) {
    [false, true].forEach(function (itemTransitions) {
      it("animates both image backgrounds in " + (isDisplay ? "output" : "controller previews") +
          " with item transitions " + (itemTransitions ? "enabled" : "disabled"), function (done) {
        loadCollection({isDisplay: isDisplay, allowThemeTransitions: true, doItemTransitions: itemTransitions},
          function (win) {
            var outgoing = win.Reveal.getCurrentSlide().slideBackgroundElement;
            expect(win.getComputedStyle(outgoing).opacity).toBe("1");
            win.Display.goToSlide(1);
            var incoming = win.Reveal.getCurrentSlide().slideBackgroundElement;
            setTimeout(function () {
              [outgoing, incoming].forEach(function (background) {
                var opacity = Number(win.getComputedStyle(background).opacity);
                expect(opacity).toBeGreaterThan(0);
                expect(opacity).toBeLessThan(1);
              });
              setTimeout(function () {
                expect(win.getComputedStyle(outgoing).opacity).toBe("0");
                expect(win.getComputedStyle(incoming).opacity).toBe("1");
                done();
              }, 850);
            }, 150);
          });
      });
    });
  });

  [{speed: TransitionSpeed.Fast, seconds: 0.4}, {speed: TransitionSpeed.Slow, seconds: 1.2}].forEach(function (test) {
    it("honours the configured " + test.seconds + " second fade without item transitions", function (done) {
      loadCollection({isDisplay: false, allowThemeTransitions: true, doItemTransitions: false}, function (win) {
        win.Display.goToSlide(1);
        var background = win.Reveal.getCurrentSlide().slideBackgroundElement;
        expect(win.getComputedStyle(background).transitionDuration).toBe(test.seconds + "s");
        setTimeout(function () {
          var opacity = Number(win.getComputedStyle(background).opacity);
          expect(opacity).toBeGreaterThan(0);
          expect(opacity).toBeLessThan(1);
          done();
        }, 150);
      }, {display_slide_transition_speed: test.speed});
    });
  });

  [false, true].forEach(function (itemTransitions) {
    it("keeps slide changes immediate when theme transitions are disabled and item transitions are " +
        itemTransitions, function (done) {
      loadCollection({isDisplay: false, allowThemeTransitions: true, doItemTransitions: itemTransitions}, function (win) {
        win.Display.goToSlide(1);
        var background = win.Reveal.getCurrentSlide().slideBackgroundElement;
        expect(win.getComputedStyle(background).transitionDuration).toBe("0s");
        expect(win.getComputedStyle(background).opacity).toBe("1");
        done();
      }, {display_slide_transition: false});
    });
  });
});
