"""
numpy_numba_canvas.py - Extreme High-Performance Terminal Canvas Engine.
Uses structured NumPy contiguous arrays, Numba parallel thread execution (prange),
and direct raw byte stream writing to sys.stdout.buffer.
"""

import os
import sys
import shutil
import time
import numpy as np
from numba import jit, prange


# =============================================================================
# DATA STRUCTURES & NUMPY DTYPE
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


# Structured 16-byte memory cell layout
CELL_DTYPE = np.dtype([
    ('char', np.uint32),    # Unicode code point
    ('fg_r', np.uint8),     # Red
    ('fg_g', np.uint8),     # Green
    ('fg_b', np.uint8),     # Blue
    ('has_fg', np.uint8),   # Boolean flag (0 or 1)
    ('bg_r', np.uint8),     # Red
    ('bg_g', np.uint8),     # Green
    ('bg_b', np.uint8),     # Blue
    ('has_bg', np.uint8),   # Boolean flag (0 or 1)
    ('style', np.uint8)     # Bitmask for text modifiers
])


# =============================================================================
# NUMBA PARALLEL ANSI BYTE GENERATOR
# =============================================================================

@jit(nopython=True)
def _append_int(buffer, offset, val):
    """Appends an integer as ASCII bytes directly into a raw uint8 array."""
    if val == 0:
        buffer[offset] = 48  # ASCII '0'
        return offset + 1
    
    # Extract digits backward
    temp = np.zeros(10, dtype=np.uint8)
    count = 0
    while val > 0:
        temp[count] = 48 + (val % 10)
        val //= 10
        count += 1
    
    # Write forward
    for i in range(count - 1, -1, -1):
        buffer[offset] = temp[i]
        offset += 1
    return offset


@jit(nopython=True, parallel=True)
def _render_lines_parallel(grid, height, width, line_buffers):
    """
    Renders every row in parallel across CPU cores using Numba prange.
    Writes ANSI escape sequences directly into pre-allocated uint8 byte buffers.
    """
    for y in prange(height):
        buf = line_buffers[y]
        pos = 0

        # Move cursor to row start: \x1b[{y+1};1H
        buf[pos] = 27; buf[pos+1] = 91; pos += 2  # ESC [
        pos = _append_int(buf, pos, y + 1)
        buf[pos] = 59; buf[pos+1] = 49; buf[pos+2] = 72; pos += 3  # ; 1 H

        last_style = np.uint8(255)
        last_fg_r, last_fg_g, last_fg_b, last_has_fg = np.uint8(0), np.uint8(0), np.uint8(0), np.uint8(0)
        last_bg_r, last_bg_g, last_bg_b, last_has_bg = np.uint8(0), np.uint8(0), np.uint8(0), np.uint8(0)

        for x in range(width):
            cell = grid[y, x]

            # Style/Color diff check
            style_changed = (cell['style'] != last_style or 
                             cell['has_fg'] != last_has_fg or 
                             cell['has_bg'] != last_has_bg or
                             (cell['has_fg'] and (cell['fg_r'] != last_fg_r or cell['fg_g'] != last_fg_g or cell['fg_b'] != last_fg_b)) or
                             (cell['has_bg'] and (cell['bg_r'] != last_bg_r or cell['bg_g'] != last_bg_g or cell['bg_b'] != last_bg_b)))

            if style_changed:
                # Reset formatting: \x1b[0m
                buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 48; buf[pos+3] = 109; pos += 4

                # Apply Modifiers
                st = cell['style']
                if st > 0:
                    if st & 1: buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 49; buf[pos+3] = 109; pos += 4  # Bold
                    if st & 2: buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 50; buf[pos+3] = 109; pos += 4  # Dim
                    if st & 4: buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 51; buf[pos+3] = 109; pos += 4  # Italic
                    if st & 8: buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 52; buf[pos+3] = 109; pos += 4  # Underline

                # Apply Foreground RGB: \x1b[38;2;R;G;Bm
                if cell['has_fg']:
                    buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 51; buf[pos+3] = 56; buf[pos+4] = 59; buf[pos+5] = 50; buf[pos+6] = 59; pos += 7
                    pos = _append_int(buf, pos, cell['fg_r']); buf[pos] = 59; pos += 1
                    pos = _append_int(buf, pos, cell['fg_g']); buf[pos] = 59; pos += 1
                    pos = _append_int(buf, pos, cell['fg_b']); buf[pos] = 109; pos += 1

                # Apply Background RGB: \x1b[48;2;R;G;Bm
                if cell['has_bg']:
                    buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 52; buf[pos+3] = 56; buf[pos+4] = 59; buf[pos+5] = 50; buf[pos+6] = 59; pos += 7
                    pos = _append_int(buf, pos, cell['bg_r']); buf[pos] = 59; pos += 1
                    pos = _append_int(buf, pos, cell['bg_g']); buf[pos] = 59; pos += 1
                    pos = _append_int(buf, pos, cell['bg_b']); buf[pos] = 109; pos += 1

                last_style = cell['style']
                last_has_fg, last_fg_r, last_fg_g, last_fg_b = cell['has_fg'], cell['fg_r'], cell['fg_g'], cell['fg_b']
                last_has_bg, last_bg_r, last_bg_g, last_bg_b = cell['has_bg'], cell['bg_r'], cell['bg_g'], cell['bg_b']

            # Append Character Byte (ASCII/UTF-8)
            ch = cell['char']
            if ch <= 127:
                buf[pos] = ch
                pos += 1
            else:
                # Basic UTF-8 Encoding
                if ch <= 0x7FF:
                    buf[pos] = 0xC0 | (ch >> 6)
                    buf[pos+1] = 0x80 | (ch & 0x3F)
                    pos += 2
                elif ch <= 0xFFFF:
                    buf[pos] = 0xE0 | (ch >> 12)
                    buf[pos+1] = 0x80 | ((ch >> 6) & 0x3F)
                    buf[pos+2] = 0x80 | (ch & 0x3F)
                    pos += 3

        # Reset line end style
        buf[pos] = 27; buf[pos+1] = 91; buf[pos+2] = 48; buf[pos+3] = 109; pos += 4
        
        # Save actual length written for this line
        line_buffers[y, -1] = pos


# =============================================================================
# CANVAS CLASS
# =============================================================================

class NumPyNumbaCanvas:
    """High-performance parallel NumPy/Numba Terminal Canvas."""

    def __init__(self, width=None, height=None):
        w, h = shutil.get_terminal_size((80, 24))
        self.width = width or w
        self.height = height or h

        # 2D Structured Array Buffer
        self.grid = np.zeros((self.height, self.width), dtype=CELL_DTYPE)
        self.clear()

        # Pre-allocated line byte buffers (Max 256 bytes per cell)
        self._max_line_bytes = self.width * 128 + 64
        self._line_buffers = np.zeros((self.height, self._max_line_bytes), dtype=np.uint8)

        # Trigger JIT compilation pass once during instantiation
        _render_lines_parallel(self.grid, self.height, self.width, self._line_buffers)

    def clear(self):
        """Vectorized clear operation across the whole matrix."""
        self.grid['char'] = 32  # Space character
        self.grid['has_fg'] = 0
        self.grid['has_bg'] = 0
        self.grid['style'] = Style.NONE

    def put_str(self, x: int, y: int, text: str, fg=None, bg=None, style=Style.NONE):
        """Draws string into NumPy matrix."""
        if y < 0 or y >= self.height:
            return

        length = min(len(text), self.width - x)
        if length <= 0 or x >= self.width:
            return

        slice_x = slice(x, x + length)
        
        # Vectorized string code point insertion
        self.grid[y, slice_x]['char'] = [ord(c) for c in text[:length]]
        self.grid[y, slice_x]['style'] = style

        if fg is not None:
            self.grid[y, slice_x]['has_fg'] = 1
            self.grid[y, slice_x]['fg_r'] = fg[0]
            self.grid[y, slice_x]['fg_g'] = fg[1]
            self.grid[y, slice_x]['fg_b'] = fg[2]

        if bg is not None:
            self.grid[y, slice_x]['has_bg'] = 1
            self.grid[y, slice_x]['bg_r'] = bg[0]
            self.grid[y, slice_x]['bg_g'] = bg[1]
            self.grid[y, slice_x]['bg_b'] = bg[2]

    def render(self):
        """Executes parallel Numba line-rendering and writes raw byte stream."""
        _render_lines_parallel(self.grid, self.height, self.width, self._line_buffers)

        # Collect written byte arrays per row and write directly to stdout buffer
        out_chunks = []
        for y in range(self.height):
            length = self._line_buffers[y, -1]
            out_chunks.append(self._line_buffers[y, :length].tobytes())

        sys.stdout.buffer.write(b"".join(out_chunks))
        sys.stdout.buffer.flush()

    @staticmethod
    def enter_alternate_screen():
        sys.stdout.buffer.write(b"\x1b[?1049h\x1b[?25l")
        sys.stdout.buffer.flush()

    @staticmethod
    def exit_alternate_screen():
        sys.stdout.buffer.write(b"\x1b[?1049l\x1b[?25h")
        sys.stdout.buffer.flush()


# =============================================================================
# BENCHMARK & DEMO
# =============================================================================

if __name__ == "__main__":
    canvas = NumPyNumbaCanvas()
    canvas.enter_alternate_screen()

    try:
        start_time = time.time()
        frames = 200

        for frame in range(frames):
            canvas.clear()

            # Fill matrix with dynamic color gradients
            for y in range(canvas.height - 2):
                r = int((y / canvas.height) * 255)
                g = int(((frame % 50) / 50) * 255)
                b = int((1 - y / canvas.height) * 255)
                canvas.put_str(2, y, f"Frame {frame:03d} | Parallel Numba + NumPy Threading Pipeline", fg=(r, g, b), style=Style.BOLD)

            canvas.render()

        elapsed = time.time() - start_time
        canvas.exit_alternate_screen()
        print(f"Rendered {frames} frames in {elapsed:.4f}s ({frames / elapsed:.2f} FPS)")

    except Exception as e:
        canvas.exit_alternate_screen()
        raise e

