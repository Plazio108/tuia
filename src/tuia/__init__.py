"""
tuia - A modular, flicker-free Python TUI engine powered by curses.
"""

from tuia.app import TUIApp
from tuia.base import Widget
from tuia.constants import Colors, Keys, Modifiers
from tuia.events import FocusManager
from tuia.frame import (
    BORDER_ASCII,
    BORDER_DOUBLE,
    BORDER_NONE,
    BORDER_ROUNDED,
    BORDER_SINGLE,
    Frame,
)
from tuia.layout import (
    BOTTOM,
    BOTTOMLEFT,
    BOTTOMRIGHT,
    CENTER,
    FILL_BOTH,
    FILL_NONE,
    FILL_X,
    FILL_Y,
    LEFT,
    RIGHT,
    TOP,
    TOPLEFT,
    TOPRIGHT,
    align,
    grid,
    pack,
    place,
)
from tuia.sync import sync, sync_wait
from tuia.widgets import (
    Button,
    CheckBox,
    Dialog,
    Label,
    ProgressBar,
    RadioButton,
    RadioGroup,
    TextInput,
)

__all__ = [
    "BORDER_ASCII",
    "BORDER_DOUBLE",
    "BORDER_NONE",
    "BORDER_ROUNDED",
    "BORDER_SINGLE",
    "BOTTOM",
    "BOTTOMLEFT",
    "BOTTOMRIGHT",
    "CENTER",
    "FILL_BOTH",
    "FILL_NONE",
    "FILL_X",
    "FILL_Y",
    "LEFT",
    "RIGHT",
    "TOP",
    "TOPLEFT",
    "TOPRIGHT",
    "Button",
    "CheckBox",
    "Colors",
    "Dialog",
    "FocusManager",
    "Frame",
    "Keys",
    "Label",
    "Modifiers",
    "ProgressBar",
    "RadioButton",
    "RadioGroup",
    "TUIApp",
    "TextInput",
    "Widget",
    "align",
    "grid",
    "pack",
    "place",
    "sync",
    "sync_wait",
]
