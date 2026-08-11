"""
tuia.widgets.radio - RadioButton and RadioGroup controls.
"""
from tuia.base import Widget
from tuia.constants import Keys, Modifiers

class RadioGroup:
    """Manages mutually exclusive RadioButtons."""
    def __init__(self, on_change=None):
        self.buttons = []
        self.selected_value = None
        self.on_change = on_change

    def add(self, button):
        if button not in self.buttons:
            self.buttons.append(button)
            if button.checked or len(self.buttons) == 1:
                self.selected_value = button.value
                button.checked = (button.value == self.selected_value)

    def select(self, selected_button):
        for btn in self.buttons:
            btn.checked = (btn == selected_button)
        self.selected_value = selected_button.value
        if callable(self.on_change):
            self.on_change(self.selected_value)


class RadioButton(Widget):
    """Mutually exclusive selection control `(•)` vs `( )`."""
    def __init__(self, parent=None, text="Option", value=None, group=None, checked=False, x=0, y=0, width=15, height=1, z_index=0):
        super().__init__(parent=parent, x=x, y=y, width=width, height=height, z_index=z_index)
        self.text = text
        self.value = value if value is not None else text
        self.group = group
        self.checked = checked
        self.focused = False

        if self.group:
            self.group.add(self)

    def focus(self): self.focused = True
    def blur(self): self.focused = False

    def select(self):
        if self.group:
            self.group.select(self)
        else:
            self.checked = True

    def process_event(self, key):
        if self.focused and key in (Keys.ENTER, Keys.SPACE):
            self.select()
            return True
        return False

    def draw(self):
        if not self.window:
            return

        bullet = "(•)" if self.checked else "( )"
        display_str = f"{bullet} {self.text}"[:self.width]
        attr = Modifiers.REVERSE if self.focused else Modifiers.NORMAL

        self.window.attron(attr)
        self.window.addstr(0, 0, display_str.ljust(self.width))
        self.window.attroff(attr)
