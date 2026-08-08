"""
tuia.widgets.text_input - Single-line text entry field.
"""
import curses
from tuia.base import Widget

class TextInput(Widget):
    """Single-line text input field supporting typing, backspace, and cursor navigation."""
    def __init__(self, parent=None, value="", placeholder="Type here...", on_submit=None, 
                 x=0, y=0, width=20, height=1, z_index=0):
        super().__init__(parent=parent, x=x, y=y, width=width, height=height, z_index=z_index)
        self.value = value
        self.placeholder = placeholder
        self.on_submit = on_submit
        self.cursor_pos = len(value)
        self.focused = False

    def focus(self): self.focused = True
    def blur(self): self.focused = False

    def process_event(self, key):
        if not self.focused:
            return False

        super().process_event(key)

        if key in (curses.KEY_ENTER, 10, 13):
            if callable(self.on_submit):
                self.on_submit(self.value)
            return True

        elif key == curses.KEY_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
            return True
        elif key == curses.KEY_RIGHT:
            self.cursor_pos = min(len(self.value), self.cursor_pos + 1)
            return True

        elif key in (curses.KEY_BACKSPACE, 8, 127):
            if self.cursor_pos > 0:
                self.value = self.value[:self.cursor_pos - 1] + self.value[self.cursor_pos:]
                self.cursor_pos -= 1
            return True

        elif 32 <= key <= 126:
            char = chr(key)
            self.value = self.value[:self.cursor_pos] + char + self.value[self.cursor_pos:]
            self.cursor_pos += 1
            return True

        return False

    def draw(self):
        if not self.window:
            return

        display_str = self.value
        if not display_str and not self.focused:
            display_str = self.placeholder
            attr = curses.A_DIM
        else:
            attr = curses.A_UNDERLINE if self.focused else curses.A_NORMAL

        visible_text = display_str[:self.width]

        try:
            self.window.attron(attr)
            self.window.addstr(0, 0, visible_text.ljust(self.width))
            self.window.attroff(attr)

            if self.focused and self.cursor_pos < self.width:
                cursor_char = self.value[self.cursor_pos] if self.cursor_pos < len(self.value) else ' '
                self.window.addstr(0, self.cursor_pos, cursor_char, curses.A_REVERSE)
        except curses.error:
            pass
