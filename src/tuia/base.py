"""
tuia.base - Base Widget class defining geometry, visibility, and Z-indexing (Textual 2D Layer).
"""
import abc
from typing import Optional, Tuple
from tuia.constants import Modifiers

from tuia.sync import sync, sync_wait


# =============================================================================
# 2D SUB-WINDOW VIRTUAL VIEW (curses.newwin Replacement)
# =============================================================================

class SubWindow:
    """
    A virtual sub-window wrapper that maps local widget coordinates (y, x) 
    to global coordinates on the root Textual 2D canvas buffer.
    """

    def __init__(self, widget: "Widget"):
        self._widget = widget
        self._active_attr = Modifiers.NORMAL

    @property
    def _root_window(self):
        return self._widget._get_root_window()

    def getmaxyx(self) -> Tuple[int, int]:
        return self._widget.height, self._widget.width

    # =========================================================================
    # ATTRIBUTE MANAGEMENT (curses parity)
    # =========================================================================

    def attrset(self, attr: int):
        """Sets the active attribute mask, overwriting previous attributes."""
        self._active_attr = attr

    def attron(self, attr: int):
        """Turns on specific attribute bits without clearing existing ones."""
        self._active_attr |= attr

    def attroff(self, attr: int):
        """Turns off specific attribute bits."""
        self._active_attr &= ~attr

    # =========================================================================
    # DRAWING OPERATIONS
    # =========================================================================

    def erase(self):
        root = self._root_window
        if not root:
            return

        blank = " " * self._widget.width
        for ly in range(self._widget.height):
            root.addstr(self._widget.y + ly, self._widget.x, blank)

    def clear(self):
        self.erase()

    def addstr(self, y: int, x: int, text: str, attr: int = 0):
        """
        Draws text using local coordinates. Combines active window attributes 
        with any inline attr parameter.
        """
        root = self._root_window
        if not root:
            return

        if y < 0 or y >= self._widget.height or x < 0 or x >= self._widget.width:
            return

        available = min(len(text), self._widget.width - x)
        if available <= 0:
            return

        clipped_text = text[:available]
        effective_attr = self._active_attr | attr

        root.addstr(self._widget.y + y, self._widget.x +
                    x, clipped_text, effective_attr)

    def addch(self, y: int, x: int, ch: str, attr: int = 0):
        self.addstr(y, x, str(ch)[:1], attr)

    def inch(self, y: int, x: int) -> int:
        root = self._root_window
        if root and 0 <= y < self._widget.height and 0 <= x < self._widget.width:
            return root.inch(self._widget.y + y, self._widget.x + x)
        return 32

    def noutrefresh(self):
        pass

    def refresh(self):
        root = self._root_window
        if root:
            root.refresh()

# =============================================================================
# WIDGET BASE CLASS
# =============================================================================


class Widget(abc.ABC):
    """
    Abstract base class for all UI components in the engine.
    """

    @sync_wait
    def __init__(self, parent=None, x=0, y=0, width=10, height=3, z_index=0):
        self.children = []
        self.x = max(0, x)
        self.y = max(0, y)
        self.width = max(1, width)
        self.height = max(1, height)
        self.req_width = max(1, width)
        self.req_height = max(1, height)

        self.layout_params = {}
        self._z_index = z_index
        self.visible = True
        self.listeners = {}

        # Initialize sub-window view bound to this widget
        self.window = SubWindow(self)

        self.parent = parent
        if self.parent is not None:
            self.app = self.parent.app
            self.parent.add_child(self)
        else:
            self.app = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        init = cls.__dict__.get("__init__")

        if init is not None and not getattr(
            init,
            "_ui_sync_wrapped",
            False
        ):
            cls.__init__ = sync_wait(init)

    def _get_root_window(self):
        """Traverses hierarchy to retrieve the root Textual 2D Window instance."""
        if self.app and getattr(self.app, "stdscr", None) is not None:
            return self.app.stdscr
        if self.parent:
            return self.parent._get_root_window()
        return None

    @property
    def z_index(self):
        return self._z_index

    @z_index.setter
    @sync
    def z_index(self, value):
        self._z_index = value
        if self.parent:
            self.parent._sort_children()

    @sync
    def add_child(self, child):
        if child not in self.children:
            self.children.append(child)
            self._sort_children()

    @sync
    def remove_child(self, child):
        if child in self.children:
            self.children.remove(child)

    def _sort_children(self):
        self.children.sort(key=lambda c: c.z_index)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def update_layout(self):
        """
        Triggers geometry recalculation for child widgets.
        Base implementation delegates layout computation down the container tree.
        """
        for child in self.children:
            child.update_layout()

    @sync_wait
    def update_geometry(self, x, y, width, height):
        """Updates widget coordinates and dimension bounds."""
        self.x = max(0, x)
        self.y = max(0, y)
        self.width = max(1, width)
        self.height = max(1, height)

        if self.window is None:
            self.window = SubWindow(self)

    @abc.abstractmethod
    def draw(self):
        pass

    def render(self):
        """Executes drawing pass for this widget and recursively renders children."""
        if not self.visible or not self.window:
            return

        self.window.erase()
        self.draw()
        self.window.noutrefresh()

        for child in self.children:
            child.render()

    @sync
    def bind(self, event_type, callback):
        """Registers an event listener callback for a given event type."""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        if callback not in self.listeners[event_type]:
            self.listeners[event_type].append(callback)

    @sync
    def unbind(self, event_type, callback=None):
        """
        Removes an event listener callback. 
        If callback is None, removes all listeners for the given event_type.
        """
        if event_type in self.listeners:
            if callback is None:
                del self.listeners[event_type]
            else:
                if callback in self.listeners[event_type]:
                    self.listeners[event_type].remove(callback)
                # Clean up the key if the list becomes empty
                if not self.listeners[event_type]:
                    del self.listeners[event_type]

    def handle_event(self, event):
        if not self.visible:
            return False

        for child in reversed(self.children):
            if child.handle_event(event):
                return True

        return self.process_event(event)

    def process_event(self, event):
        """
        Executes any callbacks bound to this event type.
        """
        if event in self.listeners:
            for callback in self.listeners[event]:
                callback(self, event)
            return True

        return False
