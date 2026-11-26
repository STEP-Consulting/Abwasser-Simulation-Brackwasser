# -*- coding: utf-8 -*-
"""
Rechenkern: Brackwasser-Aufbereitung (UO, UO + NF, UO + FCDI, UO + NF + FCDI)

Abgeleitet aus der Excel-Simulation „E190_TP05_16-2 Simulierung Konzept 4 – Brackwasser“.
Prozess:  Rohwasser -> UO (Umkehrosmose) -> Permeat = Produkt
          UO-Konzentrat -> [NF] -> NF-Permeat zurück in den UO-Zulauf (Rezirkulation)
          UO- bzw. NF-Konzentrat -> [FCDI] -> Diluat = Produkt, Konzentrat = Sole

Die Rückhalte, Drücke und spezifischen Energien der Verfahren sind Surrogatmodelle
(lineare bzw. quadratische Regressionen) aus Simulations- und Versuchsdaten (siehe DATEN).
Rezirkulationen werden iterativ gelöst (statt Excel-Solver).

Zwei Betriebsmodi zur Nachrechnung der Excel-Datei:
  bilanz_modus="excel"   : UO-Konzentrat-Salzbilanz wie im Excel (NF-Permeat statt UO-Permeat abgezogen)
  nf_energie_basis="permeat": NF-Energie je m³ Permeat wie im Excel (statt je m³ NF-Zulauf)
Standard ist jeweils die physikalisch konsistente Variante ("korrekt" bzw. "zulauf").
"""

import copy
import math

import numpy as np
import pandas as pd

# =========================================================
# 1. DATEN UND KOEFFIZIENTEN
# =========================================================

# Rohdaten der Regressionen (Quelle: Excel, Blätter „Auswertung UO/NF/FCDI“, „Labordaten …“)
DATEN = {
    "uo_niedrig": {  # TDS-Feed 1.000 mg/L, UO-Simulation (WAVE)
        "ausbeute": [55, 65, 75, 85], "rej_tds": [99.154, 98.603, 98.052, 97.502], "rej_so4": [99.9, 99.9, 99.85, 99.8],
        "p_feed": [6.82, 8.27, 9.71, 11.16], "p_konz": [3.78, 5.74, 7.70, 9.65], "e_spec": [0.47, 0.44, 0.41, 0.39]},
    "uo_hoch": {  # TDS-Feed 10.000 mg/L
        "ausbeute": [55, 65, 75], "rej_tds": [99.0435, 98.9884, 98.9333], "rej_so4": [99.9, 99.875, 99.8],
        "p_feed": [21.52, 22.96, 24.41], "p_konz": [18.39, 20.34, 22.30], "e_spec": [1.31, 1.28, 1.25]},
    "nf_A": {"tds_feed": [3610, 7670, 18700], "rej_tds": [56.5097, 43.15515, 47.96791], "rej_so4": [85.0, 80.90909, 80.71429]},
    "nf_B": {"tds_feed": [3610, 7679, 18700], "rej_tds": [85.62327, 86.57106, 80.42781], "rej_so4": [98.33333, 99.35455, 97.28571]},
    "fcdi_niedrig": {"tds_feed": [5628.4, 9244.0, 9224.46667], "ausbeute": [50.0, 66.66667, 83.33333],
                     "rej_tds": [97.48216, 98.13139, 97.91884], "rej_so4": [92.12598, 98.14328, 97.89907], "e_spec": [3.029, 3.50296, 3.42245]},
    "fcdi_hoch": {"tds_feed": [35780.5, 37376.33333, 37524.0], "ausbeute": [50.0, 66.66667, 83.33333],
                  "rej_tds": [81.5352, 64.80671, 78.0419], "rej_so4": [81.22944, 65.63674, 78.05594], "e_spec": [17.63, 15.3363, 15.37806]},
}

# Koeffizienten wie in der Excel-Datei hinterlegt (Ausbeute in %, bei FCDI als Anteil 0..1)
UO_KOEFF = {
    "niedrig": dict(rej_tds=(-0.055, 102.175), rej_so4=(-0.0035, 100.1075), p_feed=(0.1446, -1.132), p_konz=(0.1957, -6.9815), e_spec=(-0.0027, 0.6165)),
    "hoch": dict(rej_tds=(-0.0055, 99.3442), rej_so4=(-0.005, 100.185), p_feed=(0.1445, 13.5708), p_konz=(0.1955, 7.6358), e_spec=(-0.003, 1.475)),
}
FCDI_KOEFF = {  # y = a*TDS_in + b*Ausbeute(Anteil) + c
    "niedrig": dict(rej_tds=(0.00024, -1.283192, 96.770159), e_spec=(0.000153, -0.48137, 2.411647), rej_so4=(0.001719, -0.01239, 83.0722)),
    "hoch": dict(rej_tds=(-0.021396, 102.43436, 795.870347), e_spec=(-0.001621, 1.746077, 74.756989), rej_so4=(-0.019348, 0.916995, 727.665571)),
}
NF_KOEFF_B = dict(rej_tds=(-5.2392e-08, 0.00082492, 83.3248), rej_so4=(-2.8999e-08, 0.00057804, 96.6212))

# Gültigkeitsbereiche (aus den Excel-Formeln)
UO_REJ_GRENZE = 5000.0             # < 5.000 mg/L: Regression 1.000 mg/L, sonst 10.000 mg/L
UO_PE_NIEDRIG_MAX = 2000.0         # Druck/Energie nur < 2.000 mg/L ...
UO_PE_HOCH = (9000.0, 11000.0)     # ... oder 9.000 bis 11.000 mg/L
NF_BEREICH = (2000.0, 20000.0)     # „Simulationsgrenzen“ NF-TDS-Feed
NF_DATENBEREICH = (3610.0, 18700.0)
FCDI_BEREICH_NIEDRIG = (3000.0, 13000.0)
FCDI_BEREICH_NIEDRIG_TDS_E = (2000.0, 13000.0)   # Blatt 4b: Rückhalt TDS und Energie ab 2.000 mg/L
FCDI_BEREICH_HOCH = (35000.0, 38000.0)
FCDI_AUSBEUTE_DATEN = (50.0, 83.4)
ANTISCALANT_MG_L = 3.0
HCL_MG_L = {"niedrig": 68.9, "hoch": 50.7}

VARIANTEN = {
    "UO (Bestand)": dict(nf=False, fcdi=False),
    "UO + NF": dict(nf=True, fcdi=False),
    "UO + FCDI": dict(nf=False, fcdi=True),
    "UO + NF + FCDI": dict(nf=True, fcdi=True),
}


def fit_linear(x, y):
    a, b = np.polyfit(np.asarray(x, float), np.asarray(y, float), 1)
    return float(a), float(b)


def fit_quadratisch(x, y):
    c = np.polyfit(np.asarray(x, float), np.asarray(y, float), 2)
    return tuple(float(v) for v in c)


def fit_ebene(tds, ausbeute_pct, y):
    """y = a*TDS + b*Ausbeute(Anteil) + c (exakt durch 3 Punkte)."""
    A = np.column_stack([np.asarray(tds, float), np.asarray(ausbeute_pct, float) / 100.0, np.ones(len(tds))])
    sol = np.linalg.lstsq(A, np.asarray(y, float), rcond=None)[0]
    return tuple(float(v) for v in sol)


def nf_koeff(modul):
    if modul == "B": return NF_KOEFF_B
    d = DATEN["nf_A"]
    return dict(rej_tds=fit_quadratisch(d["tds_feed"], d["rej_tds"]), rej_so4=fit_quadratisch(d["tds_feed"], d["rej_so4"]))


# =========================================================
# 2. SURROGATMODELLE
# =========================================================

def _clip_rej(x):
    return float(min(max(x, 0.0), 99.99))


def uo_eigenschaften(tds, ausbeute_pct, range_modus="extrapolieren"):
    """Rückhalte (%), Drücke (bar) und spez. Energie (kWh/m³ Permeat) der UO."""
    warn = []
    serie_rej = "niedrig" if tds < UO_REJ_GRENZE else "hoch"
    r = UO_KOEFF[serie_rej]
    out = dict(rej_tds=_clip_rej(r["rej_tds"][0] * ausbeute_pct + r["rej_tds"][1]),
               rej_so4=_clip_rej(r["rej_so4"][0] * ausbeute_pct + r["rej_so4"][1]), serie_rej=serie_rej)
    # Druck / Energie: Excel erlaubt nur 2 Bereiche
    if tds < UO_PE_NIEDRIG_MAX: serie = "niedrig"
    elif UO_PE_HOCH[0] <= tds <= UO_PE_HOCH[1]: serie = "hoch"
    else: serie = None
    if serie is None:
        if range_modus == "streng":
            out.update(p_feed=math.nan, p_konz=math.nan, e_spec=math.nan, serie_pe=None)
            warn.append(f"UO: Zulauf-TDS {tds:,.0f} mg/L außerhalb der Simulationsgrenzen für Druck/Energie (<2.000 oder 9.000–11.000 mg/L).")
            return out | dict(warnungen=warn)
        serie = "niedrig" if tds < UO_REJ_GRENZE else "hoch"
        warn.append(f"UO: Zulauf-TDS {tds:,.0f} mg/L außerhalb der Datenbereiche für Druck/Energie; Regression '{serie}' extrapoliert.")
    k = UO_KOEFF[serie]
    out.update(p_feed=k["p_feed"][0] * ausbeute_pct + k["p_feed"][1], p_konz=k["p_konz"][0] * ausbeute_pct + k["p_konz"][1],
               e_spec=k["e_spec"][0] * ausbeute_pct + k["e_spec"][1], serie_pe=serie)
    d = DATEN["uo_" + serie]
    if not (min(d["ausbeute"]) <= ausbeute_pct <= max(d["ausbeute"])):
        warn.append(f"UO: Ausbeute {ausbeute_pct:.0f} % außerhalb des Datenbereichs {min(d['ausbeute'])}–{max(d['ausbeute'])} % (Regression '{serie}').")
    if tds < 1000 * 0.5:
        warn.append(f"UO: Zulauf-TDS {tds:,.0f} mg/L deutlich unter dem Datenbereich (1.000 mg/L).")
    return out | dict(warnungen=warn)


def nf_eigenschaften(tds, modul="B"):
    """TDS- und Sulfat-Rückhalt (%) der NF in Abhängigkeit vom NF-Zulauf-TDS (quadratische Regression)."""
    k = nf_koeff(modul); warn = []
    rt = k["rej_tds"][0] * tds ** 2 + k["rej_tds"][1] * tds + k["rej_tds"][2]
    rs = k["rej_so4"][0] * tds ** 2 + k["rej_so4"][1] * tds + k["rej_so4"][2]
    if not (NF_BEREICH[0] <= tds <= NF_BEREICH[1]):
        warn.append(f"NF: Zulauf-TDS {tds:,.0f} mg/L außerhalb der Simulationsgrenzen {NF_BEREICH[0]:,.0f}–{NF_BEREICH[1]:,.0f} mg/L.".replace(",", "."))
    elif not (NF_DATENBEREICH[0] <= tds <= NF_DATENBEREICH[1]):
        warn.append(f"NF: Zulauf-TDS {tds:,.0f} mg/L liegt außerhalb der Messpunkte ({NF_DATENBEREICH[0]:,.0f}–{NF_DATENBEREICH[1]:,.0f} mg/L), Regression wird extrapoliert.".replace(",", "."))
    return dict(rej_tds=_clip_rej(rt), rej_so4=_clip_rej(rs), warnungen=warn)


def fcdi_eigenschaften(tds, ausbeute_pct, range_modus="extrapolieren", excel=False):
    """TDS-/Sulfat-Rückhalt (%) und spez. Energie (kWh/m³ Diluat) der FCDI.

    excel=True: Sulfat-Ausbeutekoeffizient wie im Excel verwendet (dort in %-Einheiten, aber mit Ausbeute als Anteil multipliziert,
    dadurch 100-fach zu klein). excel=False: Koeffizient wird korrekt auf Ausbeute als Anteil umgerechnet (x100)."""
    warn = []; y = ausbeute_pct / 100.0
    def ebene(k, so4=False): return k[0] * tds + k[1] * (100.0 if (so4 and not excel) else 1.0) * y + k[2]
    lo_t, hi_t = FCDI_BEREICH_NIEDRIG_TDS_E; lo_s, hi_s = FCDI_BEREICH_NIEDRIG
    in_hoch = FCDI_BEREICH_HOCH[0] <= tds <= FCDI_BEREICH_HOCH[1]
    res = {}
    for key, rng in (("rej_tds", (lo_t, hi_t)), ("e_spec", (lo_t, hi_t)), ("rej_so4", (lo_s, hi_s))):
        if rng[0] <= tds <= rng[1]: serie = "niedrig"
        elif in_hoch: serie = "hoch"
        else:
            if range_modus == "streng": res[key] = math.nan; continue
            serie = "niedrig" if tds < 24000 else "hoch"
        v = ebene(FCDI_KOEFF[serie][key], so4=(key == "rej_so4")); res[key] = v if key == "e_spec" else _clip_rej(v)
    if any(math.isnan(v) for v in res.values()):
        warn.append(f"FCDI: Zulauf-TDS {tds:,.0f} mg/L außerhalb der Simulationsgrenzen ({lo_s:,.0f}–{hi_s:,.0f} bzw. 35.000–38.000 mg/L); betroffene Werte nicht berechenbar.".replace(",", "."))
    elif not (lo_s <= tds <= hi_s or in_hoch):
        warn.append(f"FCDI: Zulauf-TDS {tds:,.0f} mg/L außerhalb der Simulationsgrenzen; Regression extrapoliert.".replace(",", "."))
    elif tds < lo_s:
        warn.append(f"FCDI: Zulauf-TDS {tds:,.0f} mg/L unter 3.000 mg/L: Sulfat-Rückhalt außerhalb der Messpunkte.".replace(",", "."))
    if not (FCDI_AUSBEUTE_DATEN[0] <= ausbeute_pct <= FCDI_AUSBEUTE_DATEN[1]):
        warn.append(f"FCDI: Ausbeute {ausbeute_pct:.0f} % außerhalb des Datenbereichs 50–83 % (Excel erlaubt 50–90 %).")
    if in_hoch:
        warn.append("FCDI: Regression für 35.000–38.000 mg/L beruht auf 3 Punkten mit teils unplausiblen Rückhalten; nur mit Vorsicht verwenden.")
    return res | dict(warnungen=warn)


# =========================================================
# 3. PARAMETER UND SIMULATION
# =========================================================

def standard_parameter():
    return dict(
        variante="UO + NF + FCDI", nf=True, fcdi=True,
        v_feed=10.0, tds_feed=1000.0, so4_feed=200.0,
        y_uo=55.0, y_nf=50.0, p_nf=12.0, y_fcdi=50.0,
        eta_pumpe=0.75, nf_modul="B",
        bilanz_modus="korrekt",          # "korrekt" | "excel"
        nf_energie_basis="zulauf",       # "zulauf" | "permeat"
        range_modus="extrapolieren",     # "extrapolieren" | "streng"
        strompreis=0.20,                 # €/kWh (Annahme)
    )


def mit_variante(p, name):
    q = copy.deepcopy(p); q["variante"] = name; q.update(VARIANTEN[name]); return q


def _loesen(p, warn):
    v1, c1, s1 = p["v_feed"], p["tds_feed"], p["so4_feed"]
    yu, yn = p["y_uo"] / 100.0, p["y_nf"] / 100.0
    nf = bool(p["nf"])
    v2 = v1 / (1.0 - (1.0 - yu) * yn) if nf else v1
    v3 = yu * v2; v4 = v2 - v3
    v5 = yn * v4 if nf else 0.0
    v6 = v4 - v5 if nf else v4
    c2, s2 = c1, s1; c5 = s5 = 0.0
    it = 0
    for it in range(1, 2001):
        uo = uo_eigenschaften(c2, p["y_uo"], p["range_modus"])
        c3 = c2 * (1 - uo["rej_tds"] / 100.0); s3 = s2 * (1 - uo["rej_so4"] / 100.0)
        if nf and p["bilanz_modus"] == "excel":
            c4 = (c2 * v2 - c5 * v5) / v4; s4 = (s2 * v2 - s5 * v5) / v4
        else:
            c4 = (c2 * v2 - c3 * v3) / v4; s4 = (s2 * v2 - s3 * v3) / v4
        if nf:
            nfp = nf_eigenschaften(c4, p["nf_modul"])
            c5n = c4 * (1 - nfp["rej_tds"] / 100.0); s5n = s4 * (1 - nfp["rej_so4"] / 100.0)
            c2n = (v1 * c1 + v5 * c5n) / v2; s2n = (v1 * s1 + v5 * s5n) / v2
            dif = abs(c2n - c2) + abs(s2n - s2) + abs(c5n - c5) + abs(s5n - s5)
            c2, s2, c5, s5 = c2n, s2n, c5n, s5n
        else:
            dif = 0.0
        if dif < 1e-11: break
    # konsistente Endwerte
    uo = uo_eigenschaften(c2, p["y_uo"], p["range_modus"])
    c3 = c2 * (1 - uo["rej_tds"] / 100.0); s3 = s2 * (1 - uo["rej_so4"] / 100.0)
    if nf and p["bilanz_modus"] == "excel":
        c4 = (c2 * v2 - c5 * v5) / v4; s4 = (s2 * v2 - s5 * v5) / v4
    else:
        c4 = (c2 * v2 - c3 * v3) / v4; s4 = (s2 * v2 - s3 * v3) / v4
    nfp = None
    if nf:
        nfp = nf_eigenschaften(c4, p["nf_modul"])
        c5 = c4 * (1 - nfp["rej_tds"] / 100.0); s5 = s4 * (1 - nfp["rej_so4"] / 100.0)
        c6 = (c4 * v4 - c5 * v5) / v6; s6 = (s4 * v4 - s5 * v5) / v6
    else:
        c6, s6 = c4, s4
    warn += uo["warnungen"]
    if nfp: warn += nfp["warnungen"]
    return dict(v2=v2, v3=v3, v4=v4, v5=v5, v6=v6, c2=c2, s2=s2, c3=c3, s3=s3, c4=c4, s4=s4, c5=c5, s5=s5, c6=c6, s6=s6,
                uo=uo, nfp=nfp, iterationen=it, konvergenz_diff=dif)


def simuliere(p):
    """Berechnet Stoffströme, Konzentrationen, Energie und Chemikalien für eine Variante."""
    warn = []
    nf, fcdi = bool(p["nf"]), bool(p["fcdi"])
    if p["y_uo"] >= 99 or p["y_uo"] <= 0: raise ValueError("UO-Ausbeute muss zwischen 0 und 99 % liegen.")
    s = _loesen(p, warn)
    v1, c1, s1 = p["v_feed"], p["tds_feed"], p["so4_feed"]
    fc = None
    if fcdi:
        v_in, c_in, s_in = s["v6"], s["c6"], s["s6"]
        yf = p["y_fcdi"] / 100.0
        fc = fcdi_eigenschaften(c_in, p["y_fcdi"], p["range_modus"], excel=(p["bilanz_modus"] == "excel")); warn += fc["warnungen"]
        vd = yf * v_in; vc = v_in - vd
        cd = c_in * (1 - fc["rej_tds"] / 100.0) if not math.isnan(fc["rej_tds"]) else math.nan
        sd = s_in * (1 - fc["rej_so4"] / 100.0) if not math.isnan(fc["rej_so4"]) else math.nan
        cc = (c_in * v_in - cd * vd) / vc if not math.isnan(cd) else math.nan
        sc_ = (s_in * v_in - sd * vd) / vc if not math.isnan(sd) else math.nan
    else:
        vd = vc = 0.0; cd = sd = cc = sc_ = 0.0
    vp = s["v3"] + vd
    cp = (s["v3"] * s["c3"] + vd * cd) / vp if not math.isnan(cd) else math.nan
    sp = (s["v3"] * s["s3"] + vd * sd) / vp if not math.isnan(sd) else math.nan
    if fcdi: vb, cb, sb = vc, cc, sc_
    else: vb, cb, sb = s["v6"], s["c6"], s["s6"]

    # --- Energie (kW bzw. kWh/m³ Produkt)
    uo = s["uo"]
    e_uo_spez_perm = uo["e_spec"]; p_uo = e_uo_spez_perm * s["v3"]
    if nf:
        dp = max(p["p_nf"] - uo["p_konz"], 0.0) if not math.isnan(uo["p_konz"]) else math.nan
        basis_v = s["v4"] if p["nf_energie_basis"] == "zulauf" else s["v5"]
        p_nf = basis_v * dp / (36.0 * p["eta_pumpe"]) if not math.isnan(dp) else math.nan
        e_nf_spez_perm = (dp / (36.0 * p["eta_pumpe"]) if not math.isnan(dp) else math.nan)
    else:
        dp = 0.0; p_nf = 0.0; e_nf_spez_perm = 0.0
    p_fc = fc["e_spec"] * vd if fcdi and not math.isnan(fc["e_spec"]) else (math.nan if fcdi else 0.0)
    p_ges = p_uo + p_nf + p_fc
    spez = {k: v / vp for k, v in (("UO", p_uo), ("NF", p_nf), ("FCDI", p_fc))}
    spez["gesamt"] = p_ges / vp
    # --- Chemikalien (je m³ Produkt, g/m³): Dosierung am UO-Zulauf
    serie_chem = "niedrig" if s["c2"] < UO_REJ_GRENZE else "hoch"
    chem = dict(antiscalant=ANTISCALANT_MG_L * s["v2"] / vp, hcl=HCL_MG_L[serie_chem] * s["v2"] / vp)

    # --- Stromtabelle
    zeilen = [
        ("1 Rohwasser", v1, c1, s1), ("2 UO-Zulauf", s["v2"], s["c2"], s["s2"]), ("3 UO-Permeat", s["v3"], s["c3"], s["s3"]),
        ("4 UO-Konzentrat", s["v4"], s["c4"], s["s4"]),
    ]
    if nf: zeilen += [("5 NF-Permeat (Rezirkulation)", s["v5"], s["c5"], s["s5"]), ("6 NF-Konzentrat", s["v6"], s["c6"], s["s6"])]
    if fcdi: zeilen += [("7 FCDI-Diluat", vd, cd, sd), ("8 FCDI-Konzentrat", vc, cc, sc_)]
    zeilen += [("P Produkt", vp, cp, sp), ("B Sole (Abfluss)", vb, cb, sb)]
    df = pd.DataFrame(zeilen, columns=["Strom", "Volumenstrom (m³/h)", "TDS (mg/L)", "Sulfat (mg/L)"])
    df["TDS-Fracht (g/h)"] = df["Volumenstrom (m³/h)"] * df["TDS (mg/L)"]

    wasser_abw = v1 - vp - vb
    salz_abw = (v1 * c1 - vp * cp - vb * cb) if not (math.isnan(cp) or math.isnan(cb)) else math.nan
    kenn = dict(
        v_produkt=vp, tds_produkt=cp, so4_produkt=sp, v_sole=vb, tds_sole=cb, so4_sole=sb,
        ausbeute=vp / v1 * 100.0, rueckhalt_gesamt=(1 - cp / c1) * 100.0 if not math.isnan(cp) else math.nan,
        rueckhalt_so4_gesamt=(1 - sp / s1) * 100.0 if not math.isnan(sp) else math.nan,
        leistung_kw=p_ges, p_uo_kw=p_uo, p_nf_kw=p_nf, p_fcdi_kw=p_fc,
        e_spez=spez, energiekosten_ct_m3=spez["gesamt"] * p["strompreis"] * 100.0,
        chemikalien=chem, wasserbilanz_abw=wasser_abw, salzbilanz_abw=salz_abw,
        uo=uo, nf=s["nfp"], fcdi=fc, p_nf_feed=p["p_nf"] if nf else math.nan, dp_nf_boost=dp,
        e_nf_spez_perm=e_nf_spez_perm, iterationen=s["iterationen"], volumen_uo_zulauf=s["v2"],
        gueltig=not any(math.isnan(x) for x in (cp, p_ges, cb)),
    )
    # Warnungen eindeutig machen
    seen = []
    for w in warn:
        if w not in seen: seen.append(w)
    return dict(df=df, kenn=kenn, warnungen=seen, s=s, parameter=copy.deepcopy(p))


def vergleich(p):
    """Rechnet alle vier Varianten mit denselben Eingaben."""
    return {n: simuliere(mit_variante(p, n)) for n in VARIANTEN}


def parameterstudie(p, schluessel, werte, ausgaben=("ausbeute", "tds_produkt", "e_gesamt", "v_sole")):
    zeilen = []
    for w in werte:
        q = copy.deepcopy(p); q[schluessel] = float(w)
        try:
            r = simuliere(q); k = r["kenn"]
            zeilen.append({schluessel: float(w), "ausbeute": k["ausbeute"], "tds_produkt": k["tds_produkt"], "e_gesamt": k["e_spez"]["gesamt"],
                           "v_sole": k["v_sole"], "tds_sole": k["tds_sole"], "v_produkt": k["v_produkt"], "warnungen": len(r["warnungen"])})
        except ValueError:
            zeilen.append({schluessel: float(w)})
    return pd.DataFrame(zeilen)


# Referenzwerte aus der Excel-Datei (Zwischenspeicher der Solver-Ergebnisse)
EXCEL_REFERENZ = {
    "4a": dict(v2=12.9032, c2=834.7134, v3=7.0968, c3=7.0951, c4=1722.2222, c5=265.3928, c6=3179.0517, c8=6259.2837, v_diluat=1.4516, c_diluat=98.8197,
               v_produkt=8.5484, c_produkt=22.6709, ausbeute=85.4839, e_gesamt=0.9431, e_uo=0.3885, e_nf=0.1034, e_fcdi=0.4512),
    "UO+NF": dict(v2=12.9032, c2=834.7134, c3=7.0951, c4=1722.2222, c5=265.3928, c6=3179.0517, v_produkt=7.0968, ausbeute=70.9677),
    "Bestand": dict(v2=12.1212, c2=886.9651, c3=12.4175, c4=2357.1429, c5=354.0863, c6=4360.1994, v_produkt=7.8788, ausbeute=78.7879),
    "4b": dict(v3=5.5, c4=2211.8333, c_diluat=73.8884, c8=4349.7782, c_produkt=27.4837, ausbeute=77.5, e_gesamt=1.0607),
}
