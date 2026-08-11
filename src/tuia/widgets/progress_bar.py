"""
tuia.widgets.progress_bar - Progress bar indicator.
"""
from tuia.base import Widget

class ProgressBar(Widget):
    """Visual progress bar displaying completion percentages."""
    def __init__(self, parent=None, progress=0.0, fill_char="█", empty_char="░", 
                 show_percentage=True, x=0, y=0, width=20, height=1, z_index=0):
        super().__init__(parent=parent, x=x, y=y, width=width, height=height, z_index=z_index)
        self._progress = max(0.0, min(1.0, progress))
        self.fill_char = fill_char
        self.empty_char = empty_char
        self.show_percentage = show_percentage

    @property
    def progress(self): return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = max(0.0, min(1.0, value))

    def draw(self):
        if not self.window:
            return

        pct_str = f" {int(self._progress * 100)}%" if self.show_percentage else ""
        bar_width = max(1, self.width - len(pct_str))

        filled_len = int(bar_width * self._progress)
        empty_len = max(0, bar_width - filled_len)

        bar = (self.fill_char * filled_len) + (self.empty_char * empty_len) + pct_str

        self.window.addstr(0, 0, bar[:self.width])
