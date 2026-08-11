"""
mini_canvas - A zero-dependency ANSI Terminal Buffer & Rendering Engine.
Supports TrueColor (RGB), fallback modes, text modifiers, and double-buffering.
"""

import os
import sys
import shutil
import time
from typing import Optional, Tuple, List, Union


# =============================================================================
# MODIFIERS & CAPABILITIES
# =============================================================================

class Style:
    NONE = 0
    BOLD = 1 << 0
    DIM = 1 << 1
    ITALIC = 1 << 2
    UNDERLINE = 1 << 3
    BLINK = 1 << 4
    REVERSE = 1 << 5
    STRIKE = 1 << 6


class TerminalCaps:
    """Detects terminal rendering capabilities."""

    def __init__(self):
        colorterm = os.environ.get("COLORTERM", "").lower()
        term = os.environ.get("TERM", "").lower()
        no_color = "NO_COLOR" in os.environ

        # TrueColor (24-bit) detection
        self.has_truecolor = not no_color and (
            colorterm in ("truecolor", "24bit")
            or "direct" in term
            or os.environ.get("TERM_PROGRAM") in ("iTerm.app", "WezTerm", "kitty", "Alacritty")
            or "VSCODE_GIT_IPC_HANDLE" in os.environ
        )

        # 256-Color detection
        self.has_256color = not no_color and (
            self.has_truecolor or "256color" in term or "256" in term
        )

        # Basic Modifiers (Supported on virtually all modern TTYs)
        self.has_modifiers = not os.environ.get("ANSI_COLORS_DISABLED")
        self.has_italic = self.has_modifiers and ("xterm" in term or "vt100" in term or self.has_truecolor)


# =============================================================================
# COLOR CONVERSION & FALLBACKS
# =============================================================================

RGB = Tuple[int, int, int]

def rgb_to_256(r: int, g: int, b: int) -> int:
    """Converts 24-bit RGB to the closest standard 256-color palette index."""
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return round(((r - 8) / 247) * 23) + 232
    return 16 + (36 * round(r / 255 * 5)) + (6 * round(g / 255 * 5)) + round(b / 255 * 5)


def format_style_ansi(
    fg: Optional[Union[RGB, int]] = None,
    bg: Optional[Union[RGB, int]] = None,
    style: int = Style.NONE,
    caps: Optional[TerminalCaps] = None
) -> str:
    """Generates an ANSI escape string for given styling based on terminal capabilities."""
    if caps is None:
        caps = TerminalCaps()

    codes: List[str] = []

    # Apply Modifiers
    if caps.has_modifiers and style:
        if style & Style.BOLD: codes.append("1")
        if style & Style.DIM: codes.append("2")
        if style & Style.ITALIC and caps.has_italic: codes.append("3")
        if style & Style.UNDERLINE: codes.append("4")
        if style & Style.BLINK: codes.append("5")
        if style & Style.REVERSE: codes.append("7")
        if style & Style.STRIKE: codes.append("9")

    # Apply Foreground
    if fg is not None:
        if isinstance(fg, tuple) and len(fg) == 3:
            if caps.has_truecolor:
                codes.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}")
            elif caps.has_256color:
                codes.append(f"38;5;{rgb_to_256(*fg)}")
        elif isinstance(fg, int):
            codes.append(f"38;5;{fg}")

    # Apply Background
    if bg is not None:
        if isinstance(bg, tuple) and len(bg) == 3:
            if caps.has_truecolor:
                codes.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}")
            elif caps.has_256color:
                codes.append(f"48;5;{rgb_to_256(*bg)}")
        elif isinstance(bg, int):
            codes.append(f"48;5;{bg}")

    return f"\x1b[{';'.join(codes)}m" if codes else ""


# =============================================================================
# CANVAS BUFFER & RENDERER
# =============================================================================

class Cell:
    __slots__ = ("char", "fg", "bg", "style")

    def __init__(self, char: str = " ", fg=None, bg=None, style: int = Style.NONE):
        self.char = char
        self.fg = fg
        self.bg = bg
        self.style = style

    def copy_from(self, other: "Cell"):
        self.char = other.char
        self.fg = other.fg
        self.bg = other.bg
        self.style = other.style


class TerminalCanvas:
    """A high-performance, double-buffered ANSI canvas."""

    def __init__(self, width: Optional[int] = None, height: Optional[int] = None):
        self.caps = TerminalCaps()
        w, h = shutil.get_terminal_size((80, 24))
        self.width = width or w
        self.height = height or h

        self._back_buffer = [[Cell() for _ in range(self.width)] for _ in range(self.height)]
        self._front_buffer = [[Cell() for _ in range(self.width)] for _ in range(self.height)]

    def resize(self, width: int, height: int):
        """Resizes canvas buffers dynamically."""
        self.width = width
        self.height = height
        self._back_buffer = [[Cell() for _ in range(width)] for _ in range(height)]
        self._front_buffer = [[Cell() for _ in range(width)] for _ in range(height)]

    def auto_resize(self):
        """Syncs canvas dimensions with terminal window size."""
        w, h = shutil.get_terminal_size()
        if w != self.width or h != self.height:
            self.resize(w, h)

    def clear(self):
        """Clears the back buffer."""
        for y in range(self.height):
            for x in range(self.width):
                c = self._back_buffer[y][x]
                c.char = " "
                c.fg = None
                c.bg = None
                c.style = Style.NONE

    def put_char(self, x: int, y: int, char: str, fg=None, bg=None, style: int = Style.NONE):
        """Draws a single character at (x, y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            c = self._back_buffer[y][x]
            c.char = char[0] if char else " "
            c.fg = fg
            c.bg = bg
            c.style = style

    def put_str(self, x: int, y: int, text: str, fg=None, bg=None, style: int = Style.NONE):
        """Draws a string starting at (x, y)."""
        if y < 0 or y >= self.height:
            return
        for i, char in enumerate(text):
            px = x + i
            if px >= self.width:
                break
            if px >= 0:
                c = self._back_buffer[y][px]
                c.char = char
                c.fg = fg
                c.bg = bg
                c.style = style

    def render(self):
        """Flushes changed cells in the back buffer to stdout using ANSI sequences."""
        out = []
        last_key = None

        for y in range(self.height):
            # Move cursor to row start (1-indexed ANSI coordinates)
            out.append(f"\x1b[{y + 1};1H")
            
            for x in range(self.width):
                b = self._back_buffer[y][x]
                f = self._front_buffer[y][x]

                # Update front buffer state
                f.copy_from(b)

                # Batch identical style escape sequences to save bandwidth
                key = (b.fg, b.bg, b.style)
                if key != last_key:
                    out.append("\x1b[0m")  # Reset formatting
                    ansi_code = format_style_ansi(b.fg, b.bg, b.style, self.caps)
                    if ansi_code:
                        out.append(ansi_code)
                    last_key = key

                out.append(b.char)

        out.append("\x1b[0m")  # Final style reset
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # --- Screen Buffer Management ---

    @staticmethod
    def enter_alternate_screen():
        """Switches to the alternate screen buffer and hides cursor."""
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
        sys.stdout.flush()

    @staticmethod
    def exit_alternate_screen():
        """Restores the main screen buffer and shows cursor."""
        sys.stdout.write("\x1b[?1049l\x1b[?25h")
        sys.stdout.flush()


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    canvas = TerminalCanvas()

    print(f"Detected Capabilities:")
    print(f" - TrueColor (24-bit): {canvas.caps.has_truecolor}")
    print(f" - 256 Colors:         {canvas.caps.has_256color}")
    print(f" - Modifiers:          {canvas.caps.has_modifiers}")
    time.sleep(1.5)

    try:
        canvas.enter_alternate_screen()

        for frame in range(100):
            canvas.auto_resize()
            canvas.clear()

            # Render TrueColor Gradient Bar
            for x in range(min(50, canvas.width - 4)):
                r = int((x / 50) * 255)
                g = int((1 - x / 50) * 255)
                b = 150
                canvas.put_char(x + 2, 2, "█", fg=(r, g, b))

            canvas.put_str(2, 1, "=== RGB TrueColor Gradient ===", style=Style.BOLD)

            # Render Text Modifiers Showcase
            canvas.put_str(2, 5, "Bold Text", fg=(255, 100, 100), style=Style.BOLD)
            canvas.put_str(2, 6, "Dimmed Text", fg=(200, 200, 200), style=Style.DIM)
            canvas.put_str(2, 7, "Italic Text", fg=(100, 255, 100), style=Style.ITALIC)
            canvas.put_str(2, 8, "Underlined Text", fg=(100, 100, 255), style=Style.UNDERLINE)
            canvas.put_str(2, 9, "Reversed Text", fg=(255, 255, 0), bg=(50, 50, 50), style=Style.REVERSE)
            canvas.put_str(2, 10, "Strikethrough Text", fg=(255, 0, 255), style=Style.STRIKE)

            # Animated Spinner
            spinner = ["|", "/", "-", "\\"][frame % 4]
            canvas.put_str(2, 13, f"Rendering Frame {frame} {spinner}", fg=(0, 255, 255), style=Style.BOLD)

            canvas.render()
            time.sleep(0.03)

    finally:
        canvas.exit_alternate_screen()

