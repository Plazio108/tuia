"""
tuia.widgets.text_input - Single-line text entry field.
"""

import time
import curses

from tuia.base import Widget


class TextInput(Widget):
    """
    Single-line text input field supporting typing, backspace,
    cursor navigation, horizontal scrolling, and a blinking
    software cursor.
    """

    def __init__(
        self,
        parent=None,
        value="",
        placeholder="Type here...",
        on_submit=None,
        x=0,
        y=0,
        width=20,
        height=1,
        z_index=0,
    ):
        super().__init__(
            parent=parent,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
        )

        self.value = value
        self.placeholder = placeholder
        self.on_submit = on_submit

        self.cursor_pos = len(value)
        self.scroll_offset = 0
        self.focused = False

        # ======================================================
        # SOFTWARE CURSOR BLINK
        # ======================================================

        # Cursor is initially visible.
        self._cursor_visible = True

        # Duration of each visible/hidden phase.
        self._cursor_blink_period = 0.5

        # Absolute monotonic deadline at which the cursor
        # should change state.
        self._cursor_blink_deadline = (
            time.monotonic() + self._cursor_blink_period
        )

    # ==========================================================
    # CURSOR BLINK
    # ==========================================================

    def _reset_cursor_blink(self):
        """
        Reset the cursor blink cycle.

        Any user interaction that changes the cursor position
        or text makes the cursor immediately visible and starts
        a fresh blink period.
        """
        self._cursor_visible = True

        self._cursor_blink_deadline = (
            time.monotonic()
            + self._cursor_blink_period
        )

    def _update_cursor_blink(self):
        """
        Update the cursor blink state according to the absolute
        monotonic clock.

        This is intentionally independent of frame rate.
        """
        now = time.monotonic()

        if now >= self._cursor_blink_deadline:
            self._cursor_visible = not self._cursor_visible

            # Start the next phase from the current time.
            self._cursor_blink_deadline = (
                now + self._cursor_blink_period
            )

    # ==========================================================
    # FOCUS
    # ==========================================================

    def focus(self):
        self.focused = True
        self._reset_cursor_blink()

    def blur(self):
        self.focused = False

    # ==========================================================
    # INPUT
    # ==========================================================

    def process_event(self, key):
        if not self.focused:
            return False

        super().process_event(key)

        # ------------------------------------------------------
        # Submit
        # ------------------------------------------------------

        if key in (curses.KEY_ENTER, 10, 13):
            if callable(self.on_submit):
                self.on_submit(self.value)

            return True

        # ------------------------------------------------------
        # Cursor left
        # ------------------------------------------------------

        elif key == curses.KEY_LEFT:

            self.cursor_pos = max(
                0,
                self.cursor_pos - 1,
            )

            self._reset_cursor_blink()

            return True

        # ------------------------------------------------------
        # Cursor right
        # ------------------------------------------------------

        elif key == curses.KEY_RIGHT:

            self.cursor_pos = min(
                len(self.value),
                self.cursor_pos + 1,
            )

            self._reset_cursor_blink()

            return True

        # ------------------------------------------------------
        # Backspace
        # ------------------------------------------------------

        elif key in (curses.KEY_BACKSPACE, 8, 127):
            if self.cursor_pos > 0:
                self.value = (
                    self.value[:self.cursor_pos - 1]
                    + self.value[self.cursor_pos:]
                )

                self.cursor_pos -= 1

                self._reset_cursor_blink()

            return True

        # ------------------------------------------------------
        # Printable character
        # ------------------------------------------------------

        elif 32 <= key <= 126:
            char = chr(key)

            self.value = (
                self.value[:self.cursor_pos]
                + char
                + self.value[self.cursor_pos:]
            )

            self.cursor_pos += 1

            self._reset_cursor_blink()

            return True

        return False

    # ==========================================================
    # DRAW
    # ==========================================================

    def draw(self):
        if not self.window:
            return

        # ------------------------------------------------------
        # Text and scrolling
        # ------------------------------------------------------

        if self.value:
            display_text = self.value
            attr = curses.A_NORMAL

            # cursor_pos is an insertion position:
            #
            #   0 <= cursor_pos <= len(value)
            #
            # The cursor may therefore be immediately after
            # the final character.

            if self.cursor_pos < self.scroll_offset:
                self.scroll_offset = self.cursor_pos

            elif self.cursor_pos >= (
                self.scroll_offset + self.width
            ):
                self.scroll_offset = (
                    self.cursor_pos
                    - self.width
                    + 1
                )

            # Keep enough room for the cursor immediately after
            # the final character.
            max_offset = max(
                0,
                len(self.value) - self.width + 1,
            )

            self.scroll_offset = max(
                0,
                min(
                    self.scroll_offset,
                    max_offset,
                ),
            )

        else:
            display_text = self.placeholder
            attr = curses.A_DIM
            self.scroll_offset = 0

        # ------------------------------------------------------
        # Draw normal text
        # ------------------------------------------------------

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

        # ------------------------------------------------------
        # Software cursor
        # ------------------------------------------------------

        if not self.focused:
            return

        # Update the timer only while the widget is focused.
        self._update_cursor_blink()

        if not self._cursor_visible:
            return

        # Convert logical cursor position into the position
        # inside the visible window.
        screen_cursor_pos = (
            self.cursor_pos
            - self.scroll_offset
        )

        if not 0 <= screen_cursor_pos < self.width:
            raise RuntimeError(
                "TextInput cursor outside visible area: "
                f"cursor_pos={self.cursor_pos}, "
                f"scroll_offset={self.scroll_offset}, "
                f"screen_cursor_pos={screen_cursor_pos}, "
                f"width={self.width}"
            )

        # The cursor modifies the character at the current
        # position.
        #
        # If it is immediately after the final character,
        # there is no character to modify, so use the padded
        # space instead.
        cursor_char = (
            self.value[self.cursor_pos]
            if self.cursor_pos < len(self.value)
            else " "
        )

        try:
            self.window.addch(
                0,
                screen_cursor_pos,
                cursor_char,
                curses.A_REVERSE,
            )
        except curses.error:
            pass
