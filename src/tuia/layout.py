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

    # 1. Discover grid dimensions
    max_row = max(c.layout_params['row'] + c.layout_params['rowspan'] - 1 for c in grid_children)
    max_col = max(c.layout_params['col'] + c.layout_params['colspan'] - 1 for c in grid_children)

    row_heights = {r: 0 for r in range(max_row + 1)}
    col_widths = {c: 0 for c in range(max_col + 1)}
    row_weights = {r: 0 for r in range(max_row + 1)}
    col_weights = {c: 0 for c in range(max_col + 1)}

    # 2. Intrinsic Sizing & Weights
    for child in grid_children:
        p = child.layout_params
        r, c_idx = p['row'], p['col']
        rs, cs = p['rowspan'], p['colspan']
        
        row_weights[r] = max(row_weights[r], p.get('weighty', 0))
        col_weights[c_idx] = max(col_weights[c_idx], p.get('weightx', 0))

        # Establish base sizes from single-cell widgets
        if rs == 1:
            row_heights[r] = max(row_heights[r], child.req_height + (p['pady'] * 2))
        if cs == 1:
            col_widths[c_idx] = max(col_widths[c_idx], child.req_width + (p['padx'] * 2))

    # 3. Distribute extra space based on weights
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

    # 4. Generate absolute cell coordinates
    row_y, col_x = {0: cy}, {0: cx}
    for r in range(1, max_row + 1):
        row_y[r] = row_y[r - 1] + row_heights.get(r - 1, 0)
    for c_idx in range(1, max_col + 1):
        col_x[c_idx] = col_x[c_idx - 1] + col_widths.get(c_idx - 1, 0)

    # 5. Place widgets within assigned cells
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
    """Standard shrinking-cavity sequential layout."""
    pack_children = [c for c in container.children if c.layout_params.get('type') == 'pack']
    if not pack_children: return
    # ... [Keep your exact existing PASS 1 and PASS 2 code here from the previous step] ...
    # (Omitted here for brevity, paste the _apply_pack we wrote earlier)

def _apply_place(container, cx, cy, cw, ch):
    """Absolute math-based coordinate placement."""
    place_children = [c for c in container.children if c.layout_params.get('type') == 'place']
    # ... [Keep your exact existing _apply_place code here] ...
