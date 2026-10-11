describe('Responsive theme layouts', function () {
  var frame, display, win;
  var theme = {
    display_size_width: 1920, display_size_height: 1080,
    background_type: 'solid', background_color: '#000000',
    font_main_x: 192, font_main_y: 108, font_main_width: 1536, font_main_height: 756,
    font_main_size: 64, font_main_name: 'Arial', font_main_color: '#ffffff',
    font_main_line_adjustment: 0, font_main_letter_adjustment: 0,
    font_footer_x: 960, font_footer_y: 972, font_footer_width: 864, font_footer_height: 108,
    font_footer_size: 24, font_footer_name: 'Arial', font_footer_color: '#ffffff',
    font_footer_line_adjustment: 0, font_footer_letter_adjustment: 0
  };

  beforeEach(async function () {
    frame = document.createElement('iframe');
    frame.style.cssText = 'width:1920px;height:1080px;border:0';
    var loaded = new Promise(resolve => frame.onload = resolve);
    frame.srcdoc = '<link rel="stylesheet" href="/base/opal/core/display/html/reveal.css">' +
      '<link rel="stylesheet" href="/base/opal/core/display/html/display.css">' +
      '<div class="reveal"><div class="slides"></div><div class="footer"></div></div>' +
      '<div id="logo-screen"><img id="logo-screen-image"></div>' +
      '<script src="/base/tests/js/fake_webchannel.js"></script>' +
      '<script src="/base/opal/core/display/html/reveal.js"></script>' +
      '<script src="/base/opal/core/display/html/display-init.js"></script>' +
      '<script src="/base/opal/core/display/html/display.js"></script>';
    document.body.appendChild(frame);
    await loaded;
    win = frame.contentWindow;
    display = win.Display;
    spyOn(win.history, 'replaceState');
    await display.init({isDisplay: true});
    display.setTheme(Object.assign({}, theme));
    display.setTextSlides([{verse: 'v1', text: 'A resolution independent slide', footer: 'Footer credits'}]);
    await settle();
  });

  afterEach(function () { frame.remove(); });

  async function settle() {
    await new Promise(resolve => win.requestAnimationFrame(() => win.requestAnimationFrame(resolve)));
    win.Reveal.layout();
  }

  function expectInside(node) {
    var viewport = win.document.querySelector('.reveal').getBoundingClientRect();
    var bounds = node.getBoundingClientRect();
    expect(bounds.width).toBeGreaterThan(0);
    expect(bounds.height).toBeGreaterThan(0);
    expect(bounds.left).toBeGreaterThanOrEqual(viewport.left - 1);
    expect(bounds.top).toBeGreaterThanOrEqual(viewport.top - 1);
    expect(bounds.right).toBeLessThanOrEqual(viewport.right + 1);
    expect(bounds.bottom).toBeLessThanOrEqual(viewport.bottom + 1);
  }

  [[1280, 720, 1], [1920, 1080, 1], [2560, 1440, 1], [3840, 2160, 1], [1024, 768, 1], [384, 216, .2]].forEach(([width, height, zoom]) => {
    it(`scales fonts and keeps both areas on a ${width} x ${height} display at zoom ${zoom}`, async function () {
      frame.style.width = `${width}px`;
      frame.style.height = `${height}px`;
      display.setScale(zoom * 100);
      await settle();
      var text = win.document.querySelector('.slide-text-content');
      var footer = win.document.querySelector('.footer');
      expectInside(text);
      expectInside(footer);
      expect(parseFloat(win.getComputedStyle(text).fontSize) * zoom / height).toBeCloseTo(64 * 4 / 3 / 1080, 5);
      expect(parseFloat(win.getComputedStyle(footer).fontSize) * zoom / height).toBeCloseTo(24 * 4 / 3 / 1080, 5);
      var bounds = text.getBoundingClientRect();
      expect(bounds.width / width).toBeCloseTo(.8, 3);
      expect(bounds.height / height).toBeCloseTo(.7, 3);
      expect(footer.style.left).toBe('auto');
      expect(footer.style.right).toBe('5%');
      expect(footer.style.top).toBe('auto');
      expect(footer.style.bottom).toBe('0%');
    });
  });

  it('clamps oversized and offscreen theme areas without modifying their saved coordinates', async function () {
    var changed = Object.assign({}, theme, {
      font_main_x: -200, font_main_y: 1200, font_main_width: 2400, font_main_height: 2000,
      font_footer_x: 2400, font_footer_y: -100, font_footer_width: 600, font_footer_height: 100
    });
    display.setTheme(changed);
    display.resetTheme();
    await settle();
    expectInside(win.document.querySelector('.slide-text-content'));
    expectInside(win.document.querySelector('.footer'));
    expect(changed.font_main_x).toBe(-200);
    expect(changed.font_footer_x).toBe(2400);
    display.setThemePreviewAreas({main: {x: 2400, y: -50, width: 500, height: 500},
      footer: {x: -50, y: 1400, width: 2500, height: 100}});
    await settle();
    expectInside(win.document.querySelector('.slide-text-content'));
    expectInside(win.document.querySelector('.footer'));
  });

  it('keeps per-slide footers inside the viewport and detects long text overflow for pagination', async function () {
    display.setTextSlides([{verse: 'v1', text: 'Long line<br>'.repeat(40), footer: 'Credits',
      theme: Object.assign({}, theme, {font_footer_y: 1300})}]);
    await settle();
    expectInside(win.document.querySelector('.slide-text-content'));
    expectInside(win.document.querySelector('.footer-item'));
    expect(display.doesContentFit()).toBe(false);
  });

  it('keeps explicit line-count font sizes relative when the output is resized', async function () {
    var count = display.calculateLineCount(64);
    frame.style.width = '1280px';
    frame.style.height = '720px';
    await settle();
    expect(display.calculateLineCount(64)).toBe(count);
    var paragraph = win.document.querySelector('.slide-text-content p');
    expect(paragraph.style.fontSize).toContain('cqh');
  });
});
