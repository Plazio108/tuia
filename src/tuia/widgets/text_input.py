"""
tuia.widgets.text_input - Single-line text entry field.
"""
import curses
from tuia.base import Widget

class TextInput(Widget):
    """Single-line text input field supporting typing, backspace, cursor navigation, and horizontal scrolling."""
    def __init__(self, parent=None, value="", placeholder="Type here...", on_submit=None, 
                 x=0, y=0, width=20, height=1, z_index=0):
        super().__init__(parent=parent, x=x, y=y, width=width, height=height, z_index=z_index)
        self.value = value
        self.placeholder = placeholder
        self.on_submit = on_submit
        self.cursor_pos = len(value)
        self.scroll_offset = 0
        self.focused = False

    def focus(self):
        self.focused = True
        try:
            curses.curs_set(1)  # Show hardware cursor
        except curses.error:
            pass

    def blur(self):
        self.focused = False
        try:
            curses.curs_set(0)  # Hide hardware cursor
        except curses.error:
            pass

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

        if not self.value:
            display_str = self.placeholder
            attr = curses.A_DIM
            self.scroll_offset = 0
            screen_cursor_pos = 0
        else:
            attr = curses.A_UNDERLINE if self.focused else curses.A_NORMAL
            
            # Adjust horizontal scroll window based on cursor position
            if self.cursor_pos < self.scroll_offset:
                self.scroll_offset = self.cursor_pos
            elif self.cursor_pos >= self.scroll_offset + self.width:
                self.scroll_offset = self.cursor_pos - self.width + 1

            max_offset = max(0, len(self.value) - self.width + 1)
            self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
            screen_cursor_pos = self.cursor_pos - self.scroll_offset

        display_text = self.value if self.value else self.placeholder
        visible_text = display_text[self.scroll_offset:self.scroll_offset + self.width]
        padded_text = visible_text.ljust(self.width)

        try:
            # Draw the input field text content safely
            self.window.attron(attr)
            self.window.addstr(0, 0, padded_text[:self.width])
            self.window.attroff(attr)

            # Position the blinking hardware cursor correctly when focused
            if self.focused:
                cursor_x = min(max(0, screen_cursor_pos), self.width - 1)
                self.window.move(0, cursor_x)
        except curses.error:
            pass
