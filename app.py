import streamlit as st
import streamlit.components.v1 as components

import simulation as sim

try:
    import darstellung as dar
except ImportError:
    dar = None


# ============================================================
# 1. SEITENKONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Simulation Wasseraufbereitung",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("💧 Simulation von Wasseraufbereitungsanlagen")
st.caption(
    "Automatische Neuberechnung bei Parameteränderungen • "
    "Variantenvergleich & Parameterstudie • Regressionsmodelle mit Gültigkeitsprüfung"
)

with st.expander("Hinweise zu Modell, Varianten und Methodik", expanded=False):
    st.markdown(
        """
        1. Die Ergebnisse werden bei jeder Parameteränderung automatisch neu berechnet.
        2. Im **Variantenvergleich** werden alle vier Anlagenkonzepte mit denselben
           Rohwasser- und Betriebsparametern gegenübergestellt.
        3. In der **Parameterstudie** lässt sich der Einfluss eines einzelnen
           Parameters auf ausgewählte Ergebnisgrößen untersuchen.

        **Abgebildete Anlagenvarianten**
        - **UO** (Bestand)
        - **UO + NF**
        - **UO + FCDI**
        - **UO + NF + FCDI**

        Die Rückhalte-, Druck- und Energiemodelle sind Regressionsmodelle.
        Gültigkeitsbereichs- und Extrapolationswarnungen werden direkt angezeigt.
        """
    )


# ============================================================
# 2. CACHING FÜR DEN RECHENKERN
# ============================================================

@st.cache_data(show_spinner=False)
def berechne_einzelvariante(params: dict) -> dict:
    return sim.simuliere(params)


@st.cache_data(show_spinner=False)
def berechne_vergleich(params: dict):
    return sim.vergleich(params)


# ============================================================
# 3. SIDEBAR: EINGABEPARAMETER
# ============================================================

p_default = sim.standard_parameter()
varianten_liste = list(sim.VARIANTEN.keys())

with st.sidebar:
    st.header("⚙️ Simulationseingaben")

    col_reset, col_info = st.columns([1, 1])
    with col_reset:
        if st.button("Standardwerte", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key.startswith("bw_"):
                    del st.session_state[key]
            st.rerun()
    with col_info:
        st.caption(f"Aktiv: **{st.session_state.get('bw_variante', p_default['variante'])}**")

    st.divider()
    st.subheader("Anlagenkonzept")
    variante = st.selectbox(
        "Zu berechnende Variante",
        varianten_liste,
        index=varianten_liste.index(p_default["variante"]),
        key="bw_variante",
    )

    hat_nf = "NF" in variante
    hat_fcdi = "FCDI" in variante

    st.subheader("Rohwasser")
    v_feed = st.number_input(
        "Rohwasser-Volumenstrom (m³/h)",
        min_value=0.1,
        max_value=10000.0,
        value=float(p_default["v_feed"]),
        step=0.5,
        format="%.2f",
        key="bw_v_feed",
        help="Volumenstrom des Rohwassers in m³/h.",
    )
    tds_feed = st.number_input(
        "TDS im Rohwasser (mg/L)",
        min_value=1.0,
        max_value=100000.0,
        value=float(p_default["tds_feed"]),
        step=100.0,
        format="%.1f",
        key="bw_tds_feed",
        help="Gesamter gelöster Feststoffgehalt in mg/L.",
    )
    so4_feed = st.number_input(
        "Sulfat im Rohwasser (mg/L)",
        min_value=0.0,
        max_value=100000.0,
        value=float(p_default["so4_feed"]),
        step=25.0,
        format="%.1f",
        key="bw_so4_feed",
    )

    with st.expander("UO – Umkehrosmose", expanded=True):
        y_uo = st.slider(
            "UO-Ausbeute (%)",
            1.0,
            99.0,
            float(p_default["y_uo"]),
            1.0,
            key="bw_y_uo",
        )

    with st.expander("NF – Nanofiltration", expanded=hat_nf):
        if not hat_nf:
            st.caption("In der gewählten Variante nicht aktiv (Werte bleiben im Hintergrund erhalten).")
        y_nf = st.slider(
            "NF-Ausbeute (%)",
            1.0,
            99.0,
            float(p_default["y_nf"]),
            1.0,
            key="bw_y_nf",
            disabled=not hat_nf,
        )
        p_nf = st.number_input(
            "NF-Zulaufdruck (bar)",
            min_value=0.0,
            max_value=100.0,
            value=float(p_default["p_nf"]),
            step=0.5,
            key="bw_p_nf",
            disabled=not hat_nf,
        )
        nf_modul = st.selectbox(
            "NF-Modul / Regression",
            ["A", "B"],
            index=0 if p_default["nf_modul"] == "A" else 1,
            key="bw_nf_modul",
            disabled=not hat_nf,
        )
        nf_energie_basis = st.selectbox(
            "Bezugsbasis NF-Energie",
            ["zulauf", "permeat"],
            index=["zulauf", "permeat"].index(p_default["nf_energie_basis"]),
            format_func=lambda x: "NF-Zulauf" if x == "zulauf" else "NF-Permeat",
            key="bw_nf_energie_basis",
            disabled=not hat_nf,
        )

    with st.expander("FCDI – Kapazitive Deionisation", expanded=hat_fcdi):
        if not hat_fcdi:
            st.caption("In der gewählten Variante nicht aktiv (Werte bleiben im Hintergrund erhalten).")
        y_fcdi = st.slider(
            "FCDI-Ausbeute (%)",
            1.0,
            99.0,
            float(p_default["y_fcdi"]),
            1.0,
            key="bw_y_fcdi",
            disabled=not hat_fcdi,
        )

    with st.expander("Energie, Bilanzierung und Modell", expanded=False):
        eta_pumpe = (
            st.slider(
                "Pumpenwirkungsgrad (%)",
                10,
                100,
                int(round(p_default["eta_pumpe"] * 100)),
                1,
                key="bw_eta_pumpe",
            )
            / 100.0
        )
        strompreis = st.number_input(
            "Strompreis (€/kWh)",
            min_value=0.0,
            max_value=10.0,
            value=float(p_default["strompreis"]),
            step=0.01,
            format="%.3f",
            key="bw_strompreis",
        )
        bilanz_modus = st.selectbox(
            "Bilanzierungsmodus",
            ["korrekt", "excel"],
            format_func=lambda x: (
                "Physikalisch konsistent" if x == "korrekt" else "Excel-Nachrechnung"
            ),
            key="bw_bilanz_modus",
        )
        range_modus = st.selectbox(
            "Umgang mit Modellgrenzen",
            ["extrapolieren", "streng"],
            format_func=lambda x: (
                "Außerhalb extrapolieren (mit Warnung)"
                if x == "extrapolieren"
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
        res = berechne_einzelvariante(p_einzel)
        vergleich = berechne_vergleich(p_basis)
except Exception as exc:
    st.error(f"Die Simulation konnte nicht berechnet werden: {exc}")
    st.exception(exc)
    st.stop()

kenn = res.get("kenn", {})
df = res.get("df")
warnungen = res.get("warnungen") or kenn.get("warnungen") or []


# ============================================================
# 5. WARNHINWEISE & HAUPTANSICHT IN TABS
# ============================================================

if warnungen:
    with st.container(border=True):
        st.warning(
            "**Modell- / Extrapolationswarnungen:**\n"
            + "\n".join(f"- {w}" for w in warnungen)
        )

tab_einzel, tab_vergleich, tab_studie = st.tabs(
    ["🔍 Einzelanlage & Fließbild", "📊 Variantenvergleich", "📈 Parameterstudie"]
)

with tab_einzel:
    st.subheader(f"Kennzahlen – {variante}")

    # Defensiver Zugriff auf gängige Kennzahlen-Keys aus `kenn`
    ausbeute = kenn.get("gesamtausbeute_pct", kenn.get("ausbeute_pct"))
    spec_energie = kenn.get("spez_energie_kwh_m3", kenn.get("energie_kwh_m3"))
    stromkosten = kenn.get("stromkosten_eur_m3", kenn.get("kosten_eur_m3"))
    permeat_tds = kenn.get("permeat_tds_mg_l", kenn.get("tds_produkt"))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Gesamtausbeute",
        f"{ausbeute:.1f} %" if isinstance(ausbeute, (int, float)) else "–",
    )
    k2.metric(
        "Spez. Energiebedarf",
        f"{spec_energie:.2f} kWh/m³" if isinstance(spec_energie, (int, float)) else "–",
    )
    k3.metric(
        "Spez. Stromkosten",
        f"{stromkosten:.3f} €/m³" if isinstance(stromkosten, (int, float)) else "–",
    )
    k4.metric(
        "Produkt-TDS",
        f"{permeat_tds:.1f} mg/L" if isinstance(permeat_tds, (int, float)) else "–",
    )

    st.subheader(f"Prozessfließbild – {variante}")

    if dar is not None and hasattr(dar, "build_svg"):
        try:
            svg = dar.build_svg(res)
            # Wenn ein <svg>-Tag vorhanden ist, Breite/Höhe responsiv machen, um Scrollbalken zu vermeiden
            svg_responsive = svg.replace(
                "<svg ",
                '<svg style="width:100%; height:100%; max-height:460px;" ',
                1,
            )
            components.html(svg_responsive, height=475, scrolling=False)
        except Exception as exc:
            st.warning(f"Das Prozessfließbild konnte nicht erzeugt werden: {exc}")
    else:
        st.info(
            "Für das dynamische Prozessfließbild bitte die Datei "
            "`darstellung.py` mit der Funktion `build_svg(res)` neben `app.py` ablegen."
        )

    if df is not None:
        with st.expander("Bilanz- / Stromtabelle anzeigen", expanded=False):
            st.dataframe(df, use_container_width=True)

with tab_vergleich:
    st.subheader("Vergleich aller vier Anlagenkonzepte")
    st.dataframe(vergleich, use_container_width=True)

with tab_studie:
    st.subheader("Parameterstudie")
    st.info(
        "Hier kannst du einen Eingangsparameter über einen Bereich variieren und den "
        "Verlauf ausgewählter Kennzahlen für die gewählte Variante plotten."
    )
