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

        # Custom resize callback:
        # on_resize(app, width, height)
        self.on_resize = on_resize

        # ======================================================
        # THREAD-SAFE UI UPDATES
        # ======================================================

        # Functions waiting to be executed by the current UI thread.
        self._ui_queue = queue.Queue()

        # Wakes the current UI thread when:
        #   - another thread queues UI work
        #   - the current frame sleep needs to be interrupted
        self._ui_wakeup = threading.Event()

        # Identifies the thread currently owning the TUI.
        self._ui_thread_id = None

        # ======================================================
        # TEMPORARY BACKGROUND ENGINE
        # ======================================================

        self._tui_thread = None

        # True while the temporary background TUI owns curses.
        self.background_running = False

        # Signals the background TUI thread that it should stop.
        self._background_stop = threading.Event()

        # Set when the background TUI thread has completely stopped.
        #
        # This allows the foreground thread to wait for ownership
        # to be returned safely.
        self._background_finished = threading.Event()
        self._background_finished.set()

        self.ignore_input = False

    # ==========================================================
    # CURSES INITIALIZATION
    # ==========================================================

    def init_curses(self, stdscr):
        """Initializes curses parameters for optimal TUI experience."""
        self.stdscr = stdscr

        curses.curs_set(0)
        self.stdscr.nodelay(1)
        self.stdscr.keypad(1)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()

    def set_root(self, frame):
        """Sets the root Frame that contains all other widgets."""
        self.root_frame = frame
        self.root_frame.app = self

    # ==========================================================
    # THREAD / UI OWNERSHIP
    # ==========================================================

    def is_ui_thread(self):
        """
        Return True if called from the thread currently owning
        the TUI.
        """
        return (
            self._ui_thread_id is not None
            and threading.get_ident() == self._ui_thread_id
        )

    # ==========================================================
    # TEMPORARY BACKGROUND ENGINE
    # ==========================================================

    def start_background_loop(self, handle_input=False):
        """
        Temporarily transfers TUI ownership to a background thread.

        The foreground loop remains alive but waits while the
        background thread owns the curses screen.
        """
        if not self.running:
            return

        if not self.root_frame:
            raise ValueError(
                "Call set_root() and start() before"
            )

        # Do not start another background loop.
        if self.background_running:
            return

        self.ignore_input = not handle_input

        # Prepare lifecycle events.
        self._background_stop.clear()
        self._background_finished.clear()

        self.background_running = True

        self._tui_thread = threading.Thread(
            target=self._run_background_loop,
            daemon=True,
        )

        self._tui_thread.start()

    def _run_background_loop(self):
        """
        Execute the TUI loop temporarily in a background thread.

        This thread becomes the owner of curses/UI operations until
        stop_background_loop() is called.
        """
        self._ui_thread_id = threading.get_ident()

        try:
            while (
                not self._background_stop.is_set()
                and self.running
            ):
                loop_start = time.monotonic()

                # Consume a previous wake-up before processing
                # the current frame.
                self._ui_wakeup.clear()

                self.loop()

                elapsed = time.monotonic() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )

        finally:
            # The background thread no longer owns the UI.
            self.background_running = False

            # Only the owning thread should clear its ownership.
            if self._ui_thread_id == threading.get_ident():
                self._ui_thread_id = None

            # Tell the foreground thread that ownership has returned.
            self._background_finished.set()

    def stop_background_loop(self):
        """
        Stop the temporary background TUI thread.

        This method is safe to call from another thread and will
        wake the background loop immediately if it is sleeping.
        """
        thread = self._tui_thread

        if thread is None:
            return

        # Tell the background thread to stop.
        self._background_stop.set()

        # IMPORTANT:
        #
        # The background thread may currently be blocked inside:
        #
        #     self._ui_wakeup.wait(...)
        #
        # Wake it immediately.
        self._ui_wakeup.set()

        # Never join the current thread.
        if thread is not threading.current_thread():
            thread.join()

        # The thread has now stopped.
        if not thread.is_alive():
            self._tui_thread = None

        self.ignore_input = False

    # ==========================================================
    # UI QUEUE
    # ==========================================================

    def flush(self):
        """
        Wait until all UI operations queued before this call
        have been processed.

        If called from the UI thread, process the queue immediately.
        """
        if self.is_ui_thread():
            self._flush_queue()
            return

        done = threading.Event()

        def barrier():
            done.set()

        self._ui_queue.put(barrier)

        # Wake whichever thread currently owns the TUI.
        self._ui_wakeup.set()

        done.wait()

    def _flush_queue(self):
        """
        Process everything currently pending in the UI queue.

        Must only be called by the UI thread.
        """
        while True:
            try:
                func = self._ui_queue.get_nowait()
            except queue.Empty:
                break

            func()

    # ==========================================================
    # FOREGROUND MAIN LOOP
    # ==========================================================

    def start(self):
        """
        Starts the main TUI loop in the foreground (blocking).
        """
        if not self.root_frame:
            raise ValueError(
                "Cannot start TUIApp without a root frame. "
                "Call set_root() first."
            )

        curses.wrapper(self._run)

    def _run(self, stdscr):
        """
        The main internal event loop.

        The foreground thread temporarily stops executing UI frames
        while the background TUI thread owns the curses screen.
        """
        self._ui_thread_id = threading.get_ident()

        try:
            self.init_curses(stdscr)
            self.running = True

            # Initial layout calculation.
            self.root_frame._resize_to_terminal(self.stdscr)

            while self.running:

                # ==================================================
                # BACKGROUND TUI OWNS THE SCREEN
                # ==================================================

                if self.background_running:
                    # The foreground thread must not touch curses
                    # while the background thread is the owner.
                    self._background_finished.wait()

                    if not self.running:
                        break

                    # Ownership is now returned to this thread.
                    self._ui_thread_id = threading.get_ident()

                    # The background thread may have finished but
                    # its Thread object still exists.
                    if (
                        self._tui_thread is not None
                        and not self._tui_thread.is_alive()
                    ):
                        self._tui_thread = None

                    continue

                # ==================================================
                # CLEAN UP FINISHED BACKGROUND THREAD
                # ==================================================

                if self._tui_thread is not None:
                    self._tui_thread.join()
                    self._tui_thread = None

                    self._ui_thread_id = threading.get_ident()

                    continue

                # ==================================================
                # NORMAL FOREGROUND FRAME
                # ==================================================

                loop_start = time.monotonic()

                # Consume any previous wake-up before starting
                # this frame.
                self._ui_wakeup.clear()

                self.loop()

                elapsed = time.monotonic() - loop_start

                if elapsed < self._frame_time:
                    self._ui_wakeup.wait(
                        self._frame_time - elapsed
                    )

        finally:
            self._ui_thread_id = None

    # ==========================================================
    # ONE UI FRAME
    # ==========================================================

    def loop(self):
        """Perform one complete update/render cycle."""

        # Process thread-safe structural updates first.
        self._flush_queue()

        self._handle_input()
        self._update()
        self._render()
        print(self.ignore_input)

    # ==========================================================
    # INPUT
    # ==========================================================

    def _handle_input(self):
        """
        Fetch input and pass it to the root frame for event bubbling.
        """
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
        """Checks for terminal resize events and updates layout."""
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

            # Resize root frame to fit terminal.
            if self.root_frame:
                self.root_frame._resize_to_terminal(
                    self.stdscr
                )

            # User-provided resize handler.
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
        """Executes a flicker-free render cycle."""
        self.stdscr.erase()
        self.stdscr.noutrefresh()

        self.root_frame.render()

        curses.doupdate()

    # ==========================================================
    # APPLICATION LIFECYCLE
    # ==========================================================

    def quit(self):
        """
        Signals the application to terminate.

        All sleeping loops are explicitly woken so shutdown does
        not have to wait for the next frame timeout.
        """
        self.running = False

        # Stop a background loop if one exists.
        self._background_stop.set()

        # Wake whichever loop is currently sleeping.
        self._ui_wakeup.set()

        self.stop_background_loop()

    # ==========================================================
    # EXTERNAL TUI HANDOFF
    # ==========================================================

    @contextlib.contextmanager
    def suspend_for_handoff(self):
        """
        Context manager to hand off the terminal to an external TUI app.
        """
        curses.def_prog_mode()
        curses.endwin()

        try:
            yield

        finally:
            self.stdscr.clear()
            curses.reset_prog_mode()
            self.stdscr.refresh()
