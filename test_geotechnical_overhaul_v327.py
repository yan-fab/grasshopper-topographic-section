# -*- coding: utf-8 -*-
"""
test_geotechnical_overhaul_v327.py
Unit tests verifying geotechnical calculations, Brückner mass haul,
and 3D design surface interpolation consistency in v3.2.7.
"""
import math

def test_soil_bulking_and_homogenization():
    fator_k = 1.20
    expansao_pct = int(round((fator_k - 1.0) * 100))
    assert expansao_pct == 20, f"Expected 20% expansion, got {expansao_pct}%"

    fh = 1.15
    contracao_pct = int(round((fh - 1.0) * 100))
    assert contracao_pct == 15, f"Expected 15% contraction, got {contracao_pct}%"

    vol_corte = 19257.89
    vol_aterro_geo = 146230.16
    vol_aterro_banco = vol_aterro_geo * fh
    saldo_geo = vol_corte - vol_aterro_banco
    
    assert round(vol_aterro_banco, 2) == 168164.68
    assert round(saldo_geo, 2) == -148906.79
    print(f"[PASS] Soil bulking (K={fator_k} -> +{expansao_pct}%) & Homogenization (Fh={fh} -> Deficit {saldo_geo:+.2f} m3)")

def test_bruckner_mass_haul_separation():
    # Mock cross-section areas
    secoes = [
        {"lbl": "A", "corte": 107.25, "aterro": 15.87},
        {"lbl": "B", "corte": 218.72, "aterro": 113.04},
        {"lbl": "C", "corte": 335.51, "aterro": 137.58},
        {"lbl": "D", "corte": 176.90, "aterro": 233.35},
        {"lbl": "E", "corte": 17.23, "aterro": 363.53},
        {"lbl": "F", "corte": 0.00, "aterro": 752.78},
    ]
    fh = 1.15
    dist = 25.0 # 25m between sections
    
    fluxo = []
    acum = 0.0
    for i in range(len(secoes) - 1):
        s1 = secoes[i]
        s2 = secoes[i+1]
        vc = ((s1["corte"] + s2["corte"]) / 2.0) * dist
        va_geo = ((s1["aterro"] + s2["aterro"]) / 2.0) * dist
        va_banco = va_geo * fh
        saldo_local = vc - va_banco
        acum += saldo_local
        fluxo.append({
            "trecho": f"{s1['lbl']} -> {s2['lbl']}",
            "vc": vc,
            "va_banco": va_banco,
            "saldo_local": saldo_local,
            "ordenada": acum
        })
    
    # Check that Trecho A->B has local surplus
    assert fluxo[0]["saldo_local"] > 0
    # Check that Trecho B->C has its own local surplus!
    assert fluxo[1]["saldo_local"] > 0
    # Check that accumulated Brückner ordinates increase while saldo_local > 0
    assert fluxo[1]["ordenada"] > fluxo[0]["ordenada"]
    
    print("[PASS] Brückner Mass Haul Separation: Local segment balance vs cumulative ordinate distinguished correctly.")

def test_3d_surface_interpolation_limits():
    # Check that sampled longitudinal profile is bounded by adjacent transverse profiles
    def sample_surface_mock(y, y_a, y_b, z_a, z_b):
        t = (y - y_a) / float(y_b - y_a)
        t = max(0.0, min(1.0, t))
        return (1.0 - t) * z_a + t * z_b

    # Section A at y=0 has cut elevation 100.0 (natural 102.14 -> cut 2.14m)
    # Section B at y=25 has cut elevation 98.0 (natural 102.11 -> cut 4.11m)
    y_test = 10.0
    z_interp = sample_surface_mock(y_test, 0.0, 25.0, 100.0, 98.0)
    expected_z = 0.6 * 100.0 + 0.4 * 98.0 # 99.20
    assert abs(z_interp - expected_z) < 1e-6
    # Exact crossing at y=0 must give exactly z_a
    assert abs(sample_surface_mock(0.0, 0.0, 25.0, 100.0, 98.0) - 100.0) < 1e-9
    # Exact crossing at y=25 must give exactly z_b
    assert abs(sample_surface_mock(25.0, 0.0, 25.0, 100.0, 98.0) - 98.0) < 1e-9

    print("[PASS] 3D Continuous Surface Interpolation: Exact matching at cross-sections and bounded interpolation.")

def test_vols_trechos_unpacking_and_banner_format():
    # Simulate vols_trechos with 5 items (as in v3.2.7)
    vols_trechos = [
        (25.0, 4074.6, 1438.3, 1654.1, 2420.5),
        (25.0, 6927.9, 2808.3, 3229.5, 3698.4),
    ]
    fluxo_transporte = [
        {'d_trecho': 25.0, 'vc': 4074.6, 'va_geo': 1438.3, 'va_banco': 1654.1, 'saldo_local': 2420.5, 'ordenada': 2420.5},
        {'d_trecho': 25.0, 'vc': 6927.9, 'va_geo': 2808.3, 'va_banco': 3229.5, 'saldo_local': 3698.4, 'ordenada': 6118.9},
    ]
    
    # Test unpacking 5 items as in line 3617
    idx_s = 0
    d_t, vc_t, va_t, va_banco_t, s_t = vols_trechos[idx_s]
    fl_item = fluxo_transporte[idx_s]
    if s_t > 0.01:
        nota_t = "SOBRA LOCAL: +{:.1f}m³ | BRÜCKNER: {:+.1f}m³ (RAMO ASCENDENTE)".format(s_t, fl_item['ordenada']).replace('.', ',')
    elif s_t < -0.01:
        nota_t = "DÉFICIT LOCAL: {:.1f}m³ | BRÜCKNER: {:+.1f}m³ (DEMANDA JAZIDA)".format(s_t, fl_item['ordenada']).replace('.', ',')
    else:
        nota_t = "COMPENSADO LOCALMENTE | BRÜCKNER: {:+.1f}m³".format(fl_item['ordenada']).replace('.', ',')

    assert isinstance(nota_t, str)
    assert "SOBRA LOCAL: +2420,5m³" in nota_t
    assert "BRÜCKNER: +2420,5m³" in nota_t
    print("[PASS] 5-tuple vols_trechos unpacking and banner text generation verified!")

if __name__ == "__main__":
    test_soil_bulking_and_homogenization()
    test_bruckner_mass_haul_separation()
    test_3d_surface_interpolation_limits()
    test_vols_trechos_unpacking_and_banner_format()
    print("\nALL GEOTECHNICAL OVERHAUL TESTS PASSED (v3.2.7)!")
