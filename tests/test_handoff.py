#!/usr/bin/env python3
"""
Standalone Yazi Handoff Test Script
Simulates TUI alternate screen mode, cbreak input, and safe handoff to Yazi.
"""

import sys
import os
import subprocess
import termios
import tty
import contextlib
import time

@contextlib.contextmanager
def tui_simulation():
    """Simulates starting the gleaf/Tuia TUI engine environment."""
    print("Initializing TUI simulation...")
    
    # 1. Enter alternate screen and hide cursor
    sys.__stdout__.write("\033[?1049h\033[H\033[2J\033[?25l")
    sys.__stdout__.flush()
    
    # 2. Set terminal to cbreak mode (mimicking key listener)
    old_term = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    
    # Clear screen area for our mock UI text
    sys.stdout.write("\033[1;1H=== TUI SIMULATION RUNNING ===\r\n")
    sys.stdout.write("Press [y] to handoff to Yazi.\r\n")
    sys.stdout.write("Press [q] to quit simulation.\r\n")
    sys.stdout.flush()
    
    try:
        yield old_term
    finally:
        # 3. Teardown: Restore cooked mode and exit alternate screen
        termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, old_term)
        sys.__stdout__.write("\033[0m\033[?1049l\033[?25h")
        sys.__stdout__.flush()
        print("\nTUI Simulation cleanly exited.")

@contextlib.contextmanager
def safe_handoff(old_term):
    """Simulates suspend_for_handoff with stdin flushing and screen restoration."""
    # Flush outputs
    sys.stdout.flush()
    sys.stderr.flush()
    
    # Exit alternate screen & restore cooked terminal settings temporarily
    sys.__stdout__.write("\033[0m\033[?1049l\033[?25h")
    sys.__stdout__.flush()
    termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, old_term)
    
    # CRITICAL FIX: Purge the 'y' keystroke from stdin buffer so Yazi doesn't eat it
    try:
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception as e:
        print(f"Flush error: {e}", file=sys.stderr)
        
    try:
        yield
    finally:
        # Restore alternate screen & cbreak mode
        sys.__stdout__.write("\033[?1049h\033[H\033[2J\033[?25l")
        sys.__stdout__.flush()
        tty.setcbreak(sys.stdin.fileno())

def main():
    with tui_simulation() as old_term:
        while True:
            # Read single keypress in cbreak mode
            char = sys.stdin.read(1)
            
            if char == 'q':
                break
            elif char == 'y':
                with safe_handoff(old_term):
                    # Launch Yazi directly on the real terminal
                    subprocess.run(["yazi"])
                
                # Redraw mock UI after returning from Yazi
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write("=== RETURNED FROM YAZI ===\r\n")
                sys.stdout.write("Press [y] to launch Yazi again, or [q] to quit.\r\n")
                sys.stdout.flush()

if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("Error: Must be run directly inside an interactive terminal.")
        sys.exit(1)
    main()
