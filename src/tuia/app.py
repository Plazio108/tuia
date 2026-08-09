"""
tuia.app - Core engine and lifecycle management for the TUI.
"""
import curses
import contextlib
import time
import threading
import queue


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

        # --- Thread-Safe UI Updates ---
        self._ui_queue = queue.Queue()

        # Wakes the UI thread when another thread queues work.
        self._ui_wakeup = threading.Event()

        # Identifies the thread that owns the TUI loop.
        self._ui_thread_id = None

        # --- Temporary Background Engine ---
        self._tui_thread = None
        self.background_running = False
        self.ignore_input = False

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

    # ==========================================
    # TEMPORARY BACKGROUND ENGINE
    # ==========================================

    def start_background_loop(self, handle_input=False):
        """Starts the TUI engine temporarily in a background thread."""
        if not self.running:
            return

        if not self.root_frame:
            raise ValueError("Call set_root() and start() before")

        self.ignore_input = not handle_input
        self._tui_thread = threading.Thread(
            target=self._run_background_loop, daemon=True)
        self._tui_thread.start()

    def _run_background_loop(self):
        """Wrapper to execute curses loop inside the background thread."""
        self._ui_thread_id = threading.get_ident()
        self.background_running = True

        try:
            while self.background_running:
                loop_start = time.time()

                self._ui_wakeup.clear()

                self.loop()

                elapsed = time.time() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )

        finally:
            self._ui_thread_id = None
            print('test')

    def stop_background_loop(self):
        """Manually stops the temporary background TUI thread."""
        if self.background_running and self._tui_thread and self._tui_thread.is_alive():
            self.background_running = False
            self._tui_thread.join()  # Wait for the UI loop to safely exit curses
            self._tui_thread = None
            self.ignore_input = False

    def flush(self):
        """
        Wait until all UI operations queued before this call
        have been processed.
        """
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
        """Process everything currently pending in the UI queue."""
        while True:
            try:
                func = self._ui_queue.get_nowait()
            except queue.Empty:
                break

            func()

    def is_ui_thread(self):
        """Return True if called from the thread currently running the TUI."""
        return (
            self._ui_thread_id is not None
            and threading.get_ident() == self._ui_thread_id
        )

    # ==========================================
    # FOREGROUND MAIN LOOP
    # ==========================================

    def start(self):
        """
        Starts the main TUI loop in the foreground (blocking).
        """
        if not self.root_frame:
            raise ValueError(
                "Cannot start TUIApp without a root frame. Call set_root() first.")

        curses.wrapper(self._run)

    def loop(self):
        """Perform one update of the TUI."""
        # Process thread-safe structural updates first

        self._flush_queue()

        self._handle_input()
        self._update()
        self._render()

    def _run(self, stdscr):
        """The main internal event loop."""
        self._ui_thread_id = threading.get_ident()

        try:
            self.init_curses(stdscr)
            self.running = True

            # Trigger initial layout calculations
            self.root_frame._resize_to_terminal(self.stdscr)

            while self.running:
                if self.background_running or self._tui_thread:
                    self.stop_background_loop()
                    self.background_running = False
                    if self._tui_thread:
                        self._tui_thread.join(0)
                        self._tui_thread = None

                if self._ui_thread_id != threading.get_ident():
                    self._ui_thread_id = threading.get_ident()
                    print('mainuhbzedhbadhahzbdjahzbjhbecjhbazjhbajhbcjhbhanbkhzbjkcjnkjnakhzbbkjnkxjankzhbhbckjanzkjbxkjnc')

                loop_start = time.time()

                # Any wake-up that caused us to enter this iteration
                # has now been consumed.
                self._ui_wakeup.clear()

                self.loop()

                elapsed = time.time() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )
        finally:
            self._ui_thread_id = None

    def _handle_input(self):
        """Fetches input and passes it to the root frame for event bubbling."""
        try:
            key = self.stdscr.getch()
            if key != curses.ERR:
                if self.ignore_input:
                    curses.flushinp()
                else:
                    self.root_frame.handle_event(key)
        except curses.error:
            pass

    def _update(self):
        """Checks for terminal resize events and triggers layout recalculation."""
        if curses.is_term_resized(curses.LINES, curses.COLS):

            curses.update_lines_cols()
            curses.resizeterm(curses.LINES, curses.COLS)

            self.stdscr.clear()

            max_y, max_x = self.stdscr.getmaxyx()

            # Default Behavior: Resize root frame to fit terminal window
            if self.root_frame:
                self.root_frame._resize_to_terminal(self.stdscr)

            # User-provided custom resize handler
            if callable(self.on_resize):
                self.on_resize(self, max_x, max_y)

    def _render(self):
        """Executes a flicker-free render cycle."""
        self.stdscr.erase()
        self.stdscr.noutrefresh()
        self.root_frame.render()
        curses.doupdate()

    def quit(self):
        """Signals the application loop to terminate."""
        self.stop_background_loop()
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
