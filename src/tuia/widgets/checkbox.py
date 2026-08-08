"""
tuia.widgets.checkbox - CheckBox control.
"""
import curses
from tuia.base import Widget

class CheckBox(Widget):
    """Interactive toggle checkbox widget `[X]` vs `[ ]`."""
    def __init__(self, parent=None, text="CheckBox", checked=False, command=None, x=0, y=0, width=15, height=1, z_index=0):
        super().__init__(parent=parent, x=x, y=y, width=width, height=height, z_index=z_index)
        self.text = text
        self.checked = checked
        self.command = command
        self.focused = False

    def focus(self): self.focused = True
    def blur(self): self.focused = False

    def toggle(self):
        self.checked = not self.checked
        if callable(self.command):
            self.command(self.checked)

    def process_event(self, key):
        if self.focused:
            result = super().process_event()
            if key in (curses.KEY_ENTER, 10, 13, ord(' ')):
                self.toggle()
                return True
            return result
        return False

    def draw(self):
        if not self.window:
            return

        mark = "[X]" if self.checked else "[ ]"
        display_str = f"{mark} {self.text}"[:self.width]
        attr = curses.A_REVERSE if self.focused else curses.A_NORMAL

        try:
            self.window.attron(attr)
            self.window.addstr(0, 0, display_str.ljust(self.width))
            self.window.attroff(attr)
        except curses.error:
            pass
