"""
tuia.widgets.button - Interactive button widget.
"""

from tuia.base import Widget
from tuia.constants import Keys, Modifiers


class Button(Widget):
    """An interactive button widget with focus states and click callbacks."""

    def __init__(
        self,
        parent=None,
        text="Button",
        focused_text=None,
        command=None,
        x=0,
        y=0,
        width=None,
        height=3,
        z_index=0,
    ):
        width = width or max(1, len(text))
        super().__init__(
            parent=parent, x=x, y=y, width=width, height=height, z_index=z_index
        )
        self.text = text
        self.focused_text = focused_text or text
        self.command = command
        self.focused = False

    def focus(self):
        self.focused = True

    def blur(self):
        self.focused = False

    def process_event(self, key):
        if self.focused:
            result = super().process_event(key)
            if key in (Keys.ENTER, Keys.SPACE):
                if callable(self.command):
                    self.command()
                return True
            return result
        return False

    def draw(self):
        if not self.window:
            return

        attr = Modifiers.REVERSE if self.focused else Modifiers.NORMAL
        label = self.focused_text if self.focused else self.text
        if len(label) > self.width:
            label = label[: max(1, self.width)]

        start_x = 0  # max(0, (self.width - len(label)) // 2)
        start_y = 0  # max(0, self.height // 2)

        self.window.attron(attr)
        self.window.addstr(start_y, start_x, label)
        self.window.attroff(attr)
