"""
tuia.styles - Color management supporting Standard (8/16), 256-color, and 24-bit TrueColor.
"""
import curses
import math

class ColorManager:
    """
    Manages terminal color capabilities, custom color pair allocation, 
    and RGB / TrueColor palette mappings.
    """
    def __init__(self):
        self.has_colors = False
        self.can_custom_color = False
        self._pair_counter = 1
        self._color_counter = 16  # Reserve 0-15 for system standard colors
        self._pair_cache = {}     # Cache (fg_rgb_or_id, bg_rgb_or_id) -> pair_number
        self._custom_color_cache = {} # Cache (r, g, b) -> color_id

    def init_colors(self):
        """Initializes curses color capabilities."""
        if not curses.has_colors():
            self.has_colors = False
            return

        self.has_colors = True
        curses.start_color()
        curses.use_default_colors()
        self.can_custom_color = curses.can_change_color()

    def _rgb_to_256(self, r: int, g: int, b: int) -> int:
        """Fallback Euclidean RGB matching to 256-color ANSI palette."""
        # Check standard 6x6x6 color cube
        r_idx = round(r / 255 * 5)
        g_idx = round(g / 255 * 5)
        b_idx = round(b / 255 * 5)
        return 16 + (36 * r_idx) + (6 * g_idx) + b_idx

    def _get_or_create_color_id(self, r: int, g: int, b: int) -> int:
        """
        Creates a custom curses color ID from 24-bit RGB if terminal supports TrueColor/redefinition,
        otherwise maps to nearest 256-color palette index.
        """
        rgb_key = (r, g, b)
        if rgb_key in self._custom_color_cache:
            return self._custom_color_cache[rgb_key]

        if self.can_custom_color and self._color_counter < curses.COLORS:
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

    def get_color_pair(self, fg, bg=-1):
        """
        Gets or creates a curses color pair.
        Accepts:
            - Integers: Standard curses color IDs or 256-color indices.
            - Tuples: (R, G, B) tuples for 24-bit TrueColor.
            - -1: Default terminal background/foreground.
        """
        if not self.has_colors:
            return 0

        # Resolve FG
        if isinstance(fg, (tuple, list)) and len(fg) == 3:
            fg_id = self._get_or_create_color_id(*fg)
        else:
            fg_id = fg

        # Resolve BG
        if isinstance(bg, (tuple, list)) and len(bg) == 3:
            bg_id = self._get_or_create_color_id(*bg)
        else:
            bg_id = bg

        pair_key = (fg_id, bg_id)
        if pair_key in self._pair_cache:
            return curses.color_pair(self._pair_cache[pair_key])

        if self._pair_counter < curses.COLOR_PAIRS - 1:
            pair_num = self._pair_counter
            self._pair_counter += 1
            try:
                curses.init_pair(pair_num, fg_id, bg_id)
                self._pair_cache[pair_key] = pair_num
                return curses.color_pair(pair_num)
            except curses.error:
                return 0

        return 0

# Global singleton color manager instance
colors = ColorManager()
