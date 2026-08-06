"""
tuify.layout - Geometry managers for TUI UI calculation.
"""

# 9-Point Compass Constants (Used for Align and Grid Sticky)
TOPLEFT = 'topleft'
TOP = 'top'
TOPRIGHT = 'topright'
LEFT = 'left'
CENTER = 'center'
RIGHT = 'right'
BOTTOMLEFT = 'bottomleft'
BOTTOM = 'bottom'
BOTTOMRIGHT = 'bottomright'

# Pack & Fill Constants
FILL_NONE = 'none'
FILL_X = 'x'
FILL_Y = 'y'
FILL_BOTH = 'both'


def pack(widget, side=TOP, fill=FILL_NONE, expand=False, padx=0, pady=0, anchor=CENTER):
    """
    Strict Cavity Manager. Docks the widget sequentially to the edges of the available space.
    Does NOT handle floating corners. Use align() or grid() for that.
    """
    widget.layout_params = {
        'type': 'pack',
        'side': side,
        'fill': fill,
        'expand': expand,
        'padx': padx,
        'pady': pady,
        'anchor': anchor
    }
    if widget.parent:
        widget.parent.update_layout()


def align(widget, position=CENTER, padx=0, pady=0):
    """
    Floating Layout Manager. 
    Positions a widget absolutely in one of the 9 compass points of its parent.
    It ignores other widgets and does not consume space from the pack() cavity.
    Perfect for Modals, Corner Badges, and overlays.
    """
    widget.layout_params = {
        'type': 'align',
        'position': position,
        'padx': padx,
        'pady': pady
    }
    if widget.parent:
        widget.parent.update_layout()


def grid(widget, row=0, col=0, rowspan=1, colspan=1, weightx=0, weighty=0, sticky=CENTER, padx=0, pady=0):
    """
    2D Cellular Layout Manager.
    Divides the container into rows and columns. Widgets can span cells and stretch (weights).
    sticky dictates how the widget aligns inside its cell(s) (e.g., TOPLEFT or FILL_BOTH).
    """
    widget.layout_params = {
        'type': 'grid',
        'row': row,
        'col': col,
        'rowspan': rowspan,
        'colspan': colspan,
        'weightx': weightx,
        'weighty': weighty,
        'sticky': sticky,
        'padx': padx,
        'pady': pady
    }
    if widget.parent:
        widget.parent.update_layout()


def place(widget, x=0, y=0, width=None, height=None, relx=0.0, rely=0.0, relwidth=0.0, relheight=0.0, anchor=TOPLEFT):
    """Strict Coordinate Manager. Positions the widget using math."""
    widget.layout_params = {
        'type': 'place',
        'x': x,
        'y': y,
        'width': width,
        'height': height,
        'relx': relx,
        'rely': rely,
        'relwidth': relwidth,
        'relheight': relheight,
        'anchor': anchor
    }
    if widget.parent:
        widget.parent.update_layout()


def compute_layout(container):
    """Calculates all 4 independent layout engines for the container."""
    if not container.visible:
        return

    if hasattr(container, 'get_content_area'):
        cx, cy, cw, ch = container.get_content_area()
    else:
        cx, cy, cw, ch = container.x, container.y, container.width, container.height

    # Run layout engines
    _apply_grid(container, cx, cy, cw, ch)
    _apply_pack(container, cx, cy, cw, ch)
    _apply_align(container, cx, cy, cw, ch)
    _apply_place(container, cx, cy, cw, ch)

    for child in container.children:
        compute_layout(child)


# ==========================================
# INTERNAL ENGINE IMPLEMENTATIONS
# ==========================================

def _apply_align(container, cx, cy, cw, ch):
    """Calculates independent floating widgets."""
    align_children = [c for c in container.children if c.layout_params.get('type') == 'align']
    
    for child in align_children:
        params = child.layout_params
        pos = params['position']
        padx, pady = params['padx'], params['pady']
        
        fw, fh = child.req_width, child.req_height
        float_w = max(0, cw - fw - (padx * 2))
        float_h = max(0, ch - fh - (pady * 2))

        # X Alignment
        if pos in (TOPLEFT, LEFT, BOTTOMLEFT):
            fx = cx + padx
        elif pos in (TOPRIGHT, RIGHT, BOTTOMRIGHT):
            fx = cx + padx + float_w
        else: # CENTER, TOP, BOTTOM
            fx = cx + padx + (float_w // 2)

        # Y Alignment
        if pos in (TOPLEFT, TOP, TOPRIGHT):
            fy = cy + pady
        elif pos in (BOTTOMLEFT, BOTTOM, BOTTOMRIGHT):
            fy = cy + pady + float_h
        else: # CENTER, LEFT, RIGHT
            fy = cy + pady + (float_h // 2)

        child.update_geometry(fx, fy, fw, fh)


def _apply_grid(container, cx, cy, cw, ch):
    """Calculates 2D rows, columns, weights, and spans."""
    grid_children = [c for c in container.children if c.layout_params.get('type') == 'grid']
    if not grid_children:
        return

    max_row = max(c.layout_params['row'] + c.layout_params['rowspan'] - 1 for c in grid_children)
    max_col = max(c.layout_params['col'] + c.layout_params['colspan'] - 1 for c in grid_children)

    row_heights = {r: 0 for r in range(max_row + 1)}
    col_widths = {c: 0 for c in range(max_col + 1)}
    row_weights = {r: 0 for r in range(max_row + 1)}
    col_weights = {c: 0 for c in range(max_col + 1)}

    for child in grid_children:
        p = child.layout_params
        r, c_idx = p['row'], p['col']
        rs, cs = p['rowspan'], p['colspan']
        
        row_weights[r] = max(row_weights[r], p.get('weighty', 0))
        col_weights[c_idx] = max(col_weights[c_idx], p.get('weightx', 0))

        if rs == 1:
            row_heights[r] = max(row_heights[r], child.req_height + (p['pady'] * 2))
        if cs == 1:
            col_widths[c_idx] = max(col_widths[c_idx], child.req_width + (p['padx'] * 2))

    extra_w = max(0, cw - sum(col_widths.values()))
    extra_h = max(0, ch - sum(row_heights.values()))
    tot_weight_x = sum(col_weights.values())
    tot_weight_y = sum(row_weights.values())

    if tot_weight_x > 0 and extra_w > 0:
        for c_idx in col_widths:
            col_widths[c_idx] += int(extra_w * (col_weights[c_idx] / tot_weight_x))
    if tot_weight_y > 0 and extra_h > 0:
        for r in row_heights:
            row_heights[r] += int(extra_h * (row_weights[r] / tot_weight_y))

    row_y, col_x = {0: cy}, {0: cx}
    for r in range(1, max_row + 1):
        row_y[r] = row_y[r - 1] + row_heights.get(r - 1, 0)
    for c_idx in range(1, max_col + 1):
        col_x[c_idx] = col_x[c_idx - 1] + col_widths.get(c_idx - 1, 0)

    for child in grid_children:
        p = child.layout_params
        r, c_idx, sticky = p['row'], p['col'], p['sticky']
        padx, pady = p['padx'], p['pady']

        cell_w = sum(col_widths.get(c_idx + i, 0) for i in range(p['colspan']))
        cell_h = sum(row_heights.get(r + i, 0) for i in range(p['rowspan']))

        fw, fh = child.req_width, child.req_height

        if sticky in (FILL_X, FILL_BOTH): fw = max(1, cell_w - (padx * 2))
        if sticky in (FILL_Y, FILL_BOTH): fh = max(1, cell_h - (pady * 2))
        fw = min(fw, max(1, cell_w - (padx * 2)))
        fh = min(fh, max(1, cell_h - (pady * 2)))

        float_w = max(0, cell_w - fw - (padx * 2))
        float_h = max(0, cell_h - fh - (pady * 2))

        ox = 0 if sticky in (TOPLEFT, LEFT, BOTTOMLEFT) else (float_w if sticky in (TOPRIGHT, RIGHT, BOTTOMRIGHT) else float_w // 2)
        oy = 0 if sticky in (TOPLEFT, TOP, TOPRIGHT) else (float_h if sticky in (BOTTOMLEFT, BOTTOM, BOTTOMRIGHT) else float_h // 2)

        child.update_geometry(col_x[c_idx] + padx + ox, row_y[r] + pady + oy, fw, fh)


def _apply_pack(container, cx, cy, cw, ch):
    """
    Two-Pass Pack Geometry Calculation:
    Pass 1: Pre-calculate total requested dimensions and leftover space for expanders.
    Pass 2: Allocate parcels and apply fill/alignment constraints.
    """
    pack_children = [c for c in container.children if c.layout_params.get('type') == 'pack']
    if not pack_children:
        return

    horiz_children = [c for c in pack_children if c.layout_params.get('side') in (LEFT, RIGHT)]
    vert_children = [c for c in pack_children if c.layout_params.get('side') in (TOP, BOTTOM)]

    total_req_w = sum(c.req_width + (c.layout_params.get('padx', 0) * 2) for c in horiz_children)
    exp_horiz_count = sum(1 for c in horiz_children if c.layout_params.get('expand', False))
    extra_w_total = max(0, cw - total_req_w)
    extra_w_per_exp = (extra_w_total // exp_horiz_count) if exp_horiz_count > 0 else 0

    total_req_h = sum(c.req_height + (c.layout_params.get('pady', 0) * 2) for c in vert_children)
    exp_vert_count = sum(1 for c in vert_children if c.layout_params.get('expand', False))
    extra_h_total = max(0, ch - total_req_h)
    extra_h_per_exp = (extra_h_total // exp_vert_count) if exp_vert_count > 0 else 0

    rem_x, rem_y = cx, cy
    rem_w, rem_h = max(0, cw), max(0, ch)

    for child in pack_children:
        params = child.layout_params
        side = params.get('side', TOP)
        fill = params.get('fill', FILL_NONE)
        expand = params.get('expand', False)
        padx = params.get('padx', 0)
        pady = params.get('pady', 0)
        anchor = params.get('anchor', CENTER)

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

        final_w = child.req_width
        final_h = child.req_height

        if fill in (FILL_X, FILL_BOTH):
            final_w = max(1, alloc_w - (padx * 2))
        if fill in (FILL_Y, FILL_BOTH):
            final_h = max(1, alloc_h - (pady * 2))

        final_w = min(final_w, max(1, alloc_w - (padx * 2)))
        final_h = min(final_h, max(1, alloc_h - (pady * 2)))

        float_w = max(0, alloc_w - final_w - (padx * 2))
        float_h = max(0, alloc_h - final_h - (pady * 2))

        if anchor in (TOPLEFT, LEFT, BOTTOMLEFT):
            offset_x = 0
        elif anchor in (TOPRIGHT, RIGHT, BOTTOMRIGHT):
            offset_x = float_w
        else:
            offset_x = float_w // 2

        if anchor in (TOPLEFT, TOP, TOPRIGHT):
            offset_y = 0
        elif anchor in (BOTTOMLEFT, BOTTOM, BOTTOMRIGHT):
            offset_y = float_h
        else:
            offset_y = float_h // 2

        final_x = alloc_x + padx + offset_x
        final_y = alloc_y + pady + offset_y

        child.update_geometry(final_x, final_y, final_w, final_h)


def _apply_place(container, cx, cy, cw, ch):
    """Applies absolute and relative placement for placed children."""
    place_children = [c for c in container.children if c.layout_params.get('type') == 'place']

    for child in place_children:
        params = child.layout_params
        anchor = params.get('anchor', TOPLEFT)

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

        base_x = cx + params['x']
        if params['relx'] > 0:
            base_x += int(cw * params['relx'])

        base_y = cy + params['y']
        if params['rely'] > 0:
            base_y += int(ch * params['rely'])

        if anchor in (TOPRIGHT, RIGHT, BOTTOMRIGHT):
            final_x = base_x - final_w
        elif anchor in (CENTER, TOP, BOTTOM):
            final_x = base_x - (final_w // 2)
        else:
            final_x = base_x

        if anchor in (BOTTOMLEFT, BOTTOM, BOTTOMRIGHT):
            final_y = base_y - final_h
        elif anchor in (CENTER, LEFT, RIGHT):
            final_y = base_y - (final_h // 2)
        else:
            final_y = base_y

        child.update_geometry(
            max(0, final_x),
            max(0, final_y),
            max(1, final_w),
            max(1, final_h)
        )
