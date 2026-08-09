"""
tuia.app - Core engine and lifecycle management for the TUI.
"""

import contextlib
import curses
import queue
import threading
import time


class TUIApp:
    """
    The main application engine for the TUI.

    Manages:
        - curses screen
        - event loop
        - automatic resizing
        - flicker-free rendering
        - thread-safe UI updates
        - temporary background TUI execution
    """

    def __init__(self, fps_target: int = 60, on_resize=None):
        self.stdscr = None
        self.running = False
        self.root_frame = None

        self._fps_target = fps_target
        self._frame_time = 1.0 / fps_target

        self.on_resize = on_resize

        # ======================================================
        # UI QUEUE
        # ======================================================

        self._ui_queue = queue.Queue()

        # Wakes the thread currently owning the UI.
        self._ui_wakeup = threading.Event()

        # ID of the thread currently owning curses/UI operations.
        self._ui_thread_id = None

        # ======================================================
        # BACKGROUND UI ENGINE
        # ======================================================

        self._tui_thread = None

        # True while the temporary background UI loop is active.
        self.background_running = False

        # Tells the background loop that it must terminate.
        self._background_stop = threading.Event()

        # Set when the background loop has completely terminated.
        self._background_finished = threading.Event()
        self._background_finished.set()

        # Whether input should be discarded while running
        # the temporary background UI.
        self.ignore_input = False

    # ==========================================================
    # CURSES
    # ==========================================================

    def init_curses(self, stdscr):
        """Initialize curses parameters."""
        self.stdscr = stdscr

        curses.curs_set(0)

        self.stdscr.nodelay(1)
        self.stdscr.keypad(1)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()

    def set_root(self, frame):
        """Set the root Frame."""
        self.root_frame = frame
        self.root_frame.app = self

    # ==========================================================
    # UI THREAD OWNERSHIP
    # ==========================================================

    def is_ui_thread(self):
        """
        Return True if the calling thread currently owns the TUI.
        """
        return (
            self._ui_thread_id is not None
            and threading.get_ident() == self._ui_thread_id
        )

    # ==========================================================
    # BACKGROUND LOOP
    # ==========================================================

    def start_background_loop(self, handle_input=False):
        """
        Temporarily transfer TUI ownership to a background thread.
        """
        if not self.running:
            return

        if not self.root_frame:
            raise ValueError(
                "Call set_root() and start() before"
            )

        # Already running.
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
        """
        Execute the temporary UI loop in the background thread.
        """
        self._ui_thread_id = threading.get_ident()

        try:
            while (
                self.running
                and not self._background_stop.is_set()
            ):
                loop_start = time.monotonic()

                # Consume any previous wake-up.
                self._ui_wakeup.clear()

                self.loop()

                elapsed = time.monotonic() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )

        finally:
            # --------------------------------------------------
            # IMPORTANT:
            #
            # This path is reached both when:
            #   - stop_background_loop() stops us
            #   - quit() stops the application
            #   - running becomes false
            #
            # Therefore ALL background state must be restored here.
            # --------------------------------------------------

            self.background_running = False
            self.ignore_input = False

            # Release UI ownership.
            if self._ui_thread_id == threading.get_ident():
                self._ui_thread_id = None

            # Tell the foreground loop that ownership is back.
            self._background_finished.set()

            # Wake the foreground loop if it happens to be waiting.
            self._ui_wakeup.set()

    def stop_background_loop(self):
        """
        Explicitly stop the temporary background UI loop.

        Safe to call from another thread.
        """
        thread = self._tui_thread

        if thread is None:
            # Ensure the state is still sane.
            self.background_running = False
            self.ignore_input = False
            return

        # Request termination.
        self._background_stop.set()

        # Interrupt Event.wait() immediately.
        self._ui_wakeup.set()

        # If called from the background thread itself, we cannot
        # join ourselves.
        if thread is not threading.current_thread():
            thread.join()

        # At this point the thread should be finished.
        if not thread.is_alive():
            self._tui_thread = None

        self.background_running = False
        self.ignore_input = False

    # ==========================================================
    # UI QUEUE
    # ==========================================================

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

        # Wake whichever thread currently owns the UI.
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
        """
        Start the main TUI loop.

        curses.wrapper() is intentionally kept at the outermost
        level so terminal restoration happens even when an exception
        or KeyboardInterrupt occurs.
        """
        if not self.root_frame:
            raise ValueError(
                "Cannot start TUIApp without a root frame. "
                "Call set_root() first."
            )

        curses.wrapper(self._run)

    # ==========================================================
    # FOREGROUND LOOP
    # ==========================================================

    def _run(self, stdscr):
        """
        Main foreground TUI loop.

        While a background TUI is active, this thread waits and
        does not touch curses.
        """
        self._ui_thread_id = threading.get_ident()

        try:
            self.init_curses(stdscr)

            self.running = True

            # Initial layout.
            self.root_frame._resize_to_terminal(
                self.stdscr
            )

            while self.running:

                # ==================================================
                # BACKGROUND TUI OWNS THE SCREEN
                # ==================================================

                if self.background_running:
                    # Do NOT execute curses operations here.
                    #
                    # The background thread owns the UI.
                    self._background_finished.wait()

                    if not self.running:
                        break

                    # Background thread is finished.
                    self._ui_thread_id = threading.get_ident()

                    if (
                        self._tui_thread is not None
                        and not self._tui_thread.is_alive()
                    ):
                        self._tui_thread = None

                    # Continue immediately with a foreground frame.
                    continue

                # ==================================================
                # CLEAN UP NATURALLY FINISHED BACKGROUND THREAD
                # ==================================================

                if self._tui_thread is not None:

                    if self._tui_thread.is_alive():
                        # This shouldn't normally happen here because
                        # background_running should remain true while
                        # the thread is alive, but don't touch curses
                        # if ownership is ambiguous.
                        self._background_finished.wait()

                    self._tui_thread.join()
                    self._tui_thread = None

                    self.ignore_input = False
                    self._ui_thread_id = threading.get_ident()

                    continue

                # ==================================================
                # NORMAL FOREGROUND FRAME
                # ==================================================

                loop_start = time.monotonic()

                self._ui_wakeup.clear()

                self.loop()

                elapsed = time.monotonic() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )

        finally:
            # ------------------------------------------------------
            # If the foreground loop exits for ANY reason, make
            # absolutely sure no background thread is left owning
            # the TUI.
            # ------------------------------------------------------

            self.running = False

            self._background_stop.set()
            self._ui_wakeup.set()

            background_thread = self._tui_thread

            if (
                background_thread is not None
                and background_thread is not threading.current_thread()
            ):
                background_thread.join()

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
        """Fetch and dispatch one input event."""
        try:
            key = self.stdscr.getch()

            if key != curses.ERR:

                if self.ignore_input:
                    curses.flushinp()

                else:
                    self.root_frame.handle_event(key)

        except curses.error:
            pass

    # ==========================================================
    # UPDATE
    # ==========================================================

    def _update(self):
        """Handle terminal resizing and layout updates."""
        if curses.is_term_resized(
            curses.LINES,
            curses.COLS
        ):
            curses.update_lines_cols()

            curses.resizeterm(
                curses.LINES,
                curses.COLS
            )

            self.stdscr.clear()

            max_y, max_x = self.stdscr.getmaxyx()

            if self.root_frame:
                self.root_frame._resize_to_terminal(
                    self.stdscr
                )

            if callable(self.on_resize):
                self.on_resize(
                    self,
                    max_x,
                    max_y,
                )

    # ==========================================================
    # RENDER
    # ==========================================================

    def _render(self):
        """Execute a flicker-free render cycle."""
        self.stdscr.erase()
        self.stdscr.noutrefresh()

        self.root_frame.render()

        curses.doupdate()

    # ==========================================================
    # QUIT
    # ==========================================================

    def quit(self):
        """
        Request application shutdown.

        This method deliberately does not join the background
        thread itself. It only signals the loops to stop.

        The owning loop performs the actual cleanup.
        """
        self.running = False

        self._background_stop.set()

        # Wake:
        #   - foreground frame sleep
        #   - background frame sleep
        #   - foreground ownership wait
        self._ui_wakeup.set()

    # ==========================================================
    # EXTERNAL TUI HANDOFF
    # ==========================================================

    @contextlib.contextmanager
    def suspend_for_handoff(self):
        """
        Temporarily give the terminal to an external TUI program.
        """
        curses.def_prog_mode()
        curses.endwin()

        try:
            yield

        finally:
            self.stdscr.clear()
            curses.reset_prog_mode()
            self.stdscr.refresh()
