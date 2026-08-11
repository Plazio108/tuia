"""
tuia/utils.py - Drawing and zone manipulation utilities compatible with Window and SubWindow.
"""

from typing import Union, Tuple

ColorType = Union[None, Tuple[int, int, int], str]


def draw_text(win, y: int, x: int, text: str, attr: int = 0):
    """
    Safely draws text to a Window or SubWindow using local coordinates.
    """
    win.addstr(y, x, text, attr)


def draw_block(win, y: int, x: int, text: str, attr: int = 0):
    """
    Draws a multi-line text block to a Window or SubWindow.
    """
    for i, line in enumerate(text.split("\n")):
        win.addstr(y + i, x, line, attr)


def _resolve_grid_and_offsets(win):
    """Helper to extract the root grid buffer and coordinate offsets."""
    if hasattr(win, "_root_window"):  # It's a Widget's SubWindow
        root = win._root_window
        if not root:
            return None, 0, 0, 0, 0
        offset_y, offset_x = win._widget.y, win._widget.x
        local_h, local_w = win.getmaxyx()
    else:  # It's the root Window
        root = win
        offset_y, offset_x = 0, 0
        local_h, local_w = root.getmaxyx()

    return root, offset_y, offset_x, local_h, local_w


def edit_zone_color(
    win,
    y: int,
    x: int,
    height: int,
    width: int,
    fg: ColorType,
    bg: ColorType = None,
):
    """
    Applies TrueColor RGB styling to a local rectangle inside a Window or SubWindow.
    """
    root, offset_y, offset_x, local_h, local_w = _resolve_grid_and_offsets(win)
    if not root:
        return

    # Local clipping within local window bounds
    for ly in range(max(0, y), min(y + height, local_h)):
        for lx in range(max(0, x), min(x + width, local_w)):
            gy, gx = ly + offset_y, lx + offset_x
            if 0 <= gy < root._height and 0 <= gx < root._width:
                cell = root._grid[gy][gx]
                cell.fg = fg
                cell.bg = bg


def edit_zone_modifiers(
    win,
    y: int,
    x: int,
    height: int,
    width: int,
    modifiers: int,
    action: str = "add",
):
    """
    Applies or removes bitmask modifiers in a local rectangle inside a Window or SubWindow.
    """
    root, offset_y, offset_x, local_h, local_w = _resolve_grid_and_offsets(win)
    if not root:
        return

    for ly in range(max(0, y), min(y + height, local_h)):
        for lx in range(max(0, x), min(x + width, local_w)):
            gy, gx = ly + offset_y, lx + offset_x
            if 0 <= gy < root._height and 0 <= gx < root._width:
                cell = root._grid[gy][gx]

                if action == "add":
                    cell.modifiers |= modifiers
                elif action == "remove":
                    cell.modifiers &= ~modifiers
                elif action == "set":
                    cell.modifiers = modifiers
