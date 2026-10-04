"""Designer variants of the original text-editing dialogs."""
from openlp.plugins.slide_designer.forms.designer import SlideDesignerDialogMixin, designer_dialog_parent
from openlp.plugins.songs.forms.editverseform import EditVerseForm
from openlp.plugins.custom.forms.editcustomslideform import EditCustomSlideForm


class SongSlideDesigner(SlideDesignerDialogMixin, EditVerseForm):
    uses_slide_designer = True

    def __init__(self, owner):
        super().__init__(designer_dialog_parent(owner))
        self.setup_slide_designer(owner, self.verse_text_edit, 'song')


class CustomSlideDesigner(SlideDesignerDialogMixin, EditCustomSlideForm):
    uses_slide_designer = True

    def __init__(self, owner):
        super().__init__(designer_dialog_parent(owner))
        self.setup_slide_designer(owner, self.slide_text_edit, 'custom')
