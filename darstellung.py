# -*- coding: utf-8 -*-
"""Darstellungshilfen ohne Streamlit-/Plotly-Abhängigkeit (testbar): Zahlenformat und Prozessfließbild (SVG)."""
import math
from html import escape


from html import escape
import numpy as np


def fmt_de(value, stellen=1):
    """Deutsches Zahlenformat."""
    if value is None:
        return "–"
    try:
        if not np.isfinite(float(value)):
            return "–"
    except (TypeError, ValueError):
        return "–"
    return f"{float(value):,.{stellen}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_svg(res):
    """Prozessfließbild der gerechneten Variante mit Volumenströmen und TDS-Werten."""
    p = res["parameter"]
    d = res["df"].set_index("Strom")
    k = res["kenn"]

    nf = bool(p["nf"])
    fcdi = bool(p["fcdi"])

    def row_name(prefix):
        matches = [n for n in d.index if str(n).startswith(prefix)]
        if not matches:
            raise KeyError(f"Kein Strom mit Präfix '{prefix}' gefunden.")
        return matches[0]

    def lab(stream_key):
        r = d.loc[stream_key]
        vol = fmt_de(r["Volumenstrom (m³/h)"], 1)
        tds = fmt_de(r["TDS (mg/L)"], 0)
        return f"{vol} m³/h · {tds} mg/L"

    # Layout-Konstanten (zentrale Geometrie statt verstreuter Magic Numbers)
    W, H = 1220, 345
    Y_PROD = 46      # Obere Sammelleitung: Produkt
    Y_MAIN = 132     # Hauptachse: Zulauf & Apparate
    Y_SOLE = 218     # Untere Sammelleitung: Sole / Abfluss
    Y_RECIRC = 280   # Eigene Spur unterhalb der Sole für NF-Rezirkulation

    BOX_W, BOX_H = 116, 76
    BOX_Y = Y_MAIN - BOX_H / 2  # 94

    X_FEED_START = 18
    X_MIX = 165
    X_UO = 215
    X_SINK = 965
    SINK_W = 235

    parts = []

    def add_text(x, y, text, cls="label", anchor="middle"):
        parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}">{escape(str(text))}</text>'
        )

    def ortho_path(pts, radius=8, arrow=True, cls="pipe", marker="url(#arrow)"):
        """Zeichnet einen orthogonalen Linienzug mit sanft abgerundeten Ecken."""
        if len(pts) < 2:
            return
        cmds = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
        for i in range(1, len(pts) - 1):
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]

            dx1, dy1 = x1 - x0, y1 - y0
            dx2, dy2 = x2 - x1, y2 - y1
            len1 = (dx1 * dx1 + dy1 * dy1) ** 0.5
            len2 = (dx2 * dx2 + dy2 * dy2) ** 0.5

            if len1 == 0 or len2 == 0:
                continue

            r = min(radius, len1 / 2, len2 / 2)
            # Punkt kurz vor der Ecke
            px_in = x1 - (dx1 / len1) * r
            py_in = y1 - (dy1 / len1) * r
            # Punkt kurz nach der Ecke
            px_out = x1 + (dx2 / len2) * r
            py_out = y1 + (dy2 / len2) * r

            cmds.append(f"L {px_in:.1f} {py_in:.1f}")
            cmds.append(f"Q {x1:.1f} {y1:.1f} {px_out:.1f} {py_out:.1f}")

        cmds.append(f"L {pts[-1][0]:.1f} {pts[-1][1]:.1f}")
        marker_attr = f' marker-end="{marker}"' if arrow else ""
        parts.append(f'<path d="{" ".join(cmds)}" class="{cls}"{marker_attr}/>')

    def draw_unit(x, title, subtitle=None):
        parts.append(
            f'<rect x="{x:.1f}" y="{BOX_Y:.1f}" width="{BOX_W}" height="{BOX_H}" rx="7" class="unit"/>'
        )
        if subtitle:
            add_text(x + BOX_W / 2, BOX_Y + BOX_H / 2 - 2, title, "unit-title")
            add_text(x + BOX_W / 2, BOX_Y + BOX_H / 2 + 15, subtitle, "unit-sub")
        else:
            add_text(x + BOX_W / 2, BOX_Y + BOX_H / 2 + 5, title, "unit-title")

    def draw_sink(y_center, h, title, val_text, cls="sink"):
        y_top = y_center - h / 2
        parts.append(
            f'<rect x="{X_SINK}" y="{y_top:.1f}" width="{SINK_W}" height="{h}" rx="7" class="{cls}"/>'
        )
        add_text(X_SINK + SINK_W / 2, y_top + 18, title, "sink-title")
        add_text(X_SINK + SINK_W / 2, y_top + 35, val_text, "small")

    def draw_node(x, y):
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="node"/>')

    # SVG-Header & Styles
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}" '
        f'preserveAspectRatio="xMidYMid meet" role="img">'
        "<defs>"
        '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0.8 L7.5,4 L0,7.2 Z" class="head"/>'
        "</marker>"
        '<marker id="arrow-prod" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0.8 L7.5,4 L0,7.2 Z" class="head-prod"/>'
        "</marker>"
        '<marker id="arrow-sole" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">'
        '<path d="M0,0.8 L7.5,4 L0,7.2 Z" class="head-sole"/>'
        "</marker>"
        "</defs>"
        "<style>"
        "text{font-family:Arial,Helvetica,sans-serif;fill:#111827}"
        ".label{font-size:12.5px;font-weight:600}"
        ".small{font-size:11px;fill:#374151}"
        ".unit-title{font-size:15px;font-weight:700;fill:#0f172a}"
        ".unit-sub{font-size:10.5px;fill:#475569}"
        ".sink-title{font-size:13px;font-weight:700}"
        ".kpi{font-size:12px;font-weight:600;fill:#1f2937}"
        ".unit{fill:#ffffff;stroke:#1e293b;stroke-width:1.8}"
        ".sink{fill:#f8fafc;stroke:#1e293b;stroke-width:1.8}"
        ".sink-prod{fill:#eff6ff;stroke:#1d4ed8;stroke-width:1.8}"
        ".sink-sole{fill:#fefce8;stroke:#854d0e;stroke-width:1.6}"
        ".pipe{fill:none;stroke:#1e293b;stroke-width:1.8}"
        ".pipe-prod{fill:none;stroke:#1d4ed8;stroke-width:1.8}"
        ".pipe-sole{fill:none;stroke:#854d0e;stroke-width:1.7}"
        ".pipe-recirc{fill:none;stroke:#475569;stroke-width:1.6;stroke-dasharray:5,3}"
        ".head{fill:#1e293b}"
        ".head-prod{fill:#1d4ed8}"
        ".head-sole{fill:#854d0e}"
        ".node{fill:#1e293b}"
        "</style>"
    )

    # 1. Rohwasser-Eingang & Mischpunkt
    add_text(X_FEED_START, Y_MAIN - 16, "Rohwasser", "label", "start")
    add_text(X_FEED_START, Y_MAIN + 2, f"{fmt_de(p['v_feed'], 1)} m³/h", "small", "start")
    add_text(X_FEED_START, Y_MAIN + 16, f"{fmt_de(p['tds_feed'], 0)} mg/L TDS", "small", "start")

    ortho_path([(118, Y_MAIN), (X_MIX, Y_MAIN)], arrow=False)
    draw_node(X_MIX, Y_MAIN)
    ortho_path([(X_MIX, Y_MAIN), (X_UO, Y_MAIN)])

    # 2. UO-Stufe
    draw_unit(X_UO, "UO", "Umkehrosmose")
    s_uo_in = row_name("2")
    s_uo_perm = row_name("3")
    s_uo_conc = row_name("4")

    add_text(X_UO + BOX_W / 2, BOX_Y - 10, f"Zulauf {lab(s_uo_in)}", "small")

    # UO-Permeat -> obere Produkt-Schiene
    x_uo_out = X_UO + BOX_W
    ortho_path(
        [(x_uo_out, BOX_Y + 18), (x_uo_out + 26, BOX_Y + 18), (x_uo_out + 26, Y_PROD), (X_SINK, Y_PROD)],
        cls="pipe-prod",
        marker="url(#arrow-prod)",
    )
    add_text(x_uo_out + 36, Y_PROD - 8, f"UO-Permeat: {lab(s_uo_perm)}", "small", "start")

    # UO-Konzentrat (Strom 4) weiter nach rechts
    cur_x = x_uo_out + 75
    ortho_path([(x_uo_out, BOX_Y + 56), (cur_x, BOX_Y + 56)])
    add_text((x_uo_out + cur_x) / 2, BOX_Y + 72, f"Strom 4 · {lab(s_uo_conc)}", "small")

    # 3. Optionale Nanofiltration (NF)
    if nf:
        x_nf = cur_x
        draw_unit(x_nf, "NF", "Nanofiltration")
        s_nf_recirc = row_name("5")
        s_nf_conc = row_name("6")

        # NF-Permeat (Rezirkulation) sauber auf eigener Spur unten zum Mischpunkt
        x_nf_mid = x_nf + BOX_W / 2
        ortho_path(
            [(x_nf_mid, BOX_Y + BOX_H), (x_nf_mid, Y_RECIRC), (X_MIX, Y_RECIRC), (X_MIX, Y_MAIN + 5)],
            cls="pipe-recirc",
        )
        add_text((x_nf_mid + X_MIX) / 2, Y_RECIRC - 7, f"NF-Permeat (Rezirkulation): {lab(s_nf_recirc)}", "small")

        # NF-Konzentrat weiter nach rechts
        x_nf_out = x_nf + BOX_W
        cur_x = x_nf_out + 75
        ortho_path([(x_nf_out, BOX_Y + 38), (cur_x, BOX_Y + 38)])
        add_text(x_nf + BOX_W / 2, BOX_Y - 10, f"NF-Konzentrat: {lab(s_nf_conc)}", "small")

    # 4. Optionale FCDI-Stufe oder direkter Sole-Abgang
    if fcdi:
        x_fcdi = cur_x
        draw_unit(x_fcdi, "FCDI", "Kapazitive Entsalzung")
        s_dil = row_name("7")
        s_brine = row_name("8")

        x_fcdi_out = x_fcdi + BOX_W
        # Diluat -> obere Produkt-Schiene
        x_dil_turn = x_fcdi_out + 24
        ortho_path(
            [(x_fcdi_out, BOX_Y + 20), (x_dil_turn, BOX_Y + 20), (x_dil_turn, Y_PROD), (X_SINK, Y_PROD)],
            cls="pipe-prod",
            marker="url(#arrow-prod)",
        )
        add_text(x_dil_turn + 8, BOX_Y + 12, f"Diluat: {lab(s_dil)}", "small", "start")

        # Sole -> untere Sole-Schiene
        x_sole_turn = x_fcdi_out + 46
        ortho_path(
            [(x_fcdi_out, BOX_Y + 56), (x_sole_turn, BOX_Y + 56), (x_sole_turn, Y_SOLE), (X_SINK, Y_SOLE)],
            cls="pipe-sole",
            marker="url(#arrow-sole)",
        )
        add_text(x_fcdi + BOX_W / 2, BOX_Y + BOX_H + 16, f"Sole: {lab(s_brine)}", "small")
    else:
        # Konzentrat geht direkt in die Sole-Schiene
        x_sole_turn = cur_x + 25
        ortho_path(
            [(cur_x, BOX_Y + 56), (x_sole_turn, BOX_Y + 56), (x_sole_turn, Y_SOLE), (X_SINK, Y_SOLE)],
            cls="pipe-sole",
            marker="url(#arrow-sole)",
        )

    # 5. Zielblöcke rechts: Produkt & Sole
    draw_sink(Y_PROD, 44, "Produkt", lab(row_name("P")), cls="sink sink-prod")
    draw_sink(Y_SOLE, 46, "Sole (Abfluss)", lab(row_name("B")), cls="sink sink-sole")

    # 6. Kennzahlen-Leiste unten
    kpi_text = (
        f"Ausbeute gesamt: {fmt_de(k['ausbeute'], 1)} %   ·   "
        f"Produkt-TDS: {fmt_de(k['tds_produkt'], 1)} mg/L   ·   "
        f"Spez. Energie: {fmt_de(k['e_spez']['gesamt'], 2)} kWh/m³ Produkt"
    )
    add_text(X_FEED_START, H - 14, kpi_text, "kpi", "start")

    parts.append("</svg>")
    return "".join(parts)
