#!/usr/bin/env python3
"""
Test script for verifying Yazi handoff inside the actual TUIApp engine.
"""

import subprocess
import sys
from tuia.app import TUIApp, tuia_app_context

class HandoffTestFrame:
    """A minimal root frame for testing input events and subprocess handoffs."""
    def __init__(self):
        self.app = None

    def _resize_to_terminal(self, stdscr):
        # Called on resize or startup
        pass

    def handle_event(self, key):
        self.app.LOG.info(f"Received key event: {key!r}")
        
        if key == 'y':
            self.app.LOG.info("Triggering Yazi handoff...")
            # Use app.suspend_for_handoff to cleanly yield the terminal
            with self.app.suspend_for_handoff(clear_on_resume=True):
                subprocess.run(["yazi"])
            self.app.LOG.info("Returned from Yazi handoff.")
            
        elif key in ('q', '\x03', '\x11'):
            self.app.LOG.info("Quit requested.")
            self.app.quit()

    def render(self):
        if self.app and self.app.stdscr:
            # Draw a simple UI menu
            self.app.stdscr.addstr(0, 0, "=== TUIA YAZI HANDOFF TEST ===")
            self.app.stdscr.addstr(2, 0, "Press [y] to launch Yazi")
            self.app.stdscr.addstr(3, 0, "Press [q] to Quit")

def main():
    # Wrap execution in tuia_app_context to safely log debug statements
    with tuia_app_context("handoff_test.log"):
        app = TUIApp(fps_target=60, log_file="handoff_test.log")
        
        # NOTE: If your app requires app.key_listener to be explicitly assigned 
        # before starting, plug it in here:
        # from your_key_module import KeyListener
        # app.key_listener = KeyListener()
        
        root_frame = HandoffTestFrame()
        app.set_root(root_frame)
        
        app.LOG.info("Starting TUIApp Yazi test script...")
        try:
            app.start()
        except KeyboardInterrupt:
            app.quit()
        except Exception as e:
            app.LOG.exception(f"Test crashed with error: {e}")
            raise

    print("Test finished. Check handoff_test.log for logs.")

if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("Error: Must be run interactively inside a terminal.")
        sys.exit(1)
    main()
