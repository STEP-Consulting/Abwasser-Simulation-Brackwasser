# -*- coding: utf-8 -*-
"""Tests für brack_simulation.py  (pytest oder: python test_brack_simulation.py)"""
import math
import numpy as np
import brack_simulation as bs


def lauf(name="UO + NF + FCDI", **kw):
    p = bs.mit_variante(bs.standard_parameter(), name); p.update(kw); return bs.simuliere(p)

def tab(r): return r["df"].set_index("Strom")
def nahe(a, b, tol=2e-4): return abs(a - b) <= tol * max(1.0, abs(b))


# ---------- Nachrechnung der Excel-Datei (Excel-Modus) ----------
def test_excel_4a():
    R = bs.EXCEL_REFERENZ["4a"]; r = lauf(bilanz_modus="excel", nf_energie_basis="permeat"); d = tab(r); k = r["kenn"]
    assert nahe(d.loc["2 UO-Zulauf", "Volumenstrom (m³/h)"], R["v2"]); assert nahe(d.loc["2 UO-Zulauf", "TDS (mg/L)"], R["c2"])
    assert nahe(d.loc["4 UO-Konzentrat", "TDS (mg/L)"], R["c4"]); assert nahe(d.loc["5 NF-Permeat (Rezirkulation)", "TDS (mg/L)"], R["c5"])
    assert nahe(d.loc["6 NF-Konzentrat", "TDS (mg/L)"], R["c6"]); assert nahe(d.loc["8 FCDI-Konzentrat", "TDS (mg/L)"], R["c8"])
    assert nahe(k["tds_produkt"], R["c_produkt"]); assert nahe(k["ausbeute"], R["ausbeute"])
    assert nahe(k["e_spez"]["gesamt"], R["e_gesamt"]); assert nahe(k["e_spez"]["NF"], R["e_nf"]); assert nahe(k["e_spez"]["FCDI"], R["e_fcdi"])
    # Sulfat (Excel-Werte Zeile 55)
    for stufe, ref in (("2 UO-Zulauf", 156.9137), ("3 UO-Permeat", 0.1334), ("4 UO-Konzentrat", 344.4444), ("5 NF-Permeat (Rezirkulation)", 8.5054),
                       ("6 NF-Konzentrat", 680.3835), ("8 FCDI-Konzentrat", 1282.7325), ("7 FCDI-Diluat", 78.0346), ("P Produkt", 13.3619)):
        assert nahe(d.loc[stufe, "Sulfat (mg/L)"], ref), stufe

def test_excel_uo_nf_und_bestand():
    R = bs.EXCEL_REFERENZ["UO+NF"]; r = lauf("UO + NF", bilanz_modus="excel"); d = tab(r)
    assert nahe(d.loc["4 UO-Konzentrat", "TDS (mg/L)"], R["c4"]); assert nahe(d.loc["6 NF-Konzentrat", "TDS (mg/L)"], R["c6"]); assert nahe(r["kenn"]["ausbeute"], R["ausbeute"])
    B = bs.EXCEL_REFERENZ["Bestand"]; r = lauf("UO + NF", y_uo=65.0, bilanz_modus="excel"); d = tab(r)
    for stufe, key in (("2 UO-Zulauf", "c2"), ("3 UO-Permeat", "c3"), ("4 UO-Konzentrat", "c4"), ("5 NF-Permeat (Rezirkulation)", "c5"), ("6 NF-Konzentrat", "c6")):
        assert nahe(d.loc[stufe, "TDS (mg/L)"], B[key]), stufe
    assert nahe(d.loc["2 UO-Zulauf", "Volumenstrom (m³/h)"], B["v2"]); assert nahe(r["kenn"]["ausbeute"], B["ausbeute"])

def test_excel_4b_streng_sulfat_nicht_berechenbar():
    R = bs.EXCEL_REFERENZ["4b"]; r = lauf("UO + FCDI", range_modus="streng"); d = tab(r); k = r["kenn"]
    assert nahe(d.loc["4 UO-Konzentrat", "TDS (mg/L)"], R["c4"]); assert nahe(d.loc["7 FCDI-Diluat", "TDS (mg/L)"], R["c_diluat"])
    assert nahe(d.loc["8 FCDI-Konzentrat", "TDS (mg/L)"], R["c8"]); assert nahe(k["tds_produkt"], R["c_produkt"]); assert nahe(k["e_spez"]["gesamt"], R["e_gesamt"])
    assert math.isnan(d.loc["7 FCDI-Diluat", "Sulfat (mg/L)"])        # wie im Excel: Sulfat außerhalb 3.000–13.000 mg/L


# ---------- Physik ----------
def test_bilanzen_korrekter_modus():
    for n in bs.VARIANTEN:
        for y_uo in (50.0, 55.0, 65.0, 75.0):
            r = lauf(n, y_uo=y_uo); k = r["kenn"]
            assert abs(k["wasserbilanz_abw"]) < 1e-9 and abs(k["salzbilanz_abw"]) < 1e-6, (n, y_uo)
            d = tab(r)
            assert abs(d.loc["P Produkt", "Volumenstrom (m³/h)"] + d.loc["B Sole (Abfluss)", "Volumenstrom (m³/h)"] - 10.0) < 1e-9
            # Sulfatbilanz
            s_in = 10.0 * 200.0; s_out = k["v_produkt"] * k["so4_produkt"] + k["v_sole"] * k["so4_sole"]
            assert abs(s_in - s_out) < 1e-6

def test_excel_modus_ist_nicht_bilanziert():
    r = lauf("UO + NF + FCDI", bilanz_modus="excel")
    assert abs(r["kenn"]["salzbilanz_abw"]) > 100.0       # bekannter Fehler der Excel-Salzbilanz (NF- statt UO-Permeat)

def test_konvergenz_und_rezirkulation():
    r = lauf("UO + NF"); assert r["kenn"]["iterationen"] < 100
    assert nahe(r["kenn"]["volumen_uo_zulauf"], 10.0 / (1 - 0.45 * 0.5))
    assert lauf("UO (Bestand)")["kenn"]["volumen_uo_zulauf"] == 10.0

def test_ausbeute_und_produktreihenfolge():
    a = {n: lauf(n)["kenn"]["ausbeute"] for n in bs.VARIANTEN}
    assert a["UO (Bestand)"] < a["UO + NF"] < a["UO + NF + FCDI"] and a["UO + FCDI"] > a["UO (Bestand)"]

def test_energie_nf_korrekt_gegen_excel():
    r1 = lauf("UO + NF", nf_energie_basis="zulauf")["kenn"]; r2 = lauf("UO + NF", nf_energie_basis="permeat")["kenn"]
    assert nahe(r1["p_nf_kw"], 2.0 * r2["p_nf_kw"])           # bei 50 % NF-Ausbeute genau Faktor 2

def test_nf_energie_formel():
    k = lauf("UO + NF")["kenn"]
    erwartet = lauf("UO + NF")["s"]["v4"] * (12.0 - k["uo"]["p_konz"]) / (36.0 * 0.75)
    assert nahe(k["p_nf_kw"], erwartet)

def test_monotonie_uo_ausbeute():
    st = bs.parameterstudie(bs.mit_variante(bs.standard_parameter(), "UO (Bestand)"), "y_uo", [55, 60, 65, 70, 75, 80])
    assert (np.diff(st["v_sole"]) < 0).all()                  # höhere Ausbeute -> weniger Sole
    assert (np.diff(st["tds_produkt"]) > 0).all()             # höhere Ausbeute -> schlechtere Qualität

def test_regressionskoeffizienten_aus_daten():
    for serie in ("niedrig", "hoch"):
        d = bs.DATEN["uo_" + serie]
        for g, k in (("rej_tds", "rej_tds"), ("p_feed", "p_feed"), ("p_konz", "p_konz"), ("e_spec", "e_spec")):
            a, b = bs.fit_linear(d["ausbeute"], d[g]); ae, be = bs.UO_KOEFF[serie][k]
            assert abs(a - ae) < 2e-3 and abs(b - be) < 0.2, (serie, g, a, ae, b, be)
    d = bs.DATEN["nf_B"]; c = bs.fit_quadratisch(d["tds_feed"], d["rej_tds"])
    for v in (3610.0, 7679.0, 18700.0):
        ref = sum(x * v ** (2 - i) for i, x in enumerate(bs.NF_KOEFF_B["rej_tds"])); fit = sum(x * v ** (2 - i) for i, x in enumerate(c))
        assert abs(ref - fit) < 0.05
    d = bs.DATEN["fcdi_niedrig"]
    for g in ("rej_tds", "e_spec", "rej_so4"):
        e = bs.fit_ebene(d["tds_feed"], d["ausbeute"], d[g]); k = list(bs.FCDI_KOEFF["niedrig"][g])
        if g == "rej_so4": k[1] *= 100.0            # Excel-Koeffizient ist in %-Einheiten
        for a, b in zip(e, k): assert abs(a - b) < 0.03 * max(1.0, abs(b)), (g, a, b)

def test_warnungen_ausserhalb_bereich():
    r = lauf("UO + NF + FCDI", tds_feed=1000.0)
    assert any("NF" in w for w in r["warnungen"])             # UO-Konzentrat ~1.850 mg/L < 2.000 mg/L
    r = lauf("UO (Bestand)", tds_feed=20000.0); assert any("UO" in w for w in r["warnungen"])

def test_ungueltige_eingabe():
    try: lauf(y_uo=100.0); assert False
    except ValueError: pass

def test_eingabe_unveraendert():
    p = bs.standard_parameter(); q = dict(p); bs.simuliere(bs.mit_variante(p, "UO + NF")); assert p == q


if __name__ == "__main__":
    ts = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]; fehler = 0
    for n, f in ts:
        try: f(); print("OK    ", n)
        except Exception as e: fehler += 1; print("FEHLER", n, "->", repr(e))
    print(f"\n{len(ts) - fehler}/{len(ts)} Tests bestanden"); raise SystemExit(1 if fehler else 0)
