describe("Reveal display startup", function () {
  var frame;

  function loadDisplay(done, check, hidden) {
    frame = document.createElement('iframe');
    frame.style.width = '320px';
    frame.style.height = '180px';
    if (hidden) frame.style.display = 'none';
    frame.onload = function () {
      var win = frame.contentWindow;
      var errors = [];
      win.addEventListener('error', function (event) { errors.push(event.message); });
      spyOn(win.displayWatcher, 'setInitialised');
      var startup = win.requestAction('init', {isDisplay: true});
      expect(win.displayWatcher.setInitialised).not.toHaveBeenCalled();
      expect(win.Display.init({isDisplay: true})).toBe(startup);
      startup.then(function () {
        expect(win.Reveal.isReady()).toBe(true);
        expect(win.displayWatcher.setInitialised).toHaveBeenCalledWith(true);
        expect(win.Display._backgroundsContainer).toBe(win.Reveal.getBackgroundsElement());
        return check(win, errors);
      }).then(done, done.fail);
    };
    frame.srcdoc = '<link rel="stylesheet" href="/base/openlp/core/display/html/reveal.css">' +
      '<link rel="stylesheet" href="/base/openlp/core/display/html/display.css">' +
      '<div class="reveal"><div class="slides"><section>' +
      '<span class="fragment">First</span><span class="fragment">Second</span>' +
      '</section></div><div class="footer"></div></div>' +
      '<script src="/base/tests/js/fake_webchannel.js"></script>' +
      '<script src="/base/openlp/core/display/html/reveal.js"></script>' +
      '<script src="/base/openlp/core/display/html/display-init.js"></script>' +
      '<script src="/base/openlp/core/display/html/display.js"></script>';
    document.body.appendChild(frame);
  }

  afterEach(function () { frame.remove(); });

  it("keeps narrow previews in slide mode and preserves transparent output", function (done) {
    loadDisplay(done, function (win) {
      expect(win.Reveal.VERSION).toBe('6.0.2');
      expect(win.Reveal.isScrollView()).toBe(false);
      expect(win.document.querySelector('.slides > section')).toBe(win.Reveal.getCurrentSlide());
      expect(win.getComputedStyle(win.document.body).backgroundColor).toBe('rgba(0, 0, 0, 0)');
      expect(win.document.querySelector('.resume-button')).toBe(null);
    });
  });

  it("connects fragment navigation after the singleton API becomes available", function (done) {
    loadDisplay(done, function (win) {
      var fragment = win.document.querySelector('.fragment');
      expect(win.Display.next()).toBe(true);
      expect(fragment.classList.contains('visible')).toBe(true);
      expect(win.Display.prev()).toBe(true);
      expect(fragment.classList.contains('visible')).toBe(false);
    });
  });

  it("starts hidden previews without recursive resize errors and lays them out when shown", function (done) {
    loadDisplay(done, function (win, errors) {
      expect(errors).toEqual([]);
      expect(win.Reveal.getScale()).toBe(1);
      frame.style.display = '';
      return new Promise(function (resolve) {
        win.requestAnimationFrame(function () {
          win.Reveal.layout();
          expect(errors).toEqual([]);
          expect(win.Reveal.getScale()).toBe(1);
          var slides = win.Reveal.getSlidesElement();
          expect(slides.clientWidth).toBe(win.document.querySelector('.reveal').offsetWidth);
          expect(slides.clientHeight).toBe(win.document.querySelector('.reveal').offsetHeight);
          expect(win.Display.next()).toBe(true);
          resolve();
        });
      });
    }, true);
  });
});
