"""
tuia.base - Base Widget class defining geometry, visibility, and Z-indexing.
"""
import curses
import abc

class Widget(abc.ABC):
    """
    Abstract base class for all UI components in the engine.
    """
    def __init__(self, parent=None, x=0, y=0, width=10, height=3, z_index=0):
        self.children = []
        self.x = x
        self.y = y
        self.width = max(1, width)
        self.height = max(1, height)
        self.req_width = max(1, width)
        self.req_height = max(1, height)
        
        self.layout_params = {}
        self._z_index = z_index
        self.visible = True
        self.window = None
        self.listeners = {}

        self.parent = parent
        if self.parent is not None:
            self.parent.add_child(self)
            self.app = self.parent.app
        else:
            self.app = None

    @property
    def z_index(self):
        return self._z_index

    @z_index.setter
    def z_index(self, value):
        self._z_index = value
        if self.parent:
            self.parent._sort_children()

    def add_child(self, child):
        if child not in self.children:
            self.children.append(child)
            self._sort_children()

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

    def update_geometry(self, x, y, width, height):
        self.x = max(0, x)
        self.y = max(0, y)
        self.width = max(1, width)
        self.height = max(1, height)

        if self.window is not None:
            del self.window

        try:
            self.window = curses.newwin(self.height, self.width, self.y, self.x)
        except curses.error:
            self.window = None

    @abc.abstractmethod
    def draw(self):
        pass

    def render(self):
        if not self.visible or not self.window:
            return

        self.window.erase()
        self.draw()

        try:
            self.window.noutrefresh()
        except curses.error:
            pass

        for child in self.children:
            child.render()

    def bind(self, event_type, callback):
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)

    def handle_event(self, event):
        if not self.visible:
            return False

        for child in reversed(self.children):
            if child.handle_event(event):
                return True
        
        return self.process_event(event)

    def process_event(self, event):
        return False
