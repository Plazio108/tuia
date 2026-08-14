"""
tuia.frame - Frame container widget with customizable borders and titles.
"""

import curses

from tuia.base import Widget
from tuia.layout import compute_layout

# Border Style Definitions: (top_left, top_right, bottom_left, bottom_right, horiz, vert)
BORDER_NONE = None
BORDER_SINGLE = ("┌", "┐", "└", "┘", "─", "│")
BORDER_DOUBLE = ("╔", "╗", "╚", "╝", "═", "║")
BORDER_ROUNDED = ("╭", "╮", "╰", "╯", "─", "│")
BORDER_ASCII = ("+", "+", "+", "+", "-", "|")


class Frame(Widget):
    """
    A container widget that can host child widgets, manage nested layouts,
    and render preset or custom border styles with optional titles.
    """

    def __init__(
        self,
        parent=None,
        title="",
        border_style=BORDER_SINGLE,
        x=0,
        y=0,
        width=10,
        height=3,
        z_index=0,
    ):
        super().__init__(
            parent=parent, x=x, y=y, width=width, height=height, z_index=z_index
        )
        self.title = title
        self.border_style = border_style

    def get_content_area(self):
        """
        Returns the inner content bounds (x, y, width, height) available for child widgets.
        Accounts for border thickness if borders are enabled.
        """
        if self.border_style is None:
            return self.x, self.y, self.width, self.height

        # With border: inner area is offset by 1 char on all sides
        inner_x = self.x + 1
        inner_y = self.y + 1
        inner_w = max(1, self.width - 2)
        inner_h = max(1, self.height - 2)
        return inner_x, inner_y, inner_w, inner_h

    def _resize_to_terminal(self, stdscr):
        """
        Special method used by TUIApp for the root frame to match terminal window size
        and recursively re-layout all children.
        """
        max_y, max_x = stdscr.getmaxyx()
        self.update_geometry(0, 0, max_x, max_y)
        self.update_layout()

    def update_layout(self):
        """Triggers geometry recalculation for all children and nested frames."""
        compute_layout(self)
        for child in self.children:
            child.update_layout()

    def update_geometry(self, x, y, width, height):
        """Override geometry update to recalculate inner layouts automatically."""
        super().update_geometry(x, y, width, height)
        self.update_layout()

    def draw(self):
        """Draws the frame's border and title onto its curses window."""
        if not self.window:
            return

        # 1. Draw Border if configured
        if self.border_style:
            tl, tr, bl, br, h, v = self.border_style

            # Horizontal borders
            if self.width > 0:
                line = (h * self.width)[: self.width]
                try:
                    self.window.addstr(0, 0, line)
                except curses.error:
                    pass
                try:
                    self.window.addstr(self.height - 1, 0, line)
                except curses.error:
                    pass

            # Vertical borders
            for y_pos in range(self.height):
                try:
                    self.window.addstr(y_pos, 0, v)
                except curses.error:
                    pass
                try:
                    self.window.addstr(y_pos, max(0, self.width - 1), v)
                except curses.error:
                    pass

            # Four Corners
            try:
                self.window.addstr(0, 0, tl)
            except curses.error:
                pass
            try:
                self.window.addstr(0, max(0, self.width - 1), tr)
            except curses.error:
                pass
            try:
                self.window.addstr(max(0, self.height - 1), 0, bl)
            except curses.error:
                pass
            try:
                self.window.addstr(max(0, self.height - 1), max(0, self.width - 1), br)
            except curses.error:
                pass

        # 2. Draw Title if provided and space permits
        if self.title and self.border_style and self.width > 4:
            max_title_len = self.width - 4
            formatted_title = f" {self.title[:max_title_len]} "
            try:
                self.window.addstr(0, 2, formatted_title)
            except curses.error:
                pass

    def render(self):
        """
        Calculates layout before delegating rendering to the base class pipeline.
        """
        if not self.visible or not self.window:
            return

        # Ensure layout calculation is fresh before child rendering
        compute_layout(self)
        super().render()
