fig_uls_11 = _make_uls_stress_block_figure(
    b_mm=b or 0.0,
    D_mm=D or 0.0,
    d_mm=d,
    dn_mm=dn,
    a_mm=a_uls,
    alpha2=alpha2_uls,
    gamma=gamma_uls,
    fc=fc,
    fsy=fsy,
    show_lever_arm=False,
    show_dn=False,          # no d_n on 1.1
    show_alpha_label=True,
    variant="11",
)

fig_uls_13 = _make_uls_stress_block_figure(
    b_mm=b or 0.0,
    D_mm=D or 0.0,
    d_mm=d,
    dn_mm=dn,
    a_mm=a_uls,
    alpha2=alpha2_uls,
    gamma=gamma_uls,
    fc=fc,
    fsy=fsy,
    show_lever_arm=True,    # show z
    show_dn=True,
    show_alpha_label=True,  # α2 f'c back on 1.3
    variant="13",
)
