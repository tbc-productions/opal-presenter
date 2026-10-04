/* Exercise the real renderer; unit spies cannot detect missing animation frames. */
describe("Display transition contract", function () {
  var frame;
  var imageUrl = "/base/tests/js/fixtures/Preview%20images/Slide%20%231%20(100%25)%20%E2%80%94%20caf%C3%A9.svg";
  function wait(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }
  function theme(win, overrides) {
    return Object.assign({
      display_slide_transition: false,
      display_slide_transition_type: win.TransitionType.Fade,
      display_slide_transition_speed: win.TransitionSpeed.Normal,
      display_slide_transition_direction: win.TransitionDirection.Horizontal,
      background_type: win.BackgroundType.Solid, background_color: '#123456',
      font_main_size: 24, font_main_width: 300, font_main_height: 150, font_main_x: 0, font_main_y: 0,
      font_main_color: '#fff', font_main_name: 'Arial',
      font_footer_size: 12, font_footer_width: 300, font_footer_height: 30, font_footer_x: 0, font_footer_y: 150
    }, overrides);
  }
  function render(win, type, label) {
    win.Display.setTheme(theme(win, {
      display_slide_transition_direction: type === 'vertical song' ?
        win.TransitionDirection.Vertical : win.TransitionDirection.Horizontal
    }));
    if (type === 'image' || type === 'PDF') {
      win.Display.setImageSlides([0, 1].map(function (index) {
        return {path: imageUrl + '?' + label + index, use_background_image: type === 'PDF',
          pdf_transition_enabled: true, pdf_transition_effect: 'fade', pdf_transition_speed_seconds: 0.4};
      }), 'contain', '#fff');
    } else if (type === 'media') {
      win.Display.setVideo({path: ''});
    } else {
      win.Display.setTextSlides([{verse: 'v1', text: label, footer: label + ' footer'},
        {verse: 'v2', text: label + ' second'}]);
    }
  }
  function scenario(done, run) {
    frame = document.createElement('iframe');
    frame.onload = function () {
      var win = frame.contentWindow;
      win.displayWatcher.pleaseRepaint = function () {};
      spyOn(win.history, 'replaceState');
      win.Display.init({isDisplay: false, allowThemeTransitions: true, doItemTransitions: false});
      win.Reveal.addEventListener('ready', function () {
        Promise.resolve().then(function () { return run(win); }).then(done, done.fail);
      });
    };
    frame.srcdoc = '<link rel="stylesheet" href="/base/openlp/core/display/html/reveal.css">' +
      '<link rel="stylesheet" href="/base/openlp/core/display/html/display.css">' +
      '<div class="reveal"><div class="slides"><section></section></div><div class="footer"></div></div>' +
      '<div id="logo-screen"></div><div id="logo-screen-image"></div>' +
      '<script src="/base/tests/js/fake_webchannel.js"></script>' +
      '<script src="/base/openlp/core/display/html/reveal.js"></script>' +
      '<script src="/base/openlp/core/display/html/display-init.js"></script>' +
      '<script src="/base/openlp/core/display/html/display.js"></script>';
    document.body.appendChild(frame);
  }
  afterEach(function () { frame.remove(); });

  ['horizontal song', 'vertical song', 'image', 'PDF', 'media'].forEach(function (source) {
    ['horizontal song', 'vertical song', 'image', 'PDF', 'media'].forEach(function (target) {
      it('fades ' + source + ' to ' + target + ' without inheriting the slide transition', function (done) {
        scenario(done, async function (win) {
          render(win, source, 'outgoing');
          await wait(100);
          win.Display.updateItemTransitionSettings(true, 0.3, 'linear');
          render(win, target, 'incoming');
          var snapshot = win.Display._pendingItemSnapshot;
          expect(snapshot).not.toBeNull();
          expect(win.Reveal.getTotalSlides()).toBe(target === 'media' ? 1 : 2);
          await wait(120);
          var opacity = Number(win.getComputedStyle(snapshot).opacity);
          expect(opacity).toBeGreaterThan(0);
          expect(opacity).toBeLessThan(1);
          await wait(300);
          expect(win.document.querySelector('.display-item-snapshot')).toBeNull();
          expect(win.Reveal.getIndices().h).toBe(0);
          expect(win.Reveal.getIndices().v).toBe(0);
        });
      });
    });
  });

  ['show', 'black', 'logo', 'theme', 'desktop'].forEach(function (source) {
    ['show', 'black', 'logo', 'theme', 'desktop'].forEach(function (target) {
      [false, true].forEach(function (enabled) {
        it(source + ' → ' + target + ' completes with transitions ' + enabled, function (done) {
          scenario(done, async function (win) {
            render(win, 'image', 'original');
            await wait(60);
            function mode(name) {
              if (name === 'logo') { return win.Display.toLogo('#abcdef', null, 'contain'); }
              return win.Display[{show: 'show', black: 'toBlack', theme: 'toTheme', desktop: 'toTransparent'}[name]]();
            }
            await mode(source);
            win.Display.updateItemTransitionSettings(enabled, 0.12, 'linear');
            await mode(target);
            expect(win.Display._displayMode).toBe(target);
            expect(win.getComputedStyle(win.document.body).opacity).toBe(target === 'desktop' ? '0' : '1');
            if (target !== 'desktop') {
              expect(win.Reveal.isPaused()).toBe(target === 'black');
              expect(win.document.body.classList.contains('disable-transitions')).toBe(false);
              expect(win.Display._logoScreen.classList.contains('show')).toBe(target === 'logo');
            }
            if (target === 'theme') {
              expect(win.getComputedStyle(win.Reveal.getCurrentSlide().slideBackgroundElement).opacity).toBe('0');
            }
            expect(win.Display._getRootSlideSection().getAttribute('data-background-color')).toBe('#fff');
          });
        });
      });
    });
  });

  it('retains the newest item after rapid replacements', function (done) {
    scenario(done, async function (win) {
      render(win, 'image', 'first');
      await wait(60);
      win.Display.updateItemTransitionSettings(true, 0.3, 'linear');
      render(win, 'horizontal song', 'second');
      await wait(80);
      render(win, 'vertical song', 'third');
      await wait(80);
      render(win, 'image', 'fourth');
      await wait(450);
      expect(win.document.querySelector('.display-item-snapshot')).toBeNull();
      expect(win.Reveal.getCurrentSlide().getAttribute('data-slide-image')).toContain('fourth0');
      expect(win.Display._slidesContainer.children.length).toBe(1);
    });
  });

  it('fades a logo over a native window and back without replacing the transparent backdrop', function (done) {
    scenario(done, async function (win) {
      render(win, 'horizontal song', 'outgoing');
      await wait(60);
      win.Display.finishWithCurrentItem();
      await win.Display.toTransparent(true);
      win.Display.updateItemTransitionSettings(true, 0.4, 'linear');
      var cover = win.Display.toLogo('#123456', null, 'contain');
      await wait(140);
      var opacity = Number(win.getComputedStyle(win.document.body).opacity);
      expect(opacity).toBeGreaterThan(0);
      expect(opacity).toBeLessThan(1);
      expect(win.Display._logoScreen.classList.contains('show')).toBe(true);
      expect(win.getComputedStyle(win.Display._slidesContainer).opacity).toBe('0');
      await cover;
      expect(win.getComputedStyle(win.document.body).opacity).toBe('1');
      var uncover = win.Display.toTransparent();
      await wait(140);
      opacity = Number(win.getComputedStyle(win.document.body).opacity);
      expect(opacity).toBeGreaterThan(0);
      expect(opacity).toBeLessThan(1);
      expect(win.Display._logoScreen.classList.contains('show')).toBe(true);
      await uncover;
      expect(win.getComputedStyle(win.document.body).opacity).toBe('0');
    });
  });

  it('cancels a desktop completion when another mode takes over', function (done) {
    scenario(done, async function (win) {
      render(win, 'image', 'original');
      await wait(60);
      win.Display.updateItemTransitionSettings(true, 0.2, 'linear');
      var desktopCompleted = false;
      win.Display.toTransparent().then(function () { desktopCompleted = true; });
      await wait(50);
      await win.Display.toLogo('#abc', null, 'contain');
      await wait(150);
      expect(desktopCompleted).toBe(false);
      expect(win.Display._displayMode).toBe('logo');
      expect(win.getComputedStyle(win.document.body).opacity).toBe('1');
    });
  });

  it('keeps per-slide fade timing independent of item timing', function (done) {
    scenario(done, async function (win) {
      render(win, 'horizontal song', 'song');
      win.Display.setTheme(theme(win, {display_slide_transition: true,
        display_slide_transition_speed: win.TransitionSpeed.Slow}));
      win.Display.resetTheme();
      win.Display.updateItemTransitionSettings(true, 0.2, 'linear');
      await wait(60);
      win.Display.goToSlide('v2');
      var slide = win.Reveal.getCurrentSlide();
      expect(win.getComputedStyle(slide).transitionDuration).toBe('1.2s');
      expect(win.getComputedStyle(slide).transitionDelay).toBe('0s');
      await wait(150);
      expect(Number(win.getComputedStyle(slide).opacity)).toBeGreaterThan(0);
      expect(Number(win.getComputedStyle(slide).opacity)).toBeLessThan(1);
    });
  });
  it('keeps outgoing content through the native window handoff and clears it only when invisible', function (done) {
    scenario(done, async function (win) {
      render(win, 'horizontal song', 'outgoing');
      await wait(60);
      win.Display.updateItemTransitionSettings(true, 0.2, 'linear');
      win.Display.finishWithCurrentItem();
      expect(win.Display._slidesContainer.textContent).toContain('outgoing');
      var handoff = win.Display.toTransparent();
      await wait(80);
      expect(win.Display._slidesContainer.textContent).toContain('outgoing');
      expect(Number(win.getComputedStyle(win.document.body).opacity)).toBeGreaterThan(0);
      await handoff;
      expect(win.Display._slidesContainer.textContent).not.toContain('outgoing');
      expect(win.getComputedStyle(win.document.body).opacity).toBe('0');
    });
  });

  it('refreshes all horizontal slides without leaving an item cover behind', function (done) {
    scenario(done, async function (win) {
      render(win, 'horizontal song', 'song');
      await wait(60);
      win.Display.updateItemTransitionSettings(true, 0.2, 'linear');
      win.Display.setTheme(theme(win, {display_slide_transition: true}));
      win.Display.resetTheme();
      expect(win.document.querySelector('.display-item-snapshot')).toBeNull();
      Array.from(win.Display._slidesContainer.children).forEach(function (slide) {
        expect(slide.getAttribute('data-transition')).toBe('fade');
      });
    });
  });

  it('preserves both the outgoing picture and footer during a different item fade', function (done) {
    scenario(done, async function (win) {
      render(win, 'horizontal song', 'outgoing');
      await wait(60);
      win.Display.updateItemTransitionSettings(true, 0.3, 'linear');
      render(win, 'image', 'incoming');
      expect(win.Display._pendingItemSnapshot.textContent).toContain('outgoing footer');
      expect(win.Display._pendingItemSnapshot.querySelector('[id]')).toBeNull();
      await wait(80);
      win.Display.updateItemTransitionSettings(false);
      expect(win.document.querySelector('.display-item-snapshot')).toBeNull();
    });
  });

  it('does not cancel an item fade when auto-unblank sends Show again', function (done) {
    scenario(done, async function (win) {
      render(win, 'horizontal song', 'outgoing');
      await wait(60);
      win.Display.updateItemTransitionSettings(true, 0.3, 'linear');
      render(win, 'image', 'incoming');
      await win.Display.show();
      expect(win.Display._pendingItemSnapshot).not.toBeNull();
      await wait(400);
      expect(win.Display._pendingItemSnapshot).toBeNull();
    });
  });

  ['slide', 'convex', 'concave', 'zoom'].forEach(function (effect) {
    it('uses the PDF duration and directional effect for ' + effect, function (done) {
      scenario(done, async function (win) {
        win.Display.setTheme(theme(win, {display_slide_transition: true,
          display_slide_transition_type: effect}));
        win.Display.setImageSlides([0, 1].map(function (index) {
          return {path: imageUrl + '?' + index, use_background_image: true,
            pdf_transition_enabled: true, pdf_transition_effect: effect,
            pdf_transition_speed_seconds: 1.2};
        }));
        await wait(60);
        win.Display.updateItemTransitionSettings(true, 0.2, 'linear');
        win.Display.goToSlide(1);
        var slide = win.Reveal.getCurrentSlide();
        expect(slide.getAttribute('data-transition')).toBe(effect + '-horizontal');
        expect(win.getComputedStyle(slide).transitionDuration).toBe('1.2s');
        if (effect !== 'zoom') {
          var next = win.Display._slidesContainer.querySelector('section.past');
          await wait(1400);
          var transform = new win.DOMMatrix(win.getComputedStyle(next).transform);
          expect(Math.abs(transform.m41)).toBeGreaterThan(0);
          expect(Math.abs(transform.m42)).toBeLessThan(1);
        }
        win.document.body.classList.add('disable-transitions');
        expect(win.getComputedStyle(slide).transitionDuration).toBe('0s');
      });
    });
  });

  it('ignores an old image load after a newer item has completed its fade', function (done) {
    scenario(done, async function (win) {
      render(win, 'image', 'first');
      await wait(60);
      win.Display.updateItemTransitionSettings(true, 0.15, 'linear');
      var releaseOldLoad;
      var oldLoad = new Promise(function (resolve) { releaseOldLoad = resolve; });
      spyOn(win.Display, '_waitForSlideImages').and.returnValues(oldLoad, Promise.resolve());
      render(win, 'image', 'second');
      await wait(40);
      render(win, 'horizontal song', 'third');
      await wait(250);
      releaseOldLoad();
      await wait(40);
      expect(win.Display._pendingItemSnapshot).toBeNull();
      expect(win.Reveal.getTotalSlides()).toBe(2);
      expect(win.Reveal.getCurrentSlide().textContent).toBe('third');
    });
  });

});
