"""
tuia.app - Core engine and lifecycle management for the TUI (gleaf Backend).
"""

import contextlib
import logging
import queue
import sys
import termios
import threading
import time
from collections.abc import Callable
from typing import Any

from gleaf import managed_canvas
from oakey import KeyListener

from tuia.constants import Keys
from tuia.window import Window


@contextlib.contextmanager
def tuia_app_context(log_file="tuia.log"):
    """
    Redirects standard output and standard error to a log file safely.
    Proxies essential I/O methods so terminal stream attributes remain intact.
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    with open(log_file, "a", encoding="utf-8") as log_f:

        class LogWriter:
            def __init__(self, target):
                self._target = target

            def write(self, s):
                return log_f.write(s)

            def flush(self):
                log_f.flush()

            def isatty(self):
                return getattr(self._target, "isatty", lambda: False)()

            def fileno(self):
                return getattr(self._target, "fileno", lambda: 1)()

            @property
            def encoding(self):
                return getattr(self._target, "encoding", "utf-8")

        sys.stdout = LogWriter(original_stdout)
        sys.stderr = LogWriter(original_stderr)

        try:
            yield
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr


class TUIApp:
    """
    The main application engine for the TUI via gleaf.
    """

    LOG = logging.getLogger("tuia")

    def __init__(
        self,
        fps_target: int = 60,
        on_resize=None,
        log_file: str = "tuia.log",
        backend: str = "auto",
    ):
        self._setup_logger(log_file)

        self.stdscr: Window | None = None
        self.running = False
        self.root_frame = None
        self._backend = backend

        self._fps_target = fps_target
        self._frame_time = 1.0 / fps_target

        self.on_resize = on_resize
        self.key_listener = KeyListener()
        self._input_queue: queue.Queue | None = None
        self._resize_flag = False

        self._ui_queue = queue.Queue()
        self._ui_wakeup = threading.Event()
        self._ui_thread_id = None

        self._tui_thread = None
        self.background_running = False
        self._background_stop = threading.Event()
        self._background_finished = threading.Event()
        self._background_finished.set()

        self.ignore_input = False

    @classmethod
    def _setup_logger(cls, log_file: str):
        if not cls.LOG.handlers:
            cls.LOG.setLevel(logging.DEBUG)
            handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            formatter = logging.Formatter(
                "[%(asctime)s][%(threadName)s][%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
            handler.setFormatter(formatter)
            cls.LOG.addHandler(handler)
            cls.LOG.info("=== TUIA Engine Logging Started ===")

    def set_root(self, frame):
        self.root_frame = frame
        self.root_frame.app = self

    # ==========================================================
    # MAIN THREAD MARSHALLING
    # ==========================================================

    def _run_on_main_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Schedules a function to run on the primary UI thread."""
        if self.is_ui_thread():
            return func(*args, **kwargs)

        done = threading.Event()
        result = []
        exception = []

        def _target():
            try:
                result.append(func(*args, **kwargs))
            except Exception as exc:
                exception.append(exc)
            finally:
                done.set()

        self._ui_queue.put(_target)
        self._ui_wakeup.set()
        done.wait()

        if exception:
            raise exception[0]

        return result[0] if result else None

    # ==========================================================
    # UI THREAD OWNERSHIP & BACKGROUND LOOP
    # ==========================================================

    def is_ui_thread(self) -> bool:
        return (
            self._ui_thread_id is not None
            and threading.get_ident() == self._ui_thread_id
        )

    def start_background_loop(self, handle_input: bool = False):
        if not self.running or not self.root_frame or self.background_running:
            return

        self.LOG.info("Starting background UI loop thread...")
        self.ignore_input = not handle_input

        self._background_stop.clear()
        self._background_finished.clear()
        self.background_running = True

        self._tui_thread = threading.Thread(
            target=self._run_background_loop, daemon=True, name="TUI-background"
        )
        self._tui_thread.start()

    def _run_background_loop(self):
        self._ui_thread_id = threading.get_ident()
        raise_error = None
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
        except BaseException as e:

            def raise_error(error: BaseException = e):
                raise error

        finally:
            self.background_running = False
            self.ignore_input = False
            if self._ui_thread_id == threading.get_ident():
                self._ui_thread_id = None
            self._background_finished.set()
            if raise_error:
                self._run_on_main_thread(raise_error)
            self._ui_wakeup.set()

    def stop_background_loop(self):
        thread = self._tui_thread
        if thread is None:
            self.background_running = False
            self.ignore_input = False
            return

        self._background_stop.set()
        self._ui_wakeup.set()

        if thread is not threading.current_thread():
            self._background_finished.wait()
            thread.join()

        if self._tui_thread is thread:
            self._tui_thread = None

        self.background_running = False
        self.ignore_input = False
        if self.running:
            self._ui_thread_id = threading.get_ident()

    def flush(self):
        if self.is_ui_thread():
            self._flush_queue()
            return

        done = threading.Event()
        self._ui_queue.put(done.set)
        self._ui_wakeup.set()
        done.wait()

    def _flush_queue(self):
        while True:
            try:
                func = self._ui_queue.get_nowait()
                func()
            except queue.Empty:
                break
            except Exception as e:
                self.LOG.exception(f"Exception during queued UI operation: {e}")

    # ==========================================================
    # MAIN ENTRY POINT & INPUT POLLING
    # ==========================================================

    def start(self):
        """Starts the main TUI loop, delegating rendering to gleaf."""
        if not self.root_frame:
            raise ValueError("Call set_root() first.")

        self.LOG.info("Launching TUIApp via gleaf engine...")
        self.stdscr = Window(self, backend=self._backend)
        self.LOG.info(f"Loaded {type(self.stdscr.canvas).__name__} backend")

        # managed_canvas safely initializes termios settings and alternate screen
        with managed_canvas(self.stdscr.canvas), self.key_listener:
            # Block main thread with the UI Enginee
            self._input_queue = self.key_listener.queue
            self.LOG.debug(
                f"input listener running: {self.key_listener.is_running()} paused: {self.key_listener.is_paused()}"
            )
            self._run_engine()

        self.LOG.info("TUIApp session ended.")

    # ==========================================================
    # FOREGROUND LOOP
    # ==========================================================

    def _run_engine(self):
        self._ui_thread_id = threading.get_ident()
        try:
            self.running = True

            if self.root_frame and self.stdscr:
                self.stdscr.canvas.auto_resize()
                max_y, max_x = self.stdscr.getmaxyx()
                self.root_frame._resize_to_terminal(self.stdscr)

            while self.running:
                if self.background_running:
                    self._background_finished.wait()
                    if not self.running:
                        break
                    self._ui_thread_id = threading.get_ident()
                    if self._tui_thread is not None and not self._tui_thread.is_alive():
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

    def loop(self):
        self._flush_queue()
        self._handle_input()
        self._update()
        self._render()

    # ==========================================================
    # INPUT, UPDATE, RENDER
    # ==========================================================

    def _handle_input(self):
        while not self._input_queue.empty():
            try:
                raw_key = self._input_queue.get_nowait()
                if raw_key == Keys.CTRL_C:
                    raise KeyboardInterrupt
                if self.ignore_input:
                    continue
                if self.root_frame:
                    self.root_frame.handle_event(raw_key)
            except queue.Empty:
                break

    def _update(self):
        if self.stdscr:
            old_h, old_w = self.stdscr.getmaxyx()
            self.stdscr.canvas.auto_resize()  # Let gleaf check dimensions
            new_h, new_w = self.stdscr.getmaxyx()

            if new_w != old_w or new_h != old_h:
                self.LOG.info(
                    f"Terminal resize detected ({old_w}x{old_h} -> {new_w}x{new_h})"
                )
                self._resize_flag = True

        if self._resize_flag:
            self._resize_flag = False
            if self.stdscr:
                if self.root_frame:
                    self.root_frame._resize_to_terminal(self.stdscr)
                if callable(self.on_resize):
                    max_y, max_x = self.stdscr.getmaxyx()
                    self.on_resize(self, max_x, max_y)

    def _render(self):
        if not self.stdscr or not self.root_frame:
            return
        self.stdscr.erase()
        self.root_frame.render()
        self.stdscr.doupdate()

    def clear(self):
        if self.stdscr:
            self.stdscr.clear()

    # ==========================================================
    # QUIT & EXTERNAL HANDOFF
    # ==========================================================

    def quit(self):
        self.LOG.info("Shutdown requested via app.quit()")
        self.running = False
        self._background_stop.set()
        self._ui_wakeup.set()

    # @contextlib.contextmanager
    # def suspend_for_handoff(self, clear_on_resume: bool = False):
    #     """Temporarily yields the terminal to external subprocesses."""
    #     self.LOG.info("Suspending TUIApp for external handoff...")

    #     if self.stdscr and hasattr(self.stdscr.canvas, 'exit_alternate_screen'):
    #         self._run_on_main_thread(self.stdscr.canvas.exit_alternate_screen)

    #     original_stdout = sys.stdout
    #     original_stderr = sys.stderr
    #     sys.stdout = sys.__stdout__
    #     sys.stderr = sys.__stderr__

    #     sys.stdout.flush()
    #     sys.stderr.flush()

    #     try:
    #         yield
    #     finally:
    #         sys.stdout.flush()
    #         sys.stderr.flush()

    #         if clear_on_resume:
    #             sys.stdout.write("\033[2J\033[3J\033[H")
    #             sys.stdout.flush()

    #         sys.stdout = original_stdout
    #         sys.stderr = original_stderr

    #         self.LOG.info("Resuming TUIApp after handoff. Restoring screen...")
    #         if self.stdscr and hasattr(self.stdscr.canvas, 'enter_alternate_screen'):
    #             self._run_on_main_thread(
    #                 self.stdscr.canvas.enter_alternate_screen)

    #         if self.stdscr:
    #             self.stdscr.force_full_repaint()
    #         if self.root_frame and self.stdscr:
    #             self._run_on_main_thread(
    #                 self.root_frame._resize_to_terminal, self.stdscr)

    #         self._ui_wakeup.set()
    #         self.loop()

    # @contextlib.contextmanager
    # def suspend_for_handoff(self, clear_on_resume: bool = False):
    #     """
    #     Temporarily yields the terminal to external subprocesses or print calls.
    #     Paues input polling and ensures stream buffers are flushed in strict sequence.
    #     """
    #     self.LOG.info("Suspending TUIApp for external handoff...")
    #     self.LOG.debug(f"input listener running: {self.key_listener.is_running()} paused: {self.key_listener.is_paused()}")

    #     sys.stdout.flush()
    #     sys.stderr.flush()
    #     sys.__stdout__.flush()
    #     sys.__stderr__.flush()

    #     original_stdout = sys.stdout
    #     original_stderr = sys.stderr
    #     sys.stdout = sys.__stdout__
    #     sys.stderr = sys.__stderr__

    #     if self.stdscr and hasattr(self.stdscr.canvas, 'exit_alternate_screen'):
    #         self.stdscr.canvas.exit_alternate_screen()

    #     sys.stdout.flush()

    #     try:
    #         with self.key_listener.handoff():
    #             self.LOG.debug(f"input listener running: {self.key_listener.is_running()} paused: {self.key_listener.is_paused()}")
    #             yield
    #     finally:
    #         sys.stdout.flush()
    #         sys.stderr.flush()

    #         if clear_on_resume:
    #             sys.stdout.write("\033[2J\033[3J\033[H")
    #             sys.stdout.flush()

    #         if self.stdscr and hasattr(self.stdscr.canvas, 'enter_alternate_screen'):
    #             self.stdscr.canvas.enter_alternate_screen()

    #         sys.stdout = original_stdout
    #         sys.stderr = original_stderr

    #         if self.stdscr:
    #             self.stdscr.force_full_repaint()
    #         if self.root_frame and self.stdscr:
    #             self.root_frame._resize_to_terminal(self.stdscr)

    #         self.LOG.debug(f"input listener running: {self.key_listener.is_running()} paused: {self.key_listener.is_paused()}")
    #         self._ui_wakeup.set()
    #         self.loop()

    @contextlib.contextmanager
    def suspend_for_handoff(self, clear_on_resume: bool = False):
        """
        Temporarily yields the terminal to external subprocesses or print calls.
        """
        self.LOG.info("Suspending TUIApp for external handoff...")
        self.LOG.debug(
            f"input listener running: {self.key_listener.is_running()} paused: {self.key_listener.is_paused()}"
        )

        # 1. Flush all output streams
        sys.stdout.flush()
        sys.stderr.flush()
        sys.__stdout__.flush()
        sys.__stderr__.flush()

        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        # 2. Pause the key listener first via its handoff context manager
        # with self.key_listener.handoff():
        if True:
            self.key_listener.stop()

            self.LOG.debug(
                f"input listener inside handoff running: {self.key_listener.is_running()} paused: {self.key_listener.is_paused()}"
            )

            # 3. Exit alternate screen (restores terminal cooked mode)
            if self.stdscr and hasattr(self.stdscr.canvas, "exit_alternate_screen"):
                self._run_on_main_thread(self.stdscr.canvas.exit_alternate_screen)

            sys.stdout.flush()

            # 4. CRITICAL: Purge the triggering hotkey from stdin so Yazi gets a completely clean stream
            try:
                termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
            except Exception as e:
                self.LOG.warning(f"Failed to flush stdin buffer: {e}")

            try:
                yield
            finally:
                sys.stdout.flush()
                sys.stderr.flush()

                if clear_on_resume:
                    sys.stdout.write("\033[2J\033[3J\033[H")
                    sys.stdout.flush()

                # 5. Re-enter alternate screen before key listener resumes
                if self.stdscr and hasattr(
                    self.stdscr.canvas, "enter_alternate_screen"
                ):
                    self._run_on_main_thread(self.stdscr.canvas.enter_alternate_screen)

        self.key_listener.start()

        # 6. Restore original log redirects
        sys.stdout = original_stdout
        sys.stderr = original_stderr

        if self.stdscr:
            self.stdscr.force_full_repaint()
        if self.root_frame and self.stdscr:
            self._run_on_main_thread(self.root_frame._resize_to_terminal, self.stdscr)

        self.LOG.debug(
            f"input listener after handoff running: {self.key_listener.is_running()} paused: {self.key_listener.is_paused()}"
        )
        self._ui_wakeup.set()
        self.loop()
        self.LOG.info("Resumed TUIApp after handoff.")
