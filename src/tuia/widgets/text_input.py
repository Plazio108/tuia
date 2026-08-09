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

        # Hide the real terminal cursor.
        try:
            curses.curs_set(0)
        except curses.error:
            pass

        # ----------------------------------------------------------
        # Determine what is displayed
        # ----------------------------------------------------------

        if not self.value:
            display_text = self.placeholder
            attr = curses.A_DIM

            self.scroll_offset = 0
            screen_cursor_pos = 0

        else:
            display_text = self.value
            attr = curses.A_NORMAL

            # Keep the cursor visible horizontally.
            if self.cursor_pos < self.scroll_offset:
                self.scroll_offset = self.cursor_pos

            elif self.cursor_pos >= self.scroll_offset + self.width:
                self.scroll_offset = (
                    self.cursor_pos - self.width + 1
                )

            max_offset = max(
                0,
                len(self.value) - self.width
            )

            self.scroll_offset = max(
                0,
                min(self.scroll_offset, max_offset)
            )

            screen_cursor_pos = (
                self.cursor_pos - self.scroll_offset
            )

        # ----------------------------------------------------------
        # Draw text
        # ----------------------------------------------------------

        visible_text = display_text[
            self.scroll_offset:
            self.scroll_offset + self.width
        ]

        padded_text = visible_text.ljust(self.width)

        try:
            self.window.attron(attr)

            self.window.addnstr(
                0,
                0,
                padded_text,
                self.width,
            )

            self.window.attroff(attr)

        except curses.error:
            return

        # ----------------------------------------------------------
        # Software cursor
        # ----------------------------------------------------------

        if not self.focused:
            return

        # Blink at approximately 2 Hz.
        blink_on = (int(time.monotonic() * 2) % 2) == 0

        if not blink_on:
            return

        # The cursor can be at:
        #
        #     0 <= screen_cursor_pos <= width
        #
        # But if it is exactly width, it is outside the drawable
        # columns of the curses window.
        #
        # Scrolling above should normally prevent this, but clamp
        # defensively.
        if screen_cursor_pos >= self.width:
            screen_cursor_pos = self.width - 1

        if screen_cursor_pos < 0:
            return

        # Character under the cursor.
        if (
            self.value
            and self.cursor_pos < len(self.value)
        ):
            cursor_char = self.value[self.cursor_pos]

        elif not self.value and self.placeholder:
            cursor_char = self.placeholder[0]

        else:
            cursor_char = " "

        # ----------------------------------------------------------
        # Draw the software cursor.
        #
        # Use a space when the cursor is at the end of the value.
        # Use reverse video to make the cursor visible.
        # ----------------------------------------------------------

        try:
            self.window.addch(
                0,
                screen_cursor_pos,
                cursor_char,
                curses.A_REVERSE,
            )

        except curses.error:
            # The cursor is purely visual, so don't let a terminal
            # boundary condition break the entire TUI.
            pass
