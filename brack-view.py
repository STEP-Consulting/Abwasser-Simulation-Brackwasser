# -*- coding: utf-8 -*-
"""Darstellungshilfen ohne Streamlit-/Plotly-Abhängigkeit (testbar): Zahlenformat und Prozessfließbild (SVG)."""
import math
from html import escape


def fmt_de(x, nd=1):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "–"
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def build_svg(res):
    """Prozessfließbild der gerechneten Variante mit Volumenströmen und TDS-Werten."""
    p, d, k = res["parameter"], res["df"].set_index("Strom"), res["kenn"]
    nf, fcdi = bool(p["nf"]), bool(p["fcdi"])
    def lab(name):
        r = d.loc[name]; return f"{fmt_de(r['Volumenstrom (m³/h)'], 1)} m³/h · {fmt_de(r['TDS (mg/L)'], 0)} mg/L"
    def row(name): return [n for n in d.index if n.startswith(name)][0]
    parts = []
    def text(x, y, s, cls="label", anchor="middle"): parts.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(s)}</text>')
    def line(pts, arrow=True): parts.append('<polyline points="%s" class="pipe"%s/>' % (" ".join(f"{a},{b}" for a, b in pts), ' marker-end="url(#arrow)"' if arrow else ""))
    def box(x, y, w, h, s): parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5"/>'); text(x + w / 2, y + h / 2 + 5, s, "box")
    def dot(x, y): parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" class="dot"/>')
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 1180 330" preserveAspectRatio="xMidYMid meet" role="img">'
                 '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 Z" class="head"/></marker></defs>'
                 '<style>text{font-family:Arial,sans-serif;font-size:12px;fill:#000}.box{font-size:14px;font-weight:bold}.small{font-size:11px;fill:#333}.pipe{fill:none;stroke:#000;stroke-width:1.8}'
                 '.head{fill:#000}rect{fill:#fff;stroke:#000;stroke-width:1.8}.dot{fill:#000}</style>')
    text(10, 92, "Rohwasser", "label", "start"); text(10, 108, f"{fmt_de(p['v_feed'], 1)} m³/h", "small", "start"); text(10, 122, f"{fmt_de(p['tds_feed'], 0)} mg/L TDS", "small", "start")
    line([(105, 100), (150, 100)], False); dot(150, 100); line([(150, 100), (200, 100)])
    box(200, 60, 120, 80, "UO")
    text(260, 52, f"UO-Zulauf {lab(row('2'))}", "small")
    # Permeat -> Produkt
    line([(320, 78), (350, 78), (350, 34), (930, 34)]); text(520, 26, f"UO-Permeat {lab(row('3'))}", "small")
    x_next = 400
    line([(320, 112), (x_next, 112)]); text((320 + x_next) / 2, 132, "4", "small")
    last_name = row("4")
    if nf:
        box(x_next, 72, 120, 80, "NF")
        line([(x_next + 60, 152), (x_next + 60, 250), (150, 250), (150, 104)]); text(300, 244, f"NF-Permeat (Rezirkulation) {lab(row('5'))}", "small")
        line([(x_next + 120, 112), (x_next + 190, 112)]);
        text(x_next + 60, 66, f"NF-Konz. {lab(row('6'))}", "small")
        x_next += 190; last_name = row("6")
    if fcdi:
        box(x_next, 72, 120, 80, "FCDI")
        line([(x_next + 120, 90), (x_next + 150, 90), (x_next + 150, 34)]); text(x_next + 160, 62, f"Diluat {lab(row('7'))}", "small", "start")
        line([(x_next + 120, 134), (x_next + 190, 134), (x_next + 190, 200), (930, 200)]); text(x_next + 60, 170, f"Sole {lab(row('8'))}", "small")
        sole_y = 200
    else:
        line([(x_next, 112), (x_next + 40, 112), (x_next + 40, 200), (930, 200)]); sole_y = 200
    parts.append('<rect x="930" y="14" width="235" height="40" rx="5"/>'); text(1047, 30, "Produkt", "box"); text(1047, 46, lab(row("P")), "small")
    parts.append('<rect x="930" y="178" width="235" height="44" rx="5"/>'); text(1047, 194, "Sole (Abfluss)", "box"); text(1047, 211, lab(row("B")), "small")
    text(10, 300, f"Ausbeute gesamt {fmt_de(k['ausbeute'], 1)} %  ·  Produkt-TDS {fmt_de(k['tds_produkt'], 1)} mg/L  ·  spez. Energie {fmt_de(k['e_spez']['gesamt'], 2)} kWh/m³ Produkt", "label", "start")
    parts.append("</svg>")
    return "".join(parts)
