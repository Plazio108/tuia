"""
tuia.widgets.label - Label widget for displaying text.
"""
from tuia.base import Widget


class Label(Widget):
    """A simple text display widget supporting alignment and text truncation."""

    def __init__(self, parent=None, text="", align="left", x=0, y=0, width=None, height=1, z_index=0):
        self._text = text
        # If width is not explicitly specified, infer requested width from text length
        calc_width = width if width is not None else max(1, len(text))

        super().__init__(parent=parent, x=x, y=y,
                         width=calc_width, height=height, z_index=z_index)
        self.align = align

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = str(value)
        # Update requested width dynamically when text changes
        self.req_width = max(1, len(self._text))
        if self.parent:
            self.parent.update_layout()

    def draw(self):
        if not self.window:
            return

        display_text = self._text
        if len(display_text) > self.width:
            display_text = display_text[:max(0, self.width - 1)] + "…"

        if self.align == "center":
            start_x = max(0, (self.width - len(display_text)) // 2)
        elif self.align == "right":
            start_x = max(0, self.width - len(display_text))
        else:
            start_x = 0

        self.window.addstr(0, start_x, display_text)
