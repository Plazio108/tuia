"""
tuia.window - The gleaf bridge for Tuia Engine.
Translates synchronous curses-like 2D drawing operations directly into gleaf's high-performance canvas.
"""

import threading
from typing import Tuple, TYPE_CHECKING

from gleaf import TerminalCanvas
from tuia.constants import Modifiers

if TYPE_CHECKING:
    from tuia.app import TUIApp


class Window:
    """
    A 2D canvas facade that mimics standard curses/textual window operations,
    but pipes all drawing and rendering natively into gleaf.
    """

    def __init__(self, tui_engine: "TUIApp", backend: str = "auto"):
        self.tui_engine = tui_engine

        # Use gleaf's auto-resolution for the best available backend
        self.canvas = TerminalCanvas(backend=backend)

        self._active_attr = Modifiers.NORMAL
        self._lock = threading.Lock()

    def getmaxyx(self) -> Tuple[int, int]:
        """Returns (height, width)."""
        return self.canvas.height, self.canvas.width

    def attrset(self, attr: int):
        self._active_attr = attr

    def attron(self, attr: int):
        self._active_attr |= attr

    def attroff(self, attr: int):
        self._active_attr &= ~attr

    def resize_buffers(self, new_width: int, new_height: int):
        """Passes resize signals down to gleaf."""
        with self._lock:
            self.canvas.resize(new_width, new_height)

    def force_full_repaint(self):
        """Forces the terminal to repaint from scratch."""
        with self._lock:
            self.canvas.clear()
        self.doupdate()

    def erase(self):
        """Clears all cells in the gleaf buffer."""
        with self._lock:
            self.canvas.clear()

    def clear(self):
        self.erase()

    def addstr(self, y: int, x: int, text: str, attr: int = 0):
        """Writes a string to the buffer, using gleaf's bounds-checked put_str."""
        with self._lock:
            effective_attr = self._active_attr | attr
            # Note: Assuming gleaf handles the bitmask 'style' directly,
            # or you can map `Modifiers` to gleaf's Style constants here if they differ.
            self.canvas.put_str(x, y, text, style=effective_attr)

    def addch(self, y: int, x: int, ch: str, attr: int = 0):
        """Writes a single character to the buffer."""
        self.addstr(y, x, str(ch)[:1], attr)

    def inch(self, y: int, x: int) -> str:
        """Returns character at (y, x)."""
        with self._lock:
            try:
                return self.canvas.get_char(x, y)
            except Exception:
                return " "

    def noutrefresh(self):
        pass  # doupdate handles the render pass automatically in gleaf

    def doupdate(self):
        """Fires the gleaf backend render cycle."""
        with self._lock:
            self.canvas.render()
