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

        # ----------------------------------------------------------
        # Text and scrolling
        # ----------------------------------------------------------

        if self.value:
            display_text = self.value
            attr = curses.A_NORMAL

            # cursor_pos is an insertion position:
            #
            #   0 <= cursor_pos <= len(value)
            #
            # The character being modified is:
            #
            #   value[cursor_pos]
            #
            # so there is no character to modify when cursor_pos
            # equals len(value).

            if self.cursor_pos < self.scroll_offset:
                self.scroll_offset = self.cursor_pos

            elif self.cursor_pos >= self.scroll_offset + self.width:
                self.scroll_offset = (
                    self.cursor_pos - self.width + 1
                )

            # We need to be able to display the insertion position
            # immediately after the final character.
            max_offset = max(
                0,
                len(self.value) - self.width + 1
            )

            self.scroll_offset = max(
                0,
                min(self.scroll_offset, max_offset)
            )

        else:
            display_text = self.placeholder
            attr = curses.A_DIM
            self.scroll_offset = 0

        # ----------------------------------------------------------
        # Draw normal text
        # ----------------------------------------------------------

        visible_text = display_text[
            self.scroll_offset:
            self.scroll_offset + self.width
        ]

        padded_text = visible_text.ljust(self.width)

        self.window.attron(attr)

        try:
            self.window.addnstr(
                0,
                0,
                padded_text,
                self.width,
            )
        except curses.error:
            pass
        finally:
            self.window.attroff(attr)

        # ----------------------------------------------------------
        # Software cursor
        # ----------------------------------------------------------

        if not self.focused:
            print('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
            return

        if (int(time.monotonic() * 2) % 2) != 0:
            return

        # At the end of the text there is no character to modify.
        if self.cursor_pos > len(self.value):
            return

        screen_cursor_pos = (
            self.cursor_pos - self.scroll_offset
        )

        if not 0 <= screen_cursor_pos < self.width:
            raise RuntimeError(
                "TextInput cursor outside visible area: "
                f"cursor_pos={self.cursor_pos}, "
                f"scroll_offset={self.scroll_offset}, "
                f"screen_cursor_pos={screen_cursor_pos}, "
                f"width={self.width}"
            )

        # Modify the character already rendered at the cursor.
        self.window.addch(
            0,
            screen_cursor_pos,
            self.window.getch(0, screen_cursor_pos),
            curses.A_REVERSE,
        )
