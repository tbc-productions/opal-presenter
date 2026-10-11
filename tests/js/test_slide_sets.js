describe('Mixed service slide sets', function () {
  it('keeps image content and custom text themes separate in one deck', function () {
    var previousTheme = Display._theme;
    var previousSlides = Display._slides;
    var previousContainer = Display._slidesContainer;
    var previousFooter = Display._footerContainer;
    var previousTransitions = Display._doTransitions;
    Display._doTransitions = true;
    var host = document.createElement('div');
    document.body.appendChild(host);
    Display._slidesContainer = document.createElement('div');
    Display._footerContainer = document.createElement('div');
    host.appendChild(Display._slidesContainer);
    host.appendChild(Display._footerContainer);
    Display._slides = {};
    var common = {background_type: 'solid', background_color: '#000000', font_main_size: 30,
      font_main_x: 10, font_main_y: 20, font_main_width: 300, font_main_height: 200,
      font_main_line_adjustment: 0, font_main_letter_adjustment: 0,
      display_slide_transition: true, display_slide_transition_type: TransitionType.Slide,
      display_slide_transition_speed: TransitionSpeed.Slow};
    Display._theme = common;
    var image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB';
    var pictureTheme = Object.assign({}, common, {
      background_type: 'image', background_filename: image, background_fit: 'contain'
    });
    var customTheme = Object.assign({}, common, {background_color: '#123456', font_main_size: 60});
    spyOn(Display, 'replaceSlides').and.callFake(function (deck) {
      Display._slidesContainer.appendChild(deck);
      Display.applyTheme(deck);
    });
    try {
      Display.setTextSlides([
        {verse: 0, text: '', footer: '', set_image: image, theme: pictureTheme},
        {verse: 1, text: 'Welcome', footer: 'Credits', theme: customTheme},
        {verse: 2, text: '', footer: '', set_image: image, theme: pictureTheme}
      ]);
      var slides = host.querySelectorAll('.text-slide');
      expect(slides.length).toBe(3);
      expect(slides[0].getAttribute('data-background-image')).toBeNull();
      expect(slides[0].querySelector('img').src).toBe(image);
      expect(slides[1].getAttribute('data-background-image')).toBe(null);
      expect(slides[1].getAttribute('data-background')).toBe('#123456');
      expect(slides[1].querySelector('.slide-text-content').style.fontSize).toBe('60pt');
      expect(slides[2].getAttribute('data-background-image')).toBeNull();
      expect(slides[2].querySelector('img').src).toBe(image);
      expect(host.querySelectorAll('.footer-item').length).toBe(1);
      expect(Display._theme).toBe(common);
      Array.from(slides).forEach(function (section) {
        expect(section.getAttribute('data-transition')).toBe('slide');
        expect(section.getAttribute('data-transition-speed')).toBe('slow');
        section._slideTheme.display_slide_transition = false;
      });
      Display.applyTheme(slides[0].parentElement);
      Array.from(slides).forEach(function (section) {
        expect(section.getAttribute('data-transition')).toBe('none');
      });
    } finally {
      host.remove();
      Display._theme = previousTheme;
      Display._slides = previousSlides;
      Display._slidesContainer = previousContainer;
      Display._footerContainer = previousFooter;
      Display._doTransitions = previousTransitions;
    }
  });
});
