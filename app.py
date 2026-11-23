# -*- coding: utf-8 -*-
"""
Streamlit-App: Brackwasser-Aufbereitung
Benötigte Dateien im selben Ordner:
    app.py
    simulation.py
    darstellung.py

Start:
    streamlit run app.py
"""

import math
import io

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import simulation as sim

try:
    import darstellung as dar
except ImportError:
    dar = None


# ============================================================
# 1. SEITENKONFIGURATION UND DESIGN
# ============================================================

st.set_page_config(
    page_title="Brackwasser-Aufbereitung | Simulation",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        background: #f7f9fb;
        border: 1px solid #e6ebf0;
        padding: 13px 15px;
        border-radius: 10px;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #e6ebf0;
        border-radius: 10px;
    }
    .small-muted {color: #667085; font-size: 0.88rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


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


def metric_safe(container, label, value, unit="", help_text=None):
    text = f"{value} {unit}".strip()
    container.metric(label, text, help=help_text)


# ============================================================
# 2. KOPFBEREICH
# ============================================================

st.title("Brackwasser-Aufbereitung")
st.caption(
    "Verfahrenssimulation für Umkehrosmose (UO), Nanofiltration (NF) "
    "und kapazitive Deionisation (FCDI)"
)

with st.expander("Bedienung und Modellübersicht", expanded=False):
    st.markdown(
        """
        **So verwendest du die Simulation**

        1. Stelle links die Rohwasser- und Verfahrensparameter ein.
        2. Wähle die Anlagenvariante und den Bilanzierungsmodus.
        3. Die Ergebnisse werden automatisch neu berechnet.
        4. Im Variantenvergleich werden alle vier Anlagenkonzepte mit denselben
           Rohwasser- und Betriebsparametern gegenübergestellt.
        5. In der Parameterstudie lässt sich der Einfluss eines einzelnen
           Parameters auf ausgewählte Ergebnisgrößen untersuchen.

        **Abgebildete Anlagenvarianten**
        - UO (Bestand)
        - UO + NF
        - UO + FCDI
        - UO + NF + FCDI

        Die Rückhalte-, Druck- und Energiemodelle sind Regressionsmodelle.
        Die vom Rechenkern ausgegebenen Gültigkeitsbereichs- und
        Extrapolationswarnungen werden deshalb in der App angezeigt.
        """
    )


# ============================================================
# 3. SIDEBAR: EINGABEPARAMETER
# ============================================================

p_default = sim.standard_parameter()

with st.sidebar:
    st.header("Simulationseingaben")

    if st.button("Standardwerte wiederherstellen", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("bw_"):
                del st.session_state[key]
        st.rerun()

    st.subheader("Anlagenkonzept")
    variante = st.selectbox(
        "Zu berechnende Variante",
        list(sim.VARIANTEN.keys()),
        index=list(sim.VARIANTEN.keys()).index(p_default["variante"]),
        key="bw_variante",
    )

    st.subheader("Rohwasser")
    v_feed = st.number_input(
        "Rohwasser-Volumenstrom",
        min_value=0.1, max_value=10000.0,
        value=float(p_default["v_feed"]), step=0.5,
        format="%.2f", key="bw_v_feed",
        help="Volumenstrom des Rohwassers in m³/h.",
    )
    tds_feed = st.number_input(
        "TDS im Rohwasser",
        min_value=1.0, max_value=100000.0,
        value=float(p_default["tds_feed"]), step=100.0,
        format="%.1f", key="bw_tds_feed",
        help="Gesamter gelöster Feststoffgehalt in mg/L.",
    )
    so4_feed = st.number_input(
        "Sulfat im Rohwasser",
        min_value=0.0, max_value=100000.0,
        value=float(p_default["so4_feed"]), step=25.0,
        format="%.1f", key="bw_so4_feed",
    )

    with st.expander("UO – Umkehrosmose", expanded=True):
        y_uo = st.slider(
            "UO-Ausbeute (%)", 1.0, 99.0,
            float(p_default["y_uo"]), 1.0, key="bw_y_uo",
        )

    with st.expander("NF – Nanofiltration", expanded=True):
        y_nf = st.slider(
            "NF-Ausbeute (%)", 1.0, 99.0,
            float(p_default["y_nf"]), 1.0, key="bw_y_nf",
        )
        p_nf = st.number_input(
            "NF-Zulaufdruck (bar)",
            min_value=0.0, max_value=100.0,
            value=float(p_default["p_nf"]), step=0.5,
            key="bw_p_nf",
        )
        nf_modul = st.selectbox(
            "NF-Modul / Regression",
            ["A", "B"],
            index=0 if p_default["nf_modul"] == "A" else 1,
            key="bw_nf_modul",
        )
        nf_energie_basis = st.selectbox(
            "Bezugsbasis NF-Energie",
            ["zulauf", "permeat"],
            index=["zulauf", "permeat"].index(p_default["nf_energie_basis"]),
            format_func=lambda x: "NF-Zulauf" if x == "zulauf" else "NF-Permeat",
            key="bw_nf_energie_basis",
        )

    with st.expander("FCDI – kapazitive Deionisation", expanded=True):
        y_fcdi = st.slider(
            "FCDI-Ausbeute (%)", 1.0, 99.0,
            float(p_default["y_fcdi"]), 1.0, key="bw_y_fcdi",
        )

    with st.expander("Energie, Bilanzierung und Modell", expanded=False):
        eta_pumpe = st.slider(
            "Pumpenwirkungsgrad (%)", 10, 100,
            int(round(p_default["eta_pumpe"] * 100)), 1,
            key="bw_eta_pumpe",
        ) / 100.0
        strompreis = st.number_input(
            "Strompreis (€/kWh)",
            min_value=0.0, max_value=10.0,
            value=float(p_default["strompreis"]), step=0.01,
            format="%.3f", key="bw_strompreis",
        )
        bilanz_modus = st.selectbox(
            "Bilanzierungsmodus",
            ["korrekt", "excel"],
            format_func=lambda x: (
                "Physikalisch konsistent" if x == "korrekt"
                else "Excel-Nachrechnung"
            ),
            key="bw_bilanz_modus",
        )
        range_modus = st.selectbox(
            "Umgang mit Modellgrenzen",
            ["extrapolieren", "streng"],
            format_func=lambda x: (
                "Außerhalb extrapolieren (mit Warnung)" if x == "extrapolieren"
                else "Streng – außerhalb nicht berechnen"
            ),
            key="bw_range_modus",
        )


# Parameterdictionary des Rechenkerns aufbauen
p_basis = dict(p_default)
p_basis.update(
    {
        "v_feed": float(v_feed),
        "tds_feed": float(tds_feed),
        "so4_feed": float(so4_feed),
        "y_uo": float(y_uo),
        "y_nf": float(y_nf),
        "p_nf": float(p_nf),
        "y_fcdi": float(y_fcdi),
        "eta_pumpe": float(eta_pumpe),
        "nf_modul": nf_modul,
        "nf_energie_basis": nf_energie_basis,
        "strompreis": float(strompreis),
        "bilanz_modus": bilanz_modus,
        "range_modus": range_modus,
    }
)

p_einzel = sim.mit_variante(p_basis, variante)


# ============================================================
# 4. BERECHNUNG
# ============================================================

try:
    with st.spinner("Simulation wird berechnet …"):
        res = sim.simuliere(p_einzel)
        vergleich = sim.vergleich(p_basis)
except Exception as exc:
    st.error(f"Die Simulation konnte nicht berechnet werden: {exc}")
    st.exception(exc)
    st.stop()

kenn = res["kenn"]
df = res["df"]


# ============================================================
# 5. PROZESSFLIESSBILD
# ============================================================

st.subheader(f"Prozessfließbild – {variante}")

if dar is not None and hasattr(dar, "build_svg"):
    try:
        svg = dar.build_svg(res)
        components.html(svg, height=470, scrolling=True)
    except Exception as exc:
        st.warning(f"Das Prozessfließbild konnte nicht erzeugt werden: {exc}")
else:
    st.info(
        "Für das dynamische Prozessfließbild bitte die Datei "
        "`darstellung.py` mit der Funktion `build_svg(res)` neben `app.py` ablegen."
    )


# ============================================================
# 6. ERGEBNIS-KENNZAHLEN
# ============================================================

st.subheader("Ergebnisübersicht")

k1, k2, k3, k4 = st.columns(4)
metric_safe(k1, "Produktwasser", fmt_de(kenn["v_produkt"], 2), "m³/h")
metric_safe(k2, "Produktwasser-TDS", fmt_de(kenn["tds_produkt"], 1), "mg/L")
metric_safe(k3, "Gesamtausbeute", fmt_de(kenn["ausbeute"], 1), "%")
metric_safe(k4, "Gesamtrückhalt TDS", fmt_de(kenn["rueckhalt_gesamt"], 1), "%")

k5, k6, k7, k8 = st.columns(4)
metric_safe(k5, "Spezifischer Energiebedarf", fmt_de(kenn["e_spez"]["gesamt"], 3), "kWh/m³ Produkt")
metric_safe(k6, "Elektrische Leistung", fmt_de(kenn["leistung_kw"], 2), "kW")
metric_safe(k7, "Sole-Volumenstrom", fmt_de(kenn["v_sole"], 2), "m³/h")
metric_safe(k8, "Energiekosten", fmt_de(kenn["energiekosten_ct_m3"], 2), "ct/m³ Produkt")

if not kenn.get("gueltig", True):
    st.error(
        "Mindestens eine zentrale Ergebnisgröße ist nicht berechenbar. "
        "Bitte Modellgrenzen und Warnungen prüfen."
    )

if res["warnungen"]:
    with st.expander(f"Modell- und Gültigkeitsbereichswarnungen ({len(res['warnungen'])})", expanded=True):
        for warnung in res["warnungen"]:
            st.warning(warnung)
else:
    st.success("Keine Modell-Gültigkeitsbereichswarnungen für diese Berechnung.")


# ============================================================
# 7. REGISTERKARTEN
# ============================================================

tab_einzel, tab_vergleich, tab_studie = st.tabs(
    ["Einzelkonzept", "Variantenvergleich", "Parameterstudie"]
)


with tab_einzel:
    st.markdown("#### Stoffstrombilanz")

    anzeige = df.copy()
    for col in [
        "Volumenstrom (m³/h)", "TDS (mg/L)", "Sulfat (mg/L)",
        "TDS-Fracht (g/h)",
    ]:
        if col in anzeige.columns:
            anzeige[col] = anzeige[col].map(
                lambda x: fmt_de(x, 2) if pd.notna(x) else "–"
            )

    st.dataframe(anzeige, use_container_width=True, hide_index=True)

    c_left, c_right = st.columns(2)

    with c_left:
        st.markdown("#### Volumenströme")
        fig_v = px.bar(
            df, x="Strom", y="Volumenstrom (m³/h)",
            text="Volumenstrom (m³/h)",
        )
        fig_v.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_v.update_layout(
            template="plotly_white", height=390,
            xaxis_title="", yaxis_title="Volumenstrom (m³/h)",
            margin=dict(l=20, r=20, t=35, b=90),
        )
        st.plotly_chart(fig_v, use_container_width=True)

    with c_right:
        st.markdown("#### TDS-Konzentrationen")
        df_tds = df[df["TDS (mg/L)"].notna()].copy()
        fig_tds = px.bar(
            df_tds, x="Strom", y="TDS (mg/L)",
            text="TDS (mg/L)",
        )
        fig_tds.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_tds.update_layout(
            template="plotly_white", height=390,
            xaxis_title="", yaxis_title="TDS (mg/L)",
            margin=dict(l=20, r=20, t=35, b=90),
        )
        st.plotly_chart(fig_tds, use_container_width=True)

    st.markdown("#### Energieaufteilung")
    energie = pd.DataFrame(
        {
            "Verfahren": ["UO", "NF", "FCDI"],
            "Leistung (kW)": [
                kenn["p_uo_kw"], kenn["p_nf_kw"], kenn["p_fcdi_kw"]
            ],
        }
    )
    energie = energie.replace([np.inf, -np.inf], np.nan).dropna()
    fig_e = px.bar(
        energie, x="Verfahren", y="Leistung (kW)",
        text="Leistung (kW)",
    )
    fig_e.update_traces(texttemplate="%{text:.3f}", textposition="outside")
    fig_e.update_layout(
        template="plotly_white", height=320,
        yaxis_title="Leistung (kW)", xaxis_title="",
    )
    st.plotly_chart(fig_e, use_container_width=True)

    st.markdown("#### Weitere Kennzahlen")
    weitere = pd.DataFrame(
        [
            ("Produktwasser-Sulfat", kenn["so4_produkt"], "mg/L"),
            ("Sole-TDS", kenn["tds_sole"], "mg/L"),
            ("Sole-Sulfat", kenn["so4_sole"], "mg/L"),
            ("Gesamtrückhalt Sulfat", kenn["rueckhalt_so4_gesamt"], "%"),
            ("NF-Druckerhöhung", kenn["dp_nf_boost"], "bar"),
            ("Iterationen NF-Rezirkulation", kenn["iterationen"], "–"),
            ("Abweichung Wasserbilanz", kenn["wasserbilanz_abw"], "m³/h"),
            ("Abweichung Salzbilanz", kenn["salzbilanz_abw"], "g/h"),
        ],
        columns=["Kennzahl", "Wert", "Einheit"],
    )
    weitere["Wert"] = weitere["Wert"].map(lambda x: fmt_de(x, 4))
    st.dataframe(weitere, use_container_width=True, hide_index=True)

    csv_bytes = df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "Stoffstromtabelle als CSV herunterladen",
        data=csv_bytes,
        file_name="brackwasser_stoffstroeme.csv",
        mime="text/csv",
    )


with tab_vergleich:
    st.markdown("#### Vergleich aller vier Anlagenvarianten")
    st.caption(
        "Alle Varianten werden mit denselben Rohwasser- und Betriebsparametern "
        "berechnet. Die NF- und FCDI-Stufen werden je nach Variante aktiviert."
    )

    vergleich_zeilen = []
    for name, ergebnis in vergleich.items():
        k = ergebnis["kenn"]
        vergleich_zeilen.append(
            {
                "Variante": name,
                "Produktwasser (m³/h)": k["v_produkt"],
                "TDS Produkt (mg/L)": k["tds_produkt"],
                "Ausbeute (%)": k["ausbeute"],
                "TDS-Rückhalt (%)": k["rueckhalt_gesamt"],
                "Energie (kWh/m³)": k["e_spez"]["gesamt"],
                "Leistung (kW)": k["leistung_kw"],
                "Sole (m³/h)": k["v_sole"],
                "Energiekosten (ct/m³)": k["energiekosten_ct_m3"],
                "Gültig": "Ja" if k.get("gueltig", True) else "Nein",
                "Warnungen": len(ergebnis["warnungen"]),
            }
        )

    df_vgl = pd.DataFrame(vergleich_zeilen)
    df_vgl_anzeige = df_vgl.copy()
    for col in df_vgl_anzeige.columns:
        if col not in ("Variante", "Gültig", "Warnungen"):
            df_vgl_anzeige[col] = df_vgl_anzeige[col].map(
                lambda x: fmt_de(x, 3)
            )
    st.dataframe(df_vgl_anzeige, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            df_vgl, x="Variante", y="TDS Produkt (mg/L)",
            color="Variante", text="TDS Produkt (mg/L)",
            title="TDS im Produktwasser",
        )
        fig.update_layout(template="plotly_white", showlegend=False, xaxis_title="")
        fig.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = px.bar(
            df_vgl, x="Variante", y="Energie (kWh/m³)",
            color="Variante", text="Energie (kWh/m³)",
            title="Spezifischer Energiebedarf",
        )
        fig.update_layout(template="plotly_white", showlegend=False, xaxis_title="")
        fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Modellwarnungen je Variante")
    for name, ergebnis in vergleich.items():
        if ergebnis["warnungen"]:
            with st.expander(f"{name}: {len(ergebnis['warnungen'])} Warnung(en)"):
                for w in ergebnis["warnungen"]:
                    st.warning(w)
        else:
            st.caption(f"{name}: keine Warnungen")

    vgl_csv = df_vgl.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "Variantenvergleich als CSV herunterladen",
        data=vgl_csv,
        file_name="brackwasser_variantenvergleich.csv",
        mime="text/csv",
        key="download_vgl",
    )


with tab_studie:
    st.markdown("#### Einfluss eines Parameters untersuchen")
    st.caption(
        "Die Parameterstudie variiert jeweils einen Parameter und berechnet "
        "die gewählte Anlagenvariante erneut."
    )

    parameter_optionen = {
        "UO-Ausbeute (%)": ("y_uo", 30.0, 90.0, 5.0),
        "NF-Ausbeute (%)": ("y_nf", 20.0, 80.0, 5.0),
        "NF-Zulaufdruck (bar)": ("p_nf", 5.0, 30.0, 2.5),
        "FCDI-Ausbeute (%)": ("y_fcdi", 50.0, 90.0, 5.0),
        "Rohwasser-TDS (mg/L)": ("tds_feed", 500.0, 15000.0, 500.0),
        "Rohwasser-Volumenstrom (m³/h)": ("v_feed", 1.0, 100.0, 5.0),
    }

    auswahl = st.selectbox("Zu variierender Parameter", list(parameter_optionen.keys()))
    key, minimum, maximum, schritt = parameter_optionen[auswahl]

    aktueller_wert = float(p_einzel[key])
    start_wert = st.number_input(
        "Startwert", min_value=float(minimum), max_value=float(maximum),
        value=float(max(minimum, min(maximum, aktueller_wert - 2 * schritt))),
        step=float(schritt), key="bw_studie_start",
    )
    ende_wert = st.number_input(
        "Endwert", min_value=float(minimum), max_value=float(maximum),
        value=float(max(minimum, min(maximum, aktueller_wert + 2 * schritt))),
        step=float(schritt), key="bw_studie_ende",
    )
    anzahl = st.slider("Anzahl Berechnungspunkte", 3, 25, 9, 1)

    if start_wert >= ende_wert:
        st.warning("Der Endwert muss größer als der Startwert sein.")
    else:
        werte = np.linspace(start_wert, ende_wert, anzahl)
        studie = sim.parameterstudie(
            p_einzel,
            key,
            werte,
        )

        if not studie.empty:
            y_auswahl = st.selectbox(
                "Darzustellende Ergebnisgröße",
                [
                    "ausbeute",
                    "tds_produkt",
                    "e_gesamt",
                    "v_sole",
                    "tds_sole",
                    "v_produkt",
                ],
                format_func=lambda x: {
                    "ausbeute": "Gesamtausbeute (%)",
                    "tds_produkt": "Produktwasser-TDS (mg/L)",
                    "e_gesamt": "Spezifische Energie (kWh/m³)",
                    "v_sole": "Sole-Volumenstrom (m³/h)",
                    "tds_sole": "Sole-TDS (mg/L)",
                    "v_produkt": "Produktwasser-Volumenstrom (m³/h)",
                }[x],
            )
            x_col = key
            if y_auswahl in studie.columns:
                plot_df = studie.dropna(subset=[y_auswahl]).copy()
                if not plot_df.empty:
                    fig = px.line(
                        plot_df, x=x_col, y=y_auswahl,
                        markers=True,
                        title=f"{auswahl} – Einfluss auf {y_auswahl}",
                    )
                    fig.update_layout(
                        template="plotly_white",
                        xaxis_title=auswahl,
                        yaxis_title=y_auswahl,
                        height=420,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(
                        "Für diese Parameterkombination konnten keine "
                        "gültigen Werte berechnet werden."
                    )

            studie_anzeige = studie.copy()
            for col in studie_anzeige.columns:
                if col != key and col != "warnungen":
                    studie_anzeige[col] = studie_anzeige[col].map(
                        lambda x: fmt_de(x, 3) if pd.notna(x) else "–"
                    )
            st.dataframe(studie_anzeige, use_container_width=True, hide_index=True)

            studie_csv = studie.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
            st.download_button(
                "Parameterstudie als CSV herunterladen",
                data=studie_csv,
                file_name="brackwasser_parameterstudie.csv",
                mime="text/csv",
                key="download_studie",
            )


# ============================================================
# 8. FOOTER
# ============================================================

st.divider()
st.caption(
    "Brackwasser-Aufbereitungssimulation | Ergebnisse basieren auf den im "
    "Rechenkern hinterlegten Regressionsmodellen und Betriebsannahmen."
)
