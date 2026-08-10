"""
tuia.app - Core engine and lifecycle management for the TUI (Textual Backend).
"""

import contextlib
import queue
import threading
import time
from typing import Optional, Tuple, List, Union

from textual.app import App as TextualApp, ComposeResult
from textual.widget import Widget
from rich.text import Text
from rich.style import Style


# =============================================================================
# 2D WINDOW COMPATIBILITY LAYER (stdscr Replacement)
# =============================================================================

class _Cell:
    __slots__ = ("char", "fg", "bg", "modifiers")

    def __init__(
        self,
        char: str = " ",
        fg: Union[None, Tuple[int, int, int], str] = None,
        bg: Union[None, Tuple[int, int, int], str] = None,
        modifiers: int = 0,
    ):
        self.char = char
        self.fg = fg
        self.bg = bg
        self.modifiers = modifiers


class Window(Widget):
    """
    A 2D curses-compatible canvas widget that manages an explicit matrix buffer.
    Acts as a stdscr drop-in replacement for drawing and rendering.
    """

    def __init__(self, name: Optional[str] = None, id: Optional[str] = None):
        super().__init__(name=name, id=id)
        self._grid: List[List[_Cell]] = []
        self._height = 0
        self._width = 0
        self._active_attr = Modifiers.NORMAL
        self._lock = threading.Lock()

    def attrset(self, attr: int):
        self._active_attr = attr

    def attron(self, attr: int):
        self._active_attr |= attr

    def attroff(self, attr: int):
        self._active_attr &= ~attr

    def addstr(self, y: int, x: int, text: str, attr: int = 0):
        with self._lock:
            if y < 0 or y >= self._height or x < 0 or x >= self._width:
                return

            available = self._width - x
            if available <= 0:
                return

            effective_attr = self._active_attr | attr
            text = text[:available]

            for i, char in enumerate(text):
                cell = self._grid[y][x + i]
                cell.char = char
                cell.modifiers = effective_attr

    def on_resize(self, event) -> None:
        """Re-initializes matrix buffer on resize while preserving valid cell contents."""
        new_width, new_height = event.size.width, event.size.height

        with self._lock:
            new_grid = [
                [_Cell() for _ in range(new_width)] for _ in range(new_height)
            ]
            for y in range(min(self._height, new_height)):
                for x in range(min(self._width, new_width)):
                    new_grid[y][x] = self._grid[y][x]

            self._grid = new_grid
            self._height = new_height
            self._width = new_width

    def getmaxyx(self) -> Tuple[int, int]:
        """Returns (height, width) matching standard curses syntax."""
        return self._height, self._width

    def erase(self):
        """Clears all cells in the grid."""
        with self._lock:
            for y in range(self._height):
                for x in range(self._width):
                    cell = self._grid[y][x]
                    cell.char = " "
                    cell.fg = None
                    cell.bg = None
                    cell.modifiers = 0

    def clear(self):
        self.erase()

    def addstr(self, y: int, x: int, text: str, attr: int = 0):
        """Safely writes a string at (y, x), strictly clipped to window bounds."""
        with self._lock:
            if y < 0 or y >= self._height or x < 0 or x >= self._width:
                return

            available = self._width - x
            if available <= 0:
                return

            text = text[:available]
            for i, char in enumerate(text):
                cell = self._grid[y][x + i]
                cell.char = char
                cell.modifiers = attr

    def addch(self, y: int, x: int, ch: str, attr: int = 0):
        """Writes a single character at (y, x)."""
        self.addstr(y, x, str(ch)[:1], attr)

    def inch(self, y: int, x: int) -> int:
        """Mock inch for compatibility."""
        with self._lock:
            if 0 <= y < self._height and 0 <= x < self._width:
                return ord(self._grid[y][x].char[0])
            return 32

    def noutrefresh(self):
        """No-op for curses parity."""
        pass

    def doupdate(self):
        """Triggers a Textual widget refresh."""
        self.refresh()

    def render(self) -> Text:
        """Converts the internal 2D grid matrix into a styled Rich renderable."""
        rendered_text = Text()

        with self._lock:
            for y in range(self._height):
                for x in range(self._width):
                    cell = self._grid[y][x]

                    fg = (
                        f"rgb({cell.fg[0]},{cell.fg[1]},{cell.fg[2]})"
                        if isinstance(cell.fg, (tuple, list))
                        else cell.fg
                    )
                    bg = (
                        f"rgb({cell.bg[0]},{cell.bg[1]},{cell.bg[2]})"
                        if isinstance(cell.bg, (tuple, list))
                        else cell.bg
                    )

                    style = Style(
                        color=fg,
                        bgcolor=bg,
                        bold=bool(cell.modifiers & 1),
                        dim=bool(cell.modifiers & 2),
                        underline=bool(cell.modifiers & 4),
                        reverse=bool(cell.modifiers & 8),
                        italic=bool(cell.modifiers & 16),
                    )
                    rendered_text.append(cell.char, style=style)

                if y < self._height - 1:
                    rendered_text.append("\n")

        return rendered_text


# =============================================================================
# TEXTUAL BRIDGE APP
# =============================================================================

class _TextualBridgeApp(TextualApp):
    """Textual container housing the 2D window buffer and routing events."""

    def __init__(self, tui_engine: "TUIApp"):
        super().__init__()
        self.tui_engine = tui_engine
        self.window = Window()

    def compose(self) -> ComposeResult:
        yield self.window

    def on_mount(self) -> None:
        self.tui_engine.stdscr = self.window
        # Start TUIApp foreground thread execution inside Textual worker
        self.run_worker(self._start_engine, thread=True)

    def _start_engine(self):
        self.tui_engine._run_engine()

    def on_key(self, event) -> None:
        """Routes Textual keyboard events to TUIApp input queue."""
        key = event.character if event.character else event.key
        self.tui_engine._input_queue.put(key)

    def on_resize(self, event) -> None:
        """Signals resize to the TUIApp engine."""
        self.tui_engine._resize_flag = True


# =============================================================================
# MAIN TUIA APPLICATION ENGINE
# =============================================================================

class TUIApp:
    """
    The main application engine for the TUI.

    Manages:
        - 2D window rendering buffer
        - event loop
        - automatic resizing
        - flicker-free rendering
        - thread-safe UI updates
        - temporary background TUI execution
    """

    def __init__(self, fps_target: int = 60, on_resize=None):
        self.stdscr = None  # Holds the 2D Window instance
        self.running = False
        self.root_frame = None

        self._fps_target = fps_target
        self._frame_time = 1.0 / fps_target

        self.on_resize = on_resize
        self._textual_app = None
        self._input_queue = queue.Queue()
        self._resize_flag = False

        # ======================================================
        # UI QUEUE
        # ======================================================

        self._ui_queue = queue.Queue()
        self._ui_wakeup = threading.Event()
        self._ui_thread_id = None

        # ======================================================
        # BACKGROUND UI ENGINE
        # ======================================================

        self._tui_thread = None
        self.background_running = False
        self._background_stop = threading.Event()
        self._background_finished = threading.Event()
        self._background_finished.set()

        self.ignore_input = False

    def set_root(self, frame):
        """Set the root Frame."""
        self.root_frame = frame
        self.root_frame.app = self

    # ==========================================================
    # UI THREAD OWNERSHIP
    # ==========================================================

    def is_ui_thread(self):
        """Return True if the current thread owns the TUI."""
        return (
            self._ui_thread_id is not None
            and threading.get_ident() == self._ui_thread_id
        )

    # ==========================================================
    # BACKGROUND LOOP
    # ==========================================================

    def start_background_loop(self, handle_input=False):
        """Temporarily transfer TUI ownership to a background thread."""
        if not self.running:
            return

        if not self.root_frame:
            raise ValueError("Call set_root() and start() before")

        if self.background_running:
            return

        self.ignore_input = not handle_input

        self._background_stop.clear()
        self._background_finished.clear()
        self.background_running = True

        self._tui_thread = threading.Thread(
            target=self._run_background_loop,
            daemon=True,
            name="TUI-background",
        )
        self._tui_thread.start()

    def _run_background_loop(self):
        """Execute the temporary UI loop in the background thread."""
        self._ui_thread_id = threading.get_ident()

        try:
            while self.running and not self._background_stop.is_set():
                loop_start = time.monotonic()
                self._ui_wakeup.clear()

                self.loop()

                if self._background_stop.is_set():
                    break

                elapsed = time.monotonic() - loop_start
                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(self._frame_time - elapsed)

        finally:
            self.background_running = False
            self.ignore_input = False

            if self._ui_thread_id == threading.get_ident():
                self._ui_thread_id = None

            self._background_finished.set()
            self._ui_wakeup.set()

    def stop_background_loop(self):
        """Stop the temporary background TUI loop safely."""
        thread = self._tui_thread

        if thread is None:
            self.background_running = False
            self.ignore_input = False
            return

        self._background_stop.set()
        self._ui_wakeup.set()

        if thread is threading.current_thread():
            return

        self._background_finished.wait()
        thread.join()

        if self._tui_thread is thread:
            self._tui_thread = None

        self.background_running = False
        self.ignore_input = False

        if self.running:
            self._ui_thread_id = threading.get_ident()

    # ==========================================================
    # UI QUEUE
    # ==========================================================

    def flush(self):
        """Wait until all UI operations queued before this call are processed."""
        if self.is_ui_thread():
            self._flush_queue()
            return

        done = threading.Event()

        def barrier():
            done.set()

        self._ui_queue.put(barrier)
        self._ui_wakeup.set()
        done.wait()

    def _flush_queue(self):
        """Execute every currently queued UI operation."""
        while True:
            try:
                func = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            func()

    # ==========================================================
    # MAIN ENTRY POINT
    # ==========================================================

    def start(self):
        """Start the main TUI loop via Textual backend."""
        if not self.root_frame:
            raise ValueError(
                "Cannot start TUIApp without a root frame. Call set_root() first."
            )

        self._textual_app = _TextualBridgeApp(self)
        self._textual_app.run()

    # ==========================================================
    # FOREGROUND LOOP
    # ==========================================================

    def _run_engine(self):
        """Main foreground TUI loop running on Textual worker thread."""
        self._ui_thread_id = threading.get_ident()

        try:
            self.running = True

            if self.root_frame and self.stdscr:
                self.root_frame._resize_to_terminal(self.stdscr)

            while self.running:
                if self.background_running:
                    self._background_finished.wait()

                    if not self.running:
                        break

                    self._ui_thread_id = threading.get_ident()

                    if (
                        self._tui_thread is not None
                        and not self._tui_thread.is_alive()
                    ):
                        self._tui_thread = None

                    self.ignore_input = False
                    continue

                if self._tui_thread is not None:
                    thread = self._tui_thread

                    if thread.is_alive():
                        self._background_finished.wait()

                    thread.join()

                    if self._tui_thread is thread:
                        self._tui_thread = None

                    self.background_running = False
                    self.ignore_input = False
                    self._ui_thread_id = threading.get_ident()
                    continue

                loop_start = time.monotonic()
                self._ui_wakeup.clear()

                self.loop()

                if self.background_running:
                    continue

                elapsed = time.monotonic() - loop_start
                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(self._frame_time - elapsed)

        finally:
            self.running = False
            self._background_stop.set()
            self._ui_wakeup.set()

            thread = self._tui_thread
            if thread is not None and thread is not threading.current_thread():
                self._background_finished.wait()
                thread.join()

            self._tui_thread = None
            self.background_running = False
            self.ignore_input = False
            self._ui_thread_id = None

    # ==========================================================
    # ONE UI FRAME
    # ==========================================================

    def loop(self):
        """Perform one complete update/render cycle."""
        self._flush_queue()
        self._handle_input()
        self._update()
        self._render()

    # ==========================================================
    # INPUT
    # ==========================================================

    def _handle_input(self):
        """Fetch and dispatch one input event from queue."""
        while not self._input_queue.empty():
            try:
                key = self._input_queue.get_nowait()
                if self.ignore_input:
                    continue
                else:
                    if self.root_frame:
                        self.root_frame.handle_event(key)
            except queue.Empty:
                break

    # ==========================================================
    # UPDATE
    # ==========================================================

    def _update(self):
        """Handle terminal resizing."""
        if self._resize_flag:
            self._resize_flag = False

            if self.stdscr:
                self.stdscr.clear()
                max_y, max_x = self.stdscr.getmaxyx()

                if self.root_frame:
                    self.root_frame._resize_to_terminal(self.stdscr)

                if callable(self.on_resize):
                    self.on_resize(self, max_x, max_y)

    # ==========================================================
    # RENDER
    # ==========================================================

    def _render(self):
        """Execute a flicker-free render cycle."""
        if not self.stdscr or not self.root_frame:
            return

        self.stdscr.erase()
        self.root_frame.render()
        self.stdscr.doupdate()

    def clear(self):
        if self.stdscr:
            self.stdscr.clear()

    # ==========================================================
    # QUIT
    # ==========================================================

    def quit(self):
        """Request application shutdown."""
        self.running = False
        self._background_stop.set()
        self._ui_wakeup.set()
        if self._textual_app:
            self._textual_app.exit()

    # ==========================================================
    # EXTERNAL TUI HANDOFF
    # ==========================================================

    @contextlib.contextmanager
    def suspend_for_handoff(self):
        """Temporarily give the terminal to an external CLI/TUI program."""
        if self._textual_app:
            with self._textual_app.suspend():
                yield
                if self.stdscr:
                    self.stdscr.clear()
        else:
            yield