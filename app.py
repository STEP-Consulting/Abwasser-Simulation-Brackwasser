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
