"""
tuia.widgets.dialog - Modal dialog window.
"""
from tuia.frame import Frame, BORDER_ROUNDED
from tuia.layout import pack, place, LEFT
from tuia.widgets.label import Label
from tuia.widgets.button import Button

class Dialog(Frame):
    """
    Modal Dialog popup window centered inside its parent container.
    Renders with high Z-index overlay and returns standard action responses.
    """
    def __init__(self, parent, title="Dialog", message="", buttons=None, on_close=None, 
                 width=42, height=9, z_index=100):
        super().__init__(parent=parent, title=title, border_style=BORDER_ROUNDED, 
                         width=width, height=height, z_index=z_index)
        self.message = message
        self.on_close = on_close
        self.result = None

        self.center()

        if message:
            lbl = Label(parent=self, text=message, align="center")
            place(lbl, relx=0.05, rely=0.15, relwidth=0.9, height=2)

        button_specs = buttons if buttons else [("OK", "ok"), ("Cancel", "cancel")]
        btn_frame = Frame(parent=self, border_style=None, height=1)
        place(btn_frame, rely=0.65, relx=0.1, relwidth=0.8, height=1)

        for btn_text, btn_val in button_specs:
            def make_cmd(val=btn_val):
                return lambda: self.close(val)
            b = Button(parent=btn_frame, text=btn_text, command=make_cmd(btn_val), width=len(btn_text) + 4, height=1)
            pack(b, side=LEFT, padx=1)

    def center(self):
        """Centers the dialog inside its parent content area."""
        if hasattr(self.parent, 'get_content_area'):
            _, _, pw, ph = self.parent.get_content_area()
        else:
            pw, ph = self.parent.width, self.parent.height

        center_x = max(0, (pw - self.req_width) // 2)
        center_y = max(0, (ph - self.req_height) // 2)
        place(self, x=center_x, y=center_y, width=self.req_width, height=self.req_height)

    def close(self, result=None):
        """Closes and removes the dialog."""
        self.result = result
        self.hide()
        if self.parent:
            self.parent.remove_child(self)
            self.parent.update_layout()
        if callable(self.on_close):
            self.on_close(result)
