# torsion_diagrams.py
# ==========================================
# 3D Torsion Prism Diagram Functions
# ==========================================

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def draw_face_label_debug(
    cam_a: float = -0.65,
    cam_b: float = 0.28,
    L: float = 8000.0,
    B: float = 400.0,
    D: float = 600.0,
    fs: int = 9,
    show_corners: bool = True,
    n_cracks: int = 3,
    start_t_min: float = 0.10,
    start_t_span: float = 0.30,
    crack_lw: float = 4.0,
    show_cracks: bool = True,
    k_slope: float = 0.50,
    s0_min: float = 0.10,
    theta_deg: float = 1.00,
):
    """
    Internal function to draw the 3D torsion prism with cracks.
    
    Returns a matplotlib figure with the 3D torsion diagram.
    """
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection='3d')
    
    # Convert inputs to float
    L = float(L)
    B = float(B)
    D = float(D)
    cam_a = float(cam_a)
    cam_b = float(cam_b)
    
    # Define the prism vertices
    # Coordinate system: x = length (L), y = breadth (B), z = depth (D)
    vertices = np.array([
        [0, 0, 0],      # 0: front-bottom-left
        [L, 0, 0],     # 1: front-bottom-right
        [L, B, 0],     # 2: front-top-right
        [0, B, 0],     # 3: front-top-left
        [0, 0, D],     # 4: back-bottom-left
        [L, 0, D],     # 5: back-bottom-right
        [L, B, D],     # 6: back-top-right
        [0, B, D],     # 7: back-top-left
    ])
    
    # Define the 6 faces of the prism
    faces = [
        [vertices[0], vertices[1], vertices[2], vertices[3]],  # front face (y=0)
        [vertices[4], vertices[5], vertices[6], vertices[7]],  # back face (y=B)
        [vertices[0], vertices[1], vertices[5], vertices[4]],  # bottom face (z=0)
        [vertices[2], vertices[3], vertices[7], vertices[6]],  # top face (z=D)
        [vertices[0], vertices[3], vertices[7], vertices[4]],  # left face (x=0)
        [vertices[1], vertices[2], vertices[6], vertices[5]],  # right face (x=L)
    ]
    
    # Draw the prism faces with transparency
    face_collection = Poly3DCollection(
        faces,
        alpha=0.2,
        facecolor='lightgray',
        edgecolor='black',
        linewidths=1.0,
    )
    ax.add_collection3d(face_collection)
    
    # Draw cracks if enabled
    if show_cracks and n_cracks > 0:
        # Helix cracks along the length
        theta_rad = np.radians(theta_deg * 45.0)  # Convert multiplier to angle
        for i in range(n_cracks):
            t_start = start_t_min + (i / max(1, n_cracks - 1)) * start_t_span
            t_start = max(0.0, min(1.0, t_start))
            
            # Create helix crack path
            n_points = 50
            t_vals = np.linspace(t_start, t_start + 0.3, n_points)
            
            # Helix equation: x = L*t, y = B/2 + k_slope*B*sin(2*pi*t), z = D/2 + k_slope*D*cos(2*pi*t)
            x_crack = L * t_vals
            y_crack = B / 2.0 + k_slope * B * 0.3 * np.sin(2 * np.pi * t_vals + theta_rad)
            z_crack = D / 2.0 + k_slope * D * 0.3 * np.cos(2 * np.pi * t_vals + theta_rad)
            
            # Clip to prism bounds
            y_crack = np.clip(y_crack, 0, B)
            z_crack = np.clip(z_crack, 0, D)
            
            ax.plot(x_crack, y_crack, z_crack, 'r-', linewidth=crack_lw, alpha=0.7)
    
    # Corner labels if enabled
    if show_corners:
        corner_labels = ['0', '1', '2', '3', '4', '5', '6', '7']
        for i, (v, label) in enumerate(zip(vertices, corner_labels)):
            ax.text(v[0], v[1], v[2], label, fontsize=fs)
    
    # Set axis labels
    ax.set_xlabel('Length (mm)', fontsize=fs)
    ax.set_ylabel('Breadth (mm)', fontsize=fs)
    ax.set_zlabel('Depth (mm)', fontsize=fs)
    
    # Set camera/view angle based on cam_a and cam_b
    # cam_a controls horizontal rotation, cam_b controls vertical elevation
    elev = 20.0 + cam_b * 40.0  # Elevation angle
    azim = 45.0 + cam_a * 60.0   # Azimuth angle
    
    ax.view_init(elev=elev, azim=azim)
    
    # Set axis limits with some margin
    ax.set_xlim([-0.1*L, 1.1*L])
    ax.set_ylim([-0.1*B, 1.1*B])
    ax.set_zlim([-0.1*D, 1.1*D])
    
    # Equal aspect ratio
    ax.set_box_aspect([L, B, D])
    
    plt.tight_layout()
    return fig


def plot_torsion_prism_3d(
    L: float,
    B: float,
    D: float,
    cam_a: float = -0.65,
    cam_b: float = 0.28,
    show_corners: bool = True,
    show_cracks: bool = True,
    n_cracks: int = 3,
    start_t_min: float = 0.10,
    start_t_span: float = 0.30,
    crack_lw: float = 4.0,
    k_slope: float = 0.50,
    theta_multiplier: float = 1.00,
    fs: int = 9,
):
    """
    Returns a Matplotlib figure for the torsion prism/crack diagram.
    
    NOTE: theta_multiplier is your 'wall angle multiplier (proportional to roof angle)'.
    """
    fig = draw_face_label_debug(
        cam_a=float(cam_a),
        cam_b=float(cam_b),
        L=float(L),
        B=float(B),
        D=float(D),
        fs=int(fs),
        show_corners=bool(show_corners),
        n_cracks=int(n_cracks),
        start_t_min=float(start_t_min),
        start_t_span=float(start_t_span),
        crack_lw=float(crack_lw),
        show_cracks=bool(show_cracks),
        k_slope=float(k_slope),
        s0_min=float(start_t_min),
        theta_deg=float(theta_multiplier),  # keep your naming internally
    )
    return fig






