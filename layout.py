"""
tuia.layout - Geometry managers for Tkinter-like layout calculation.
"""

TOP = 'top'
BOTTOM = 'bottom'
LEFT = 'left'
RIGHT = 'right'

FILL_NONE = 'none'
FILL_X = 'x'
FILL_Y = 'y'
FILL_BOTH = 'both'


def pack(widget, side=TOP, fill=FILL_NONE, expand=False, padx=0, pady=0):
    """
    Tkinter-like Pack geometry manager. Docks the widget to a side of its parent.

    Args:
        widget: The Widget instance to pack.
        side: The side to dock to (TOP, BOTTOM, LEFT, RIGHT).
        fill: How the widget expands inside its parcel (FILL_NONE, FILL_X, FILL_Y, FILL_BOTH).
        expand: Whether the widget's parcel claims leftover unallocated space.
        padx: Horizontal padding.
        pady: Vertical padding.
    """
    widget.layout_params = {
        'type': 'pack',
        'side': side,
        'fill': fill,
        'expand': expand,
        'padx': padx,
        'pady': pady
    }
    if widget.parent:
        compute_layout(widget.parent)


def place(widget, x=0, y=0, width=None, height=None, relx=0.0, rely=0.0, relwidth=0.0, relheight=0.0):
    """
    Tkinter-like Place geometry manager. Positions the widget absolutely or relatively.
    """
    widget.layout_params = {
        'type': 'place',
        'x': x,
        'y': y,
        'width': width,
        'height': height,
        'relx': relx,
        'rely': rely,
        'relwidth': relwidth,
        'relheight': relheight
    }
    if widget.parent:
        compute_layout(widget.parent)


def compute_layout(container):
    """Computes layout for packed and placed children inside a container."""
    if not container.visible:
        return

    if hasattr(container, 'get_content_area'):
        cx, cy, cw, ch = container.get_content_area()
    else:
        cx, cy, cw, ch = container.x, container.y, container.width, container.height

    _apply_pack(container, cx, cy, cw, ch)
    _apply_place(container, cx, cy, cw, ch)

    for child in container.children:
        compute_layout(child)


def _apply_pack(container, cx, cy, cw, ch):
    """
    Two-Pass Pack Geometry Calculation:
    Pass 1: Pre-calculate total requested dimensions and leftover space for expanders.
    Pass 2: Allocate parcels and apply fill/alignment constraints.
    """
    pack_children = [
        c for c in container.children if c.layout_params.get('type') == 'pack']
    if not pack_children:
        return

    # ------------------------------------------------------------------
    # PASS 1: Calculate aggregate space requirements and expansion shares
    # ------------------------------------------------------------------
    horiz_children = [c for c in pack_children if c.layout_params.get(
        'side') in (LEFT, RIGHT)]
    vert_children = [c for c in pack_children if c.layout_params.get(
        'side') in (TOP, BOTTOM)]

    # Horizontal space budget
    total_req_w = sum(c.req_width + (c.layout_params.get('padx', 0) * 2)
                      for c in horiz_children)
    exp_horiz_count = sum(
        1 for c in horiz_children if c.layout_params.get('expand', False))
    extra_w_total = max(0, cw - total_req_w)
    extra_w_per_exp = (
        extra_w_total // exp_horiz_count) if exp_horiz_count > 0 else 0

    # Vertical space budget
    total_req_h = sum(c.req_height + (c.layout_params.get('pady', 0) * 2)
                      for c in vert_children)
    exp_vert_count = sum(
        1 for c in vert_children if c.layout_params.get('expand', False))
    extra_h_total = max(0, ch - total_req_h)
    extra_h_per_exp = (
        extra_h_total // exp_vert_count) if exp_vert_count > 0 else 0

    # ------------------------------------------------------------------
    # PASS 2: Sequential parcel allocation on shrinking cavity
    # ------------------------------------------------------------------
    rem_x, rem_y = cx, cy
    rem_w, rem_h = max(0, cw), max(0, ch)

    for child in pack_children:
        params = child.layout_params
        side = params.get('side', TOP)
        fill = params.get('fill', FILL_NONE)
        expand = params.get('expand', False)
        padx = params.get('padx', 0)
        pady = params.get('pady', 0)

        base_req_w = child.req_width + (padx * 2)
        base_req_h = child.req_height + (pady * 2)

        alloc_x, alloc_y, alloc_w, alloc_h = 0, 0, 0, 0

        if side == TOP:
            parcel_h = base_req_h + (extra_h_per_exp if expand else 0)
            alloc_w = rem_w
            alloc_h = min(rem_h, parcel_h)
            alloc_x = rem_x
            alloc_y = rem_y

            rem_y += alloc_h
            rem_h = max(0, rem_h - alloc_h)

        elif side == BOTTOM:
            parcel_h = base_req_h + (extra_h_per_exp if expand else 0)
            alloc_w = rem_w
            alloc_h = min(rem_h, parcel_h)
            alloc_x = rem_x
            alloc_y = rem_y + rem_h - alloc_h

            rem_h = max(0, rem_h - alloc_h)

        elif side == LEFT:
            parcel_w = base_req_w + (extra_w_per_exp if expand else 0)
            alloc_w = min(rem_w, parcel_w)
            alloc_h = rem_h
            alloc_x = rem_x
            alloc_y = rem_y

            rem_x += alloc_w
            rem_w = max(0, rem_w - alloc_w)

        elif side == RIGHT:
            parcel_w = base_req_w + (extra_w_per_exp if expand else 0)
            alloc_w = min(rem_w, parcel_w)
            alloc_h = rem_h
            alloc_x = rem_x + rem_w - alloc_w
            alloc_y = rem_y

            rem_w = max(0, rem_w - alloc_w)

        # Apply Fill constraints inside the assigned parcel
        final_w = child.req_width
        final_h = child.req_height

        if fill in (FILL_X, FILL_BOTH):
            final_w = max(1, alloc_w - (padx * 2))
        if fill in (FILL_Y, FILL_BOTH):
            final_h = max(1, alloc_h - (pady * 2))

        # Clamp against physical parcel bounds
        final_w = min(final_w, max(1, alloc_w - (padx * 2)))
        final_h = min(final_h, max(1, alloc_h - (pady * 2)))

        # Center widget within its parcel if fill doesn't stretch it completely
        final_x = alloc_x + padx + \
            max(0, (alloc_w - final_w - (padx * 2)) // 2)
        final_y = alloc_y + pady + \
            max(0, (alloc_h - final_h - (pady * 2)) // 2)

        child.update_geometry(final_x, final_y, final_w, final_h)


def _apply_place(container, cx, cy, cw, ch):
    """Applies absolute and relative placement for placed children."""
    place_children = [
        c for c in container.children if c.layout_params.get('type') == 'place']

    for child in place_children:
        params = child.layout_params

        final_w = child.req_width
        if params['width'] is not None:
            final_w = params['width']
        elif params['relwidth'] > 0:
            final_w = int(cw * params['relwidth'])

        final_h = child.req_height
        if params['height'] is not None:
            final_h = params['height']
        elif params['relheight'] > 0:
            final_h = int(ch * params['relheight'])

        final_x = cx + params['x']
        if params['relx'] > 0:
            final_x += int(cw * params['relx'])

        final_y = cy + params['y']
        if params['rely'] > 0:
            final_y += int(ch * params['rely'])

        child.update_geometry(
            max(0, final_x),
            max(0, final_y),
            max(1, final_w),
            max(1, final_h)
        )
