"""Torsion and shear crack schematic diagram builders."""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
from matplotlib.patches import FancyArrowPatch


# ------------------------------------------------------------
#  3D Torsion/Shear Crack Helix Diagram (Unwrapped Surface)
# ------------------------------------------------------------

def proj(P, a=-0.65, b=0.28):
    """Project 3D point to 2D using camera parameters."""
    x, y, z = P
    u = x + a * y
    v = z + b * y
    return np.array([u, v], dtype=float)


def clamp_inside(val, lo, hi, eps=1e-6):
    """
    Clamp scalar OR numpy array into (lo+eps, hi-eps).
    Returns same type shape as input.
    """
    if np.isscalar(val):
        return max(lo + eps, min(hi - eps, float(val)))
    arr = np.asarray(val, dtype=float)
    return np.clip(arr, lo + eps, hi - eps)


def ray_rect_hit_2d(p, d, umin, umax, vmin, vmax, eps=1e-9):
    """
    Intersect ray p + t d (t>0) with axis-aligned rectangle [umin,umax]x[vmin,vmax].
    Returns nearest hit (t, hit_point), else (None, None).
    """
    p = np.asarray(p, float)
    d = np.asarray(d, float)

    hits = []

    # u = umin / umax
    if abs(d[0]) > eps:
        for u in (umin, umax):
            t = (u - p[0]) / d[0]
            if t > eps:
                v = p[1] + t * d[1]
                if vmin - 1e-9 <= v <= vmax + 1e-9:
                    hits.append((t, np.array([u, v], float)))

    # v = vmin / vmax
    if abs(d[1]) > eps:
        for v in (vmin, vmax):
            t = (v - p[1]) / d[1]
            if t > eps:
                u = p[0] + t * d[0]
                if umin - 1e-9 <= u <= umax + 1e-9:
                    hits.append((t, np.array([u, v], float)))

    if not hits:
        return None, None

    hits.sort(key=lambda x: x[0])
    return hits[0][0], hits[0][1]


def surface_point(x, s, B, D):
    """
    Map (x, s%P3) to 3D point on unwrapped surface.
    P3 = 2*B + D is the 3-face perimeter (roof + far wall + bottom).
    Unwrapping order: roof (0..B) -> far wall (B..B+D) -> bottom (B+D..2*B+D)
    NO near wall (Y=0) - closure is via front end face (X=0).
    Returns (x, y, z, face_name) where face_name is one of: 'roof', 'far', 'bottom'
    """
    P3 = 2.0 * B + D
    s_mod = float(s % P3)
    if s_mod < 0:
        s_mod += P3
    
    if s_mod < B:
        # (A) Roof (Z=D), from near edge to far edge
        y = s_mod
        z = D
        return np.array([x, y, z], float), 'roof'
    elif s_mod < B + D:
        # (B) Far wall (Y=B), go down
        y = B
        z = D - (s_mod - B)
        return np.array([x, y, z], float), 'far'
    else:
        # (C) Bottom (Z=0), go back toward near
        y = B - (s_mod - (B + D))
        z = 0.0
        return np.array([x, y, z], float), 'bottom'


def draw_face_label_debug(cam_a=-0.65, cam_b=0.28, L=10.0, B=3.2, D=2.4, fs=10, show_corners=True,
                           n_cracks=3, start_t_min=0.1, start_t_span=0.3, crack_lw=4.0, show_cracks=False,
                           k_slope=0.5, s0_min=0.1, theta_deg=45.0):
    """
    Draw the 3D torsion prism with unwrapped surface crack helixes.
    Uses 2D projection (not 3D matplotlib).
    """
    # 8 corners in 3D
    FBR = np.array([0, 0, 0])
    FBL = np.array([0, B, 0])
    FTR = np.array([0, 0, D])
    FTL = np.array([0, B, D])

    BBR = np.array([L, 0, 0])
    BBL = np.array([L, B, 0])
    BTR = np.array([L, 0, D])
    BTL = np.array([L, B, D])

    def P2D(P3):
        return proj(P3, a=cam_a, b=cam_b)

    # Only the 3 faces you want visible
    faces_3d = {
        "SIDE WALL (Y=0)":    [FBL, FTL, FTR, FBR],  # SAME polygon as before, NEW label
        "ROOF (Z=D)":         [FTL, BTL, BTR, FTR],  # unchanged
        "END FACE (X=0)":     [FTR, BTR, BBR, FBR],  # SAME polygon as before, NEW label
    }

    faces_2d = {name: np.array([P2D(p) for p in pts], float) for name, pts in faces_3d.items()}

    fig, ax = plt.subplots(figsize=(9, 5))

    # Draw SOLID filled faces (white, no transparency)
    for name in ["END FACE (X=0)", "ROOF (Z=D)", "SIDE WALL (Y=0)"]:
        poly = faces_2d[name]
        ax.fill(poly[:, 0], poly[:, 1], color='white', alpha=1.0, zorder=1)  # solid white
        P = np.vstack([poly, poly[0]])
        ax.plot(P[:, 0], P[:, 1], linewidth=2.2, zorder=2)

    # ------------------------------------------------------------
    # Torsion arrows on END FACE (always visible)
    # ------------------------------------------------------------
    # Always show arrows regardless of cracks
    end_poly = faces_2d["END FACE (X=0)"]  # 4 points in 2D
    cx = float(np.mean(end_poly[:, 0]))
    cy = float(np.mean(end_poly[:, 1]))

    # Use a radius based on face size
    span_u = float(np.max(end_poly[:, 0]) - np.min(end_poly[:, 0]))
    span_v = float(np.max(end_poly[:, 1]) - np.min(end_poly[:, 1]))
    r = 0.18 * min(span_u, span_v)

    def arc_arrow_ccw(a0, a1, lw=2.4):
        # CCW arc from angle a0 to a1 around centroid
        x0 = cx + r * math.cos(a0)
        y0 = cy + r * math.sin(a0)
        x1 = cx + r * math.cos(a1)
        y1 = cy + r * math.sin(a1)

        arr = FancyArrowPatch(
            (x0, y0), (x1, y1),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=lw,
            color="black",
            connectionstyle="arc3,rad=0.35",  # curved arc
            zorder=80,
        )
        ax.add_patch(arr)

    # Two CCW curved arrows (counter-clockwise)
    arc_arrow_ccw(a0=math.radians(-30), a1=math.radians(80))
    arc_arrow_ccw(a0=math.radians(150), a1=math.radians(260))

    # Optional label
    ax.text(cx, cy, "T", ha="center", va="center", fontsize=10, zorder=85)

    # Crack generation: unwrapped surface helix approach (3-face only)
    if show_cracks:
        P3_perimeter = float(2.0 * B + D)  # 3-face perimeter: roof + far wall + bottom (ensure Python float)
        epsx = 1e-3 * L
        eps = 1e-6
        
        # Sample start s0 values
        tmax = min(0.98, start_t_min + start_t_span)
        ts = np.linspace(start_t_min, tmax, max(1, int(n_cracks)))
        s0_values = [float(t * P3_perimeter) for t in ts]  # Convert to Python floats
        
        # Sample points along x for each crack
        n_samples = 200  # Number of points to sample along x
        x_samples = np.linspace(0.0, L - epsx, n_samples)
        
        def plot_seg(Pa3, Pb3, face_name, lw):
            """Plot segment with guard against forbidden Y=0 wall"""
            if Pa3 is None or Pb3 is None:
                return
            
            # Hard filter: reject ONLY pure vertical segments on the near wall (Y=0)
            # (i.e. x ~ constant but z changes). We DO want sloped drops where x changes.
            ya = abs(float(Pa3[1]))
            yb = abs(float(Pb3[1]))
            xa = float(Pa3[0])
            xb = float(Pb3[0])
            za = float(Pa3[2])
            zb = float(Pb3[2])
            
            dx = abs(xa - xb)
            dz = abs(za - zb)
            
            # If it's on y=0 AND basically no x movement AND it drops in z => reject
            if (ya < eps and yb < eps and dx < (2.0 * epsx) and dz > eps):
                return
            
            a2 = P2D(Pa3)
            b2 = P2D(Pb3)
            
            # Check if segment is on visible face
            # Visible: roof and side wall (green face x=0)
            # Green face segments have x=0, so check for that
            xa_abs = abs(float(Pa3[0]))
            xb_abs = abs(float(Pb3[0]))
            on_green_face = (xa_abs < epsx and xb_abs < epsx)
            is_visible = (face_name in ('roof', 'side') or on_green_face)
            
            if is_visible:
                ax.plot(
                    [a2[0], b2[0]],
                    [a2[1], b2[1]],
                    linewidth=lw,
                    solid_capstyle="round",
                    zorder=50,
                    color='black',
                )
            else:
                # Hidden faces: dashed line
                ax.plot(
                    [a2[0], b2[0]],
                    [a2[1], b2[1]],
                    linewidth=lw * 0.6,
                    linestyle='--',
                    alpha=0.4,
                    zorder=45,
                    color='gray',
                )
        
        for s0 in s0_values:
            # Define crack path: s(x) = s0 + k*x
            # Convert to Python floats to avoid numpy type issues
            s_values = [float(s0 + k_slope * x) for x in x_samples]
            
            # Map to 3D points and track face changes
            points_3d = []
            face_names = []
            s_mod_values = []
            
            for i, x in enumerate(x_samples):
                s = s_values[i]  # Already a Python float
                P3, face = surface_point(x, s, B, D)
                points_3d.append(P3)
                face_names.append(face)
                
                # Track s_mod to detect wraps (ensure all are Python floats)
                s_mod = float(s) % P3_perimeter
                if s_mod < 0:
                    s_mod = s_mod + P3_perimeter
                s_mod_values.append(s_mod)
            
            # Store original points_3d for this crack before building segments
            crack_points_3d = points_3d.copy()
            crack_face_names = face_names.copy()
            
            # Build polyline segments, inserting side wall continuation at wraps
            segments = []  # List of (points, face_name) tuples
            
            current_segment = [points_3d[0]]
            current_face = face_names[0]
            prev_s_mod = s_mod_values[0]
            
            for i in range(1, len(points_3d)):
                s_mod = s_mod_values[i]
                
                # Check for wrap (more bulletproof: check if integer part of s/P3 changed)
                wrap_detected = False
                prev_wrap_count = int(s_values[i-1] / P3_perimeter)
                curr_wrap_count = int(s_values[i] / P3_perimeter)
                wrap_detected = (prev_wrap_count != curr_wrap_count)
                
                if wrap_detected:
                    # Finish current segment
                    if len(current_segment) > 1:
                        segments.append((current_segment, current_face))
                    
                    # Add side wall continuation on Y=0 when wrapping
                    # Get the bottom point (last point of current segment)
                    P_bottom = current_segment[-1].copy()
                    x_bottom = float(P_bottom[0])
                    # Clamp x away from end face to ensure it stays on side wall
                    x_bottom = float(clamp_inside(x_bottom, epsx, L - epsx, eps=1e-6))
                    
                    # Get the roof point (next point after wrap)
                    P_roof_next = points_3d[i].copy()
                    x_roof = float(P_roof_next[0])
                    # Clamp x away from end face to ensure it stays on side wall
                    x_roof = float(clamp_inside(x_roof, epsx, L - epsx, eps=1e-6))
                    
                    # Continue on side wall (Y=0): slanted line from bottom to roof
                    # Start at bottom edge of side wall: (x_bottom, 0, 0)
                    # End at roof edge of side wall: (x_roof, 0, D)
                    # This creates a slanted continuation on the side wall
                    P_side_start = np.array([x_bottom, 0.0, 0.0], float)
                    P_side_end = np.array([x_roof, 0.0, D], float)
                    segments.append(([P_side_start, P_side_end], 'side'))
                    
                    # Start new segment from side wall end to next roof point
                    current_segment = [P_side_end, P_roof_next]
                    current_face = face_names[i]
                elif face_names[i] != current_face:
                    # Face boundary crossed (not a wrap): finish current segment and start new one
                    if len(current_segment) > 1:
                        segments.append((current_segment, current_face))
                    # Start new segment (include last point of previous segment for continuity)
                    current_segment = [current_segment[-1], points_3d[i]]
                    current_face = face_names[i]
                else:
                    # Same face: continue segment
                    current_segment.append(points_3d[i])
                
                prev_s_mod = s_mod
            
            # Add remaining segment
            if len(current_segment) > 1:
                segments.append((current_segment, current_face))
            
            # --- Extend each roof crack down the GREEN face (x=0) as a continuation ---
            # Green face = x=0 = "SIDE WALL (Y=0)" label (but actually x=0 plane)
            # Use the original crack_points_3d to find where roof crack hits x=0
            
            # θ is now the true physical crack angle
            theta = math.radians(theta_deg)
            tan_t = math.tan(theta)
            
            wall_drops = []
            
            # Find where this roof crack (from original points) intersects x=0
            # This ensures wall drops are directly linked to roof cracks
            roof_pts = [p for p, f in zip(crack_points_3d, crack_face_names) if f == "roof"]
            
            if len(roof_pts) >= 2:
                # Find where the roof crack crosses x=0
                hit_point = None
                
                # Search through roof points to find where it crosses x=0
                for k in range(len(roof_pts) - 1):
                    P0 = roof_pts[k]
                    P1 = roof_pts[k + 1]
                    x0, x1 = float(P0[0]), float(P1[0])
                    
                    # Check if this segment crosses x=0
                    if (x0 <= 0.0 + 1e-9 and x1 >= 0.0 - 1e-9) or (x1 <= 0.0 + 1e-9 and x0 >= 0.0 - 1e-9):
                        # Segment crosses x=0, interpolate to find exact intersection
                        if abs(x1 - x0) > 1e-12:
                            t = (0.0 - x0) / (x1 - x0)
                            t = float(np.clip(t, 0.0, 1.0))
                            y_hit = float(P0[1] + t * (P1[1] - P0[1]))
                            z_hit = float(P0[2] + t * (P1[2] - P0[2]))
                        else:
                            # Points are at same x, use the one closer to x=0
                            if abs(x0) < abs(x1):
                                y_hit = float(P0[1])
                                z_hit = float(P0[2])
                            else:
                                y_hit = float(P1[1])
                                z_hit = float(P1[2])
                        
                        hit_point = np.array([0.0, y_hit, z_hit], float)
                        break
                
                # If no crossing found, use the roof point closest to x=0
                if hit_point is None:
                    Pmin = min(roof_pts, key=lambda p: abs(float(p[0])))
                    y_min = float(Pmin[1])
                    z_min = float(Pmin[2])
                    hit_point = np.array([0.0, y_min, z_min], float)
                
                # Use the exact hit point as the start of the wall drop
                y0 = float(clamp_inside(hit_point[1], 0.0, B, eps=1e-6))
                z0 = float(clamp_inside(hit_point[2], 0.0, D, eps=1e-6))
                P_top = np.array([0.0, y0, z0], float)
                
                # Drop down green face (x=0) at angle theta: from P_top to bottom edge
                # In y-z plane: z = z0 - (y-y0)*tan(theta)  [going from y0 away from end wall, towards y=B]
                # To reach z=0: y_end = y0 + z0/tan(theta)  [moving towards y=B, away from end wall]
                if tan_t < 1e-9:
                    y_end = y0  # almost vertical
                else:
                    y_end = y0 + (z0 / tan_t)  # move towards y=B, away from end wall
                
                # Clamp y_end to stay within beam [0, B]
                y_end = float(clamp_inside(y_end, 0.0, B, eps=1e-6))
                z_end = float(max(0.0, z0 - (y_end - y0) * tan_t))
                
                P_bot = np.array([0.0, y_end, z_end], float)
                
                # Continue back up at the same angle, still moving away from end wall (toward y=B)
                # From P_bot (0, y_end, z_end) go up at angle theta
                # z = z_end + (y - y_end)*tan(theta), moving toward y=B
                # To reach z=D: y_up = y_end + (D - z_end)/tan(theta)
                if tan_t < 1e-9:
                    y_up = y_end  # almost vertical
                else:
                    y_up = y_end + ((D - z_end) / tan_t)  # continue toward y=B, away from end wall
                
                # Clamp y_up to stay within beam [0, B]
                y_up = float(clamp_inside(y_up, 0.0, B, eps=1e-6))
                z_up = float(min(D, z_end + (y_up - y_end) * tan_t))
                
                P_up = np.array([0.0, y_up, z_up], float)
                
                # Add the angled drop and rise on green face (x=0) - directly linked to roof crack
                # First segment: down from roof to bottom
                wall_drops.append(([P_top, P_bot], "side"))
                # Second segment: back up from bottom
                wall_drops.append(([P_bot, P_up], "side"))
                
                # Extend back onto roof at the same angle magnitude but away from end wall
                # The roof crack follows s(x) = s0 + k*x, so we continue from x=0
                # Find where we are in the s parameter space when we hit x=0
                # On the roof edge at x=0, y determines s: s = y (since roof is s_mod < B)
                s_at_x0 = float(y_up)  # On roof, s_mod = y
                
                # Use the same angle magnitude (abs(k_slope)) but ensure direction is away from end wall
                # Since we're at y_up (away from y=0), we want to continue increasing y (positive direction)
                # So use positive k_slope magnitude
                k_extend = abs(k_slope)  # Use absolute value to move away from end wall
                
                # Continue the roof crack by sampling x values from 0 to L (BTR/BTL edge)
                # Use k_extend to continue: s(x) = s_at_x0 + k_extend * x (moving away from end wall)
                # Sample points to extend the roof crack all the way to x=L
                n_roof_extend = 100
                x_extend = np.linspace(epsx, L - epsx, n_roof_extend)  # Extend all the way to back edge
                roof_extend_points = []
                
                for x_ext in x_extend:
                    s_ext = s_at_x0 + k_extend * x_ext  # Positive k ensures movement away from end wall
                    P_roof, face_roof = surface_point(x_ext, s_ext, B, D)
                    if face_roof == 'roof':
                        roof_extend_points.append(P_roof)
                    else:
                        # If we've left the roof, we've reached the edge - find the intersection
                        # The last roof point should be close to the edge
                        if len(roof_extend_points) > 0:
                            break
                
                # Ensure we reach the back edge (x=L)
                # Find the last point and extend it to x=L if needed
                if len(roof_extend_points) >= 2:
                    last_roof_pt = roof_extend_points[-1]
                    x_last = float(last_roof_pt[0])
                    
                    # If we haven't reached x=L, add a point at the back edge
                    if x_last < L - epsx:
                        # Interpolate to find y at x=L
                        if len(roof_extend_points) >= 2:
                            P0 = roof_extend_points[-2]
                            P1 = roof_extend_points[-1]
                            x0, x1 = float(P0[0]), float(P1[0])
                            if abs(x1 - x0) > 1e-12:
                                t = (L - epsx - x0) / (x1 - x0)
                                t = float(np.clip(t, 0.0, 1.0))
                                y_edge = float(P0[1] + t * (P1[1] - P0[1]))
                                y_edge = float(clamp_inside(y_edge, 0.0, B, eps=1e-6))
                            else:
                                y_edge = float(clamp_inside(float(P1[1]), 0.0, B, eps=1e-6))
                        else:
                            y_edge = float(clamp_inside(float(last_roof_pt[1]), 0.0, B, eps=1e-6))
                        
                        P_edge = np.array([L - epsx, y_edge, D], float)
                        roof_extend_points.append(P_edge)
                
                if len(roof_extend_points) >= 2:
                    # Create roof continuation segment starting from P_up (projected to roof)
                    P_roof_start = np.array([0.0, y_up, D], float)  # Start at roof edge where we came up
                    roof_segment = [P_roof_start] + roof_extend_points
                    wall_drops.append((roof_segment, "roof"))
                    
                    # Extend back to the top of green wall using the same angle as first roof cracks (k_slope)
                    # Start from the back edge (last point of roof extension)
                    P_back_edge = roof_extend_points[-1]
                    x_back = float(P_back_edge[0])
                    y_back = float(P_back_edge[1])
                    
                    # Use original k_slope (which may be negative) to go back toward x=0
                    # s(x) = s_back + k_slope * (x - x_back)
                    # At x=L, s = y_back (on roof, s = y)
                    s_at_back = float(y_back)
                    
                    # Sample x values going back from L to 0
                    n_roof_return = 100
                    x_return = np.linspace(L - epsx, epsx, n_roof_return)  # From back edge to front edge
                    roof_return_points = []
                    
                    for x_ret in x_return:
                        # Use original k_slope to go back (negative k_slope will make it go back)
                        s_ret = s_at_back + k_slope * (x_ret - x_back)
                        P_roof_ret, face_roof_ret = surface_point(x_ret, s_ret, B, D)
                        if face_roof_ret == 'roof':
                            roof_return_points.append(P_roof_ret)
                        else:
                            # If we've left the roof, we've reached the edge
                            if len(roof_return_points) > 0:
                                break
                    
                    # Ensure we reach the front edge (x=0)
                    if len(roof_return_points) >= 2:
                        last_return_pt = roof_return_points[-1]
                        x_last_ret = float(last_return_pt[0])
                        
                        # If we haven't reached x=0, add a point at the front edge
                        if x_last_ret > epsx:
                            # Interpolate to find y at x=0
                            if len(roof_return_points) >= 2:
                                P0_ret = roof_return_points[-2]
                                P1_ret = roof_return_points[-1]
                                x0_ret, x1_ret = float(P0_ret[0]), float(P1_ret[0])
                                if abs(x1_ret - x0_ret) > 1e-12:
                                    t = (epsx - x0_ret) / (x1_ret - x0_ret)
                                    t = float(np.clip(t, 0.0, 1.0))
                                    y_front = float(P0_ret[1] + t * (P1_ret[1] - P0_ret[1]))
                                    y_front = float(clamp_inside(y_front, 0.0, B, eps=1e-6))
                                else:
                                    y_front = float(clamp_inside(float(P1_ret[1]), 0.0, B, eps=1e-6))
                            else:
                                y_front = float(clamp_inside(float(last_return_pt[1]), 0.0, B, eps=1e-6))
                            
                            P_front_edge = np.array([epsx, y_front, D], float)
                            roof_return_points.append(P_front_edge)
                        
                        # Create roof return segment
                        roof_return_segment = roof_return_points
                        wall_drops.append((roof_return_segment, "roof"))
                        
                        # Add another down segment on green wall from the front edge
                        # Start point is where we hit x=0 on the roof
                        P_top2 = roof_return_points[-1].copy()
                        P_top2[0] = 0.0  # Ensure x=0
                        y0_2 = float(clamp_inside(P_top2[1], 0.0, B, eps=1e-6))
                        z0_2 = float(clamp_inside(P_top2[2], 0.0, D, eps=1e-6))
                        P_top2 = np.array([0.0, y0_2, z0_2], float)
                        
                        # Drop down green face (x=0) at angle theta, away from end wall
                        if tan_t < 1e-9:
                            y_end2 = y0_2  # almost vertical
                        else:
                            y_end2 = y0_2 + (z0_2 / tan_t)  # move towards y=B, away from end wall
                        
                        # Clamp y_end2 to stay within beam [0, B]
                        y_end2 = float(clamp_inside(y_end2, 0.0, B, eps=1e-6))
                        z_end2 = float(max(0.0, z0_2 - (y_end2 - y0_2) * tan_t))
                        
                        P_bot2 = np.array([0.0, y_end2, z_end2], float)
                        
                        # Add the second angled drop on green face (x=0)
                        wall_drops.append(([P_top2, P_bot2], "side"))
            
            segments.extend(wall_drops)
            
            # Plot all segments
            for segment_points, seg_face in segments:
                for j in range(len(segment_points) - 1):
                    plot_seg(segment_points[j], segment_points[j+1], seg_face, crack_lw)

    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.margins(0.10)
    return fig


def plot_shear_step1_theta_cracks_3d(
    L_mm: float,
    b_mm: float,
    D_mm: float,
    theta_deg: float = 45.0,
    cam_a: float = -0.65,
    cam_b: float = 0.28,
    n_cracks: int = 3,
    start_t_min: float = 0.10,
    start_t_span: float = 0.06,
    crack_lw: float = 4.0,
    show_cracks: bool = True,
):
    """
    Step 1 Shear diagram: 3D 'unwrapped helix' crack sketch as a pure matplotlib figure.
    
    Uses θ (degrees) as the physical crack angle; internally k = -tan(θ).
    
    Note: Geometry mapping matches torsion app:
      - model_L (X axis) = b_mm (breadth)
      - model_B (Y axis) = L_mm (length) 
      - model_D (Z axis) = D_mm (depth)
    
    Args:
        L_mm: Beam length in mm (maps to model_B, Y axis)
        b_mm: Beam width (breadth) in mm (maps to model_L, X axis)
        D_mm: Beam depth in mm (maps to model_D, Z axis)
        theta_deg: Physical crack angle in degrees (default 45.0)
        cam_a: Camera horizontal rotation parameter (default -0.65)
        cam_b: Camera vertical elevation parameter (default 0.28)
        n_cracks: Number of crack helixes to draw
        start_t_min: Starting position for first crack (normalized 0-1)
        start_t_span: Span between crack starts (normalized 0-1)
        crack_lw: Crack line width
        show_cracks: Whether to show cracks
    
    Returns:
        matplotlib.figure.Figure: The 3D diagram figure
    """
    # Scale mm -> meters so the drawing stays numerically sane
    # Swap L and B to match torsion app mapping:
    # model_L (X) = b_mm, model_B (Y) = L_mm, model_D (Z) = D_mm
    L = float(b_mm) / 1000.0  # model length axis X = breadth
    B = float(L_mm) / 1000.0   # model breadth axis Y = length
    D = float(D_mm) / 1000.0   # model depth axis Z = depth
    
    theta_deg = float(theta_deg)
    k_slope = -math.tan(math.radians(theta_deg))
    
    fig = draw_face_label_debug(
        cam_a=float(cam_a),
        cam_b=float(cam_b),
        L=float(L),
        B=float(B),
        D=float(D),
        fs=9,
        show_corners=False,
        n_cracks=int(n_cracks),
        start_t_min=float(start_t_min),
        start_t_span=float(start_t_span),
        crack_lw=float(crack_lw),
        show_cracks=bool(show_cracks),
        k_slope=float(k_slope),
        s0_min=float(start_t_min),
        theta_deg=float(theta_deg),
    )
    return fig


def _torsion_section_perimeter(L: float, D: float) -> float:
    """Rectangular section perimeter in the x–z plane (breadth L, depth D)."""
    return 2.0 * float(L) + 2.0 * float(D)


def _torsion_xz_from_unwrapped_s(s: float, L: float, D: float) -> tuple[float, float]:
    """
    Map unwrapped perimeter coordinate s onto the section outline in the x–z plane.

    Origin s = 0 at (0, 0); trace: bottom z=0 from x=0→L, far vertical x=L z=0→D,
    top z=D from x=L→0, near vertical x=0 z=D→0. Period P = 2L + 2D.
    """
    L = float(L)
    D = float(D)
    P = _torsion_section_perimeter(L, D)
    u = float(s) % P
    if u < 0:
        u += P
    if u < L:
        return u, 0.0
    u -= L
    if u < D:
        return L, u
    u -= L
    if u < L:
        return L - u, D
    u -= L
    return 0.0, D - u


def _torsion_on_visible_skin(
    x: float,
    y: float,
    z: float,
    L: float,
    B: float,
    D: float,
    tol: float,
) -> bool:
    """Point on union of drawn faces: roof z=D, end y=0, near lateral x=0."""
    if (
        abs(z - D) <= tol
        and -tol <= x <= L + tol
        and -tol <= y <= B + tol
    ):
        return True
    if (
        abs(y) <= tol
        and -tol <= x <= L + tol
        and -tol <= z <= D + tol
    ):
        return True
    if (
        abs(x) <= tol
        and -tol <= y <= B + tol
        and -tol <= z <= D + tol
    ):
        return True
    return False


def _bisect_first_visible_y(
    y_a: float,
    y_b: float,
    vis_at,
    *,
    max_iter: int = 56,
) -> float:
    """
    Assume vis_at(y_a) is False and vis_at(y_b) is True (or y_a already visible).
    Return the infimum y in [y_a, y_b] where the band becomes visible — i.e. the
    true left boundary of a visible run (face edge / occlusion boundary).
    """
    if vis_at(y_a):
        return float(y_a)
    if not vis_at(y_b):
        return float(y_b)
    lo, hi = float(y_a), float(y_b)
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if vis_at(mid):
            hi = mid
        else:
            lo = mid
    return float(hi)


def _bisect_last_visible_y(
    y_a: float,
    y_b: float,
    vis_at,
    *,
    max_iter: int = 56,
) -> float:
    """
    Assume vis_at(y_a) is True and vis_at(y_b) is False.
    Return the supremum y in [y_a, y_b] where the band stays visible — i.e. the
    true right boundary of a visible run.
    """
    if vis_at(y_b):
        return float(y_b)
    if not vis_at(y_a):
        return float(y_a)
    lo, hi = float(y_a), float(y_b)
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if vis_at(mid):
            lo = mid
        else:
            hi = mid
    return float(lo)


def _torsion_band_projected_polyline(
    L: float,
    B: float,
    D: float,
    c: float,
    m: float,
    cam_a: float,
    cam_b: float,
    *,
    n_samples: int = 520,
    stylize_strength: float = 1.0,
    band_phase: float = 0.0,
    end_trim_frac: float = 0.0,
) -> tuple[list[float | None], list[float | None]]:
    """
    One developed-surface band: unwrapped law s = m*y + c (y = beam length),
    mapped to skin (x,z) = f(s mod P), kept only where the union of visible
    faces is hit. Endpoints of each visible run are refined by bisection to the
    exact visibility boundary (no inset from discrete sampling). None breaks
    runs across hidden bottom/far faces only (not at face changes). A tiny,
    deterministic in-plane jitter is applied to interior points only so traces
    read as cracks while preserving edge hits and wrapped continuity.
    """
    B = float(B)
    y0 = min(max(0.0, float(end_trim_frac)) * B, 0.08 * B)
    ys = np.linspace(y0, B, int(max(48, n_samples)))
    tol = max(1e-12, min(L, D, B if B > 1e-12 else L) * 6e-6)

    def vis_at(yv: float) -> bool:
        s_lin = m * float(yv) + float(c)
        x, z = _torsion_xz_from_unwrapped_s(s_lin, L, D)
        return _torsion_on_visible_skin(x, float(yv), z, L, B, D, tol)

    def proj_y(yv: float) -> tuple[float, float]:
        s_lin = m * float(yv) + float(c)
        x, z = _torsion_xz_from_unwrapped_s(s_lin, L, D)
        p2 = proj(np.array([x, float(yv), z], dtype=float), a=cam_a, b=cam_b)
        return float(p2[0]), float(p2[1])

    vis = np.array([vis_at(float(y)) for y in ys], dtype=bool)
    runs: list[tuple[int, int]] = []
    k = 0
    n = len(ys)
    while k < n:
        if not vis[k]:
            k += 1
            continue
        k0 = k
        while k + 1 < n and vis[k + 1]:
            k += 1
        runs.append((k0, k))
        k += 1

    ydup = max(1e-12, B * 1e-10)
    crack_jitter_amp = min(L, D) * 0.0062 * max(0.0, float(stylize_strength))

    xs_out: list[float | None] = []
    ys_out: list[float | None] = []
    for ri, (i, j) in enumerate(runs):
        # Refined span along beam axis (exact visibility boundaries).
        if i > 0:
            y_left = _bisect_first_visible_y(float(ys[i - 1]), float(ys[i]), vis_at)
        else:
            y_left = 0.0 if vis_at(0.0) else _bisect_first_visible_y(0.0, float(ys[0]), vis_at)

        if j + 1 < n:
            y_right = _bisect_last_visible_y(float(ys[j]), float(ys[j + 1]), vis_at)
        else:
            y_right = B if vis_at(B) else _bisect_last_visible_y(float(ys[j]), B, vis_at)

        if y_right < y_left:
            y_left, y_right = y_right, y_left

        y_seq: list[float] = [y_left]
        for idx in range(i, j + 1):
            yy = float(ys[idx])
            if yy > y_left + ydup and yy < y_right - ydup:
                if not y_seq or abs(yy - y_seq[-1]) > ydup:
                    y_seq.append(yy)
        if not y_seq or abs(y_right - y_seq[-1]) > ydup:
            y_seq.append(y_right)
        else:
            y_seq[-1] = y_right

        merged: list[float] = []
        for yy in y_seq:
            if not merged or abs(yy - merged[-1]) > ydup * 0.5:
                merged.append(yy)
            else:
                merged[-1] = yy

        run_xy: list[tuple[float, float]] = []
        for yy in merged:
            run_xy.append(proj_y(yy))

        if len(run_xy) >= 3 and crack_jitter_amp > 1e-12:
            # Cumulative arclength lets jitter follow local line direction.
            s_acc = [0.0]
            for kk in range(1, len(run_xy)):
                dx = run_xy[kk][0] - run_xy[kk - 1][0]
                dy = run_xy[kk][1] - run_xy[kk - 1][1]
                s_acc.append(s_acc[-1] + math.hypot(dx, dy))
            s_tot = max(s_acc[-1], 1e-12)
            stylized: list[tuple[float, float]] = [run_xy[0]]
            for kk in range(1, len(run_xy) - 1):
                x0, y0 = run_xy[kk]
                x_prev, y_prev = run_xy[kk - 1]
                x_next, y_next = run_xy[kk + 1]
                tx = x_next - x_prev
                ty = y_next - y_prev
                lt = math.hypot(tx, ty)
                if lt < 1e-12:
                    stylized.append((x0, y0))
                    continue
                nx = -ty / lt
                ny = tx / lt
                t = s_acc[kk] / s_tot
                # Envelope is zero at both ends to keep exact face-edge endpoints.
                env = math.sin(math.pi * t)
                wav = 0.58 * math.sin(2.0 * math.pi * (1.12 * t + 0.17 * band_phase))
                wav += 0.34 * math.sin(2.0 * math.pi * (2.85 * t + 0.31 * band_phase + 0.18))
                wav += 0.18 * math.sin(2.0 * math.pi * (4.15 * t + 0.08 * band_phase + 0.41))
                off = crack_jitter_amp * env * wav
                stylized.append((x0 + off * nx, y0 + off * ny))
            stylized.append(run_xy[-1])
            run_xy = stylized

        for uu, vv in run_xy:
            xs_out.append(uu)
            ys_out.append(vv)

        if ri < len(runs) - 1:
            xs_out.append(None)
            ys_out.append(None)

    while xs_out and xs_out[-1] is None:
        xs_out.pop()
        ys_out.pop()
    return xs_out, ys_out


def _torsion_y_interval_near_lateral_leg(
    c: float,
    m: float,
    L: float,
    B: float,
    D: float,
) -> tuple[float, float] | None:
    """y-range with s=m*y+c on fourth perimeter leg [2L+D, P]."""
    if m <= 1e-15:
        return None
    P = _torsion_section_perimeter(L, D)
    y_lo = max(0.0, (2 * L + D - c) / m)
    y_hi = min(float(B), (P - c) / m)
    if y_hi - y_lo <= max(1e-9 * B, 1e-10):
        return None
    return (y_lo, y_hi)


def _torsion_dxz_ds(s: float, L: float, D: float) -> tuple[float, float]:
    """Derivative (dx/ds, dz/ds) along the rectangular perimeter path (unit speed in s)."""
    L = float(L)
    D = float(D)
    P = _torsion_section_perimeter(L, D)
    u = float(s) % P
    if u < 0:
        u += P
    eps = 1e-12
    if u < L - eps:
        return 1.0, 0.0
    if u < L + D - eps:
        return 0.0, 1.0
    if u < 2 * L + D - eps:
        return -1.0, 0.0
    return 0.0, -1.0


def _torsion_theta_marker_on_lateral(
    L: float,
    B: float,
    D: float,
    c_band: float,
    m: float,
    theta_deg: float,
    cam_a: float,
    cam_b: float,
    *,
    y_frac: float = 0.42,
) -> tuple[list[go.Scatter] | None, list[dict] | None]:
    """
    θ on near lateral (x≈0): developed law s = m*y + c_band; axis vs crack tangent.
    """
    iv = _torsion_y_interval_near_lateral_leg(c_band, m, L, B, D)
    if iv is None:
        return None, None
    y1, y2 = iv
    y0 = y1 + (y2 - y1) * y_frac
    s = m * y0 + c_band
    x, z = _torsion_xz_from_unwrapped_s(s, L, D)
    if abs(x) > max(1e-6, 2e-4 * L):
        return None, None
    dz_dy = -m
    len_ref = min(B, D) * 0.165
    p0 = np.array([0.0, y0, z], dtype=float)
    p_axis = np.array([0.0, y0 + len_ref, z], dtype=float)
    p_crack = np.array([0.0, y0 + len_ref, z + len_ref * dz_dy], dtype=float)

    v0 = proj(p0, a=cam_a, b=cam_b)
    va = proj(p_axis, a=cam_a, b=cam_b)
    vc = proj(p_crack, a=cam_a, b=cam_b)
    ex = np.array([va[0] - v0[0], va[1] - v0[1]], dtype=float)
    ec = np.array([vc[0] - v0[0], vc[1] - v0[1]], dtype=float)
    le = math.hypot(ex[0], ex[1])
    lc = math.hypot(ec[0], ec[1])
    if le < 1e-12 or lc < 1e-12:
        return None, None
    ex /= le
    ec /= lc
    ang0 = math.atan2(ex[1], ex[0])
    ang1 = math.atan2(ec[1], ec[0])
    d_ang = ang1 - ang0
    while d_ang <= -math.pi:
        d_ang += 2 * math.pi
    while d_ang > math.pi:
        d_ang -= 2 * math.pi
    if abs(d_ang) < 0.04:
        return None, None

    r_arc = min(B, D) * 0.095
    n_arc = 40
    arc_x: list[float] = []
    arc_y: list[float] = []
    for i in range(n_arc + 1):
        t = i / n_arc
        ang = ang0 + t * d_ang
        arc_x.append(float(v0[0]) + r_arc * math.cos(ang))
        arc_y.append(float(v0[1]) + r_arc * math.sin(ang))

    traces = [
        go.Scatter(
            x=[float(v0[0]), float(va[0])],
            y=[float(v0[1]), float(va[1])],
            mode="lines",
            line=dict(width=1.45, color="rgba(45,45,45,0.82)", dash="dot"),
            hoverinfo="skip",
            showlegend=False,
        ),
        go.Scatter(
            x=[float(v0[0]), float(vc[0])],
            y=[float(v0[1]), float(vc[1])],
            mode="lines",
            line=dict(width=1.55, color="rgba(25,25,25,0.92)"),
            hoverinfo="skip",
            showlegend=False,
        ),
        go.Scatter(
            x=arc_x,
            y=arc_y,
            mode="lines",
            line=dict(width=1.5, color="rgba(30,30,30,0.9)"),
            hoverinfo="skip",
            showlegend=False,
        ),
    ]
    bis = ang0 + 0.5 * d_ang
    off = r_arc * 1.75
    lx = float(v0[0]) + off * math.cos(bis)
    ly = float(v0[1]) + off * math.sin(bis)
    ann = [
        dict(
            x=lx,
            y=ly,
            text="θ",
            showarrow=False,
            font=dict(size=15, color="rgba(20,20,20,0.98)"),
            xref="x",
            yref="y",
        )
    ]
    return traces, ann


def _torsion_theta_marker_on_bottom_edge(
    L: float,
    B: float,
    D: float,
    c_band: float,
    m: float,
    cam_a: float,
    cam_b: float,
    *,
    subdued: bool = False,
) -> tuple[list[go.Scatter] | None, list[dict] | None]:
    """
    θ at the projected corner wedge where the representative crack meets the
    bottom outline: 3D vertex (0, y_edge, 0) with s = m*y + c = P (wrap onto
    bottom at x=0). Edge ray = beam axis along the visible bottom front (x=0,
    z=0, +y); crack ray = bottom-face tangent (dx/dy=m, +y). Arc and label sit
    in the acute wedge in projection (engineering angle style).
    """
    if m <= 1e-15:
        return None, None
    P = _torsion_section_perimeter(L, D)
    y_raw = (P - c_band) / m
    # Clamp to visible bottom front edge so θ still draws if (P−c)/m is off-span.
    y_edge = min(float(B), max(0.0, float(y_raw)))
    len_base = max(min(B, D) * 0.13, 0.07 * min(B, D), 1e-4)
    span_up = max(0.0, float(B) - y_edge)
    span_dn = max(0.0, y_edge)
    # Avoid degenerate rays when y_edge sits at an end of the beam (was hiding θ).
    if span_up >= span_dn:
        h_edge = min(len_base, max(1e-5, span_up) * 0.92)
        p0 = np.array([0.0, y_edge, 0.0], dtype=float)
        p_edge = np.array([0.0, y_edge + h_edge, 0.0], dtype=float)
        h_c = min(len_base, max(1e-5, span_up) * 0.92)
        p_crack = np.array([0.78 * h_c * m, y_edge + h_c, 0.0], dtype=float)
    else:
        h_edge = min(len_base, max(1e-5, span_dn) * 0.92)
        p0 = np.array([0.0, y_edge, 0.0], dtype=float)
        p_edge = np.array([0.0, y_edge - h_edge, 0.0], dtype=float)
        h_c = min(len_base, max(1e-5, span_dn) * 0.92)
        p_crack = np.array([-0.78 * h_c * m, y_edge - h_c, 0.0], dtype=float)

    v0 = proj(p0, a=cam_a, b=cam_b)
    va = proj(p_edge, a=cam_a, b=cam_b)
    vc = proj(p_crack, a=cam_a, b=cam_b)
    ex = np.array([va[0] - v0[0], va[1] - v0[1]], dtype=float)
    ec = np.array([vc[0] - v0[0], vc[1] - v0[1]], dtype=float)
    le = math.hypot(ex[0], ex[1])
    lc = math.hypot(ec[0], ec[1])
    if le < 1e-12 or lc < 1e-12:
        return None, None
    ex /= le
    ec /= lc
    ang_edge = math.atan2(ex[1], ex[0])
    ang_crack = math.atan2(ec[1], ec[0])
    d_ang = ang_crack - ang_edge
    while d_ang <= -math.pi:
        d_ang += 2 * math.pi
    while d_ang > math.pi:
        d_ang -= 2 * math.pi
    # Smaller (acute) wedge between the two rays in the corner.
    if abs(d_ang) > 0.5 * math.pi + 1e-6:
        d_ang = math.copysign(math.pi - abs(d_ang), d_ang)
    cross_z = ex[0] * ec[1] - ex[1] * ec[0]
    if abs(d_ang) < 0.04:
        # Nearly parallel in projection: still show a readable wedge.
        d_ang = math.copysign(max(0.14, math.radians(10.0)), cross_z if abs(cross_z) > 1e-9 else 1.0)

    ang0 = ang_edge
    r_arc = min(B, D) * (0.078 if subdued else 0.09)
    bis = ang0 + 0.5 * d_ang
    off = r_arc * (1.36 if subdued else 1.42)
    lx = float(v0[0]) + off * math.cos(bis)
    ly = float(v0[1]) + off * math.sin(bis)
    # Other side of the representative crack line (reflect across ray along ec).
    wx, wy = lx - float(v0[0]), ly - float(v0[1])
    proj_len = wx * ec[0] + wy * ec[1]
    lx = float(v0[0]) + 2.0 * proj_len * ec[0] - wx
    ly = float(v0[1]) + 2.0 * proj_len * ec[1] - wy
    # Slight push toward +u (to the right in the figure).
    nudge_u = min(B, D) * (0.032 if subdued else 0.038)
    lx += nudge_u
    # θ label: farther right and lower (projection coords: +x right, −y down).
    _scale = min(B, D)
    lx += _scale * (0.118 if subdued else 0.136)
    ly -= _scale * (0.088 if subdued else 0.104)

    tf = 15 if subdued else 20
    # θ only: no arc, edge ray, or crack tick (avoids stray segments at the beam corner).
    traces = [
        go.Scatter(
            x=[lx],
            y=[ly],
            mode="text",
            text=["\u03b8"],
            textposition="middle center",
            textfont=dict(
                size=tf,
                color="rgba(70,70,70,0.95)" if subdued else "rgba(8,8,8,1)",
                family="Arial, DejaVu Sans, sans-serif",
            ),
            hoverinfo="skip",
            showlegend=False,
            cliponaxis=False,
        ),
    ]
    return traces, None


def build_torsion_plotly_figure(
    *,
    torsion_design_required: bool = True,
    L_mm: float | None = None,
    b_mm: float | None = None,
    D_mm: float | None = None,
    theta_crack_deg: float = 45.0,
    cam_a: float = -0.65,
    cam_b: float = 0.28,
) -> go.Figure:
    """
    Pseudo-3D torsion schematic using the same oblique ``proj`` as
    ``draw_face_label_debug`` / ``plot_shear_step1_theta_cracks_3d``.

    Parallel bands ``s = m·y + c`` on the developed strip (``y`` = beam length,
    ``m = tan θ``): each band is sampled along ``y``, mapped with ``(x,z) = f(s mod P)``,
    and only visible stretches are drawn as one polyline—no per-face stitching.

    Model axes (metres): x = breadth *b*, y = span *L*, z = depth *D*.

    When torsion design is not required, keep a lighter/fewer wrapped crack set
    for schematic continuity, with a subdued θ marker.
    """
    L_span_mm = float(L_mm if L_mm is not None else 8000.0)
    b_use_mm = float(b_mm if b_mm is not None else 400.0)
    D_use_mm = float(D_mm if D_mm is not None else 600.0)

    L = b_use_mm / 1000.0
    B = L_span_mm / 1000.0
    D = D_use_mm / 1000.0

    theta_use = min(55.0, max(30.0, float(theta_crack_deg)))
    slope_ds_dy = math.tan(math.radians(theta_use))

    if torsion_design_required:
        n_bands = 5
        crack_lw = 1.85
        crack_color = "rgba(14,14,14,0.94)"
        crack_stylize_strength = 1.0
    else:
        n_bands = 3
        crack_lw = 1.12
        crack_color = "rgba(70,70,70,0.42)"
        crack_stylize_strength = 0.55

    # Visible faces (same corner semantics as draw_face_label_debug in this module).
    faces_3d = {
        "end_x0": np.array([[0, B, 0], [0, B, D], [0, 0, D], [0, 0, 0]], dtype=float),
        "roof": np.array([[0, B, D], [L, B, D], [L, 0, D], [0, 0, D]], dtype=float),
        "side_y0": np.array([[0, 0, D], [L, 0, D], [L, 0, 0], [0, 0, 0]], dtype=float),
    }
    draw_order = ["end_x0", "roof", "side_y0"]

    faces_2d = {
        name: np.array([proj(p, a=cam_a, b=cam_b) for p in pts], dtype=float)
        for name, pts in faces_3d.items()
    }

    fig = go.Figure()
    xs_all: list[float] = []
    ys_all: list[float] = []

    edge_color = "#222222"
    for name in draw_order:
        poly = faces_2d[name]
        xs = np.append(poly[:, 0], poly[0, 0])
        ys = np.append(poly[:, 1], poly[0, 1])
        xs_all.extend(xs.tolist())
        ys_all.extend(ys.tolist())
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                fill="toself",
                fillcolor="rgba(255,255,255,1)",
                mode="lines",
                line=dict(color=edge_color, width=2.2),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    P = _torsion_section_perimeter(L, D)

    if n_bands > 0:
        for i in range(n_bands):
            c = (i + 0.5) * P / n_bands
            tx, ty = _torsion_band_projected_polyline(
                L,
                B,
                D,
                c,
                slope_ds_dy,
                cam_a,
                cam_b,
                n_samples=560,
                stylize_strength=crack_stylize_strength,
                band_phase=c / max(P, 1e-12),
                end_trim_frac=0.016 if torsion_design_required else 0.012,
            )
            if not tx or all(v is None for v in tx):
                continue
            xs_all.extend([v for v in tx if v is not None])
            ys_all.extend([v for v in ty if v is not None])
            fig.add_trace(
                go.Scatter(
                    x=tx,
                    y=ty,
                    mode="lines",
                    line=dict(width=crack_lw, color=crack_color),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        c_theta = None
        best_c: float | None = None
        best_pen = float("inf")
        for i in range(n_bands):
            c = (i + 0.5) * P / n_bands
            y_bot = (P - c) / max(slope_ds_dy, 1e-12)
            if 0.0 <= y_bot <= B:
                c_theta = c
                break
            if y_bot < 0.0:
                pen = -y_bot
            else:
                pen = max(0.0, y_bot - B)
            if pen < best_pen:
                best_pen = pen
                best_c = c
        if c_theta is None and best_c is not None:
            c_theta = best_c
        if c_theta is not None:
            tr_th, ann_th = _torsion_theta_marker_on_bottom_edge(
                L,
                B,
                D,
                c_theta,
                slope_ds_dy,
                cam_a,
                cam_b,
                subdued=not torsion_design_required,
            )
            if tr_th:
                for t in tr_th:
                    fig.add_trace(t)
                    xs_all.extend([v for v in t.x if v is not None])
                    ys_all.extend([v for v in t.y if v is not None])
            if ann_th:
                for ad in ann_th:
                    fig.add_annotation(ad)
                    if ad.get("x") is not None and ad.get("y") is not None:
                        xs_all.append(float(ad["x"]))
                        ys_all.append(float(ad["y"]))

    # Torsion symbol on right visible face (y = 0), in the x–z plane.
    cx_face, cz_face = 0.52 * L, 0.48 * D
    r = 0.145 * min(L, D)
    # Two compact curved arrows wrapped around T (no detached semicircle).
    arc_specs = [(0.35, 2.45), (3.55, 5.65)]
    arr_lw = 2.4 if torsion_design_required else 1.5
    arr_color = "#1a1a1a" if torsion_design_required else "rgba(60,60,60,0.55)"
    ah_len = 0.055 * min(B, D)
    ah_ang = 0.55
    for a0, a1 in arc_specs:
        ang = np.linspace(float(a0), float(a1), max(16, int(24 * (a1 - a0))))
        arc_pts = []
        for t in ang:
            xp = cx_face + r * math.cos(t)
            zp = cz_face + r * math.sin(t)
            p2 = proj(np.array([xp, 0.0, zp], dtype=float), a=cam_a, b=cam_b)
            arc_pts.append((float(p2[0]), float(p2[1])))
        xs_a = [p[0] for p in arc_pts]
        ys_a = [p[1] for p in arc_pts]
        xs_all.extend(xs_a)
        ys_all.extend(ys_a)
        fig.add_trace(
            go.Scatter(
                x=xs_a,
                y=ys_a,
                mode="lines",
                line=dict(width=arr_lw, color=arr_color),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        # Arrowhead at arc end using two short wing segments (engineering-clean).
        x_end = cx_face + r * math.cos(a1)
        z_end = cz_face + r * math.sin(a1)
        # Tangent direction for increasing angle.
        tx = -math.sin(a1)
        tz = math.cos(a1)
        tnorm = max(math.hypot(tx, tz), 1e-12)
        tx /= tnorm
        tz /= tnorm
        for sgn in (-1.0, 1.0):
            wx = x_end - ah_len * (tx * math.cos(ah_ang) + sgn * math.sin(ah_ang))
            wz = z_end - ah_len * (tz * math.cos(ah_ang) + sgn * math.sin(ah_ang))
            p_tip = proj(np.array([x_end, 0.0, z_end], dtype=float), a=cam_a, b=cam_b)
            p_wng = proj(np.array([wx, 0.0, wz], dtype=float), a=cam_a, b=cam_b)
            xh = [float(p_wng[0]), float(p_tip[0])]
            yh = [float(p_wng[1]), float(p_tip[1])]
            xs_all.extend(xh)
            ys_all.extend(yh)
            fig.add_trace(
                go.Scatter(
                    x=xh,
                    y=yh,
                    mode="lines",
                    line=dict(width=max(1.0, arr_lw * 0.9), color=arr_color),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    c2 = proj(np.array([cx_face, 0.0, cz_face], dtype=float), a=cam_a, b=cam_b)
    cx, cxy = float(c2[0]), float(c2[1])
    xs_all.append(cx)
    ys_all.append(cxy)
    t_font_color = "#1a1a1a" if torsion_design_required else "#666666"
    fig.add_annotation(
        x=cx,
        y=cxy,
        text="T",
        showarrow=False,
        font=dict(size=20 if torsion_design_required else 16, color=t_font_color),
        xref="x",
        yref="y",
    )

    if xs_all:
        xmin, xmax = min(xs_all), max(xs_all)
        ymin, ymax = min(ys_all), max(ys_all)
        dx = max(xmax - xmin, 1e-6)
        dy = max(ymax - ymin, 1e-6)
        pad = 0.1 * max(dx, dy)
        fig.update_xaxes(
            visible=False,
            showgrid=False,
            zeroline=False,
            scaleanchor="y",
            scaleratio=1,
            range=[xmin - pad, xmax + pad],
        )
        fig.update_yaxes(
            visible=False,
            showgrid=False,
            zeroline=False,
            range=[ymin - pad, ymax + pad],
        )

    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode=False,
    )
    return fig
