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

