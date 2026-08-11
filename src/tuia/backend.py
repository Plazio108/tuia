"""
tuia.backend - The double-buffered Textual bridge for Tuify Engine.
Translates synchronous 2D drawing operations into async Textual renders without screen tearing.
"""

import threading
from typing import Optional, Tuple, List, Union, Dict, ClassVar, TYPE_CHECKING

from textual.app import App as TextualApp, ComposeResult
from textual.widget import Widget
from rich.text import Text
from rich.style import Style

from tuia.constants import Modifiers

if TYPE_CHECKING:
    from tuia.app import TUIApp


class _Cell:
    __slots__ = ("char", "fg", "bg", "modifiers")

    def __init__(
        self,
        char: str = " ",
        fg: Union[None, Tuple[int, int, int], str] = None,
        bg: Union[None, Tuple[int, int, int], str] = None,
        modifiers: int = Modifiers.NORMAL,
    ):
        self.char = char
        self.fg = fg
        self.bg = bg
        self.modifiers = modifiers

    def clone_from(self, other: "_Cell"):
        """Fast shallow copy for atomic buffer swapping."""
        self.char = other.char
        self.fg = other.fg
        self.bg = other.bg
        self.modifiers = other.modifiers


class Window(Widget):
    """
    A 2D double-buffered canvas widget with style caching, span batching,
    and pre-compiled rendering offloaded from the Textual UI thread.
    """
    can_focus = True

    _style_cache: ClassVar[Dict[Tuple, Style]] = {}

    def __init__(self, tui_engine: "TUIApp", name: Optional[str] = None, id: Optional[str] = None):
        super().__init__(name=name, id=id)
        self.tui_engine = tui_engine
        self._back_buffer: List[List[_Cell]] = []
        self._front_buffer: List[List[_Cell]] = []
        self._rendered_text: Text = Text(no_wrap=True)
        self._height = 0
        self._width = 0
        self._active_attr = Modifiers.NORMAL
        self._dirty = False
        self._lock = threading.Lock()

    @classmethod
    def _get_style(cls, fg: Union[None, Tuple[int, int, int], str], bg: Union[None, Tuple[int, int, int], str], mod: int) -> Style:
        """Retrieves or creates a cached Rich Style object."""
        key = (fg, bg, mod)
        style = cls._style_cache.get(key)
        if style is None:
            fg_str = f"rgb({fg[0]},{fg[1]},{fg[2]})" if isinstance(fg, (tuple, list)) else fg
            bg_str = f"rgb({bg[0]},{bg[1]},{bg[2]})" if isinstance(bg, (tuple, list)) else bg
            style = Style(
                color=fg_str,
                bgcolor=bg_str,
                bold=bool(mod & Modifiers.BOLD),
                dim=bool(mod & Modifiers.DIM),
                underline=bool(mod & Modifiers.UNDERLINE),
                reverse=bool(mod & Modifiers.REVERSE),
                italic=bool(mod & Modifiers.ITALIC),
                strike=bool(mod & Modifiers.STRIKETHROUGH),
                overline=bool(mod & Modifiers.OVERLINE),
                blink=bool(mod & Modifiers.BLINK),
            )
            cls._style_cache[key] = style
        return style

    def getmaxyx(self) -> Tuple[int, int]:
        return self._height, self._width

    def attrset(self, attr: int):
        self._active_attr = attr

    def attron(self, attr: int):
        self._active_attr |= attr

    def attroff(self, attr: int):
        self._active_attr &= ~attr

    def on_resize(self, event) -> None:
        """Immediate synchronous reallocation on resize event."""
        new_w, new_h = event.size.width, event.size.height
        if new_w != self._width or new_h != self._height:
            self.resize_buffers(new_w, new_h)
            self.tui_engine._resize_flag = True

    def resize_buffers(self, new_width: int, new_height: int):
        """Reallocates double-buffers cleanly under lock."""
        with self._lock:
            self._back_buffer = [
                [_Cell() for _ in range(new_width)] for _ in range(new_height)
            ]
            self._front_buffer = [
                [_Cell() for _ in range(new_width)] for _ in range(new_height)
            ]
            self._width = new_width
            self._height = new_height
            self._dirty = True

    def force_full_repaint(self):
        """Invalidates front buffer and cached render text to force Textual to repaint from scratch."""
        with self._lock:
            w, h = self.size.width, self.size.height
            if w > 0 and h > 0 and (w != self._width or h != self._height):
                self.resize_buffers(w, h)
            self._front_buffer = []
            self._rendered_text = Text(no_wrap=True)
            self._dirty = True
        self.refresh(layout=True)

    def erase(self):
        """Clears all cells in the back buffer."""
        with self._lock:
            for y in range(self._height):
                for x in range(self._width):
                    cell = self._back_buffer[y][x]
                    cell.char = " "
                    cell.fg = None
                    cell.bg = None
                    cell.modifiers = Modifiers.NORMAL
            self._dirty = True

    def clear(self):
        self.erase()

    def addstr(self, y: int, x: int, text: str, attr: int = 0):
        """Writes a string to the back buffer, strictly clipped to bounds."""
        with self._lock:
            if y < 0 or y >= self._height or x < 0 or x >= self._width:
                return

            available = self._width - x
            if available <= 0:
                return

            effective_attr = self._active_attr | attr
            text = text[:available]

            for i, char in enumerate(text):
                cell = self._back_buffer[y][x + i]
                cell.char = char
                cell.modifiers = effective_attr
            self._dirty = True

    def addch(self, y: int, x: int, ch: str, attr: int = 0):
        """Writes a single character to the back buffer."""
        self.addstr(y, x, str(ch)[:1], attr)

    def inch(self, y: int, x: int) -> str:
        """Returns character at (y, x) in the back buffer."""
        with self._lock:
            if 0 <= y < self._height and 0 <= x < self._width:
                return self._back_buffer[y][x].char[0]
            return " "

    def noutrefresh(self):
        pass

    def doupdate(self):
        """
        Engine thread step: Pre-compiles Rich Text with span-batching & style caching.
        Only triggers a Textual refresh if visual output actually changed.
        """
        with self._lock:
            if not self._dirty:
                return

            if len(self._front_buffer) != self._height or (
                self._height > 0 and len(self._front_buffer[0]) != self._width
            ):
                self._front_buffer = [
                    [_Cell() for _ in range(self._width)] for _ in range(self._height)
                ]

            new_rendered = Text(no_wrap=True)

            for y in range(self._height):
                row = self._back_buffer[y]
                if not row:
                    continue

                for x in range(self._width):
                    self._front_buffer[y][x].clone_from(row[x])

                run_chars = []
                run_key = (row[0].fg, row[0].bg, row[0].modifiers)

                for x in range(self._width):
                    cell = row[x]
                    cell_key = (cell.fg, cell.bg, cell.modifiers)

                    if cell_key == run_key:
                        run_chars.append(cell.char)
                    else:
                        style = self._get_style(*run_key)
                        new_rendered.append("".join(run_chars), style=style)
                        run_chars = [cell.char]
                        run_key = cell_key

                if run_chars:
                    style = self._get_style(*run_key)
                    new_rendered.append("".join(run_chars), style=style)

                if y < self._height - 1:
                    new_rendered.append("\n")

            self._dirty = False

            if new_rendered == self._rendered_text:
                return

            self._rendered_text = new_rendered

        self.refresh()

    def render(self) -> Text:
        """
        Instantaneous render pass on Textual UI thread.
        Returns pre-compiled Rich Text without cell loops or style instantiations.
        """
        with self._lock:
            return self._rendered_text


class TextualBridgeApp(TextualApp):
    """Textual container housing the double-buffered window and routing events."""

    def __init__(self, tui_engine: "TUIApp"):
        super().__init__()
        self.tui_engine = tui_engine
        self.window = Window(self.tui_engine)

    def compose(self) -> ComposeResult:
        yield self.window

    def on_mount(self) -> None:
        self.tui_engine.stdscr = self.window
        self.set_focus(self.window)
        
        # Pre-size window buffer immediately using actual terminal dimensions
        term_w, term_h = self.console.size
        if term_w > 0 and term_h > 0:
            self.window.resize_buffers(term_w, term_h)

        self.run_worker(self._start_engine, thread=True)

    def _start_engine(self):
        self.tui_engine._run_engine()

    def on_key(self, event) -> None:
        """Dispatches raw event.key directly and immediately wakes up engine thread."""
        raw_key = event.key
        self.tui_engine.LOG.debug(f"[Input] Captured raw key: {raw_key!r}")

        if raw_key in ("ctrl+c", "ctrl+q"):
            self.tui_engine.LOG.info(f"[Input] Shutdown key {raw_key!r} detected. Terminating app...")
            self.tui_engine.quit()
            return

        self.tui_engine._input_queue.put(raw_key)
        self.tui_engine._ui_wakeup.set()
