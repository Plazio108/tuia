"""
tuia.constants - Bitmasks for styling modifiers, colors, and key mappings.
"""

class Modifiers:
    NORMAL = 0
    BOLD = 1 << 0       # 1
    DIM = 1 << 1        # 2
    UNDERLINE = 1 << 2  # 4
    REVERSE = 1 << 3    # 8
    ITALIC = 1 << 4     # 16


# Curses-style alias shorthands for convenience
A_NORMAL = Modifiers.NORMAL
A_BOLD = Modifiers.BOLD
A_DIM = Modifiers.DIM
A_UNDERLINE = Modifiers.UNDERLINE
A_REVERSE = Modifiers.REVERSE
A_ITALIC = Modifiers.ITALIC


class Colors:
    DEFAULT = None
    BLACK = (0, 0, 0)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    YELLOW = (255, 255, 0)
    BLUE = (0, 0, 255)
    MAGENTA = (255, 0, 255)
    CYAN = (0, 255, 255)
    WHITE = (255, 255, 255)


class Keys:
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ENTER = "enter"
    BACKSPACE = "backspace"
    ESCAPE = "escape"
    TAB = "tab"
    SPACE = "space"