from __future__ import annotations
from typing import Dict


def compute_gross_props(shape_name: str, dims: Dict[str, float]) -> Dict[str, float]:
    """
    Returns:
      A_g (mm^2), ybar_top_g (mm), Ixx_g (mm^4), Ztop_g (mm^3), Zbot_g (mm^3),
      plus envelope b_env, D_env
    """
    if shape_name.startswith("T-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); bw = float(dims["bw"]); D = float(dims["D"])
        # Areas
        Af = bf * tf
        Aw = bw * (D - tf)
        A = Af + Aw
        # y from top
        yf = tf / 2.0
        yw = tf + (D - tf) / 2.0
        ybar = (Af*yf + Aw*yw) / A
        # I about centroid
        If = bf * tf**3 / 12.0
        Iw = bw * (D - tf)**3 / 12.0
        df = abs(ybar - yf)
        dw = abs(yw - ybar)
        Ixx = If + Af*df**2 + Iw + Aw*dw**2
        c_top = ybar
        c_bot = D - ybar
        return dict(
            b_env=bf, D_env=D, b_web=bw,
            A_g=A, ybar_top_g=ybar, Ixx_g=Ixx,
            Ztop_g=Ixx / c_top, Zbot_g=Ixx / c_bot
        )

    if shape_name.startswith("I-Section"):
        bf = float(dims["bf"]); tf = float(dims["tf"]); tw = float(dims["tw"]); D = float(dims["D"])
        Af_top = bf * tf
        Af_bot = bf * tf
        Aw = tw * (D - 2*tf)
        A = Af_top + Aw + Af_bot
        # y from top
        y_top = tf / 2.0
        y_web = tf + (D - 2*tf) / 2.0
        y_bot = D - tf / 2.0
        ybar = (Af_top*y_top + Aw*y_web + Af_bot*y_bot) / A
        # I about centroid
        I_top = bf * tf**3 / 12.0
        I_bot = bf * tf**3 / 12.0
        I_web = tw * (D - 2*tf)**3 / 12.0
        d_top = abs(ybar - y_top)
        d_web = abs(y_web - ybar)
        d_bot = abs(y_bot - ybar)
        Ixx = I_top + Af_top*d_top**2 + I_web + Aw*d_web**2 + I_bot + Af_bot*d_bot**2
        c_top = ybar
        c_bot = D - ybar
        return dict(
            b_env=bf, D_env=D, b_web=tw,
            A_g=A, ybar_top_g=ybar, Ixx_g=Ixx,
            Ztop_g=Ixx / c_top, Zbot_g=Ixx / c_bot
        )

    raise ValueError(f"Unknown shape_name: {shape_name}")
