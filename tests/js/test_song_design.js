describe('Portable slide designs', function () {
  it('waits for images and deferred layout frames before releasing a frozen preview', async function () {
    var resolveImages;
    spyOn(Display, '_waitForSlideImages').and.returnValue(new Promise(function (resolve) {
      resolveImages = resolve;
    }));
    var frames = spyOn(window, 'requestAnimationFrame').and.callThrough();
    var ready = false;
    var pending = Display.waitForDesignPreview(42).then(function (revision) {
      ready = true;
      return revision;
    });
    await Promise.resolve();
    expect(ready).toBe(false);
    resolveImages();
    expect(await pending).toBe(42);
    expect(frames.calls.count()).toBeGreaterThanOrEqual(3);
  });

  var host, slide, text, originalDispatch;
  beforeEach(function () {
    originalDispatch = displayWatcher.dispatchEvent;
    Display._designSelection = [];
    host = document.createElement('div');
    host.style.cssText = 'position:fixed;left:0;top:0;width:1000px;height:600px';
    document.body.appendChild(host);
    slide = document.createElement('section');
    slide.className = 'text-slide';
    slide.style.position = 'relative';
    host.appendChild(slide);
    text = document.createElement('div');
    text.className = 'slide-text-content';
    text.style.cssText = 'position:absolute;left:10%;top:10%;width:40%;height:30%';
    text.textContent = 'Lyrics';
    slide.appendChild(text);
    Display._designEditor = false;
    Display._theme = {song_design_output_height: 600, song_design: {
      version: 1, canvas_height: 600, lyrics: {}, elements: [
        {id: 'shape', kind: 'ellipse', x: 5, y: 10, width: 80, height: 70, fill: '#123456'},
        {id: 'caption', kind: 'text', x: 10, y: 80, width: 80, height: 10, text: '<script>unsafe</script>'}
      ]
    }};
  });
  afterEach(function () {
    host.remove();
    displayWatcher.dispatchEvent = originalDispatch;
    Display._designEditor = false;
    Display._designSelected = null;
    Display._designSelection = [];
    Display._theme = null;
  });
  it('renders shapes and plain text as children of the slide for normal blanking and transitions', function () {
    Display._applySongDesign(slide);
    var elements = slide.querySelectorAll('.song-design-element');
    expect(elements.length).toBe(2);
    expect(elements[0].style.borderRadius).toBe('50%');
    expect(elements[0].style.width).toBe('80%');
    expect(elements[1].textContent).toBe('<script>unsafe</script>');
    expect(elements[1].querySelector('script')).toBe(null);
    expect(text.style.zIndex).toBe('3');
    expect(slide.querySelector('.design-resize-handle')).toBe(null);
  });
  it('does not duplicate layers on repeated layout passes and clears them for an inherited theme', function () {
    Display._applySongDesign(slide);
    Display._applySongDesign(slide);
    expect(slide.querySelectorAll('.song-design-element').length).toBe(2);
    Display._theme = {};
    Display._applySongDesign(slide);
    expect(slide.querySelectorAll('.song-design-element').length).toBe(0);
    expect(text.textContent).toBe('Lyrics');
  });
  it('never assigns an external or active image source from an imported design', function () {
    Display._theme.song_design.elements = [{id: 'image', kind: 'image', src: 'javascript:alert(1)'}];
    Display._applySongDesign(slide);
    expect(slide.querySelector('img').getAttribute('src')).toBe(null);
  });
  it('renders an assigned slide theme without leaking its geometry into the next slide', function () {
    var originalFooter = Display._footerContainer;
    Display._footerContainer = document.createElement('div');
    host.appendChild(Display._footerContainer);
    var common = {background_type: 'solid', background_color: '#000000', font_main_size: 30,
      font_main_x: 10, font_main_y: 20, font_main_width: 300, font_main_height: 200,
      font_main_line_adjustment: 0, font_main_letter_adjustment: 0};
    Display._theme = common;
    slide._slideTheme = Object.assign({}, common, {font_main_x: 150, font_main_size: 60});
    var other = Display._createTextSlide('other', 'Other');
    host.appendChild(other);
    Display.applyTheme(slide);
    Display.applyTheme(other);
    expect(text.style.left).toBe('150px');
    expect(text.style.fontSize).toBe('60pt');
    expect(other.querySelector('.slide-text-content').style.left).toBe('10px');
    expect(Display._theme).toBe(common);
    Display._footerContainer = originalFooter;
  });
  it('only shows handles inside an enabled editor, and can turn editing off', function () {
    Display._applySongDesign(slide);
    Display.setDesignEditor('lyrics');
    expect(slide.querySelectorAll('.design-resize-handle').length).toBe(8);
    expect(text.onpointerdown).not.toBe(null);
    Display.setDesignEditor(null);
    expect(slide.querySelectorAll('.design-resize-handle').length).toBe(0);
    expect(text.onpointerdown).toBe(null);
    expect(slide.querySelector('.design-selection-outline')).toBe(null);
  });
  it('uses the same saved layer order for output and editing, including slide text', function () {
    Display._theme.song_design.order = ['caption', 'lyrics', 'shape'];
    Display._applySongDesign(slide);
    expect(text.style.zIndex).toBe('2');
    expect(slide.querySelector('[data-design-id="shape"]').style.zIndex).toBe('3');
    expect(slide.querySelector('[data-design-id="caption"]').style.zIndex).toBe('1');
    Display.setDesignEditor('caption');
    expect(slide.querySelector('[data-design-id="caption"]').style.zIndex).toBe('1');
    expect(slide.querySelector('.design-selection-outline').style.zIndex).toBe('201');
    Display.setDesignEditor(null);
    expect(slide.querySelector('[data-design-id="caption"]').style.zIndex).toBe('1');
  });
  it('can drag an obscured shape selected from the layer list without raising it', function () {
    Display._applySongDesign(slide);
    Display.setDesignEditor('shape');
    var outline = slide.querySelector('.design-selection-outline');
    var shape = slide.querySelector('[data-design-id="shape"]');
    outline.setPointerCapture = function () {};
    var received;
    displayWatcher.dispatchEvent = function (name, data) { received = data; };
    outline.dispatchEvent(new PointerEvent('pointerdown', {button: 0, clientX: 0, clientY: 0, pointerId: 1}));
    outline.onpointermove({clientX: slide.getBoundingClientRect().width * 0.05, clientY: 0});
    outline.onpointerup();
    expect(received.id).toBe('shape');
    expect(received.geometry.x).toBeCloseTo(10, 1);
    expect(shape.style.zIndex).toBe('1');
  });
  it('does not let the selected text outline block a shape in front of it', function () {
    Display._theme.song_design.order = ['lyrics', 'shape', 'caption'];
    Display._applySongDesign(slide);
    Display.setDesignEditor('lyrics');
    var bounds = slide.getBoundingClientRect();
    var hit = document.elementFromPoint(bounds.left + bounds.width * 0.3, bounds.top + bounds.height * 0.25);
    expect(hit.dataset.designId).toBe('shape');
  });
  it('keeps editing enabled when nothing is selected and clears selection on the slide', function () {
    Display._applySongDesign(slide);
    Display.setDesignEditor('');
    expect(Display._designEditor).toBe(true);
    expect(slide.querySelector('.design-selection-outline')).toBe(null);
    expect(text.onpointerdown).not.toBe(null);
    var received;
    displayWatcher.dispatchEvent = function (name, data) { received = data; };
    slide.dispatchEvent(new PointerEvent('pointerdown', {button: 0}));
    expect(received.id).toBe(null);
    expect(received.changed).toBe(false);
  });
  it('applies independent object opacity to images, shapes and text, including zero', function () {
    Display._theme.song_design.elements[0].opacity = 25;
    Display._theme.song_design.elements[1].opacity = 0;
    Display._theme.song_design.elements.push({id: 'image', kind: 'image', opacity: 70});
    Display._applySongDesign(slide);
    expect(slide.querySelector('[data-design-id="shape"]').style.opacity).toBe('0.25');
    expect(slide.querySelector('[data-design-id="caption"]').style.opacity).toBe('0');
    expect(slide.querySelector('[data-design-id="image"]').style.opacity).toBe('0.7');
    expect(text.style.opacity).toBe('1');
  });
  it('composites an image over the fill in the background plane, without fading the fill or text', function () {
    host.className = 'reveal';
    var slides = document.createElement('div');
    slides.className = 'slides';
    host.appendChild(slides);
    slides.appendChild(slide);
    var background = document.createElement('div');
    background.innerHTML = '<div class="slide-background-content" style="background:linear-gradient(red,blue)"></div>';
    host.appendChild(background);
    slide.slideBackgroundElement = background;
    slide.dataset.designBackgroundImage = 'data:image/png;base64,AAAA';
    slide.dataset.designBackgroundOpacity = '35';
    slide.dataset.designBackgroundFit = 'contain';
    slide.dataset.designBackgroundFilters = 'sepia(50%) contrast(120%)';
    Display._applyDesignBackgroundImages();
    expect(background.style.filter).toBe('sepia(50%) contrast(120%)');
    expect(text.style.filter).toBe('');
    var content = background.firstElementChild;
    expect(content.firstElementChild.style.opacity).toBe('0.35');
    expect(content.firstElementChild.style.backgroundSize).toBe('contain');
    expect(content.style.opacity).toBe('');
    expect(content.style.backgroundImage).toContain('linear-gradient');
    expect(slide.querySelector('.song-design-background-image')).toBe(null);
    slide.dataset.designBackgroundOpacity = '0';
    Display._applyDesignBackgroundImages();
    expect(content.children.length).toBe(1);
    expect(content.firstElementChild.style.opacity).toBe('0');
    delete slide.dataset.designBackgroundFilters;
    slide.removeAttribute('data-design-background-image');
    Display._applyDesignBackgroundImages();
    expect(background.style.filter).toBe('none');
    expect(content.children.length).toBe(0);
  });
  it('reports a complete drag as one geometry change in output percentages', function () {
    Display._applySongDesign(slide);
    text.setPointerCapture = function () {};
    var received;
    displayWatcher.dispatchEvent = function (name, data) { received = data; };
    var bounds = slide.getBoundingClientRect();
    Display._startDesignDrag({button: 0, clientX: 0, clientY: 0, pointerId: 1,
      preventDefault: function () {}, stopPropagation: function () {}, currentTarget: text}, text, false);
    text.onpointermove({clientX: bounds.width * 0.1, clientY: bounds.height * 0.1});
    text.onpointerup();
    expect(received.id).toBe('lyrics');
    expect(received.changed).toBe(true);
    expect(received.geometry.x).toBeCloseTo(20, 1);
    expect(received.geometry.y).toBeCloseTo(20, 1);
    expect(received.geometry.width).toBeCloseTo(40, 1);
    expect(text.onpointermove).toBe(null);
  });

  it('resizes the slide text box from a side handle and preserves the opposite edge', function () {
    Display._applySongDesign(slide);
    Display.setDesignEditor('lyrics');
    var handle = slide.querySelector('[data-edge="w"]');
    handle.setPointerCapture = function () {};
    var received;
    displayWatcher.dispatchEvent = function (name, data) { received = data; };
    handle.dispatchEvent(new PointerEvent('pointerdown', {button: 0, clientX: 0, clientY: 0, pointerId: 1}));
    handle.onpointermove({clientX: slide.getBoundingClientRect().width * 0.05, clientY: 0});
    handle.onpointerup();
    expect(received.id).toBe('lyrics');
    expect(received.geometry.x).toBeCloseTo(15, 1);
    expect(received.geometry.width).toBeCloseTo(35, 1);
    expect(received.geometry.height).toBeCloseTo(30, 1);
  });
  it('toggles canvas selection with Shift, Control or Command without moving anything', function () {
    Display._applySongDesign(slide);
    Display.setDesignEditor('lyrics');
    var shape = slide.querySelector('[data-design-id="shape"]');
    var received;
    displayWatcher.dispatchEvent = function (name, data) { received = data; };
    shape.dispatchEvent(new PointerEvent('pointerdown', {button: 0, shiftKey: true}));
    expect(received.ids).toEqual(['lyrics', 'shape']);
    expect(received.changed).toBe(false);
    expect(slide.querySelectorAll('.design-selection-outline').length).toBe(2);
    expect(slide.querySelectorAll('.design-resize-handle').length).toBe(0);
    text.dispatchEvent(new PointerEvent('pointerdown', {button: 0, metaKey: true}));
    expect(received.ids).toEqual(['shape']);
    shape.dispatchEvent(new PointerEvent('pointerdown', {button: 0, ctrlKey: true}));
    expect(received.ids).toEqual([]);
    expect(received.id).toBe(null);
  });
  it('moves selected objects together and cancels a gesture without changing saved geometry', function () {
    Display._applySongDesign(slide);
    Display.setDesignEditor(['lyrics', 'shape']);
    text.setPointerCapture = function () {};
    var received;
    displayWatcher.dispatchEvent = function (name, data) { received = data; };
    var startEvent = {button: 0, clientX: 0, clientY: 0, pointerId: 1,
      preventDefault: function () {}, stopPropagation: function () {}, currentTarget: text};
    Display._startDesignDrag(startEvent, text, false);
    text.onpointermove({clientX: slide.getBoundingClientRect().width * 0.1, clientY: 0});
    text.onpointerup();
    expect(received.geometries.lyrics.x).toBeCloseTo(20, 1);
    expect(received.geometries.shape.x).toBeCloseTo(15, 1);
    expect(received.ids).toEqual(['lyrics', 'shape']);
    expect(slide.querySelectorAll('.design-selection-outline').length).toBe(2);
    Display._startDesignDrag(startEvent, text, false);
    text.onpointermove({clientX: 20, clientY: 20});
    text.onpointercancel();
    expect(received.changed).toBe(false);
    expect(parseFloat(text.style.left)).toBeCloseTo(20, 1);
  });
  it('renders glyph outlines and shadows for text and contour effects for shapes and images', function () {
    var design = Display._theme.song_design;
    design.lyrics = {outline: true, outline_width: 2, outline_colour: '#ff0000', shadow: true,
      shadow_x: -8, shadow_y: 4, shadow_blur: 6, shadow_colour: '#000000', flip_horizontal: true};
    Object.assign(design.elements[0], {outline: true, outline_width: 3, outline_colour: '#00ff00',
      shadow: true, shadow_x: -4, shadow_y: 5, shadow_blur: 8, flip_vertical: true});
    Object.assign(design.elements[1], {outline: true, outline_width: 1, shadow: true});
    design.elements.push({id: 'image', kind: 'image', outline: true, outline_width: 2,
      shadow: true, flip_horizontal: true, rotation: 30});
    Display._applySongDesign(slide);
    var shape = slide.querySelector('[data-design-id="shape"]');
    var image = slide.querySelector('[data-design-id="image"]');
    var caption = slide.querySelector('[data-design-id="caption"]');
    expect(text.style.textShadow).toContain('rgb(255, 0, 0)');
    expect(text.style.textShadow).toContain('-8px 4px 6px');
    expect(text.style.transform).toContain('scale(-1, 1)');
    expect(shape.style.borderWidth).toBe('3px');
    expect(shape.style.filter).toContain('drop-shadow');
    expect(shape.style.transform).toContain('scale(1, -1)');
    expect(image.style.borderWidth).toBe('2px');
    expect(image.style.transform).toContain('rotate(30deg) scale(-1, 1)');
    expect(caption.style.textShadow).not.toBe('none');
    design.lyrics = {outline: false, shadow: false};
    Display._applySongDesign(slide);
    expect(text.style.textShadow).toBe('none');
  });
  it('scales effect sizes and preserves inherited text effects when only geometry changes', function () {
    Display._theme.song_design.canvas_height = 1200;
    Display._theme.song_design.elements[0].outline = true;
    Display._theme.song_design.elements[0].outline_width = 6;
    text.style.textShadow = 'black 2px 2px 2px';
    var inherited = text.style.textShadow;
    Display._theme.song_design.lyrics = {x: 10};
    Display._applySongDesign(slide);
    expect(text.style.textShadow).toBe(inherited);
    expect(slide.querySelector('[data-design-id="shape"]').style.borderWidth).toBe('3px');
  });
  it('combines image filters with shadows and scales blur to the output', function () {
    Display._theme.song_design.canvas_height = 1200;
    Display._theme.song_design.elements.push({id: 'photo', kind: 'image', shadow: true,
      filters: {blur: 8, grayscale: 100, brightness: 80, url: 'https://invalid', contrast: Infinity}});
    Display._applySongDesign(slide);
    var image = slide.querySelector('[data-design-id="photo"]');
    expect(image.style.filter).toContain('blur(4px)');
    expect(image.style.filter).toContain('grayscale(100%)');
    expect(image.style.filter).toContain('brightness(80%)');
    expect(image.style.filter).toContain('drop-shadow');
    expect(image.style.filter).not.toContain('url');
    expect(image.style.filter).not.toContain('contrast');
  });
});
