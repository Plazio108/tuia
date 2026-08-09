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

        # Thread ID currently owning curses/UI operations.
        self._ui_thread_id = None

        # ======================================================
        # BACKGROUND UI ENGINE
        # ======================================================

        self._tui_thread = None

        # True while the background loop is active.
        self.background_running = False

        # Requests that the background loop terminate.
        self._background_stop = threading.Event()

        # Set once the background loop has completely terminated.
        self._background_finished = threading.Event()
        self._background_finished.set()

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
        """Return True if the current thread owns the TUI."""
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

                # Consume any old wake-up.
                self._ui_wakeup.clear()

                self.loop()

                # A stop could have been requested while loop()
                # was executing. Don't sleep in that case.
                if self._background_stop.is_set():
                    break

                elapsed = time.monotonic() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )

        finally:
            # ----------------------------------------------
            # Background ownership is ending.
            # ----------------------------------------------

            self.background_running = False
            self.ignore_input = False

            if self._ui_thread_id == threading.get_ident():
                self._ui_thread_id = None

            # This is the synchronization point used by the
            # foreground thread and stop_background_loop().
            self._background_finished.set()

            # Wake anything waiting for the background loop.
            self._ui_wakeup.set()

    def stop_background_loop(self):
        """
        Stop the temporary background TUI loop.

        This method waits until the background thread has actually
        terminated and released UI ownership.

        It is safe to call:
            - from the foreground thread
            - from another worker thread
            - from the background UI thread itself
        """
        thread = self._tui_thread

        # Nothing to stop.
        if thread is None:
            self.background_running = False
            self.ignore_input = False
            return

        # Request termination.
        self._background_stop.set()

        # Wake it immediately if it is sleeping.
        self._ui_wakeup.set()

        # ----------------------------------------------
        # Called by the background UI thread itself.
        #
        # It cannot wait for itself.
        # Its finally block will perform the cleanup.
        # ----------------------------------------------
        if thread is threading.current_thread():
            return

        # ----------------------------------------------
        # Called by another thread.
        #
        # Wait for the actual ownership handoff rather
        # than merely waiting on Thread.join().
        # ----------------------------------------------
        self._background_finished.wait()

        # At this point the background thread has released
        # UI ownership.
        thread.join()

        if self._tui_thread is thread:
            self._tui_thread = None

        self.background_running = False
        self.ignore_input = False

        # If we're now the UI thread, restore ownership.
        if self.running:
            self._ui_thread_id = threading.get_ident()

    # ==========================================================
    # UI QUEUE
    # ==========================================================

    def flush(self):
        """
        Wait until all UI operations queued before this call
        have been processed.

        If called from the UI thread, process them immediately.
        """
        if self.is_ui_thread():
            self._flush_queue()
            return

        done = threading.Event()

        def barrier():
            done.set()

        self._ui_queue.put(barrier)

        # Wake the current UI owner.
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

        curses.wrapper() remains the outer boundary so that
        curses restores the terminal on exceptions and
        KeyboardInterrupt.
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

        The foreground thread does not touch curses while the
        background thread owns the TUI.
        """
        self._ui_thread_id = threading.get_ident()

        try:
            self.init_curses(stdscr)

            self.running = True

            self.root_frame._resize_to_terminal(
                self.stdscr
            )

            while self.running:

                # ==================================================
                # BACKGROUND TUI OWNS THE SCREEN
                # ==================================================

                if self.background_running:

                    # Wait until the background thread's finally
                    # block signals that ownership has returned.
                    self._background_finished.wait()

                    if not self.running:
                        break

                    # The foreground thread gets ownership back.
                    self._ui_thread_id = threading.get_ident()

                    if (
                        self._tui_thread is not None
                        and not self._tui_thread.is_alive()
                    ):
                        self._tui_thread = None

                    self.ignore_input = False

                    continue

                # ==================================================
                # CLEAN UP A NATURALLY FINISHED THREAD
                # ==================================================

                if self._tui_thread is not None:

                    thread = self._tui_thread

                    if thread.is_alive():
                        # Ownership is ambiguous, so wait for the
                        # actual background completion signal.
                        self._background_finished.wait()

                    thread.join()

                    if self._tui_thread is thread:
                        self._tui_thread = None

                    self.background_running = False
                    self.ignore_input = False
                    self._ui_thread_id = threading.get_ident()

                    continue

                # ==================================================
                # NORMAL FOREGROUND FRAME
                # ==================================================

                loop_start = time.monotonic()

                self._ui_wakeup.clear()

                self.loop()

                # A background loop could have been started by code
                # executed during this frame.
                if self.background_running:
                    continue

                elapsed = time.monotonic() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )

        finally:
            # ======================================================
            # FINAL APPLICATION CLEANUP
            # ======================================================

            self.running = False

            self._background_stop.set()
            self._ui_wakeup.set()

            thread = self._tui_thread

            if (
                thread is not None
                and thread is not threading.current_thread()
            ):
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
        """Handle terminal resizing."""
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

        Does not join threads. The active loop will perform the
        final cleanup itself.
        """
        self.running = False

        self._background_stop.set()
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
