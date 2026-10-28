# -*- coding: utf-8 -*-
"""
===============================================================================
CORTE TOPOGRÁFICO ARQUITETÔNICO COM SELETOR DE COTAS (NBR 6492)
===============================================================================
Algoritmo paramétrico para Grasshopper (Rhinoceros 8 / GhPython).
Gera cortes topográficos e arquitetônicos interceptando edificações, telhados/beirais,
platôs terraplenados, taludes de aterro e rampas de acesso, com marcadores de nível NBR 6492
e seletor integrado de cotas.

MODOS DO SELETOR:
  0 - Todas as Cotas e Níveis (Terreno Natural + Projeto Proposto)
  1 - Apenas Cotas do Projeto (+ Perfil do Terreno Natural) [Padrão]
  2 - Apenas Cotas do Terreno Natural

ENTRADAS (INPUTS - Bilíngue Português / English):
  Terreno / Terrain               [List, Curve/Mesh] : Curvas de nível 3D ou malha topográfica.
  LinhaCorte / CutLine            [Item/List, Curve] : Linha de corte em planta baixa.
  Ponto / Point                   [Item, Point3d]    : Ponto base de inserção da seção 2D [Opcional].
  Edificacao / Casa / Building    [Item, Curve]      : Projeção da edificação [Opcional].
  Cobertura / Telhado / Roof      [Item, Curve]      : Projeção da cobertura/beiral [Opcional].
  Plato / PlatoEntrada / Pad      [Item, Curve]      : Curva limite do platô terraplenado [Opcional].
  Aterro / Embankment / Fill      [Item, Curve]      : Talude ou aterro projetado [Opcional].
  Descida / Entrada / Ramp        [Item, Curve]      : Rampa de acesso ou descida [Opcional].
  Seletor / Mode / Selector       [Item, int]        : Modo de exibição das cotas (0, 1 ou 2, padrão: 1).
  NivelPiso / FloorLevel          [Item, float]      : Cota de nível do piso acabado (Z) [Opcional].
  NivelPlato / PadLevel           [Item, float]      : Cota de nível do platô de terraplenagem (Z) [Opcional].
  NivelAterro / FillLevel         [Item, float]      : Cota de nível do topo do aterro (Z) [Opcional].
  Altura / Height                 [Item, float]      : Pé-direito da edificação (padrão: 3.0 m).
  Espessura / Thickness           [Item, float]      : Espessura da laje (padrão: 0.20 m).
  Escala / Scale                  [Item, float]      : Fator de escala dos símbolos e textos NBR (padrão: 1.0).

SAÍDAS (OUTPUTS):
  a : Linha 3D de corte sobre o terreno natural (Coordenadas de Mundo).
  b : Curva 2D do perfil do terreno natural.
  c : Desenho 2D Completo do Corte Arquitetônico Técnico com níveis NBR, cotas, fundação e edificação.
  d : Cotas de Projeto (edificação, beirais, platô, fundações).
  e : Cotas do Terreno Natural (distâncias e níveis do terreno).
  f : Memorial Técnico do Corte Arquitetônico e Relatório de Níveis (Panel).
===============================================================================
"""

import math
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs

def to_rhino_curve(geo):
    if geo is None: return None
    if isinstance(geo, rg.Curve): return geo
    if isinstance(geo, rg.Line): return rg.LineCurve(geo)
    if hasattr(geo, "Value"): return to_rhino_curve(geo.Value)
    try:
        c = rs.coercecurve(geo)
        if c: return c
    except: pass
    try:
        doc = Rhino.RhinoDoc.ActiveDoc
        if doc:
            obj = doc.Objects.FindId(geo)
            if obj and isinstance(obj.Geometry, rg.Curve):
                return obj.Geometry
    except: pass
    return None

def to_rhino_geom(geo):
    if geo is None: return None
    if isinstance(geo, (rg.Curve, rg.Mesh, rg.Brep)): return geo
    if isinstance(geo, rg.Line): return rg.LineCurve(geo)
    if hasattr(geo, "Value"): return to_rhino_geom(geo.Value)
    try:
        c = rs.coercecurve(geo)
        if c: return c
    except: pass
    try:
        m = rs.coercemesh(geo)
        if m: return m
    except: pass
    try:
        b = rs.coercebrep(geo)
        if b: return b
    except: pass
    try:
        doc = Rhino.RhinoDoc.ActiveDoc
        if doc:
            obj = doc.Objects.FindId(geo)
            if obj: return obj.Geometry
    except: pass
    return None

def to_rhino_point(val):
    if val is None: return None
    if isinstance(val, rg.Point3d): return val
    if isinstance(val, rg.Point): return val.Location
    if hasattr(val, "Value"): return to_rhino_point(val.Value)
    if hasattr(val, "Location"): return val.Location
    try:
        pt = rs.coerce3dpoint(val)
        if pt: return pt
    except: pass
    try:
        doc = Rhino.RhinoDoc.ActiveDoc
        if doc:
            obj = doc.Objects.FindId(val)
            if obj and isinstance(obj.Geometry, rg.Point):
                return obj.Geometry.Location
    except: pass
    return None

def to_list(val):
    if val is None: return []
    if isinstance(val, (list, tuple)): return list(val)
    return [val]

def parse_seletor(val):
    """
    Parses selector input:
    0: All dimensions & levels (Complete)
    1: Proposed project dimensions only (+ natural profile) [Default]
    2: Natural terrain dimensions only
    """
    if val is None:
        return 1 # Default: proposed project dimensions + natural profile
    if isinstance(val, bool):
        return 1 if val else 2
    try:
        ival = int(val)
        if ival in [0, 1, 2]:
            return ival
    except:
        pass
    s = str(val).strip().lower()
    if "proj" in s:
        return 1
    elif "nat" in s or "tn" in s:
        return 2
    elif "tod" in s or "all" in s or "tudo" in s:
        return 0
    return 1

def make_filled_mesh(v0, v1, v2):
    m = rg.Mesh()
    m.Vertices.Add(v0)
    m.Vertices.Add(v1)
    m.Vertices.Add(v2)
    m.Faces.AddFace(0, 1, 2)
    m.Normals.ComputeNormals()
    return m

def make_text_entity(text_str, pt, height):
    try:
        plane = rg.Plane(pt, rg.Vector3d.ZAxis)
        te = rg.TextEntity()
        te.PlainText = text_str
        te.Plane = plane
        te.TextHeight = height
        te.Justification = rg.TextJustification.BottomLeft
        return te
    except:
        return None

def interpolate_terrain_z(d_val, clean_pts):
    if not clean_pts: return 0.0
    if d_val <= clean_pts[0][0]: return clean_pts[0][1].Z
    if d_val >= clean_pts[-1][0]: return clean_pts[-1][1].Z
    for i in range(len(clean_pts) - 1):
        d0, p0 = clean_pts[i]
        d1, p1 = clean_pts[i+1]
        if d0 <= d_val <= d1:
            t = (d_val - d0) / (d1 - d0) if (d1 - d0) > 1e-6 else 0.0
            return p0.Z + t * (p1.Z - p0.Z)
    return clean_pts[-1][1].Z

def draw_nbr_level_marker(x, y, text_str, s=1.0):
    """Generates NBR 6492 standard level elevation marker symbol."""
    h_tri = 0.7 * s
    w_tri = 0.9 * s
    h_stem = 0.5 * s
    w_shelf = 2.4 * s
    txt_h = 0.65 * s

    v_bot = rg.Point3d(x, y, 0.0)
    v_top_mid = rg.Point3d(x, y + h_tri, 0.0)
    v_tl = rg.Point3d(x - w_tri / 2.0, y + h_tri, 0.0)
    v_tr = rg.Point3d(x + w_tri / 2.0, y + h_tri, 0.0)

    l1 = rg.LineCurve(v_bot, v_tl)
    l2 = rg.LineCurve(v_tl, v_top_mid)
    l_mid = rg.LineCurve(v_bot, v_top_mid)
    mesh_dir = make_filled_mesh(v_bot, v_tr, v_top_mid)
    lr1 = rg.LineCurve(v_bot, v_tr)
    lr2 = rg.LineCurve(v_tr, v_top_mid)

    v_stem = rg.Point3d(x, y + h_tri + h_stem, 0.0)
    v_shelf = rg.Point3d(x + w_shelf * 1.2, y + h_tri + h_stem, 0.0)
    l_stem = rg.LineCurve(v_top_mid, v_stem)
    l_shelf = rg.LineCurve(v_stem, v_shelf)

    p_txt = rg.Point3d(x + 0.15 * s, y + h_tri + h_stem + 0.1 * s, 0.0)
    te = make_text_entity(text_str, p_txt, txt_h)

    geoms = [l1, l2, l_mid, mesh_dir, lr1, lr2, l_stem, l_shelf]
    if te: geoms.append(te)
    return geoms, te

def run():
    doc = Rhino.RhinoDoc.ActiveDoc
    tol = doc.ModelAbsoluteTolerance if doc else 0.001

    def get_input(keys, default=None):
        g = globals()
        for k in keys:
            val = g.get(k)
            if val is not None:
                return val
        return default

    raw_terreno    = get_input(['Terrain', 'Terreno', 'x'])
    raw_linha      = get_input(['CutLine', 'SectionLine', 'LinhaCorte', 'y'])
    raw_ponto      = get_input(['Point', 'Origin', 'Ponto', 'Origem', 'Localizacao'])
    raw_retangulo  = get_input(['Building', 'House', 'Retangulo', 'Edificacao', 'Casa'])
    raw_cobertura  = get_input(['Roof', 'Canopy', 'Cobertura', 'Circulo', 'Telhado'])
    raw_plato      = get_input(['Pad', 'GradedPad', 'Plato', 'CirculoAmarelo', 'CirculoPlato', 'PlatoEntrada'])
    raw_aterro     = get_input(['Fill', 'Embankment', 'Aterro', 'Aterramento'])
    raw_descida    = get_input(['Ramp', 'Entrance', 'Descida', 'Entrada', 'Rampa'])
    raw_seletor    = get_input(['Selector', 'Mode', 'Seletor', 'Modo', 'ModoCotas', 'OpcaoCotas'], 1)
    raw_nivel_piso = get_input(['FloorLevel', 'FloorElevation', 'NivelPiso', 'CotaPiso'])
    raw_nivel_plat = get_input(['PadLevel', 'PadElevation', 'NivelPlato', 'CotaPlato'])
    raw_nivel_ater = get_input(['FillLevel', 'EmbankmentLevel', 'NivelAterro', 'CotaAterro'])
    raw_altura     = get_input(['Height', 'FloorHeight', 'Altura'], 3.0)
    raw_espessura  = get_input(['Thickness', 'SlabThickness', 'Espessura'], 0.20)
    raw_escala     = get_input(['Scale', 'Escala'], 1.0)

    modo_cotas = parse_seletor(raw_seletor)

    if raw_terreno is None or raw_linha is None:
        msg = "⚠️ Please connect 'Terrain' and 'CutLine'."
        return None, None, None, [], [], [], [msg]

    cut_crv = to_rhino_curve(raw_linha)
    if cut_crv is None:
        l_list = to_list(raw_linha)
        if l_list: cut_crv = to_rhino_curve(l_list[0])

    if cut_crv is None:
        return None, None, None, [], [], [], ["ERROR: Invalid CutLine / Section Line."]

    terrain_geoms = []
    for item in to_list(raw_terreno):
        g = to_rhino_geom(item)
        if g is not None: terrain_geoms.append(g)

    if not terrain_geoms:
        return None, None, None, [], [], [], ["ERROR: No valid terrain curve/mesh found."]

    p_start = cut_crv.PointAtStart
    p_end = cut_crv.PointAtEnd
    dx = p_end.X - p_start.X
    dy = p_end.Y - p_start.Y
    L_horiz = math.hypot(dx, dy)

    if L_horiz < 1e-4:
        return None, None, None, [], [], [], ["ERROR: Cut line has zero length."]

    ux = dx / L_horiz
    uy = dy / L_horiz
    cut_plane = rg.Plane(rg.Point3d(p_start.X, p_start.Y, 0), rg.Vector3d(ux, uy, 0), rg.Vector3d.ZAxis)

    # 1. Intersection with natural terrain contour lines
    pts_with_d = []
    for g in terrain_geoms:
        if isinstance(g, rg.Curve):
            evs = rg.Intersect.Intersection.CurvePlane(g, cut_plane, tol)
            if evs:
                for ev in evs:
                    pt = ev.PointA
                    d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                    if -tol <= d <= L_horiz + tol:
                        pts_with_d.append((d, pt))
        elif isinstance(g, rg.Mesh):
            polys = rg.Intersect.Intersection.MeshPlane(g, cut_plane)
            if polys:
                for poly in polys:
                    for pt in poly:
                        d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                        if -tol <= d <= L_horiz + tol:
                            pts_with_d.append((d, pt))

    if not pts_with_d:
        return None, None, None, [], [], [], ["⚠️ No intersection found between cut line and terrain."]

    pts_with_d.sort(key=lambda x: x[0])
    clean_pts = []
    for d, pt in pts_with_d:
        if not clean_pts:
            clean_pts.append((d, pt))
        else:
            if abs(d - clean_pts[-1][0]) > 0.05 or abs(pt.Z - clean_pts[-1][1].Z) > 0.02:
                clean_pts.append((d, pt))

    if len(clean_pts) < 2:
        return None, None, None, [], [], [], ["WARNING: Cut line intersects fewer than 2 contour curves."]

    # 2. Perfil 3D
    pts_3d = [pt for d, pt in clean_pts]
    out_3d = rg.PolylineCurve(pts_3d)

    # 3. Posição no Top View
    user_pt = to_rhino_point(raw_ponto)
    if user_pt is not None:
        orig_x = user_pt.X
        orig_y = user_pt.Y
    else:
        bbox_cut = cut_crv.GetBoundingBox(True)
        orig_x = bbox_cut.Min.X
        orig_y = bbox_cut.Min.Y - 30.0

    z_min = min(pt.Z for pt in pts_3d)
    z_max = max(pt.Z for pt in pts_3d)
    delta_z = z_max - z_min
    datum_z = math.floor(z_min) - 2.0

    total_ext = clean_pts[-1][0] - clean_pts[0][0]
    s = float(raw_escala) if raw_escala is not None and float(raw_escala) > 0 else 1.0

    pts_2d = []
    base_terreno_2d = []
    cotas_tn_geoms  = []

    # Linha base do Datum
    p_base_ini = rg.Point3d(orig_x + clean_pts[0][0], orig_y, 0.0)
    p_base_fim = rg.Point3d(orig_x + clean_pts[-1][0], orig_y, 0.0)
    linha_datum = rg.LineCurve(p_base_ini, p_base_fim)
    base_terreno_2d.append(linha_datum)

    # Curvas de nível e símbolos de cota NBR no terreno natural
    for d, pt in clean_pts:
        px = orig_x + d
        py_terreno = orig_y + (pt.Z - datum_z)
        p_corte = rg.Point3d(px, py_terreno, 0.0)
        pts_2d.append(p_corte)

        cota_str = "+{:.2f}".format(pt.Z).replace('.', ',') if pt.Z > 0 else "{:.2f}".format(pt.Z).replace('.', ',')
        m_geoms, te = draw_nbr_level_marker(px, py_terreno, cota_str, s)
        cotas_tn_geoms.extend(m_geoms)

    out_2d = rg.PolylineCurve(pts_2d)
    base_terreno_2d.append(out_2d)

    poly_solo_pts = [p_base_ini, p_base_fim] + list(reversed(pts_2d)) + [p_base_ini]
    base_terreno_2d.append(rg.Polyline(poly_solo_pts).ToPolylineCurve())

    # =========================================================================
    # 4. ELEMENTOS DO PROJETO (CASA, COBERTURA, PLATÔ E ATERRAMENTO)
    # =========================================================================
    geometria_projeto_fisica = []
    cotas_projeto_geoms      = []
    cut_xy = rg.Curve.ProjectToPlane(cut_crv, rg.Plane.WorldXY)

    rect_raw  = to_rhino_curve(raw_retangulo) or (to_rhino_curve(to_list(raw_retangulo)[0]) if to_list(raw_retangulo) else None)
    circ_raw  = to_rhino_curve(raw_cobertura) or (to_rhino_curve(to_list(raw_cobertura)[0]) if to_list(raw_cobertura) else None)
    
    crv_plato = to_rhino_curve(raw_plato) or to_rhino_curve(raw_aterro)
    if crv_plato is None:
        for val in [raw_plato, raw_aterro]:
            l = to_list(val)
            if l:
                c = to_rhino_curve(l[0])
                if c:
                    crv_plato = c
                    break

    h_casa = float(raw_altura) if raw_altura is not None and float(raw_altura) > 0 else 3.0
    esp_laje = float(raw_espessura) if raw_espessura is not None and float(raw_espessura) > 0 else 0.20

    # Determinar a Cota de Referência do Projeto (Z do Piso/Platô)
    z_ref = None
    if raw_nivel_piso is not None:
        z_ref = float(raw_nivel_piso)
    elif raw_nivel_plat is not None:
        z_ref = float(raw_nivel_plat)
    elif rect_raw is not None and abs(rect_raw.PointAtStart.Z) > 1.0:
        z_ref = rect_raw.PointAtStart.Z
    elif crv_plato is not None and abs(crv_plato.PointAtStart.Z) > 1.0:
        z_ref = crv_plato.PointAtStart.Z

    # A. INTERSECTION WITH BUILDING FOOTPRINT (RECTANGLE)
    d_casa_in = None
    d_casa_out = None
    info_edificacao = "Section outside building footprint."
    if rect_raw is not None and isinstance(rect_raw, rg.Curve):
        rect_xy = rg.Curve.ProjectToPlane(rect_raw, rg.Plane.WorldXY)
        cc_events = rg.Intersect.Intersection.CurveCurve(cut_xy, rect_xy, tol, tol)
        bldg_distances = []

        if cc_events:
            for ev in cc_events:
                dist_ev = (ev.PointA.X - p_start.X) * ux + (ev.PointA.Y - p_start.Y) * uy
                bldg_distances.append(dist_ev)

        if len(bldg_distances) >= 2:
            d_casa_in = min(bldg_distances)
            d_casa_out = max(bldg_distances)

            if z_ref is None:
                z_t_in = interpolate_terrain_z(d_casa_in, clean_pts)
                z_t_out = interpolate_terrain_z(d_casa_out, clean_pts)
                z_ref = (z_t_in + z_t_out) / 2.0

            z_piso = z_ref
            x_casa_1 = orig_x + d_casa_in
            x_casa_2 = orig_x + d_casa_out
            y_piso = orig_y + (z_piso - datum_z)
            y_teto = y_piso + h_casa

            z_t_1 = interpolate_terrain_z(d_casa_in, clean_pts)
            z_t_2 = interpolate_terrain_z(d_casa_out, clean_pts)
            y_terreno_1 = orig_y + (z_t_1 - datum_z)
            y_terreno_2 = orig_y + (z_t_2 - datum_z)

            # Paredes da casa
            pts_box_casa = [
                rg.Point3d(x_casa_1, y_piso, 0.0),
                rg.Point3d(x_casa_2, y_piso, 0.0),
                rg.Point3d(x_casa_2, y_teto, 0.0),
                rg.Point3d(x_casa_1, y_teto, 0.0),
                rg.Point3d(x_casa_1, y_piso, 0.0)
            ]
            crv_box_casa = rg.Polyline(pts_box_casa).ToPolylineCurve()
            geometria_projeto_fisica.append(crv_box_casa)

            # Piso
            linha_piso = rg.LineCurve(rg.Point3d(x_casa_1, y_piso, 0.0), rg.Point3d(x_casa_2, y_piso, 0.0))
            geometria_projeto_fisica.append(linha_piso)

            # Fundações sob a casa
            fund_esq = rg.LineCurve(rg.Point3d(x_casa_1, y_piso, 0.0), rg.Point3d(x_casa_1, y_terreno_1, 0.0))
            fund_dir = rg.LineCurve(rg.Point3d(x_casa_2, y_piso, 0.0), rg.Point3d(x_casa_2, y_terreno_2, 0.0))
            geometria_projeto_fisica.extend([fund_esq, fund_dir])

            # Cota NBR Piso
            x_mid_casa = (x_casa_1 + x_casa_2) / 2.0
            txt_piso = "FLOOR +{:.2f}".format(z_piso).replace('.', ',')
            m_piso, te_p = draw_nbr_level_marker(x_mid_casa, y_piso, txt_piso, s)
            cotas_projeto_geoms.extend(m_piso)

            info_edificacao = "Building: station={:.2f}m to {:.2f}m | Finished Floor: +{:.2f}m".format(d_casa_in, d_casa_out, z_piso)

    # B. INTERSECTION WITH ROOF / CANOPY
    d_roof_in = None
    d_roof_out = None
    info_cobertura = "Section outside roof/canopy."
    if circ_raw is not None and isinstance(circ_raw, rg.Curve):
        circ_xy = rg.Curve.ProjectToPlane(circ_raw, rg.Plane.WorldXY)
        circ_events = rg.Intersect.Intersection.CurveCurve(cut_xy, circ_xy, tol, tol)
        roof_distances = []

        if circ_events:
            for ev in circ_events:
                dist_ev = (ev.PointA.X - p_start.X) * ux + (ev.PointA.Y - p_start.Y) * uy
                roof_distances.append(dist_ev)

        if len(roof_distances) >= 2:
            d_roof_in = min(roof_distances)
            d_roof_out = max(roof_distances)

            z_base = z_ref if z_ref is not None else z_max
            z_cob_inf = z_base + h_casa
            z_cob_sup = z_cob_inf + esp_laje

            x_roof_1 = orig_x + d_roof_in
            x_roof_2 = orig_x + d_roof_out
            y_cob_inf = orig_y + (z_cob_inf - datum_z)
            y_cob_sup = orig_y + (z_cob_sup - datum_z)

            pts_laje_cob = [
                rg.Point3d(x_roof_1, y_cob_inf, 0.0),
                rg.Point3d(x_roof_2, y_cob_inf, 0.0),
                rg.Point3d(x_roof_2, y_cob_sup, 0.0),
                rg.Point3d(x_roof_1, y_cob_sup, 0.0),
                rg.Point3d(x_roof_1, y_cob_inf, 0.0)
            ]
            crv_laje_cob = rg.Polyline(pts_laje_cob).ToPolylineCurve()
            geometria_projeto_fisica.append(crv_laje_cob)

            # Cota NBR Cobertura
            x_pos_cob = x_roof_2 - 2.5 * s
            txt_cob = "ROOF +{:.2f}".format(z_cob_sup).replace('.', ',')
            m_cob, te_c = draw_nbr_level_marker(x_pos_cob, y_cob_sup, txt_cob, s)
            cotas_projeto_geoms.extend(m_cob)

            info_cobertura = "Roof/Canopy: station={:.2f}m to {:.2f}m | Elevation: +{:.2f}m".format(d_roof_in, d_roof_out, z_cob_sup)

    # =========================================================================
    # C. PROCESSAMENTO DO PLATÔ E ATERRO
    # =========================================================================
    info_plato = "No pad or embankment intercepted."

    # Detect intersection with Graded Pad (Circle / Boundary Curve)
    d_pl_1 = None
    d_pl_2 = None
    if crv_plato is not None and isinstance(crv_plato, rg.Curve):
        plato_xy = rg.Curve.ProjectToPlane(crv_plato, rg.Plane.WorldXY)
        pl_events = rg.Intersect.Intersection.CurveCurve(cut_xy, plato_xy, tol, tol)
        pl_dists = []
        if pl_events:
            for ev in pl_events:
                dist_ev = (ev.PointA.X - p_start.X) * ux + (ev.PointA.Y - p_start.Y) * uy
                pl_dists.append(dist_ev)
        if len(pl_dists) >= 2:
            d_pl_1 = min(pl_dists)
            d_pl_2 = max(pl_dists)

    # Cota Z definitiva do Platô
    if z_ref is None:
        if d_pl_1 is not None and d_pl_2 is not None:
            z_ref = (interpolate_terrain_z(d_pl_1, clean_pts) + interpolate_terrain_z(d_pl_2, clean_pts)) / 2.0
        else:
            z_ref = (z_min + z_max) / 2.0

    z_plato = z_ref
    y_plato = orig_y + (z_plato - datum_z)

    # -------------------------------------------------------------------------
    # CASO 1: A LINHA DE CORTE CRUZA A CASA (Corte Longitudinal)
    # -------------------------------------------------------------------------
    if d_casa_in is not None and d_casa_out is not None:
        if d_pl_1 is None: d_pl_1 = max(clean_pts[0][0], d_casa_in - 8.0)
        if d_pl_2 is None: d_pl_2 = min(clean_pts[-1][0], d_casa_out + 15.0)

        # 1. Platô à esquerda da casa
        if d_casa_in > d_pl_1 + 0.3:
            x_pesq_1 = orig_x + d_pl_1
            x_pesq_2 = orig_x + d_casa_in
            linha_plat_esq = rg.LineCurve(rg.Point3d(x_pesq_1, y_plato, 0.0), rg.Point3d(x_pesq_2, y_plato, 0.0))
            geometria_projeto_fisica.append(linha_plat_esq)

            z_tn_pesq = interpolate_terrain_z(d_pl_1, clean_pts)
            y_tn_pesq = orig_y + (z_tn_pesq - datum_z)
            muro_esq = rg.LineCurve(rg.Point3d(x_pesq_1, y_plato, 0.0), rg.Point3d(x_pesq_1, y_tn_pesq, 0.0))
            geometria_projeto_fisica.append(muro_esq)

            txt_pesq = "PLATÔ +{:.2f}".format(z_plato).replace('.', ',')
            m_pe, te_pe = draw_nbr_level_marker((x_pesq_1 + x_pesq_2) / 2.0, y_plato, txt_pesq, s)
            cotas_projeto_geoms.extend(m_pe)

        # 2. Platô à direita (sob o beiral da cobertura)
        d_ramp_start = d_roof_out if (d_roof_out is not None and d_roof_out > d_casa_out) else d_casa_out + 2.0
        d_ramp_start = min(d_ramp_start, d_pl_2 - 1.0)
        if d_ramp_start > d_casa_out + 0.1:
            x_pdir_1 = orig_x + d_casa_out
            x_pdir_2 = orig_x + d_ramp_start
            linha_plat_dir = rg.LineCurve(rg.Point3d(x_pdir_1, y_plato, 0.0), rg.Point3d(x_pdir_2, y_plato, 0.0))
            geometria_projeto_fisica.append(linha_plat_dir)

            m_pd, te_pd = draw_nbr_level_marker(x_pdir_2, y_plato, "PLATÔ +{:.2f}".format(z_plato).replace('.', ','), s)
            cotas_projeto_geoms.extend(m_pd)

        # 3. Rampa de aterro subindo até o terreno natural alto
        d_at_end = max(d_pl_2, d_ramp_start + 5.0)
        d_at_end = min(d_at_end, clean_pts[-1][0])
        if d_at_end > d_ramp_start + 0.5:
            z_at_fim = float(raw_nivel_ater) if raw_nivel_ater is not None else interpolate_terrain_z(d_at_end, clean_pts)
            x_at_1 = orig_x + d_ramp_start
            x_at_2 = orig_x + d_at_end
            y_at_1 = y_plato
            y_at_2 = orig_y + (z_at_fim - datum_z)

            linha_rampa = rg.LineCurve(rg.Point3d(x_at_1, y_at_1, 0.0), rg.Point3d(x_at_2, y_at_2, 0.0))
            geometria_projeto_fisica.append(linha_rampa)

            # Muro final
            y_tn_fim = orig_y + (interpolate_terrain_z(d_at_end, clean_pts) - datum_z)
            if abs(y_at_2 - y_tn_fim) > 0.05:
                muro_f = rg.LineCurve(rg.Point3d(x_at_2, y_at_2, 0.0), rg.Point3d(x_at_2, y_tn_fim, 0.0))
                geometria_projeto_fisica.append(muro_f)

            # Polígono de aterro
            pts_under = [rg.Point3d(x_at_1, orig_y + (interpolate_terrain_z(d_ramp_start, clean_pts) - datum_z), 0.0)]
            for d, pt in clean_pts:
                if d_ramp_start < d < d_at_end:
                    pts_under.append(rg.Point3d(orig_x + d, orig_y + (pt.Z - datum_z), 0.0))
            pts_under.append(rg.Point3d(x_at_2, y_tn_fim, 0.0))

            p_poly = [rg.Point3d(x_at_1, y_at_1, 0.0), rg.Point3d(x_at_2, y_at_2, 0.0)] + list(reversed(pts_under)) + [rg.Point3d(x_at_1, y_at_1, 0.0)]
            geometria_projeto_fisica.append(rg.Polyline(p_poly).ToPolylineCurve())

            # Cotas NBR intermediárias
            dz_r = z_at_fim - z_plato
            dx_r = d_at_end - d_ramp_start
            if abs(dz_r) > 0.3 and dx_r > 1.0:
                for z_c in range(int(math.ceil(min(z_plato, z_at_fim))), int(math.floor(max(z_plato, z_at_fim))) + 1):
                    t = (float(z_c) - z_plato) / dz_r
                    if 0.08 <= t <= 0.92:
                        xc = x_at_1 + t * dx_r
                        yc = y_at_1 + t * (y_at_2 - y_at_1)
                        m_c, te_c = draw_nbr_level_marker(xc, yc, "+{:.2f}".format(float(z_c)).replace('.', ','), s)
                        cotas_projeto_geoms.extend(m_c)

            m_top, te_top = draw_nbr_level_marker(x_at_2, y_at_2, "ATERRO +{:.2f}".format(z_at_fim).replace('.', ','), s)
            cotas_projeto_geoms.extend(m_top)

        info_plato = "Longitudinal Section: Pad +{:.2f}m with Building and Access Ramp".format(z_plato)

    # -------------------------------------------------------------------------
    # CASO 2: A LINHA DE CORTE NÃO CRUZA A CASA (Corte Transversal)
    # Platô contínuo, limpo e sem buracos!
    # -------------------------------------------------------------------------
    elif d_pl_1 is not None and d_pl_2 is not None and (d_pl_2 - d_pl_1) > 0.5:
        d_pl_1 = max(d_pl_1, clean_pts[0][0])
        d_pl_2 = min(d_pl_2, clean_pts[-1][0])

        x_p1 = orig_x + d_pl_1
        x_p2 = orig_x + d_pl_2

        # Linha horizontal contínua de todo o Platô
        linha_plato_cont = rg.LineCurve(rg.Point3d(x_p1, y_plato, 0.0), rg.Point3d(x_p2, y_plato, 0.0))
        geometria_projeto_fisica.append(linha_plato_cont)

        # Muro de contenção / talude na extremidade esquerda
        z_tn_1 = interpolate_terrain_z(d_pl_1, clean_pts)
        y_tn_1 = orig_y + (z_tn_1 - datum_z)
        muro_1 = rg.LineCurve(rg.Point3d(x_p1, y_plato, 0.0), rg.Point3d(x_p1, y_tn_1, 0.0))
        geometria_projeto_fisica.append(muro_1)

        # Muro de contenção / talude na extremidade direita
        z_tn_2 = interpolate_terrain_z(d_pl_2, clean_pts)
        y_tn_2 = orig_y + (z_tn_2 - datum_z)
        muro_2 = rg.LineCurve(rg.Point3d(x_p2, y_plato, 0.0), rg.Point3d(x_p2, y_tn_2, 0.0))
        geometria_projeto_fisica.append(muro_2)

        # Polígono de terraplanagem fechado do Platô (Corte/Aterro contínuo)
        pts_tn_under = [rg.Point3d(x_p1, y_tn_1, 0.0)]
        for d, pt in clean_pts:
            if d_pl_1 < d < d_pl_2:
                pts_tn_under.append(rg.Point3d(orig_x + d, orig_y + (pt.Z - datum_z), 0.0))
        pts_tn_under.append(rg.Point3d(x_p2, y_tn_2, 0.0))

        poly_pts = [rg.Point3d(x_p1, y_plato, 0.0), rg.Point3d(x_p2, y_plato, 0.0)] + list(reversed(pts_tn_under)) + [rg.Point3d(x_p1, y_plato, 0.0)]
        crv_poly = rg.Polyline(poly_pts).ToPolylineCurve()
        geometria_projeto_fisica.append(crv_poly)

        # Cota NBR no centro do Platô
        x_mid_plat = (x_p1 + x_p2) / 2.0
        txt_pl = "PLATÔ +{:.2f}".format(z_plato).replace('.', ',')
        m_pl, te_pl = draw_nbr_level_marker(x_mid_plat, y_plato, txt_pl, s)
        cotas_projeto_geoms.extend(m_pl)

        info_plato = "Cross Section: Continuous Graded Pad +{:.2f}m (Length: {:.2f}m)".format(z_plato, d_pl_2 - d_pl_1)

    # =========================================================================
    # 5. APLICAÇÃO DO SELETOR DE COTAS NO DESENHO COMPLETO
    # =========================================================================
    desenho_completo_2d = list(base_terreno_2d)

    if modo_cotas == 1:
        # Modo 1: Apenas as cotas do terreno projetado e o perfil natural
        desenho_completo_2d.extend(geometria_projeto_fisica)
        desenho_completo_2d.extend(cotas_projeto_geoms)
        desc_modo = "Mode 1: Proposed Project Elevations Only (+ Natural Ground Profile)"
    elif modo_cotas == 2:
        # Modo 2: Apenas as cotas do terreno natural
        desenho_completo_2d.extend(cotas_tn_geoms)
        # Mantém a geometria do projeto sem as cotas do projeto
        desenho_completo_2d.extend(geometria_projeto_fisica)
        desc_modo = "Mode 2: Natural Ground Elevations Only"
    else:
        # Mode 0: Complete (All dimensions of natural terrain and project)
        desenho_completo_2d.extend(cotas_tn_geoms)
        desenho_completo_2d.extend(geometria_projeto_fisica)
        desenho_completo_2d.extend(cotas_projeto_geoms)
        desc_modo = "Mode 0: All Elevations (Natural Ground + Proposed Project)"

    # 6. Relatório Técnico
    decliv_pct = (delta_z / total_ext * 100.0) if total_ext > 0 else 0.0
    decliv_deg = math.degrees(math.atan2(delta_z, total_ext)) if total_ext > 0 else 0.0
    cota_ini = pts_3d[0].Z
    cota_fim = pts_3d[-1].Z
    sentido = "Uphill" if cota_fim > cota_ini else "Downhill" if cota_fim < cota_ini else "Flat"

    relatorio = [
        "=== RELATÓRIO DO CORTE TOPOGRÁFICO ARQUITETÔNICO - NBR 6492 ===",
        "Section Insertion Point: X={:.2f}, Y={:.2f}".format(orig_x, orig_y),
        "Section Length        : {:.2f} m".format(total_ext),
        "Start / End Elevation : {:.2f} m / {:.2f} m ({})".format(cota_ini, cota_fim, sentido),
        "Min / Max Elev (Ground): {:.2f} m / {:.2f} m (ΔZ = {:.2f} m)".format(z_min, z_max, delta_z),
        "Average Slope         : {:.2f}% ({:.2f}°)".format(decliv_pct, decliv_deg),
        "----------------------------------------",
        "ACTIVE DIMENSION SELECTOR:",
        desc_modo,
        "----------------------------------------",
        "GRADED PAD / EMBANKMENT:",
        info_plato,
        "----------------------------------------",
        "BUILDING (RECTANGLE):",
        info_edificacao,
        "----------------------------------------",
        "ROOF / CANOPY (CIRCLE):",
        info_cobertura,
        "========================================"
    ]

    # Isolated geometries for specific Grasshopper outputs
    geometria_plato_output = list(geometria_projeto_fisica)
    geometria_casa_output = [g for g in geometria_projeto_fisica if g not in base_terreno_2d]

    return out_3d, out_2d, desenho_completo_2d, cotas_projeto_geoms, cotas_tn_geoms, relatorio

res_3d, res_2d, res_desenho, res_cotas_proj, res_cotas_tn, rel = run()

# OUTPUTS CONNECTED IN GRASSHOPPER:
a = res_3d           # 3D Section Profile curve on terrain (World Coordinates)
b = res_2d           # 2D Terrain profile curve
c = res_desenho      # FINAL COMPLETE 2D DRAWING (Filtered per Selector mode)
d = res_cotas_proj   # Proposed Project Elevations Only (Pad, Ramp, Floor, Roof)
e = res_cotas_tn     # Natural Ground Elevations Only
f = rel              # Technical Calculation & Descriptive Report (Panel)
