/* Real Reveal/Display rendering; only the Python web-channel callbacks are substituted. */
describe('Production display stress', function () {
  let frame;
  let settings;
  const originalTimeout = jasmine.DEFAULT_TIMEOUT_INTERVAL;
  beforeAll(async function () {
    settings = await (await fetch('/stress-settings')).json();
    jasmine.DEFAULT_TIMEOUT_INTERVAL = settings.cycles * 3000 + 30000;
  });
  afterAll(function () { jasmine.DEFAULT_TIMEOUT_INTERVAL = originalTimeout; });
  afterEach(function () { if (frame) frame.remove(); });

  it('repeatedly switches songs, image/PDF slides, video and output modes', async function () {
    const errors = [];
    const timings = [];
    let maxNodes = 0;
    frame = document.createElement('iframe');
    frame.style.cssText = 'width:1280px;height:720px;border:0';
    const loaded = new Promise(resolve => frame.onload = resolve);
    frame.srcdoc = '<link rel="stylesheet" href="/base/openlp/core/display/html/reveal.css">' +
      '<link rel="stylesheet" href="/base/openlp/core/display/html/display.css">' +
      '<div class="reveal"><div class="slides"></div><div class="footer"></div></div>' +
      '<div id="logo-screen"><img id="logo-screen-image"></div>' +
      '<script src="/base/tests/js/fake_webchannel.js"></script>' +
      '<script src="/base/openlp/core/display/html/reveal.js"></script>' +
      '<script src="/base/openlp/core/display/html/display-init.js"></script>' +
      '<script src="/base/openlp/core/display/html/display.js"></script>';
    document.body.appendChild(frame);
    await loaded;
    const win = frame.contentWindow;
    win.addEventListener('error', event => errors.push(event.message));
    win.addEventListener('unhandledrejection', event => errors.push(String(event.reason)));
    win.displayWatcher.pleaseRepaint = function () {};
    win.mediaWatcher = Object.fromEntries(['update_duration', 'update_progress', 'update_volume',
      'update_playback_rate', 'has_ended', 'has_muted'].map(name => [name, function () {}]));
    spyOn(win.history, 'replaceState');
    await win.Display.init({isDisplay: true, doItemTransitions: true, itemTransitionSpeed: .05});
    const theme = {
      display_size_width: 1920, display_size_height: 1080,
      background_type: 'solid', background_color: '#123456',
      font_main_x: 100, font_main_y: 100, font_main_width: 1700, font_main_height: 800,
      font_main_size: 48, font_main_name: 'Arial', font_main_color: '#ffffff',
      font_main_line_adjustment: 0, font_main_letter_adjustment: 0,
      font_footer_x: 100, font_footer_y: 950, font_footer_width: 1700, font_footer_height: 100,
      font_footer_size: 20, font_footer_name: 'Arial', font_footer_color: '#ffffff',
      display_slide_transition: true, display_slide_transition_type: win.TransitionType.Fade,
      display_slide_transition_speed: win.TransitionSpeed.Fast
    };
    const imageUrl = '/base/tests/js/fixtures/Preview%20images/Slide%20%231%20(100%25)%20%E2%80%94%20caf%C3%A9.svg';
    const wait = ms => new Promise(resolve => win.setTimeout(resolve, ms));
    async function paint() {
      await new Promise(resolve => win.requestAnimationFrame(() => win.requestAnimationFrame(resolve)));
    }
    const started = performance.now();
    try {
      for (let cycle = 0; cycle < settings.cycles; cycle++) {
        const tick = performance.now();
        const kind = cycle % 4;
        win.Display.setTheme({...theme, display_slide_transition_direction: Math.floor(cycle / 4) % 2 ?
          win.TransitionDirection.Vertical : win.TransitionDirection.Horizontal});
        if (kind === 0) {
          if (cycle % 8 === 0) {
            win.Display.setTextSlides([{verse: 'old', text: 'Superseded item', footer: 'Old credits'}]);
          }
          win.Display.setTextSlides(Array.from({length: settings.slides}, (_, index) => ({
            verse: 'v' + index, text: `Song ${cycle} verse ${index}<br>Hallelujah — café 世界`,
            footer: `Credits ${cycle} / ${index}`
          })));
        } else if (kind === 3) {
          win.Display.setVideo({path: '/base/tests/resources/media/mp4_file.mp4'});
        } else {
          win.Display.setImageSlides(Array.from({length: settings.slides}, () => ({
            path: imageUrl, use_background_image: kind === 2,
            pdf_transition_enabled: true, pdf_transition_effect: 'fade', pdf_transition_speed_seconds: .05
          })), 'contain', '#000000');
        }
        await win.Display._waitForSlideImages();
        await paint();
        timings.push(performance.now() - tick);
        expect(win.Reveal.getTotalSlides()).withContext(`cycle ${cycle}`).toBe(kind === 3 ? 1 : settings.slides);
        if (kind === 3) {
          const video = win.document.querySelector('#video');
          video.muted = true;
          await video.play();
          await wait(150);
          expect(video.currentTime).withContext(`video cycle ${cycle}`).toBeGreaterThan(0);
          expect(video.videoWidth).toBeGreaterThan(0);
          win.Display.pauseVideo();
          expect(video.paused).toBe(true);
          win.Display.stopVideo();
          expect(video.currentTime).toBe(0);
        } else {
          for (const index of [0, settings.slides - 1, Math.floor(settings.slides / 2)]) {
            win.Display.goToSlide(kind === 0 ? 'v' + index : index);
            await paint();
            const slide = win.Reveal.getCurrentSlide();
            if (kind === 0) {
              expect(slide.textContent).toContain(`Song ${cycle} verse ${index}`);
              expect(win.document.querySelector('.footer-item.active').textContent).toBe(`Credits ${cycle} / ${index}`);
            } else {
              expect(win.Reveal.getIndices().v).toBe(index);
              const image = slide.querySelector('img') || slide.slideBackgroundElement.querySelector('img');
              if (image) {
                expect(image.naturalWidth).toBeGreaterThan(0);
              } else {
                expect(slide.slideBackgroundElement.querySelector('.slide-background-content').style.backgroundImage)
                  .toContain('caf%C3%A9.svg');
              }
            }
          }
        }
        await win.Display.toBlack();
        expect(win.Reveal.isPaused()).toBe(true);
        await win.Display.show();
        expect(win.Reveal.isPaused()).toBe(false);
        if (cycle % 10 === 0) {
          frame.style.width = cycle % 20 === 0 ? '384px' : '1280px';
          await paint();
        }
        await wait(100);
        expect(win.document.querySelector('.display-item-snapshot')).toBeNull();
        expect(win.document.querySelectorAll('video').length).toBe(kind === 3 ? 1 : 0);
        maxNodes = Math.max(maxNodes, win.document.querySelectorAll('*').length);
        expect(maxNodes).withContext('DOM growth').toBeLessThan(settings.slides * 30 + 200);
        expect(errors).withContext(`browser errors at cycle ${cycle}`).toEqual([]);
      }
    } finally {
      const sorted = timings.slice().sort((a, b) => a - b);
      const p95 = sorted[Math.ceil(sorted.length * .95) - 1];
      jasmine.getEnv().setSpecProperty('stress', {settings, completedCycles: timings.length,
        elapsedSeconds: (performance.now() - started) / 1000, renderP95Ms: p95,
        renderMaxMs: Math.max(...timings), maxDomNodes: maxNodes, browserErrors: errors});
      expect(p95).withContext('deck replacement to two animation frames, p95 ms').toBeLessThanOrEqual(settings.p95BudgetMs);
    }
  });
});
