"""
tuia.events - Focus management and keyboard navigation routing.
"""
from tuia.constants import Keys

class FocusManager:
    """
    Manages interactive widget focus switching via Tab and Shift-Tab.
    """

    def __init__(self, root_frame):
        self.root_frame = root_frame
        self.focused_widget = None

    def _get_focusable_widgets(self, widget):
        """Recursively collects all visible, focusable child widgets."""
        focusable = []
        if not widget.visible:
            return focusable

        # Check if the widget supports focus
        if hasattr(widget, 'focus') and hasattr(widget, 'blur'):
            focusable.append(widget)

        for child in widget.children:
            focusable.extend(self._get_focusable_widgets(child))

        return focusable

    def focus_next(self):
        """Advances focus to the next focusable widget."""
        widgets = self._get_focusable_widgets(self.root_frame)
        if not widgets:
            return

        if self.focused_widget in widgets:
            idx = (widgets.index(self.focused_widget) + 1) % len(widgets)
        else:
            idx = 0

        self._set_focus(widgets[idx])

    def focus_previous(self):
        """Moves focus to the previous focusable widget."""
        widgets = self._get_focusable_widgets(self.root_frame)
        if not widgets:
            return

        if self.focused_widget in widgets:
            idx = (widgets.index(self.focused_widget) - 1) % len(widgets)
        else:
            idx = len(widgets) - 1

        self._set_focus(widgets[idx])

    def _set_focus(self, target_widget):
        """Unfocuses currently focused widget and sets focus to the new target."""
        if self.focused_widget and self.focused_widget != target_widget:
            self.focused_widget.blur()

        self.focused_widget = target_widget
        if self.focused_widget:
            self.focused_widget.focus()

    def handle_tab_navigation(self, key):
        """
        Intercepts Tab / Shift-Tab keys for global focus navigation.
        Returns True if the key was handled.
        """
        # Tab key
        if key == Keys.TAB:
            self.focus_next()
            return True
        # Shift-Tab (Key code 353 in ncurses)
        elif key == Keys.SHIFT_TAB:
            self.focus_previous()
            return True
        return False
