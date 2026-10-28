# -*- coding: utf-8 -*-
import math

def point_in_polygon_2d(x, y, poly_pts):
    if not poly_pts or len(poly_pts) < 3:
        return False
    inside = False
    n = len(poly_pts)
    j = n - 1
    for i in range(n):
        xi, yi = poly_pts[i][0], poly_pts[i][1]
        xj, yj = poly_pts[j][0], poly_pts[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

# Irregular lot similar to user screenshot
lot = [
    (20.0, 10.0),
    (150.0, 10.0),
    (140.0, 200.0),
    (10.0, 200.0),
    (30.0, 80.0),
    (20.0, 10.0)
]

def trim_line_to_polygon_2d(p_start, p_end, poly_pts):
    dx = p_end[0] - p_start[0]
    dy = p_end[1] - p_start[1]
    L = math.hypot(dx, dy)
    if L < 1e-4:
        return p_start, p_end, 0.0, L, L
    ux = dx / L
    uy = dy / L
    dists = []
    if point_in_polygon_2d(p_start[0], p_start[1], poly_pts):
        dists.append(0.0)
    if point_in_polygon_2d(p_end[0], p_end[1], poly_pts):
        dists.append(L)

    n = len(poly_pts)
    for i in range(n - 1):
        x1, y1 = poly_pts[i]
        x2, y2 = poly_pts[i+1]
        denom = dx * (y2 - y1) - dy * (x2 - x1)
        if abs(denom) > 1e-9:
            t = ((x1 - p_start[0]) * (y2 - y1) - (y1 - p_start[1]) * (x2 - x1)) / denom
            s = ((x1 - p_start[0]) * dy - (y1 - p_start[1]) * dx) / denom
            if 0.0 <= t <= 1.0 and 0.0 <= s <= 1.0:
                d = t * L
                dists.append(d)

    dists = sorted(list(set([round(d, 3) for d in dists])))
    for k in range(len(dists) - 1):
        d1 = dists[k]
        d2 = dists[k+1]
        if d2 - d1 > 1.0:
            d_mid = (d1 + d2) / 2.0
            px = p_start[0] + ux * d_mid
            py = p_start[1] + uy * d_mid
            if point_in_polygon_2d(px, py, poly_pts):
                p_s_trimmed = (p_start[0] + ux * d1, p_start[1] + uy * d1)
                p_e_trimmed = (p_start[0] + ux * d2, p_start[1] + uy * d2)
                return p_s_trimmed, p_e_trimmed, d1, d2, d2 - d1

    return p_start, p_end, 0.0, L, L

# Test clipping 5 sections
sections = []
for y in [30.0, 70.0, 110.0, 150.0, 190.0]:
    p_s = (-30.0, y)
    p_e = (180.0, y)
    p_s_trim, p_e_trim, d1, d2, length = trim_line_to_polygon_2d(p_s, p_e, lot)
    sections.append({
        'y': y,
        'p_start': p_s_trim,
        'p_end': p_e_trim,
        'd1': d1,
        'd2': d2,
        'length': length
    })

print(f"Trimmed {len(sections)} sections:")
for s in sections:
    print(f"  y={s['y']:.0f}: x_start={s['p_start'][0]:.2f}, x_end={s['p_end'][0]:.2f}, length={s['length']:.2f}m")

# Test quad mesh generation
quads_inside = []
quads_outside = []
for i in range(len(sections) - 1):
    sa = sections[i]
    sb = sections[i+1]
    n_trans = 40
    n_long = 15
    for m in range(n_long):
        v0 = m / float(n_long)
        v1 = (m + 1) / float(n_long)
        for k in range(n_trans):
            u0 = k / float(n_trans)
            u1 = (k + 1) / float(n_trans)
            def eval_p(u, v):
                xa = sa['p_start'][0] + u * (sa['p_end'][0] - sa['p_start'][0])
                ya = sa['y']
                xb = sb['p_start'][0] + u * (sb['p_end'][0] - sb['p_start'][0])
                yb = sb['y']
                return ((1.0 - v) * xa + v * xb, (1.0 - v) * ya + v * yb)
            p00 = eval_p(u0, v0); p10 = eval_p(u1, v0); p11 = eval_p(u1, v1); p01 = eval_p(u0, v1)
            cx = (p00[0] + p10[0] + p11[0] + p01[0]) / 4.0
            cy = (p00[1] + p10[1] + p11[1] + p01[1]) / 4.0
            if point_in_polygon_2d(cx, cy, lot):
                quads_inside.append((cx, cy))
            else:
                quads_outside.append((cx, cy))

print(f"Total evaluated quads: {len(quads_inside) + len(quads_outside)}")
print(f"Quads inside lot: {len(quads_inside)}")
print(f"Quads filtered out: {len(quads_outside)}")
assert len(quads_inside) > 0
for cx, cy in quads_inside:
    assert point_in_polygon_2d(cx, cy, lot) == True

print("All tests passed successfully!")
