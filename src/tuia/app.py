"""
tuia.app - Core engine and lifecycle management for the TUI (Textual Backend).
"""

import contextlib
import logging
import queue
import threading
import time
from typing import Optional, Callable, Any

from tuia.backend import TextualBridgeApp, Window


# =============================================================================
# MAIN TUIA APPLICATION ENGINE
# =============================================================================

import sys


@contextlib.contextmanager
def tuia_app_context(log_file="tuia.log"):
    """
    Redirects standard output and standard error to a log file.
    Because Tuia engine components write directly to sys.__stdout__, 
    the UI will render perfectly while all normal print() calls are logged.
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    with open(log_file, "a", encoding="utf-8") as log_f:
        class LogWriter:
            def write(self, s):
                log_f.write(s)
            def flush(self):
                log_f.flush()
                
        redirector = LogWriter()
        sys.stdout = redirector
        sys.stderr = redirector
        
        try:
            yield
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

class TUIApp:
    """
    The main application engine for the TUI.

    Manages:
        - Local file logging via `TUIApp.LOG`
        - High-performance 2D double-buffered rendering
        - Instantaneous event wakeup & raw input dispatching
        - Auto-polled responsive resizing
        - Thread-safe CLI/TUI external handoff & restoration
        - Clean multi-threaded shutdown
    """

    LOG = logging.getLogger("tuia")

    def __init__(self, fps_target: int = 60, on_resize=None, log_file: str = "tuia.log"):
        self._setup_logger(log_file)

        self.stdscr: Optional[Window] = None
        self.running = False
        self.root_frame = None

        self._fps_target = fps_target
        self._frame_time = 1.0 / fps_target

        self.on_resize = on_resize
        self._textual_app: Optional[TextualBridgeApp] = None
        self._input_queue = queue.Queue()
        self._resize_flag = False

        # UI Queue & Wakeup Signal
        self._ui_queue = queue.Queue()
        self._ui_wakeup = threading.Event()
        self._ui_thread_id = None

        # Background UI Engine
        self._tui_thread = None
        self.background_running = False
        self._background_stop = threading.Event()
        self._background_finished = threading.Event()
        self._background_finished.set()

        self.ignore_input = False

    @classmethod
    def _setup_logger(cls, log_file: str):
        """Initializes logging to a local file if not already configured."""
        if not cls.LOG.handlers:
            cls.LOG.setLevel(logging.DEBUG)
            handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            formatter = logging.Formatter(
                "[%(asctime)s][%(threadName)s][%(levelname)s] %(message)s",
                datefmt="%H:%M:%S"
            )
            handler.setFormatter(formatter)
            cls.LOG.addHandler(handler)
            cls.LOG.info("=== TUIA Engine Logging Started ===")

    def set_root(self, frame):
        """Set the root Frame."""
        self.root_frame = frame
        self.root_frame.app = self

    # ==========================================================
    # MAIN THREAD MARSHALLING
    # ==========================================================

    def _run_on_main_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Executes a function synchronously on Textual's MainThread."""
        if threading.current_thread() is threading.main_thread():
            return func(*args, **kwargs)

        if not self._textual_app:
            return func(*args, **kwargs)

        done = threading.Event()
        result = []
        exception = []

        def _target():
            try:
                res = func(*args, **kwargs)
                result.append(res)
            except Exception as exc:
                exception.append(exc)
            finally:
                done.set()

        try:
            self._textual_app.call_from_thread(_target)
            done.wait()
        except RuntimeError as err:
            self.LOG.warning(
                f"Could not schedule on main thread ({err}); calling directly.")
            return func(*args, **kwargs)

        if exception:
            raise exception[0]

        return result[0] if result else None

    # ==========================================================
    # UI THREAD OWNERSHIP
    # ==========================================================

    def is_ui_thread(self) -> bool:
        """Return True if the current thread owns the TUI loop."""
        return (
            self._ui_thread_id is not None
            and threading.get_ident() == self._ui_thread_id
        )

    # ==========================================================
    # BACKGROUND LOOP
    # ==========================================================

    def start_background_loop(self, handle_input: bool = False):
        """Temporarily transfer TUI ownership to a background thread."""
        if not self.running:
            return

        if not self.root_frame:
            raise ValueError(
                "Call set_root() and start() before running background loop.")

        if self.background_running:
            return

        self.LOG.info("Starting background UI loop thread...")
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
            self.LOG.info("Exiting background UI loop thread...")
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

        self.LOG.info("Stopping background UI loop thread...")
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
            try:
                func()
            except Exception as e:
                self.LOG.exception(
                    f"Exception during queued UI operation execution: {e}")

    # ==========================================================
    # MAIN ENTRY POINT
    # ==========================================================

    def start(self):
        """Start the main TUI loop via Textual backend."""
        if not self.root_frame:
            raise ValueError(
                "Cannot start TUIApp without a root frame. Call set_root() first."
            )

        self.LOG.info("Launching TUIApp via Textual backend...")
        self._textual_app = TextualBridgeApp(self)
        self._textual_app.run()
        self.LOG.info("TUIApp session ended.")

    # ==========================================================
    # FOREGROUND LOOP
    # ==========================================================

    def _run_engine(self):
        """Main foreground TUI loop running on Textual worker thread."""
        self._ui_thread_id = threading.get_ident()

        try:
            self.running = True

            if self.root_frame and self.stdscr:
                max_y, max_x = self.stdscr.getmaxyx()
                if max_x == 0 or max_y == 0:
                    if self._textual_app and self._textual_app.console:
                        max_x, max_y = self._textual_app.console.size
                    if max_x == 0 or max_y == 0:
                        max_x, max_y = 80, 24
                self.stdscr.resize_buffers(max_x, max_y)
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

        except Exception as e:
            self.LOG.exception(f"Fatal exception in TUI engine thread: {e}")
        finally:
            self.LOG.info("Engine thread shutting down...")
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
        """Fetch and dispatch raw input events from queue."""
        while not self._input_queue.empty():
            try:
                raw_key = self._input_queue.get_nowait()
                if self.ignore_input:
                    self.LOG.debug(
                        f"[Input] Dropped key (ignore_input=True): {raw_key!r}")
                    continue

                self.LOG.debug(
                    f"[Input] Dispatching key to root_frame: {raw_key!r}")
                if self.root_frame:
                    self.root_frame.handle_event(raw_key)
            except queue.Empty:
                break

    # ==========================================================
    # FOREGROUND LOOP
    # ==========================================================

    def _run_engine(self):
        """Main foreground TUI loop running on Textual worker thread."""
        self._ui_thread_id = threading.get_ident()

        try:
            self.running = True

            if self.root_frame and self.stdscr:
                max_y, max_x = self.stdscr.getmaxyx()
                if max_x == 0 or max_y == 0:
                    if self._textual_app and self._textual_app.console:
                        max_x, max_y = self._textual_app.console.size
                    if max_x == 0 or max_y == 0:
                        max_x, max_y = 80, 24
                self.stdscr.resize_buffers(max_x, max_y)
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

        except Exception as e:
            self.LOG.exception(f"Fatal exception in TUI engine thread: {e}")
        finally:
            self.LOG.info("Engine thread shutting down...")
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
    # UPDATE
    # ==========================================================

    def _update(self):
        """Handle terminal layout recalculations after window resize."""
        if self.stdscr:
            w, h = self.stdscr.size.width, self.stdscr.size.height
            if (w == 0 or h == 0) and self._textual_app and self._textual_app.console:
                w, h = self._textual_app.console.size

            if w > 0 and h > 0:
                curr_h, curr_w = self.stdscr.getmaxyx()
                if w != curr_w or h != curr_h:
                    self.LOG.info(f"Terminal resize detected ({
                                  curr_w}x{curr_h} -> {w}x{h})")
                    self.stdscr.resize_buffers(w, h)
                    self._resize_flag = True

        if self._resize_flag:
            self._resize_flag = False

            if self.stdscr:
                max_y, max_x = self.stdscr.getmaxyx()
                self.LOG.info(f"Layout resized to {max_x}x{max_y}")

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
        """Request application shutdown cleanly across threads."""
        self.LOG.info("Shutdown requested via app.quit()")
        self.running = False
        self._background_stop.set()
        self._ui_wakeup.set()

        if self._textual_app:
            try:
                self._textual_app.call_from_thread(self._textual_app.exit)
            except RuntimeError:
                self._textual_app.exit()

    # ==========================================================
    # EXTERNAL TUI HANDOFF
    # ==========================================================

    @contextlib.contextmanager
    def suspend_for_handoff(self, clear_on_resume: bool = False):
        """
        Temporarily give the terminal to an external CLI/TUI program or script.

        Args:
            clear_on_resume (bool): 
                - If False (default): Keeps subprocess and print output on the main 
                  terminal screen/scrollback history after the TUI resumes and exits.
                - If True: Clears handoff prints/output from the main terminal buffer 
                  right before returning to the TUI screen.
        """
        import sys

        self.LOG.info("Suspending TUIApp for external handoff...")
        if self._textual_app and getattr(self._textual_app, "_driver", None):
            driver = self._textual_app._driver

            # Exit raw mode & restore standard terminal main buffer
            self._run_on_main_thread(driver.stop_application_mode)

            # Textual overrides sys.stdout. Restore the original TTY for prints.
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

            sys.stdout.flush()
            sys.stderr.flush()

            try:
                yield
            finally:
                sys.stdout.flush()
                sys.stderr.flush()

                if clear_on_resume:
                    # Clear screen (\033[2J), scrollback (\033[3J), and reset cursor (\033[H)
                    sys.stdout.write("\033[2J\033[3J\033[H")
                    sys.stdout.flush()

                # Restore Textual's stdout/stderr capture
                sys.stdout = original_stdout
                sys.stderr = original_stderr

                self.LOG.info(
                    "Resuming TUIApp after handoff. Restoring screen...")
                self._run_on_main_thread(driver.start_application_mode)

                if self.stdscr:
                    self.stdscr.force_full_repaint()
                if self.root_frame and self.stdscr:
                    self.root_frame._resize_to_terminal(self.stdscr)

                self._ui_wakeup.set()
                self.loop()
        else:
            yield

        self.LOG.info("Resumed TUIApp after handoff.")
