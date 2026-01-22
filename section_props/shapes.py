from __future__ import annotations

import math
from typing import Dict, Any


def _rect_props(b: float, D: float) -> Dict[str, float]:
    A = b * D
    ybar_top = D / 2.0
    Ixx = b * D**3 / 12.0
    Ztop = Ixx / (D / 2.0)
    Zbot = Ztop
    return dict(A=A, ybar_top=ybar_top, Ixx=Ixx, Ztop=Ztop, Zbot=Zbot)


def _hollow_rect_props(b: float, D: float, t: float) -> Dict[str, float]:
    bi = b - 2*t
    Di = D - 2*t
    A = b * D - bi * Di
    ybar_top = D / 2.0
    Ixx = (b * D**3 - bi * Di**3) / 12.0
    Ztop = Ixx / (D / 2.0)
    Zbot = Ztop
    return dict(A=A, ybar_top=ybar_top, Ixx=Ixx, Ztop=Ztop, Zbot=Zbot)


def _circle_props(D: float) -> Dict[str, float]:
    r = D / 2.0
    A = math.pi * r**2
    ybar_top = r
    Ixx = (math.pi * r**4) / 4.0
    Ztop = Ixx / r
    Zbot = Ztop
    return dict(A=A, ybar_top=ybar_top, Ixx=Ixx, Ztop=Ztop, Zbot=Zbot)


def _hollow_circle_props(D: float, t: float) -> Dict[str, float]:
    ro = D / 2.0
    ri = ro - t
    A = math.pi * (ro**2 - ri**2)
    ybar_top = ro
    Ixx = (math.pi * (ro**4 - ri**4)) / 4.0
    Ztop = Ixx / ro
    Zbot = Ztop
    return dict(A=A, ybar_top=ybar_top, Ixx=Ixx, Ztop=Ztop, Zbot=Zbot)


def _t_section_props(bf: float, tf: float, bw: float, D: float) -> Dict[str, float]:
    # Composite of flange + web (web below flange)
    Af = bf * tf
    Aw = bw * (D - tf)
    A = Af + Aw

    # y measured from top
    yf = tf / 2.0
    yw = tf + (D - tf) / 2.0
    ybar_top = (Af*yf + Aw*yw) / A

    # Ixx about centroid: sum (I_local + A*d^2)
    If_local = bf * tf**3 / 12.0
    Iw_local = bw * (D - tf)**3 / 12.0
    df = abs(ybar_top - yf)
    dw = abs(yw - ybar_top)
    Ixx = If_local + Af*df**2 + Iw_local + Aw*dw**2

    c_top = ybar_top
    c_bot = D - ybar_top
    Ztop = Ixx / c_top
    Zbot = Ixx / c_bot
    return dict(A=A, ybar_top=ybar_top, Ixx=Ixx, Ztop=Ztop, Zbot=Zbot)


def _i_section_props(bf: float, tf: float, tw: float, D: float) -> Dict[str, float]:
    # Composite of: top flange + web + bottom flange
    Af_top = bf * tf
    Af_bot = bf * tf
    Aw = tw * (D - 2*tf)
    A = Af_top + Aw + Af_bot

    # y measured from top
    y_top = tf / 2.0
    y_web = tf + (D - 2*tf) / 2.0
    y_bot = D - tf / 2.0

    ybar_top = (Af_top*y_top + Aw*y_web + Af_bot*y_bot) / A

    # Ixx about centroid (parallel axis)
    I_top_local = bf * tf**3 / 12.0
    I_bot_local = bf * tf**3 / 12.0
    I_web_local = tw * (D - 2*tf)**3 / 12.0

    d_top = abs(ybar_top - y_top)
    d_web = abs(y_web - ybar_top)
    d_bot = abs(y_bot - ybar_top)

    Ixx = (
        I_top_local + Af_top*d_top**2
        + I_web_local + Aw*d_web**2
        + I_bot_local + Af_bot*d_bot**2
    )

    c_top = ybar_top
    c_bot = D - ybar_top
    Ztop = Ixx / c_top
    Zbot = Ixx / c_bot
    return dict(A=A, ybar_top=ybar_top, Ixx=Ixx, Ztop=Ztop, Zbot=Zbot)


def compute_section_properties(shape_name: str, dims: Dict[str, float]) -> Dict[str, Any]:
    """
    Returns properties in mm-based units:
      A: mm^2
      ybar_top: mm
      Ixx: mm^4
      Ztop/Zbot: mm^3
    """
    if shape_name.startswith("Rectangle (b × D)"):
        return _rect_props(dims["b"], dims["D"])

    if shape_name.startswith("Hollow Rectangle"):
        return _hollow_rect_props(dims["b"], dims["D"], dims["t"])

    if shape_name.startswith("Circle (diameter"):
        return _circle_props(dims["D"])

    if shape_name.startswith("Hollow Circle"):
        return _hollow_circle_props(dims["D"], dims["t"])

    if shape_name.startswith("T-Section"):
        return _t_section_props(dims["bf"], dims["tf"], dims["bw"], dims["D"])

    if shape_name.startswith("I-Section"):
        return _i_section_props(dims["bf"], dims["tf"], dims["tw"], dims["D"])

    raise ValueError(f"Unknown shape_name: {shape_name}")
