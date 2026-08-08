"""
tuia.widgets.button - Interactive button widget.
"""
import curses
from tuia.base import Widget


class Button(Widget):
    """An interactive button widget with focus states and click callbacks."""

    def __init__(self, parent=None, text="Button", focused_text=None, command=None, x=0, y=0, width=None, height=3, z_index=0):
        width = width or max(1, len(text))
        super().__init__(parent=parent, x=x, y=y, width=width, height=height, z_index=z_index)
        self.text = text
        self.focused_text = focused_text or text
        self.command = command
        self.focused = False

    def focus(self): self.focused = True
    def blur(self): self.focused = False

    def process_event(self, key):
        if self.focused:
            result = super().process_event(key)
            if key in (curses.KEY_ENTER, 10, 13, ord(' ')):
                if callable(self.command):
                    self.command()
                return True
            return result
        return False

    def draw(self):
        if not self.window:
            return

        attr = curses.A_REVERSE if self.focused else curses.A_NORMAL
        label = self.focused_text if self.focused else self.text
        if len(label) > self.width:
            label = label[:max(1, self.width)]

        start_x = max(0, (self.width - len(label)) // 2)
        start_y = max(0, self.height // 2)

        try:
            self.window.attron(attr)
            self.window.addstr(start_y, start_x, label)
            self.window.attroff(attr)
        except curses.error:
            pass
