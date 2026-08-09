"""
tuia.widgets.text_input - Single-line text entry field.
"""
import time
import curses
from tuia.base import Widget

class TextInput(Widget):
    """Single-line text input field supporting typing, backspace, cursor navigation, horizontal scrolling, and a blinking software cursor."""
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

    def blur(self):
        self.focused = False

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

        # Ensure terminal's native hardware cursor is hidden
        try:
            curses.curs_set(0)
        except curses.error:
            pass

        if not self.value:
            display_str = self.placeholder
            attr = curses.A_DIM
            self.scroll_offset = 0
            screen_cursor_pos = 0
        else:
            attr = curses.A_NORMAL
            
            # Correct horizontal scroll bounds based on exact widget width
            if self.cursor_pos < self.scroll_offset:
                self.scroll_offset = self.cursor_pos
            elif self.cursor_pos > self.scroll_offset + self.width - 1:
                self.scroll_offset = self.cursor_pos - self.width + 1

            max_offset = max(0, len(self.value) - self.width + 1)
            self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
            screen_cursor_pos = self.cursor_pos - self.scroll_offset

        display_text = self.value if self.value else self.placeholder
        visible_text = display_text[self.scroll_offset:self.scroll_offset + self.width]
        padded_text = visible_text.ljust(self.width)

        try:
            # Draw the base text field content
            self.window.attron(attr)
            self.window.addstr(0, 0, padded_text[:self.width])
            self.window.attroff(attr)

            # Draw the blinking software cursor if focused
            if self.focused:
                # Toggle blink state every ~0.5 seconds (2 Hz blink rate)
                is_blink_on = (int(time.time() * 2) % 2) == 0

                if is_blink_on:
                    if not self.value:
                        cursor_char = self.placeholder[0] if self.placeholder else ' '
                        self.window.addch(0, 0, cursor_char, curses.A_REVERSE)# | curses.A_BOLD | curses.A_DIM)
                    elif 0 <= screen_cursor_pos < self.width:
                        cursor_char = self.value[self.cursor_pos] if self.cursor_pos < len(self.value) else ' '
                        # High-contrast reverse + bold styling to ensure it's clearly visible
                        self.window.addch(0, screen_cursor_pos, cursor_char, curses.A_REVERSE)# | curses.A_BOLD)
        except curses.error:
            print("test")
