# -*- coding: utf-8 -*-
"""
===============================================================================
CÁLCULO DE TERRAPLENAGEM E VOLUMES DE CORTE E ATERRO (NBR 6492 & AGPTEA)
===============================================================================
Algoritmo paramétrico para Grasshopper (Rhinoceros 8 / GhPython).
Gera cortes topográficos com cálculo analítico de movimentação de terra,
áreas de corte e aterro pelo Método das Seções Transversais / Trapézios,
identificação de Pontos de Passagem (P.P.), cubação volumétrica com empolamento
e representação gráfica com polígonos coloridos e simbologia técnica NBR 6492.

Metodologia baseada em:
- "TOPOGRAFIA: CÁLCULO DE VOLUMES – NOTAS DE AULA"
  Prof. Luís Augusto Koenig Veiga (UFPR / AGPTEA)
  Cap. 3.2 (Método das Seções Transversais) e Cap. 3.4 (Terraplenagem para Plataformas)
- NBR 6492: Representação de Projetos de Arquitetura (Simbologia de Níveis em Corte)

ENTRADAS (INPUTS):
  Terreno      [List, Curve/Mesh] : Curvas de nível 3D ou Malha topográfica.
  LinhaCorte   [Item, Curve]      : Linha do corte desenhada no Rhino.
  CurvaProjeto [Item, Curve]      : Linha/Curva de terraplenagem (pode ser desenhada
                                    em 2D diretamente sobre o corte ou em 3D no terreno).
  Ponto        [Item, Point3d]    : Ponto de referência para inserção no Top View.
  Largura      [Item, float]      : Faixa de influência / largura da seção em metros (padrão: 1.0 m).
  Empolamento  [Item, float]      : Fator de empolamento do solo para transporte (padrão: 1.20 = 20%).
  Seletor      [Item, int]        : Modo de exibição:
                                    0 = Completo (TN + Greide + Áreas + Todas as Cotas)
                                    1 = Terraplenagem / Projetado [Padrão]
                                    2 = Apenas Terreno Natural
  Escala       [Item, float]      : Fator de escala dos símbolos e textos NBR (padrão: 1.0).
  NivelProjeto [Item, float]      : Cota Z horizontal caso CurvaProjeto não seja informada.

SAÍDAS (OUTPUTS):
  a : Linha 3D do corte sobre o relevo natural (Coordenadas de Mundo / UTM).
  b : Polilinha 2D do perfil do terreno natural na vista Top.
  c : DESENHO COMPLETO (Perfil TN + Greide Projetado + Malhas Coloridas de Corte e Aterro + Cotas NBR).
  d : Polígonos de CORTE (Closed Curves para cálculo de área, hachura e layers).
  e : Polígonos de ATERRO (Closed Curves para cálculo de área, hachura e layers).
  f : Memorial Técnico de Terraplenagem AGPTEA (Texto formatado para Panel).
===============================================================================
"""

import math
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import System.Drawing

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
    0: Todas as cotas e geometrias (Completo)
    1: Foco em Terraplenagem (Perfil TN + Greide + Corte/Aterro + Cotas do Projeto)
    2: Apenas Terreno Natural
    """
    if val is None:
        return 1
    if isinstance(val, bool):
        return 1 if val else 2
    try:
        ival = int(val)
        if ival in [0, 1, 2]:
            return ival
    except:
        pass
    s = str(val).strip().lower()
    if "proj" in s or "terra" in s or "corte" in s:
        return 1
    elif "nat" in s or "tn" in s:
        return 2
    elif "tod" in s or "all" in s or "tudo" in s:
        return 0
    return 1

def make_filled_mesh_tri(v0, v1, v2, color=None):
    m = rg.Mesh()
    m.Vertices.Add(v0)
    m.Vertices.Add(v1)
    m.Vertices.Add(v2)
    m.Faces.AddFace(0, 1, 2)
    if color:
        m.VertexColors.Add(color)
        m.VertexColors.Add(color)
        m.VertexColors.Add(color)
    m.Normals.ComputeNormals()
    return m

def create_colored_mesh(quads_and_tris, color):
    """Cria uma malha contínua colorida para visualização de corte/aterro."""
    if not quads_and_tris: return None
    m = rg.Mesh()
    for pts in quads_and_tris:
        if len(pts) == 3:
            i0 = m.Vertices.Add(pts[0])
            i1 = m.Vertices.Add(pts[1])
            i2 = m.Vertices.Add(pts[2])
            m.Faces.AddFace(i0, i1, i2)
            if color:
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
        elif len(pts) == 4:
            i0 = m.Vertices.Add(pts[0])
            i1 = m.Vertices.Add(pts[1])
            i2 = m.Vertices.Add(pts[2])
            i3 = m.Vertices.Add(pts[3])
            m.Faces.AddFace(i0, i1, i2, i3)
            if color:
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
    m.Normals.ComputeNormals()
    return m

def make_text_entity(text_str, pt, height, justification=None):
    try:
        plane = rg.Plane(pt, rg.Vector3d.ZAxis)
        te = rg.TextEntity()
        te.PlainText = text_str
        te.Plane = plane
        te.TextHeight = height
        if justification is not None:
            te.Justification = justification
        else:
            te.Justification = rg.TextJustification.BottomLeft
        return te
    except:
        return None

def make_callout_card(center_x, center_y, title_text, sub_text, s=1.0):
    """Cria uma caixa retangular técnica com textos centralizados de volume e área."""
    txt_h1 = 0.65 * s
    txt_h2 = 0.45 * s
    gap_y  = 0.35 * s
    pad_x  = 0.85 * s
    pad_y  = 0.45 * s

    max_chars = max(len(title_text), len(sub_text))
    w_box = max(max_chars * 0.44 * s + pad_x * 2.0, 7.5 * s)
    h_box = txt_h1 + txt_h2 + gap_y + pad_y * 2.0

    p0 = rg.Point3d(center_x - w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p1 = rg.Point3d(center_x + w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p2 = rg.Point3d(center_x + w_box / 2.0, center_y + h_box / 2.0, 0.0)
    p3 = rg.Point3d(center_x - w_box / 2.0, center_y + h_box / 2.0, 0.0)
    box_crv = rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve()

    pt_t1 = rg.Point3d(center_x, center_y + 0.35 * s, 0.0)
    te1 = make_text_entity(title_text, pt_t1, txt_h1, rg.TextJustification.MiddleCenter)

    pt_t2 = rg.Point3d(center_x, center_y - 0.45 * s, 0.0)
    te2 = make_text_entity(sub_text, pt_t2, txt_h2, rg.TextJustification.MiddleCenter)

    geoms = [box_crv]
    if te1: geoms.append(te1)
    if te2: geoms.append(te2)
    return geoms, (w_box, h_box)

def interpolate_terrain_z(d_val, clean_pts=None):
    if clean_pts is None:
        clean_pts = globals().get('_cached_clean_pts', None)
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
    """Gera o símbolo de cota de nível padrão NBR 6492."""
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
    mesh_dir = make_filled_mesh_tri(v_bot, v_tr, v_top_mid)
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

    # 1. Obtenção dos parâmetros de entrada
    raw_terreno      = globals().get('Terreno', globals().get('x', None))
    raw_linha        = globals().get('LinhaCorte', globals().get('y', None))
    raw_projeto      = globals().get('CurvaProjeto', globals().get('Greide', globals().get('Projeto', globals().get('LinhaProjeto', globals().get('CurvaCorte', None)))))
    raw_ponto        = globals().get('Ponto', globals().get('Point', globals().get('Origem', globals().get('Localizacao', None))))
    
    raw_largura      = globals().get('Largura', globals().get('Faixa', globals().get('FaixaInfluencia', globals().get('LarguraFaixa', 1.0))))
    raw_empolamento  = globals().get('Empolamento', globals().get('FatorK', globals().get('K', 1.20)))
    raw_seletor      = globals().get('Seletor', globals().get('Modo', globals().get('ModoCotas', 1)))
    raw_escala       = globals().get('Escala', 1.0)
    raw_nivel_proj   = globals().get('NivelProjeto', globals().get('CotaProjeto', globals().get('CotaGreide', None)))

    modo_cotas = parse_seletor(raw_seletor)
    largura_secao = float(raw_largura) if raw_largura is not None and float(raw_largura) > 0 else 1.0
    fator_k = float(raw_empolamento) if raw_empolamento is not None and float(raw_empolamento) > 0 else 1.20
    s = float(raw_escala) if raw_escala is not None and float(raw_escala) > 0 else 1.0

    if raw_terreno is None or raw_linha is None:
        msg = "⚠️ Conecte 'Terreno' e 'LinhaCorte' para gerar o perfil topográfico."
        return None, None, None, [], [], [msg]

    cut_crv = to_rhino_curve(raw_linha)
    if cut_crv is None:
        l_list = to_list(raw_linha)
        if l_list: cut_crv = to_rhino_curve(l_list[0])

    if cut_crv is None:
        return None, None, None, [], [], ["ERRO: 'LinhaCorte' inválida ou não pôde ser convertida."]

    terrain_geoms = []
    for item in to_list(raw_terreno):
        g = to_rhino_geom(item)
        if g is not None: terrain_geoms.append(g)

    if not terrain_geoms:
        return None, None, None, [], [], ["ERRO: Nenhuma curva ou malha válida fornecida em 'Terreno'."]

    # Geometria e orientação da linha de corte
    p_start = cut_crv.PointAtStart
    p_end = cut_crv.PointAtEnd
    dx = p_end.X - p_start.X
    dy = p_end.Y - p_start.Y
    L_horiz = math.hypot(dx, dy)

    if L_horiz < 1e-4:
        return None, None, None, [], [], ["ERRO: 'LinhaCorte' com comprimento nulo."]

    ux = dx / L_horiz
    uy = dy / L_horiz
    cut_plane = rg.Plane(rg.Point3d(p_start.X, p_start.Y, 0), rg.Vector3d(ux, uy, 0), rg.Vector3d.ZAxis)

    # 2. Interseção com as curvas de nível do terreno natural (Perfil 3D)
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
        return None, None, None, [], [], ["⚠️ Nenhuma interseção encontrada entre 'LinhaCorte' e 'Terreno'."]

    pts_with_d.sort(key=lambda x: x[0])
    clean_pts = []
    for d, pt in pts_with_d:
        if not clean_pts:
            clean_pts.append((d, pt))
        else:
            if abs(d - clean_pts[-1][0]) > 0.05 or abs(pt.Z - clean_pts[-1][1].Z) > 0.02:
                clean_pts.append((d, pt))

    if len(clean_pts) < 2:
        return None, None, None, [], [], ["AVISO: A linha de corte cruza menos de 2 pontos de relevo."]

    globals()['_cached_clean_pts'] = clean_pts

    # Perfil 3D
    pts_3d = [pt for d, pt in clean_pts]
    out_3d = rg.PolylineCurve(pts_3d)

    # Ponto de Inserção da Seção 2D na vista Top
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

    # Construção do Perfil 2D do Terreno Natural
    pts_2d = []
    base_terreno_2d = []
    cotas_tn_geoms  = []

    p_base_ini = rg.Point3d(orig_x + clean_pts[0][0], orig_y, 0.0)
    p_base_fim = rg.Point3d(orig_x + clean_pts[-1][0], orig_y, 0.0)
    linha_datum = rg.LineCurve(p_base_ini, p_base_fim)
    base_terreno_2d.append(linha_datum)

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

    # Polígono base sob o terreno natural
    poly_solo_pts = [p_base_ini, p_base_fim] + list(reversed(pts_2d)) + [p_base_ini]
    base_terreno_2d.append(rg.Polyline(poly_solo_pts).ToPolylineCurve())

    # =========================================================================
    # 3. INTERPRETAÇÃO DA CURVA DO PROJETO / GREIDE DE TERRAPLENAGEM
    # =========================================================================
    crv_proj = to_rhino_curve(raw_projeto)
    if crv_proj is None and to_list(raw_projeto):
        crv_proj = to_rhino_curve(to_list(raw_projeto)[0])

    proj_samples = [] # lista de tuplas (d, Z_proj)
    tipo_greide = "Automático (Compensação)"

    if crv_proj is not None:
        bbox_p = crv_proj.GetBoundingBox(True)
        c_proj = bbox_p.Center
        dist_to_section = math.hypot(c_proj.X - orig_x, c_proj.Y - orig_y)
        dist_to_terrain = math.hypot(c_proj.X - p_start.X, c_proj.Y - p_start.Y)
        is_flat_z = (bbox_p.Max.Z - bbox_p.Min.Z < 0.1) and (abs(c_proj.Z) < 1.0)

        # Detecta se foi desenhada diretamente em 2D na vista Top sobre o corte
        is_2d_section = (dist_to_section < dist_to_terrain or is_flat_z) and (dist_to_section < 3.0 * (L_horiz + 100.0))

        if is_2d_section:
            tipo_greide = "Curva 2D no Corte"
            succ, poly = crv_proj.TryGetPolyline()
            if succ and poly:
                for pt in poly:
                    d = pt.X - orig_x
                    z = (pt.Y - orig_y) + datum_z
                    proj_samples.append((d, z))
            else:
                t_div = crv_proj.DivideByCount(80, True)
                if t_div:
                    for t in t_div:
                        pt = crv_proj.PointAt(t)
                        d = pt.X - orig_x
                        z = (pt.Y - orig_y) + datum_z
                        proj_samples.append((d, z))
                else:
                    ps, pe = crv_proj.PointAtStart, crv_proj.PointAtEnd
                    proj_samples = [
                        (ps.X - orig_x, (ps.Y - orig_y) + datum_z),
                        (pe.X - orig_x, (pe.Y - orig_y) + datum_z)
                    ]
        else:
            # Curva 3D sobre o relevo
            tipo_greide = "Curva 3D no Terreno"
            succ, poly = crv_proj.TryGetPolyline()
            pts_3d_p = list(poly) if (succ and poly) else [crv_proj.PointAt(t) for t in (crv_proj.DivideByCount(80, True) or [])]
            if not pts_3d_p: pts_3d_p = [crv_proj.PointAtStart, crv_proj.PointAtEnd]
            for pt in pts_3d_p:
                d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                z = pt.Z
                proj_samples.append((d, z))

    # Fallback se CurvaProjeto não foi fornecida
    if not proj_samples:
        if raw_nivel_proj is not None:
            z_fixo = float(raw_nivel_proj)
            tipo_greide = "Cota Fixa Horizontal (+{:.2f}m)".format(z_fixo)
        else:
            # Hipótese 01 AGPTEA (pág. 40-41): Plano de equilíbrio onde Corte ≈ Aterro
            # Média ponderada pela extensão do terreno
            area_tn_acc = 0.0
            for i in range(len(clean_pts) - 1):
                da, pa = clean_pts[i]
                db, pb = clean_pts[i+1]
                area_tn_acc += ((pa.Z + pb.Z) / 2.0) * (db - da)
            z_fixo = (area_tn_acc / total_ext) if total_ext > 0 else z_min
            tipo_greide = "Compensação Automática AGPTEA (+{:.2f}m)".format(z_fixo)

        d_ini = clean_pts[0][0]
        d_fim = clean_pts[-1][0]
        proj_samples = [(d_ini, z_fixo), (d_fim, z_fixo)]

    # Ordena os pontos do projeto por d
    proj_samples.sort(key=lambda x: x[0])

    # Se for uma reta simples de 2 pontos, extrapola até os limites do corte
    d_min_corte = clean_pts[0][0]
    d_max_corte = clean_pts[-1][0]
    if len(proj_samples) == 2:
        d0, z0 = proj_samples[0]
        d1, z1 = proj_samples[1]
        if abs(d1 - d0) > 1e-4:
            m_slope = (z1 - z0) / (d1 - d0)
            proj_samples = [
                (d_min_corte, z0 + m_slope * (d_min_corte - d0)),
                (d_max_corte, z0 + m_slope * (d_max_corte - d0))
            ]

    def interpolate_proj_z(d_val):
        if not proj_samples: return z_min
        if d_val <= proj_samples[0][0]:
            if len(proj_samples) >= 2:
                d0, z0 = proj_samples[0]
                d1, z1 = proj_samples[1]
                slope = (z1 - z0) / (d1 - d0) if abs(d1 - d0) > 1e-6 else 0.0
                return z0 + slope * (d_val - d0)
            return proj_samples[0][1]
        if d_val >= proj_samples[-1][0]:
            if len(proj_samples) >= 2:
                d0, z0 = proj_samples[-2]
                d1, z1 = proj_samples[-1]
                slope = (z1 - z0) / (d1 - d0) if abs(d1 - d0) > 1e-6 else 0.0
                return z1 + slope * (d_val - d1)
            return proj_samples[-1][1]
        for i in range(len(proj_samples) - 1):
            d0, z0 = proj_samples[i]
            d1, z1 = proj_samples[i+1]
            if d0 <= d_val <= d1:
                t = (d_val - d0) / (d1 - d0) if (d1 - d0) > 1e-6 else 0.0
                return z0 + t * (z1 - z0)
        return proj_samples[-1][1]

    # =========================================================================
    # 4. DISCRETIZAÇÃO, PONTOS DE PASSAGEM E CÁLCULO DAS ÁREAS (AGPTEA)
    # =========================================================================
    # Coleta todas as estacas / pontos notáveis
    estacas_set = set()
    for d, _ in clean_pts: estacas_set.add(round(d, 4))
    for d, _ in proj_samples:
        if d_min_corte <= d <= d_max_corte: estacas_set.add(round(d, 4))

    # Adiciona amostragem regular fina para precisão
    d_step = 0.5
    cur_d = d_min_corte
    while cur_d <= d_max_corte:
        estacas_set.add(round(cur_d, 4))
        cur_d += d_step
    estacas_set.add(round(d_max_corte, 4))

    estacas_ordenadas = sorted(list(estacas_set))

    # Busca analítica rigorosa dos Pontos de Passagem (P.P. onde h = 0)
    pontos_passagem = []
    for i in range(len(estacas_ordenadas) - 1):
        da = estacas_ordenadas[i]
        db = estacas_ordenadas[i+1]
        ha = interpolate_terrain_z(da, clean_pts) - interpolate_proj_z(da)
        hb = interpolate_terrain_z(db, clean_pts) - interpolate_proj_z(db)

        if abs(ha) < 1e-4:
            za = interpolate_proj_z(da)
            if not any(abs(da - p[0]) < 0.05 for p in pontos_passagem):
                pontos_passagem.append((da, za))
        elif ha * hb < -1e-6:
            # Fórmula da Interpolação Linear / Ponto de Passagem (AGPTEA pág. 41)
            t = abs(ha) / (abs(ha) + abs(hb))
            dp = da + t * (db - da)
            zp = interpolate_proj_z(dp)
            if not any(abs(dp - p[0]) < 0.05 for p in pontos_passagem):
                pontos_passagem.append((dp, zp))
                estacas_set.add(round(dp, 4))

    estacas_finais = sorted(list(estacas_set))

    # Agrupamento em Regiões Contínuas de Corte e Aterro
    regioes = [] # [(tipo, [d0, d1, d2...])]
    tipo_atual = None
    d_acumulados = []

    for i in range(len(estacas_finais) - 1):
        da = estacas_finais[i]
        db = estacas_finais[i+1]
        dx = db - da
        if dx < 1e-4: continue

        d_mid = (da + db) / 2.0
        h_mid = interpolate_terrain_z(d_mid, clean_pts) - interpolate_proj_z(d_mid)
        tipo_seg = "CORTE" if h_mid > 1e-4 else ("ATERRO" if h_mid < -1e-4 else "NULO")
        if tipo_seg == "NULO": continue

        if tipo_atual is None:
            tipo_atual = tipo_seg
            d_acumulados = [da, db]
        elif tipo_atual == tipo_seg:
            d_acumulados.append(db)
        else:
            regioes.append((tipo_atual, d_acumulados))
            tipo_atual = tipo_seg
            d_acumulados = [da, db]

    if tipo_atual and d_acumulados:
        regioes.append((tipo_atual, d_acumulados))

    # Construção dos Polígonos Fechados e Malhas Coloridas
    poligonos_corte_crvs  = []
    poligonos_aterro_crvs = []
    quads_corte_mesh      = []
    quads_aterro_mesh     = []

    area_total_corte  = 0.0
    area_total_aterro = 0.0
    max_h_corte  = 0.0
    d_max_corte  = d_min_corte
    max_h_aterro = 0.0
    d_max_aterro = d_min_corte

    for r_type, d_list in regioes:
        # 1. Quads elementares para malha colorida e cálculo de área
        for j in range(len(d_list) - 1):
            d1 = d_list[j]
            d2 = d_list[j+1]
            dx = d2 - d1

            z_tn1 = interpolate_terrain_z(d1, clean_pts)
            z_tn2 = interpolate_terrain_z(d2, clean_pts)
            z_pr1 = interpolate_proj_z(d1)
            z_pr2 = interpolate_proj_z(d2)

            h1 = abs(z_tn1 - z_pr1)
            h2 = abs(z_tn2 - z_pr2)
            # Método dos Trapézios das Notas de Aula da AGPTEA (pág. 30, 42-44)
            a_elem = ((h1 + h2) / 2.0) * dx

            p_tn1 = rg.Point3d(orig_x + d1, orig_y + (z_tn1 - datum_z), 0.0)
            p_tn2 = rg.Point3d(orig_x + d2, orig_y + (z_tn2 - datum_z), 0.0)
            p_pr1 = rg.Point3d(orig_x + d1, orig_y + (z_pr1 - datum_z), 0.0)
            p_pr2 = rg.Point3d(orig_x + d2, orig_y + (z_pr2 - datum_z), 0.0)

            if r_type == "CORTE":
                area_total_corte += a_elem
                quads_corte_mesh.append([p_tn1, p_tn2, p_pr2, p_pr1])
                if h1 > max_h_corte: max_h_corte, d_max_corte = h1, d1
                if h2 > max_h_corte: max_h_corte, d_max_corte = h2, d2
            else:
                area_total_aterro += a_elem
                quads_aterro_mesh.append([p_pr1, p_pr2, p_tn2, p_tn1])
                if h1 > max_h_aterro: max_h_aterro, d_max_aterro = h1, d1
                if h2 > max_h_aterro: max_h_aterro, d_max_aterro = h2, d2

        # 2. Polígono fechado do contorno da região
        pts_poly = []
        if r_type == "CORTE":
            for d in d_list:
                z = interpolate_terrain_z(d, clean_pts)
                pts_poly.append(rg.Point3d(orig_x + d, orig_y + (z - datum_z), 0.0))
            for d in reversed(d_list):
                z = interpolate_proj_z(d)
                pts_poly.append(rg.Point3d(orig_x + d, orig_y + (z - datum_z), 0.0))
            pts_poly.append(pts_poly[0])
            crv_fechada = rg.Polyline(pts_poly).ToPolylineCurve()
            poligonos_corte_crvs.append(crv_fechada)
        else:
            for d in d_list:
                z = interpolate_proj_z(d)
                pts_poly.append(rg.Point3d(orig_x + d, orig_y + (z - datum_z), 0.0))
            for d in reversed(d_list):
                z = interpolate_terrain_z(d, clean_pts)
                pts_poly.append(rg.Point3d(orig_x + d, orig_y + (z - datum_z), 0.0))
            pts_poly.append(pts_poly[0])
            crv_fechada = rg.Polyline(pts_poly).ToPolylineCurve()
            poligonos_aterro_crvs.append(crv_fechada)

    # Malhas Coloridas em Laranja (Corte) e Verde (Aterro)
    cor_corte  = System.Drawing.Color.FromArgb(245, 130, 32)
    cor_aterro = System.Drawing.Color.FromArgb(46, 204, 113)

    mesh_corte  = create_colored_mesh(quads_corte_mesh, cor_corte)
    mesh_aterro = create_colored_mesh(quads_aterro_mesh, cor_aterro)

    # Linha 2D do Greide de Terraplenagem
    pts_greide_2d = []
    for d in estacas_finais:
        z = interpolate_proj_z(d)
        pts_greide_2d.append(rg.Point3d(orig_x + d, orig_y + (z - datum_z), 0.0))
    crv_greide_2d = rg.Polyline(pts_greide_2d).ToPolylineCurve()

    # Cotas e Símbolos NBR do Projeto / Greide
    cotas_projeto_geoms = []

    # Cota início e fim do greide
    d_g_ini = clean_pts[0][0]
    d_g_fim = clean_pts[-1][0]
    z_g_ini = interpolate_proj_z(d_g_ini)
    z_g_fim = interpolate_proj_z(d_g_fim)

    m_ini, _ = draw_nbr_level_marker(orig_x + d_g_ini, orig_y + (z_g_ini - datum_z), "GREIDE INI +{:.2f}".format(z_g_ini).replace('.', ','), s)
    m_fim, _ = draw_nbr_level_marker(orig_x + d_g_fim, orig_y + (z_g_fim - datum_z), "GREIDE FIM +{:.2f}".format(z_g_fim).replace('.', ','), s)
    cotas_projeto_geoms.extend(m_ini)
    cotas_projeto_geoms.extend(m_fim)

    # Marcadores dos Pontos de Passagem (P.P.)
    for dp, zp in pontos_passagem:
        m_pp, _ = draw_nbr_level_marker(orig_x + dp, orig_y + (zp - datum_z), "P.P. +{:.2f}".format(zp).replace('.', ','), s)
        cotas_projeto_geoms.extend(m_pp)

    # Textos indicativos das alturas máximas
    if max_h_corte > 0.05:
        p_cmax = rg.Point3d(orig_x + d_max_corte, orig_y + (interpolate_terrain_z(d_max_corte, clean_pts) - datum_z) + 0.3 * s, 0.0)
        t_cmax = make_text_entity("Corte Máx: {:.2f}m".format(max_h_corte), p_cmax, 0.55 * s)
        if t_cmax: cotas_projeto_geoms.append(t_cmax)

    if max_h_aterro > 0.05:
        p_amax = rg.Point3d(orig_x + d_max_aterro, orig_y + (interpolate_proj_z(d_max_aterro) - datum_z) + 0.3 * s, 0.0)
        t_amax = make_text_entity("Aterro Máx: {:.2f}m".format(max_h_aterro), p_amax, 0.55 * s)
        if t_amax: cotas_projeto_geoms.append(t_amax)

    # Cubação volumétrica para apresentação gráfica
    vol_corte_geo   = area_total_corte * largura_secao
    vol_aterro_geo  = area_total_aterro * largura_secao
    vol_corte_solto = vol_corte_geo * fator_k
    saldo_vol       = vol_corte_geo - vol_aterro_geo

    # -------------------------------------------------------------------------
    # CAIXAS DE VOLUME RETIRADO E REALOCADO (CONFORME IMAGEM DE REFERÊNCIA)
    # -------------------------------------------------------------------------
    # 1. CAIXA SUPERIOR ESQUERDA: Quantidade retirada (Corte / Escavação)
    d_corte_all = [d for r_type, d_list in regioes if r_type == "CORTE" for d in d_list]
    if area_total_corte > 0.01 and d_corte_all:
        d_c_min = min(d_corte_all)
        d_c_max = max(d_corte_all)
        d_c_mid = (d_c_min + d_c_max) / 2.0
        z_c_top = max(interpolate_terrain_z(d, clean_pts) for d in d_corte_all)
        y_c_top = orig_y + (z_c_top - datum_z)

        txt_vol_ret  = "RETIRADO: {:.2f} m³".format(vol_corte_geo).replace('.', ',')
        txt_area_ret = "Área: {:.2f} m²".format(area_total_corte).replace('.', ',')
        if abs(largura_secao - 1.0) > 0.01:
            txt_area_ret += " | L={:.1f}m".format(largura_secao).replace('.', ',')

        w_est_c = max(len(txt_vol_ret), len(txt_area_ret)) * 0.44 * s + 1.7 * s
        x_box_c = orig_x + d_c_mid
        x_box_c = max(orig_x + w_est_c / 2.0 + 0.5 * s, x_box_c)
        y_box_c = y_c_top + 2.5 * s + 1.2 * s

        geoms_box_c, (w_c, h_c) = make_callout_card(x_box_c, y_box_c, txt_vol_ret, txt_area_ret, s)
        cotas_projeto_geoms.extend(geoms_box_c)

        # Linha guia conectando a caixa ao relevo
        p_box_bot = rg.Point3d(x_box_c, y_box_c - h_c / 2.0, 0.0)
        p_c_crest = rg.Point3d(x_box_c, orig_y + (interpolate_terrain_z(d_c_mid, clean_pts) - datum_z), 0.0)
        linha_guia_c = rg.LineCurve(p_box_bot, p_c_crest)
        cotas_projeto_geoms.append(linha_guia_c)

    # 2. CAIXA INFERIOR DIREITA: Quantidade realocada (Aterro / Preenchimento)
    d_aterro_all = [d for r_type, d_list in regioes if r_type == "ATERRO" for d in d_list]
    if area_total_aterro > 0.01 and d_aterro_all:
        d_a_min = min(d_aterro_all)
        d_a_max = max(d_aterro_all)
        d_a_mid = (d_a_min + d_a_max) / 2.0

        txt_vol_rea  = "REALOCADO: {:.2f} m³".format(vol_aterro_geo).replace('.', ',')
        txt_area_rea = "Área: {:.2f} m²".format(area_total_aterro).replace('.', ',')
        if abs(largura_secao - 1.0) > 0.01:
            txt_area_rea += " | L={:.1f}m".format(largura_secao).replace('.', ',')

        w_est_a = max(len(txt_vol_rea), len(txt_area_rea)) * 0.44 * s + 1.7 * s
        x_box_a = orig_x + d_a_mid
        x_box_a = min(orig_x + total_ext - w_est_a / 2.0 - 0.5 * s, x_box_a)
        y_box_a = orig_y - 2.5 * s - 1.2 * s

        geoms_box_a, (w_a, h_a) = make_callout_card(x_box_a, y_box_a, txt_vol_rea, txt_area_rea, s)
        cotas_projeto_geoms.extend(geoms_box_a)

        # Linha guia conectando a base do datum à caixa
        p_box_top = rg.Point3d(x_box_a, y_box_a + h_a / 2.0, 0.0)
        p_datum_conn = rg.Point3d(x_box_a, orig_y, 0.0)
        linha_guia_a = rg.LineCurve(p_box_top, p_datum_conn)
        cotas_projeto_geoms.append(linha_guia_a)

    # =========================================================================
    # 5. MONTAGEM DO DESENHO COMPLETO DE ACORDO COM O SELETOR
    # =========================================================================
    desenho_completo_2d = list(base_terreno_2d)
    desenho_completo_2d.append(crv_greide_2d)
    if mesh_corte:  desenho_completo_2d.append(mesh_corte)
    if mesh_aterro: desenho_completo_2d.append(mesh_aterro)

    if modo_cotas == 1:
        # Modo 1: Apenas Terraplenagem e Cotas de Projeto (Desenho Limpo)
        desenho_completo_2d.extend(cotas_projeto_geoms)
        desc_modo = "Modo 1: Apenas Cotas do Greide e Terraplenagem (Perfil Natural Limpo)"
    elif modo_cotas == 2:
        # Modo 2: Apenas Cotas do Terreno Natural
        desenho_completo_2d.extend(cotas_tn_geoms)
        desc_modo = "Modo 2: Apenas Cotas do Terreno Natural"
    else:
        # Modo 0: Completo (Todas as cotas simultâneas)
        desenho_completo_2d.extend(cotas_tn_geoms)
        desenho_completo_2d.extend(cotas_projeto_geoms)
        desc_modo = "Modo 0: Completo (Terreno Natural + Greide + Terraplenagem)"

    # =========================================================================
    # 6. CUBAÇÃO VOLUMÉTRICA E MEMORIAL TÉCNICO (AGPTEA)
    # =========================================================================
    vol_corte_geo  = area_total_corte * largura_secao
    vol_aterro_geo = area_total_aterro * largura_secao
    vol_corte_solto = vol_corte_geo * fator_k
    saldo_vol = vol_corte_geo - vol_aterro_geo

    # Diagnóstico de compensação de massas
    if abs(saldo_vol) < 0.1:
        diagnostico = "COMPENSAÇÃO COMPLETA: Volume de corte supre exatamente o aterro!"
        vol_botafora = 0.0
        vol_emprestimo = 0.0
    elif saldo_vol > 0:
        vol_botafora = saldo_vol * fator_k
        vol_emprestimo = 0.0
        diagnostico = "EXCESSO DE TERRA (SOBRA): Necessário transporte para BOTA-FORA de {:.2f} m³ (solto).".format(vol_botafora)
    else:
        vol_botafora = 0.0
        vol_emprestimo = abs(saldo_vol)
        diagnostico = "FALTA DE TERRA (DÉFICIT): Necessário EMPRÉSTIMO DE JAZIDA de {:.2f} m³ (compactado).".format(vol_emprestimo)

    # Declividade do terreno e do greide
    decliv_tn_pct = (delta_z / total_ext * 100.0) if total_ext > 0 else 0.0
    decliv_tn_deg = math.degrees(math.atan2(delta_z, total_ext)) if total_ext > 0 else 0.0

    dz_greide = z_g_fim - z_g_ini
    decliv_gr_pct = (dz_greide / total_ext * 100.0) if total_ext > 0 else 0.0
    decliv_gr_deg = math.degrees(math.atan2(abs(dz_greide), total_ext)) if total_ext > 0 else 0.0
    sentido_gr = "Aclive" if dz_greide > 0 else ("Declive" if dz_greide < 0 else "Plano Horizontal")

    # Lista de pontos de passagem formatados
    if pontos_passagem:
        lista_pp = ["  - P.P. {}: d = {:.2f} m | Cota = +{:.2f} m".format(k+1, dp, zp) for k, (dp, zp) in enumerate(pontos_passagem)]
    else:
        lista_pp = ["  - Nenhum Ponto de Passagem interceptado (Seção pura em Corte ou pura em Aterro)."]

    relatorio = [
        "=================================================================",
        "      MEMORIAL DE CÁLCULO DE TERRAPLENAGEM (NBR 6492 & AGPTEA)    ",
        "=================================================================",
        "1. DADOS DA SEÇÃO TOPOGRÁFICA:",
        "   - Localização no Top View : X = {:.2f}, Y = {:.2f}".format(orig_x, orig_y),
        "   - Extensão da Linha de Corte: {:.2f} m".format(total_ext),
        "   - Cota Mín / Máx (TN)     : +{:.2f} m / +{:.2f} m (ΔZ = {:.2f} m)".format(z_min, z_max, delta_z),
        "   - Declividade Média do TN : {:.2f}% ({:.2f}°)".format(decliv_tn_pct, decliv_tn_deg),
        "-----------------------------------------------------------------",
        "2. GREIDE PROJETADO:",
        "   - Tipo de Definição       : {}".format(tipo_greide),
        "   - Cota Inicial / Final    : +{:.2f} m / +{:.2f} m ({})".format(z_g_ini, z_g_fim, sentido_gr),
        "   - Inclinação do Greide    : {:.2f}% ({:.2f}°)".format(decliv_gr_pct, decliv_gr_deg),
        "-----------------------------------------------------------------",
        "3. PONTOS DE PASSAGEM (P.P. - TRANSIÇÃO CORTE/ATERRO):",
    ] + lista_pp + [
        "-----------------------------------------------------------------",
        "4. QUADRO DE ÁREAS DA SEÇÃO (MÉTODO DOS TRAPÉZIOS AGPTEA):",
        "   - Área Total de CORTE  : {:.2f} m²".format(area_total_corte),
        "   - Área Total de ATERRO : {:.2f} m²".format(area_total_aterro),
        "   - Altura Máxima de Corte : {:.2f} m (em d = {:.2f} m)".format(max_h_corte, d_max_corte),
        "   - Altura Máxima de Aterro: {:.2f} m (em d = {:.2f} m)".format(max_h_aterro, d_max_aterro),
        "-----------------------------------------------------------------",
        "5. CUBAÇÃO VOLUMÉTRICA:",
        "   - Faixa de Influência (L) : {:.2f} m".format(largura_secao),
        "   - Fator de Empolamento (K): {:.2f} ({}% de expansão)".format(fator_k, int((fator_k - 1.0) * 100)),
        "   - Volume Geométrico de CORTE : {:.2f} m³".format(vol_corte_geo),
        "   - Volume Geométrico de ATERRO: {:.2f} m³".format(vol_aterro_geo),
        "   - Volume de Corte Solto (Transporte): {:.2f} m³".format(vol_corte_solto),
        "-----------------------------------------------------------------",
        "6. BALANÇO DE MOVIMENTAÇÃO DE MASSA (COMPENSAÇÃO):",
        "   - Saldo Líquido (Corte - Aterro): {:+.2f} m³".format(saldo_vol),
        "   - Diagnóstico Operacional:",
        "     " + diagnostico,
        "-----------------------------------------------------------------",
        "7. CONFIGURAÇÃO DE VISUALIZAÇÃO:",
        "   - " + desc_modo,
        "================================================================="
    ]

    return out_3d, out_2d, desenho_completo_2d, poligonos_corte_crvs, poligonos_aterro_crvs, relatorio

res_3d, res_2d, res_desenho, res_corte, res_aterro, rel = run()

# SAÍDAS CONECTADAS NO GRASSHOPPER:
a = res_3d         # Linha 3D do corte no relevo natural
b = res_2d         # Polilinha 2D do terreno natural
c = res_desenho    # DESENHO COMPLETO (Perfil TN + Greide + Malhas Coloridas Laranja/Verde + Cotas NBR)
d = res_corte      # Polígonos Fechados de CORTE (Curves para Area / Hatch / Bake)
e = res_aterro     # Polígonos Fechados de ATERRO (Curves para Area / Hatch / Bake)
f = rel            # Memorial Técnico de Terraplenagem AGPTEA (Panel)
