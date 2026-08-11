"""
gleaf.py - Functional drawing abstraction layer for Python curses windows/panels.
"""

import curses
from typing import Union, Tuple, List

# =============================================================================
# Constants Definitions
# =============================================================================


class Keys:
    """Clearer naming for standard curses keys."""
    UP = curses.KEY_UP
    DOWN = curses.KEY_DOWN
    LEFT = curses.KEY_LEFT
    RIGHT = curses.KEY_RIGHT
    ENTER = curses.KEY_ENTER
    BACKSPACE = curses.KEY_BACKSPACE
    DELETE = curses.KEY_DC
    ESCAPE = 27
    TAB = 9
    SPACE = 32


class Modifiers:
    """Clearer naming for text attributes."""
    NORMAL = curses.A_NORMAL
    BOLD = curses.A_BOLD
    DIM = curses.A_DIM
    UNDERLINE = curses.A_UNDERLINE
    REVERSE = curses.A_REVERSE
    BLINK = curses.A_BLINK
    INVISIBLE = curses.A_INVIS
    ITALIC = getattr(curses, 'A_ITALIC', 0)


class Colors:
    """Standard color definitions."""
    DEFAULT = -1
    BLACK = curses.COLOR_BLACK
    RED = curses.COLOR_RED
    GREEN = curses.COLOR_GREEN
    YELLOW = curses.COLOR_YELLOW
    BLUE = curses.COLOR_BLUE
    MAGENTA = curses.COLOR_MAGENTA
    CYAN = curses.COLOR_CYAN
    WHITE = curses.COLOR_WHITE


# =============================================================================
# Enhanced Color Manager
# =============================================================================

ColorType = Union[int, Tuple[int, int, int], List[int]]


class ColorManager:
    """
    Manages terminal color capabilities, custom color pair allocation, 
    and RGB / TrueColor palette mappings.
    """

    def __init__(self):
        self._initialized = False
        self.has_colors = False
        self.can_custom_color = False
        self._pair_counter = 1
        self._color_counter = 16       # Reserve 0-15 for system standard colors
        self._pair_cache = {}          # Cache (fg_id, bg_id) -> pair_attr
        self._custom_color_cache = {}  # Cache (r, g, b) -> color_id

    def init_colors(self):
        """Initializes curses color capabilities."""
        if not curses.has_colors():
            self.has_colors = False
            self._initialized = True
            return

        self.has_colors = True
        try:
            curses.start_color()
            curses.use_default_colors()
        except curses.error:
            pass

        self.can_custom_color = curses.can_change_color()
        self._initialized = True

    def _rgb_to_256(self, r: int, g: int, b: int) -> int:
        """
        Maps RGB to the 256-color ANSI palette. 
        Uses dedicated grayscale ramp (232-255) for grays, and 6x6x6 cube (16-231) for colors.
        """
        # Grayscale optimization
        if abs(r - g) < 8 and abs(g - b) < 8 and abs(r - b) < 8:
            if r < 8:
                return 16   # Black
            if r > 248:
                return 231  # Bright White
            return 232 + int((r - 8) / 247 * 24)

        # 6x6x6 color cube lookup
        r_idx = round(r / 255 * 5)
        g_idx = round(g / 255 * 5)
        b_idx = round(b / 255 * 5)
        return 16 + (36 * r_idx) + (6 * g_idx) + b_idx

    def _get_or_create_color_id(self, r: int, g: int, b: int) -> int:
        """
        Creates a custom curses color ID from 24-bit RGB if terminal supports TrueColor,
        otherwise falls back to the nearest 256-color palette index.
        """
        rgb_key = (r, g, b)
        if rgb_key in self._custom_color_cache:
            return self._custom_color_cache[rgb_key]

        if self.can_custom_color and self._color_counter < getattr(curses, 'COLORS', 0):
            color_id = self._color_counter
            self._color_counter += 1
            # Curses expects RGB values in range [0, 1000]
            curses_r = int((r / 255.0) * 1000)
            curses_g = int((g / 255.0) * 1000)
            curses_b = int((b / 255.0) * 1000)
            try:
                curses.init_color(color_id, curses_r, curses_g, curses_b)
                self._custom_color_cache[rgb_key] = color_id
                return color_id
            except curses.error:
                pass

        # Fallback to 256-color lookup
        color_id = self._rgb_to_256(r, g, b)
        self._custom_color_cache[rgb_key] = color_id
        return color_id

    def get_color_pair(self, fg: ColorType, bg: ColorType = -1) -> int:
        """
        Gets or creates a curses color pair attribute.
        Accepts:
            - Integers: Standard curses color IDs, 256-color indices, or -1 for default.
            - Tuples/Lists: (R, G, B) tuples (0-255) for 24-bit TrueColor.
        """
        if not self._initialized:
            self.init_colors()

        if not self.has_colors:
            return 0

        # Resolve FG
        if isinstance(fg, (tuple, list)) and len(fg) == 3:
            fg_id = self._get_or_create_color_id(*fg)
        else:
            fg_id = int(fg)

        # Resolve BG
        if isinstance(bg, (tuple, list)) and len(bg) == 3:
            bg_id = self._get_or_create_color_id(*bg)
        else:
            bg_id = int(bg)

        pair_key = (fg_id, bg_id)
        if pair_key in self._pair_cache:
            return self._pair_cache[pair_key]

        max_pairs = getattr(curses, 'COLOR_PAIRS', 256)
        if self._pair_counter < max_pairs - 1:
            pair_num = self._pair_counter
            self._pair_counter += 1
            try:
                curses.init_pair(pair_num, fg_id, bg_id)
                pair_attr = curses.color_pair(pair_num)
                self._pair_cache[pair_key] = pair_attr
                return pair_attr
            except curses.error:
                return 0

        return 0


# Global singleton instance
colors = ColorManager()


def init_colors():
    """Module-level helper to initialize color management explicitly."""
    colors.init_colors()


# =============================================================================
# Drawing & Editing Functions
# =============================================================================

def draw_text(win, y: int, x: int, text: str, attr: int = 0):
    """
    Safely draws a string to the window, handling bounds clipping and bottom-right corner edge cases.
    """
    max_y, max_x = win.getmaxyx()

    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return

    available_space = max_x - x
    if available_space <= 0:
        return

    text = text[:available_space]

    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        # Expected and safe to ignore when writing to the bottom-right cell
        pass


def draw_block(win, y: int, x: int, text: str, attr: int = 0):
    """
    Draws multi-line text blocks to the window.
    """
    for i, line in enumerate(text.split('\n')):
        draw_text(win, y + i, x, line, attr)


def edit_zone_color(win, y: int, x: int, height: int, width: int, fg: ColorType, bg: ColorType = -1):
    """
    Changes the foreground/background color in a rectangle while keeping text and existing modifiers intact.
    """
    max_y, max_x = win.getmaxyx()
    color_attr = colors.get_color_pair(fg, bg)

    for cy in range(max(0, y), min(y + height, max_y)):
        for cx in range(max(0, x), min(x + width, max_x)):
            try:
                char_data = win.inch(cy, cx)
                char = char_data & curses.A_CHARTEXT
                mods = char_data & curses.A_ATTRIBUTES

                # Clear existing color bits, apply new color pair
                mods &= ~curses.A_COLOR
                win.addch(cy, cx, char, mods | color_attr)
            except curses.error:
                pass


def edit_zone_modifiers(win, y: int, x: int, height: int, width: int, modifiers: int, action: str = 'add'):
    """
    Modifies text attributes in a rectangle while keeping character content and colors intact.

    :param action: 'add' (combine), 'remove' (strip), or 'set' (replace non-color modifiers).
    """
    max_y, max_x = win.getmaxyx()

    for cy in range(max(0, y), min(y + height, max_y)):
        for cx in range(max(0, x), min(x + width, max_x)):
            try:
                char_data = win.inch(cy, cx)
                char = char_data & curses.A_CHARTEXT
                current_attr = char_data & curses.A_ATTRIBUTES

                if action == 'add':
                    new_attr = current_attr | modifiers
                elif action == 'remove':
                    new_attr = current_attr & ~modifiers
                elif action == 'set':
                    color_part = current_attr & curses.A_COLOR
                    new_attr = color_part | modifiers
                else:
                    new_attr = current_attr

                win.addch(cy, cx, char, new_attr)
            except curses.error:
                pass
