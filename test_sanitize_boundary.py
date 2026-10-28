# -*- coding: utf-8 -*-
"""
Unit test for Site Boundary Engine (Approach 1: Complete 3D + 2D Lot Clipping)
"""
import math

def point_in_polygon_2d(x, y, poly_pts):
    if not poly_pts or len(poly_pts) < 3: return False
    inside = False; n = len(poly_pts); j = n - 1
    for i in range(n):
        xi, yi = poly_pts[i]; xj, yj = poly_pts[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def find_ray_polygon_interval(p_origin, u_dir, poly_pts):
    px, py = p_origin
    ux, uy = u_dir
    dists = []
    n = len(poly_pts)
    for i in range(n - 1):
        x1, y1 = poly_pts[i]
        x2, y2 = poly_pts[i+1]
        denom = ux * (y2 - y1) - uy * (x2 - x1)
        if abs(denom) > 1e-9:
            s = (ux * (y1 - py) - uy * (x1 - px)) / (-denom)
            u = ((x1 - px) * (y2 - y1) - (y1 - py) * (x2 - x1)) / denom
            if 0.0 <= s <= 1.0:
                dists.append(round(u, 3))
    dists = sorted(list(set(dists)))
    for k in range(len(dists) - 1):
        u1 = dists[k]
        u2 = dists[k+1]
        if u2 - u1 > 0.5:
            u_mid = (u1 + u2) / 2.0
            if point_in_polygon_2d(px + u_mid * ux, py + u_mid * uy, poly_pts):
                return u1, u2
    return None

# User-like lot: (20, 10), (150, 10), (140, 200), (10, 200), (30, 80), (20, 10)
lot = [(20.0, 10.0), (150.0, 10.0), (140.0, 200.0), (10.0, 200.0), (30.0, 80.0), (20.0, 10.0)]

# Calculate lot area
area = abs(sum(lot[i][0]*lot[i+1][1] - lot[i+1][0]*lot[i][1] for i in range(len(lot)-1))) * 0.5
print(f"Lot Area: {area:.2f} m² ({area/10000.0:.4f} ha)")
assert area > 20000.0

# Clip horizontal section lines at y = 20, 50, 100, 150, 180
for y in [20.0, 50.0, 100.0, 150.0, 180.0]:
    inter = find_ray_polygon_interval((0.0, y), (1.0, 0.0), lot)
    assert inter is not None
    u1, u2 = inter
    length = u2 - u1
    assert length > 100.0
    print(f"Section y={y:5.1f}m: start x={u1:6.2f}m, end x={u2:6.2f}m, net width={length:6.2f}m")

# Clip vertical axis at x = 80
inter_v = find_ray_polygon_interval((80.0, 0.0), (0.0, 1.0), lot)
assert inter_v is not None
v1, v2 = inter_v
print(f"Vertical axis x=80.0m: start y={v1:6.2f}m, end y={v2:6.2f}m, net length={v2-v1:6.2f}m")
assert round(v1, 1) == 10.0
assert round(v2, 1) == 200.0

print("All site boundary ray-clipping unit tests PASSED successfully!")
