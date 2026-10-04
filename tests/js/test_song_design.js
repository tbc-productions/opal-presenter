describe('Portable slide designs', function () {
  var host, slide, text;
  beforeEach(function () {
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
    Display._designEditor = false;
    Display._designSelected = null;
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
    expect(text.style.zIndex).toBe('101');
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
  it('only shows handles inside an enabled editor, and can turn editing off', function () {
    Display._applySongDesign(slide);
    Display.setDesignEditor('lyrics');
    expect(slide.querySelectorAll('.design-resize-handle').length).toBe(1);
    expect(text.onpointerdown).not.toBe(null);
    Display.setDesignEditor(null);
    expect(slide.querySelectorAll('.design-resize-handle').length).toBe(0);
    expect(text.onpointerdown).toBe(null);
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
});
