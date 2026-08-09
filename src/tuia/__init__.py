"""
tuia - A modular, flicker-free Python TUI engine powered by curses.
"""
from tuia.app import TUIApp
from tuia.base import Widget
from tuia.frame import (
    Frame, 
    BORDER_NONE, 
    BORDER_SINGLE, 
    BORDER_DOUBLE, 
    BORDER_ROUNDED, 
    BORDER_ASCII
)
from tuia.layout import (
    pack, 
    place, 
    align,
    grid,
    TOPLEFT,
    TOP,
    TOPRIGHT,
    LEFT,
    CENTER,
    RIGHT,
    BOTTOMLEFT,
    BOTTOM,
    BOTTOMRIGHT,
    FILL_NONE, 
    FILL_X, 
    FILL_Y, 
    FILL_BOTH
)
from tuia.widgets import (
    Label, 
    Button, 
    TextInput, 
    ProgressBar, 
    CheckBox, 
    RadioButton, 
    RadioGroup, 
    Dialog
)
from tuia.styles import colors
from tuia.events import FocusManager
from tuia.sync import sync, sync_wait

__all__ = [
    'TUIApp',
    'Widget',
    'Frame',
    'BORDER_NONE',
    'BORDER_SINGLE',
    'BORDER_DOUBLE',
    'BORDER_ROUNDED',
    'BORDER_ASCII',
    'pack',
    'place',
    'align',
    'grid',
    'TOPLEFT',
    'TOP',
    'TOPRIGHT',
    'LEFT',
    'CENTER',
    'RIGHT',
    'BOTTOMLEFT',
    'BOTTOM',
    'BOTTOMRIGHT',
    'FILL_NONE',
    'FILL_X',
    'FILL_Y',
    'FILL_BOTH',
    'Label',
    'Button',
    'TextInput',
    'ProgressBar',
    'CheckBox',
    'RadioButton',
    'RadioGroup',
    'Dialog',
    'colors',
    'FocusManager',
    'sync',
    'sync_wait'
]
