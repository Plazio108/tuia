"""
tuia.constants - Native styling modifiers, colors, and key mappings for Tuify Engine.
Zero Curses dependencies.
"""


class Modifiers:
    NORMAL = 0
    BOLD = 1 << 0          # 1
    DIM = 1 << 1           # 2
    UNDERLINE = 1 << 2     # 4
    REVERSE = 1 << 3       # 8
    ITALIC = 1 << 4        # 16
    STRIKETHROUGH = 1 << 5 # 32
    OVERLINE = 1 << 6      # 64
    BLINK = 1 << 7         # 128


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
    # Action & Navigation
    ENTER = "enter"
    TAB = "tab"
    SHIFT_TAB = "shift+tab"
    ESCAPE = "escape"
    BACKSPACE = "backspace"
    DELETE = "delete"
    SPACE = "space"

    # Arrow Keys
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    # Page & Line Navigation
    HOME = "home"
    END = "end"
    PAGE_UP = "pageup"
    PAGE_DOWN = "pagedown"

    # Function Keys
    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"
