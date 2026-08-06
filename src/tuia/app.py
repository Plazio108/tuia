"""
tuia.app - Core engine and lifecycle management for the TUI.
"""
import curses
import contextlib
import time


class TUIApp:
    """
    The main application engine for the TUI.
    Manages the curses screen, event loop, automatic resizing, and flicker-free rendering.
    """

    def __init__(self, fps_target: int = 60, on_resize=None):
        self.stdscr = None
        self.running = False
        self.root_frame = None
        self._fps_target = fps_target
        self._frame_time = 1.0 / fps_target
        # Custom resize callback: on_resize(app, width, height)
        self.on_resize = on_resize

    def init_curses(self, stdscr):
        """Initializes curses parameters for optimal TUI experience."""
        self.stdscr = stdscr
        curses.curs_set(0)       # Hide the cursor by default
        self.stdscr.nodelay(1)   # Non-blocking input
        self.stdscr.keypad(1)    # Enable special keys (arrows, etc.)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()

    def set_root(self, frame):
        """Sets the root Frame that contains all other widgets."""
        self.root_frame = frame
        self.root_frame.app = self

    def start(self):
        """Starts the application and enters the curses wrapper."""
        if not self.root_frame:
            raise ValueError(
                "Cannot start TUIApp without a root frame. Call set_root() first.")
        curses.wrapper(self._run)

    def _run(self, stdscr):
        """The main internal event loop."""
        self.init_curses(stdscr)
        self.running = True

        # Trigger initial layout calculations
        self.root_frame._resize_to_terminal(self.stdscr)

        while self.running:
            loop_start = time.time()

            self._handle_input()
            self._update()
            self._render()

            elapsed = time.time() - loop_start
            if elapsed < self._frame_time:
                time.sleep(self._frame_time - elapsed)

    def _handle_input(self):
        """Fetches input and passes it to the root frame for event bubbling."""
        try:
            key = self.stdscr.getch()
            if key != curses.ERR:
                self.root_frame.handle_event(key)
        except curses.error:
            pass

    def _update(self):
        """Checks for terminal resize events and triggers layout recalculation."""
        if curses.is_term_resized(curses.LINES, curses.COLS):
            self.stdscr.clear()
            curses.update_lines_cols()
            curses.resizeterm(curses.LINES, curses.COLS)
            max_y, max_x = self.stdscr.getmaxyx()

            # 1. Default Behavior: Resize root frame to fit terminal window
            if self.root_frame:
                self.root_frame._resize_to_terminal(self.stdscr)

            # 2. User-provided custom resize handler
            if callable(self.on_resize):
                self.on_resize(self, max_x, max_y)

    def _render(self):
        """Executes a flicker-free render cycle."""
        self.stdscr.erase()
        self.stdscr.noutrefresh()
        self.root_frame.render()
        curses.doupdate()

    def quit(self):
        """Signals the application to terminate."""
        self.running = False

    @contextlib.contextmanager
    def suspend_for_handoff(self):
        """Context manager to handoff the screen to an external TUI app."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            yield
        finally:
            self.stdscr.clear()
            curses.reset_prog_mode()
            self.stdscr.refresh()
