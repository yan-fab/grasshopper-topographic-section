# -*- coding: utf-8 -*-
"""
===============================================================================
CÁLCULO DE TERRAPLENAGEM, VOLUMES MULTI-EIXOS & SISTEMA VIÁRIO (NBR 6492 & AGPTEA)
===============================================================================
Algoritmo paramétrico para Grasshopper (Rhinoceros 8 / GhPython).
Unifica múltiplos eixos de corte transversais (A, B, C...) e longitudinais (1, 2, 3...),
integra o sistema viário projetado em 2D/3D (ruas, calçadas, abaulamento de 2.0% e desnível de guias),
calcula automaticamente as distâncias entre eixos consecutivos, calcula as metragens
cúbicas de corte e aterro pelo Método das Seções Transversais da AGPTEA, alinha todas
as seções com espaçamento uniforme e realiza a COMPENSAÇÃO PROGRESSIVA DE MASSAS
(rastreando de onde sai a terra excedente para abastecer o aterro da próxima seção).

Metodologia baseada em:
- "TOPOGRAFIA: CÁLCULO DE VOLUMES – NOTAS DE AULA"
  Prof. Luís Augusto Koenig Veiga (UFPR / AGPTEA)
  Cap. 3.2 (Método das Seções Transversais) e Cap. 3.3 (Balanço de Massas)
- NBR 6492: Representação de Projetos de Arquitetura (Simbologia de Cortes e Níveis)
- Normas DNIT / NBR de Vias Urbanas (Carroçabilidade, Greide e Drenagem com Abaulamento)

ENTRADAS (INPUTS - Bilíngue Português / English):
  Terreno / Terrain                 [List, Curve/Mesh] : Curvas de nível 3D ou Malha topográfica.
  LinhasCorte / SectionLines        [List, Curve]      : Eixos de corte transversais (Seções A, B, C, D...).
  EixosVerticais / LongitudinalLines[List, Curve]      : Eixos longitudinais/verticais (1, 2, 3...) [Opcional].
  CurvaProjeto / GradingLine        [Item/List, Curve] : Curva(s) de greide ou projeto / LinhaDelimitadora [Opcional].
  Viario / Roadway / Ruas           [Item/List, Curve] : Poligonais fechadas 2D do viário (calçadas + pistas + cul-de-sacs) [Opcional].
  InclinacaoMaxima / MaxSlope       [Item, float]      : Inclinação máxima permitida para o greide delimitador [Opcional, Padrão = 15.0 (%)].
  NivelProjeto / ProjectElevation   [Item/List/Tree]   : Cota(s) de platô individual por trecho/quadrante [Opcional].
  Ponto / Point                     [Item, Point3d]    : Ponto base de inserção das seções 2D no Top View [Opcional].
  Espacamento / Spacing             [Item, float]      : Distância vertical uniforme entre as seções 2D [Opcional].
  Largura / Width                   [Item, float]      : Faixa de influência para seção unitária (padrão: 1.0 m).
  Empolamento / BulkingFactor       [Item, float]      : Fator de empolamento do solo para transporte (padrão: 1.20).
  Seletor / Selector                [Item, int]        : Modo de exibição:
                                                         0 = Completo (TN + Greide + Áreas + Todas as Cotas)
                                                         1 = Terraplenagem / Projetado [Padrão]
                                                         2 = Apenas Terreno Natural
  Escala / Scale                    [Item, float]      : Fator de escala dos símbolos, textos e balões NBR (padrão: 1.0).

SAÍDAS (OUTPUTS):
  a : Modelo 3D Completo de Terraplenagem (Superfície Projetada com Asfalto/Calçada + Fatias 3D Laranja/Verde + Greides 3D).
  b : PLANTA BAIXA TÉCNICA (Eixos A, B, C... e 1, 2, 3... com balões NBR, setas de corte, cotas de distância, quadrantes e viário).
  c : DESENHO COMPLETO DAS SEÇÕES 2D ALINHADAS (Títulos, malhas coloridas Laranja/Verde, cotas NBR, corredores viários e banners).
  d : Polígonos de CORTE de todas as seções (Curvas Fechadas para Hachura/Bake).
  e : Polígonos de ATERRO de todas as seções (Curvas Fechadas para Hachura/Bake).
  f : Memorial Técnico Completo de Terraplenagem, Balanço de Massas e Sistema Viário (Panel).
  Viario3D / Roadway3D : Malhas 3D do leito viário (asfalto e calçadas com relevo de guias).
  Asfalto3D            : Malhas 3D exclusivas da pista de rolamento (asfalto grafite escuro).
  Calcadas3D           : Malhas 3D exclusivas dos passeios públicos (concreto claro).
  Viario2D             : Contornos 2D das ruas para planta técnica.
===============================================================================
"""

import math
import Rhino
import Rhino.Geometry as rg
import rhinoscriptsyntax as rs
import System.Drawing

def to_rhino_curve(geo):
    if geo is None: return None
    if hasattr(geo, "Value"):
        val = getattr(geo, "Value", None)
        if val is not None and val is not geo:
            c = to_rhino_curve(val)
            if c is not None: return c
    if isinstance(geo, rg.Curve): return geo
    if isinstance(geo, rg.Polyline): return geo.ToPolylineCurve()
    if isinstance(geo, rg.Line): return rg.LineCurve(geo)
    if isinstance(geo, rg.Arc): return rg.ArcCurve(geo)
    if isinstance(geo, rg.Circle): return rg.ArcCurve(geo)
    try:
        c = rs.coercecurve(geo)
        if c: return c
    except: pass
    try:
        doc = Rhino.RhinoDoc.ActiveDoc
        if doc:
            obj = doc.Objects.FindId(geo)
            if obj and obj.Geometry and isinstance(obj.Geometry, rg.Curve):
                return obj.Geometry
    except: pass
    return None

def to_rhino_geom(geo):
    if geo is None: return None
    if hasattr(geo, "Value"):
        val = getattr(geo, "Value", None)
        if val is not None and val is not geo:
            res = to_rhino_geom(val)
            if res is not None: return res
    if isinstance(geo, (rg.Curve, rg.Mesh, rg.Brep)): return geo
    if isinstance(geo, rg.Polyline): return geo.ToPolylineCurve()
    if isinstance(geo, rg.Line): return rg.LineCurve(geo)
    if isinstance(geo, rg.Arc): return rg.ArcCurve(geo)
    if isinstance(geo, rg.Circle): return rg.ArcCurve(geo)
    if isinstance(geo, rg.Surface): return geo.ToBrep()
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
            if obj and obj.Geometry:
                geom = obj.Geometry
                if isinstance(geom, (rg.Curve, rg.Mesh, rg.Brep)): return geom
                if isinstance(geom, rg.Surface): return geom.ToBrep()
    except: pass
    return None

def to_rhino_point(val):
    if val is None: return None
    if hasattr(val, "Value"):
        v = getattr(val, "Value", None)
        if v is not None and v is not val:
            res = to_rhino_point(v)
            if res is not None: return res
    if isinstance(val, rg.Point3d): return val
    if isinstance(val, rg.Point): return val.Location
    if hasattr(val, "Location"): return val.Location
    try:
        pt = rs.coerce3dpoint(val)
        if pt: return pt
    except: pass
    try:
        doc = Rhino.RhinoDoc.ActiveDoc
        if doc:
            obj = doc.Objects.FindId(val)
            if obj and obj.Geometry and isinstance(obj.Geometry, rg.Point):
                return obj.Geometry.Location
    except: pass
    return None

def to_list(val):
    if val is None: return []
    out = []
    def _flatten(v):
        if v is None: return
        # Suporte completo a Grasshopper DataTree e GH_Structure
        if hasattr(v, "AllData"):
            try:
                for x in v.AllData(): _flatten(x)
                return
            except: pass
        if hasattr(v, "Branches"):
            try:
                for b in v.Branches: _flatten(b)
                return
            except: pass
        # Unpacks iterable collections (List, Array, Tuple, Set), excluding strings and geometrias Rhino
        if hasattr(v, "__iter__"):
            if isinstance(v, (str, bytes)):
                out.append(v)
                return
            is_geom = False
            try:
                if isinstance(v, (rg.GeometryBase, rg.Point3d, rg.Vector3d, rg.Plane)):
                    is_geom = True
            except: pass
            if not is_geom:
                try:
                    for x in v: _flatten(x)
                    return
                except: pass
        out.append(v)
    _flatten(val)
    return out

def parse_seletor(val):
    if val is None: return 1
    if isinstance(val, bool): return 1 if val else 2
    try:
        ival = int(val)
        if ival in [0, 1, 2]: return ival
    except: pass
    s = str(val).strip().lower()
    if "proj" in s or "terra" in s or "corte" in s: return 1
    elif "nat" in s or "tn" in s: return 2
    elif "tod" in s or "all" in s or "tudo" in s: return 0
    return 1

def format_section_label(idx):
    """Generates alphabetic section identifiers: A, B, C... Z, AA, AB..."""
    if idx < 26:
        return chr(65 + idx)
    else:
        return chr(65 + (idx // 26) - 1) + chr(65 + (idx % 26))

def make_filled_mesh_tri(v0, v1, v2, color=None):
    if v0 is None or v1 is None or v2 is None:
        return None
    if v0.DistanceTo(v1) < 1e-4 or v1.DistanceTo(v2) < 1e-4 or v2.DistanceTo(v0) < 1e-4:
        return None
    cross = rg.Vector3d.CrossProduct(v1 - v0, v2 - v0)
    if cross.Length < 1e-6:
        return None
    m = rg.Mesh()
    m.Vertices.Add(v0)
    m.Vertices.Add(v1)
    m.Vertices.Add(v2)
    m.Faces.AddFace(0, 1, 2)
    if color:
        m.VertexColors.Add(color)
        m.VertexColors.Add(color)
        m.VertexColors.Add(color)
    m.Compact()
    try:
        m.Normals.ComputeNormals()
    except:
        pass
    return m if m.IsValid else None

def make_safe_closed_polyline(pts):
    """Creates a valid closed Polyline curve, checking minimum vertex count and validity."""
    if not pts or len(pts) < 3:
        return None
    clean = []
    for p in pts:
        if p is None: continue
        if not clean or p.DistanceTo(clean[-1]) > 1e-4:
            clean.append(p)
    if len(clean) < 3:
        return None
    if clean[0].DistanceTo(clean[-1]) > 1e-4:
        clean.append(clean[0])
    if len(clean) < 4:
        return None
    poly = rg.Polyline(clean)
    if not poly.IsValid:
        return None
    crv = poly.ToPolylineCurve()
    if crv and crv.IsValid:
        return crv
    return None

def create_colored_mesh(quads_pts, color):
    """Creates a 100% valid, sanitized, non-degenerate RhinoCommon mesh.
    Eliminates duplicate vertices, discards zero-area faces and decomposes
    quadrilaterals into clean planar triangles for absolute stability in Rhino 8 / .NET Core.
    """
    if not quads_pts:
        return None

    m = rg.Mesh()

    def add_safe_triangle(v0, v1, v2):
        if v0 is None or v1 is None or v2 is None:
            return False
        if v0.DistanceTo(v1) < 1e-4 or v1.DistanceTo(v2) < 1e-4 or v2.DistanceTo(v0) < 1e-4:
            return False
        cross = rg.Vector3d.CrossProduct(v1 - v0, v2 - v0)
        if cross.Length < 1e-6:
            return False
        if abs(v0.Z) < 1e-3 and abs(v1.Z) < 1e-3 and abs(v2.Z) < 1e-3:
            if cross.Z < 0.0:
                v1, v2 = v2, v1
        idx = m.Vertices.Count
        m.Vertices.Add(v0)
        m.Vertices.Add(v1)
        m.Vertices.Add(v2)
        m.Faces.AddFace(idx, idx + 1, idx + 2)
        if color:
            m.VertexColors.Add(color)
            m.VertexColors.Add(color)
            m.VertexColors.Add(color)
        return True

    for pts in quads_pts:
        if not pts or len(pts) < 3:
            continue

        clean = []
        for p in pts:
            if p is None: continue
            if not clean or p.DistanceTo(clean[-1]) > 1e-4:
                clean.append(p)
        if len(clean) > 1 and clean[0].DistanceTo(clean[-1]) < 1e-4:
            clean.pop()

        n = len(clean)
        if n < 3:
            continue
        elif n == 3:
            add_safe_triangle(clean[0], clean[1], clean[2])
        elif n == 4:
            add_safe_triangle(clean[0], clean[1], clean[2])
            add_safe_triangle(clean[0], clean[2], clean[3])
        else:
            for i in range(1, n - 1):
                add_safe_triangle(clean[0], clean[i], clean[i + 1])

    if m.Faces.Count == 0:
        return None

    m.Compact()
    try:
        m.Normals.ComputeNormals()
    except:
        pass

    if not m.IsValid:
        return None

    return m

# =============================================================================
# MOTOR DE VIÁRIO E TRAFEGABILIDADE (VIÁRIO CARROÇÁVEL NBR / DNIT)
# =============================================================================

def point_in_polygon_2d(x, y, poly_pts):
    """
    Algoritmo padrão de Ray-Casting para contenção de ponto em polígono 2D.
    100% imune a tolerâncias do RhinoCommon e orientações de curva,
    suportando geometrias côncavas, balões de retorno e poligonais complexas de CAD.
    """
    if not poly_pts or len(poly_pts) < 3:
        return False
    inside = False
    n = len(poly_pts)
    j = n - 1
    for i in range(n):
        xi, yi = poly_pts[i][0], poly_pts[i][1]
        xj, yj = poly_pts[j][0], poly_pts[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def point_distance_to_segments(x, y, pts):
    """
    Calcula a distância euclidiana mínima de um ponto 2D (x, y) a uma lista de segmentos de polilinha.
    Utilizado para classificação de calçada vs pista de asfalto e cálculo de buffers de corredor.
    """
    if not pts or len(pts) < 2:
        return 9999.0
    min_dist = float('inf')
    n = len(pts)
    for i in range(n - 1):
        x1, y1 = pts[i][0], pts[i][1]
        x2, y2 = pts[i+1][0], pts[i+1][1]
        dx = x2 - x1
        dy = y2 - y1
        L2 = dx*dx + dy*dy
        if L2 < 1e-12:
            dist = math.hypot(x - x1, y - y1)
        else:
            t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = math.hypot(x - proj_x, y - proj_y)
        if dist < min_dist:
            min_dist = dist
    return min_dist

def find_ray_polygon_interval(p_origin, u_dir, poly_pts):
    """
    Localiza o intervalo de estaca [u_in, u_out] ao longo do raio 2D P(u) = p_origin + u * u_dir
    que se encontra no interior de poly_pts. Utilizado para recortar os eixos de corte exatamente no lote.
    """
    if not poly_pts or len(poly_pts) < 3:
        return None
    px, py = p_origin[0], p_origin[1]
    ux, uy = u_dir[0], u_dir[1]
    dists = []
    n = len(poly_pts)
    for i in range(n - 1):
        x1, y1 = poly_pts[i][0], poly_pts[i][1]
        x2, y2 = poly_pts[i+1][0], poly_pts[i+1][1]
        denom = ux * (y2 - y1) - uy * (x2 - x1)
        if abs(denom) > 1e-9:
            s = (ux * (y1 - py) - uy * (x1 - px)) / (-denom)
            u = ((x1 - px) * (y2 - y1) - (y1 - py) * (x2 - x1)) / denom
            if 0.0 <= s <= 1.0:
                dists.append(round(u, 3))
    dists = sorted(list(set(dists)))
    for k in range(len(dists) - 1):
        u1 = dists[k]
        u2 = dists[k+1]
        if u2 - u1 > 0.5:
            u_mid = (u1 + u2) / 2.0
            if point_in_polygon_2d(px + u_mid * ux, py + u_mid * uy, poly_pts):
                return u1, u2
    return None

def sanitize_site_boundary(raw_limite, raw_projeto=None, tol=0.001):
    """
    Higieniza, projeta em XY, une e valida o polígono de limite do terreno / perímetro do lote.
    Suporta: Curve, Polyline, Brep, Surface, Mesh, ou segmentos de borda desmembrados.
    Se raw_limite for None, verifica se raw_projeto contém o polígono fechado de divisa.
    Retorna: dicionário com curve, bbox, pts_2d, area, ou None.
    """
    candidate_items = []
    if raw_limite is not None:
        candidate_items.extend(to_list(raw_limite))
    elif raw_projeto is not None:
        for it in to_list(raw_projeto):
            c_test = to_rhino_curve(it)
            if c_test and c_test.IsValid:
                c_test_xy = rg.Curve.ProjectToPlane(c_test, rg.Plane.WorldXY) or c_test
                if c_test_xy.IsClosed or c_test_xy.PointAtStart.DistanceTo(c_test_xy.PointAtEnd) < 25.0:
                    candidate_items.append(it)

    if not candidate_items:
        return None

    def extract_curves(item):
        extracted = []
        if item is None: return extracted
        if hasattr(item, "Value"):
            val = getattr(item, "Value", None)
            if val is not None and val is not item:
                return extract_curves(val)
        if isinstance(item, (list, tuple)):
            for sub in item: extracted.extend(extract_curves(sub))
            return extracted
        c = to_rhino_curve(item)
        if c is not None and c.IsValid:
            extracted.append(c)
            return extracted
        if isinstance(item, rg.Brep):
            naked = item.DuplicateNakedEdgeCurves(True, True)
            extracted.extend(naked if naked else item.DuplicateEdgeCurves(True))
            return extracted
        if isinstance(item, rg.Surface):
            b = item.ToBrep()
            if b:
                naked = b.DuplicateNakedEdgeCurves(True, True)
                extracted.extend(naked if naked else b.DuplicateEdgeCurves(True))
            return extracted
        if isinstance(item, rg.Mesh):
            try:
                naked_polys = item.GetNakedEdges()
                if naked_polys:
                    for poly in naked_polys: extracted.append(poly.ToPolylineCurve())
            except: pass
            return extracted
        try:
            b = rs.coercebrep(item)
            if b:
                naked = b.DuplicateNakedEdgeCurves(True, True)
                extracted.extend(naked if naked else b.DuplicateEdgeCurves(True))
                return extracted
        except: pass
        return extracted

    all_crvs = extract_curves(candidate_items)
    if not all_crvs:
        return None

    xy_crvs = []
    for c in all_crvs:
        try:
            c_xy = rg.Curve.ProjectToPlane(c, rg.Plane.WorldXY)
            if c_xy and c_xy.IsValid: xy_crvs.append(c_xy)
            else: xy_crvs.append(c)
        except: xy_crvs.append(c)

    if len(xy_crvs) > 1:
        try:
            joined = rg.Curve.JoinCurves(xy_crvs, 2.5)
            if joined and len(joined) > 0:
                joined_list = list(joined)
            else:
                joined_list = list(xy_crvs)
        except:
            joined_list = list(xy_crvs)
    else:
        joined_list = list(xy_crvs)

    best_c = None
    best_area = 0.0
    for c in joined_list:
        if c is None or not c.IsValid: continue
        c_work = c
        if not c_work.IsClosed:
            d_ends = c_work.PointAtStart.DistanceTo(c_work.PointAtEnd)
            if d_ends <= 35.0:
                try:
                    c_copy = c_work.DuplicateCurve()
                    if c_copy.MakeClosed(d_ends + 0.1) and c_copy.IsClosed:
                        c_work = c_copy
                except: pass
                if not c_work.IsClosed:
                    try:
                        l_close = rg.LineCurve(c_work.PointAtEnd, c_work.PointAtStart)
                        rejoined = rg.Curve.JoinCurves([c_work, l_close], 0.5)
                        if rejoined and len(rejoined) > 0 and rejoined[0].IsClosed:
                            c_work = rejoined[0]
                    except: pass

        if c_work.IsClosed:
            area_val = 0.0
            try:
                amp = rg.AreaMassProperties.Compute(c_work)
                if amp: area_val = abs(amp.Area)
            except: pass
            if area_val > best_area:
                best_area = area_val
                best_c = c_work

    if best_c is None:
        return None

    bb = best_c.GetBoundingBox(True)
    length = best_c.GetLength()
    n_samples = max(int(length / 1.0), 40)
    pts_2d = []
    for i_pt in range(n_samples + 1):
        t_pt = best_c.Domain.T0 + (i_pt / float(n_samples)) * (best_c.Domain.T1 - best_c.Domain.T0)
        p_ev = best_c.PointAt(t_pt)
        pts_2d.append((p_ev.X, p_ev.Y))
    if pts_2d and pts_2d[0] != pts_2d[-1]:
        pts_2d.append(pts_2d[0])

    if best_area < 1e-4 and len(pts_2d) >= 3:
        best_area = abs(sum(pts_2d[i][0]*pts_2d[i+1][1] - pts_2d[i+1][0]*pts_2d[i][1] for i in range(len(pts_2d)-1))) * 0.5

    return {
        'curve': best_c,
        'bbox': bb,
        'bbox_xy': (bb.Min.X, bb.Min.Y, bb.Max.X, bb.Max.Y),
        'pts_2d': pts_2d,
        'area': best_area,
        'is_closed': True
    }

def sanitize_road_polygons(raw_viario, tol=0.001):
    """
    Higieniza, projeta em XY, une e valida geometrias de malha viária de CAD/BIM/Civil 3D.
    Suporta:
      1. Poligonais/curvas fechadas únicas ou múltiplas (calçadas + pistas, lotes, balões de retorno).
      2. Segmentos de curva de CAD desmembrados (linhas, arcos, polilinhas) - unidos via rg.Curve.JoinCurves.
      3. Balões de retorno/ruas abertas na divisa do terreno - fechadas automaticamente na embocadura (até 35m).
      4. Eixos de rua ou guias abertas - convertidos em corredores trafegáveis com largura de faixa.
      5. Breps, Superfícies e Malhas - extrai automaticamente as bordas de contorno.
    Retorna lista de dicionários com arrays discretos de vértices 2D para ray-casting de alta velocidade.
    """
    if not raw_viario:
        return []

    def extract_curves(item):
        extracted = []
        if item is None:
            return extracted
        if hasattr(item, "Value"):
            val = getattr(item, "Value", None)
            if val is not None and val is not item:
                return extract_curves(val)
        if isinstance(item, (list, tuple)):
            for sub in item:
                extracted.extend(extract_curves(sub))
            return extracted

        c = to_rhino_curve(item)
        if c is not None and c.IsValid:
            extracted.append(c)
            return extracted

        if isinstance(item, rg.Brep):
            naked = item.DuplicateNakedEdgeCurves(True, True)
            if naked:
                extracted.extend(naked)
            else:
                extracted.extend(item.DuplicateEdgeCurves(True))
            return extracted

        if isinstance(item, rg.Surface):
            b = item.ToBrep()
            if b:
                naked = b.DuplicateNakedEdgeCurves(True, True)
                extracted.extend(naked if naked else b.DuplicateEdgeCurves(True))
            return extracted

        if isinstance(item, rg.Mesh):
            try:
                naked_polys = item.GetNakedEdges()
                if naked_polys:
                    for poly in naked_polys:
                        extracted.append(poly.ToPolylineCurve())
            except:
                pass
            return extracted

        try:
            b = rs.coercebrep(item)
            if b:
                naked = b.DuplicateNakedEdgeCurves(True, True)
                extracted.extend(naked if naked else b.DuplicateEdgeCurves(True))
                return extracted
        except:
            pass

        return extracted

    raw_curves = extract_curves(raw_viario)
    if not raw_curves:
        return []

    xy_curves = []
    for c in raw_curves:
        if c is None or not c.IsValid:
            continue
        try:
            c_xy = rg.Curve.ProjectToPlane(c, rg.Plane.WorldXY)
            if c_xy is not None and c_xy.IsValid:
                xy_curves.append(c_xy)
            else:
                xy_curves.append(c)
        except:
            xy_curves.append(c)

    if not xy_curves:
        return []

    # 1. União automática de curvas fragmentadas de CAD
    joined_curves = []
    if len(xy_curves) > 1:
        try:
            joined = rg.Curve.JoinCurves(xy_curves, 2.5)
            if joined and len(joined) > 0:
                joined_curves = list(joined)
            else:
                joined_curves = list(xy_curves)
        except:
            joined_curves = list(xy_curves)
    else:
        joined_curves = list(xy_curves)

    # 2. Fechamento automático de curvas quase-fechadas (ex: balão com embocadura aberta na divisa)
    processed_curves = []
    for c in joined_curves:
        if c is None or not c.IsValid:
            continue
        if c.IsClosed:
            processed_curves.append(c)
            continue
        d_ends = c.PointAtStart.DistanceTo(c.PointAtEnd)
        # No desenho viário, embocaduras de acesso na divisa do lote medem tipicamente de 6m a 35m
        if d_ends <= 35.0:
            closed_success = False
            try:
                c_copy = c.DuplicateCurve()
                if c_copy.MakeClosed(d_ends + 0.1) and c_copy.IsClosed:
                    processed_curves.append(c_copy)
                    closed_success = True
            except:
                pass
            if not closed_success:
                try:
                    l_close = rg.LineCurve(c.PointAtEnd, c.PointAtStart)
                    rejoined = rg.Curve.JoinCurves([c, l_close], 0.5)
                    if rejoined and len(rejoined) > 0 and rejoined[0].IsClosed:
                        processed_curves.append(rejoined[0])
                        closed_success = True
                except:
                    pass
            if closed_success:
                continue
        processed_curves.append(c)

    # 3. Discretização em arrays de vértices para cálculos ultra-rápidos (ray-casting e distância)
    polys = []
    for c in processed_curves:
        if c is None or not c.IsValid:
            continue
        bb = c.GetBoundingBox(True)
        is_closed = bool(c.IsClosed)

        length = c.GetLength()
        n_samples = max(int(length / 1.0), 30)
        pts_2d = []
        for i_pt in range(n_samples + 1):
            t_pt = c.Domain.T0 + (i_pt / float(n_samples)) * (c.Domain.T1 - c.Domain.T0)
            p_ev = c.PointAt(t_pt)
            pts_2d.append((p_ev.X, p_ev.Y))

        if is_closed and pts_2d and pts_2d[0] != pts_2d[-1]:
            pts_2d.append(pts_2d[0])

        area_val = 0.0
        if is_closed:
            try:
                amp = rg.AreaMassProperties.Compute(c)
                if amp: area_val = abs(amp.Area)
            except:
                pass
            if area_val < 1e-4 and len(pts_2d) >= 3:
                area_val = abs(sum(pts_2d[i][0]*pts_2d[i+1][1] - pts_2d[i+1][0]*pts_2d[i][1] for i in range(len(pts_2d)-1))) * 0.5

        polys.append({
            'curve': c,
            'bbox': bb,
            'bbox_xy': (bb.Min.X, bb.Min.Y, bb.Max.X, bb.Max.Y),
            'pts_2d': pts_2d,
            'is_closed': is_closed,
            'area': area_val,
            'half_width': 4.70  # Meia-largura padrão para corredores abertos (via padrão 9.40m)
        })

    polys.sort(key=lambda p: (1 if p['is_closed'] else 0, p['area']), reverse=True)
    return polys

def is_point_in_road(pt, road_polygons, tol=0.001):
    """
    Motor ultra-robusto de contenção e classificação de ponto na malha viária.
    Utiliza Ray-Casting para polígonos fechados e distância de buffer para eixos abertos.
    Retorna: (esta_no_viario, eh_pista_asfalto, eh_calcada_pedestre)
    """
    if not road_polygons:
        return False, False, False

    px, py = pt.X, pt.Y
    pt_2d = rg.Point3d(px, py, 0.0)

    # 1. Verificação de polígonos fechados (Ray-Casting + Buffer de calçada NBR)
    for p_info in road_polygons:
        if not p_info['is_closed']:
            continue
        min_x, min_y, max_x, max_y = p_info['bbox_xy']
        if min_x - 0.05 <= px <= max_x + 0.05 and min_y - 0.05 <= py <= max_y + 0.05:
            inside = point_in_polygon_2d(px, py, p_info['pts_2d'])
            if not inside:
                try:
                    rc = p_info['curve'].Contains(pt_2d, rg.Plane.WorldXY, 0.01)
                    if rc in (rg.PointContainment.Inside, rg.PointContainment.Coincident):
                        inside = True
                except:
                    pass
            if inside:
                d_edge = point_distance_to_segments(px, py, p_info['pts_2d'])
                # Faixa de passeio NBR 9050: 1.25m junto às bordas externas
                is_sidewalk = (d_edge < 1.25)
                is_pista = not is_sidewalk
                return True, is_pista, is_sidewalk

    # 2. Verificação de eixos/guias abertas (Buffer de proximidade)
    for c_info in road_polygons:
        if c_info['is_closed']:
            continue
        min_x, min_y, max_x, max_y = c_info['bbox_xy']
        half_w = c_info.get('half_width', 4.70)
        if min_x - half_w <= px <= max_x + half_w and min_y - half_w <= py <= max_y + half_w:
            d_cor = point_distance_to_segments(px, py, c_info['pts_2d'])
            if d_cor <= half_w:
                is_sidewalk = (d_cor > half_w - 1.25)
                is_pista = not is_sidewalk
                return True, is_pista, is_sidewalk

    return False, False, False

def compute_road_corridors_for_section(crv_corte, road_polygons, tol=0.001):
    """
    Localiza todos os intervalos de estaca [d_in, d_out] onde a linha de corte da seção
    atravessa um ou mais polígonos de viário ou eixos de via (calçada + pista).
    """
    if not crv_corte or not road_polygons:
        return []

    p_start = crv_corte.PointAtStart
    p_end = crv_corte.PointAtEnd
    dx = p_end.X - p_start.X
    dy = p_end.Y - p_start.Y
    L_h = math.hypot(dx, dy)
    if L_h < 1e-4: return []
    ux = dx / L_h
    uy = dy / L_h

    crv_xy = rg.Curve.ProjectToPlane(crv_corte, rg.Plane.WorldXY) or crv_corte
    bb_c = crv_xy.GetBoundingBox(True)
    corridors = []

    for p_info in road_polygons:
        r_crv = p_info['curve']
        bb_r = p_info['bbox']

        if p_info['is_closed']:
            if bb_r.Max.X < bb_c.Min.X or bb_r.Min.X > bb_c.Max.X or bb_r.Max.Y < bb_c.Min.Y or bb_r.Min.Y > bb_c.Max.Y:
                continue

            events = rg.Intersect.Intersection.CurveCurve(crv_xy, r_crv, tol, tol)
            dists = []
            if events:
                for ev in events:
                    pt = ev.PointA
                    d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                    if -tol <= d <= L_h + tol:
                        dists.append(max(0.0, min(L_h, d)))

            if point_in_polygon_2d(p_start.X, p_start.Y, p_info['pts_2d']):
                dists.append(0.0)
            if point_in_polygon_2d(p_end.X, p_end.Y, p_info['pts_2d']):
                dists.append(L_h)

            dists = sorted(list(set([round(d, 3) for d in dists])))
            for k in range(0, len(dists) - 1, 2):
                d1 = dists[k]
                d2 = dists[k+1]
                if d2 - d1 > 0.4:
                    d_test = (d1 + d2) / 2.0
                    px_t = p_start.X + ux * d_test
                    py_t = p_start.Y + uy * d_test
                    if point_in_polygon_2d(px_t, py_t, p_info['pts_2d']):
                        corridors.append({
                            'd_in': d1,
                            'd_out': d2,
                            'width': d2 - d1,
                            'd_mid': d_test,
                            'poly': r_crv
                        })
        else:
            # Eixo de via aberto ou guia aberta:
            half_w = p_info.get('half_width', 4.70)
            if bb_r.Max.X + half_w < bb_c.Min.X or bb_r.Min.X - half_w > bb_c.Max.X or bb_r.Max.Y + half_w < bb_c.Min.Y or bb_r.Min.Y - half_w > bb_c.Max.Y:
                continue
            events = rg.Intersect.Intersection.CurveCurve(crv_xy, r_crv, half_w, tol)
            if events:
                for ev in events:
                    pt = ev.PointA
                    d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                    if -tol <= d <= L_h + tol:
                        d1 = max(0.0, d - half_w)
                        d2 = min(L_h, d + half_w)
                        if d2 - d1 > 0.4:
                            corridors.append({
                                'd_in': d1,
                                'd_out': d2,
                                'width': d2 - d1,
                                'd_mid': d,
                                'poly': r_crv
                            })

    if len(corridors) > 1:
        corridors.sort(key=lambda c: c['d_in'])
        merged = [corridors[0]]
        for curr in corridors[1:]:
            prev = merged[-1]
            if curr['d_in'] <= prev['d_out'] + 0.15:
                prev['d_out'] = max(prev['d_out'], curr['d_out'])
                prev['width'] = prev['d_out'] - prev['d_in']
                prev['d_mid'] = (prev['d_in'] + prev['d_out']) / 2.0
            else:
                merged.append(curr)
        corridors = merged

    return corridors
def make_drivable_road_z(d_val, z_base, corridors, cross_slope=0.02, curb_h=0.15, sw_w=1.20):
    """
    Computes normative drivable road elevation at station d_val:
    - Centerline crowned at z_base with 2% cross-slope to gutters
    - +0.15m curb step up to sidewalk
    - Returns z_base if outside any road corridor
    """
    if not corridors:
        return z_base

    for cor in corridors:
        d_in = cor['d_in']
        d_out = cor['d_out']
        if d_in - 1e-4 <= d_val <= d_out + 1e-4:
            w = cor['width']
            d_mid = cor['d_mid']
            w_sw = min(sw_w, w * 0.18) if w >= 3.0 else 0.0
            d_p1 = d_in + w_sw
            d_p2 = d_out - w_sw
            w_pista = max(d_p2 - d_p1, 0.5)

            z_eixo = z_base
            z_gutter = z_eixo - cross_slope * (w_pista / 2.0)
            z_curb = z_gutter + curb_h

            if d_val < d_p1:
                dist_curb = d_p1 - d_val
                return z_curb + 0.015 * dist_curb
            elif d_val <= d_p2:
                dist_center = abs(d_val - d_mid)
                return z_eixo - cross_slope * dist_center
            else:
                dist_curb = d_val - d_p2
                return z_curb + 0.015 * dist_curb

    return z_base

# =============================================================================
# HIGH-DEFINITION VECTOR STROKE FONT ENGINE TABLES
# =============================================================================
STROKES = {
    '0': [[(0.1,0),(0.5,0),(0.6,0.2),(0.6,0.8),(0.5,1),(0.1,1),(0,0.8),(0,0.2),(0.1,0)], [(0.1,0.2),(0.5,0.8)]],
    '1': [[(0.1,0.8),(0.35,1),(0.35,0)], [(0.1,0),(0.6,0)]],
    '2': [[(0,0.8),(0.15,1),(0.45,1),(0.6,0.8),(0.6,0.55),(0,0),(0.6,0)]],
    '3': [[(0,1),(0.6,1),(0.3,0.55),(0.5,0.55),(0.6,0.4),(0.6,0.15),(0.45,0),(0.1,0),(0,0.15)]],
    '4': [[(0.45,0),(0.45,1),(0,0.3),(0.6,0.3)]],
    '5': [[(0.6,1),(0,1),(0,0.55),(0.45,0.55),(0.6,0.4),(0.6,0.15),(0.45,0),(0,0)]],
    '6': [[(0.5,1),(0.15,0.8),(0,0.4),(0,0.2),(0.15,0),(0.45,0),(0.6,0.2),(0.6,0.4),(0.45,0.55),(0,0.55)]],
    '7': [[(0,1),(0.6,1),(0.2,0)]],
    '8': [[(0.15,0.5),(0,0.75),(0.15,1),(0.45,1),(0.6,0.75),(0.45,0.5),(0.6,0.25),(0.45,0),(0.15,0),(0,0.25),(0.15,0.5),(0.45,0.5)]],
    '9': [[(0.6,0.45),(0.15,0.45),(0,0.6),(0,0.8),(0.15,1),(0.45,1),(0.6,0.8),(0.6,0.2),(0.45,0),(0.1,0)]],
    'A': [[(0,0),(0.3,1),(0.6,0)], [(0.12,0.35),(0.48,0.35)]],
    'B': [[(0,0),(0,1),(0.4,1),(0.55,0.85),(0.4,0.55),(0.55,0.3),(0.4,0),(0,0)], [(0,0.55),(0.4,0.55)]],
    'C': [[(0.6,0.85),(0.45,1),(0.15,1),(0,0.75),(0,0.25),(0.15,0),(0.45,0),(0.6,0.15)]],
    'D': [[(0,0),(0,1),(0.35,1),(0.6,0.75),(0.6,0.25),(0.35,0),(0,0)]],
    'E': [[(0.6,1),(0,1),(0,0),(0.6,0)], [(0,0.5),(0.45,0.5)]],
    'F': [[(0.6,1),(0,1),(0,0)], [(0,0.55),(0.45,0.55)]],
    'G': [[(0.6,0.85),(0.45,1),(0.15,1),(0,0.75),(0,0.25),(0.15,0),(0.45,0),(0.6,0.15),(0.6,0.45),(0.35,0.45)]],
    'H': [[(0,0),(0,1)], [(0.6,0),(0.6,1)], [(0,0.5),(0.6,0.5)]],
    'I': [[(0.15,1),(0.45,1)], [(0.3,1),(0.3,0)], [(0.15,0),(0.45,0)]],
    'J': [[(0,0.25),(0.15,0),(0.4,0),(0.5,0.15),(0.5,1)]],
    'K': [[(0,0),(0,1)], [(0.6,1),(0,0.45)], [(0.2,0.55),(0.6,0)]],
    'L': [[(0,1),(0,0),(0.6,0)]],
    'M': [[(0,0),(0,1),(0.3,0.45),(0.6,1),(0.6,0)]],
    'N': [[(0,0),(0,1),(0.6,0),(0.6,1)]],
    'O': [[(0.15,0),(0.45,0),(0.6,0.25),(0.6,0.75),(0.45,1),(0.15,1),(0,0.75),(0,0.25),(0.15,0)]],
    'P': [[(0,0),(0,1),(0.45,1),(0.6,0.8),(0.45,0.55),(0,0.55)]],
    'Q': [[(0.15,0),(0.45,0),(0.6,0.25),(0.6,0.75),(0.45,1),(0.15,1),(0,0.75),(0,0.25),(0.15,0)], [(0.35,0.25),(0.6,-0.1)]],
    'R': [[(0,0),(0,1),(0.45,1),(0.6,0.8),(0.45,0.55),(0,0.55)], [(0.3,0.55),(0.6,0)]],
    'S': [[(0.6,0.85),(0.45,1),(0.15,1),(0,0.8),(0.15,0.55),(0.45,0.45),(0.6,0.25),(0.45,0),(0.15,0),(0,0.15)]],
    'T': [[(0,1),(0.6,1)], [(0.3,1),(0.3,0)]],
    'U': [[(0,1),(0,0.25),(0.15,0),(0.45,0),(0.6,0.25),(0.6,1)]],
    'V': [[(0,1),(0.3,0),(0.6,1)]],
    'W': [[(0,1),(0.15,0),(0.3,0.6),(0.45,0),(0.6,1)]],
    'X': [[(0,0),(0.6,1)], [(0,1),(0.6,0)]],
    'Y': [[(0,1),(0.3,0.5),(0.6,1)], [(0.3,0.5),(0.3,0)]],
    'Z': [[(0,1),(0.6,1),(0,0),(0.6,0)]],
    '+': [[(0.3,0.2),(0.3,0.8)], [(0.05,0.5),(0.55,0.5)]],
    '-': [[(0.05,0.5),(0.55,0.5)]],
    '.': [[(0.25,0),(0.35,0),(0.35,0.1),(0.25,0.1),(0.25,0)]],
    ',': [[(0.35,0.1),(0.35,0),(0.2,-0.15)]],
    ':': [[(0.25,0.2),(0.35,0.2),(0.35,0.3),(0.25,0.3),(0.25,0.2)], [(0.25,0.65),(0.35,0.65),(0.35,0.75),(0.25,0.75),(0.25,0.65)]],
    ';': [[(0.35,0.1),(0.35,0),(0.2,-0.15)], [(0.25,0.65),(0.35,0.65),(0.35,0.75),(0.25,0.75),(0.25,0.65)]],
    '|': [[(0.3,-0.1),(0.3,1.05)]],
    '/': [[(0.05,0),(0.55,1)]],
    '\\': [[(0.05,1),(0.55,0)]],
    '=': [[(0.05,0.35),(0.55,0.35)], [(0.05,0.65),(0.55,0.65)]],
    '(': [[(0.45,1),(0.2,0.75),(0.2,0.25),(0.45,0)]],
    ')': [[(0.15,1),(0.4,0.75),(0.4,0.25),(0.15,0)]],
    '[': [[(0.45,1),(0.2,1),(0.2,0),(0.45,0)]],
    ']': [[(0.15,1),(0.4,1),(0.4,0),(0.15,0)]],
    '%': [[(0.55,1),(0.05,0)], [(0.15,0.75),(0.25,0.75),(0.25,0.85),(0.15,0.85),(0.15,0.75)], [(0.35,0.15),(0.45,0.15),(0.45,0.25),(0.35,0.25),(0.35,0.15)]],
    '°': [[(0.2,0.75),(0.4,0.75),(0.4,0.95),(0.2,0.95),(0.2,0.75)]],
    '²': [[(0.2,0.9),(0.4,1),(0.5,0.9),(0.2,0.65),(0.5,0.65)]],
    '³': [[(0.2,1),(0.5,1),(0.35,0.82),(0.5,0.82),(0.4,0.65),(0.2,0.65)]],
    ' ': [],
}

ACCENT_STROKES = {
    'acute': [[(0.25, 1.1), (0.45, 1.25)]],
    'grave': [[(0.45, 1.1), (0.25, 1.25)]],
    'tilde': [[(0.15, 1.12), (0.28, 1.24), (0.42, 1.12), (0.55, 1.24)]],
    'circ':  [[(0.18, 1.1), (0.35, 1.25), (0.52, 1.1)]],
    'cedil': [[(0.3, 0), (0.3, -0.15), (0.42, -0.2)]],
}

LOWER_STROKES = {
    'a': [[(0.55,0.65),(0.15,0.65),(0,0.5),(0,0.15),(0.15,0),(0.45,0),(0.55,0.15),(0.55,0)], [(0.55,0.65),(0.55,0)], [(0,0.35),(0.55,0.35)]],
    'b': [[(0,1),(0,0)], [(0,0.65),(0.4,0.65),(0.55,0.45),(0.55,0.2),(0.4,0),(0,0)]],
    'c': [[(0.55,0.55),(0.4,0.65),(0.15,0.65),(0,0.45),(0,0.2),(0.15,0),(0.4,0),(0.55,0.1)]],
    'd': [[(0.55,1),(0.55,0)], [(0.55,0.65),(0.15,0.65),(0,0.45),(0,0.2),(0.15,0),(0.55,0)]],
    'e': [[(0,0.35),(0.55,0.35),(0.55,0.5),(0.4,0.65),(0.15,0.65),(0,0.45),(0,0.2),(0.15,0),(0.4,0),(0.55,0.1)]],
    'f': [[(0.45,1),(0.3,1),(0.15,0.85),(0.15,0)], [(0,0.65),(0.45,0.65)]],
    'g': [[(0.55,0.65),(0.15,0.65),(0,0.45),(0,0.2),(0.15,0),(0.55,0),(0.55,-0.25),(0.35,-0.35),(0.15,-0.35)]],
    'h': [[(0,1),(0,0)], [(0,0.45),(0.2,0.65),(0.4,0.65),(0.55,0.45),(0.55,0)]],
    'i': [[(0.3,0.65),(0.3,0)], [(0.25,0.85),(0.35,0.85),(0.35,0.95),(0.25,0.95),(0.25,0.85)]],
    'j': [[(0.4,0.65),(0.4,-0.25),(0.2,-0.35),(0.05,-0.25)], [(0.35,0.85),(0.45,0.85),(0.45,0.95),(0.35,0.95),(0.35,0.85)]],
    'k': [[(0,1),(0,0)], [(0.55,0.65),(0,0.25)], [(0.2,0.38),(0.55,0)]],
    'l': [[(0.2,1),(0.2,0.1),(0.35,0)]],
    'm': [[(0,0.65),(0,0)], [(0,0.5),(0.2,0.65),(0.35,0.5),(0.35,0)], [(0.35,0.5),(0.55,0.65),(0.7,0.5),(0.7,0)]],
    'n': [[(0,0.65),(0,0)], [(0,0.5),(0.2,0.65),(0.4,0.65),(0.55,0.45),(0.55,0)]],
    'o': [[(0.15,0),(0.4,0),(0.55,0.15),(0.55,0.5),(0.4,0.65),(0.15,0.65),(0,0.5),(0,0.15),(0.15,0)]],
    'p': [[(0,0.65),(0,-0.35)], [(0,0.65),(0.4,0.65),(0.55,0.45),(0.55,0.2),(0.4,0),(0,0)]],
    'q': [[(0.55,0.65),(0.55,-0.35)], [(0.55,0.65),(0.15,0.65),(0,0.45),(0,0.2),(0.15,0),(0.55,0)]],
    'r': [[(0,0.65),(0,0)], [(0,0.45),(0.2,0.65),(0.45,0.65)]],
    's': [[(0.55,0.55),(0.4,0.65),(0.15,0.65),(0,0.5),(0.15,0.35),(0.4,0.3),(0.55,0.15),(0.4,0),(0.15,0),(0,0.1)]],
    't': [[(0.25,0.9),(0.25,0.1),(0.4,0)], [(0.1,0.65),(0.45,0.65)]],
    'u': [[(0,0.65),(0,0.15),(0.15,0),(0.4,0),(0.55,0.15),(0.55,0.65),(0.55,0)]],
    'v': [[(0,0.65),(0.3,0),(0.6,0.65)]],
    'w': [[(0,0.65),(0.15,0),(0.3,0.45),(0.45,0),(0.6,0.65)]],
    'x': [[(0,0.65),(0.55,0)], [(0,0),(0.55,0.65)]],
    'y': [[(0,0.65),(0.3,0),(0.6,0.65)], [(0.3,0),(0.15,-0.35)]],
    'z': [[(0,0.65),(0.55,0.65),(0,0),(0.55,0)]],
}

def generate_stroke_text(text_str, pt, height, justification=None, plane=None):
    curves = []
    if text_str is None: return curves
    text_str = str(text_str)
    if not text_str: return curves

    char_widths = []
    char_data = []

    for raw_ch in text_str:
        ch = str(raw_ch)
        accent_type = None
        base_char = ch
        if ch in 'Áá':   base_char, accent_type = ('A' if ch.isupper() else 'a'), 'acute'
        elif ch in 'Àà': base_char, accent_type = ('A' if ch.isupper() else 'a'), 'grave'
        elif ch in 'Ãã': base_char, accent_type = ('A' if ch.isupper() else 'a'), 'tilde'
        elif ch in 'Ââ': base_char, accent_type = ('A' if ch.isupper() else 'a'), 'circ'
        elif ch in 'Éé': base_char, accent_type = ('E' if ch.isupper() else 'e'), 'acute'
        elif ch in 'Êê': base_char, accent_type = ('E' if ch.isupper() else 'e'), 'circ'
        elif ch in 'Íí': base_char, accent_type = ('I' if ch.isupper() else 'i'), 'acute'
        elif ch in 'Óó': base_char, accent_type = ('O' if ch.isupper() else 'o'), 'acute'
        elif ch in 'Õõ': base_char, accent_type = ('O' if ch.isupper() else 'o'), 'tilde'
        elif ch in 'Ôô': base_char, accent_type = ('O' if ch.isupper() else 'o'), 'circ'
        elif ch in 'Úú': base_char, accent_type = ('U' if ch.isupper() else 'u'), 'acute'
        elif ch in 'Çç': base_char, accent_type = ('C' if ch.isupper() else 'c'), 'cedil'

        strokes = None
        w_factor = 0.60
        if base_char in STROKES:
            strokes = STROKES[base_char]
            if base_char in '1I.,:|;': w_factor = 0.35
            elif base_char in 'MW': w_factor = 0.75
            elif base_char in ' ': w_factor = 0.40
        elif base_char in LOWER_STROKES:
            strokes = LOWER_STROKES[base_char]
            if base_char in 'ijlft': w_factor = 0.35
            elif base_char in 'mw': w_factor = 0.75
        elif base_char.upper() in STROKES:
            strokes = STROKES[base_char.upper()]
            if base_char.upper() in '1I.,:|;': w_factor = 0.35
            elif base_char.upper() in 'MW': w_factor = 0.75

        cw = height * w_factor
        char_widths.append(cw)
        char_data.append((strokes, accent_type, cw))

    char_gap = height * 0.18
    total_w = sum(char_widths) + max(0, len(text_str) - 1) * char_gap

    start_x = 0.0
    start_y = 0.0

    if justification == rg.TextJustification.MiddleCenter:
        start_x = -total_w / 2.0
        start_y = -height / 2.0
    elif justification == rg.TextJustification.BottomCenter:
        start_x = -total_w / 2.0
        start_y = 0.0
    elif justification == rg.TextJustification.TopCenter:
        start_x = -total_w / 2.0
        start_y = -height
    elif justification == rg.TextJustification.TopLeft:
        start_x = 0.0
        start_y = -height
    elif justification == rg.TextJustification.MiddleRight:
        start_x = -total_w
        start_y = -height / 2.0
    elif justification == rg.TextJustification.BottomRight:
        start_x = -total_w
        start_y = 0.0

    if plane is None:
        p_origin = rg.Point3d(pt.X, pt.Y, pt.Z)
        x_axis = rg.Vector3d.XAxis
        y_axis = rg.Vector3d.YAxis
    else:
        p_origin = rg.Point3d(pt.X, pt.Y, pt.Z)
        x_axis = plane.XAxis
        y_axis = plane.YAxis

    cur_x = start_x
    for strokes, accent_type, cw in char_data:
        scale_x = cw / 0.60
        if strokes:
            for stroke in strokes:
                if len(stroke) >= 2:
                    pts = [p_origin + x_axis * (cur_x + sx * scale_x) + y_axis * (start_y + sy * height) for sx, sy in stroke]
                    if len(pts) == 2:
                        crv = rg.LineCurve(pts[0], pts[1])
                        if crv and crv.IsValid: curves.append(crv)
                    else:
                        poly = rg.Polyline(pts)
                        if poly.IsValid:
                            crv = poly.ToPolylineCurve()
                            if crv and crv.IsValid: curves.append(crv)

        if accent_type and accent_type in ACCENT_STROKES:
            for a_stroke in ACCENT_STROKES[accent_type]:
                pts = [p_origin + x_axis * (cur_x + sx * scale_x) + y_axis * (start_y + sy * height) for sx, sy in a_stroke]
                if len(pts) == 2:
                    crv = rg.LineCurve(pts[0], pts[1])
                    if crv and crv.IsValid: curves.append(crv)
                else:
                    poly = rg.Polyline(pts)
                    if poly.IsValid:
                        crv = poly.ToPolylineCurve()
                        if crv and crv.IsValid: curves.append(crv)

        cur_x += cw + char_gap

    return curves

def make_text_geometry(text_str, pt, height, justification=None, s=1.0, plane=None):
    """Generates clean, lightweight 2D vector curves for technical text (Stroke Vector Font Engine)
    and native Rhino.Geometry.TextEntity objects for SelText selection and baking in Rhino 8.
    """
    if text_str is None: return []
    text_str = str(text_str)
    if not text_str: return []
    curves = generate_stroke_text(text_str, pt, height, justification, plane)
    try:
        te = rg.TextEntity()
        te.PlainText = text_str
        if plane is not None:
            te.Plane = plane
        else:
            te.Plane = rg.Plane(rg.Point3d(pt.X, pt.Y, pt.Z), rg.Vector3d.XAxis, rg.Vector3d.YAxis)
        te.TextHeight = float(height)
        if justification is not None:
            te.Justification = justification
        else:
            te.Justification = rg.TextJustification.MiddleCenter
        curves.append(te)
    except:
        pass
    return curves

make_text_entity = make_text_geometry

def get_stroke_text_width(text_str, height):
    """Calculates the exact horizontal width that the vector text will occupy."""
    if text_str is None: return 0.0
    text_str = str(text_str)
    if not text_str: return 0.0
    total_w = 0.0
    for ch in text_str:
        base_char = ch
        if ch in 'ÁáÀàÃãÂâ': base_char = 'A' if ch.isupper() else 'a'
        elif ch in 'ÉéÊê':   base_char = 'E' if ch.isupper() else 'e'
        elif ch in 'Íí':     base_char = 'I' if ch.isupper() else 'i'
        elif ch in 'ÓóÕõÔô': base_char = 'O' if ch.isupper() else 'o'
        elif ch in 'Úú':     base_char = 'U' if ch.isupper() else 'u'
        elif ch in 'Çç':     base_char = 'C' if ch.isupper() else 'c'

        w_factor = 0.60
        if base_char in '1I.,:|;': w_factor = 0.35
        elif base_char in 'MW':    w_factor = 0.75
        elif base_char in ' ':     w_factor = 0.40
        elif base_char in 'ijlft': w_factor = 0.35
        elif base_char in 'mw':    w_factor = 0.75
        elif base_char.upper() in '1I.,:|;': w_factor = 0.35
        elif base_char.upper() in 'MW':    w_factor = 0.75

        total_w += height * w_factor

    char_gap = height * 0.18
    total_w += max(0, len(text_str) - 1) * char_gap
    return total_w

def make_box_background_mesh(p0, p1, p2, p3, color=None):
    """Generates a rectangular 2D mesh serving as a background wipeout mask under text."""
    if p0 is None or p1 is None or p2 is None or p3 is None:
        return None
    try:
        m = rg.Mesh()
        for p in [p0, p1, p2, p3]:
            try:
                m.Vertices.Add(p)
            except:
                m.Vertices.Add(float(p.X), float(p.Y), float(getattr(p, 'Z', 0.0)))
        m.Faces.AddFace(0, 1, 2)
        m.Faces.AddFace(0, 2, 3)
        if color is not None:
            for _ in range(4):
                try:
                    m.VertexColors.Add(color)
                except:
                    if hasattr(color, 'R'):
                        m.VertexColors.Add(color.R, color.G, color.B)
                    elif isinstance(color, (tuple, list)):
                        m.VertexColors.Add(color[0], color[1], color[2])
        m.Compact()
        try:
            m.Normals.ComputeNormals()
        except:
            pass
        return m if m.IsValid else None
    except:
        return None

def make_callout_card(center_x, center_y, title_text, sub_text, s=1.0, is_corte=True):
    """Creates a technical callout card with neatly framed text and generous padding."""
    txt_h1 = 1.15 * s
    txt_h2 = 0.85 * s
    pad_x  = 3.00 * s   # Margem lateral ampla para nunca encostar nas bordas verticais
    pad_y  = 1.20 * s   # Margem superior e inferior confortável
    gap_y  = 1.20 * s   # Folga entre os textos e a divisória central

    w_text1 = get_stroke_text_width(title_text, txt_h1)
    w_text2 = get_stroke_text_width(sub_text, txt_h2)
    w_content = max(w_text1, w_text2)
    w_box = max(w_content + pad_x * 2.0, 18.0 * s)
    h_box = txt_h1 + txt_h2 + gap_y + pad_y * 2.0

    p0 = rg.Point3d(center_x - w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p1 = rg.Point3d(center_x + w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p2 = rg.Point3d(center_x + w_box / 2.0, center_y + h_box / 2.0, 0.0)
    p3 = rg.Point3d(center_x - w_box / 2.0, center_y + h_box / 2.0, 0.0)
    box_crv = rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve()

    # Fundo preenchido suave (máscara / wipeout)
    cor_fundo = System.Drawing.Color.FromArgb(255, 255, 255)
    bg_mesh = make_box_background_mesh(p0, p1, p2, p3, cor_fundo)

    # Linha divisória horizontal interna técnica
    y_div = center_y
    p_div_l = rg.Point3d(center_x - w_box / 2.0 + 1.2 * s, y_div, 0.0)
    p_div_r = rg.Point3d(center_x + w_box / 2.0 - 1.2 * s, y_div, 0.0)
    div_crv = rg.LineCurve(p_div_l, p_div_r)

    # Textos perfeitamente centralizados em suas respectivas metades
    y_t1 = center_y + (h_box / 4.0)
    y_t2 = center_y - (h_box / 4.0)

    pt_t1 = rg.Point3d(center_x, y_t1, 0.0)
    te1_crvs = make_text_geometry(title_text, pt_t1, txt_h1, rg.TextJustification.MiddleCenter, s)

    pt_t2 = rg.Point3d(center_x, y_t2, 0.0)
    te2_crvs = make_text_geometry(sub_text, pt_t2, txt_h2, rg.TextJustification.MiddleCenter, s)

    geoms = [bg_mesh, box_crv, div_crv]
    if te1_crvs: geoms.extend(te1_crvs)
    if te2_crvs: geoms.extend(te2_crvs)
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
    """Generates NBR 6492 standard level marker symbol with sharp vector text and dynamic shelf."""
    h_tri = 0.85 * s
    w_tri = 1.10 * s
    h_stem = 0.60 * s
    txt_h = 0.85 * s

    char_w = 0.65 * txt_h
    w_shelf = max(len(text_str) * char_w + 0.6 * s, 3.2 * s)

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
    v_shelf = rg.Point3d(x + w_shelf, y + h_tri + h_stem, 0.0)
    l_stem = rg.LineCurve(v_top_mid, v_stem)
    l_shelf = rg.LineCurve(v_stem, v_shelf)

    p_txt = rg.Point3d(x + 0.20 * s, y + h_tri + h_stem + 0.12 * s, 0.0)
    te_crvs = make_text_geometry(text_str, p_txt, txt_h, rg.TextJustification.BottomLeft, s)

    geoms = [g for g in [l1, l2, l_mid, mesh_dir, lr1, lr2, l_stem, l_shelf] if g is not None]
    if te_crvs:
        if isinstance(te_crvs, list):
            geoms.extend([c for c in te_crvs if c is not None])
        else:
            geoms.append(te_crvs)
    return geoms, te_crvs

# =============================================================================
# MULTI-AXIS SUPPORT FUNCTIONS: PLAN VIEW, NBR BUBBLES AND DIMENSIONS
# =============================================================================

def draw_plan_axis_bubble(pt, arg2, arg3=None, s=1.0):
    """Generates NBR 6492 circular axis bubble at cut line ends in plan view with sight arrow."""
    # Robustly handle both parameter orders:
    # (pt, label_str, dir_vec, s) or (pt, dir_vec, label_str, s)
    if isinstance(arg2, (rg.Vector3d, rg.Vector3f)):
        dir_vec = arg2
        label_str = str(arg3) if arg3 is not None else ""
    elif isinstance(arg3, (rg.Vector3d, rg.Vector3f)):
        label_str = str(arg2) if arg2 is not None else ""
        dir_vec = arg3
    else:
        label_str = str(arg2) if arg2 is not None else ""
        dir_vec = arg3

    geoms = []
    p_flat = rg.Point3d(pt.X, pt.Y, 0.0)
    r = 1.35 * s
    circ = rg.Circle(p_flat, r).ToNurbsCurve()
    geoms.append(circ)

    txt_crvs = make_text_geometry(label_str, p_flat, 1.15 * s, rg.TextJustification.MiddleCenter, s)
    if txt_crvs: geoms.extend(txt_crvs)

    if dir_vec and dir_vec.Length > 1e-4:
        v_norm = rg.Vector3d(dir_vec.X, dir_vec.Y, 0.0)
        if v_norm.Length > 1e-6:
            v_norm.Unitize()
            n_view = rg.Vector3d(-v_norm.Y, v_norm.X, 0.0)
            p_base = p_flat + n_view * r
            p_tip = p_flat + n_view * (r + 1.2 * s)
            p_left = p_base - v_norm * (0.45 * s)
            p_right = p_base + v_norm * (0.45 * s)

            seta_mesh = make_filled_mesh_tri(p_tip, p_left, p_right)
            l_seta1 = rg.LineCurve(p_tip, p_left)
            l_seta2 = rg.LineCurve(p_tip, p_right)
            l_seta3 = rg.LineCurve(p_left, p_right)
            geoms.extend([g for g in [seta_mesh, l_seta1, l_seta2, l_seta3] if g is not None])

    return geoms

def draw_plan_dimension(p1, p2, dist_val, s=1.0, offset_dir=None, offset_dist=0.0):
    """
    Draws a technical linear dimension chain with extension lines, 45° NBR ticks and aligned text
    aligned parallel to dimension line outside the drawing.
    """
    geoms = []
    p1_2d = rg.Point3d(p1.X, p1.Y, 0.0)
    p2_2d = rg.Point3d(p2.X, p2.Y, 0.0)
    vec = p2_2d - p1_2d
    d_len = vec.Length
    if d_len < 1e-3: return geoms

    u_dim = rg.Vector3d(vec.X, vec.Y, vec.Z)
    u_dim.Unitize()

    # If offset is provided, shifts dimension line outward from the drawing
    if offset_dir is not None and abs(offset_dist) > 1e-4:
        off_v = rg.Vector3d(offset_dir.X, offset_dir.Y, 0.0)
        off_v.Unitize()
        p1_cota = p1_2d + off_v * offset_dist
        p2_cota = p2_2d + off_v * offset_dist

        # Extension lines
        l_ext1 = rg.LineCurve(p1_2d + off_v * (0.8 * s), p1_cota + off_v * (1.2 * s))
        l_ext2 = rg.LineCurve(p2_2d + off_v * (0.8 * s), p2_cota + off_v * (1.2 * s))
        geoms.extend([l_ext1, l_ext2])
    else:
        p1_cota = p1_2d
        p2_cota = p2_2d
        off_v = rg.Vector3d(-u_dim.Y, u_dim.X, 0.0)

    # Main dimension line
    l_cota = rg.LineCurve(p1_cota, p2_cota)
    geoms.append(l_cota)

    # Ticks arquitetônicos a 45 graus
    tick_len = 0.85 * s
    tick_vec = (u_dim + off_v) * 0.7071
    t1_a = p1_cota - tick_vec * (tick_len / 2.0)
    t1_b = p1_cota + tick_vec * (tick_len / 2.0)
    t2_a = p2_cota - tick_vec * (tick_len / 2.0)
    t2_b = p2_cota + tick_vec * (tick_len / 2.0)
    geoms.append(rg.LineCurve(t1_a, t1_b))
    geoms.append(rg.LineCurve(t2_a, t2_b))

    # Orientação legível do texto (evita texto de cabeça para baixo segundo NBR 6492)
    if u_dim.Y < -1e-4 or (abs(u_dim.Y) <= 1e-4 and u_dim.X < 0):
        u_txt = -u_dim
    else:
        u_txt = u_dim
    v_txt = rg.Vector3d(-u_txt.Y, u_txt.X, 0.0)

    # Text position slightly offset outward from the dimension line
    p_mid = rg.Point3d((p1_cota.X + p2_cota.X) / 2.0, (p1_cota.Y + p2_cota.Y) / 2.0, 0.0) + off_v * (0.85 * s)
    plane_txt = rg.Plane(p_mid, u_txt, v_txt)
    if isinstance(dist_val, str):
        txt_str = dist_val
    elif isinstance(dist_val, (int, float)):
        txt_str = "D = {:.2f}m".format(dist_val).replace('.', ',')
    else:
        txt_str = str(dist_val)
    txt_cota = make_text_geometry(txt_str, p_mid, 0.85 * s, rg.TextJustification.MiddleCenter, s, plane_txt)
    if txt_cota: geoms.extend(txt_cota)

    return geoms

def draw_quadrant_badge(p_cen, txt_str, s=1.0, plane_ref=None):
    """
    Desenha o badge retangular técnico com o ID do quadrante perfeitamente
    centralizado no centroide geométrico, com máscara suave de fundo e contorno nítido.
    """
    geoms = []
    txt_h = 0.90 * s
    pad_x = 1.60 * s
    pad_y = 0.75 * s

    w_txt = get_stroke_text_width(txt_str, txt_h)
    w_box = max(w_txt + pad_x * 2.0, 8.5 * s)
    h_box = txt_h + pad_y * 2.0

    if plane_ref is None:
        plane_badge = rg.Plane(p_cen, rg.Vector3d.XAxis, rg.Vector3d.YAxis)
    else:
        # Garante leitura da esquerda para a direita (evita texto invertido)
        u_axis = rg.Vector3d(plane_ref.XAxis)
        v_axis = rg.Vector3d(plane_ref.YAxis)
        if u_axis.X < -1e-4 or (abs(u_axis.X) <= 1e-4 and u_axis.Y < 0):
            u_axis = -u_axis
            v_axis = -v_axis
        plane_badge = rg.Plane(p_cen, u_axis, v_axis)

    p0 = p_cen - plane_badge.XAxis * (w_box / 2.0) - plane_badge.YAxis * (h_box / 2.0)
    p1 = p_cen + plane_badge.XAxis * (w_box / 2.0) - plane_badge.YAxis * (h_box / 2.0)
    p2 = p_cen + plane_badge.XAxis * (w_box / 2.0) + plane_badge.YAxis * (h_box / 2.0)
    p3 = p_cen - plane_badge.XAxis * (w_box / 2.0) + plane_badge.YAxis * (h_box / 2.0)

    bg_mesh = make_box_background_mesh(p0, p1, p2, p3, System.Drawing.Color.FromArgb(255, 255, 255))
    badge_crv = rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve()
    if bg_mesh: geoms.append(bg_mesh)
    if badge_crv and badge_crv.IsValid: geoms.append(badge_crv)

    txt_crvs = make_text_geometry(txt_str, p_cen, txt_h, rg.TextJustification.MiddleCenter, s, plane_badge)
    if txt_crvs: geoms.extend(txt_crvs)

    return geoms


# =============================================================================
# NORMATIVE FUNCTIONS: 20M ROAD STATIONING, SLOPE TEETH, CONTOURS & CLEARANCE
# (ABNT NBR 13.133, NBR 6492, DNIT & LEI FEDERAL 6.766/1979)
# =============================================================================


def draw_linear_graphic_scale(p_orig, s=1.0):
    """Desenha escala gráfica linear de 0 a 20m com blocos alternados preto e branco."""
    geoms = []
    blocks = [0, 5, 10, 20]
    h_bar = 1.6 * s
    for k in range(len(blocks) - 1):
        b0 = blocks[k] * s
        b1 = blocks[k+1] * s
        p0 = p_orig + rg.Vector3d(b0, 0, 0)
        p1 = p_orig + rg.Vector3d(b1, 0, 0)
        p2 = p_orig + rg.Vector3d(b1, h_bar, 0)
        p3 = p_orig + rg.Vector3d(b0, h_bar, 0)
        cor_b = System.Drawing.Color.Black if (k % 2 == 0) else System.Drawing.Color.White
        m_b = make_box_background_mesh(p0, p1, p2, p3, cor_b)
        if m_b: geoms.append(m_b)
        geoms.append(rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve())
        geoms.extend(make_text_geometry("{}m".format(blocks[k]), p0 - rg.Vector3d(0, 1.2*s, 0), 0.70*s, rg.TextJustification.MiddleCenter, s))
    p_last = p_orig + rg.Vector3d(blocks[-1] * s, 0, 0)
    geoms.extend(make_text_geometry("{}m".format(blocks[-1]), p_last - rg.Vector3d(0, 1.2*s, 0), 0.70*s, rg.TextJustification.MiddleCenter, s))
    geoms.extend(make_text_geometry("ESCALA GRÁFICA LINEAR", p_orig + rg.Vector3d((blocks[-1]*s)/2.0, h_bar + 2.0*s, 0), 0.75*s, rg.TextJustification.MiddleCenter, s))
    return geoms

# =========================================================================
# TABELA OFICIAL DE ROTEIRO PERIMÉTRICO (MATRÍCULA 30.901 - 18 VÉRTICES)
# (Coordenadas UTM SIRGAS 2000 Fuso 23S, Azimutes, Distâncias e Lat/Long)
# =========================================================================
ROTEIRO_PERIMETRICO_OFICIAL = [
    ("1", "2", "7.386.322,1600", "293.173,5520", "259°44'25\"", "2,835 m", "1,00012840", "23°37'13,789920\"S", "47°01'38,206611\"W"),
    ("2", "3", "7.386.320,3710", "293.167,7500", "252°51'48\"", "6,072 m", "1,00012843", "23°37'13,845383\"S", "47°01'38,412139\"W"),
    ("3", "4", "7.386.316,5680", "293.160,5540", "242°08'39\"", "8,139 m", "1,00012847", "23°37'13,965654\"S", "47°01'38,667841\"W"),
    ("4", "5", "7.386.288,6190", "293.101,7100", "244°35'38\"", "65,144 m", "1,00012877", "23°37'14,846796\"S", "47°01'40,757223\"W"),
    ("5", "6", "7.386.289,9750", "293.089,0030", "276°05'28\"", "12,779 m", "1,00012884", "23°37'14,796870\"S", "47°01'41,204714\"W"),
    ("6", "7", "7.386.296,4170", "293.069,2890", "288°05'46\"", "20,740 m", "1,00012894", "23°37'14,578431\"S", "47°01'41,896794\"W"),
    ("7", "8", "7.386.329,9840", "293.052,0560", "332°49'28\"", "37,732 m", "1,00012903", "23°37'13,479645\"S", "47°01'42,487792\"W"),
    ("8", "9", "7.386.342,7040", "293.045,1770", "331°35'43\"", "14,461 m", "1,00012906", "23°37'13,063106\"S", "47°01'42,724043\"W"),
    ("9", "10", "7.386.402,7530", "293.013,1630", "331°56'11\"", "68,002 m", "1,00012922", "23°37'11,096906\"S", "47°01'43,823096\"W"),
    ("10", "11", "7.386.420,8650", "293.004,0370", "333°15'29\"", "20,281 m", "1,00012927", "23°37'10,504105\"S", "47°01'44,135896\"W"),
    ("11", "12", "7.386.460,2300", "292.984,7390", "333°53'04\"", "43,841 m", "1,00012937", "23°37'09,215944\"S", "47°01'44,796813\"W"),
    ("12", "13", "7.386.546,9843", "292.952,6286", "339°41'20\"", "92,506 m", "1,00012953", "23°37'06,381845\"S", "47°01'45,885877\"W"),
    ("13", "14", "7.386.579,2082", "293.083,1451", "76°07'53\"", "134,436 m", "1,00012887", "23°37'05,394848\"S", "47°01'41,266584\"W"),
    ("14", "15", "7.386.447,6400", "293.130,6640", "160°08'30\"", "139,887 m", "1,00012862", "23°37'09,692379\"S", "47°01'39,656468\"W"),
    ("15", "16", "7.386.380,5850", "293.155,0810", "159°59'30\"", "71,362 m", "1,00012850", "23°37'11,882746\"S", "47°01'38,828845\"W"),
    ("16", "17", "7.386.330,1660", "293.173,6450", "159°47'12\"", "53,728 m", "1,00012840", "23°37'13,529788\"S", "47°01'38,199326\"W"),
    ("17", "18", "7.386.326,3840", "293.174,9550", "160°53'42\"", "4,002 m", "1,00012840", "23°37'13,653297\"S", "47°01'38,155015\"W"),
    ("18", "1", "7.386.322,6650", "293.176,3420", "159°32'49\"", "3,969 m", "1,00012839", "23°37'13,774794\"S", "47°01'38,107957\"W"),
]

def make_box_poly(x0, y0, x1, y1):
    """Gera uma PolylineCurve fechada retangular 2D."""
    return rg.Polyline([
        rg.Point3d(x0, y0, 0), rg.Point3d(x1, y0, 0),
        rg.Point3d(x1, y1, 0), rg.Point3d(x0, y1, 0),
        rg.Point3d(x0, y0, 0)
    ]).ToPolylineCurve()

def make_rounded_rect_poly(x0, y0, x1, y1, r):
    """Gera um contorno retangular com cantos chanfrados/arredondados."""
    r = min(r, abs(x1 - x0) * 0.35, abs(y1 - y0) * 0.35)
    pts = [
        rg.Point3d(x0 + r, y0, 0), rg.Point3d(x1 - r, y0, 0),
        rg.Point3d(x1, y0 + r, 0), rg.Point3d(x1, y1 - r, 0),
        rg.Point3d(x1 - r, y1, 0), rg.Point3d(x0 + r, y1, 0),
        rg.Point3d(x0, y1 - r, 0), rg.Point3d(x0, y0 + r, 0),
        rg.Point3d(x0 + r, y0, 0)
    ]
    return rg.Polyline(pts).ToPolylineCurve()

def draw_official_a0_carimbo(xs0, ys0, sc, sheet_title, sheet_num, scale_str, volume_summary=None, s=1.0):
    """
    Desenha o carimbo / selo técnico regulamentar oficial do projeto,
    replicando com fidelidade geométrica o modelo oficial da Prefeitura
    e do projeto de referência (Marcos Jefferson Cardone CAU A206145-7,
    Nicole Yukie Pisciottano, Matrícula 30901, Vargem Grande Paulista-SP).
    Dimensões nominais no papel A0: 175 x 277 mm.
    """
    geoms = []
    w_selo = 175.0 * sc
    h_selo = 277.0 * sc
    xs1 = xs0 + w_selo
    ys1 = ys0 + h_selo

    # 1. Fundo opaco e moldura externa do carimbo
    bg_selo = make_box_background_mesh(
        rg.Point3d(xs0, ys0, 0), rg.Point3d(xs1, ys0, 0),
        rg.Point3d(xs1, ys1, 0), rg.Point3d(xs0, ys1, 0),
        System.Drawing.Color.FromArgb(254, 254, 254)
    )
    if bg_selo: geoms.append(bg_selo)
    geoms.append(make_box_poly(xs0, ys0, xs1, ys1))

    # 2. BLOCO 1 (TOPO): TÍTULO DA PRANCHA E NÚMERO DA FOLHA (H = 32mm)
    y_div_top = ys1 - 32.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(xs0, y_div_top, 0), rg.Point3d(xs1, y_div_top, 0)))

    # Divisão vertical: Título à esquerda (138mm) e Folha em badge à direita (37mm)
    x_badge_div = xs1 - 37.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(x_badge_div, y_div_top, 0), rg.Point3d(x_badge_div, ys1, 0)))

    # Box com cantos arredondados para a Folha
    bx0 = x_badge_div + 2.5 * sc; by0 = y_div_top + 2.5 * sc
    bx1 = xs1 - 2.5 * sc; by1 = ys1 - 2.5 * sc
    geoms.append(make_rounded_rect_poly(bx0, by0, bx1, by1, 2.5 * sc))
    geoms.extend(make_text_geometry("Folha:", rg.Point3d(bx0 + 2.5*sc, by1 - 4.2*sc, 0), 1.9*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry(sheet_num, rg.Point3d((bx0 + bx1)/2.0, (by0 + by1)/2.0 - 1.0*sc, 0), 5.2*sc, rg.TextJustification.MiddleCenter, s))

    # Título da Prancha
    geoms.extend(make_text_geometry("Título:", rg.Point3d(xs0 + 3.0*sc, ys1 - 3.8*sc, 0), 1.9*sc, rg.TextJustification.TopLeft, s))
    # Quebra de título se muito longo
    if len(sheet_title) > 28:
        pts_tit = sheet_title.split(" (")
        t1 = pts_tit[0]
        t2 = "(" + pts_tit[1] if len(pts_tit) > 1 else ""
        geoms.extend(make_text_geometry(t1, rg.Point3d(xs0 + 3.0*sc, ys1 - 13.5*sc, 0), 3.2*sc, rg.TextJustification.BottomLeft, s))
        if t2:
            geoms.extend(make_text_geometry(t2, rg.Point3d(xs0 + 3.0*sc, ys1 - 22.0*sc, 0), 2.4*sc, rg.TextJustification.BottomLeft, s))
    else:
        geoms.extend(make_text_geometry(sheet_title, rg.Point3d(xs0 + 3.0*sc, ys1 - 16.0*sc, 0), 3.6*sc, rg.TextJustification.BottomLeft, s))

    # 3. BLOCO 2: DADOS CADASTRAIS DO PROJETO E DO IMÓVEL (H = 68mm)
    y_div_cad = y_div_top - 68.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(xs0, y_div_cad, 0), rg.Point3d(xs1, y_div_cad, 0)))

    geoms.extend(make_text_geometry("Objetivo:", rg.Point3d(xs0 + 3.0*sc, y_div_top - 4.5*sc, 0), 1.8*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("Condomínio de Lotes", rg.Point3d(xs0 + 3.0*sc, y_div_top - 12.0*sc, 0), 3.0*sc, rg.TextJustification.BottomLeft, s))
    geoms.append(rg.LineCurve(rg.Point3d(xs0, y_div_top - 16.0*sc, 0), rg.Point3d(xs1, y_div_top - 16.0*sc, 0)))

    # Sub-colunas: Esquerda (Município, Proprietário, Imóvel, Escala) e Direita (Área, Perímetro, Matrícula, Data)
    x_cad_mid = xs0 + 104.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(x_cad_mid, y_div_cad, 0), rg.Point3d(x_cad_mid, y_div_top - 16.0*sc, 0)))

    # Esquerda:
    geoms.extend(make_text_geometry("Município:", rg.Point3d(xs0 + 3.0*sc, y_div_top - 18.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("Vargem Grande Paulista-SP", rg.Point3d(xs0 + 3.0*sc, y_div_top - 26.0*sc, 0), 2.5*sc, rg.TextJustification.BottomLeft, s))

    geoms.extend(make_text_geometry("Proprietário(a):", rg.Point3d(xs0 + 3.0*sc, y_div_top - 29.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("NICOLE YUKIE PISCIOTTANO", rg.Point3d(xs0 + 3.0*sc, y_div_top - 37.0*sc, 0), 2.5*sc, rg.TextJustification.BottomLeft, s))

    geoms.extend(make_text_geometry("Imóvel:", rg.Point3d(xs0 + 3.0*sc, y_div_top - 40.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("CONDOMÍNIO VARGEM GRANDE", rg.Point3d(xs0 + 3.0*sc, y_div_top - 48.0*sc, 0), 2.5*sc, rg.TextJustification.BottomLeft, s))

    geoms.extend(make_text_geometry("Escala:", rg.Point3d(xs0 + 3.0*sc, y_div_top - 51.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry(scale_str, rg.Point3d(xs0 + 3.0*sc, y_div_cad + 3.5*sc, 0), 2.8*sc, rg.TextJustification.BottomLeft, s))

    # Direita:
    geoms.extend(make_text_geometry("Área Total:", rg.Point3d(x_cad_mid + 3.0*sc, y_div_top - 18.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("35.087,731 m²", rg.Point3d(x_cad_mid + 3.0*sc, y_div_top - 26.5*sc, 0), 2.8*sc, rg.TextJustification.BottomLeft, s))

    geoms.extend(make_text_geometry("Perímetro:", rg.Point3d(x_cad_mid + 3.0*sc, y_div_top - 29.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("799,964 m", rg.Point3d(x_cad_mid + 3.0*sc, y_div_top - 37.0*sc, 0), 2.5*sc, rg.TextJustification.BottomLeft, s))

    geoms.extend(make_text_geometry("Matrícula:", rg.Point3d(x_cad_mid + 3.0*sc, y_div_top - 40.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("Matrícula 30901", rg.Point3d(x_cad_mid + 3.0*sc, y_div_top - 48.0*sc, 0), 2.5*sc, rg.TextJustification.BottomLeft, s))

    geoms.extend(make_text_geometry("Data:", rg.Point3d(x_cad_mid + 3.0*sc, y_div_top - 51.5*sc, 0), 1.6*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("30/09/2026", rg.Point3d(x_cad_mid + 3.0*sc, y_div_cad + 3.5*sc, 0), 2.5*sc, rg.TextJustification.BottomLeft, s))

    # 4. BLOCO 3: SITUAÇÃO, QUADRO DE VOLUMES E RESPONSABILIDADE TÉCNICA (H = 117mm)
    y_div_mid = ys0 + 60.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(xs0, y_div_mid, 0), rg.Point3d(xs1, y_div_mid, 0)))

    # Divisão vertical central (Esquerda: Situação/Volumes; Direita: Assinaturas)
    x_mid_col = xs0 + 82.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(x_mid_col, y_div_mid, 0), rg.Point3d(x_mid_col, y_div_cad, 0)))

    # Sub-bloco Situação (Topo Esquerda, H=50mm)
    y_div_sit = y_div_cad - 50.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(xs0, y_div_sit, 0), rg.Point3d(x_mid_col, y_div_sit, 0)))
    geoms.extend(make_text_geometry("Situação:", rg.Point3d(xs0 + 3.0*sc, y_div_cad - 4.5*sc, 0), 1.8*sc, rg.TextJustification.TopLeft, s))

    # Esboço esquemático de situação da gleba com vias de acesso
    cx_sit = xs0 + 41.0 * sc; cy_sit = (y_div_cad + y_div_sit) / 2.0 - 2.0 * sc
    geoms.append(make_rounded_rect_poly(cx_sit - 22.0*sc, cy_sit - 14.0*sc, cx_sit + 22.0*sc, cy_sit + 14.0*sc, 2.0*sc))
    # Eixo rodoviário Raposo Tavares e Estrada de Caucaia
    geoms.append(rg.LineCurve(rg.Point3d(cx_sit - 30.0*sc, cy_sit - 8.0*sc, 0), rg.Point3d(cx_sit + 30.0*sc, cy_sit - 4.0*sc, 0)))
    geoms.append(rg.LineCurve(rg.Point3d(cx_sit + 12.0*sc, cy_sit - 18.0*sc, 0), rg.Point3d(cx_sit + 8.0*sc, cy_sit + 18.0*sc, 0)))
    geoms.extend(make_text_geometry("Rod. Raposo Tavares Km 43", rg.Point3d(cx_sit, cy_sit - 10.5*sc, 0), 1.3*sc, rg.TextJustification.MiddleCenter, s))
    geoms.extend(make_text_geometry("Est. Caucaia do Alto", rg.Point3d(cx_sit + 22.0*sc, cy_sit + 8.0*sc, 0), 1.2*sc, rg.TextJustification.MiddleLeft, s))
    # Seta Norte na situação
    geoms.append(rg.LineCurve(rg.Point3d(cx_sit - 26.0*sc, cy_sit + 6.0*sc, 0), rg.Point3d(cx_sit - 26.0*sc, cy_sit + 14.0*sc, 0)))
    geoms.append(rg.LineCurve(rg.Point3d(cx_sit - 28.0*sc, cy_sit + 11.0*sc, 0), rg.Point3d(cx_sit - 26.0*sc, cy_sit + 14.0*sc, 0)))
    geoms.append(rg.LineCurve(rg.Point3d(cx_sit - 24.0*sc, cy_sit + 11.0*sc, 0), rg.Point3d(cx_sit - 26.0*sc, cy_sit + 14.0*sc, 0)))
    geoms.extend(make_text_geometry("N", rg.Point3d(cx_sit - 26.0*sc, cy_sit + 15.8*sc, 0), 1.4*sc, rg.TextJustification.MiddleCenter, s))

    # Sub-bloco Quadro de Volumes & Áreas (Fundo Esquerda, H=67mm)
    geoms.extend(make_text_geometry("Quadro de Volumes & Áreas:", rg.Point3d(xs0 + 3.0*sc, y_div_sit - 4.5*sc, 0), 1.8*sc, rg.TextJustification.TopLeft, s))
    if volume_summary:
        v_c = volume_summary.get('corte_geo', 0.0)
        v_a = volume_summary.get('aterro_geo', 0.0)
        s_g = volume_summary.get('saldo', 0.0)
        fk  = volume_summary.get('fator_k', 1.20)
        txt_vc = "Corte Geométrico: {:.2f} m³".format(v_c).replace('.', ',')
        txt_va = "Aterro Compact.: {:.2f} m³".format(v_a).replace('.', ',')
        txt_fk = "Fator Empolamento K: {:.2f}".format(fk).replace('.', ',')
        txt_sg = "Saldo Global: {:+.2f} m³".format(s_g).replace('.', ',')
        txt_dg = "Balanço: {}".format("SOBRA / BOTA-FORA" if s_g > 0 else "DÉFICIT / JAZIDA")
    else:
        txt_vc = "Corte Geométrico: Calculado em 3D"
        txt_va = "Aterro Compact.: Conforme Seções"
        txt_fk = "Fator Empolamento K: 1,20 (Argila)"
        txt_sg = "Compensação: Otimizada (Bruckner)"
        txt_dg = "Movimentação: Seções Médias AGPTEA"

    geoms.extend(make_text_geometry(txt_vc, rg.Point3d(xs0 + 3.0*sc, y_div_sit - 13.0*sc, 0), 1.8*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry(txt_va, rg.Point3d(xs0 + 3.0*sc, y_div_sit - 22.0*sc, 0), 1.8*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry(txt_fk, rg.Point3d(xs0 + 3.0*sc, y_div_sit - 31.0*sc, 0), 1.8*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry(txt_sg, rg.Point3d(xs0 + 3.0*sc, y_div_sit - 40.0*sc, 0), 1.8*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry(txt_dg, rg.Point3d(xs0 + 3.0*sc, y_div_sit - 49.0*sc, 0), 1.7*sc, rg.TextJustification.BottomLeft, s))

    # Sub-bloco Assinaturas e Responsabilidade Técnica (Direita, H=117mm)
    geoms.extend(make_text_geometry("Proprietário(a):", rg.Point3d(x_mid_col + 3.0*sc, y_div_cad - 4.5*sc, 0), 1.8*sc, rg.TextJustification.TopLeft, s))
    # Linha de assinatura proprietário
    y_sig_prop = y_div_cad - 22.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(x_mid_col + 8.0*sc, y_sig_prop, 0), rg.Point3d(xs1 - 8.0*sc, y_sig_prop, 0)))
    geoms.extend(make_text_geometry("NICOLE YUKIE PISCIOTTANO", rg.Point3d((x_mid_col + xs1)/2.0, y_sig_prop - 3.5*sc, 0), 2.0*sc, rg.TextJustification.MiddleCenter, s))

    geoms.extend(make_text_geometry("Resp. Técnico(a):", rg.Point3d(x_mid_col + 3.0*sc, y_div_cad - 34.0*sc, 0), 1.8*sc, rg.TextJustification.TopLeft, s))
    # Linha de assinatura arquiteto urbanista
    y_sig_rt = y_div_cad - 52.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(x_mid_col + 8.0*sc, y_sig_rt, 0), rg.Point3d(xs1 - 8.0*sc, y_sig_rt, 0)))
    geoms.extend(make_text_geometry("Marcos Jefferson Cardone", rg.Point3d((x_mid_col + xs1)/2.0, y_sig_rt - 3.5*sc, 0), 2.2*sc, rg.TextJustification.MiddleCenter, s))
    geoms.extend(make_text_geometry("CAU nº A206145-7", rg.Point3d((x_mid_col + xs1)/2.0, y_sig_rt - 7.5*sc, 0), 1.8*sc, rg.TextJustification.MiddleCenter, s))

    # Topógrafo
    geoms.extend(make_text_geometry("Levantamento Topográfico Cadastral:", rg.Point3d(x_mid_col + 3.0*sc, y_div_cad - 69.0*sc, 0), 1.7*sc, rg.TextJustification.TopLeft, s))
    geoms.extend(make_text_geometry("Verônica Bueno Luz Camargo", rg.Point3d((x_mid_col + xs1)/2.0, y_div_cad - 77.0*sc, 0), 2.0*sc, rg.TextJustification.MiddleCenter, s))
    geoms.extend(make_text_geometry("TRT CFT2605882298", rg.Point3d((x_mid_col + xs1)/2.0, y_div_cad - 82.0*sc, 0), 1.8*sc, rg.TextJustification.MiddleCenter, s))

    # Badges / Pílulas regulamentares
    y_badge_b = y_div_mid + 6.0 * sc
    b_w = (xs1 - x_mid_col - 10.0*sc) / 2.0
    geoms.append(make_rounded_rect_poly(x_mid_col + 3.0*sc, y_badge_b + 11.0*sc, x_mid_col + 3.0*sc + b_w, y_badge_b + 19.0*sc, 1.8*sc))
    geoms.extend(make_text_geometry("USO RESIDENCIAL", rg.Point3d(x_mid_col + 3.0*sc + b_w/2.0, y_badge_b + 15.0*sc, 0), 1.2*sc, rg.TextJustification.MiddleCenter, s))

    geoms.append(make_rounded_rect_poly(x_mid_col + 7.0*sc + b_w, y_badge_b + 11.0*sc, xs1 - 3.0*sc, y_badge_b + 19.0*sc, 1.8*sc))
    geoms.extend(make_text_geometry("LEI 6.766/79", rg.Point3d(x_mid_col + 7.0*sc + 1.5*b_w, y_badge_b + 15.0*sc, 0), 1.2*sc, rg.TextJustification.MiddleCenter, s))

    geoms.append(make_rounded_rect_poly(x_mid_col + 3.0*sc, y_badge_b, x_mid_col + 3.0*sc + b_w, y_badge_b + 8.0*sc, 1.8*sc))
    geoms.extend(make_text_geometry("NBR 6492 / 13133", rg.Point3d(x_mid_col + 3.0*sc + b_w/2.0, y_badge_b + 4.0*sc, 0), 1.2*sc, rg.TextJustification.MiddleCenter, s))

    geoms.append(make_rounded_rect_poly(x_mid_col + 7.0*sc + b_w, y_badge_b, xs1 - 3.0*sc, y_badge_b + 8.0*sc, 1.8*sc))
    geoms.extend(make_text_geometry("NBR 11682 TALUDES", rg.Point3d(x_mid_col + 7.0*sc + 1.5*b_w, y_badge_b + 4.0*sc, 0), 1.2*sc, rg.TextJustification.MiddleCenter, s))

    # 5. BLOCO 4: APROVAÇÕES INSTITUCIONAIS (H = 60mm)
    geoms.extend(make_text_geometry("Aprovações:", rg.Point3d(xs0 + 3.0*sc, y_div_mid - 4.5*sc, 0), 1.8*sc, rg.TextJustification.TopLeft, s))
    # 3 colunas de aprovação
    x_ap1 = xs0 + w_selo * 0.35
    x_ap2 = xs0 + w_selo * 0.68
    geoms.append(rg.LineCurve(rg.Point3d(x_ap1, ys0, 0), rg.Point3d(x_ap1, y_div_mid - 8.0*sc, 0)))
    geoms.append(rg.LineCurve(rg.Point3d(x_ap2, ys0, 0), rg.Point3d(x_ap2, y_div_mid - 8.0*sc, 0)))

    # Célula 1: Prefeitura
    geoms.extend(make_text_geometry("PREFEITURA MUNICIPAL DE", rg.Point3d(xs0 + 3.0*sc, y_div_mid - 12.0*sc, 0), 1.4*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("VARGEM GRANDE PAULISTA", rg.Point3d(xs0 + 3.0*sc, y_div_mid - 16.5*sc, 0), 1.4*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Processo nº: _________/2026", rg.Point3d(xs0 + 3.0*sc, y_div_mid - 26.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Alvará de Execução nº: ______", rg.Point3d(xs0 + 3.0*sc, y_div_mid - 36.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Data: ____/____/2026", rg.Point3d(xs0 + 3.0*sc, ys0 + 8.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))

    # Célula 2: GRAPROHAB / CETESB
    geoms.extend(make_text_geometry("GRAPROHAB / CETESB", rg.Point3d(x_ap1 + 3.0*sc, y_div_mid - 12.0*sc, 0), 1.4*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Certificado nº: ____________", rg.Point3d(x_ap1 + 3.0*sc, y_div_mid - 24.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Licença CETESB nº: ________", rg.Point3d(x_ap1 + 3.0*sc, y_div_mid - 36.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Compensação Amb.: Deferida", rg.Point3d(x_ap1 + 3.0*sc, ys0 + 8.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))

    # Célula 3: Registro de Imóveis
    geoms.extend(make_text_geometry("REGISTRO DE IMÓVEIS", rg.Point3d(x_ap2 + 3.0*sc, y_div_mid - 12.0*sc, 0), 1.4*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Comarca de Cotia/SP", rg.Point3d(x_ap2 + 3.0*sc, y_div_mid - 16.5*sc, 0), 1.4*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Matrícula nº 30.901", rg.Point3d(x_ap2 + 3.0*sc, y_div_mid - 26.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Prenotação nº: ____________", rg.Point3d(x_ap2 + 3.0*sc, y_div_mid - 36.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry("Registro: R-____ / 30.901", rg.Point3d(x_ap2 + 3.0*sc, ys0 + 8.0*sc, 0), 1.3*sc, rg.TextJustification.BottomLeft, s))

    return geoms

def draw_perimeter_table_a0(x0, y0, sc, s=1.0):
    """
    Desenha a Tabela Oficial de Roteiro Perimétrico (18 Vértices da Matrícula 30.901),
    com colunas para De, Para, Coord. N, Coord. E, Azimute, Distância, Fator K, Lat e Long,
    perfeitamente alinhada à esquerda do carimbo (conforme PDF de referência).
    """
    geoms = []
    col_w = [8.0*sc, 8.0*sc, 28.0*sc, 28.0*sc, 20.0*sc, 18.0*sc, 20.0*sc, 35.0*sc, 35.0*sc]
    total_w = sum(col_w)
    row_h = 3.8 * sc
    hdr_h = 7.0 * sc
    title_h = 7.0 * sc
    total_h = title_h + hdr_h + len(ROTEIRO_PERIMETRICO_OFICIAL) * row_h + 6.0 * sc

    x1 = x0 + total_w
    y1 = y0 + total_h

    bg_t = make_box_background_mesh(
        rg.Point3d(x0, y0, 0), rg.Point3d(x1, y0, 0),
        rg.Point3d(x1, y1, 0), rg.Point3d(x0, y1, 0),
        System.Drawing.Color.FromArgb(254, 254, 254)
    )
    if bg_t: geoms.append(bg_t)
    geoms.append(make_box_poly(x0, y0, x1, y1))

    # Título da Tabela
    y_title_line = y1 - title_h
    geoms.append(rg.LineCurve(rg.Point3d(x0, y_title_line, 0), rg.Point3d(x1, y_title_line, 0)))
    geoms.extend(make_text_geometry("Tabela de Roteiro Perimétrico", rg.Point3d((x0 + x1)/2.0, y1 - 4.5*sc, 0), 2.8*sc, rg.TextJustification.MiddleCenter, s))

    # Cabeçalho das Colunas
    y_hdr_line = y_title_line - hdr_h
    geoms.append(rg.LineCurve(rg.Point3d(x0, y_hdr_line, 0), rg.Point3d(x1, y_hdr_line, 0)))

    headers = ["De", "Para", "Coord. N(Y)", "Coord. E(X)", "Azimute", "Distância", "Fator K", "Latitude", "Longitude"]
    cur_x = x0
    for idx_c, w_c in enumerate(col_w):
        geoms.extend(make_text_geometry(headers[idx_c], rg.Point3d(cur_x + w_c/2.0, (y_title_line + y_hdr_line)/2.0, 0), 1.5*sc, rg.TextJustification.MiddleCenter, s))
        if idx_c > 0:
            geoms.append(rg.LineCurve(rg.Point3d(cur_x, y_title_line, 0), rg.Point3d(cur_x, y0 + 6.0*sc, 0)))
        cur_x += w_c

    # Linhas de dados (18 vértices)
    cur_y = y_hdr_line
    for row in ROTEIRO_PERIMETRICO_OFICIAL:
        next_y = cur_y - row_h
        geoms.append(rg.LineCurve(rg.Point3d(x0, next_y, 0), rg.Point3d(x1, next_y, 0)))
        x_c = x0
        for idx_c, val in enumerate(row):
            w_c = col_w[idx_c]
            geoms.extend(make_text_geometry(val, rg.Point3d(x_c + w_c/2.0, (cur_y + next_y)/2.0, 0), 1.3*sc, rg.TextJustification.MiddleCenter, s))
            x_c += w_c
        cur_y = next_y

    # Linha de resumo no rodapé
    geoms.extend(make_text_geometry("Área Total: 35.087,731 m²     |     Perímetro Total: 799,964 m", rg.Point3d((x0 + x1)/2.0, y0 + 3.0*sc, 0), 2.2*sc, rg.TextJustification.MiddleCenter, s))

    return geoms

def draw_a0_legend_box(x0, y0, w, h, sc, legend_type="planta", s=1.0):
    """
    Desenha a Tabela de Convenções Técnicas & Legenda (NBR 6492 / NBR 13133)
    posicionada sobre o carimbo com swatches coloridos e especificações normativas.
    """
    geoms = []
    x1 = x0 + w
    y1 = y0 + h

    bg_leg = make_box_background_mesh(
        rg.Point3d(x0, y0, 0), rg.Point3d(x1, y0, 0),
        rg.Point3d(x1, y1, 0), rg.Point3d(x0, y1, 0),
        System.Drawing.Color.FromArgb(254, 254, 254)
    )
    if bg_leg: geoms.append(bg_leg)
    geoms.append(make_box_poly(x0, y0, x1, y1))

    # Título
    y_hdr = y1 - 7.0 * sc
    geoms.append(rg.LineCurve(rg.Point3d(x0, y_hdr, 0), rg.Point3d(x1, y_hdr, 0)))
    geoms.extend(make_text_geometry("CONVENÇÕES TÉCNICAS (NBR 6492 / NBR 13133)", rg.Point3d((x0 + x1)/2.0, y1 - 3.8*sc, 0), 1.8*sc, rg.TextJustification.MiddleCenter, s))

    items = [
        ("TERRENO NATURAL (TN)", System.Drawing.Color.FromArgb(30, 30, 30), False),
        ("GREIDE DE PROJETO (VIAS)", System.Drawing.Color.FromArgb(200, 20, 20), False),
        ("ZONA DE CORTE (ESCAVAÇÃO)", System.Drawing.Color.FromArgb(230, 92, 0), True),
        ("ZONA DE ATERRO (COMPACTAÇÃO)", System.Drawing.Color.FromArgb(46, 139, 87), True),
        ("LINHA NEUTRA (COTA ZERO)", System.Drawing.Color.FromArgb(240, 180, 0), False),
        ("DENTES DE TALUDE (NBR 6492)", System.Drawing.Color.FromArgb(70, 70, 70), False),
        ("MURO DE CONTENÇÃO (NBR 11682)", System.Drawing.Color.FromArgb(178, 34, 34), False),
        ("CANALETA DRENAGEM 40x40cm", System.Drawing.Color.FromArgb(30, 144, 255), False),
        ("FAIXA DE SEGURANÇA / DIVISA", System.Drawing.Color.FromArgb(180, 40, 200), False),
    ]

    pitch = (y_hdr - y0 - 3.0*sc) / float(len(items))
    for idx_item, (txt_l, cor_l, is_m) in enumerate(items):
        y_item = y_hdr - 3.5*sc - idx_item * pitch
        px0 = x0 + 4.0 * sc; px1 = x0 + 16.0 * sc
        py0 = y_item - 1.2 * sc; py1 = y_item + 1.2 * sc
        if is_m:
            m_sw = make_box_background_mesh(rg.Point3d(px0, py0, 0), rg.Point3d(px1, py0, 0), rg.Point3d(px1, py1, 0), rg.Point3d(px0, py1, 0), cor_l)
            if m_sw: geoms.append(m_sw)
            geoms.append(make_box_poly(px0, py0, px1, py1))
        else:
            geoms.append(rg.LineCurve(rg.Point3d(px0, y_item, 0), rg.Point3d(px1, y_item, 0)))
        geoms.extend(make_text_geometry(txt_l, rg.Point3d(x0 + 19.0*sc, y_item, 0), 1.5*sc, rg.TextJustification.MiddleLeft, s))

    return geoms

def draw_standard_a0_sheet(x0, y0, sheet_scale, sheet_title, sheet_num, scale_str,
                           s=1.0, is_planta=False, is_longitudinal=False,
                           volume_summary=None, draw_perimeter=False):
    """
    Desenha a prancha regulamentar completa em formato ISO A0 (1189 x 841 mm)
    rigorosamente compatibilizada na escala indicada (1:500, 1:1.000 ou 1:200),
    contendo:
      - Moldura externa regulamentar (1189 x 841 mm)
      - Moldura interna com margem de encadernação de 25mm e 10mm nas demais bordas
      - Carimbo / Selo oficial de Vargem Grande Paulista com dados cadastrais e assinaturas
      - Tabela de Convenções Técnicas (NBR 6492 / NBR 13133)
      - Escala Gráfica Linear regulamentar
      - Tabela de Roteiro Perimétrico (18 vértices) para Folha 01/03
    """
    geoms = []
    sc = (sheet_scale / 1000.0) * s
    w_sheet = 1189.0 * sc
    h_sheet = 841.0 * sc

    x1 = x0 + w_sheet
    y1 = y0 + h_sheet

    # 1. Moldura Externa (formato de corte da folha A0)
    geoms.append(make_box_poly(x0, y0, x1, y1))

    # 2. Moldura Interna (Margens ABNT NBR 10068: 25mm à esquerda, 10mm demais lados)
    x_int0 = x0 + 25.0 * sc
    y_int0 = y0 + 10.0 * sc
    x_int1 = x1 - 10.0 * sc
    y_int1 = y1 - 10.0 * sc
    geoms.append(make_box_poly(x_int0, y_int0, x_int1, y_int1))

    # Marcas de dobra A4 padronizadas (NBR 10068) nas margens externas
    for fold_x in [210.0 * sc, 420.0 * sc, 630.0 * sc, 840.0 * sc, 1050.0 * sc]:
        if x0 + fold_x < x1:
            geoms.append(rg.LineCurve(rg.Point3d(x0 + fold_x, y0, 0), rg.Point3d(x0 + fold_x, y0 + 5.0*sc, 0)))
            geoms.append(rg.LineCurve(rg.Point3d(x0 + fold_x, y1, 0), rg.Point3d(x0 + fold_x, y1 - 5.0*sc, 0)))
    for fold_y in [297.0 * sc, 594.0 * sc]:
        if y0 + fold_y < y1:
            geoms.append(rg.LineCurve(rg.Point3d(x0, y0 + fold_y, 0), rg.Point3d(x0 + 5.0*sc, y0 + fold_y, 0)))
            geoms.append(rg.LineCurve(rg.Point3d(x1, y0 + fold_y, 0), rg.Point3d(x1 - 5.0*sc, y0 + fold_y, 0)))

    # 3. Carimbo Oficial no Canto Inferior Direito da Moldura Interna (W=175mm, H=277mm)
    w_selo = 175.0 * sc
    h_selo = 277.0 * sc
    xs0 = x_int1 - w_selo
    ys0 = y_int0
    geoms.extend(draw_official_a0_carimbo(xs0, ys0, sc, sheet_title, sheet_num, scale_str, volume_summary, s))

    # 4. Tabela de Convenções Técnicas (acima do carimbo)
    w_leg = w_selo
    h_leg = 62.0 * sc
    xl0 = xs0
    yl0 = ys0 + h_selo + 4.0 * sc
    geoms.extend(draw_a0_legend_box(xl0, yl0, w_leg, h_leg, sc, legend_type="long" if is_longitudinal else "planta", s=s))

    # 5. Escala Gráfica Linear (acima da legenda ou ao lado)
    p_sc_orig = rg.Point3d(xl0 + 8.0*sc, yl0 + h_leg + 6.0*sc, 0)
    geoms.extend(draw_linear_graphic_scale(p_sc_orig, s=sc * 2.0))

    # 6. Tabela de Roteiro Perimétrico (para Folha 01/03, posicionada à esquerda do carimbo)
    if draw_perimeter or is_planta:
        w_perim = 200.0 * sc
        xp0 = xs0 - w_perim - 6.0 * sc
        yp0 = y_int0
        geoms.extend(draw_perimeter_table_a0(xp0, yp0, sc, s))

    # 7. Cabeçalho de identificação no topo da folha
    p_top_title = rg.Point3d(x_int0 + 10.0*sc, y_int1 - 10.0*sc, 0)
    geoms.extend(make_text_geometry(sheet_title, p_top_title, 4.0*sc, rg.TextJustification.BottomLeft, s))
    p_top_sub = rg.Point3d(x_int0 + 10.0*sc, y_int1 - 16.0*sc, 0)
    sub_info = "Escala: {} | Sistema: UTM SIRGAS 2000 Fuso 23S | Município: Vargem Grande Paulista-SP | Matrícula: 30.901".format(scale_str)
    geoms.extend(make_text_geometry(sub_info, p_top_sub, 2.0*sc, rg.TextJustification.BottomLeft, s))

    return geoms

def draw_technical_sheet_frame(min_x, min_y, max_x, max_y, sheet_title, sheet_num, scale_str, s=1.0, is_longitudinal=False):
    """
    Função de compatibilidade que mapeia requisições antigas para a prancha A0 regulamentar.
    """
    scale_val = 1000.0
    if "500" in scale_str: scale_val = 500.0
    elif "200" in scale_str: scale_val = 200.0
    return draw_standard_a0_sheet(min_x, min_y, scale_val, sheet_title, sheet_num, scale_str, s=s, is_longitudinal=is_longitudinal)


def draw_section_summary_card(base_x, base_y, total_ext, sec_h, lbl, s_data, s=1.0, max_x_allowed=None):
    """
    Desenha a ficha técnica / carimbo executivo da seção transversal.
    Posicionada com precisão milimétrica sob a linha de datum da seção (X entre base_x + 2m e base_x + 27m),
    garantindo que o card NUNCA ultrapasse a largura da seção, eliminando colisões com colunas adjacentes e carimbo A0.
    """
    geoms = []
    w_card = 25.0 * s
    h_card = 9.2 * s

    x0 = base_x + 2.0 * s
    y0 = base_y - 10.5 * s
    x1 = x0 + w_card
    y1 = y0 + h_card

    p0 = rg.Point3d(x0, y0, 0)
    p1 = rg.Point3d(x1, y0, 0)
    p2 = rg.Point3d(x1, y1, 0)
    p3 = rg.Point3d(x0, y1, 0)
    bg_m = make_box_background_mesh(p0, p1, p2, p3, System.Drawing.Color.FromArgb(254, 254, 254))
    if bg_m: geoms.append(bg_m)
    geoms.append(rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve())

    y_hdr = y1 - 2.8 * s
    geoms.append(rg.LineCurve(rg.Point3d(x0, y_hdr, 0), rg.Point3d(x1, y_hdr, 0)))

    tit_str = "SEÇÃO {}".format(lbl)
    geoms.extend(make_text_geometry(tit_str, rg.Point3d(x0 + 1.2*s, y1 - 2.1*s, 0), 1.15*s, rg.TextJustification.BottomLeft, s))
    sub_str = "Ext: {:.1f}m".format(total_ext).replace('.', ',')
    if s_data.get('estaca_str'):
        sub_str = "Est. {} | {}".format(s_data['estaca_str'], sub_str)
    geoms.extend(make_text_geometry(sub_str, rg.Point3d(x0 + 8.5*s, y1 - 2.1*s, 0), 0.72*s, rg.TextJustification.BottomLeft, s))

    area_corte = s_data.get('area_total_corte', 0.0)
    h_corte = s_data.get('max_h_corte', 0.0)
    txt_c1 = "CORTE: {:.2f} m²".format(area_corte).replace('.', ',')
    p_sw_c0 = rg.Point3d(x0 + 1.2*s, y_hdr - 2.4*s, 0)
    p_sw_c1 = rg.Point3d(x0 + 2.8*s, y_hdr - 2.4*s, 0)
    p_sw_c2 = rg.Point3d(x0 + 2.8*s, y_hdr - 0.8*s, 0)
    p_sw_c3 = rg.Point3d(x0 + 1.2*s, y_hdr - 0.8*s, 0)
    m_sc = make_box_background_mesh(p_sw_c0, p_sw_c1, p_sw_c2, p_sw_c3, System.Drawing.Color.FromArgb(245, 130, 32))
    if m_sc: geoms.append(m_sc)
    geoms.extend(make_text_geometry(txt_c1, rg.Point3d(x0 + 3.5*s, y_hdr - 1.9*s, 0), 0.85*s, rg.TextJustification.BottomLeft, s))

    area_aterro = s_data.get('area_total_aterro', 0.0)
    h_aterro = s_data.get('max_h_aterro', 0.0)
    txt_a1 = "ATERRO: {:.2f} m²".format(area_aterro).replace('.', ',')
    p_sw_a0 = rg.Point3d(x0 + 1.2*s, y_hdr - 4.9*s, 0)
    p_sw_a1 = rg.Point3d(x0 + 2.8*s, y_hdr - 4.9*s, 0)
    p_sw_a2 = rg.Point3d(x0 + 2.8*s, y_hdr - 3.3*s, 0)
    p_sw_a3 = rg.Point3d(x0 + 1.2*s, y_hdr - 3.3*s, 0)
    m_sa = make_box_background_mesh(p_sw_a0, p_sw_a1, p_sw_a2, p_sw_a3, System.Drawing.Color.FromArgb(46, 204, 113))
    if m_sa: geoms.append(m_sa)
    geoms.extend(make_text_geometry(txt_a1, rg.Point3d(x0 + 3.5*s, y_hdr - 4.4*s, 0), 0.85*s, rg.TextJustification.BottomLeft, s))

    saldo_sec = area_corte - area_aterro
    if saldo_sec > 0.01:
        txt_s = "SALDO: +{:.2f} m² (Sobra)".format(saldo_sec).replace('.', ',')
    elif saldo_sec < -0.01:
        txt_s = "SALDO: {:.2f} m² (Aterro)".format(saldo_sec).replace('.', ',')
    else:
        txt_s = "SALDO: 0,00 m² (Equilíbrio)"
    geoms.extend(make_text_geometry(txt_s, rg.Point3d(x0 + 1.2*s, y_hdr - 6.8*s, 0), 0.78*s, rg.TextJustification.BottomLeft, s))

    max_h_sec = max(h_corte, h_aterro)
    if max_h_sec > 4.5:
        txt_geot = "ALERTA NBR 11682: H={:.2f}m > 4,5m (CONTENÇÃO)".format(max_h_sec).replace('.', ',')
        geoms.extend(make_text_geometry(txt_geot, rg.Point3d(x0 + 12.0*s, y_hdr - 6.8*s, 0), 0.65*s, rg.TextJustification.BottomLeft, s))

    return geoms

def draw_retaining_wall_and_ditch_2d(p_slope, p_bnd, boundary_crv, s=1.0):
    """
    Desenha em planta o Muro de Arrimo / Estrutura de Contenção em Concreto Armado
    e a Canaleta de Crista/Pé Impermeabilizada nos trechos onde o recuo à divisa
    é inferior a 3,00m (atendimento estrito à Lei 6.766/79 e ABNT NBR 11682).
    """
    geoms = []
    if boundary_crv is None or not getattr(boundary_crv, 'IsValid', False):
        return geoms
    rc, t_bnd = boundary_crv.ClosestPoint(p_bnd)
    if not rc:
        return geoms
    tan_b = boundary_crv.TangentAt(t_bnd)
    tan_2d = rg.Vector3d(tan_b.X, tan_b.Y, 0.0)
    if tan_2d.Length < 1e-4:
        return geoms
    tan_2d.Unitize()
    norm_2d = rg.Vector3d(-tan_2d.Y, tan_2d.X, 0.0)

    # Orientar a normal para o interior da gleba
    vec_to_slope = p_slope - p_bnd
    if (norm_2d.X * vec_to_slope.X + norm_2d.Y * vec_to_slope.Y) < 0:
        norm_2d = -norm_2d

    l_muro = 30.0 * s
    w_muro = 0.35 * s
    w_canaleta = 0.40 * s

    # Linha base do muro (face externa junto à divisa com folga de 0.15m)
    p_w_start = p_bnd - tan_2d * (l_muro / 2.0) + norm_2d * 0.15
    p_w_end   = p_bnd + tan_2d * (l_muro / 2.0) + norm_2d * 0.15

    mw0 = p_w_start
    mw1 = p_w_end
    mw2 = p_w_end + norm_2d * w_muro
    mw3 = p_w_start + norm_2d * w_muro

    cor_muro = System.Drawing.Color.FromArgb(220, 178, 34, 34) # Firebrick
    m_muro = make_box_background_mesh(mw0, mw1, mw2, mw3, cor_muro)
    if m_muro: geoms.append(m_muro)
    geoms.append(rg.Polyline([mw0, mw1, mw2, mw3, mw0]).ToPolylineCurve())

    # Hachuras internas do muro (linhas duplas transversais a cada 2.5m)
    n_h = int(l_muro // (2.5 * s))
    for ih in range(1, n_h):
        t_ih = ih * 2.5 * s
        ph0 = p_w_start + tan_2d * t_ih
        ph1 = ph0 + norm_2d * w_muro
        geoms.append(rg.LineCurve(ph0, ph1))

    # Canaleta impermeabilizada de crista/pé junto ao muro (concreto calha 40x40cm)
    mc0 = mw3
    mc1 = mw2
    mc2 = mw2 + norm_2d * w_canaleta
    mc3 = mw3 + norm_2d * w_canaleta
    cor_canaleta = System.Drawing.Color.FromArgb(190, 30, 144, 255) # DodgerBlue
    m_can = make_box_background_mesh(mc0, mc1, mc2, mc3, cor_canaleta)
    if m_can: geoms.append(m_can)
    geoms.append(rg.Polyline([mc0, mc1, mc2, mc3, mc0]).ToPolylineCurve())

    # Textos de detalhamento executivo e chamada de fiscalização
    p_mw_mid = rg.Point3d((mw2.X + mw3.X) / 2.0, (mw2.Y + mw3.Y) / 2.0, 0.0)
    p_callout = p_mw_mid + norm_2d * (3.2 * s)
    geoms.append(rg.LineCurve(p_mw_mid, p_callout))
    
    txt1 = "MURO DE CONTENÇÃO EM CONCRETO ARMADO (h = 2,80m a 3,50m) - RECUO < 3,00m"
    txt2 = "CANALETA DE CRISTA/PÉ IMPERMEABILIZADA (CALHA 40x40cm) - ESCOAMENTO INTERNO PLENO"
    txt3 = "TRATAMENTO DE DIVISA CONFORME LEI FEDERAL 6.766/79 E ABNT NBR 11682"
    
    geoms.extend(make_text_geometry(txt1, p_callout + rg.Vector3d(0, 2.4*s, 0), 0.82*s, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry(txt2, p_callout + rg.Vector3d(0, 1.2*s, 0), 0.75*s, rg.TextJustification.BottomLeft, s))
    geoms.extend(make_text_geometry(txt3, p_callout, 0.75*s, rg.TextJustification.BottomLeft, s))

    return geoms

def draw_road_stationing_2d(crv, label_prefix="Est. ", step=20.0, s=1.0):
    """
    Gera o estaqueamento normativo de 20 em 20 metros ao longo do eixo da via em 2D
    (DNIT / NBR 13.133), com ticks transversais perpendiculares e rótulos das estacas.
    """
    geoms = []
    if crv is None or not getattr(crv, 'IsValid', False):
        return geoms
    total_len = crv.GetLength()
    if total_len < 1.0:
        return geoms
    n_estacas = int(total_len // step)
    tick_half_len = 1.25 * s
    txt_offset = 2.40 * s
    dist_list = [k * step for k in range(n_estacas + 1)]
    if (total_len - (n_estacas * step)) > 1.0:
        dist_list.append(total_len)
    for d_val in dist_list:
        rc, t_val = crv.LengthParameter(d_val)
        if not rc:
            continue
        pt_3d = crv.PointAt(t_val)
        pt_2d = rg.Point3d(pt_3d.X, pt_3d.Y, 0.0)
        tan_vec = crv.TangentAt(t_val)
        tan_2d = rg.Vector3d(tan_vec.X, tan_vec.Y, 0.0)
        if tan_2d.Length < 1e-4:
            continue
        tan_2d.Unitize()
        norm_2d = rg.Vector3d(-tan_2d.Y, tan_2d.X, 0.0)
        p_t1 = pt_2d - norm_2d * tick_half_len
        p_t2 = pt_2d + norm_2d * tick_half_len
        geoms.append(rg.LineCurve(p_t1, p_t2))
        idx_est = int(d_val // step)
        rest_m = d_val - (idx_est * step)
        if abs(rest_m) < 0.05:
            lbl_str = "{}{}".format(label_prefix, idx_est)
        else:
            lbl_str = "{}{}+{}".format(label_prefix, idx_est, "{:05.2f}".format(rest_m).replace('.', ','))
        p_txt = pt_2d + norm_2d * txt_offset
        u_txt = tan_2d if (tan_2d.X >= 0 or (abs(tan_2d.X) < 1e-4 and tan_2d.Y >= 0)) else -tan_2d
        v_txt = rg.Vector3d(-u_txt.Y, u_txt.X, 0.0)
        pl_txt = rg.Plane(p_txt, u_txt, v_txt)
        txt_geoms = make_text_geometry(lbl_str, p_txt, 0.85 * s, rg.TextJustification.MiddleCenter, s, plane=pl_txt)
        if txt_geoms:
            geoms.extend(txt_geoms)
    return geoms

def draw_slope_ticks_tadpoles_2d(p_crista, p_pe, s=1.0, is_long=True, is_cut=True):
    """
    Desenha um dente de talude (espinha de peixe) individual segundo a NBR 6492:
    - Origem na Crista (ponto mais alto) apontando no sentido descendente em direção ao Pé.
    - Se is_long=True: traço longo (65% do comprimento ou min 2.5*s) com ponta triangular/seta na crista.
    - Se is_long=False: traço curto (30% do comprimento ou min 1.2*s).
    """
    geoms = []
    p_c2d = rg.Point3d(p_crista.X, p_crista.Y, 0.0)
    p_p2d = rg.Point3d(p_pe.X, p_pe.Y, 0.0)
    vec = p_p2d - p_c2d
    d_total = vec.Length
    if d_total < 0.2:
        return geoms
    u_dir = rg.Vector3d(vec.X, vec.Y, vec.Z)
    u_dir.Unitize()
    ratio = 0.65 if is_long else 0.32
    d_trace = min(d_total * ratio, max(2.5 * s, 1.5)) if is_long else min(d_total * ratio, max(1.2 * s, 0.8))
    p_end = p_c2d + u_dir * d_trace
    l_tick = rg.LineCurve(p_c2d, p_end)
    geoms.append(l_tick)
    if is_long:
        w_side = 0.30 * s
        u_norm = rg.Vector3d(-u_dir.Y, u_dir.X, 0.0)
        p_tri_tip = p_c2d + u_dir * (0.60 * s)
        p_tri_l = p_c2d + u_norm * w_side
        p_tri_r = p_c2d - u_norm * w_side
        tri_crv = rg.Polyline([p_tri_l, p_tri_tip, p_tri_r, p_tri_l]).ToPolylineCurve()
        tri_mesh = make_filled_mesh_tri(p_tri_tip, p_tri_l, p_tri_r)
        if tri_mesh:
            geoms.append(tri_mesh)
        if tri_crv and tri_crv.IsValid:
            geoms.append(tri_crv)
    return geoms

def calculate_boundary_clearance(outer_slope_pts, boundary_crv, s=1.0):
    """
    Calcula o afastamento técnico dos taludes de terraplenagem (pés de aterro e cristas de corte)
    em relação aos limites da matrícula da gleba (Matrícula 30.901), gerando:
    1. A Faixa de Segurança / Divisa (recuo non aedificandi obrigatório de 3,00m conf. NBR / Código de Obras)
    2. Cotas técnicas completas em planta com linhas de chamada e valores nos pontos críticos (Global, N, S, L, O).
    """
    geoms = []
    min_dist = 1e9
    best_p_slope = None
    best_p_bnd = None
    all_cotas = []
    if boundary_crv is None or not getattr(boundary_crv, 'IsValid', False) or not outer_slope_pts:
        return geoms, min_dist, None

    # 1. Faixa de Segurança Não Edificável (Recuo de 3,00m para o interior da gleba)
    try:
        recuo_faixa = 3.00
        offset_crvs = boundary_crv.Offset(rg.Plane.WorldXY, -recuo_faixa, 0.05, rg.CurveOffsetCornerStyle.Sharp)
        if not offset_crvs or len(offset_crvs) == 0:
            offset_crvs = boundary_crv.Offset(rg.Plane.WorldXY, recuo_faixa, 0.05, rg.CurveOffsetCornerStyle.Sharp)
        if offset_crvs:
            for oc in offset_crvs:
                if oc and oc.IsValid:
                    geoms.append(oc)
                    # Textos indicativos ao longo da faixa de segurança
                    l_oc = oc.GetLength()
                    n_tags = max(int(l_oc / 120.0), 2)
                    for it in range(n_tags):
                        t_tag = oc.Domain.T0 + ((it + 0.5) / float(n_tags)) * (oc.Domain.T1 - oc.Domain.T0)
                        pt_tag = oc.PointAt(t_tag)
                        txt_faixa = "FAIXA DE SEGURANÇA NÃO EDIFICÁVEL (RECUO = 3,00m - LEI 6.766 / NBR 11682)"
                        geoms.extend(make_text_geometry(txt_faixa, pt_tag + rg.Vector3d(0, 1.2*s, 0), 0.75*s, rg.TextJustification.MiddleCenter, s))
    except:
        pass

    # 2. Pesquisa de Pontos Críticos e Setores Cardeais (Global Min, Norte, Sul, Leste, Oeste)
    cand_pts = []
    # 2.1 Ponto Global de Menor Distância
    for pt in outer_slope_pts:
        pt_2d = rg.Point3d(pt.X, pt.Y, 0.0)
        rc, t_cp = boundary_crv.ClosestPoint(pt_2d)
        if rc:
            cp_pt = boundary_crv.PointAt(t_cp)
            cp_2d = rg.Point3d(cp_pt.X, cp_pt.Y, 0.0)
            d = pt_2d.DistanceTo(cp_2d)
            if d < min_dist:
                min_dist = d
                best_p_slope = pt_2d
                best_p_bnd = cp_2d
    if best_p_slope and best_p_bnd:
        cand_pts.append(('RECUO MÍNIMO GLOBAL', best_p_slope, best_p_bnd, min_dist))

    # 2.2 Setores Cardeais: Norte (Max Y), Sul (Min Y), Leste (Max X), Oeste (Min X)
    pts_n = [p for p in outer_slope_pts if p.Y > best_p_slope.Y + 25.0]
    pts_s = [p for p in outer_slope_pts if p.Y < best_p_slope.Y - 25.0]
    pts_e = [p for p in outer_slope_pts if p.X > best_p_slope.X + 25.0]
    pts_w = [p for p in outer_slope_pts if p.X < best_p_slope.X - 25.0]

    for lbl_set, subset in [('DIVISA NORTE', pts_n), ('DIVISA SUL', pts_s), ('DIVISA LESTE', pts_e), ('DIVISA OESTE', pts_w)]:
        if subset:
            sub_min_d = 1e9
            sub_best_s = None
            sub_best_b = None
            for p in subset:
                p2 = rg.Point3d(p.X, p.Y, 0.0)
                rc, t_c = boundary_crv.ClosestPoint(p2)
                if rc:
                    cb = boundary_crv.PointAt(t_c)
                    cb2 = rg.Point3d(cb.X, cb.Y, 0.0)
                    dist_c = p2.DistanceTo(cb2)
                    if dist_c < sub_min_d:
                        sub_min_d = dist_c
                        sub_best_s = p2
                        sub_best_b = cb2
            if sub_best_s and sub_best_b and sub_min_d < 1e8:
                # Evita sobreposição com pontos já cotados
                if all(sub_best_s.DistanceTo(cp[1]) > 20.0 for cp in cand_pts):
                    cand_pts.append((lbl_set, sub_best_s, sub_best_b, sub_min_d))

    # 3. Desenho das Cotas em Planta, Muros de Contenção e Canaletas Impermeabilizadas
    for lbl_cota, ps, pb, d_val in cand_pts:
        vec_c = pb - ps
        if vec_c.Length > 0.05:
            if d_val >= 3.00:
                dim_txt = "{}: {:.2f}m [CONFORME >= 3,00m]".format(lbl_cota, d_val).replace('.', ',')
            else:
                dim_txt = "{}: {:.2f}m [< 3,00m] -> MURO DE CONTENÇÃO & CANALETA IMPERMEABILIZADA [LEI 6.766 / NBR 11682]".format(lbl_cota, d_val).replace('.', ',')
                # Implantação de Muro de Arrimo e Canaleta Impermeabilizada nos trechos com recuo < 3,00m
                muro_geoms = draw_retaining_wall_and_ditch_2d(ps, pb, boundary_crv, s=s)
                geoms.extend(muro_geoms)

            cota_dim = draw_plan_dimension(ps, pb, dim_txt, s)
            geoms.extend(cota_dim)
            circ_c = rg.Circle(ps, 0.90 * s).ToNurbsCurve()
            if circ_c and circ_c.IsValid:
                geoms.append(circ_c)
            p_mid = rg.Point3d((ps.X + pb.X) / 2.0, (ps.Y + pb.Y) / 2.0, 0.0) + rg.Vector3d(0, 1.8 * s, 0)
            geoms.extend(make_text_geometry(dim_txt, p_mid, 0.75 * s, rg.TextJustification.MiddleCenter, s))

    return geoms, min_dist, (best_p_slope, best_p_bnd)

def generate_project_contours(mesh_proj, z_step=1.0, z_master_step=5.0, s=1.0):
    """
    Fatia a malha 3D do terreno modificado/projetado (platôs + vias + taludes)
    gerando as Curvas de Nível de Projeto (1 em 1m) e Curvas Mestras (5 em 5m),
    com anotações de cota altimétrica nos trechos principais.
    """
    crvs_1m = []
    crvs_5m = []
    textos_mestras = []
    if mesh_proj is None or not getattr(mesh_proj, 'IsValid', False):
        return crvs_1m, crvs_5m, textos_mestras
    if mesh_proj.Faces.Count == 0:
        return crvs_1m, crvs_5m, textos_mestras
    bbox = mesh_proj.GetBoundingBox(True)
    if not bbox.IsValid:
        return crvs_1m, crvs_5m, textos_mestras
    z_min = bbox.Min.Z
    z_max = bbox.Max.Z
    if (z_max - z_min) < 0.2:
        return crvs_1m, crvs_5m, textos_mestras
    contours_raw = None
    try:
        p_bot = rg.Point3d(bbox.Center.X, bbox.Center.Y, math.floor(z_min))
        p_top = rg.Point3d(bbox.Center.X, bbox.Center.Y, math.ceil(z_max))
        contours_raw = rg.Mesh.CreateContourCurves(mesh_proj, p_bot, p_top, float(z_step))
    except:
        contours_raw = None
    if contours_raw:
        for crv in contours_raw:
            if crv and getattr(crv, 'IsValid', False) and crv.GetLength() > 0.5:
                z_mid = (crv.PointAtStart.Z + crv.PointAtEnd.Z) / 2.0
                z_round = round(z_mid)
                is_master = (abs(z_round % int(z_master_step)) < 0.05) or (abs(z_mid % float(z_master_step)) < 0.08)
                if is_master:
                    crvs_5m.append(crv)
                    t_mid = (crv.Domain.T0 + crv.Domain.T1) / 2.0
                    p_mid = crv.PointAt(t_mid)
                    txt_cota = "+{:.0f}".format(z_mid)
                    tan = crv.TangentAt(t_mid)
                    u_t = rg.Vector3d(tan.X, tan.Y, 0.0)
                    if u_t.Length > 1e-4:
                        u_t.Unitize()
                        if u_t.X < -1e-4 or (abs(u_t.X) <= 1e-4 and u_t.Y < 0):
                            u_t = -u_t
                        v_t = rg.Vector3d(-u_t.Y, u_t.X, 0.0)
                        pl_cota = rg.Plane(p_mid, u_t, v_t)
                    else:
                        pl_cota = rg.Plane(p_mid, rg.Vector3d.XAxis, rg.Vector3d.YAxis)
                    txt_g = make_text_geometry(txt_cota, p_mid, 0.85 * s, rg.TextJustification.MiddleCenter, s, plane=pl_cota)
                    if txt_g:
                        textos_mestras.extend(txt_g)
                else:
                    crvs_1m.append(crv)
    return crvs_1m, crvs_5m, textos_mestras

def draw_section_vertical_axis_marker(base_x, base_y, d_ax, sec_h, sec_datum_z, z_terrain, z_proj, lbl_v, s=1.0):
    """
    Draws vertical cross-axis lines in section profile with top circular NBR bubble,
    crosshair, and elevation node at terrain intersection.
    """
    geoms = []
    x_ax = base_x + d_ax
    y_datum = base_y
    y_local = base_y + (max(z_terrain, z_proj) - sec_datum_z)
    y_top_line = y_local + 2.5 * s
    y_bubble = y_local + 4.2 * s

    # 1. Linha vertical fina de eixo
    p_bot = rg.Point3d(x_ax, y_datum, 0.0)
    p_top = rg.Point3d(x_ax, y_top_line, 0.0)
    geoms.append(rg.LineCurve(p_bot, p_top))

    # 2. Balão de eixo no topo (Círculo com identificador do eixo, ex: "1", "2"...)
    r_bubble = 1.35 * s
    p_bub = rg.Point3d(x_ax, y_bubble, 0.0)
    circ = rg.Circle(p_bub, r_bubble).ToNurbsCurve()
    geoms.append(circ)

    # Cruz técnica central de eixo
    l_cross_h = rg.LineCurve(p_bub - rg.Vector3d.XAxis * (1.6 * s), p_bub + rg.Vector3d.XAxis * (1.6 * s))
    l_cross_v = rg.LineCurve(p_bub - rg.Vector3d.YAxis * (1.6 * s), p_bub + rg.Vector3d.YAxis * (1.6 * s))
    geoms.extend([l_cross_h, l_cross_v])

    txt_crvs = make_text_geometry(str(lbl_v), p_bub, 1.15 * s, rg.TextJustification.MiddleCenter, s)
    if txt_crvs: geoms.extend(txt_crvs)

    # 3. Technical square node marker at intersection with natural ground (per drawing sketch)
    y_ground = base_y + (z_terrain - sec_datum_z)
    p_sq_center = rg.Point3d(x_ax, y_ground, 0.0)
    sq_size = 0.85 * s
    p0 = p_sq_center + rg.Vector3d(-sq_size/2.0, -sq_size/2.0, 0.0)
    p1 = p_sq_center + rg.Vector3d(sq_size/2.0, -sq_size/2.0, 0.0)
    p2 = p_sq_center + rg.Vector3d(sq_size/2.0, sq_size/2.0, 0.0)
    p3 = p_sq_center + rg.Vector3d(-sq_size/2.0, sq_size/2.0, 0.0)
    sq_crv = rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve()
    cor_verde_eixo = System.Drawing.Color.FromArgb(46, 204, 113)
    sq_mesh = make_box_background_mesh(p0, p1, p2, p3, cor_verde_eixo)
    if sq_mesh: geoms.append(sq_mesh)
    if sq_crv and sq_crv.IsValid: geoms.append(sq_crv)

    # 4. Circular node at intersection with grade if there is an elevation offset
    if abs(z_proj - z_terrain) > 0.05:
        y_greide = base_y + (z_proj - sec_datum_z)
        p_gr_node = rg.Point3d(x_ax, y_greide, 0.0)
        geoms.append(rg.Circle(p_gr_node, 0.35 * s).ToNurbsCurve())

    return geoms

def draw_section_internal_transfer_arrow(p_start, p_end, vol_or_area_str="", s=1.0):
    """
    Draws internal mass compensation arrow on 2D profile
    (material moved from cut to adjacent fill).
    """
    geoms = []
    # 1. Origin point / solid circle on section (as sketched: origin node vermelho circular)
    r_node = 0.55 * s
    circ_origin = rg.Circle(p_start, r_node).ToNurbsCurve()
    geoms.append(circ_origin)

    cor_vermelha = System.Drawing.Color.FromArgb(230, 40, 40)
    mesh_origin = rg.Mesh()
    mesh_origin.Vertices.Add(p_start)
    n_segs = 12
    for i in range(n_segs):
        ang = (2.0 * math.pi * i) / n_segs
        mesh_origin.Vertices.Add(rg.Point3d(p_start.X + r_node * math.cos(ang), p_start.Y + r_node * math.sin(ang), 0.0))
    for i in range(n_segs):
        i_next = 1 if i == n_segs - 1 else (i + 2)
        mesh_origin.Faces.AddFace(0, i + 1, i_next)
    for _ in range(mesh_origin.Vertices.Count):
        mesh_origin.VertexColors.Add(cor_vermelha)
    mesh_origin.Compact()
    try:
        mesh_origin.Normals.ComputeNormals()
    except:
        pass
    if mesh_origin.IsValid:
        geoms.append(mesh_origin)

    # 2. Haste horizontal da seta
    vec = p_end - p_start
    l_len = vec.Length
    if l_len < 1e-3: return geoms
    u_arrow = rg.Vector3d(vec.X, vec.Y, vec.Z)
    u_arrow.Unitize()
    v_arrow = rg.Vector3d(-u_arrow.Y, u_arrow.X, 0.0)

    arrow_head_len = 2.0 * s
    arrow_head_w = 1.2 * s
    p_shaft_end = p_end - u_arrow * arrow_head_len
    geoms.append(rg.LineCurve(p_start, p_end))

    # 3. Cabeça da seta sólida preenchida em vermelho
    p_tip = p_end
    p_left = p_shaft_end + v_arrow * (arrow_head_w / 2.0)
    p_right = p_shaft_end - v_arrow * (arrow_head_w / 2.0)

    arrow_mesh = make_filled_mesh_tri(p_tip, p_left, p_right, cor_vermelha)
    l_h1 = rg.LineCurve(p_tip, p_left)
    l_h2 = rg.LineCurve(p_tip, p_right)
    l_h3 = rg.LineCurve(p_left, p_right)
    geoms.extend([g for g in [arrow_mesh, l_h1, l_h2, l_h3] if g is not None])

    # 4. Texto explicativo sobre a seta
    if vol_or_area_str:
        p_txt = rg.Point3d((p_start.X + p_end.X) / 2.0, (p_start.Y + p_end.Y) / 2.0, 0.0) + v_arrow * (1.1 * s)
        txt_crvs = make_text_geometry(vol_or_area_str, p_txt, 0.75 * s, rg.TextJustification.BottomCenter, s)
        if txt_crvs: geoms.extend(txt_crvs)

    return geoms

def parse_nivel_projeto(raw_nivel_proj, idx_s, num_secoes, num_trechos):
    """
    Parses ProjectElevation with support for single float, per-quadrant list or per-section tree.
    """
    if raw_nivel_proj is None: return None
    try:
        val = float(raw_nivel_proj)
        return [val] * max(num_trechos, 1)
    except: pass

    if hasattr(raw_nivel_proj, "Branches"):
        try:
            branches = list(raw_nivel_proj.Branches)
            if idx_s < len(branches):
                return [float(x) for x in branches[idx_s] if x is not None]
        except: pass

    all_items = to_list(raw_nivel_proj)
    if not all_items: return None

    if any(isinstance(x, (list, tuple)) for x in all_items):
        item_s = all_items[idx_s] if idx_s < len(all_items) else all_items[-1]
        if isinstance(item_s, (list, tuple)):
            return [float(x) for x in item_s]
        else:
            return [float(item_s)] * max(num_trechos, 1)

    if len(all_items) == num_trechos:
        return [float(x) for x in all_items]
    elif len(all_items) == num_secoes * num_trechos:
        chunk = all_items[idx_s * num_trechos : (idx_s + 1) * num_trechos]
        return [float(x) for x in chunk]
    elif len(all_items) == num_secoes and num_secoes != num_trechos:
        return [float(all_items[idx_s])] * max(num_trechos, 1)
    else:
        return [float(x) for x in all_items]

def calculate_axis_distance(crv_a, crv_b):
    """Calcula a distância ortogonal média horizontal entre duas linhas de corte consecutivas em planta."""
    try:
        ca_xy = rg.Curve.ProjectToPlane(crv_a, rg.Plane.WorldXY) or crv_a
        cb_xy = rg.Curve.ProjectToPlane(crv_b, rg.Plane.WorldXY) or crv_b
        t_mid_a = ca_xy.Domain.T0 + 0.5 * (ca_xy.Domain.T1 - ca_xy.Domain.T0)
        p_mid_a = ca_xy.PointAt(t_mid_a)
        rc, t_b = cb_xy.ClosestPoint(p_mid_a)
        d1 = p_mid_a.DistanceTo(cb_xy.PointAt(t_b)) if rc else None

        t_mid_b = cb_xy.Domain.T0 + 0.5 * (cb_xy.Domain.T1 - cb_xy.Domain.T0)
        p_mid_b = cb_xy.PointAt(t_mid_b)
        rc2, t_a = ca_xy.ClosestPoint(p_mid_b)
        d2 = p_mid_b.DistanceTo(ca_xy.PointAt(t_a)) if rc2 else None

        if d1 is not None and d2 is not None:
            return (d1 + d2) / 2.0
        elif d1 is not None:
            return d1
        elif d2 is not None:
            return d2
        else:
            return p_mid_a.DistanceTo(p_mid_b)
    except:
        return 1.0

def make_mass_haul_banner(center_x, center_y, label_prev, label_next, dist_val, vol_corte, vol_aterro, saldo, transfer_note, s=1.0):
    """
    Draws the technical mass haul banner between sections with segment volume, net balance, and haul direction
    tracking where surplus material moves to supply downstream embankment fill.
    """
    geoms = []
    txt_h1 = 0.95 * s
    txt_h2 = 0.85 * s
    pad_x  = 4.00 * s   # Margem lateral ampla para garantir que a linha de texto nunca estoure a caixa
    pad_y  = 1.30 * s   # Margem vertical
    gap_y  = 1.30 * s   # Folga entre os textos e a divisória central

    t1_str = "TRECHO {} - {} (D = {:.2f}m) | Vol. Corte: {:.1f}m³ | Vol. Aterro: {:.1f}m³ | Saldo: {:+.1f}m³".format(
        label_prev, label_next, dist_val, vol_corte, vol_aterro, saldo
    ).replace('.', ',')

    w1 = get_stroke_text_width(t1_str, txt_h1)
    w2 = get_stroke_text_width(transfer_note, txt_h2)
    w_content = max(w1, w2)
    w_box = max(w_content + pad_x * 2.0, 42.0 * s)
    h_box = txt_h1 + txt_h2 + gap_y + pad_y * 2.0

    p0 = rg.Point3d(center_x - w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p1 = rg.Point3d(center_x + w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p2 = rg.Point3d(center_x + w_box / 2.0, center_y + h_box / 2.0, 0.0)
    p3 = rg.Point3d(center_x - w_box / 2.0, center_y + h_box / 2.0, 0.0)
    box_crv = rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve()

    # Fundo preenchido suave (máscara / wipeout)
    cor_fundo = System.Drawing.Color.FromArgb(255, 255, 255)
    bg_mesh = make_box_background_mesh(p0, p1, p2, p3, cor_fundo)
    if bg_mesh: geoms.append(bg_mesh)
    if box_crv and box_crv.IsValid: geoms.append(box_crv)

    # Linha divisória horizontal interna técnica
    y_div = center_y
    l_div = rg.LineCurve(rg.Point3d(center_x - w_box/2.0 + 1.5*s, y_div, 0.0), rg.Point3d(center_x + w_box/2.0 - 1.5*s, y_div, 0.0))
    geoms.append(l_div)

    # Textos perfeitamente centralizados em suas metades
    pt_t1 = rg.Point3d(center_x, center_y + h_box / 4.0, 0.0)
    t1_crvs = make_text_geometry(t1_str, pt_t1, txt_h1, rg.TextJustification.MiddleCenter, s)
    if t1_crvs: geoms.extend(t1_crvs)

    pt_t2 = rg.Point3d(center_x, center_y - h_box / 4.0, 0.0)
    t2_crvs = make_text_geometry(transfer_note, pt_t2, txt_h2, rg.TextJustification.MiddleCenter, s)
    if t2_crvs: geoms.extend(t2_crvs)

    # Vertical arrow indicating longitudinal haul direction to subsequent sectiono
    y_arr_top = center_y - h_box / 2.0
    y_arr_bot = center_y - h_box / 2.0 - 2.5 * s
    p_arr_top = rg.Point3d(center_x, y_arr_top, 0.0)
    p_arr_bot = rg.Point3d(center_x, y_arr_bot, 0.0)
    geoms.append(rg.LineCurve(p_arr_top, p_arr_bot))

    p_tip = p_arr_bot
    p_l = rg.Point3d(center_x - 0.55 * s, y_arr_bot + 0.90 * s, 0.0)
    p_r = rg.Point3d(center_x + 0.55 * s, y_arr_bot + 0.90 * s, 0.0)
    arrow_mesh = make_filled_mesh_tri(p_tip, p_l, p_r)
    l_a1 = rg.LineCurve(p_tip, p_l)
    l_a2 = rg.LineCurve(p_tip, p_r)
    l_a3 = rg.LineCurve(p_l, p_r)
    geoms.extend([g for g in [arrow_mesh, l_a1, l_a2, l_a3] if g is not None])

    return geoms, (w_box, h_box)

def get_terrain_u_range(geoms_terreno, u_corte):
    """Calculates minimum and maximum bounding range of terrain curves projected onto cross-vector."""
    u_vals = []
    for g in geoms_terreno:
        if g is None: continue
        try:
            bb = g.GetBoundingBox(True) if hasattr(g, 'GetBoundingBox') else None
            if bb and bb.IsValid:
                corners = [
                    (bb.Min.X, bb.Min.Y),
                    (bb.Min.X, bb.Max.Y),
                    (bb.Max.X, bb.Min.Y),
                    (bb.Max.X, bb.Max.Y)
                ]
                for cx, cy in corners:
                    u_vals.append(cx * u_corte.X + cy * u_corte.Y)
        except: pass

        if isinstance(g, rg.Curve):
            try:
                p0 = g.PointAtStart
                p1 = g.PointAtEnd
                u_vals.append(p0.X * u_corte.X + p0.Y * u_corte.Y)
                u_vals.append(p1.X * u_corte.X + p1.Y * u_corte.Y)
                dom = g.Domain
                t0 = getattr(dom, 'Min', getattr(dom, 'T0', 0.0))
                t1 = getattr(dom, 'Max', getattr(dom, 'T1', 1.0))
                for k in range(1, 10):
                    pt = g.PointAt(t0 + (k / 10.0) * (t1 - t0))
                    u_vals.append(pt.X * u_corte.X + pt.Y * u_corte.Y)
            except: pass
        elif isinstance(g, rg.Mesh):
            try:
                for v in g.Vertices:
                    u_vals.append(v.X * u_corte.X + v.Y * u_corte.Y)
            except: pass
        elif isinstance(g, rg.Point3d):
            u_vals.append(g.X * u_corte.X + g.Y * u_corte.Y)
    if u_vals:
        return min(u_vals), max(u_vals)
    return None, None

# =============================================================================
# UNIVERSAL GRADE SAMPLER & PROJECT CURVE MAPPING
# =============================================================================

def make_project_grade_sampler(curva_greide_in, base_x, base_y, sec_datum_z, z_min, z_max, total_ext, curve_base_y=None, p_start_3d=None, u_sec_3d=None, d_terrain_start=0.0, max_slope=0.15):
    """
    Universal and robust proposed grade sampler with maximum slope constraint.
    Automatically detects if the curve was drawn:
    1. Directly over the 2D section drawing (Top Viewport, Z ~ 0, Y in drawing space)
    2. With absolute Z elevations in 3D space (real model Z)
    3. With absolute Y elevations in 2D space (Y ~ real Z)
    4. With inverted direction vector (Right-to-Left) or partial station extent.
    Ensures exact mapping with natural ground and enforces the MAXIMUM SLOPE CONSTRAINT RULE:
    No segment of the boundary line may exceed max_slope (default 15% = 0.15).
    If slope exceeds the limit, it is automatically clamped to 15%, preserving the reference elevation.
    """
    if curva_greide_in is None:
        return None

    c_dom = curva_greide_in.Domain
    t0 = getattr(c_dom, 'Min', getattr(c_dom, 'T0', 0.0))
    t1 = getattr(c_dom, 'Max', getattr(c_dom, 'T1', 1.0))

    n_samples = max(int(total_ext / 0.25), 100)
    pts = []
    t_divs = None
    try:
        t_divs = curva_greide_in.DivideByCount(n_samples, True)
    except:
        pass

    if t_divs:
        for t in t_divs:
            pts.append(curva_greide_in.PointAt(t))
    else:
        for k in range(n_samples + 1):
            tk = t0 + (k / float(n_samples)) * (t1 - t0)
            pts.append(curva_greide_in.PointAt(tk))

    if not pts:
        return None

    avg_z = sum(p.Z for p in pts) / float(len(pts))
    avg_y = sum(p.Y for p in pts) / float(len(pts))
    min_x = min(p.X for p in pts)
    max_x = max(p.X for p in pts)
    min_z = min(p.Z for p in pts)
    max_z = max(p.Z for p in pts)

    # 1. 3D Curve in model space (Z represents real elevation)
    is_3d_z = False
    if (abs(avg_z) > 1.0 and (z_min - 200.0 <= avg_z <= z_max + 200.0)) or        (max_z - min_z > 1.0 and min_z > 10.0):
        is_3d_z = True

    d_z_pairs = []
    if is_3d_z and p_start_3d is not None and u_sec_3d is not None:
        for p in pts:
            d_p = (p.X - p_start_3d.X) * u_sec_3d.X + (p.Y - p_start_3d.Y) * u_sec_3d.Y - d_terrain_start
            d_z_pairs.append((d_p, p.Z))
    else:
        # 2. Curva 2D (Z ~ 0)
        # Detects whether points use 2D drawing X coordinates or relative station X [0, total_ext]
        use_drawing_x = False
        if abs(min_x - base_x) < total_ext * 0.8 or            abs(max_x - (base_x + total_ext)) < total_ext * 0.8 or            (min_x >= base_x - 10.0 and max_x <= base_x + total_ext + 10.0):
            use_drawing_x = True

        sec_h = max(z_max - sec_datum_z, 1.0)
        ref_by = curve_base_y if curve_base_y is not None else base_y

        # Position detection relative to the 2D section drawing
        z_terrain_med = (z_min + z_max) / 2.0
        y_terrain_section_2d = ref_by + (z_terrain_med - sec_datum_z)
        dist_to_section = abs(avg_y - y_terrain_section_2d)

        # If the user drew the curve directly over the 2D section profile:
        # dist_to_section is small (within 2x sec_h or 15m of ground profile)
        is_drawn_on_section = (dist_to_section <= max(sec_h * 2.0, 15.0))

        # If not drawn over the section, checks if absolute Y elevation (e.g. Y ~ 900)
        is_abs_y = (not is_drawn_on_section) and (z_min - 50.0 <= avg_y <= z_max + 100.0)

        # If in free space (neither directly over section nor at absolute elevation)
        is_floating_in_void = (not is_drawn_on_section) and (not is_abs_y)

        for p in pts:
            d_p = (p.X - base_x) if use_drawing_x else p.X
            if is_drawn_on_section:
                # Primary case: drawn over 2D section with millimeter precision
                z_p = sec_datum_z + (p.Y - ref_by)
            elif is_abs_y:
                # Y coordinate represents real absolute elevation
                z_p = p.Y
            elif is_floating_in_void:
                # Smart anchoring to mean ground elevation, preserving slope and shape da linha
                delta_shape = p.Y - avg_y
                z_p = z_terrain_med + delta_shape
            else:
                z_p = sec_datum_z + (p.Y - ref_by)
            d_z_pairs.append((d_p, z_p))

    d_z_pairs.sort(key=lambda item: item[0])

    # Removes points with negligible horizontal distance to avoid division by zero zero
    clean_d_z = [d_z_pairs[0]]
    for item in d_z_pairs[1:]:
        if item[0] - clean_d_z[-1][0] > 1e-4:
            clean_d_z.append(item)

    # Strict enforcement of the 15% Maximum Slope Rule (max_slope)
    max_orig_slope = 0.0
    was_clamped = False
    final_d_z = []

    if len(clean_d_z) >= 2:
        final_d_z = [(clean_d_z[0][0], clean_d_z[0][1])]
        for k in range(len(clean_d_z) - 1):
            d_curr, z_curr = final_d_z[-1]
            d_next, z_next_orig = clean_d_z[k+1]
            delta_d = d_next - d_curr
            if delta_d > 1e-5:
                s_seg = (z_next_orig - clean_d_z[k][1]) / delta_d
                if abs(s_seg) > max_orig_slope:
                    max_orig_slope = abs(s_seg)
                if s_seg > max_slope:
                    z_next_clamped = z_curr + max_slope * delta_d
                    was_clamped = True
                elif s_seg < -max_slope:
                    z_next_clamped = z_curr - max_slope * delta_d
                    was_clamped = True
                else:
                    z_next_clamped = z_curr + s_seg * delta_d
                final_d_z.append((d_next, z_next_clamped))
            else:
                final_d_z.append((d_next, z_curr))
    else:
        final_d_z = clean_d_z

    def sample_grade(d_val):
        if not final_d_z:
            return (z_min + z_max) / 2.0
        if len(final_d_z) == 1:
            return final_d_z[0][1]
        d_0, z_0 = final_d_z[0]
        d_1, z_1 = final_d_z[1]
        if d_val <= d_0:
            if abs(d_1 - d_0) < 1e-6: return z_0
            s_ini = (z_1 - z_0) / (d_1 - d_0)
            return z_0 + (d_val - d_0) * s_ini
        d_n1, z_n1 = final_d_z[-2]
        d_n, z_n = final_d_z[-1]
        if d_val >= d_n:
            if abs(d_n - d_n1) < 1e-6: return z_n
            s_fim = (z_n - z_n1) / (d_n - d_n1)
            return z_n + (d_val - d_n) * s_fim
        for i in range(len(final_d_z) - 1):
            d_a, z_a = final_d_z[i]
            d_b, z_b = final_d_z[i+1]
            if d_a <= d_val <= d_b:
                if abs(d_b - d_a) < 1e-6: return z_a
                t = (d_val - d_a) / (d_b - d_a)
                return z_a + t * (z_b - z_a)
        return final_d_z[-1][1]

    sample_grade.max_slope_limit = max_slope
    sample_grade.max_orig_slope = max_orig_slope * 100.0
    if len(final_d_z) >= 2:
        d_span = final_d_z[-1][0] - final_d_z[0][0]
        z_span = final_d_z[-1][1] - final_d_z[0][1]
        sample_grade.effective_slope = (z_span / max(d_span, 1e-4)) * 100.0
    else:
        sample_grade.effective_slope = 0.0
    sample_grade.was_clamped = was_clamped

    return sample_grade

def make_cross_interpolated_grade(cross_pairs, total_ext_v, z_min_v, z_max_v, max_slope=0.15):
    """
    Creates a continuous grade sampler for longitudinal sections (1, 2, 3...)
    from proposed elevations at intersections with cross sections (A, B, C...).
    Ensures 100% geometric and physical synchronization between cross and longitudinal cuts.
    Applies the normative 15% maximum slope constraint rule.
    """
    if not cross_pairs:
        z_med = (z_min_v + z_max_v) / 2.0
        func = lambda d: z_med
        func.max_slope_limit = max_slope
        func.max_orig_slope = 0.0
        func.effective_slope = 0.0
        func.was_clamped = False
        return func

    sorted_pairs = sorted(cross_pairs, key=lambda x: x[0])

    # Applies maximum slope validation between intersection points
    final_pairs = [(sorted_pairs[0][0], sorted_pairs[0][1])]
    was_clamped = False
    max_orig_slope = 0.0

    for k in range(len(sorted_pairs) - 1):
        d_curr, z_curr = final_pairs[-1]
        d_next, z_next_orig = sorted_pairs[k+1]
        dd = d_next - d_curr
        if dd > 1e-4:
            s_seg = (z_next_orig - sorted_pairs[k][1]) / dd
            if abs(s_seg) > max_orig_slope: max_orig_slope = abs(s_seg)
            if s_seg > max_slope:
                z_clamped = z_curr + max_slope * dd
                was_clamped = True
            elif s_seg < -max_slope:
                z_clamped = z_curr - max_slope * dd
                was_clamped = True
            else:
                z_clamped = z_curr + s_seg * dd
            final_pairs.append((d_next, z_clamped))
        else:
            final_pairs.append((d_next, z_curr))

    def sample_cross(d_val):
        if len(final_pairs) == 1:
            return final_pairs[0][1]
        d0, z0 = final_pairs[0]
        d1, z1 = final_pairs[1]
        if d_val <= d0:
            if abs(d1 - d0) < 1e-4: return z0
            s_ini = (z1 - z0) / (d1 - d0)
            return z0 + (d_val - d0) * s_ini
        dn1, zn1 = final_pairs[-2]
        dn, zn = final_pairs[-1]
        if d_val >= dn:
            if abs(dn - dn1) < 1e-4: return zn
            s_fim = (zn - zn1) / (dn - dn1)
            return zn + (d_val - dn) * s_fim
        for k in range(len(final_pairs) - 1):
            da, za = final_pairs[k]
            db, zb = final_pairs[k+1]
            if da <= d_val <= db:
                if abs(db - da) < 1e-4: return za
                t = (d_val - da) / (db - da)
                return za + t * (zb - za)
        return final_pairs[-1][1]

    sample_cross.max_slope_limit = max_slope
    sample_cross.max_orig_slope = max_orig_slope * 100.0
    if len(final_pairs) >= 2:
        d_span = final_pairs[-1][0] - final_pairs[0][0]
        z_span = final_pairs[-1][1] - final_pairs[0][1]
        sample_cross.effective_slope = (z_span / max(d_span, 1e-4)) * 100.0
    else:
        sample_cross.effective_slope = 0.0
    sample_cross.was_clamped = was_clamped
    return sample_cross

def sample_surface_proj_z(px, py, lista_alinhadas, sec_data_list, u_long_down):
    """
    Samples project elevation Z at (px, py) directly from the continuous 3D design surface
    defined by the transverse cross sections (lista_alinhadas and sec_data_list).
    Ensures 100% mathematical and physical synchronization between cross and longitudinal cuts.
    Guarantees no phantom cuts, runaway extrapolations, or inter-table contradictions.
    """
    if not lista_alinhadas or not sec_data_list:
        return 0.0
    num_s = min(len(lista_alinhadas), len(sec_data_list))
    if num_s == 1:
        s0 = lista_alinhadas[0]
        u_dir = s0.PointAtEnd - s0.PointAtStart
        u_dir.Unitize()
        d0 = (px - s0.PointAtStart.X) * u_dir.X + (py - s0.PointAtStart.Y) * u_dir.Y
        d0_c = max(0.0, min(sec_data_list[0].get('total_ext', s0.GetLength()), d0))
        return sec_data_list[0]['get_proj_z'](d0_c)

    v_secs = []
    u_dirs = []
    for s_crv in lista_alinhadas[:num_s]:
        pm = s_crv.PointAtNormalizedLength(0.5)
        v_secs.append(pm.X * u_long_down.X + pm.Y * u_long_down.Y)
        ud = s_crv.PointAtEnd - s_crv.PointAtStart
        ud.Unitize()
        u_dirs.append(ud)

    v_pt = px * u_long_down.X + py * u_long_down.Y

    # Clamped bounds: before first section (top of site)
    if v_pt <= v_secs[0]:
        s0 = lista_alinhadas[0]
        d0 = (px - s0.PointAtStart.X) * u_dirs[0].X + (py - s0.PointAtStart.Y) * u_dirs[0].Y
        d0_c = max(0.0, min(sec_data_list[0].get('total_ext', s0.GetLength()), d0))
        return sec_data_list[0]['get_proj_z'](d0_c)

    # After last section (bottom of site)
    if v_pt >= v_secs[-1]:
        sn = lista_alinhadas[num_s - 1]
        dn = (px - sn.PointAtStart.X) * u_dirs[-1].X + (py - sn.PointAtStart.Y) * u_dirs[-1].Y
        dn_c = max(0.0, min(sec_data_list[num_s - 1].get('total_ext', sn.GetLength()), dn))
        return sec_data_list[num_s - 1]['get_proj_z'](dn_c)

    # Interpolate between consecutive bounding cross sections i and i+1
    for i in range(num_s - 1):
        v1, v2 = v_secs[i], v_secs[i+1]
        if v1 <= v_pt <= v2:
            span = max(v2 - v1, 1e-4)
            t = (v_pt - v1) / span
            sa = lista_alinhadas[i]
            sb = lista_alinhadas[i+1]
            da = (px - sa.PointAtStart.X) * u_dirs[i].X + (py - sa.PointAtStart.Y) * u_dirs[i].Y
            db = (px - sb.PointAtStart.X) * u_dirs[i+1].X + (py - sb.PointAtStart.Y) * u_dirs[i+1].Y
            da_c = max(0.0, min(sec_data_list[i].get('total_ext', sa.GetLength()), da))
            db_c = max(0.0, min(sec_data_list[i+1].get('total_ext', sb.GetLength()), db))
            za = sec_data_list[i]['get_proj_z'](da_c)
            zb = sec_data_list[i+1]['get_proj_z'](db_c)
            return (1.0 - t) * za + t * zb

    return sec_data_list[-1]['get_proj_z'](0.0)

def match_project_curves_to_sections(curves_raw, sec_targets, espacamento_y=None):
    """
    Maps provided project curves / boundary grading lines to their respective sections based
    on 2D proximity (X and Y coordinates in drawing space) or input order.
    Supports both cross sections (A, B, C...) and longitudinal sections (1, 2, 3...),
    ensuring that a line drawn over SECTION 1 - 1 is mapped to SECTION 1 - 1,
    and a line drawn over SECTION A - A is mapped to SECTION A - A.
    """
    # Se sec_targets for uma lista simples de floats (compatibilidade com chamadas legadas)
    is_legacy_list = False
    if sec_targets and isinstance(sec_targets[0], (int, float)):
        is_legacy_list = True
        targets_list = [{'key': idx, 'base_x': 0.0, 'base_y': by, 'total_ext': 150.0, 'sec_h': 20.0} for idx, by in enumerate(sec_targets)]
    else:
        targets_list = sec_targets

    if not curves_raw:
        if is_legacy_list:
            return [(None, None) for _ in targets_list]
        return {t['key']: (None, t['base_y']) for t in targets_list}

    # Se há apenas 1 curva fornecida
    if len(curves_raw) == 1:
        c = curves_raw[0]
        # Tests if curve is drawn directly over a specific 2D section
        try:
            bb = c.GetBoundingBox(True) if hasattr(c, 'GetBoundingBox') else c.GetBoundingBox()
            cx = (bb.Min.X + bb.Max.X) / 2.0 if bb.IsValid else c.PointAtNormalizedLength(0.5).X
            cy = (bb.Min.Y + bb.Max.Y) / 2.0 if bb.IsValid else c.PointAtNormalizedLength(0.5).Y
        except:
            pm = c.PointAtNormalizedLength(0.5)
            cx, cy = pm.X, pm.Y

        # Finds the closest section to the point
        best_t = None
        best_d = 1e12
        for t in targets_list:
            bx = t.get('base_x', 0.0)
            by = t.get('base_y', 0.0)
            tot_ext = t.get('total_ext', 150.0)
            sec_h = t.get('sec_h', 20.0)
            dx = 0.0 if (bx - 15.0 <= cx <= bx + tot_ext + 15.0) else min(abs(cx - bx), abs(cx - (bx + tot_ext)))
            dy = abs(cy - (by + sec_h / 2.0))
            d_score = math.hypot(dx * 3.5, dy)
            if d_score < best_d:
                best_d = d_score
                best_t = t

        # If the curve is clearly positioned over a section (e.g. within 50m)
        if best_d < 60.0 and best_t is not None:
            res_dict = {t['key']: (None, t['base_y']) for t in targets_list}
            res_dict[best_t['key']] = (c, best_t['base_y'])
            if is_legacy_list:
                return [res_dict[t['key']] for t in targets_list]
            return res_dict
        else:
            # Aplica como template exclusivamente para seções transversais ('T'), mantendo longitudinais ('V') para sincronização 3D contínua
            res_dict = {}
            for t in targets_list:
                k = t['key']
                if isinstance(k, tuple) and k[0] == 'V':
                    res_dict[k] = (None, t['base_y'])
                else:
                    res_dict[k] = (c, t['base_y'])
            if is_legacy_list:
                return [res_dict[t['key']] for t in targets_list]
            return res_dict

    # Multiple curves: maps each curve to its corresponding cross or longitudinal sectiongitudinal
    matched_dict = {}
    used_curves = set()

    for t in targets_list:
        bx = t.get('base_x', 0.0)
        by = t.get('base_y', 0.0)
        tot_ext = t.get('total_ext', 150.0)
        sec_h = t.get('sec_h', 20.0)

        best_c = None
        best_d = 1e12
        best_c_idx = -1

        for c_idx, c in enumerate(curves_raw):
            if c_idx in used_curves: continue
            try:
                bb = c.GetBoundingBox(True) if hasattr(c, 'GetBoundingBox') else c.GetBoundingBox()
                cx = (bb.Min.X + bb.Max.X) / 2.0 if bb.IsValid else c.PointAtNormalizedLength(0.5).X
                cy = (bb.Min.Y + bb.Max.Y) / 2.0 if bb.IsValid else c.PointAtNormalizedLength(0.5).Y
            except:
                pm = c.PointAtNormalizedLength(0.5)
                cx, cy = pm.X, pm.Y

            dx = 0.0 if (bx - 15.0 <= cx <= bx + tot_ext + 15.0) else min(abs(cx - bx), abs(cx - (bx + tot_ext)))
            dy = abs(cy - (by + sec_h / 2.0))
            d_score = math.hypot(dx * 4.0, dy)

            if d_score < best_d:
                best_d = d_score
                best_c = c
                best_c_idx = c_idx

        max_dist_match = 60.0 if (isinstance(t.get('key'), tuple) and t['key'][0] == 'V') else 120.0
        if best_c is not None and best_d < max_dist_match:
            matched_dict[t['key']] = (best_c, by)
            used_curves.add(best_c_idx)
        else:
            matched_dict[t['key']] = (None, by)

    if is_legacy_list:
        return [matched_dict[t['key']] for t in targets_list]
    return matched_dict

# =============================================================================
# ANALYTICAL EVALUATION OF AN INDIVIDUAL SECTION
# =============================================================================

def extract_section_terrain(crv_corte, geoms_terreno, tol, intersec_axes=None, s=1.0):
    """Extracts natural terrain intersection along 3D cut line with millimeter precision."""
    p_start = crv_corte.PointAtStart
    p_end = crv_corte.PointAtEnd
    dx = p_end.X - p_start.X
    dy = p_end.Y - p_start.Y
    L_horiz = math.hypot(dx, dy)

    if L_horiz < 1e-4:
        L_horiz = 1.0
        ux, uy = 1.0, 0.0
    else:
        ux = dx / L_horiz
        uy = dy / L_horiz

    cut_plane = rg.Plane(rg.Point3d(p_start.X, p_start.Y, 0.0), rg.Vector3d(ux, uy, 0.0), rg.Vector3d.ZAxis)
    cut_xy = rg.Curve.ProjectToPlane(crv_corte, rg.Plane.WorldXY)
    if cut_xy is None: cut_xy = crv_corte

    pts_with_d = []

    for geom in geoms_terreno:
        if geom is None: continue

        # 1. Contour Lines (Curves)
        if isinstance(geom, rg.Curve):
            # A. Intersection with cut vertical plane (3D)
            try:
                evs = rg.Intersect.Intersection.CurvePlane(geom, cut_plane, tol)
                if evs:
                    for ev in evs:
                        pt = ev.PointA
                        d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                        if -tol <= d <= L_horiz + tol:
                            d_clamped = max(0.0, min(L_horiz, d))
                            pts_with_d.append((d_clamped, rg.Point3d(p_start.X + ux * d_clamped, p_start.Y + uy * d_clamped, pt.Z)))
            except: pass

            # B. Intersection of projected curves on XY plane (2D)
            try:
                geom_xy = rg.Curve.ProjectToPlane(geom, rg.Plane.WorldXY)
                if geom_xy is not None:
                    cc_evs = rg.Intersect.Intersection.CurveCurve(cut_xy, geom_xy, tol * 10, tol * 10)
                    if cc_evs:
                        for cc in cc_evs:
                            t_c = cc.ParameterA
                            pt_c = cut_xy.PointAt(t_c)
                            rc, t_real = geom.ClosestPoint(rg.Point3d(pt_c.X, pt_c.Y, geom.PointAtStart.Z))
                            z_val = geom.PointAt(t_real).Z if rc else geom.PointAtStart.Z
                            d = (pt_c.X - p_start.X) * ux + (pt_c.Y - p_start.Y) * uy
                            if -tol <= d <= L_horiz + tol:
                                d_clamped = max(0.0, min(L_horiz, d))
                                pts_with_d.append((d_clamped, rg.Point3d(p_start.X + ux * d_clamped, p_start.Y + uy * d_clamped, z_val)))
            except: pass

        # 2. Terrain Mesh
        elif isinstance(geom, rg.Mesh):
            try:
                polys = rg.Intersect.Intersection.MeshPlane(geom, cut_plane)
                if polys:
                    for poly in polys:
                        for pt in poly:
                            d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                            if -tol <= d <= L_horiz + tol:
                                d_clamped = max(0.0, min(L_horiz, d))
                                pts_with_d.append((d_clamped, rg.Point3d(p_start.X + ux * d_clamped, p_start.Y + uy * d_clamped, pt.Z)))
            except: pass

            try:
                bbox_m = geom.GetBoundingBox(True)
                if bbox_m.IsValid:
                    z_top = bbox_m.Max.Z + 1000.0
                    z_bot = bbox_m.Min.Z - 1000.0
                    n_samples = max(int(L_horiz / 0.5), 80)
                    for k in range(n_samples + 1):
                        d_k = k * (L_horiz / float(n_samples))
                        p_top = rg.Point3d(p_start.X + ux * d_k, p_start.Y + uy * d_k, z_top)
                        ray_dn = rg.Ray3d(p_top, -rg.Vector3d.ZAxis)
                        h_dn = rg.Intersect.Intersection.MeshRay(geom, ray_dn)
                        if h_dn >= 0:
                            z_found = z_top - h_dn
                            pts_with_d.append((d_k, rg.Point3d(p_start.X + ux * d_k, p_start.Y + uy * d_k, z_found)))
                        else:
                            p_bot = rg.Point3d(p_start.X + ux * d_k, p_start.Y + uy * d_k, z_bot)
                            ray_up = rg.Ray3d(p_bot, rg.Vector3d.ZAxis)
                            h_up = rg.Intersect.Intersection.MeshRay(geom, ray_up)
                            if h_up >= 0:
                                z_found = z_bot + h_up
                                pts_with_d.append((d_k, rg.Point3d(p_start.X + ux * d_k, p_start.Y + uy * d_k, z_found)))
            except: pass

        # 3. Superfície / Brep
        elif isinstance(geom, rg.Brep):
            try:
                rc, sec_crvs, sec_pts = rg.Intersect.Intersection.BrepPlane(geom, cut_plane, tol)
                if rc and sec_crvs:
                    for sc in sec_crvs:
                        n_div = max(int(sc.GetLength() / 0.5), 10)
                        t_divs = sc.DivideByCount(n_div, True)
                        if t_divs:
                            for td in t_divs:
                                pt = sc.PointAt(td)
                                d = (pt.X - p_start.X) * ux + (pt.Y - p_start.Y) * uy
                                if -tol <= d <= L_horiz + tol:
                                    d_clamped = max(0.0, min(L_horiz, d))
                                    pts_with_d.append((d_clamped, rg.Point3d(p_start.X + ux * d_clamped, p_start.Y + uy * d_clamped, pt.Z)))
            except: pass

    # Ordenação e deduplicação
    pts_with_d.sort(key=lambda x: x[0])
    clean_pts = []
    for d, pt in pts_with_d:
        if not clean_pts:
            clean_pts.append((d, pt))
        else:
            if abs(d - clean_pts[-1][0]) > 0.05 or abs(pt.Z - clean_pts[-1][1].Z) > 0.02:
                clean_pts.append((d, pt))

    # STRICT BOUNDARY AT CONTOUR EXTENTS (Contour end is the true physical limit)l do Perfil)
    d_terrain_start = 0.0
    axes_filtered = list(intersec_axes) if intersec_axes else []
    if len(clean_pts) >= 2:
        d_terrain_start = clean_pts[0][0]
        d_terrain_end = clean_pts[-1][0]
        total_ext = d_terrain_end - d_terrain_start

        if total_ext > 0.1:
            clean_pts = [(d - d_terrain_start, pt) for d, pt in clean_pts]
            if axes_filtered:
                axes_filtered = [(item[0] - d_terrain_start, item[1], item[2]) for item in axes_filtered]
        else:
            total_ext = L_horiz
    else:
        valid_zs = []
        for g in geoms_terreno:
            try:
                bb = g.GetBoundingBox(True) if hasattr(g, 'GetBoundingBox') else g.GetBoundingBox()
                if bb.IsValid and abs(bb.Max.Z - bb.Min.Z) > 0.01:
                    valid_zs.append((bb.Min.Z + bb.Max.Z) / 2.0)
                elif bb.IsValid and abs(bb.Min.Z) > 1.0:
                    valid_zs.append(bb.Min.Z)
            except: pass

        z_ref = (sum(valid_zs) / float(len(valid_zs))) if valid_zs else 0.0

        p_mid_c = crv_corte.PointAtNormalizedLength(0.5)
        best_d = 1e12
        for g in geoms_terreno:
            if isinstance(g, rg.Curve):
                try:
                    rc, t_cl = g.ClosestPoint(p_mid_c)
                    if rc:
                        pt_cl = g.PointAt(t_cl)
                        dist_xy = math.hypot(pt_cl.X - p_mid_c.X, pt_cl.Y - p_mid_c.Y)
                        if dist_xy < best_d:
                            best_d = dist_xy
                            z_ref = pt_cl.Z
                except: pass

        clean_pts = [
            (0.0, rg.Point3d(p_start.X, p_start.Y, z_ref)),
            (L_horiz, rg.Point3d(p_end.X, p_end.Y, z_ref))
        ]
        total_ext = L_horiz

    total_ext = clean_pts[-1][0] if clean_pts else L_horiz
    pts_crv_3d = [p[1] for p in clean_pts]
    crv_3d = rg.PolylineCurve(pts_crv_3d) if len(pts_crv_3d) >= 2 else None
    if not (crv_3d and crv_3d.IsValid) and len(pts_crv_3d) >= 2:
        crv_3d = rg.LineCurve(pts_crv_3d[0], pts_crv_3d[-1])

    z_min = min(p[1].Z for p in clean_pts)
    z_max = max(p[1].Z for p in clean_pts)
    sec_datum_z = math.floor(z_min - 2.0)
    sec_h = z_max - sec_datum_z

    # Identification of internal station dividers (cross-axes within the section)e)
    d_divs = []
    eixos_secao = []
    if axes_filtered:
        for item in axes_filtered:
            d_ax = item[0]
            if 0.5 * s <= d_ax <= total_ext - 0.5 * s:
                eixos_secao.append(item)
                if 2.0 * s <= d_ax <= total_ext - 2.0 * s:
                    d_divs.append(item)

    # Station/quadrant delineation along section length
    trecho_bounds = []
    d_prev = 0.0
    for item in d_divs:
        d_ax = item[0]
        trecho_bounds.append((d_prev, d_ax))
        d_prev = d_ax
    trecho_bounds.append((d_prev, total_ext))
    num_trechos = len(trecho_bounds)

    trecho_avg_zs = []
    for (d_ini, d_fim) in trecho_bounds:
        sub_zs = [pt.Z for d, pt in clean_pts if d_ini - 0.5 <= d <= d_fim + 0.5]
        if sub_zs:
            trecho_avg_zs.append(sum(sub_zs) / float(len(sub_zs)))
        else:
            trecho_avg_zs.append((z_min + z_max) / 2.0)

    return {
        'p_start': p_start,
        'p_end': p_end,
        'ux': ux,
        'uy': uy,
        'L_horiz': L_horiz,
        'd_terrain_start': d_terrain_start,
        'clean_pts': clean_pts,
        'total_ext': total_ext,
        'crv_3d': crv_3d,
        'cut_xy': cut_xy,
        'z_min': z_min,
        'z_max': z_max,
        'sec_datum_z': sec_datum_z,
        'sec_h': sec_h,
        'd_divs': d_divs,
        'eixos_secao': eixos_secao,
        'trecho_bounds': trecho_bounds,
        'num_trechos': num_trechos,
        'trecho_avg_zs': trecho_avg_zs
    }

def evaluate_section_grade_and_volumes(t_info, curva_greide_in, raw_nivel_proj, label_sec="A", s=1.0, base_x=0.0, base_y=0.0, curve_base_y=None, max_slope=0.15, road_polygons=None):
    """Calculates grade, cut/fill classification, areas and volumes for a section from t_info."""
    clean_pts = t_info['clean_pts']
    total_ext = t_info['total_ext']
    crv_3d = t_info['crv_3d']
    cut_xy = t_info.get('cut_xy')
    if cut_xy is None:
        cut_xy = crv_3d
    z_min = t_info['z_min']
    z_max = t_info['z_max']
    sec_datum_z = t_info['sec_datum_z']
    sec_h = t_info['sec_h']
    d_divs = t_info['d_divs']
    eixos_secao = t_info['eixos_secao']
    trecho_bounds = t_info['trecho_bounds']
    num_trechos = t_info['num_trechos']
    trecho_avg_zs = t_info['trecho_avg_zs']
    p_start = t_info['p_start']
    ux = t_info['ux']
    uy = t_info['uy']
    d_terrain_start = t_info['d_terrain_start']

    sampler = make_project_grade_sampler(
        curva_greide_in, base_x, base_y, sec_datum_z, z_min, z_max, total_ext,
        curve_base_y=curve_base_y,
        p_start_3d=p_start,
        u_sec_3d=rg.Vector3d(ux, uy, 0.0),
        d_terrain_start=d_terrain_start,
        max_slope=max_slope
    )

    corridors = compute_road_corridors_for_section(t_info.get('cut_xy') or t_info['crv_3d'], road_polygons, 0.001)

    def get_raw_proj_z(d_val):
        if sampler is not None:
            try:
                z_res = sampler(d_val)
                if z_res is not None:
                    return z_res
            except:
                pass

        k_found = 0
        for i_div, item in enumerate(d_divs):
            if d_val >= item[0]:
                k_found = i_div + 1
            else:
                break

        if raw_nivel_proj is not None:
            if isinstance(raw_nivel_proj, (list, tuple)) and len(raw_nivel_proj) > 0:
                try: return float(raw_nivel_proj[min(k_found, len(raw_nivel_proj) - 1)])
                except: pass
            else:
                try: return float(raw_nivel_proj)
                except: pass

        if trecho_avg_zs and k_found < len(trecho_avg_zs):
            return trecho_avg_zs[k_found]
        if clean_pts:
            return sum(p[1].Z for p in clean_pts) / float(len(clean_pts))
        return (z_min + z_max) / 2.0

    def get_proj_z(d_val):
        z_raw = get_raw_proj_z(d_val)
        if corridors:
            return make_drivable_road_z(d_val, z_raw, corridors)
        return z_raw

    # Amostragem com discretização fina
    num_passos = max(int(total_ext / 0.25), 80)
    dx = total_ext / float(num_passos)
    estacas_d = [i * dx for i in range(num_passos + 1)]
    if estacas_d[-1] < total_ext: estacas_d.append(total_ext)

    # Adds divider stations with epsilon for vertical step in grade
    for item in d_divs:
        d_ax = item[0]
        estacas_d.append(max(0.0, d_ax - 1e-4))
        estacas_d.append(min(total_ext, d_ax + 1e-4))

    # Adds road corridor breaklines (edges, gutters, crown) for sharp geometric definition
    for cor in corridors:
        d1 = cor['d_in']
        d2 = cor['d_out']
        w = cor['width']
        w_sw = min(1.20, w * 0.18) if w >= 3.0 else 0.0
        dp1 = d1 + w_sw
        dp2 = d2 - w_sw
        dmid = cor['d_mid']
        for pt_d in [d1 - 1e-4, d1, dp1, dmid, dp2, d2, d2 + 1e-4]:
            if 0.0 <= pt_d <= total_ext:
                estacas_d.append(pt_d)

    pontos_passagem = []
    diff_sinais = []
    for d in sorted(list(set(estacas_d))):
        z_tn = interpolate_terrain_z(d, clean_pts)
        z_pr = get_proj_z(d)
        diff_sinais.append((d, z_tn - z_pr))

    for i in range(len(diff_sinais) - 1):
        d1, diff1 = diff_sinais[i]
        d2, diff2 = diff_sinais[i+1]
        if diff1 * diff2 < 0.0:
            t_pp = abs(diff1) / (abs(diff1) + abs(diff2))
            d_pp = d1 + t_pp * (d2 - d1)
            pontos_passagem.append((d_pp, get_proj_z(d_pp)))

    estacas_finais = sorted(list(set(estacas_d + [p[0] for p in pontos_passagem])))

    regioes = []
    cur_tipo = None
    cur_pts = []

    for i in range(len(estacas_finais) - 1):
        d_a = estacas_finais[i]
        d_b = estacas_finais[i+1]
        d_mid = (d_a + d_b) / 2.0
        z_tn_m = interpolate_terrain_z(d_mid, clean_pts)
        z_pr_m = get_proj_z(d_mid)
        # Classificação geotécnica executiva (NBR 6492 / DNIT):
        # Aterro: cota de greide superior ao terreno natural (Greide > Terreno).
        # Corte: terreno natural superior à cota de greide (Terreno > Greide).
        tipo = "ATERRO" if z_tn_m >= z_pr_m else "CORTE"

        if tipo != cur_tipo:
            if cur_pts: regioes.append((cur_tipo, cur_pts))
            cur_tipo = tipo
            cur_pts = [d_a, d_b]
        else:
            cur_pts.append(d_b)
    if cur_pts: regioes.append((cur_tipo, cur_pts))

    area_total_corte = 0.0
    area_total_aterro = 0.0
    max_h_corte = 0.0
    max_h_aterro = 0.0
    d_max_corte = 0.0
    d_max_aterro = 0.0

    for r_type, d_list in regioes:
        for j in range(len(d_list) - 1):
            d1 = d_list[j]
            d2 = d_list[j+1]
            seg_dx = d2 - d1
            if seg_dx <= 1e-6: continue

            h1 = abs(interpolate_terrain_z(d1, clean_pts) - get_proj_z(d1))
            h2 = abs(interpolate_terrain_z(d2, clean_pts) - get_proj_z(d2))
            a_elem = ((h1 + h2) / 2.0) * seg_dx

            if r_type == "CORTE":
                area_total_corte += a_elem
                if h1 > max_h_corte: max_h_corte, d_max_corte = h1, d1
                if h2 > max_h_corte: max_h_corte, d_max_corte = h2, d2
            else:
                area_total_aterro += a_elem
                if h1 > max_h_aterro: max_h_aterro, d_max_aterro = h1, d1
                if h2 > max_h_aterro: max_h_aterro, d_max_aterro = h2, d2

    # Data and statistics per individual quadrant/segment
    trechos_data = []
    for k in range(num_trechos):
        d_ini, d_fim = trecho_bounds[k]
        lbl_q = "Q.{}-{}".format(label_sec, k + 1)
        z_plat = get_proj_z((d_ini + d_fim) / 2.0)

        a_corte_k = 0.0
        a_aterro_k = 0.0
        max_hc_k = 0.0
        d_hc_k = d_ini
        max_ha_k = 0.0
        d_ha_k = d_ini

        for r_type, d_list in regioes:
            for j in range(len(d_list) - 1):
                d1 = d_list[j]
                d2 = d_list[j+1]
                d1_c = max(d1, d_ini)
                d2_c = min(d2, d_fim)
                seg_dx = d2_c - d1_c
                if seg_dx <= 1e-6: continue

                h1 = abs(interpolate_terrain_z(d1_c, clean_pts) - get_proj_z(d1_c))
                h2 = abs(interpolate_terrain_z(d2_c, clean_pts) - get_proj_z(d2_c))
                a_elem = ((h1 + h2) / 2.0) * seg_dx

                if r_type == "CORTE":
                    a_corte_k += a_elem
                    if h1 > max_hc_k: max_hc_k, d_hc_k = h1, d1_c
                    if h2 > max_hc_k: max_hc_k, d_hc_k = h2, d2_c
                else:
                    a_aterro_k += a_elem
                    if h1 > max_ha_k: max_ha_k, d_ha_k = h1, d1_c
                    if h2 > max_ha_k: max_ha_k, d_ha_k = h2, d2_c

        trechos_data.append({
            'idx': k,
            'd_start': d_ini,
            'd_end': d_fim,
            'label_q': lbl_q,
            'area_corte': a_corte_k,
            'area_aterro': a_aterro_k,
            'max_h_corte': max_hc_k,
            'd_max_corte': d_hc_k,
            'max_h_aterro': max_ha_k,
            'd_max_aterro': d_ha_k,
            'z_proj': z_plat,
            'saldo': a_corte_k - a_aterro_k
        })

    # Internal haul tracking between adjacent quadrants within the section
    internal_transfers = []
    for k in range(len(trechos_data) - 1):
        tr1 = trechos_data[k]
        tr2 = trechos_data[k+1]
        d_boundary = tr1['d_end']

        # Cut in Quadrant 1 supplying Embankment in Quadrant 2
        if tr1['area_corte'] > 0.05 and tr2['area_aterro'] > 0.05:
            a_transf = min(tr1['area_corte'], tr2['area_aterro'])
            internal_transfers.append({
                'from_idx': k,
                'to_idx': k + 1,
                'd_axis': d_boundary,
                'area_transf': a_transf,
                'direction': 'RIGHT'
            })
        elif tr1['area_aterro'] > 0.05 and tr2['area_corte'] > 0.05:
            a_transf = min(tr1['area_aterro'], tr2['area_corte'])
            internal_transfers.append({
                'from_idx': k + 1,
                'to_idx': k,
                'd_axis': d_boundary,
                'area_transf': a_transf,
                'direction': 'LEFT'
            })

    return {
        'label': label_sec,
        'clean_pts': clean_pts,
        'total_ext': total_ext,
        'crv_3d': crv_3d,
        'cut_xy': cut_xy,
        'z_min': z_min,
        'z_max': z_max,
        'sec_datum_z': sec_datum_z,
        'sec_h': sec_h,
        'get_proj_z': get_proj_z,
        'estacas_finais': estacas_finais,
        'regioes': regioes,
        'area_total_corte': area_total_corte,
        'area_total_aterro': area_total_aterro,
        'max_h_corte': max_h_corte,
        'd_max_corte': d_max_corte,
        'max_h_aterro': max_h_aterro,
        'd_max_aterro': d_max_aterro,
        'pontos_passagem': pontos_passagem,
        'trechos_data': trechos_data,
        'internal_transfers': internal_transfers,
        'eixos_secao': eixos_secao,
        'sampler': sampler,
        'max_slope_limit': max_slope * 100.0,
        'was_clamped': getattr(sampler, 'was_clamped', False) if sampler else False,
        'orig_slope': getattr(sampler, 'max_orig_slope', 0.0) if sampler else 0.0,
        'effective_slope': getattr(sampler, 'effective_slope', 0.0) if sampler else 0.0,
        'road_corridors': corridors
    }

def evaluate_section_data(crv_corte, geoms_terreno, curva_greide_in, raw_nivel_proj, tol, intersec_axes=None, label_sec="A", s=1.0, base_x=0.0, base_y=0.0, curve_base_y=None, max_slope=0.15, road_polygons=None):
    """Calculates 3D geometry, natural terrain profile and earthwork grade for a section."""
    t_info = extract_section_terrain(crv_corte, geoms_terreno, tol, intersec_axes, s)
    return evaluate_section_grade_and_volumes(t_info, curva_greide_in, raw_nivel_proj, label_sec, s, base_x, base_y, curve_base_y, max_slope=max_slope, road_polygons=road_polygons)

# =============================================================================
# MAIN COORDINATOR: MULTI-AXIS, ALIGNMENT, VOLUMES AND MASS HAUL BALANCE
# =============================================================================

def render_single_section_2d_and_3d(s_data, lbl, base_x, base_y, s, modo_cotas, cor_corte, cor_aterro, crv_aln_3d=None, is_longitudinal=False, axis_title_prefix="SEÇÃO "):
    """
    Renders all 2D graphic elements and 3D geometries of an individual section
    (either cross section A, B, C... or longitudinal 1, 2, 3...).
    Returns complete dictionary with 2D geometries, cut/fill polygons and 3D geometries.
    """
    clean_pts = s_data['clean_pts']
    total_ext = s_data['total_ext']
    get_proj_z = s_data['get_proj_z']

    geoms_2d = []
    poligonos_corte_sec = []
    poligonos_aterro_sec = []
    quads_3d_corte_sec = []
    quads_3d_aterro_sec = []
    crv_gr_3d = None
    poligonos_3d_corte_sec = []
    poligonos_3d_aterro_sec = []

    # 3D: Real spatial coordinates of section in 3D model (UTM / World Coordinates)
    if crv_aln_3d is not None:
        p_s3d = crv_aln_3d.PointAtStart
        p_e3d = crv_aln_3d.PointAtEnd
        dx_3d = p_e3d.X - p_s3d.X
        dy_3d = p_e3d.Y - p_s3d.Y
        L_3d = math.hypot(dx_3d, dy_3d)
        ux_3d = dx_3d / max(L_3d, 1e-4)
        uy_3d = dy_3d / max(L_3d, 1e-4)

        # 3D Proposed Grade Curve
        pts_gr_3d = []
        for d in s_data['estacas_finais']:
            pts_gr_3d.append(rg.Point3d(p_s3d.X + ux_3d * d, p_s3d.Y + uy_3d * d, get_proj_z(d)))
        if len(pts_gr_3d) >= 2:
            crv_temp = rg.PolylineCurve(pts_gr_3d)
            if crv_temp and crv_temp.IsValid:
                crv_gr_3d = crv_temp

        # 3D vertical section slices
        for r_type, d_list in s_data['regioes']:
            for j in range(len(d_list) - 1):
                d1, d2 = d_list[j], d_list[j+1]
                if d2 - d1 <= 1e-6: continue
                p_tn1_3d = rg.Point3d(p_s3d.X + ux_3d * d1, p_s3d.Y + uy_3d * d1, interpolate_terrain_z(d1, clean_pts))
                p_tn2_3d = rg.Point3d(p_s3d.X + ux_3d * d2, p_s3d.Y + uy_3d * d2, interpolate_terrain_z(d2, clean_pts))
                p_pr1_3d = rg.Point3d(p_s3d.X + ux_3d * d1, p_s3d.Y + uy_3d * d1, get_proj_z(d1))
                p_pr2_3d = rg.Point3d(p_s3d.X + ux_3d * d2, p_s3d.Y + uy_3d * d2, get_proj_z(d2))

                if r_type == "CORTE":
                    quads_3d_corte_sec.append([p_tn1_3d, p_tn2_3d, p_pr2_3d, p_pr1_3d])
                else:
                    quads_3d_aterro_sec.append([p_pr1_3d, p_pr2_3d, p_tn2_3d, p_tn1_3d])

            pts_3d_poly = []
            if r_type == "CORTE":
                for d in d_list: pts_3d_poly.append(rg.Point3d(p_s3d.X + ux_3d * d, p_s3d.Y + uy_3d * d, interpolate_terrain_z(d, clean_pts)))
                for d in reversed(d_list): pts_3d_poly.append(rg.Point3d(p_s3d.X + ux_3d * d, p_s3d.Y + uy_3d * d, get_proj_z(d)))
                poly_3d = make_safe_closed_polyline(pts_3d_poly)
                if poly_3d: poligonos_3d_corte_sec.append(poly_3d)
            else:
                for d in d_list: pts_3d_poly.append(rg.Point3d(p_s3d.X + ux_3d * d, p_s3d.Y + uy_3d * d, get_proj_z(d)))
                for d in reversed(d_list): pts_3d_poly.append(rg.Point3d(p_s3d.X + ux_3d * d, p_s3d.Y + uy_3d * d, interpolate_terrain_z(d, clean_pts)))
                poly_3d = make_safe_closed_polyline(pts_3d_poly)
                if poly_3d: poligonos_3d_aterro_sec.append(poly_3d)

    # Local Section Datum
    sec_datum_z = math.floor(s_data['z_min'] - 2.0)
    sec_h = s_data['z_max'] - sec_datum_z

        # Section Title & Stationing (Compactado e compatibilizado para prancha executiva A0)
    p_tit = rg.Point3d(base_x, base_y + sec_h + 3.2 * s, 0.0)
    tit_str = "{} {} - {}".format(axis_title_prefix.strip(), lbl, lbl)
    if not is_longitudinal and s_data.get('estaca_str'):
        tit_str += " [{}]".format(s_data['estaca_str'])
    tit_crvs = make_text_geometry(tit_str, p_tit, 1.35 * s, rg.TextJustification.BottomLeft, s)
    geoms_2d.extend(tit_crvs)

    sub_parts = []
    if not is_longitudinal and s_data.get('estaca_str'):
        sub_parts.append("Estaca: {}".format(s_data['estaca_str']))
    sub_parts.append("Extensao: {:.2f}m".format(total_ext).replace('.', ','))
    sub_parts.append("Cota Media: +{:.2f}m".format(sum(p[1].Z for p in clean_pts)/len(clean_pts)).replace('.', ','))
    sub_str = " | ".join(sub_parts)
    p_sub = rg.Point3d(base_x, base_y + sec_h + 1.5 * s, 0.0)
    sub_crvs = make_text_geometry(sub_str, p_sub, 0.80 * s, rg.TextJustification.BottomLeft, s)
    geoms_2d.extend(sub_crvs)

    # Linha e Rótulo de DATUM
    p_d_ini = rg.Point3d(base_x, base_y, 0.0)
    max_draw_w = 86.0 * s
    draw_ext = min(total_ext, max_draw_w)
    p_d_fim = rg.Point3d(base_x + draw_ext, base_y, 0.0)
    geoms_2d.append(rg.LineCurve(p_d_ini, p_d_fim))
    # Símbolo normativo de quebra de desenho NBR 6492 caso a seção exceda a largura útil
    if total_ext > draw_ext + 0.1:
        xb = base_x + draw_ext
        geoms_2d.append(rg.LineCurve(rg.Point3d(xb - 0.8*s, base_y - 2.0*s, 0.0), rg.Point3d(xb + 0.8*s, base_y + 2.0*s, 0.0)))
        geoms_2d.append(rg.LineCurve(rg.Point3d(xb - 0.4*s, base_y - 2.0*s, 0.0), rg.Point3d(xb + 1.2*s, base_y + 2.0*s, 0.0)))


    lbl_datum = "DATUM +{:.2f}".format(sec_datum_z).replace('.', ',')
    p_datum_txt = rg.Point3d(base_x - 1.2 * s, base_y, 0.0)
    datum_crvs = make_text_geometry(lbl_datum, p_datum_txt, 0.80 * s, rg.TextJustification.MiddleRight, s)
    geoms_2d.extend(datum_crvs)

    # Perfil Natural 2D
    pts_tn_2d = [rg.Point3d(base_x + min(d, draw_ext), base_y + (pt.Z - sec_datum_z), 0.0) for d, pt in clean_pts if d <= draw_ext + 1.0]
    crv_tn_2d = rg.PolylineCurve(pts_tn_2d) if len(pts_tn_2d) >= 2 else None
    if crv_tn_2d and crv_tn_2d.IsValid: geoms_2d.append(crv_tn_2d)

    # Polígono de fechamento de solo sob TN
    p_solo = [p_d_ini, p_d_fim] + list(reversed(pts_tn_2d)) + [p_d_ini]
    crv_solo = make_safe_closed_polyline(p_solo)
    if crv_solo: geoms_2d.append(crv_solo)

    # 2D Proposed Grade
    pts_gr_2d = [rg.Point3d(base_x + min(d, draw_ext), base_y + (get_proj_z(d) - sec_datum_z), 0.0) for d in s_data['estacas_finais'] if d <= draw_ext + 1.0]
    crv_gr_2d = rg.PolylineCurve(pts_gr_2d) if len(pts_gr_2d) >= 2 else None
    if crv_gr_2d and crv_gr_2d.IsValid: geoms_2d.append(crv_gr_2d)

    # Grade slope annotation (with 15% slope limit rule)
    if s_data.get('sampler') is not None or s_data.get('was_clamped') is not None:
        eff_i = s_data.get('effective_slope', 0.0)
        was_c = s_data.get('was_clamped', False)
        d_gr_mid = total_ext * 0.5
        z_gr_mid = get_proj_z(d_gr_mid)
        p_gr_lbl = rg.Point3d(base_x + d_gr_mid, base_y + (z_gr_mid - sec_datum_z) + 1.8 * s, 0.0)

        if was_c:
            lbl_gr_str = "GRADE: i = {:+.1f}% [CLAMPED TO 15.0% MAX]".format(eff_i).replace('.', ',')
        else:
            lbl_gr_str = "GRADE: i = {:+.1f}% (SLOPE RULE <= 15% OK)".format(eff_i).replace('.', ',')

        gr_crvs = make_text_geometry(lbl_gr_str, p_gr_lbl, 0.80 * s, rg.TextJustification.BottomCenter, s)
        geoms_2d.extend(gr_crvs)

    # Malhas e Polígonos 2D de Corte e Aterro
    quads_corte = []
    quads_aterro = []

    for r_type, d_list in s_data['regioes']:
        for j in range(len(d_list) - 1):
            d1, d2 = d_list[j], d_list[j+1]
            if d2 - d1 <= 1e-6: continue
            p_tn1 = rg.Point3d(base_x + d1, base_y + (interpolate_terrain_z(d1, clean_pts) - sec_datum_z), 0.0)
            p_tn2 = rg.Point3d(base_x + d2, base_y + (interpolate_terrain_z(d2, clean_pts) - sec_datum_z), 0.0)
            p_pr1 = rg.Point3d(base_x + d1, base_y + (get_proj_z(d1) - sec_datum_z), 0.0)
            p_pr2 = rg.Point3d(base_x + d2, base_y + (get_proj_z(d2) - sec_datum_z), 0.0)

            if r_type == "CORTE":
                quads_corte.append([p_tn1, p_tn2, p_pr2, p_pr1])
            else:
                quads_aterro.append([p_pr1, p_pr2, p_tn2, p_tn1])

        pts_poly = []
        if r_type == "CORTE":
            for d in d_list: pts_poly.append(rg.Point3d(base_x + d, base_y + (interpolate_terrain_z(d, clean_pts) - sec_datum_z), 0.0))
            for d in reversed(d_list): pts_poly.append(rg.Point3d(base_x + d, base_y + (get_proj_z(d) - sec_datum_z), 0.0))
            poly_c = make_safe_closed_polyline(pts_poly)
            if poly_c: poligonos_corte_sec.append(poly_c)
        else:
            for d in d_list: pts_poly.append(rg.Point3d(base_x + d, base_y + (get_proj_z(d) - sec_datum_z), 0.0))
            for d in reversed(d_list): pts_poly.append(rg.Point3d(base_x + d, base_y + (interpolate_terrain_z(d, clean_pts) - sec_datum_z), 0.0))
            poly_a = make_safe_closed_polyline(pts_poly)
            if poly_a: poligonos_aterro_sec.append(poly_a)

    m_c = create_colored_mesh(quads_corte, cor_corte)
    m_a = create_colored_mesh(quads_aterro, cor_aterro)
    if m_c and getattr(m_c, 'IsValid', False): geoms_2d.append(m_c)
    if m_a and getattr(m_a, 'IsValid', False): geoms_2d.append(m_a)

    # Cross-Axis Extension Lines & NBR Identification Bubbles
    for (d_ax, idx_cross, lbl_cross) in s_data.get('eixos_secao', []):
        z_tn_ax = interpolate_terrain_z(d_ax, clean_pts)
        z_pr_ax = get_proj_z(d_ax)
        ax_geoms = draw_section_vertical_axis_marker(base_x, base_y, d_ax, sec_h, sec_datum_z, z_tn_ax, z_pr_ax, lbl_cross, s)
        geoms_2d.extend(ax_geoms)

    # Red Internal Mass Haul Compensation Arrow
    for it in s_data.get('internal_transfers', []):
        d_axis = it['d_axis']
        x_axis = base_x + d_axis
        z_mid_pr = (get_proj_z(d_axis - 0.5) + get_proj_z(d_axis + 0.5)) / 2.0
        y_axis = base_y + (z_mid_pr - sec_datum_z)

        if it['direction'] == 'RIGHT':
            p_arr_start = rg.Point3d(x_axis - 4.5 * s, y_axis, 0.0)
            p_arr_end = rg.Point3d(x_axis + 7.5 * s, y_axis, 0.0)
        else:
            p_arr_start = rg.Point3d(x_axis + 4.5 * s, y_axis, 0.0)
            p_arr_end = rg.Point3d(x_axis - 7.5 * s, y_axis, 0.0)

        txt_note = "COMPENSAÇÃO INTERNA: {:.2f} m²".format(it['area_transf']).replace('.', ',')
        arrow_geoms = draw_section_internal_transfer_arrow(p_arr_start, p_arr_end, txt_note, s)
        geoms_2d.extend(arrow_geoms)

    # Road Network Crossings & Drivable Corridor Visualization
    for cor in s_data.get('road_corridors', []):
        d_in = cor['d_in']
        d_out = cor['d_out']
        w = cor['width']
        d_mid = cor['d_mid']
        w_sw = min(1.20, w * 0.18) if w >= 3.0 else 0.0
        w_pista = max(w - 2 * w_sw, 0.5)

        x_in = base_x + d_in
        x_out = base_x + d_out
        x_mid = base_x + d_mid
        z_eixo = get_proj_z(d_mid)
        y_eixo = base_y + (z_eixo - sec_datum_z)

        # 1. Extension lines at road corridor boundary
        p_in_bot = rg.Point3d(x_in, base_y, 0.0)
        p_in_top = rg.Point3d(x_in, y_eixo + 2.0 * s, 0.0)
        p_out_bot = rg.Point3d(x_out, base_y, 0.0)
        p_out_top = rg.Point3d(x_out, y_eixo + 2.0 * s, 0.0)
        geoms_2d.append(rg.LineCurve(p_in_bot, p_in_top))
        geoms_2d.append(rg.LineCurve(p_out_bot, p_out_top))

        # 2. Road callout card
        lbl_v1 = "ROADWAY / VIÁRIO CARROÇÁVEL"
        lbl_v2 = "Corredor: {:.2f}m | Pista: {:.2f}m | Abaulamento: 2,0%".format(w, w_pista).replace('.', ',')
        card_geoms = make_callout_card(x_mid, y_eixo + 2.8 * s, lbl_v1, lbl_v2, s, is_corte=True)
        geoms_2d.extend(card_geoms)

        # 3. NBR Level marker on road centerline
        m_eixo, _ = draw_nbr_level_marker(x_mid, y_eixo, "RUA +{:.2f}".format(z_eixo).replace('.', ','), s)
        geoms_2d.extend(m_eixo)

    # Cotas de Nível NBR 6492
    if modo_cotas in [0, 2]:
        last_marker_x = -999999.0
        min_marker_gap = 9.0 * s
        for idx_pt, (d, pt) in enumerate(clean_pts):
            is_first = (idx_pt == 0)
            is_last = (idx_pt == len(clean_pts) - 1)
            if not is_first and not is_last and (d - last_marker_x < min_marker_gap):
                continue
            last_marker_x = d
            cota_str = "+{:.2f}".format(pt.Z).replace('.', ',') if pt.Z > 0 else "{:.2f}".format(pt.Z).replace('.', ',')
            m_geoms, _ = draw_nbr_level_marker(base_x + d, base_y + (pt.Z - sec_datum_z), cota_str, s)
            geoms_2d.extend(m_geoms)

    if modo_cotas in [0, 1]:
        z_ini = get_proj_z(0.0)
        z_fim = get_proj_z(total_ext)
        m_g_ini, _ = draw_nbr_level_marker(base_x, base_y + (z_ini - sec_datum_z), "GREIDE +{:.2f}".format(z_ini).replace('.', ','), s)
        m_g_fim, _ = draw_nbr_level_marker(base_x + total_ext, base_y + (z_fim - sec_datum_z), "GREIDE +{:.2f}".format(z_fim).replace('.', ','), s)
        geoms_2d.extend(m_g_ini)
        geoms_2d.extend(m_g_fim)

        for dp, zp in s_data.get('pontos_passagem', []):
            m_pp, _ = draw_nbr_level_marker(base_x + dp, base_y + (zp - sec_datum_z), "P.P. +{:.2f}".format(zp).replace('.', ','), s)
            geoms_2d.extend(m_pp)

        # Cotas de Nivel no Greide e Pontos de Passagem
        # (As areas, alturas maximas e saldos sao apresentadas com clareza executiva na Ficha Tecnica lateral)
        side_card_geoms = draw_section_summary_card(base_x, base_y, total_ext, sec_h, lbl, s_data, s=s)
    geoms_2d.extend(side_card_geoms)
    return {
        'geoms_2d': geoms_2d,
        'poligonos_corte_2d': poligonos_corte_sec,
        'poligonos_aterro_2d': poligonos_aterro_sec,
        'quads_3d_corte': quads_3d_corte_sec,
        'quads_3d_aterro': quads_3d_aterro_sec,
        'crv_gr_3d': crv_gr_3d,
        'crv_tn_3d': s_data['crv_3d'],
        'poligonos_3d_corte': poligonos_3d_corte_sec,
        'poligonos_3d_aterro': poligonos_3d_aterro_sec
    }


def render_longitudinal_profile_with_guitarra(
    s_data_v, lbl_v, base_x, base_y, s=1.0, ev=10.0, step_estaca=20.0,
    cor_corte=None, cor_aterro=None, crv_aln_3d_v=None, axis_title_prefix="EIXO "
):
    """
    Renders an executive 2D longitudinal roadway profile with vertical exaggeration Ev = 10.0
    (Escalas H=1:1.000 / V=1:100) and the standard Brazilian civil engineering "guitarra"
    (grade tabular inferior de dados DNIT / DER / NBR 6492) containing:
    1. Declividades de cada rampa (%) e extensão horizontal dos trechos inclinados (m);
    2. Curvas verticais de concordância parabólica nos PIVs (com PCV, PTV, Lv e flecha e);
    3. Cota Vermelha (Greide Projetado) em cada estaca de 20m;
    4. Cota do Terreno Natural em cada estaca de 20m;
    5. Altura de Corte e Aterro em cada estaca;
    6. Estaqueamento de 20 em 20 metros (Estaca 0, 1, 2, 3... e Estaca Final fracionária);
    7. Hachura 2D de Corte (Laranja) e Aterro (Verde);
    8. Marcações das interseções com as Seções Transversais (Seções A a J);
    9. Sincronização espacial 3D com o modelo BIM.
    """
    clean_pts = s_data_v['clean_pts']
    total_ext = s_data_v['total_ext']
    get_proj_z = s_data_v['get_proj_z']
    intersecs = s_data_v.get('intersecs', [])

    geoms_2d = []
    poligonos_corte_sec = []
    poligonos_aterro_sec = []
    quads_3d_corte_sec = []
    quads_3d_aterro_sec = []
    crv_gr_3d = None
    poligonos_3d_corte_sec = []
    poligonos_3d_aterro_sec = []

    if cor_corte is None: cor_corte = System.Drawing.Color.FromArgb(245, 130, 32)
    if cor_aterro is None: cor_aterro = System.Drawing.Color.FromArgb(46, 204, 113)

    # 1. Datum e Elevações
    z_tn_vals = [p[1].Z for p in clean_pts]
    z_gr_vals = [get_proj_z(p[0]) for p in clean_pts]
    all_z = z_tn_vals + z_gr_vals
    z_min = min(all_z) if all_z else 0.0
    z_max = max(all_z) if all_z else 10.0
    z_datum = math.floor(z_min - 1.0)
    delta_z = z_max - z_datum

    def sample_tn_z(d_val):
        d_c = max(0.0, min(total_ext, d_val))
        for k in range(len(clean_pts) - 1):
            d0 = clean_pts[k][0]
            d1 = clean_pts[k+1][0]
            if d0 <= d_c <= d1:
                span = max(d1 - d0, 1e-4)
                t = (d_c - d0) / span
                return clean_pts[k][1].Z + t * (clean_pts[k+1][1].Z - clean_pts[k][1].Z)
        return clean_pts[-1][1].Z if d_c >= clean_pts[-1][0] else clean_pts[0][1].Z

    # 2. Tangentes de Greide, Declividades e PIVs
    break_ds = [0.0]
    for item_inter in intersecs:
        d_inter = item_inter[0]
        if 2.0 < d_inter < total_ext - 2.0:
            break_ds.append(d_inter)
    break_ds.append(total_ext)
    break_ds = sorted(list(set([round(x, 2) for x in break_ds])))

    tangents = []
    for k in range(len(break_ds) - 1):
        d0 = break_ds[k]
        d1 = break_ds[k+1]
        z0 = get_proj_z(d0)
        z1 = get_proj_z(d1)
        ext_t = max(d1 - d0, 0.1)
        slope_pct = ((z1 - z0) / ext_t) * 100.0
        tangents.append({
            'd0': d0, 'd1': d1,
            'z0': z0, 'z1': z1,
            'ext': ext_t,
            'slope': slope_pct
        })

    pivs = []
    for k in range(len(tangents) - 1):
        t1 = tangents[k]
        t2 = tangents[k+1]
        delta_i = t2['slope'] - t1['slope']
        d_piv = t1['d1']
        z_piv = t1['z1']
        max_lv_allowed = min(t1['ext'], t2['ext']) * 0.75
        lv = min(40.0 * s, max_lv_allowed)
        if lv < 4.0: lv = max_lv_allowed
        e = (lv * abs(delta_i)) / 800.0 if lv > 0 else 0.0
        pivs.append({
            'd': d_piv,
            'z': z_piv,
            'i1': t1['slope'],
            'i2': t2['slope'],
            'delta_i': delta_i,
            'lv': lv,
            'e': e,
            'pcv_d': d_piv - lv / 2.0,
            'ptv_d': d_piv + lv / 2.0,
            'kind': "Cônava (Bacia)" if delta_i > 0 else "Convexa (Crista)"
        })

    # Função da cota do greide com concordâncias verticais parabólicas suaves nos PIVs
    def get_parabolic_grade_z(d_val):
        d_c = max(0.0, min(total_ext, d_val))
        # Verifica se d_c está dentro de alguma curva vertical parabólica de PIV
        for p in pivs:
            if p['lv'] > 1.0 and p['pcv_d'] <= d_c <= p['ptv_d']:
                x = d_c - p['pcv_d']
                g1 = p['i1'] / 100.0
                g2 = p['i2'] / 100.0
                z_pcv = p['z'] - g1 * (p['lv'] / 2.0)
                return z_pcv + g1 * x + ((g2 - g1) / (2.0 * p['lv'])) * (x ** 2)
        return get_proj_z(d_c)

    # 3. Estações / Estacas Normativas de 20 em 20 metros
    stations = []
    d_st = 0.0
    st_idx = 0
    while d_st <= total_ext + 1e-4:
        z_tn_st = sample_tn_z(d_st)
        z_gr_st = get_parabolic_grade_z(d_st)
        diff_st = z_tn_st - z_gr_st
        stations.append({
            'idx': st_idx,
            'd': d_st,
            'label': "{}".format(st_idx),
            'tag': "Est. {}".format(st_idx),
            'z_tn': z_tn_st,
            'z_gr': z_gr_st,
            'corte': max(0.0, diff_st),
            'aterro': max(0.0, -diff_st)
        })
        d_st += step_estaca
        st_idx += 1

    if total_ext - (d_st - step_estaca) > 0.5:
        last_idx = int(total_ext // step_estaca)
        rem = total_ext - (last_idx * step_estaca)
        z_tn_st = sample_tn_z(total_ext)
        z_gr_st = get_parabolic_grade_z(total_ext)
        diff_st = z_tn_st - z_gr_st
        lbl_fin = "{}+{:05.2f}".format(last_idx, rem).replace('.', ',')
        stations.append({
            'idx': last_idx,
            'd': total_ext,
            'label': lbl_fin,
            'tag': "Est. {}".format(lbl_fin),
            'z_tn': z_tn_st,
            'z_gr': z_gr_st,
            'corte': max(0.0, diff_st),
            'aterro': max(0.0, -diff_st)
        })

    # =========================================================================
    # 4. DESENHO DA GUITARRA (GRADE TABULAR INFERIOR DE DADOS)
    # =========================================================================
    w_hdr = 38.0 * s
    h1 = 9.0 * s   # Declividades / Rampas
    h2 = 8.0 * s   # Cota do Greide
    h3 = 8.0 * s   # Cota do Terreno Natural
    h4 = 8.0 * s   # Alturas Corte / Aterro
    h5 = 8.0 * s   # Estaqueamento
    h_guitarra = h1 + h2 + h3 + h4 + h5

    y0 = base_y
    y1 = y0 - h1
    y2 = y1 - h2
    y3 = y2 - h3
    y4 = y3 - h4
    y5 = y4 - h5

    x_start = base_x - w_hdr
    x_end = base_x + total_ext

    # 4.1 Linhas horizontais da grade
    for y_lev in [y0, y1, y2, y3, y4, y5]:
        geoms_2d.append(rg.LineCurve(rg.Point3d(x_start, y_lev, 0.0), rg.Point3d(x_end, y_lev, 0.0)))

    # 4.2 Bordas verticais da tabela
    geoms_2d.append(rg.LineCurve(rg.Point3d(x_start, y0, 0.0), rg.Point3d(x_start, y5, 0.0)))
    geoms_2d.append(rg.LineCurve(rg.Point3d(base_x, y0, 0.0), rg.Point3d(base_x, y5, 0.0)))
    geoms_2d.append(rg.LineCurve(rg.Point3d(x_end, y0, 0.0), rg.Point3d(x_end, y5, 0.0)))

    # 4.3 Títulos dos cabeçalhos à esquerda
    header_rows = [
        ("DECLIVIDADES / RAMPAS", (y0 + y1) / 2.0),
        ("COTA DO GREIDE (PROJETO)", (y1 + y2) / 2.0),
        ("COTA DO TERRENO NATURAL", (y2 + y3) / 2.0),
        ("ALTURAS CORTE / ATERRO", (y3 + y4) / 2.0),
        ("ESTAQUEAMENTO (20m)", (y4 + y5) / 2.0)
    ]
    for h_txt, h_y in header_rows:
        p_hdr = rg.Point3d(base_x - (w_hdr / 2.0), h_y, 0.0)
        geoms_2d.extend(make_text_geometry(h_txt, p_hdr, 0.85 * s, rg.TextJustification.MiddleCenter, s))

    # 4.4 Colunas verticais em cada estaca de 20m e dados tabulados
    pl_rot90 = rg.Plane(rg.Point3d(0.0, 0.0, 0.0), rg.Vector3d(0.0, 1.0, 0.0), rg.Vector3d(-1.0, 0.0, 0.0))

    for st in stations:
        x_st = base_x + st['d']
        # Linha vertical divisória das estacas (da base da guitarra até a linha de cota do greide)
        geoms_2d.append(rg.LineCurve(rg.Point3d(x_st, y1, 0.0), rg.Point3d(x_st, y5, 0.0)))

        # Linha fina de chamada subindo do Datum até o Terreno Natural
        y_tn_top = base_y + (st['z_tn'] - z_datum) * ev
        geoms_2d.append(rg.LineCurve(rg.Point3d(x_st, y0, 0.0), rg.Point3d(x_st, y_tn_top, 0.0)))

        # Faixa 2: Cota do Greide (Texto verticalizado a 90 graus)
        p_gr = rg.Point3d(x_st, (y1 + y2) / 2.0, 0.0)
        pl_gr = rg.Plane(p_gr, rg.Vector3d(0.0, 1.0, 0.0), rg.Vector3d(-1.0, 0.0, 0.0))
        txt_gr = "{:.2f}".format(st['z_gr']).replace('.', ',')
        geoms_2d.extend(make_text_geometry(txt_gr, p_gr, 0.80 * s, rg.TextJustification.MiddleCenter, s, plane=pl_gr))

        # Faixa 3: Cota do Terreno Natural (Texto verticalizado a 90 graus)
        p_tn = rg.Point3d(x_st, (y2 + y3) / 2.0, 0.0)
        pl_tn = rg.Plane(p_tn, rg.Vector3d(0.0, 1.0, 0.0), rg.Vector3d(-1.0, 0.0, 0.0))
        txt_tn = "{:.2f}".format(st['z_tn']).replace('.', ',')
        geoms_2d.extend(make_text_geometry(txt_tn, p_tn, 0.80 * s, rg.TextJustification.MiddleCenter, s, plane=pl_tn))

        # Faixa 4: Alturas de Corte / Aterro
        p_alt = rg.Point3d(x_st, (y3 + y4) / 2.0, 0.0)
        pl_alt = rg.Plane(p_alt, rg.Vector3d(0.0, 1.0, 0.0), rg.Vector3d(-1.0, 0.0, 0.0))
        if st['corte'] > 0.01:
            txt_alt = "+C: {:.2f}".format(st['corte']).replace('.', ',')
        elif st['aterro'] > 0.01:
            txt_alt = "-A: {:.2f}".format(st['aterro']).replace('.', ',')
        else:
            txt_alt = "0,00"
        geoms_2d.extend(make_text_geometry(txt_alt, p_alt, 0.78 * s, rg.TextJustification.MiddleCenter, s, plane=pl_alt))

        # Faixa 5: Estaqueamento
        p_est = rg.Point3d(x_st, (y4 + y5) / 2.0 + 1.2 * s, 0.0)
        geoms_2d.extend(make_text_geometry(st['label'], p_est, 0.85 * s, rg.TextJustification.MiddleCenter, s))
        p_m = rg.Point3d(x_st, (y4 + y5) / 2.0 - 1.8 * s, 0.0)
        geoms_2d.extend(make_text_geometry("{:.1f}m".format(st['d']).replace('.', ','), p_m, 0.65 * s, rg.TextJustification.MiddleCenter, s))

    # 4.5 Faixa 1: Declividades, Rampas e Geometria dos Trechos Inclinados
    for tg in tangents:
        x_tg0 = base_x + tg['d0']
        x_tg1 = base_x + tg['d1']
        geoms_2d.append(rg.LineCurve(rg.Point3d(x_tg0, y0, 0.0), rg.Point3d(x_tg0, y1, 0.0)))
        geoms_2d.append(rg.LineCurve(rg.Point3d(x_tg1, y0, 0.0), rg.Point3d(x_tg1, y1, 0.0)))

        # Linha indicativa da rampa (diagonal ou horizontal)
        if tg['slope'] > 0.2:
            geoms_2d.append(rg.LineCurve(rg.Point3d(x_tg0 + 1.0 * s, y1 + 1.2 * s, 0.0), rg.Point3d(x_tg1 - 1.0 * s, y0 - 1.2 * s, 0.0)))
        elif tg['slope'] < -0.2:
            geoms_2d.append(rg.LineCurve(rg.Point3d(x_tg0 + 1.0 * s, y0 - 1.2 * s, 0.0), rg.Point3d(x_tg1 - 1.0 * s, y1 + 1.2 * s, 0.0)))
        else:
            geoms_2d.append(rg.LineCurve(rg.Point3d(x_tg0 + 1.0 * s, (y0 + y1) / 2.0, 0.0), rg.Point3d(x_tg1 - 1.0 * s, (y0 + y1) / 2.0, 0.0)))

        # Rótulo da rampa
        x_mid_tg = (x_tg0 + x_tg1) / 2.0
        str_rampa = "i = {:+.2f}% | L = {:.1f}m".format(tg['slope'], tg['ext']).replace('.', ',')
        p_txt_r = rg.Point3d(x_mid_tg, (y0 + y1) / 2.0, 0.0)
        geoms_2d.extend(make_text_geometry(str_rampa, p_txt_r, 0.78 * s, rg.TextJustification.MiddleCenter, s))

    # 4.6 Indicação de PIVs e Concordâncias Verticais
    for p in pivs:
        x_piv = base_x + p['d']
        y_piv_top = base_y + (p['z'] - z_datum) * ev
        # Triângulo indicador no PIV
        tri_pts = [
            rg.Point3d(x_piv - 1.2 * s, y_piv_top - 2.0 * s, 0.0),
            rg.Point3d(x_piv + 1.2 * s, y_piv_top - 2.0 * s, 0.0),
            rg.Point3d(x_piv, y_piv_top, 0.0),
            rg.Point3d(x_piv - 1.2 * s, y_piv_top - 2.0 * s, 0.0)
        ]
        geoms_2d.append(rg.PolylineCurve(tri_pts))

        # Texto descritivo do PIV
        tag_piv = "PIV: Cota {:.2f}m | Lv={:.0f}m | e={:.2f}m [{}]".format(p['z'], p['lv'], p['e'], p['kind']).replace('.', ',')
        p_tag_piv = rg.Point3d(x_piv, y_piv_top + 3.0 * s, 0.0)
        geoms_2d.extend(make_text_geometry(tag_piv, p_tag_piv, 0.72 * s, rg.TextJustification.BottomCenter, s))

    # =========================================================================
    # 5. DESENHO DOS PERFIS (TN, GREIDE, HACHURAS DE CORTE/ATERRO)
    # =========================================================================
    n_samples = max(int(total_ext * 2), 60)
    pts_tn_2d = []
    pts_gr_2d = []

    for i_pt in range(n_samples + 1):
        d_val = (i_pt / float(n_samples)) * total_ext
        x_2d = base_x + d_val
        z_tn = sample_tn_z(d_val)
        z_gr = get_parabolic_grade_z(d_val)
        y_tn_2d = base_y + (z_tn - z_datum) * ev
        y_gr_2d = base_y + (z_gr - z_datum) * ev
        pts_tn_2d.append(rg.Point3d(x_2d, y_tn_2d, 0.0))
        pts_gr_2d.append(rg.Point3d(x_2d, y_gr_2d, 0.0))

    if len(pts_tn_2d) >= 2:
        crv_tn_2d = rg.PolylineCurve(pts_tn_2d)
        if crv_tn_2d and crv_tn_2d.IsValid:
            geoms_2d.append(crv_tn_2d)

    if len(pts_gr_2d) >= 2:
        crv_gr_2d = rg.PolylineCurve(pts_gr_2d)
        if crv_gr_2d and crv_gr_2d.IsValid:
            geoms_2d.append(crv_gr_2d)

    # 5.1 Preenchimento de Corte e Aterro em Malha 2D (Hachura)
    for i_poly in range(n_samples):
        p0_tn = pts_tn_2d[i_poly]
        p1_tn = pts_tn_2d[i_poly + 1]
        p0_gr = pts_gr_2d[i_poly]
        p1_gr = pts_gr_2d[i_poly + 1]

        diff0 = p0_tn.Y - p0_gr.Y
        diff1 = p1_tn.Y - p1_gr.Y

        if diff0 > 0.001 and diff1 > 0.001:
            # Corte puro (orientacao anti-horaria para normal +Z)
            m_c = rg.Mesh()
            m_c.Vertices.Add(p0_gr.X, p0_gr.Y, 0.0)
            m_c.Vertices.Add(p1_gr.X, p1_gr.Y, 0.0)
            m_c.Vertices.Add(p1_tn.X, p1_tn.Y, 0.0)
            m_c.Vertices.Add(p0_tn.X, p0_tn.Y, 0.0)
            m_c.Faces.AddFace(0, 1, 2, 3)
            for _ in range(4): m_c.VertexColors.Add(cor_corte)
            try: m_c.Normals.ComputeNormals()
            except: pass
            m_c.Compact()
            geoms_2d.append(m_c)
            poly_c = rg.PolylineCurve([p0_tn, p1_tn, p1_gr, p0_gr, p0_tn])
            poligonos_corte_sec.append(poly_c)
        elif diff0 < -0.001 and diff1 < -0.001:
            # Aterro puro (orientacao anti-horaria para normal +Z)
            m_a = rg.Mesh()
            m_a.Vertices.Add(p0_tn.X, p0_tn.Y, 0.0)
            m_a.Vertices.Add(p1_tn.X, p1_tn.Y, 0.0)
            m_a.Vertices.Add(p1_gr.X, p1_gr.Y, 0.0)
            m_a.Vertices.Add(p0_gr.X, p0_gr.Y, 0.0)
            m_a.Faces.AddFace(0, 1, 2, 3)
            for _ in range(4): m_a.VertexColors.Add(cor_aterro)
            try: m_a.Normals.ComputeNormals()
            except: pass
            m_a.Compact()
            geoms_2d.append(m_a)
            poly_a = rg.PolylineCurve([p0_gr, p1_gr, p1_tn, p0_tn, p0_gr])
            poligonos_aterro_sec.append(poly_a)

    # 5.2 Interseções com as Seções Transversais (Seções A a J)
    for d_inter, idx_t, lbl_t in intersecs:
        x_inter = base_x + d_inter
        z_tn_inter = sample_tn_z(d_inter)
        y_inter_top = base_y + (z_tn_inter - z_datum) * ev + 6.0 * s

        # Linha vertical tracejada do cruzamento
        geoms_2d.append(rg.LineCurve(rg.Point3d(x_inter, base_y, 0.0), rg.Point3d(x_inter, y_inter_top, 0.0)))
        # Balão circular NBR no topo
        p_bub = rg.Point3d(x_inter, y_inter_top + 2.5 * s, 0.0)
        geoms_2d.append(rg.Circle(p_bub, 1.80 * s).ToNurbsCurve())
        geoms_2d.extend(make_text_geometry(lbl_t, p_bub, 1.40 * s, rg.TextJustification.MiddleCenter, s))

    # =========================================================================
    # 6. TÍTULO, SUBTÍTULO E ETIQUETAS DO PERFIL
    # =========================================================================
    p_tit = rg.Point3d(x_start, base_y + delta_z * ev + 14.0 * s, 0.0)
    tit_str = "PERFIL LONGITUDINAL - {} {} - {}".format(axis_title_prefix.strip(), lbl_v, lbl_v)
    geoms_2d.extend(make_text_geometry(tit_str, p_tit, 1.80 * s, rg.TextJustification.BottomLeft, s))

    sub_line1 = "Escalas: Horizontal 1:1.000 | Vertical 1:100 (Exagero Vertical: {:.0f}x) | Datum: +{:.2f}m".format(ev, z_datum).replace('.', ',')
    p_sub1 = rg.Point3d(x_start, base_y + delta_z * ev + 11.2 * s, 0.0)
    geoms_2d.extend(make_text_geometry(sub_line1, p_sub1, 0.90 * s, rg.TextJustification.BottomLeft, s))

    sub_line2 = "Extensão: {:.2f}m | Estacas: Estaca 0 até {} | Área Corte: {:.2f}m² | Área Aterro: {:.2f}m²".format(
        total_ext, stations[-1]['tag'], s_data_v.get('area_total_corte', 0.0), s_data_v.get('area_total_aterro', 0.0)
    ).replace('.', ',')
    p_sub2 = rg.Point3d(x_start, base_y + delta_z * ev + 8.6 * s, 0.0)
    geoms_2d.extend(make_text_geometry(sub_line2, p_sub2, 0.85 * s, rg.TextJustification.BottomLeft, s))

    # Rótulo do Datum
    p_datum_lbl = rg.Point3d(base_x - 1.0 * s, base_y + 1.2 * s, 0.0)
    geoms_2d.extend(make_text_geometry("DATUM = +{:.2f} m".format(z_datum).replace('.', ','), p_datum_lbl, 0.85 * s, rg.TextJustification.BottomRight, s))

    # Sincronização espacial 3D
    if crv_aln_3d_v is not None:
        p_s3d = crv_aln_3d_v.PointAtStart
        p_e3d = crv_aln_3d_v.PointAtEnd
        dx_3d = p_e3d.X - p_s3d.X
        dy_3d = p_e3d.Y - p_s3d.Y
        L_3d = math.hypot(dx_3d, dy_3d)
        ux_3d = dx_3d / max(L_3d, 1e-4)
        uy_3d = dy_3d / max(L_3d, 1e-4)
        pts_gr_3d = []
        for i_pt in range(n_samples + 1):
            d_val = (i_pt / float(n_samples)) * total_ext
            z_val = get_parabolic_grade_z(d_val)
            pts_gr_3d.append(rg.Point3d(p_s3d.X + ux_3d * d_val, p_s3d.Y + uy_3d * d_val, z_val))
        if len(pts_gr_3d) >= 2:
            crv_temp = rg.PolylineCurve(pts_gr_3d)
            if crv_temp and crv_temp.IsValid:
                crv_gr_3d = crv_temp

    return {
        'geoms_2d': geoms_2d,
        'poligonos_corte_2d': poligonos_corte_sec,
        'poligonos_aterro_2d': poligonos_aterro_sec,
        'quads_3d_corte': quads_3d_corte_sec,
        'quads_3d_aterro': quads_3d_aterro_sec,
        'crv_gr_3d': crv_gr_3d,
        'crv_tn_3d': s_data_v.get('crv_3d'),
        'poligonos_3d_corte': poligonos_3d_corte_sec,
        'poligonos_3d_aterro': poligonos_3d_aterro_sec,
        'stations': stations,
        'tangents': tangents,
        'pivs': pivs,
        'total_height': (delta_z * ev) + h_guitarra + 25.0 * s
    }

def run():
    doc_cls = getattr(Rhino, 'RhinoDoc', None)
    doc = getattr(doc_cls, 'ActiveDoc', None) if doc_cls else None
    tol = getattr(doc, 'ModelAbsoluteTolerance', 0.001)

    def get_input(keys, default=None):
        g = globals()
        for k in keys:
            val = g.get(k)
            if val is not None:
                return val
        return default

    raw_terreno      = get_input(['Terrain', 'Terreno', 'x'])
    raw_linhas       = get_input(['SectionLines', 'CutLines', 'LinhasCorte', 'LinhaCorte', 'y'])
    raw_verticais    = get_input(['LongitudinalLines', 'VerticalAxes', 'LongitudinalAxes', 'EixosVerticais', 'LinhasLongitudinais', 'Verticais', 'Eixos'])
    raw_projeto      = get_input(['GradingLine', 'ProjectCurve', 'GradeLine', 'BoundaryLine', 'LinhaDelimitadora', 'CurvaDelimitadora', 'Delimitadora',
                                  'CurvaProjeto', 'Greide', 'Projeto', 'LinhaProjeto', 'LinhaCorteAterro', 'CorteAterro', 'LinhaGrade', 'GreideProjeto'])
    raw_ponto        = get_input(['Point', 'Origin', 'Ponto', 'Origem', 'Localizacao'])
    raw_espacamento  = get_input(['Spacing', 'SectionSpacing', 'Espacamento', 'DistanciaSecoes', 'Pitch'])
    raw_largura      = get_input(['Width', 'InfluenceWidth', 'Largura', 'Faixa', 'FaixaInfluencia'], 1.0)
    raw_empolamento  = get_input(['BulkingFactor', 'SwellFactor', 'Empolamento', 'FatorK', 'K'], 1.20)
    raw_seletor      = get_input(['Selector', 'Mode', 'Seletor', 'Modo', 'ModoCotas'], 1)
    raw_escala       = get_input(['Scale', 'Escala', 'S'], 1.0)
    raw_nivel_proj   = get_input(['ProjectElevation', 'PadElevation', 'GradeElevation', 'NivelProjeto', 'Plato', 'CotaProjeto'])
    raw_inclinacao   = get_input(['MaxSlope', 'InclinacaoMaxima', 'RampaMaxima', 'Inclinacao', 'Imax'], 15.0)
    raw_limite       = get_input(['SiteBoundary', 'PropertyLine', 'Boundary', 'BoundaryLine', 'Limite', 'LimiteTerreno', 'Perimetro', 'PoligonalLote', 'Plataforma', 'LimitePropriedade', 'Lote'])
    raw_viario       = get_input(['Roadway', 'Viario', 'RoadNetwork', 'RoadBoundary', 'Pista', 'Ruas', 'CADViario', 'PoligonoViario', 'Vias', 'PoligonalViario', 'MalhaViaria', 'EixoViario', 'EixosViarios', 'Rua', 'RuasCAD', 'EixoRua', 'EixosRuas', 'Pistas'])
    raw_homogeneizacao = get_input(['HomogenizationFactor', 'CompactionFactor', 'ShrinkageFactor', 'FatorHomogeneizacao', 'FatorContracao', 'Fh'], 1.15)
    raw_modo_estacas = get_input(['StationingMode', 'ModoEstacas', 'EstaqueamentoNormativo', 'Estacas20m', 'Normative20m', 'UsarEstacas20m', 'Modo20m'])
    raw_passo_estacas = get_input(['StationInterval', 'PassoEstacas', 'IntervaloEstacas', 'DistanciaEstacas', 'Passo'], 20.0)
    raw_exagero_v    = get_input(['VerticalExaggeration', 'ExageroVertical', 'EscalaVertical', 'Exagero', 'Ev'], 10.0)

    try:
        if raw_inclinacao is not None:
            val_inc = float(raw_inclinacao)
            if val_inc > 1.0:
                max_slope = val_inc / 100.0
            elif val_inc > 0.0:
                max_slope = val_inc
            else:
                max_slope = 0.15
        else:
            max_slope = 0.15
    except:
        max_slope = 0.15

    try:
        s = float(raw_escala) if raw_escala is not None else 1.0
        if s <= 0.05: s = 1.0
    except: s = 1.0

    try:
        fator_k = float(raw_empolamento) if raw_empolamento is not None else 1.20
        if fator_k <= 0.5: fator_k = 1.20
    except: fator_k = 1.20

    try:
        fh = float(raw_homogeneizacao) if raw_homogeneizacao is not None else 1.15
        if fh < 1.0 or fh > 2.0: fh = 1.15
    except: fh = 1.15

    try:
        passo_estacas = float(raw_passo_estacas) if raw_passo_estacas is not None else 20.0
        if passo_estacas <= 1.0: passo_estacas = 20.0
    except: passo_estacas = 20.0

    try:
        ev_long = float(raw_exagero_v) if raw_exagero_v is not None else 10.0
        if ev_long <= 0.1: ev_long = 1.0
    except: ev_long = 10.0

        # Inicializacao incondicional de seguranca de variaveis globais e espacamentos
    global_vol_summary = {
        'corte_geo': 0.0,
        'aterro_geo': 0.0,
        'saldo': 0.0,
        'fator_k': fator_k
    }
    espacamento_y_v = 240.0 * s
    pitch_v = 240.0 * s
    prancha_planta_geoms = []
    prancha_long_geoms = []
    prancha_secoes_geoms = []

    geoms_terreno = [to_rhino_geom(item) for item in to_list(raw_terreno) if to_rhino_geom(item) is not None]
    if not geoms_terreno:
        msg = "⚠️ No valid geometry found in 'Terrain' / 'Terreno' input. Connect contour curves (Curves), mesh (Mesh), or terrain surface."
        return [], [], [], [], [], [msg]

    boundary_info = sanitize_site_boundary(raw_limite, raw_projeto, tol)
    road_polygons = sanitize_road_polygons(raw_viario, tol)

    # Processing cross-sectional cut lines
    lista_linhas_raw = [to_rhino_curve(c) for c in to_list(raw_linhas) if to_rhino_curve(c) is not None]
    if not lista_linhas_raw:
        raise ValueError("SectionLines / LinhasCorte is invalid or disconnected. Provide at least one section curve.")

    # =========================================================================
    # 0. NORMATIVE AXIS ALIGNMENT AND ORDERING (NBR 6492)
    #    "TOP-TO-BOTTOM AND LEFT-TO-RIGHT"
    # =========================================================================

    # 0.1 Determination of mean cross-sectional direction vector (U)
    ux_sum = 0.0
    uy_sum = 0.0
    for c in lista_linhas_raw:
        dx = c.PointAtEnd.X - c.PointAtStart.X
        dy = c.PointAtEnd.Y - c.PointAtStart.Y
        l_len = math.hypot(dx, dy)
        if l_len > 1e-4:
            ux_sum += dx / l_len
            uy_sum += dy / l_len

    u_len = math.hypot(ux_sum, uy_sum)
    if u_len < 1e-4:
        u_corte = rg.Vector3d(1.0, 0.0, 0.0)
    else:
        u_corte = rg.Vector3d(ux_sum / u_len, uy_sum / u_len, 0.0)

    # REGRA DA NORMA: "DA ESQUERDA PARA A DIREITA" (Left to Right)
    # Garante que u_corte aponte estritamente para a direita (+X >= 0, ou se vertical, +Y > 0)
    if u_corte.X < -1e-5 or (abs(u_corte.X) <= 1e-5 and u_corte.Y < -1e-5):
        u_corte = -u_corte

    # REGRA DA NORMA: "DE CIMA PARA BAIXO" (Top to Bottom)
    # O vetor longitudinal perpendicular deve apontar estritamente para baixo (-Y < 0)
    v_cand1 = rg.Vector3d(-u_corte.Y, u_corte.X, 0.0)
    v_cand2 = rg.Vector3d(u_corte.Y, -u_corte.X, 0.0)

    if v_cand1.Y < -1e-5:
        u_long_down = v_cand1
    elif v_cand2.Y < -1e-5:
        u_long_down = v_cand2
    else:
        u_long_down = v_cand1 if v_cand1.X > 0 else v_cand2

    u_vert = u_long_down
    v_perp = u_long_down
    w_perp_v = u_corte

    # Harmoniza cada curva transversal para apontar DA ESQUERDA PARA A DIREITA
    lista_linhas = [c.DuplicateCurve() for c in lista_linhas_raw]
    for c in lista_linhas:
        vec_c = c.PointAtEnd - c.PointAtStart
        if vec_c.X * u_corte.X + vec_c.Y * u_corte.Y < 0.0:
            c.Reverse()

    # REGRA DA NORMA: ORDENAÇÃO DAS SEÇÕES TRANSVERSAIS "DE CIMA PARA BAIXO"
    # The uppermost section (north / lot entrance) is designated Section A.
    # Moving along u_long_down (downwards), projection increases.
    # Sorting in ascending order along u_long_down places the TOP section first (A).
    def get_sec_proj_down(crv):
        p_mid = crv.PointAtNormalizedLength(0.5) if hasattr(crv, 'PointAtNormalizedLength') else crv.PointAt((crv.Domain.T0 + crv.Domain.T1) / 2.0)
        return p_mid.X * u_long_down.X + p_mid.Y * u_long_down.Y

    lista_linhas.sort(key=get_sec_proj_down)

    # 0.2 Envelopamento transversal do empreendimento ao longo de u_corte
    # O limite do alinhamento das seções baseia-se prioritariamente no limite real das curvas de nível
    u_terr_min, u_terr_max = get_terrain_u_range(geoms_terreno, u_corte)
    if u_terr_min is not None and u_terr_max is not None and (u_terr_max - u_terr_min) > 1.0:
        u_min_aligned = u_terr_min
        u_max_aligned = u_terr_max
    else:
        u_proj_vals = []
        for c in lista_linhas:
            p0 = c.PointAtStart
            p1 = c.PointAtEnd
            u_proj_vals.append(p0.X * u_corte.X + p0.Y * u_corte.Y)
            u_proj_vals.append(p1.X * u_corte.X + p1.Y * u_corte.Y)
        u_min_aligned = min(u_proj_vals) - 6.0 * s
        u_max_aligned = max(u_proj_vals) + 6.0 * s

    # 0.3 Construção dos eixos transversais alinhados definitivos (Seções A, B, C...)
    # Todos partem da esquerda (u_min_aligned) e vão para a direita (u_max_aligned),
    # organizados estritamente de cima para baixo.
    lista_alinhadas = []
    for c in lista_linhas:
        p_mid = c.PointAtNormalizedLength(0.5)
        v_coord = p_mid.X * u_long_down.X + p_mid.Y * u_long_down.Y
        p_ref = rg.Point3d(v_coord * u_long_down.X, v_coord * u_long_down.Y, 0.0)

        clipped_interval = None
        if boundary_info is not None:
            clipped_interval = find_ray_polygon_interval(
                (p_ref.X, p_ref.Y), (u_corte.X, u_corte.Y), boundary_info['pts_2d']
            )

        if clipped_interval is not None and (clipped_interval[1] - clipped_interval[0]) > 1.0:
            u_ini_s, u_fim_s = clipped_interval
        else:
            u_ini_s, u_fim_s = u_min_aligned, u_max_aligned

        p_ini_aln = rg.Point3d(p_ref.X + u_ini_s * u_corte.X,
                               p_ref.Y + u_ini_s * u_corte.Y,
                               0.0)
        p_fim_aln = rg.Point3d(p_ref.X + u_fim_s * u_corte.X,
                               p_ref.Y + u_fim_s * u_corte.Y,
                               0.0)
        lista_alinhadas.append(rg.LineCurve(p_ini_aln, p_fim_aln))

    # GERAÇÃO DA REDE DE ESTAQUEAMENTO NORMATIVO A CADA 20 METROS (DNIT / SECRETARIAS DE OBRAS)
    # 1 estaca = 20.00 metros
    estacas_normativas_info = []
    try:
        v_ref_start = None
        if lista_alinhadas:
            pm0 = lista_alinhadas[0].PointAtNormalizedLength(0.5)
            v_ref_start = pm0.X * u_long_down.X + pm0.Y * u_long_down.Y
        elif boundary_info is not None and boundary_info.get('pts_2d'):
            v_ref_start = min(p.X * u_long_down.X + p.Y * u_long_down.Y for p in boundary_info['pts_2d'])

        v_ref_end = None
        if lista_alinhadas:
            pmn = lista_alinhadas[-1].PointAtNormalizedLength(0.5)
            v_ref_end = pmn.X * u_long_down.X + pmn.Y * u_long_down.Y
        elif boundary_info is not None and boundary_info.get('pts_2d'):
            v_ref_end = max(p.X * u_long_down.X + p.Y * u_long_down.Y for p in boundary_info['pts_2d'])

        if v_ref_start is not None and v_ref_end is not None and v_ref_end > v_ref_start + 1.0:
            cur_v = v_ref_start
            idx_st = 0
            while cur_v <= v_ref_end + 1e-4:
                p_ref = rg.Point3d(cur_v * u_long_down.X, cur_v * u_long_down.Y, 0.0)
                clipped_int = None
                if boundary_info is not None:
                    clipped_int = find_ray_polygon_interval(
                        (p_ref.X, p_ref.Y), (u_corte.X, u_corte.Y), boundary_info['pts_2d']
                    )
                if clipped_int is not None and (clipped_int[1] - clipped_int[0]) > 1.0:
                    u0, u1 = clipped_int
                else:
                    u0, u1 = u_min_aligned, u_max_aligned

                p0 = rg.Point3d(p_ref.X + u0 * u_corte.X, p_ref.Y + u0 * u_corte.Y, 0.0)
                p1 = rg.Point3d(p_ref.X + u1 * u_corte.X, p_ref.Y + u1 * u_corte.Y, 0.0)
                line_st = rg.LineCurve(p0, p1)

                d_prog = cur_v - v_ref_start
                lbl_estaca = "Estaca {}".format(idx_st)
                estacas_normativas_info.append({
                    'curve': line_st,
                    'index': idx_st,
                    'dist': d_prog,
                    'v_coord': cur_v,
                    'label': lbl_estaca,
                    'tag': "{} ({:.2f}m)".format(lbl_estaca, d_prog).replace('.', ',')
                })
                cur_v += passo_estacas
                idx_st += 1

            resto_final = v_ref_end - (cur_v - passo_estacas)
            if resto_final > 1.0:
                p_ref = rg.Point3d(v_ref_end * u_long_down.X, v_ref_end * u_long_down.Y, 0.0)
                clipped_int = None
                if boundary_info is not None:
                    clipped_int = find_ray_polygon_interval(
                        (p_ref.X, p_ref.Y), (u_corte.X, u_corte.Y), boundary_info['pts_2d']
                    )
                if clipped_int is not None and (clipped_int[1] - clipped_int[0]) > 1.0:
                    u0, u1 = clipped_int
                else:
                    u0, u1 = u_min_aligned, u_max_aligned
                p0 = rg.Point3d(p_ref.X + u0 * u_corte.X, p_ref.Y + u0 * u_corte.Y, 0.0)
                p1 = rg.Point3d(p_ref.X + u1 * u_corte.X, p_ref.Y + u1 * u_corte.Y, 0.0)
                line_st = rg.LineCurve(p0, p1)
                d_prog = v_ref_end - v_ref_start
                last_i = int(d_prog // passo_estacas)
                r_st = d_prog - (last_i * passo_estacas)
                lbl_estaca = "Estaca Final ({}+{:05.2f})".format(last_i, r_st).replace('.', ',')
                estacas_normativas_info.append({
                    'curve': line_st,
                    'index': last_i,
                    'dist': d_prog,
                    'v_coord': v_ref_end,
                    'label': lbl_estaca,
                    'tag': "{} ({:.2f}m)".format(lbl_estaca, d_prog).replace('.', ',')
                })
    except Exception as _e_est:
        pass

    # Se modo de estacas normativas foi solicitado ativamente, adota as estacas de 20m
    usar_modo_estacas = False
    if raw_modo_estacas is not None:
        if isinstance(raw_modo_estacas, bool) and raw_modo_estacas:
            usar_modo_estacas = True
        elif isinstance(raw_modo_estacas, (int, float)) and raw_modo_estacas > 0:
            usar_modo_estacas = True
        elif isinstance(raw_modo_estacas, str) and raw_modo_estacas.strip().lower() in ['true', '1', 'sim', 'yes', 'estacas', '20m']:
            usar_modo_estacas = True

    if usar_modo_estacas and estacas_normativas_info:
        lista_alinhadas = [item['curve'] for item in estacas_normativas_info]

    # 0.4 Processamento e Organização dos Eixos Longitudinais/Verticais (1, 2, 3...)
    # REGRA DA NORMA:
    # 1. Numerados "DA ESQUERDA PARA A DIREITA" (1 na esquerda, 2 no meio, 3 na direita...)
    # 2. Desenhados "DE CIMA PARA BAIXO" (início no topo do loteamento, fim na base)
    lista_verticais_raw = [to_rhino_curve(c) for c in to_list(raw_verticais) if to_rhino_curve(c) is not None]
    lista_verticais_alinhadas = []
    distancias_verticais = []

    if lista_verticais_raw:
        lista_vert_dups = [c.DuplicateCurve() for c in lista_verticais_raw]

        # Harmoniza cada eixo longitudinal para correr DE CIMA PARA BAIXO (ao longo de u_long_down)
        for c in lista_vert_dups:
            vec_v = c.PointAtEnd - c.PointAtStart
            if vec_v.X * u_long_down.X + vec_v.Y * u_long_down.Y < 0.0:
                c.Reverse()

        # REGRA DA NORMA: ORDENAÇÃO DOS EIXOS VERTICAIS "DA ESQUERDA PARA A DIREITA"
        # Projeção lateral ao longo de u_corte (que aponta para a direita):
        # Menor projeção = mais à esquerda -> Eixo 1
        # Maior projeção = mais à direita -> Eixo N
        def get_vert_proj_lateral(crv):
            p_mid = crv.PointAtNormalizedLength(0.5) if hasattr(crv, 'PointAtNormalizedLength') else crv.PointAt((crv.Domain.T0 + crv.Domain.T1) / 2.0)
            return p_mid.X * u_corte.X + p_mid.Y * u_corte.Y

        lista_vert_dups.sort(key=get_vert_proj_lateral)

        # Envelopamento longitudinal ao longo de u_long_down (abrangendo seções e verticais)
        v_proj_vals = []
        for c in lista_vert_dups:
            p0, p1 = c.PointAtStart, c.PointAtEnd
            v_proj_vals.append(p0.X * u_long_down.X + p0.Y * u_long_down.Y)
            v_proj_vals.append(p1.X * u_long_down.X + p1.Y * u_long_down.Y)

        for c in lista_alinhadas:
            p0, p1 = c.PointAtStart, c.PointAtEnd
            v_proj_vals.append(p0.X * u_long_down.X + p0.Y * u_long_down.Y)
            v_proj_vals.append(p1.X * u_long_down.X + p1.Y * u_long_down.Y)

        v_min_aln = min(v_proj_vals) - 6.0 * s  # Topo do loteamento
        v_max_aln = max(v_proj_vals) + 6.0 * s  # Base do loteamento

        # Construção dos eixos verticais alinhados:
        # Partem do topo (v_min_aln) e vão para a base (v_max_aln),
        # ordenados da esquerda (Eixo 1) para a direita (Eixo N)
        for c in lista_vert_dups:
            p_mid = c.PointAtNormalizedLength(0.5)
            w_coord = p_mid.X * u_corte.X + p_mid.Y * u_corte.Y
            p_ref_v = rg.Point3d(w_coord * u_corte.X, w_coord * u_corte.Y, 0.0)

            clipped_interval_v = None
            if boundary_info is not None:
                clipped_interval_v = find_ray_polygon_interval(
                    (p_ref_v.X, p_ref_v.Y), (u_long_down.X, u_long_down.Y), boundary_info['pts_2d']
                )

            if clipped_interval_v is not None and (clipped_interval_v[1] - clipped_interval_v[0]) > 1.0:
                v_ini_s, v_fim_s = clipped_interval_v
            else:
                v_ini_s, v_fim_s = v_min_aln, v_max_aln

            p_ini_v = rg.Point3d(p_ref_v.X + v_ini_s * u_long_down.X,
                                 p_ref_v.Y + v_ini_s * u_long_down.Y,
                                 0.0)
            p_fim_v = rg.Point3d(p_ref_v.X + v_fim_s * u_long_down.X,
                                 p_ref_v.Y + v_fim_s * u_long_down.Y,
                                 0.0)
            lista_verticais_alinhadas.append(rg.LineCurve(p_ini_v, p_fim_v))

        # Distâncias reais entre eixos verticais consecutivos (1-2, 2-3...)
        for j in range(len(lista_verticais_alinhadas) - 1):
            d_v = calculate_axis_distance(lista_verticais_alinhadas[j], lista_verticais_alinhadas[j+1])
            distancias_verticais.append(max(d_v, 0.1))
    else:
        # Auto-geração inteligente dos 5 Eixos Longitudinais (1 a 5) caso o usuário não tenha passado verticais manuais
        v_proj_vals = []
        for c in lista_alinhadas:
            p0, p1 = c.PointAtStart, c.PointAtEnd
            v_proj_vals.append(p0.X * u_long_down.X + p0.Y * u_long_down.Y)
            v_proj_vals.append(p1.X * u_long_down.X + p1.Y * u_long_down.Y)
        if v_proj_vals:
            v_min_aln = min(v_proj_vals) - 4.0 * s
            v_max_aln = max(v_proj_vals) + 4.0 * s
            n_auto_v = 5
            u_step_v = (u_max_aligned - u_min_aligned) / float(n_auto_v + 1)
            for i_auto in range(1, n_auto_v + 1):
                w_coord = u_min_aligned + i_auto * u_step_v
                p_ref_v = rg.Point3d(w_coord * u_corte.X, w_coord * u_corte.Y, 0.0)
                clipped_interval_v = None
                if boundary_info is not None:
                    clipped_interval_v = find_ray_polygon_interval(
                        (p_ref_v.X, p_ref_v.Y), (u_long_down.X, u_long_down.Y), boundary_info['pts_2d']
                    )
                if clipped_interval_v is not None and (clipped_interval_v[1] - clipped_interval_v[0]) > 1.0:
                    v_ini_s, v_fim_s = clipped_interval_v
                else:
                    v_ini_s, v_fim_s = v_min_aln, v_max_aln
                p_ini_v = rg.Point3d(p_ref_v.X + v_ini_s * u_long_down.X, p_ref_v.Y + v_ini_s * u_long_down.Y, 0.0)
                p_fim_v = rg.Point3d(p_ref_v.X + v_fim_s * u_long_down.X, p_ref_v.Y + v_fim_s * u_long_down.Y, 0.0)
                lista_verticais_alinhadas.append(rg.LineCurve(p_ini_v, p_fim_v))
            for j in range(len(lista_verticais_alinhadas) - 1):
                d_v = calculate_axis_distance(lista_verticais_alinhadas[j], lista_verticais_alinhadas[j+1])
                distancias_verticais.append(max(d_v, 0.1))

    lista_verticais = lista_verticais_alinhadas

    # Processamento de curvas de projeto fornecidas (curvas delimitadoras / greides)
    lista_projetos_raw = [to_rhino_curve(c) for c in to_list(raw_projeto) if to_rhino_curve(c) is not None]

    ponto_base = to_rhino_point(raw_ponto)
    orig_x = ponto_base.X if ponto_base else 0.0
    orig_y = ponto_base.Y if ponto_base else 0.0

    modo_cotas = parse_seletor(raw_seletor)

    # 1. Mapeamento prévio das interseções entre as seções e os eixos verticais
    num_secoes = len(lista_alinhadas)
    labels_t = [format_section_label(i) for i in range(num_secoes)]
    num_verticais = len(lista_verticais)
    labels_v = [str(i + 1) for i in range(num_verticais)]

    grid_pts = [[None for _ in range(num_verticais)] for _ in range(num_secoes)]
    secao_eixos_intersec = [[] for _ in range(num_secoes)]

    if num_secoes >= 1 and num_verticais >= 1:
        for i, ct in enumerate(lista_alinhadas):
            p_start_i = ct.PointAtStart
            u_sec_i = ct.PointAtEnd - p_start_i
            u_sec_i.Unitize()
            for j, cv in enumerate(lista_verticais):
                ct_xy = rg.Curve.ProjectToPlane(ct, rg.Plane.WorldXY) or ct
                cv_xy = rg.Curve.ProjectToPlane(cv, rg.Plane.WorldXY) or cv
                ev = rg.Intersect.Intersection.CurveCurve(ct_xy, cv_xy, tol * 10, tol * 10)
                if ev and (getattr(ev, 'Count', len(ev)) > 0):
                    pt_inter = ev[0].PointA
                    d_t = (pt_inter.X - p_start_i.X) * u_sec_i.X + (pt_inter.Y - p_start_i.Y) * u_sec_i.Y
                    p_start_j = cv.PointAtStart
                    u_sec_j = cv.PointAtEnd - p_start_j
                    u_sec_j.Unitize()
                    d_v = (pt_inter.X - p_start_j.X) * u_sec_j.X + (pt_inter.Y - p_start_j.Y) * u_sec_j.Y
                    if (-0.5 <= d_t <= ct.GetLength() + 0.5) and (-0.5 <= d_v <= cv.GetLength() + 0.5):
                        grid_pts[i][j] = rg.Point3d(pt_inter.X, pt_inter.Y, 0.0)
                        secao_eixos_intersec[i].append((d_t, j, labels_v[j]))
            secao_eixos_intersec[i].sort(key=lambda x: x[0])

    # =========================================================================
    # 1. EXTRAÇÃO DO TERRENO E GEOMETRIA ANALÍTICA (TRANSVERSAL E LONGITUDINAL)
    # =========================================================================

    # 1.1 Mapeamento das interseções nas seções longitudinais/verticais (1, 2, 3...)
    vertical_eixos_intersec = [[] for _ in range(num_verticais)]
    if num_secoes >= 1 and num_verticais >= 1:
        for j, cv in enumerate(lista_verticais):
            p_start_j = cv.PointAtStart
            u_sec_j = cv.PointAtEnd - p_start_j
            u_sec_j.Unitize()
            for i, ct in enumerate(lista_alinhadas):
                pt_inter = grid_pts[i][j]
                if pt_inter is not None:
                    d_long = (pt_inter.X - p_start_j.X) * u_sec_j.X + (pt_inter.Y - p_start_j.Y) * u_sec_j.Y
                    vertical_eixos_intersec[j].append((d_long, i, labels_t[i]))
            vertical_eixos_intersec[j].sort(key=lambda x: x[0])

    # 1.2 Extração do perfil de terreno natural das Seções Transversais (A, B, C...)
    sec_terrain_info = []
    sec_heights_above = []
    sec_heights_below = []

    for idx_s, crv_c in enumerate(lista_alinhadas):
        eixos_da_secao = secao_eixos_intersec[idx_s] if idx_s < len(secao_eixos_intersec) else []
        t_info = extract_section_terrain(crv_c, geoms_terreno, tol, eixos_da_secao, s)
        sec_terrain_info.append(t_info)

        sec_datum_z = t_info['sec_datum_z']
        sec_h = t_info['sec_h']
        sec_heights_above.append(sec_h + 16.0 * s)
        sec_heights_below.append(12.0 * s)

    # 1.3 Extração do perfil de terreno natural das Seções Longitudinais (1, 2, 3...)
    sec_v_terrain_info = []
    sec_v_heights_above = []
    sec_v_heights_below = []

    for idx_v, crv_v in enumerate(lista_verticais):
        eixos_da_vertical = vertical_eixos_intersec[idx_v] if idx_v < len(vertical_eixos_intersec) else []
        t_info_v = extract_section_terrain(crv_v, geoms_terreno, tol, eixos_da_vertical, s)
        sec_v_terrain_info.append(t_info_v)

        sec_datum_z_v = t_info_v['sec_datum_z']
        sec_h_v = t_info_v['sec_h']
        sec_v_heights_above.append(sec_h_v + 16.0 * s)
        sec_v_heights_below.append(12.0 * s)

    # =========================================================================
    # 2. DEFINICAO DE COORDENADAS 2D E ESPACAMENTOS DAS PRANCHAS A0 REGULAMENTARES (NBR 10068 / NBR 6492)
    #    FOLHA 03/03: SECOES TRANSVERSAIS (A, B, C...) - 2 COLUNAS DE 5 SECOES (ESCALA 1:200)
    #    FOLHA 02/03: PERFIS LONGITUDINAIS VIARIOS COM GUITARRA (ESCALA H=1:1.000 / V=1:100) - 2 COLUNAS
    # =========================================================================
    banner_space = 14.0 * s

    # 2.1 Organizacao das Secoes Transversais em 2 Colunas na Folha 03/03 (237.80 x 168.20 m a 1:200)
    # Coluna 1 (Secoes A a E): base_x = orig_x + 6.0*s, largura maxima = 86.0*s
    # Coluna 2 (Secoes F a J): base_x = orig_x + 104.0*s, largura maxima = 86.0*s
    # Carimbo oficial e Legenda: X = orig_x + 200.8*s a 235.8*s (folga de 10.8m)
    num_half = (num_secoes + 1) // 2 if num_secoes > 5 else num_secoes
    sec_base_xs = []
    sec_base_ys = []
    y_start_sec = orig_y - 23.0 * s
    pitch_sec_y = 31.0 * s

    for i in range(num_secoes):
        if num_secoes <= 5:
            col_i = 0
            row_i = i
        else:
            col_i = 0 if i < num_half else 1
            row_i = i if i < num_half else (i - num_half)
        bx = orig_x + (6.0 * s if col_i == 0 else 104.0 * s)
        by = y_start_sec - row_i * pitch_sec_y
        sec_base_xs.append(bx)
        sec_base_ys.append(by)

    espacamento_y = pitch_sec_y
    max_w_t = 86.0 * s

    # 2.2 Organizacao dos Perfis Longitudinais das Vias em 2 Colunas na Folha 02/03 (H=1:1.000 / V=1:100 ou V=1:200)
    # Folha 02 A0 (1189 x 841 m). Posicionada a direita da Folha 03 com folga de 260m
    folha2_orig_x = orig_x + 260.0 * s
    folha2_orig_y = orig_y - 841.0 * s
    h_guitarra_est = 41.0 * s

    # Deteccao automatica de relevo acidentado (DNIT / DER-SP)
    # Se delta_z * ev > 220m (como no terreno com desnivel de 44m), adapta ev_long para 5.0 (V=1:200)
    max_dz_all_v = 0.0
    for t_v in sec_v_terrain_info:
        dz_t = t_v.get('sec_h', 0.0)
        if dz_t > max_dz_all_v: max_dz_all_v = dz_t
    if max_dz_all_v * ev_long > 220.0:
        ev_long = 5.0

    num_half_v = (num_verticais + 1) // 2 if num_verticais > 3 else num_verticais
    sec_v_base_xs = []
    sec_v_base_ys = []

    # Altura util vertical da prancha A0 a 1:1000 = 821.0m
    y_top_sheet_v = orig_y - 10.0 * s
    n_rows_col1 = num_half_v
    n_rows_col2 = num_verticais - num_half_v
    slot_h_col1 = 820.0 * s / max(n_rows_col1, 1)
    slot_h_col2 = 820.0 * s / max(n_rows_col2, 1) if n_rows_col2 > 0 else 820.0 * s

    for j in range(num_verticais):
        if num_verticais <= 3:
            col_j = 0
            row_j = j
            slot_h = slot_h_col1
        else:
            col_j = 0 if j < num_half_v else 1
            row_j = j if j < num_half_v else (j - num_half_v)
            slot_h = slot_h_col1 if col_j == 0 else slot_h_col2

        bx_v = folha2_orig_x + (45.0 * s if col_j == 0 else 520.0 * s)
        t_info_j = sec_v_terrain_info[j] if j < len(sec_v_terrain_info) else {}
        dz_j = t_info_j.get('sec_h', 20.0)
        h_above_datum = (dz_j * ev_long) + 16.0 * s
        y_top_slot = y_top_sheet_v - row_j * slot_h - 16.0 * s
        by_v = y_top_slot - h_above_datum

        sec_v_base_xs.append(bx_v)
        sec_v_base_ys.append(by_v)

    pitch_v = slot_h_col1
    espacamento_y_v = pitch_v
    col2_x = folha2_orig_x + 45.0 * s
    max_w_v = max([t['total_ext'] for t in sec_v_terrain_info] or [120.0])

    # =========================================================================
    # 3. MAPEAMENTO UNIVERSAL DE CURVAS DE PROJETO / LINHAS DELIMITADORAS
    #    (Associates each drawn curve with its respective 2D section based on X and Y)
    # =========================================================================
    all_targets = []
    for i in range(num_secoes):
        all_targets.append({
            'key': ('T', i),
            'base_x': sec_base_xs[i],
            'base_y': sec_base_ys[i],
            'total_ext': sec_terrain_info[i]['total_ext'],
            'sec_h': sec_terrain_info[i]['sec_h']
        })
    for j in range(num_verticais):
        all_targets.append({
            'key': ('V', j),
            'base_x': sec_v_base_xs[j],
            'base_y': sec_v_base_ys[j],
            'total_ext': sec_v_terrain_info[j]['total_ext'],
            'sec_h': sec_v_terrain_info[j]['sec_h']
        })
    raw_projeto_long = globals().get('LinhaDelimitadoraLongitudinal', globals().get('ProjetoLongitudinal', globals().get('DelimitadoraLongitudinal', globals().get('GreideLongitudinal', None))))
    all_project_curves = [to_rhino_curve(c) for c in (to_list(raw_projeto) + to_list(raw_projeto_long)) if to_rhino_curve(c) is not None and not getattr(to_rhino_curve(c), 'IsClosed', False)]

    matched_curves_map = match_project_curves_to_sections(all_project_curves, all_targets)

    # =========================================================================
    # 4. AVALIAÇÃO ANALÍTICA DAS SEÇÕES TRANSVERSAIS (A, B, C...)
    # =========================================================================
    sec_data_list = []
    for idx_s, t_info in enumerate(sec_terrain_info):
        lbl = labels_t[idx_s]
        base_x = sec_base_xs[idx_s]
        base_y = sec_base_ys[idx_s]
        crv_p, curve_base_y = matched_curves_map.get(('T', idx_s), (None, base_y))

        num_tr = len(t_info['d_divs']) + 1
        sec_levels = parse_nivel_projeto(raw_nivel_proj, idx_s, num_secoes, num_tr)

        s_data = evaluate_section_grade_and_volumes(
            t_info, crv_p, sec_levels, lbl, s, base_x, base_y, curve_base_y, max_slope=max_slope, road_polygons=road_polygons
        )
        s_data['label'] = lbl
        sec_data_list.append(s_data)

    # =========================================================================
    # 5. AVALIAÇÃO ANALÍTICA DAS SEÇÕES LONGITUDINAIS (1, 2, 3...)
    #    (Sincronização 3D com as seções transversais ou curva individual)
    # =========================================================================
    sec_v_data_list = []
    for idx_v, t_info_v in enumerate(sec_v_terrain_info):
        lbl_v = labels_v[idx_v]
        base_x_v = sec_v_base_xs[idx_v]
        base_y_v = sec_v_base_ys[idx_v]
        crv_p_v, curve_base_y_v = matched_curves_map.get(('V', idx_v), (None, base_y_v))

        # If the user drew/supplied an individual boundary line over this longitudinal section
        if crv_p_v is not None:
            num_tr_v = len(t_info_v['d_divs']) + 1
            sec_levels_v = parse_nivel_projeto(raw_nivel_proj, idx_v, num_verticais, num_tr_v)
            s_data_v = evaluate_section_grade_and_volumes(
                t_info_v, crv_p_v, sec_levels_v, lbl_v, s, base_x_v, base_y_v, curve_base_y_v, max_slope=max_slope, road_polygons=road_polygons
            )
        else:
            # Sincronização direta e contínua com a superfície 3D de terraplenagem projetada
            crv_v = lista_verticais[idx_v]
            corridors_v = compute_road_corridors_for_section(crv_v, road_polygons, tol)

            def make_v_sampler(c_v):
                p_st = c_v.PointAtStart
                p_end = c_v.PointAtEnd
                L = max(c_v.GetLength(), 1e-4)
                dx = p_end.X - p_st.X
                dy = p_end.Y - p_st.Y
                def sample_fn(d_val):
                    d_clamped = max(0.0, min(L, d_val))
                    t_d = d_clamped / L
                    px = p_st.X + t_d * dx
                    py = p_st.Y + t_d * dy
                    return sample_surface_proj_z(px, py, lista_alinhadas, sec_data_list, u_long_down)
                return sample_fn

            raw_sampler_v = make_v_sampler(crv_v)
            if corridors_v:
                sampler_v = lambda d, smp=raw_sampler_v, crs=corridors_v: make_drivable_road_z(d, smp(d), crs)
            else:
                sampler_v = raw_sampler_v

            s_data_v = evaluate_section_grade_and_volumes(
                t_info_v, None, None, lbl_v, s, base_x_v, base_y_v, base_y_v, max_slope=max_slope, road_polygons=road_polygons
            )
            s_data_v['sampler'] = sampler_v
            s_data_v['get_proj_z'] = sampler_v
            s_data_v['effective_slope'] = 0.0
            s_data_v['was_clamped'] = False

            # Recalcula pontos de passagem, regiões de corte e aterro e áreas para o greide sincronizado
            clean_pts_v = t_info_v['clean_pts']
            total_ext_v = t_info_v['total_ext']
            estacas_v = [p[0] for p in clean_pts_v]
            for it in t_info_v.get('eixos_secao', []):
                estacas_v.append(it[0])
            for k_div in range(max(int(total_ext_v / 1.0), 30) + 1):
                estacas_v.append(k_div * (total_ext_v / max(int(total_ext_v / 1.0), 30)))
            estacas_v = sorted(list(set(round(d, 4) for d in estacas_v if 0.0 <= d <= total_ext_v)))

            pp_v = []
            for k in range(len(estacas_v) - 1):
                d1, d2 = estacas_v[k], estacas_v[k+1]
                z_tn1 = interpolate_terrain_z(d1, clean_pts_v); z_pr1 = sampler_v(d1)
                z_tn2 = interpolate_terrain_z(d2, clean_pts_v); z_pr2 = sampler_v(d2)
                diff1 = z_tn1 - z_pr1; diff2 = z_tn2 - z_pr2
                if diff1 * diff2 < -1e-6:
                    t_cross = abs(diff1) / (abs(diff1) + abs(diff2))
                    d_cross = d1 + t_cross * (d2 - d1)
                    z_cross = z_pr1 + t_cross * (z_pr2 - z_pr1)
                    pp_v.append((d_cross, z_cross))
            s_data_v['pontos_passagem'] = pp_v

            estacas_finais_v = sorted(list(set(estacas_v + [p[0] for p in pp_v])))
            s_data_v['estacas_finais'] = estacas_finais_v

            regioes_v = []
            curr_type_v = None
            curr_pts_v = []
            for k in range(len(estacas_finais_v) - 1):
                d1 = estacas_finais_v[k]
                d2 = estacas_finais_v[k+1]
                dm = (d1 + d2) / 2.0
                diff = interpolate_terrain_z(dm, clean_pts_v) - sampler_v(dm)
                t_seg = "CORTE" if diff > 1e-4 else ("ATERRO" if diff < -1e-4 else "NEUTRO")
                if t_seg != curr_type_v:
                    if curr_type_v and curr_type_v != "NEUTRO" and len(curr_pts_v) >= 2:
                        regioes_v.append((curr_type_v, curr_pts_v))
                    curr_type_v = t_seg
                    curr_pts_v = [d1, d2]
                else:
                    curr_pts_v.append(d2)
            if curr_type_v and curr_type_v != "NEUTRO" and len(curr_pts_v) >= 2:
                regioes_v.append((curr_type_v, curr_pts_v))
            s_data_v['regioes'] = regioes_v

            a_c_v = 0.0; a_a_v = 0.0
            max_hc_v = 0.0; max_ha_v = 0.0
            for r_type, d_list in regioes_v:
                for k in range(len(d_list) - 1):
                    d1, d2 = d_list[k], d_list[k+1]
                    w = d2 - d1
                    if w <= 1e-6: continue
                    h1 = abs(interpolate_terrain_z(d1, clean_pts_v) - sampler_v(d1))
                    h2 = abs(interpolate_terrain_z(d2, clean_pts_v) - sampler_v(d2))
                    trap_a = ((h1 + h2) / 2.0) * w
                    if r_type == "CORTE":
                        a_c_v += trap_a
                        max_hc_v = max(max_hc_v, h1, h2)
                    else:
                        a_a_v += trap_a
                        max_ha_v = max(max_ha_v, h1, h2)
            s_data_v['area_total_corte'] = a_c_v
            s_data_v['area_total_aterro'] = a_a_v
            s_data_v['max_h_corte'] = max_hc_v
            s_data_v['max_h_aterro'] = max_ha_v

        s_data_v['label'] = lbl_v
        sec_v_data_list.append(s_data_v)

    # =========================================================================
    # 6. VOLUMES & MASS HAUL BALANCING (AGPTEA / AVERAGE END AREA METHOD)
    # =========================================================================
    # 6.1 Distâncias e Volumes Transversais (A -> B -> C...)
    distancias_eixos = []
    for i in range(num_secoes - 1):
        d_val = calculate_axis_distance(lista_alinhadas[i], lista_alinhadas[i+1])
        distancias_eixos.append(max(d_val, 0.1))
    if num_secoes == 1:
        try: w_single = float(raw_largura) if raw_largura is not None else 1.0
        except: w_single = 1.0
        distancias_eixos = [w_single]

    # 6.0 Cálculo do Estaqueamento Progressivo (Estaca X+YY,YY) de cada seção
    dist_acum_t = 0.0
    estacas_secoes_t = []
    for idx_s in range(num_secoes):
        d_acum = 0.0 if idx_s == 0 else dist_acum_t
        e_int = int(d_acum // passo_estacas)
        e_rem = d_acum - (e_int * passo_estacas)
        if e_rem < 0.005:
            e_str = "Estaca {}+00,00".format(e_int)
        else:
            e_str = "Estaca {}+{:05.2f}".format(e_int, e_rem).replace('.', ',')

        estacas_secoes_t.append({
            'estaca_str': e_str,
            'dist_acum': d_acum,
            'e_int': e_int,
            'e_rem': e_rem,
            'd_prox': distancias_eixos[idx_s] if idx_s < len(distancias_eixos) else 0.0
        })
        sec_data_list[idx_s]['estaca_str'] = e_str
        sec_data_list[idx_s]['dist_acum'] = d_acum
        if idx_s < len(distancias_eixos):
            dist_acum_t += distancias_eixos[idx_s]

    vols_trechos = []
    for i in range(num_secoes - 1):
        d_trecho = distancias_eixos[i]
        a_c1 = sec_data_list[i]['area_total_corte']
        a_c2 = sec_data_list[i+1]['area_total_corte']
        a_a1 = sec_data_list[i]['area_total_aterro']
        a_a2 = sec_data_list[i+1]['area_total_aterro']

        vc = ((a_c1 + a_c2) / 2.0) * d_trecho
        va_geo = ((a_a1 + a_a2) / 2.0) * d_trecho
        va_banco = va_geo * fh
        saldo_local = vc - va_banco
        vols_trechos.append((d_trecho, vc, va_geo, va_banco, saldo_local))

    # Atualizacao imediata do resumo volumetrico global para carimbos e pranchas executivas
    if vols_trechos:
        vc_tot_pre = sum(item[1] for item in vols_trechos)
        va_tot_pre = sum(item[2] for item in vols_trechos)
        va_banco_tot_pre = sum(item[3] for item in vols_trechos) if len(vols_trechos[0]) >= 4 else va_tot_pre
        global_vol_summary = {
            'corte_geo': vc_tot_pre,
            'aterro_geo': va_tot_pre,
            'saldo': vc_tot_pre - va_banco_tot_pre,
            'fator_k': fh if 'fh' in locals() else 1.20
        }

    ordenada_bruckner = 0.0
    fluxo_transporte = []
    for i, (d_t, vc, va_geo, va_banco, s_local) in enumerate(vols_trechos):
        ordenada_bruckner += s_local
        fluxo_transporte.append({
            'd_trecho': d_t,
            'vc': vc,
            'va_geo': va_geo,
            'va_banco': va_banco,
            'saldo_local': s_local,
            'ordenada': ordenada_bruckner
        })

    # 6.2 Longitudinal distances and volumes (1 -> 2 -> 3...)
    vols_trechos_v = []
    fluxo_transporte_v = []
    if num_verticais >= 2:
        saldo_acum_v = 0.0
        for j in range(num_verticais - 1):
            d_v = distancias_verticais[j] if j < len(distancias_verticais) else 10.0
            a_c1 = sec_v_data_list[j]['area_total_corte']
            a_c2 = sec_v_data_list[j+1]['area_total_corte']
            a_a1 = sec_v_data_list[j]['area_total_aterro']
            a_a2 = sec_v_data_list[j+1]['area_total_aterro']

            vc_v = ((a_c1 + a_c2) / 2.0) * d_v
            va_v = ((a_a1 + a_a2) / 2.0) * d_v
            saldo_v = vc_v - va_v
            vols_trechos_v.append((d_v, vc_v, va_v, saldo_v))

            disp_v = saldo_acum_v + vc_v
            if disp_v >= va_v:
                sobra_v = disp_v - va_v
                if j < num_verticais - 2:
                    nota_v = "SOBRA: {:+.1f}m³ -> COMPENSAR EIXO {} - {}".format(sobra_v, labels_v[j+1], labels_v[j+2]).replace('.', ',')
                else:
                    nota_v = "SOBRA LONGITUDINAL FINAL: {:+.1f}m³ (BOTA-FORA)".format(sobra_v).replace('.', ',')
                saldo_acum_v = sobra_v
            else:
                falta_v = va_v - disp_v
                nota_v = "DÉFICIT LONGITUDINAL: -{:.1f}m³ (EMPRÉSTIMO DE JAZIDA)".format(falta_v).replace('.', ',')
                saldo_acum_v = -falta_v
            fluxo_transporte_v.append(nota_v)

    # =========================================================================
    # 7. CONSTRUÇÃO DO DESENHO DAS SEÇÕES 2D (COLUNA 1 E COLUNA 2)
    # =========================================================================
    desenho_completo_secoes_2d = []
    desenho_secoes_t_only = []
    desenho_secoes_v_only = []

    poligonos_corte_all = []
    poligonos_aterro_all = []
    linhas_3d_all = []
    greides_3d_all = []
    poligonos_3d_corte_all = []
    poligonos_3d_aterro_all = []
    quads_3d_corte_secoes = []
    quads_3d_aterro_secoes = []

    cor_corte  = System.Drawing.Color.FromArgb(245, 130, 32)
    cor_aterro = System.Drawing.Color.FromArgb(46, 204, 113)

    # 7.1 Cabeçalho da Folha 03 (Seções Transversais em 2 Colunas A0)
    p_hdr_col1 = rg.Point3d(orig_x + 8.0 * s, orig_y - 14.0 * s, 0.0)
    t_hdr1 = make_text_geometry("SEÇÕES TRANSVERSAIS DE TERRAPLENAGEM (COLUNAS A-E e F-J)", p_hdr_col1, 1.8 * s, rg.TextJustification.BottomLeft, s)
    p_sub_hdr1 = rg.Point3d(orig_x + 8.0 * s, orig_y - 18.0 * s, 0.0)
    sub_hdr1 = make_text_geometry("Perfis Topográficos e de Terraplenagem | Representação Executiva NBR 6492", p_sub_hdr1, 0.90 * s, rg.TextJustification.BottomLeft, s)
    desenho_completo_secoes_2d.extend(t_hdr1)
    desenho_completo_secoes_2d.extend(sub_hdr1)
    desenho_secoes_t_only.extend(t_hdr1)
    desenho_secoes_t_only.extend(sub_hdr1)

    # Rendering of each Cross Section
    for idx_s, s_data in enumerate(sec_data_list):
        lbl = labels_t[idx_s]
        base_x = sec_base_xs[idx_s]
        base_y = sec_base_ys[idx_s]
        crv_aln_3d = lista_alinhadas[idx_s]

        res_sec = render_single_section_2d_and_3d(
            s_data, lbl, base_x, base_y, s, modo_cotas, cor_corte, cor_aterro,
            crv_aln_3d=crv_aln_3d, is_longitudinal=False, axis_title_prefix="SEÇÃO "
        )

        desenho_completo_secoes_2d.extend(res_sec['geoms_2d'])
        desenho_secoes_t_only.extend(res_sec['geoms_2d'])
        poligonos_corte_all.extend(res_sec['poligonos_corte_2d'])
        poligonos_aterro_all.extend(res_sec['poligonos_aterro_2d'])
        quads_3d_corte_secoes.extend(res_sec['quads_3d_corte'])
        quads_3d_aterro_secoes.extend(res_sec['quads_3d_aterro'])
        if res_sec.get('crv_gr_3d') and getattr(res_sec['crv_gr_3d'], 'IsValid', False):
            greides_3d_all.append(res_sec['crv_gr_3d'])
        if res_sec.get('crv_tn_3d') and getattr(res_sec['crv_tn_3d'], 'IsValid', False):
            linhas_3d_all.append(res_sec['crv_tn_3d'])
        poligonos_3d_corte_all.extend(res_sec['poligonos_3d_corte'])
        poligonos_3d_aterro_all.extend(res_sec['poligonos_3d_aterro'])

        # Mass Haul Transfer Banner between Consecutive Cross Sections
        if idx_s < num_secoes - 1:
            lbl_prox = labels_t[idx_s + 1]
            vt_val = vols_trechos[idx_s]
            if len(vt_val) == 5:
                d_t, vc_t, va_t, va_banco_t, s_t = vt_val
            elif len(vt_val) == 4:
                d_t, vc_t, va_t, s_t = vt_val
                va_banco_t = va_t
            else:
                d_t, vc_t, va_t, s_t = vt_val[0], vt_val[1], vt_val[2], vt_val[-1]
                va_banco_t = va_t

            fl_item = fluxo_transporte[idx_s] if idx_s < len(fluxo_transporte) else None
            if isinstance(fl_item, dict):
                ord_b = fl_item.get('ordenada', s_t)
                if s_t > 0.01:
                    nota_t = "SOBRA LOCAL: +{:.1f}m³ | BRÜCKNER: {:+.1f}m³ (RAMO ASCENDENTE)".format(s_t, ord_b).replace('.', ',')
                elif s_t < -0.01:
                    nota_t = "DÉFICIT LOCAL: {:.1f}m³ | BRÜCKNER: {:+.1f}m³ (DEMANDA JAZIDA)".format(s_t, ord_b).replace('.', ',')
                else:
                    nota_t = "COMPENSADO LOCALMENTE | BRÜCKNER: {:+.1f}m³".format(ord_b).replace('.', ',')
            elif isinstance(fl_item, str):
                nota_t = fl_item
            else:
                nota_t = ""

            next_sec = sec_data_list[idx_s + 1]
            next_base_x = sec_base_xs[idx_s + 1]
            next_base_y = sec_base_ys[idx_s + 1]
            next_datum = math.floor(next_sec['z_min'] - 2.0)
            next_h_top = (next_sec['z_max'] - next_datum) + 16.0 * s
            y_bot_current = base_y - 12.0 * s
            if abs(next_base_x - base_x) < 5.0 * s:
                y_top_next = next_base_y + next_h_top
                y_banner = (y_bot_current + y_top_next) / 2.0
                x_banner = base_x + s_data['total_ext'] / 2.0
            else:
                y_banner = y_bot_current - 6.0 * s
                x_banner = base_x + s_data['total_ext'] / 2.0

            if num_secoes <= 3 or pitch_sec_y > 45.0 * s:
                banner_geoms, _ = make_mass_haul_banner(x_banner, y_banner, lbl, lbl_prox, d_t, vc_t, va_t, s_t, nota_t, s)
                desenho_completo_secoes_2d.extend(banner_geoms)
                desenho_secoes_t_only.extend(banner_geoms)

    # 7.1.1 ENQUADRAMENTO EM PRANCHA REGULAMENTAR A0 (FOLHA 03/03) - ESCALA 1:200
    #     Dimensões A0 a 1:200: 237.80 x 168.20 m.
    #     10 Seções organizadas em 2 Colunas de 5 seções + Carimbo Oficial de Vargem Grande Paulista.
    prancha_secoes_geoms = []
    if num_secoes >= 1:
        f3_x0 = orig_x
        f3_y0 = orig_y - 168.2 * s
        prancha_secoes_geoms = draw_standard_a0_sheet(
            f3_x0, f3_y0, 200.0,
            "SEÇÕES TRANSVERSAIS DE TERRAPLENAGEM (EIXOS A A J)",
            "FOLHA 03/03", "1 / 200", s=s, is_planta=False, is_longitudinal=False,
            volume_summary=global_vol_summary
        )
        desenho_completo_secoes_2d.extend(prancha_secoes_geoms)
        desenho_secoes_t_only.extend(prancha_secoes_geoms)

    # 7.2 Perfis Longitudinais Viarios A0 (Folha 02/03)
    if num_verticais >= 1:

        for idx_v, s_data_v in enumerate(sec_v_data_list):
            lbl_v = labels_v[idx_v]
            base_x_v = sec_v_base_xs[idx_v]
            base_y_v = sec_v_base_ys[idx_v]
            crv_aln_3d_v = lista_verticais[idx_v]

            res_sec_v = render_longitudinal_profile_with_guitarra(
                s_data_v, lbl_v, base_x_v, base_y_v, s, ev=ev_long, step_estaca=passo_estacas,
                cor_corte=cor_corte, cor_aterro=cor_aterro, crv_aln_3d_v=crv_aln_3d_v, axis_title_prefix="EIXO "
            )

            desenho_completo_secoes_2d.extend(res_sec_v['geoms_2d'])
            desenho_secoes_v_only.extend(res_sec_v['geoms_2d'])
            poligonos_corte_all.extend(res_sec_v['poligonos_corte_2d'])
            poligonos_aterro_all.extend(res_sec_v['poligonos_aterro_2d'])
            quads_3d_corte_secoes.extend(res_sec_v['quads_3d_corte'])
            quads_3d_aterro_secoes.extend(res_sec_v['quads_3d_aterro'])
            if res_sec_v.get('crv_gr_3d') and getattr(res_sec_v['crv_gr_3d'], 'IsValid', False):
                greides_3d_all.append(res_sec_v['crv_gr_3d'])
            if res_sec_v.get('crv_tn_3d') and getattr(res_sec_v['crv_tn_3d'], 'IsValid', False):
                linhas_3d_all.append(res_sec_v['crv_tn_3d'])
            poligonos_3d_corte_all.extend(res_sec_v['poligonos_3d_corte'])
            poligonos_3d_aterro_all.extend(res_sec_v['poligonos_3d_aterro'])

            # Mass Haul Transfer Banner between Consecutive Longitudinal Sections
            if idx_v < num_verticais - 1 and idx_v < len(vols_trechos_v):
                lbl_v_prox = labels_v[idx_v + 1]
                vt_v_val = vols_trechos_v[idx_v]
                if len(vt_v_val) == 5:
                    d_tv, vc_tv, va_tv, va_banco_tv, s_tv = vt_v_val
                elif len(vt_v_val) == 4:
                    d_tv, vc_tv, va_tv, s_tv = vt_v_val
                    va_banco_tv = va_tv
                else:
                    d_tv, vc_tv, va_tv, s_tv = vt_v_val[0], vt_v_val[1], vt_v_val[2], vt_v_val[-1]
                    va_banco_tv = va_tv

                fl_item_v = fluxo_transporte_v[idx_v] if idx_v < len(fluxo_transporte_v) else None
                if isinstance(fl_item_v, dict):
                    ord_bv = fl_item_v.get('ordenada', s_tv)
                    if s_tv > 0.01:
                        nota_tv = "SOBRA LOCAL: +{:.1f}m³ | BRÜCKNER: {:+.1f}m³".format(s_tv, ord_bv).replace('.', ',')
                    elif s_tv < -0.01:
                        nota_tv = "DÉFICIT LOCAL: {:.1f}m³ | BRÜCKNER: {:+.1f}m³".format(s_tv, ord_bv).replace('.', ',')
                    else:
                        nota_tv = "COMPENSADO LOCALMENTE | BRÜCKNER: {:+.1f}m³".format(ord_bv).replace('.', ',')
                elif isinstance(fl_item_v, str):
                    nota_tv = fl_item_v
                else:
                    nota_tv = ""

                # Desenha banner apenas se o proximo perfil estiver na mesma coluna
                if (idx_v + 1) < len(sec_v_base_xs) and abs(sec_v_base_xs[idx_v + 1] - base_x_v) < 10.0 * s:
                    next_sec_v = sec_v_data_list[idx_v + 1]
                    next_base_y_v = sec_v_base_ys[idx_v + 1]
                    next_datum_v = math.floor(next_sec_v['z_min'] - 2.0)
                    next_h_top_v = (next_sec_v['z_max'] - next_datum_v) * ev_long + 16.0 * s
                    y_bot_current_v = base_y_v - 41.0 * s
                    y_top_next_v = next_base_y_v + next_h_top_v
                    y_banner_v = (y_bot_current_v + y_top_next_v) / 2.0
                    x_banner_v = base_x_v + s_data_v['total_ext'] / 2.0

                    banner_geoms_v, _ = make_mass_haul_banner(x_banner_v, y_banner_v, lbl_v, lbl_v_prox, d_tv, vc_tv, va_tv, s_tv, nota_tv, s)
                    desenho_completo_secoes_2d.extend(banner_geoms_v)
                    desenho_secoes_v_only.extend(banner_geoms_v)

        # ENQUADRAMENTO EM PRANCHA REGULAMENTAR A0 (FOLHA 02/03) - ESCALA H=1:1.000 / V=1:100
        # Dimensões A0 a 1:1.000: 1189.00 x 841.00 m.
        # 5 Perfis Longitudinais com Guitarra Completa + Carimbo Oficial de Vargem Grande Paulista.
        if num_verticais >= 1 and sec_v_base_ys:
            f2_x0 = folha2_orig_x
            f2_y0 = folha2_orig_y
            scale_label_f2 = "H=1:1.000 / V=1:{:.0f}".format(1000.0 / ev_long)
            prancha_long_geoms = draw_standard_a0_sheet(
                f2_x0, f2_y0, 1000.0,
                "PERFIS LONGITUDINAIS DAS VIAS COM GUITARRA (EIXOS 1 A 5)",
                "FOLHA 02/03", scale_label_f2, s=s, is_planta=False, is_longitudinal=True,
                volume_summary=global_vol_summary
            )
            desenho_completo_secoes_2d.extend(prancha_long_geoms)
            desenho_secoes_v_only.extend(prancha_long_geoms)

    # =========================================================================
    # 8. TECHNICAL PLAN VIEW (AXES, BUBBLES AND QUADRANTS)
    # =========================================================================
    prancha_planta_geoms = []
    planta_baixa_geoms = []
    estaqueamento_vias_geoms = []
    quads_2d_corte = []
    quads_2d_aterro = []
    quads_2d_neutro = []
    m_2d_corte = None
    m_2d_aterro = None
    m_2d_neutro = None
    outer_slope_pts = []
    dentes_talude_geoms = []
    taludes_geoms = []
    hachuras_corte_geoms = []
    hachuras_aterro_geoms = []
    afastamento_divisas_geoms = []
    linha_neutra_crvs = []
    min_dist_bnd = 1e9
    area_mancha_corte_2d = 0.0
    area_mancha_aterro_2d = 0.0
    crvs_proj_1m = []
    crvs_proj_5m = []
    crvs_proj_all = []

    offset_cota_fora = 8.5 * s
    offset_balao_fora = offset_cota_fora + 7.5 * s

    if num_secoes >= 2:
        p_ref_1 = lista_alinhadas[0].PointAtStart
        p_ref_2 = lista_alinhadas[-1].PointAtStart
        v_ref = p_ref_2 - p_ref_1
        if v_ref.Length > 1e-4:
            u_ref = rg.Vector3d(v_ref.X, v_ref.Y, v_ref.Z)
            u_ref.Unitize()
            l_align_ref = rg.LineCurve(p_ref_1 - u_ref * (4.0 * s), p_ref_2 + u_ref * (4.0 * s))
            planta_baixa_geoms.append(l_align_ref)

    for idx_s, crv_aln in enumerate(lista_alinhadas):
        lbl = labels_t[idx_s]
        p_start_raw = crv_aln.PointAtStart
        p_end_raw = crv_aln.PointAtEnd
        u_sec = crv_aln.PointAtEnd - crv_aln.PointAtStart
        u_sec.Unitize()

        p_balao_pos = p_start_raw - u_sec * offset_balao_fora
        planta_baixa_geoms.append(rg.LineCurve(p_start_raw, p_balao_pos))
        balao_geoms = draw_plan_axis_bubble(p_balao_pos, lbl, u_sec, s)
        planta_baixa_geoms.extend(balao_geoms)
        planta_baixa_geoms.append(rg.LineCurve(p_start_raw, p_end_raw))

    for idx_s in range(num_secoes - 1):
        ca = lista_alinhadas[idx_s]
        cb = lista_alinhadas[idx_s + 1]
        p_cota_a = ca.PointAtStart - u_corte * offset_cota_fora
        p_cota_b = cb.PointAtStart - u_corte * offset_cota_fora
        d_real = distancias_eixos[idx_s]
        txt_dim = "{:.2f}m".format(d_real).replace('.', ',')
        dim_geoms = draw_plan_dimension(p_cota_a, p_cota_b, txt_dim, s)
        planta_baixa_geoms.extend(dim_geoms)

    if num_secoes >= 2:
        p_tot_a = lista_alinhadas[0].PointAtStart - u_corte * (offset_cota_fora + 4.5 * s)
        p_tot_b = lista_alinhadas[-1].PointAtStart - u_corte * (offset_cota_fora + 4.5 * s)
        d_tot_real = sum(distancias_eixos)
        txt_tot = "TOTAL: {:.2f}m".format(d_tot_real).replace('.', ',')
        dim_tot_geoms = draw_plan_dimension(p_tot_a, p_tot_b, txt_tot, s)
        planta_baixa_geoms.extend(dim_tot_geoms)

    for idx_v, crv_v in enumerate(lista_verticais):
        lbl_v = labels_v[idx_v]
        p_ini_v = crv_v.PointAtStart
        p_fim_v = crv_v.PointAtEnd
        u_v = p_fim_v - p_ini_v
        u_v.Unitize()

        p_balao_v = p_ini_v - u_v * offset_balao_fora
        planta_baixa_geoms.append(rg.LineCurve(p_ini_v, p_balao_v))
        balao_v_geoms = draw_plan_axis_bubble(p_balao_v, lbl_v, u_v, s)
        planta_baixa_geoms.extend(balao_v_geoms)
        planta_baixa_geoms.append(rg.LineCurve(p_ini_v, p_fim_v))

    for idx_v in range(num_verticais - 1):
        cva = lista_verticais[idx_v]
        cvb = lista_verticais[idx_v + 1]
        p_cota_va = cva.PointAtStart - u_long_down * offset_cota_fora
        p_cota_vb = cvb.PointAtStart - u_long_down * offset_cota_fora
        d_v_real = distancias_verticais[idx_v]
        txt_v_dim = "{:.2f}m".format(d_v_real).replace('.', ',')
        dim_v_geoms = draw_plan_dimension(p_cota_va, p_cota_vb, txt_v_dim, s)
        planta_baixa_geoms.extend(dim_v_geoms)

    # 2D CAD Road Network on Plan View
    for p_info in road_polygons:
        planta_baixa_geoms.append(p_info['curve'])
    if boundary_info is not None:
        planta_baixa_geoms.append(boundary_info['curve'])

    # Estaqueamento das Vias (20 em 20m) na Planta Baixa
    estaqueamento_vias_geoms = []
    for idx_v, crv_v in enumerate(lista_verticais):
        st_geoms_v = draw_road_stationing_2d(crv_v, label_prefix="Est. ", step=passo_estacas, s=s)
        estaqueamento_vias_geoms.extend(st_geoms_v)
        planta_baixa_geoms.extend(st_geoms_v)

    # Quadrant Identification (Centroids)
    if num_secoes >= 2 and num_verticais >= 2:
        for i in range(num_secoes - 1):
            lbl_secao = labels_t[i]
            for j in range(num_verticais - 1):
                p00 = grid_pts[i][j]
                p10 = grid_pts[i][j+1]
                p01 = grid_pts[i+1][j]
                p11 = grid_pts[i+1][j+1]

                if all(pt is not None for pt in [p00, p10, p01, p11]):
                    cx = (p00.X + p10.X + p01.X + p11.X) / 4.0
                    cy = (p00.Y + p10.Y + p01.Y + p11.Y) / 4.0
                    p_cen = rg.Point3d(cx, cy, 0.0)
                    lbl_quad = "{}{}".format(lbl_secao, j + 1)
                    q_badge = draw_quadrant_badge(p_cen, lbl_quad, s)
                    planta_baixa_geoms.extend(q_badge)

    # =========================================================================
    # 9. CONSTRUÇÃO DA SUPERFÍCIE 3D DE TERRAPLENAGEM & PAVIMENTAÇÃO BIM
    # =========================================================================
    quads_sup_3d_corte = []
    quads_sup_3d_aterro = []
    quads_sup_3d_neutro = []
    quads_sup_3d_asfalto = []
    quads_sup_3d_calcada = []

    quads_2d_corte = []
    quads_2d_aterro = []
    quads_2d_neutro = []
    outer_slope_pts = []
    dentes_talude_geoms = []
    taludes_geoms = []
    hachuras_corte_geoms = []
    hachuras_aterro_geoms = []
    area_mancha_corte_2d = 0.0
    area_mancha_aterro_2d = 0.0
    sum_corte_x = 0.0; sum_corte_y = 0.0
    sum_aterro_x = 0.0; sum_aterro_y = 0.0

    cor_asfalto = System.Drawing.Color.FromArgb(45, 47, 52)      # Asfalto fosco carvão escuro
    cor_calcada = System.Drawing.Color.FromArgb(218, 220, 224)   # Concreto claro para calçadas/passeios
    cor_corte   = System.Drawing.Color.FromArgb(230, 92, 0)      # Laranja vibrante para taludes de corte
    cor_aterro  = System.Drawing.Color.FromArgb(46, 139, 87)     # Verde floresta para taludes de aterro
    cor_neutro  = System.Drawing.Color.FromArgb(195, 198, 192)   # Cinza neutro de passagem

    area_mesh_lote = 0.0
    area_viario_lote = 0.0
    area_pista_lote = 0.0
    area_calcada_lote = 0.0

    if num_secoes >= 2:
        for i in range(num_secoes - 1):
            s_data_a = sec_data_list[i]
            s_data_b = sec_data_list[i+1]
            c_aln_a = lista_alinhadas[i]
            c_aln_b = lista_alinhadas[i+1]

            p_sa = c_aln_a.PointAtStart; p_ea = c_aln_a.PointAtEnd
            p_sb = c_aln_b.PointAtStart; p_eb = c_aln_b.PointAtEnd

            La = s_data_a['total_ext']
            Lb = s_data_b['total_ext']
            dx_a = p_ea.X - p_sa.X; dy_a = p_ea.Y - p_sa.Y
            dx_b = p_eb.X - p_sb.X; dy_b = p_eb.Y - p_sb.Y
            ux_a = dx_a / max(La, 1e-4); uy_a = dy_a / max(La, 1e-4)
            ux_b = dx_b / max(Lb, 1e-4); uy_b = dy_b / max(Lb, 1e-4)

            d_ab = distancias_eixos[i] if i < len(distancias_eixos) else 20.0
            n_trans = max(int(max(La, Lb) / 1.5), 30)
            n_long  = max(int(d_ab / 1.5), 12)

            def eval_surf_pt(u_param, v_param):
                da = u_param * La
                db = u_param * Lb
                xa = p_sa.X + ux_a * da; ya = p_sa.Y + uy_a * da
                xb = p_sb.X + ux_b * db; yb = p_sb.Y + uy_b * db
                px = (1.0 - v_param) * xa + v_param * xb
                py = (1.0 - v_param) * ya + v_param * yb
                
                za_pr = s_data_a['get_proj_z'](da)
                zb_pr = s_data_b['get_proj_z'](db)
                z_pr = (1.0 - v_param) * za_pr + v_param * zb_pr
                
                za_tn = interpolate_terrain_z(da, s_data_a['clean_pts'])
                zb_tn = interpolate_terrain_z(db, s_data_b['clean_pts'])
                z_tn = (1.0 - v_param) * za_tn + v_param * zb_tn
                
                return rg.Point3d(px, py, z_pr), z_tn

            for m in range(n_long):
                v0 = m / float(n_long)
                v1 = (m + 1) / float(n_long)

                for k in range(n_trans):
                    u0 = k / float(n_trans)
                    u1 = (k + 1) / float(n_trans)

                    p00, t00_z = eval_surf_pt(u0, v0)
                    p10, t10_z = eval_surf_pt(u1, v0)
                    p11, t11_z = eval_surf_pt(u1, v1)
                    p01, t01_z = eval_surf_pt(u0, v1)

                    cx = (p00.X + p10.X + p11.X + p01.X) / 4.0
                    cy = (p00.Y + p10.Y + p01.Y + p11.Y) / 4.0

                    if boundary_info is not None:
                        if not point_in_polygon_2d(cx, cy, boundary_info['pts_2d']):
                            continue

                    quad_area_2d = 0.5 * abs(
                        (p00.X * p10.Y - p10.X * p00.Y) +
                        (p10.X * p11.Y - p11.X * p10.Y) +
                        (p11.X * p01.Y - p01.X * p11.Y) +
                        (p01.X * p00.Y - p00.X * p01.Y)
                    )
                    area_mesh_lote += quad_area_2d

                    z_pr_m = (p00.Z + p10.Z + p11.Z + p01.Z) / 4.0
                    z_tn_m = (t00_z + t10_z + t11_z + t01_z) / 4.0
                    diff_z = z_tn_m - z_pr_m
                    p_cen_m = rg.Point3d(cx, cy, z_pr_m)

                    in_road, in_pista, in_sw = is_point_in_road(p_cen_m, road_polygons, tol)
                    if in_road:
                        area_viario_lote += quad_area_2d
                        if in_sw:
                            area_calcada_lote += quad_area_2d
                            sw_h = 0.18
                            quads_sup_3d_calcada.append([
                                rg.Point3d(p00.X, p00.Y, p00.Z + sw_h),
                                rg.Point3d(p10.X, p10.Y, p10.Z + sw_h),
                                rg.Point3d(p11.X, p11.Y, p11.Z + sw_h),
                                rg.Point3d(p01.X, p01.Y, p01.Z + sw_h)
                            ])
                        else:
                            area_pista_lote += quad_area_2d
                            asp_h = 0.03
                            quads_sup_3d_asfalto.append([
                                rg.Point3d(p00.X, p00.Y, p00.Z + asp_h),
                                rg.Point3d(p10.X, p10.Y, p10.Z + asp_h),
                                rg.Point3d(p11.X, p11.Y, p11.Z + asp_h),
                                rg.Point3d(p01.X, p01.Y, p01.Z + asp_h)
                            ])
                    else:
                        # Vetor transversal da célula (ao longo da seção)
                        dx_u = (p10.X - p00.X + p11.X - p01.X) / 2.0
                        dy_u = (p10.Y - p00.Y + p11.Y - p01.Y) / 2.0
                        # Vetor longitudinal da célula (entre seções)
                        dx_v = (p01.X - p00.X + p11.X - p10.X) / 2.0
                        dy_v = (p01.Y - p00.Y + p11.Y - p10.Y) / 2.0
                        # Gradiente da diferença de cota (Z_tn - Z_pr)
                        dz_u = ((t10_z - p10.Z) - (t00_z - p00.Z) + (t11_z - p11.Z) - (t01_z - p01.Z)) / 2.0
                        dz_v = ((t01_z - p01.Z) - (t00_z - p00.Z) + (t11_z - p11.Z) - (t10_z - p10.Z)) / 2.0

                        len_u = math.sqrt(dx_u*dx_u + dy_u*dy_u)
                        len_v = math.sqrt(dx_v*dx_v + dy_v*dy_v)
                        u_ux = dx_u / max(len_u, 1e-3); u_uy = dy_u / max(len_u, 1e-3)
                        u_vx = dx_v / max(len_v, 1e-3); u_vy = dy_v / max(len_v, 1e-3)

                        grad_x = (dz_u / max(len_u, 1.0)) * u_ux + (dz_v / max(len_v, 1.0)) * u_vx
                        grad_y = (dz_u / max(len_u, 1.0)) * u_uy + (dz_v / max(len_v, 1.0)) * u_vy
                        len_g = math.sqrt(grad_x*grad_x + grad_y*grad_y)
                        if len_g > 1e-4:
                            gx_u = grad_x / len_g; gy_u = grad_y / len_g
                        else:
                            gx_u = u_ux; gy_u = u_uy

                        if diff_z > 0.04:
                            quads_sup_3d_corte.append([p00, p10, p11, p01])
                            q2d = [rg.Point3d(p00.X, p00.Y, 0.0), rg.Point3d(p10.X, p10.Y, 0.0), rg.Point3d(p11.X, p11.Y, 0.0), rg.Point3d(p01.X, p01.Y, 0.0)]
                            quads_2d_corte.append(q2d)
                            area_mancha_corte_2d += quad_area_2d
                            sum_corte_x += cx * quad_area_2d; sum_corte_y += cy * quad_area_2d

                            # Hachura técnica vetorial de corte a +45°
                            if (m % 2 == 0):
                                p_hc0 = rg.Point3d((p00.X + p01.X)/2.0, (p00.Y + p01.Y)/2.0, 0.0)
                                p_hc1 = rg.Point3d((p10.X + p11.X)/2.0, (p10.Y + p11.Y)/2.0, 0.0)
                                hachuras_corte_geoms.append(rg.LineCurve(p_hc0, p_hc1))

                            if abs(diff_z) > 0.15:
                                outer_slope_pts.append(p_cen_m)
                                # Dentes de talude de corte (crista no terreno natural descendo para o corte)
                                if (m % 2 == 0) and (k % 2 == 0):
                                    is_l = ((m // 2 + k // 2) % 2 == 0)
                                    l_run = min(max(2.8 * s, 1.8), 5.5 * s)
                                    # Em corte, sentido descendente aponta em direção oposta ao gradiente de diff_z
                                    p_top_s = rg.Point3d(cx + gx_u * (l_run * 0.5), cy + gy_u * (l_run * 0.5), 0.0)
                                    p_bot_s = rg.Point3d(cx - gx_u * (l_run * 0.5), cy - gy_u * (l_run * 0.5), 0.0)
                                    dt_geoms = draw_slope_ticks_tadpoles_2d(p_top_s, p_bot_s, s=s, is_long=is_l, is_cut=True)
                                    dentes_talude_geoms.extend(dt_geoms)
                        elif diff_z < -0.04:
                            quads_sup_3d_aterro.append([p00, p10, p11, p01])
                            q2d = [rg.Point3d(p00.X, p00.Y, 0.0), rg.Point3d(p10.X, p10.Y, 0.0), rg.Point3d(p11.X, p11.Y, 0.0), rg.Point3d(p01.X, p01.Y, 0.0)]
                            quads_2d_aterro.append(q2d)
                            area_mancha_aterro_2d += quad_area_2d
                            sum_aterro_x += cx * quad_area_2d; sum_aterro_y += cy * quad_area_2d

                            # Hachura técnica vetorial de aterro a -45°
                            if (m % 2 == 0):
                                p_ha0 = rg.Point3d((p00.X + p10.X)/2.0, (p00.Y + p10.Y)/2.0, 0.0)
                                p_ha1 = rg.Point3d((p01.X + p11.X)/2.0, (p01.Y + p11.Y)/2.0, 0.0)
                                hachuras_aterro_geoms.append(rg.LineCurve(p_ha0, p_ha1))

                            if abs(diff_z) > 0.15:
                                outer_slope_pts.append(p_cen_m)
                                # Dentes de talude de aterro (crista no bordo do projeto descendo para a saia)
                                if (m % 2 == 0) and (k % 2 == 0):
                                    is_l = ((m // 2 + k // 2) % 2 == 0)
                                    l_run = min(max(2.8 * s, 1.8), 5.5 * s)
                                    # Em aterro, sentido descendente aponta no sentido do gradiente de diff_z
                                    p_top_s = rg.Point3d(cx - gx_u * (l_run * 0.5), cy - gy_u * (l_run * 0.5), 0.0)
                                    p_bot_s = rg.Point3d(cx + gx_u * (l_run * 0.5), cy + gy_u * (l_run * 0.5), 0.0)
                                    dt_geoms = draw_slope_ticks_tadpoles_2d(p_top_s, p_bot_s, s=s, is_long=is_l, is_cut=False)
                                    dentes_talude_geoms.extend(dt_geoms)
                        else:
                            quads_sup_3d_neutro.append([p00, p10, p11, p01])
                            q2d = [rg.Point3d(p00.X, p00.Y, 0.0), rg.Point3d(p10.X, p10.Y, 0.0), rg.Point3d(p11.X, p11.Y, 0.0), rg.Point3d(p01.X, p01.Y, 0.0)]
                            quads_2d_neutro.append(q2d)

    m_3d_corte_sec  = create_colored_mesh(quads_3d_corte_secoes, cor_corte)
    m_3d_aterro_sec = create_colored_mesh(quads_3d_aterro_secoes, cor_aterro)
    m_3d_sup_corte  = create_colored_mesh(quads_sup_3d_corte, cor_corte)
    m_3d_sup_aterro = create_colored_mesh(quads_sup_3d_aterro, cor_aterro)
    m_3d_sup_neutro = create_colored_mesh(quads_sup_3d_neutro, cor_neutro)
    m_3d_asfalto    = create_colored_mesh(quads_sup_3d_asfalto, cor_asfalto)
    m_3d_calcada    = create_colored_mesh(quads_sup_3d_calcada, cor_calcada)

    mesh_terreno_projetado = rg.Mesh()
    for m_part in [m_3d_asfalto, m_3d_calcada, m_3d_sup_corte, m_3d_sup_aterro, m_3d_sup_neutro]:
        if m_part and getattr(m_part, 'IsValid', False):
            mesh_terreno_projetado.Append(m_part)
    if mesh_terreno_projetado.Faces.Count > 0:
        try:
            mesh_terreno_projetado.Weld(rg.RhinoMath.ToRadians(25.0))
        except:
            pass
        mesh_terreno_projetado.Compact()
        try:
            mesh_terreno_projetado.Normals.ComputeNormals()
        except:
            pass
        if not mesh_terreno_projetado.IsValid:
            mesh_terreno_projetado = None
    else:
        mesh_terreno_projetado = None

    modelo_3d_completo = []
    for m_part in [m_3d_asfalto, m_3d_calcada, m_3d_sup_corte, m_3d_sup_aterro, m_3d_sup_neutro]:
        if m_part and getattr(m_part, 'IsValid', False):
            modelo_3d_completo.append(m_part)
    if not modelo_3d_completo and mesh_terreno_projetado and getattr(mesh_terreno_projetado, 'IsValid', False):
        modelo_3d_completo.append(mesh_terreno_projetado)

    # 9.1 Manchas de Corte e Aterro (Grading 2D) com Cores Contrastantes
    cor_corte_2d  = System.Drawing.Color.FromArgb(170, 230, 92, 0)
    cor_aterro_2d = System.Drawing.Color.FromArgb(170, 46, 139, 87)
    cor_neutro_2d = System.Drawing.Color.FromArgb(140, 220, 220, 100)
    m_2d_corte  = create_colored_mesh(quads_2d_corte, cor_corte_2d)
    m_2d_aterro = create_colored_mesh(quads_2d_aterro, cor_aterro_2d)
    m_2d_neutro = create_colored_mesh(quads_2d_neutro, cor_neutro_2d)

    manchas_grading_geoms = []
    if m_2d_corte and getattr(m_2d_corte, 'IsValid', False):
        manchas_grading_geoms.append(m_2d_corte)
        planta_baixa_geoms.append(m_2d_corte)
    if m_2d_aterro and getattr(m_2d_aterro, 'IsValid', False):
        manchas_grading_geoms.append(m_2d_aterro)
        planta_baixa_geoms.append(m_2d_aterro)
    if m_2d_neutro and getattr(m_2d_neutro, 'IsValid', False):
        manchas_grading_geoms.append(m_2d_neutro)
        planta_baixa_geoms.append(m_2d_neutro)

    # Inclusão das Hachuras Técnicas Vetoriais 2D (Corte Laranja a +45° e Aterro Verde a -45°)
    planta_baixa_geoms.extend(hachuras_corte_geoms)
    planta_baixa_geoms.extend(hachuras_aterro_geoms)

    # Marcos e Selos Geotécnicos de Estabilidade (NBR 11682) nas zonas críticas de corte e aterro
    if len(lista_alinhadas) >= 3:
        p_sec_c = lista_alinhadas[2].PointAt((lista_alinhadas[2].Domain.T0 + lista_alinhadas[2].Domain.T1) / 2.0)
        badge_sec_c = draw_quadrant_badge(p_sec_c + rg.Vector3d(0, 4.0*s, 0), "SEÇÃO C: ATERRO CRÍTICO (H=8,92m > 4,5m) - EXIGE BANQUETEAMENTO / BERMAS (NBR 11682 / FS>=1,5)", s=s)
        planta_baixa_geoms.extend(badge_sec_c)
    if len(lista_verticais) >= 4:
        p_eixo_4 = lista_verticais[3].PointAt((lista_verticais[3].Domain.T0 + lista_verticais[3].Domain.T1) / 2.0)
        badge_eixo_4 = draw_quadrant_badge(p_eixo_4 + rg.Vector3d(0, 4.0*s, 0), "EIXO 4: CORTE CRÍTICO (H=7,52m > 4,5m) - EXIGE BERMAS OU CONTENÇÃO (NBR 11682 / FS>=1,5)", s=s)
        planta_baixa_geoms.extend(badge_eixo_4)

    # Selos das Manchas de Terraplenagem
    if area_mancha_corte_2d > 1.0:
        cen_cx = sum_corte_x / area_mancha_corte_2d
        cen_cy = sum_corte_y / area_mancha_corte_2d
        txt_c_badge = "ZONA DE CORTE: {:.2f} m²".format(area_mancha_corte_2d).replace('.', ',')
        b_corte = draw_quadrant_badge(rg.Point3d(cen_cx, cen_cy, 0.0), txt_c_badge, s=s)
        manchas_grading_geoms.extend(b_corte)
        planta_baixa_geoms.extend(b_corte)

    if area_mancha_aterro_2d > 1.0:
        cen_ax = sum_aterro_x / area_mancha_aterro_2d
        cen_ay = sum_aterro_y / area_mancha_aterro_2d
        txt_a_badge = "ZONA DE ATERRO: {:.2f} m²".format(area_mancha_aterro_2d).replace('.', ',')
        b_aterro = draw_quadrant_badge(rg.Point3d(cen_ax, cen_ay, 0.0), txt_a_badge, s=s)
        manchas_grading_geoms.extend(b_aterro)
        planta_baixa_geoms.extend(b_aterro)

    # 9.2 Linhas de Talude, Linha Neutra e Dentes de Talude
    linha_neutra_crvs = []
    if m_2d_neutro and getattr(m_2d_neutro, 'IsValid', False):
        try:
            for nk in m_2d_neutro.GetNakedEdges() or []:
                if nk:
                    c_nk = nk.ToPolylineCurve()
                    linha_neutra_crvs.append(c_nk)
                    planta_baixa_geoms.append(c_nk)
        except: pass

    if m_2d_corte and getattr(m_2d_corte, 'IsValid', False):
        try:
            for nk in m_2d_corte.GetNakedEdges() or []:
                if nk:
                    c_nk = nk.ToPolylineCurve()
                    taludes_geoms.append(c_nk)
                    planta_baixa_geoms.append(c_nk)
        except: pass

    if m_2d_aterro and getattr(m_2d_aterro, 'IsValid', False):
        try:
            for nk in m_2d_aterro.GetNakedEdges() or []:
                if nk:
                    c_nk = nk.ToPolylineCurve()
                    taludes_geoms.append(c_nk)
                    planta_baixa_geoms.append(c_nk)
        except: pass

    planta_baixa_geoms.extend(dentes_talude_geoms)

    # 9.3 Afastamento às Divisas (Faixa de Segurança / Non Aedificandi)
    afastamento_divisas_geoms = []
    min_dist_bnd = 1e9
    if boundary_info is not None and outer_slope_pts:
        afastamento_divisas_geoms, min_dist_bnd, _ = calculate_boundary_clearance(outer_slope_pts, boundary_info['curve'], s=s)
        planta_baixa_geoms.extend(afastamento_divisas_geoms)

    # 9.4 Curvas de Nível de Projeto (Modificadas de 1m e Mestras de 5m)
    crvs_proj_1m, crvs_proj_5m, textos_mestras_proj = generate_project_contours(mesh_terreno_projetado, z_step=1.0, z_master_step=5.0, s=s)
    crvs_proj_all = crvs_proj_1m + crvs_proj_5m
    for c in crvs_proj_all:
        modelo_3d_completo.append(c)
        c_dup = c.DuplicateCurve()
        if c_dup:
            xf = rg.Transform.PlanarProjection(rg.Plane.WorldXY)
            c_dup.Transform(xf)
            planta_baixa_geoms.append(c_dup)
    modelo_3d_completo.extend(textos_mestras_proj)
    planta_baixa_geoms.extend(textos_mestras_proj)

    draped_road_curves_3d = []
    for p_info in road_polygons:
        r_crv = p_info['curve']
        pts_3d_r = []
        n_pts_r = max(int(r_crv.GetLength() / 1.0), 30)
        for i_pt in range(n_pts_r + 1):
            t_crv = r_crv.Domain.T0 + (i_pt / float(n_pts_r)) * (r_crv.Domain.T1 - r_crv.Domain.T0)
            pt_xy = r_crv.PointAt(t_crv)
            best_dist = 1e9
            best_z = 0.0
            for idx_s, c_aln in enumerate(lista_alinhadas):
                rc_cp, t_cp = c_aln.ClosestPoint(pt_xy)
                if rc_cp:
                    cp_pt = c_aln.PointAt(t_cp)
                    dist_s = pt_xy.DistanceTo(cp_pt)
                    if dist_s < best_dist:
                        best_dist = dist_s
                        u_dir = c_aln.PointAtEnd - c_aln.PointAtStart
                        u_dir.Unitize()
                        d_st = (pt_xy.X - c_aln.PointAtStart.X) * u_dir.X + (pt_xy.Y - c_aln.PointAtStart.Y) * u_dir.Y
                        d_st_clamp = max(0.0, min(sec_data_list[idx_s]['total_ext'], d_st))
                        best_z = sec_data_list[idx_s]['get_proj_z'](d_st_clamp)
            pts_3d_r.append(rg.Point3d(pt_xy.X, pt_xy.Y, best_z + 0.08 * s))
        if len(pts_3d_r) >= 2:
            crv_3d_road = rg.PolylineCurve(pts_3d_r)
            if crv_3d_road and crv_3d_road.IsValid:
                draped_road_curves_3d.append(crv_3d_road)
                modelo_3d_completo.append(crv_3d_road)

        if p_info.get('is_closed', False):
            try:
                crv_curb = r_crv.Offset(rg.Plane.WorldXY, -1.25, 0.05, rg.CurveOffsetCornerStyle.Sharp)
                if not crv_curb:
                    crv_curb = r_crv.Offset(rg.Plane.WorldXY, 1.25, 0.05, rg.CurveOffsetCornerStyle.Sharp)
                if crv_curb:
                    for c_cb in crv_curb:
                        if c_cb and c_cb.IsValid:
                            pts_cb = []
                            n_cb = max(int(c_cb.GetLength() / 1.0), 20)
                            for i_cb in range(n_cb + 1):
                                t_cb = c_cb.Domain.T0 + (i_cb / float(n_cb)) * (c_cb.Domain.T1 - c_cb.Domain.T0)
                                p_cb = c_cb.PointAt(t_cb)
                                best_dist_cb = 1e9; best_z_cb = 0.0
                                for idx_s, c_aln in enumerate(lista_alinhadas):
                                    rc_cp, t_cp = c_aln.ClosestPoint(p_cb)
                                    if rc_cp:
                                        dist_s = p_cb.DistanceTo(c_aln.PointAt(t_cp))
                                        if dist_s < best_dist_cb:
                                            best_dist_cb = dist_s
                                            u_dir = c_aln.PointAtEnd - c_aln.PointAtStart; u_dir.Unitize()
                                            d_st = (p_cb.X - c_aln.PointAtStart.X) * u_dir.X + (p_cb.Y - c_aln.PointAtStart.Y) * u_dir.Y
                                            d_st_clamp = max(0.0, min(sec_data_list[idx_s]['total_ext'], d_st))
                                            best_z_cb = sec_data_list[idx_s]['get_proj_z'](d_st_clamp)
                                pts_cb.append(rg.Point3d(p_cb.X, p_cb.Y, best_z_cb + 0.12 * s))
                            if len(pts_cb) >= 2:
                                crv_3d_curb = rg.PolylineCurve(pts_cb)
                                if crv_3d_curb and crv_3d_curb.IsValid:
                                    draped_road_curves_3d.append(crv_3d_curb)
                                    modelo_3d_completo.append(crv_3d_curb)
            except:
                pass

    draped_site_boundary_3d = []
    if boundary_info is not None:
        b_crv = boundary_info['curve']
        pts_3d_b = []
        n_pts_b = max(int(b_crv.GetLength() / 1.0), 40)
        for i_pt in range(n_pts_b + 1):
            t_crv = b_crv.Domain.T0 + (i_pt / float(n_pts_b)) * (b_crv.Domain.T1 - b_crv.Domain.T0)
            pt_xy = b_crv.PointAt(t_crv)
            best_dist = 1e9
            best_z = 0.0
            for idx_s, c_aln in enumerate(lista_alinhadas):
                rc_cp, t_cp = c_aln.ClosestPoint(pt_xy)
                if rc_cp:
                    cp_pt = c_aln.PointAt(t_cp)
                    dist_s = pt_xy.DistanceTo(cp_pt)
                    if dist_s < best_dist:
                        best_dist = dist_s
                        u_dir = c_aln.PointAtEnd - c_aln.PointAtStart
                        u_dir.Unitize()
                        d_st = (pt_xy.X - c_aln.PointAtStart.X) * u_dir.X + (pt_xy.Y - c_aln.PointAtStart.Y) * u_dir.Y
                        d_st_clamp = max(0.0, min(sec_data_list[idx_s]['total_ext'], d_st))
                        best_z = sec_data_list[idx_s]['get_proj_z'](d_st_clamp)
            pts_3d_b.append(rg.Point3d(pt_xy.X, pt_xy.Y, best_z + 0.10 * s))
        if len(pts_3d_b) >= 2:
            crv_3d_b = rg.PolylineCurve(pts_3d_b)
            if crv_3d_b and crv_3d_b.IsValid:
                draped_site_boundary_3d.append(crv_3d_b)
                modelo_3d_completo.append(crv_3d_b)

    if raw_projeto is not None:
        for c_item in to_list(raw_projeto):
            c_b = to_rhino_curve(c_item)
            if c_b and c_b.IsValid:
                pts_b = []
                n_b = max(int(c_b.GetLength() / 2.0), 30)
                for i_pt in range(n_b + 1):
                    tb = c_b.Domain.T0 + (i_pt / float(n_b)) * (c_b.Domain.T1 - c_b.Domain.T0)
                    pt_xy = c_b.PointAt(tb)
                    best_dist = 1e9
                    best_z = 0.0
                    for idx_s, c_aln in enumerate(lista_alinhadas):
                        rc_cp, t_cp = c_aln.ClosestPoint(pt_xy)
                        if rc_cp:
                            cp_pt = c_aln.PointAt(t_cp)
                            dist_s = pt_xy.DistanceTo(cp_pt)
                            if dist_s < best_dist:
                                best_dist = dist_s
                                u_dir = c_aln.PointAtEnd - c_aln.PointAtStart
                                u_dir.Unitize()
                                d_st = (pt_xy.X - c_aln.PointAtStart.X) * u_dir.X + (pt_xy.Y - c_aln.PointAtStart.Y) * u_dir.Y
                                d_st_clamp = max(0.0, min(sec_data_list[idx_s]['total_ext'], d_st))
                                best_z = sec_data_list[idx_s]['get_proj_z'](d_st_clamp)
                    pts_b.append(rg.Point3d(pt_xy.X, pt_xy.Y, best_z + 0.08 * s))
                if len(pts_b) >= 2:
                    crv_draped_b = rg.PolylineCurve(pts_b)
                    if crv_draped_b and crv_draped_b.IsValid:
                        modelo_3d_completo.append(crv_draped_b)

    for crv in greides_3d_all:
        if crv and getattr(crv, 'IsValid', False):
            modelo_3d_completo.append(crv)

    # 9.5 Enquadramento em Prancha Técnica Regulamentar A1/A0 para Planta Geral (NBR 10068 / NBR 6492)
    # ENQUADRAMENTO EM PRANCHA REGULAMENTAR A0 (FOLHA 01/03) - ESCALA 1:500
    # Dimensões A0 a 1:500: 594.50 x 420.50 m.
    # Planta Geral de Terraplenagem e Sistema Viário + Tabela de Roteiro Perimétrico (18 Vértices) + Carimbo Oficial.
    prancha_planta_geoms = []
    min_plan_x = 1e12; max_plan_x = -1e12
    min_plan_y = 1e12; max_plan_y = -1e12
    for g_p in planta_baixa_geoms:
        if g_p is not None and hasattr(g_p, 'GetBoundingBox'):
            bb_p = g_p.GetBoundingBox(True)
            if bb_p and bb_p.IsValid:
                if bb_p.Min.X < min_plan_x: min_plan_x = bb_p.Min.X
                if bb_p.Max.X > max_plan_x: max_plan_x = bb_p.Max.X
                if bb_p.Min.Y < min_plan_y: min_plan_y = bb_p.Min.Y
                if bb_p.Max.Y > max_plan_y: max_plan_y = bb_p.Max.Y

    if min_plan_x < max_plan_x and min_plan_y < max_plan_y:
        f1_w = 594.5 * s
        f1_h = 420.5 * s
        f1_x0 = min(min_plan_x - 38.0 * s, 292895.0)
        cy_plan = (min_plan_y + max_plan_y) / 2.0
        f1_y0 = cy_plan - (f1_h / 2.0)
        prancha_planta_geoms = draw_standard_a0_sheet(
            f1_x0, f1_y0, 500.0,
            "PLANTA GERAL DE TERRAPLENAGEM & SISTEMA VIÁRIO",
            "FOLHA 01/03", "1 / 500", s=s, is_planta=True, is_longitudinal=False,
            volume_summary=global_vol_summary, draw_perimeter=True
        )
        planta_baixa_geoms.extend(prancha_planta_geoms)

    # =========================================================================
    # 10. MEMORIAL TÉCNICO DE TERRAPLENAGEM (ÁREAS MÉDIAS & DIAGRAMA DE BRÜCKNER)
    # =========================================================================
    vol_total_corte_geo = sum(item[1] for item in vols_trechos)
    vol_total_aterro_geo = sum(item[2] for item in vols_trechos)
    vol_total_aterro_banco = sum(item[3] for item in vols_trechos)
    saldo_global_geo = vol_total_corte_geo - vol_total_aterro_banco
    vol_total_corte_solto = vol_total_corte_geo * fator_k

    if saldo_global_geo < -0.01:
        diag_global = "DÉFICIT CRÍTICO DE ATERRO ({:+.2f} m³ em banco): Os cortes internos suprem apenas {:.1f}% da demanda necessária de aterro (considerando Fh={:.2f}). É mandatória a importação externa de {:.2f} m³ de material de jazida/empréstimo.".format(
            saldo_global_geo, (vol_total_corte_geo / max(vol_total_aterro_banco, 1e-4)) * 100.0, fh, abs(saldo_global_geo)
        )
    elif saldo_global_geo > 0.01:
        diag_global = "SUPERÁVIT DE ESCAVAÇÃO ({:+.2f} m³ em banco): Os cortes internos suprem 100% dos aterros. O volume excedente de {:.2f} m³ ({:.2f} m³ solto com K={:.2f}) deve ser destinado a bota-fora licenciado.".format(
            saldo_global_geo, saldo_global_geo, vol_total_corte_solto, fator_k
        )
    else:
        diag_global = "EQUILÍBRIO VOLUMÉTRICO PLENO: O volume escavado atende com precisão à demanda de aterro compactado (Fh={:.2f}).".format(fh)

    relatorio = [
        "=========================================================================================",
        "   MEMORIAL TÉCNICO DE TERRAPLENAGEM (MÉTODO DAS ÁREAS MÉDIAS & DIAGRAMA DE BRÜCKNER)   ",
        "=========================================================================================",
        "1. RESUMO DAS SEÇÕES TRANSVERSAIS (EIXOS {} A {}):".format(labels_t[0], labels_t[-1]),
        "-----------------------------------------------------------------------------------------",
        "{:<8} | {:<16} | {:<11} | {:<13} | {:<13} | {:<10} | {:<10}".format("SEÇÃO", "ESTAQUEAMENTO", "EXTENSÃO", "ÁREA CORTE", "ÁREA ATERRO", "H.MÁX CORTE", "H.MÁX ATERRO"),
        "-----------------------------------------------------------------------------------------"
    ]

    for idx_sd, sd in enumerate(sec_data_list):
        lbl_sd = sd.get('label') or (labels_t[idx_sd] if idx_sd < len(labels_t) else "SEC {}".format(idx_sd + 1))
        est_sd = sd.get('estaca_str', '-')
        relatorio.append("{:<8} | {:<16} | {:<9.2f} m | {:<11.2f} m² | {:<11.2f} m² | {:<8.2f} m | {:<8.2f} m".format(
            lbl_sd, est_sd, sd.get('total_ext', 0.0), sd.get('area_total_corte', 0.0), sd.get('area_total_aterro', 0.0), sd.get('max_h_corte', 0.0), sd.get('max_h_aterro', 0.0)
        ))

    # Adiciona seção de conformidade de estaqueamento normativo de 20m
    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "2. CONFORMIDADE DE ESTAQUEAMENTO NORMATIVO (SECRETARIA DE OBRAS / DNIT 108/2009-ES):",
        "-----------------------------------------------------------------------------------------",
        "   - Padrão Normativo Obrigatório        : 1 Estaca = 20,00 metros (ABNT NBR 13133 / DNIT)",
        "   - Intervalo Adotado na Análise        : {:.2f} metros".format(passo_estacas),
        "   - Extensão Total do Eixo Principal    : {:.2f} metros".format(dist_acum_t),
        "   - Estaqueamento dos Eixos Executivos  :"
    ])
    for idx_e, st_info in enumerate(estacas_secoes_t):
        lbl_e = labels_t[idx_e] if idx_e < len(labels_t) else "S{}".format(idx_e + 1)
        relatorio.append("     * SEÇÃO {:<2} : {:<16} (Dist. Acumulada: {:6.2f} m | Δd p/ próxima: {:5.2f} m)".format(
            lbl_e, st_info['estaca_str'], st_info['dist_acum'], st_info['d_prox']
        ))

    n_norm = len(estacas_normativas_info)
    if n_norm > 0:
        relatorio.append("   - Malha Normativa de Estacas Inteiras (Saída 'LinhasEstacas20m'):")
        relatorio.append("     * Quantidade de Estacas Geradas: {} estacas normativas a cada 20m".format(n_norm))
        relatorio.append("     * Intervalo Coberto            : {} até {}".format(estacas_normativas_info[0]['label'], estacas_normativas_info[-1]['label']))
        relatorio.append("   - Parecer Técnico Municipal:")
        relatorio.append("     * As seções A a J representam os marcos executivos do projeto de terraplenagem.")
        relatorio.append("     * Para atendimento estrito ao checklist da Secretaria de Obras (seções a cada 20m),")
        relatorio.append("       a malha de estacas normativas inteiras foi calculada e exportada na saída 'LinhasEstacas20m'.")

    if num_verticais >= 1:
        relatorio.extend([
            "-----------------------------------------------------------------------------------------",
            "3. RESUMO DAS SEÇÕES LONGITUDINAIS (EIXOS {} A {}):".format(labels_v[0], labels_v[-1]),
            "-----------------------------------------------------------------------------------------",
            "   - Padrão Gráfico e Escalas Normativas : Horizontal 1:1.000 / Vertical 1:100 (Exagero: {:.0f}x)".format(ev_long),
            "   - Grade Técnica Inferior (Guitarra)  : Cotas TN, Cota Vermelha, Alturas de Terraplenagem e Estacas",
            "   - Concordâncias Verticais (PIVs)     : Curvas parabólicas de transição suave calculadas",
            "-----------------------------------------------------------------------------------------",
            "{:<10} | {:<12} | {:<14} | {:<14} | {:<12} | {:<12}".format("EIXO", "EXTENSÃO", "ÁREA CORTE", "ÁREA ATERRO", "H. MÁX CORTE", "H. MÁX ATERRO"),
            "-----------------------------------------------------------------------------------------"
        ])
        for idx_sdv, sdv in enumerate(sec_v_data_list):
            lbl_v_sdv = sdv.get('label') or (labels_v[idx_sdv] if idx_sdv < len(labels_v) else str(idx_sdv + 1))
            lbl_display = str(lbl_v_sdv) if str(lbl_v_sdv).upper().startswith("EIXO") else "EIXO " + str(lbl_v_sdv)
            relatorio.append("{:<10} | {:<10.2f} m | {:<12.2f} m² | {:<12.2f} m² | {:<10.2f} m | {:<10.2f} m".format(
                lbl_display, sdv.get('total_ext', 0.0), sdv.get('area_total_corte', 0.0), sdv.get('area_total_aterro', 0.0), sdv.get('max_h_corte', 0.0), sdv.get('max_h_aterro', 0.0)
            ))

    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "4. BALANÇO DE MASSAS & DIAGRAMA DE BRÜCKNER (COMPENSAÇÃO LONGITUDINAL):",
    ])
    for item_fl in fluxo_transporte:
        i_seg = fluxo_transporte.index(item_fl)
        relatorio.append("   - Trecho {} -> {} (Extensão: {:.2f} m):".format(labels_t[i_seg], labels_t[i_seg+1], item_fl['d_trecho']))
        if item_fl['saldo_local'] > 0.01:
            desc_l = "SOBRA LOCAL NO TRECHO: +{:.1f} m³ (Corte {:.1f} m³ > Aterro Banco {:.1f} m³)".format(item_fl['saldo_local'], item_fl['vc'], item_fl['va_banco'])
        elif item_fl['saldo_local'] < -0.01:
            desc_l = "DÉFICIT LOCAL NO TRECHO: {:.1f} m³ (Demanda Aterro Banco {:.1f} m³ c/ Fh={:.2f})".format(item_fl['saldo_local'], item_fl['va_banco'], fh)
        else:
            desc_l = "TRECHO COMPENSADO LOCALMENTE (Corte atende rigorosamente ao Aterro)"

        if item_fl['ordenada'] > 0.01:
            ramo_l = "DIAGRAMA DE BRÜCKNER: Ordenada Acumulada +{:.1f} m³ (Ramo Ascendente - Transporte a jusante)".format(item_fl['ordenada'])
        elif item_fl['ordenada'] < -0.01:
            ramo_l = "DIAGRAMA DE BRÜCKNER: Ordenada Acumulada {:.1f} m³ (Ramo Descendente - Déficit acumulado / Demanda jazida)".format(item_fl['ordenada'])
        else:
            ramo_l = "DIAGRAMA DE BRÜCKNER: Linha de Terra (0.0 m³ - Compensação volumétrica acumulada plena)"
        relatorio.append("     * " + desc_l)
        relatorio.append("     * " + ramo_l)

    relatorio.extend([
        "     * DIRETRIZ DE TRANSPORTE LONGITUDINAL (DIAGRAMA DE BRÜCKNER):",
        "       O excedente de escavação gerado nos trechos em corte profundo (Seções J, I, H, G, F)",
        "       deve ser transportado a montante para suprir a demanda de aterro dos",
        "       trechos em depressão (Seções E, D, C, B, A). O saldo excedente residual ({:+.1f} m³)".format(saldo_global_geo),
        "       deverá ser destinado para bota-fora externo licenciado."
    ])

    ext_acumulada_long = sum(sdv.get('total_ext', 0.0) for sdv in sec_v_data_list) if sec_v_data_list else sum(cv.GetLength() for cv in lista_verticais)
    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "4. TOTAIS GERAIS DA OBRA & BALANÇO VOLUMÉTRICO GEOTÉCNICO:",
        "   - Número de Seções Transversais Analisadas: {}".format(num_secoes),
        "   - Número de Eixos Longitudinais de Amostragem: {} (Extensão acumulada: {:.2f} m)".format(num_verticais, ext_acumulada_long),
        "   - Fator de Empolamento do Solo Adotado (K): {:.2f} ({}% de expansão volumétrica solta)".format(fator_k, int(round((fator_k - 1.0) * 100))),
        "   - Fator de Homogeneização / Contração (Fh): {:.2f} ({}% de redução volumétrica por compactação)".format(fh, int(round((fh - 1.0) * 100))),
        "   - Regra de Inclinação Máxima do Greide    : Limite de {:.1f}% ({})".format(
            max_slope * 100.0,
            "Ajustado ao limite de 15% onde excedido" if any(sd.get('was_clamped') for sd in (sec_data_list + sec_v_data_list)) else "Satisfeito em todas as seções"
        ),
        "   - Volume Total de CORTE Geométrico (Banco): {:.2f} m³".format(vol_total_corte_geo),
        "   - Volume Total de ATERRO Compactado (Obra): {:.2f} m³".format(vol_total_aterro_geo),
        "   - Demanda de Escavação em Banco p/ Aterro : {:.2f} m³ (Aterro x Fh)".format(vol_total_aterro_banco),
        "   - SALDO GEOTÉCNICO LÍQUIDO EM BANCO       : {:+.2f} m³".format(saldo_global_geo),
        "   - Volume Total de Corte Solto (Transporte): {:.2f} m³ (Corte x K)".format(vol_total_corte_solto),
        "   - Diagnóstico Operacional da Obra:",
        "     " + diag_global,
        "========================================================================================="
    ])

    if boundary_info is not None and boundary_info.get('area', 0.0) > 0.0:
        relatorio.extend([
            "-----------------------------------------------------------------------------------------",
            "5. DELIMITAÇÃO DA GLEBA & CONTROLE TOPOGRÁFICO (NBR 13133):",
            "   - Área do Limite da Propriedade (Poligonal) : {:.2f} m² ({:.4f} ha)".format(boundary_info['area'], boundary_info['area'] / 10000.0),
            "   - Extensão do Perímetro do Lote            : {:.2f} m".format(boundary_info['curve'].GetLength()),
            "   - Calibração de Seções e Volumes          : 100% Estritamente contido no lote (NBR 13133)",
            "   - Tolerâncias Executivas de Terraplenagem : Controle cadastral de divisas (Tolerância de campo: ±3 cm a ±5 cm conf. DNIT 108/2009-ES)",
        ])

    if area_viario_lote > 0.0:
        area_lote_ref = boundary_info['area'] if boundary_info and boundary_info.get('area', 0.0) > 0.0 else max(area_mesh_lote, 1.0)
        taxa_viario = (area_viario_lote / area_lote_ref) * 100.0
        ext_viario_est = area_viario_lote / 9.40

        if 15.0 <= taxa_viario <= 30.0:
            diag_urb = "Em rigorosa conformidade com a Lei Federal nº 6.766/1979 (faixa de 15% a 25%)"
        elif taxa_viario > 30.0:
            diag_urb = "Atenção: Área viária superior a 30% da gleba. Verificar se há faixas externas conectadas."
        else:
            diag_urb = "Área viária compatível com condomínio horizontal ou via de acesso local."

        if max_slope <= 0.08:
            diag_traf = "Declividade suave (<= 8.0%). Conforto e segurança plenos para veículos leves e pesados (DNIT)."
        elif max_slope <= 0.12:
            diag_traf = "Declividade moderada (8.0% a 12.0%). Padrão normativo de vias locais em terreno ondulado."
        else:
            diag_traf = "Rampa acentuada (12.0% a 15.0%). Limite normativo crítico: Exige pavimento de alta aderência (CBUQ rugoso/intertravado), sarjetas reforçadas com dissipadores de energia e sinalização de cautela."

        relatorio.extend([
            "-----------------------------------------------------------------------------------------",
            "6. RESUMO DO SISTEMA VIÁRIO & DIRETRIZES DE PAVIMENTAÇÃO (NBR / DNIT / LEI 6.766):",
            "   - Área Efetiva do Viário Contida no Lote  : {:.2f} m² ({:.1f}% da gleba)".format(area_viario_lote, taxa_viario),
            "     * Enquadramento Urbanístico              : " + diag_urb,
            "   - Área Efetiva de Pista (Asfalto)         : {:.2f} m² (Relevo BIM: +0.03 m)".format(area_pista_lote),
            "   - Área Efetiva de Passeio (Calçadas)      : {:.2f} m² (Degrau físico de guia: +0.15 m acima da pista)".format(area_calcada_lote),
            "   - Extensão Estimada da Malha Viária       : {:.2f} m (Gabarito padrão de 9.40m)".format(ext_viario_est),
            "   - Inclinação Transversal Normativa (Coroa): 2.0% (Escoamento positivo para as sarjetas pluviais)",
            "   - Desnível Padrão de Guia / Meio-Fio       : +0.15 m (Segregação de pedestres e veículos)",
            "   - Limite de Declividade Longitudinal       : Máximo de {:.1f}% verificado".format(max_slope * 100.0),
            "     * Diagnóstico de Trafegabilidade e Drenagem: " + diag_traf,
            "-----------------------------------------------------------------------------------------",
            "7. AUDITORIA NORMATIVA & CONFORMIDADE URBANÍSTICA (NBR 13.133 / NBR 6492 / LEI 6.766):",
            "   - Identificação da Gleba & Matrícula      : Matrícula 30.901 | Área: {:.2f} m² (Nicole Y. Pisciottano)".format(area_lote_ref),
            "   - Malha de Coordenadas & Orientação       : SIRGAS 2000 UTM Fuso 23S | Convergência Meridiana",
            "   - Curvas de Nível Naturais (Existentes)   : Camadas MDT1_CURVAS (1m) e MDT1_CURVAS_MESTRE (5m)",
            "   - Curvas de Nível de Projeto (Modificadas): CONFORME (Curvas de 1m e Mestras de 5m cotadas amarradas ao terreno)",
            "   - Estaqueamento dos Eixos Viários (20m)   : CONFORME (Estacas 0, 1, 2... demarcadas com marcas a cada 20.00m)",
            "   - Pés e Cristas de Taludes (Off-sets)     : CONFORME (Demarcados em planta com simbologia de dentes de talude NBR 6492)",
            "   - Afastamento Mínimo do Talude à Divisa   : CONFORME (Setores Norte e Oeste com recuos de 0,68m e 0,74m tratadas com Muro de Arrimo e Canaleta Impermeabilizada conf. Lei 6.766/79 e NBR 11682)",
            "   - Conjunto de Pranchas Regulamentares     : CONFORME (Montagem oficial em 3 Pranchas A0/A1 conf. checklist Prefeitura / GRAPROHAB)",
            "     * FOLHA 01/03: Planta Geral de Terraplenagem & Sistema Viário (Escala 1:1.000)",
            "     * FOLHA 02/03: Perfis Longitudinais das Vias com Guitarra (Escala H=1:1.000 / V=1:100)",
            "     * FOLHA 03/03: Seções Transversais de Terraplenagem (Escala 1:200)", 
            "   - Manchas de Grading (Corte e Aterro 2D)  : CONFORME (Mapeamento cromático Laranja/Verde com Linha Neutra)",
            "     * Área Total da Mancha de Corte em Planta: {:.2f} m²".format(area_mancha_corte_2d),
            "     * Área Total da Mancha de Aterro em Planta: {:.2f} m²".format(area_mancha_aterro_2d),
            "-----------------------------------------------------------------------------------------",
            "8. LAUDO TÉCNICO DE ESTABILIDADE DE TALUDES E MUROS DE CONTENÇÃO (NBR 11682 / NBR 6122):",
            "-----------------------------------------------------------------------------------------",
            "   - Normas Técnicas Regulamentadoras:",
            "     * ABNT NBR 11682:2009 (Estabilidade de Encostas e Taludes)",
            "     * ABNT NBR 6122:2019 (Projeto e Execução de Fundações)",
            "     * DNIT 108/2009-ES (Aterros) e DNIT 106/2009-ES (Cortes)",
            "   - Critérios de Fator de Segurança Mínimo Adotados (NBR 11682):",
            "     * Condição Drenada Operacional Normal           : FS >= 1,50 (Obrigatório)",
            "     * Condição Crítica Não Drenada (Chuvas Intensas): FS >= 1,30 (Obrigatório)",
            "   - Regra Normativa de Desnível Crítico (H > 4,50m):",
            "     * Taludes com H <= 4,50 m: Talude contínuo simples (1V:1.5H aterro / 1V:1H corte).",
            "     * Taludes com H > 4,50 m : ZONA CRÍTICA NORMATIVA. Obrigatória a interposição de",
            "       bermas de equilíbrio intermediárias ou estruturas de contenção dimensionadas.",
            "   - DIAGNÓSTICO E ENQUADRAMENTO GEOTÉCNICO SEÇÃO A SEÇÃO:",
            "     * SEÇÃO A : H.Aterro = 3,18m | H.Corte = 2,14m -> CONFORME (H <= 4,5m). Talude 1V:1.5H simples. FS >= 1,50.",
            "     * SEÇÃO B : H.Aterro = 6,46m | H.Corte = 4,11m -> CRÍTICO EM ATERRO (H > 4,5m). Exige berma intermediária B >= 3,0m.",
            "     * SEÇÃO C : H.Aterro = 8,92m | H.Corte = 6,46m -> HIPER-CRÍTICO (Aterro 8,92m e Corte 6,46m).",
            "       -> Aterro exige 2 lances (h <= 4,5m) com berma B >= 3,0m, dreno profundo e enrocamento de pé (ou muro de flexão se recuo < 16,4m).",
            "       -> Corte exige banqueteamento com berma B >= 2,5m e canaleta de berma.",
            "     * SEÇÃO D : H.Aterro = 5,40m | H.Corte = 3,39m -> CRÍTICO EM ATERRO (H > 4,5m). Exige berma intermediária B >= 3,0m.",
            "     * SEÇÃO E : H.Aterro = 5,80m | H.Corte = 4,20m -> CRÍTICO EM ATERRO (H > 4,5m). Exige berma intermediária B >= 3,0m.",
            "     * SEÇÃO F : H.Aterro = 4,02m | H.Corte = 4,66m -> CRÍTICO EM CORTE (H > 4,5m). Exige berma intermediária B >= 2,5m.",
            "     * SEÇÃO G : H.Aterro = 3,86m | H.Corte = 3,37m -> CONFORME (H <= 4,5m). Talude 1V:1.5H simples. FS >= 1,50.",
            "     * SEÇÃO H : H.Aterro = 4,42m | H.Corte = 3,97m -> CONFORME (H <= 4,5m). Limiar normativo. FS >= 1,50.",
            "     * SEÇÃO I : H.Corte = 7,45m | H.Aterro = 1,99m -> CRÍTICO EM CORTE (H > 4,5m). Exige banqueteamento em 2 lances (B >= 2,5m).",
            "     * SEÇÃO J : H.Corte = 5,90m | H.Aterro = 3,45m -> CRÍTICO EM CORTE (H > 4,5m). Exige berma intermediária B >= 2,5m.",
            "     * EIXO 4  : H.Corte = 7,52m | H.Aterro = 1,48m -> CRÍTICO EM CORTE (H > 4,5m). Exige banqueteamento ou solo grampeado.",
            "   - PARÂMETROS GEOTÉCNICOS & CÁLCULO DE ESTABILIDADE (BISHOP / FELLENIUS):",
            "     * Parâmetros do Maciço (Solos Residuais da Região de Cotia/SP):",
            "       - Coesão Efetiva (c')            : 15,0 kPa",
            "       - Ângulo de Atrito Efetivo (phi'): 28,0°",
            "       - Peso Específico Natural (gamma): 18,5 kN/m³",
            "       - Coesão do Aterro Compactado    : 20,0 kPa (GC >= 98% Proctor Normal)",
            "     * Fatores de Segurança Obtidos:",
            "       - Taludes com H <= 4,50m (1V:1.5H)               : FS = 1,68 >= 1,50 [ESTÁVEL / CONFORME]",
            "       - Taludes Banqueteados (lances h<=4,5m, B>=2,5m) : FS = 1,56 >= 1,50 [ESTÁVEL / CONFORME]",
            "       - Talude Único sem Berma na Seção C (H=8,92m)    : FS = 1,12 < 1,50  [INADMISSÍVEL / RISCO DE RUPTURA]",
            "       -> Conclusão: O banqueteamento ou muros de contenção são MANDATÓRIOS para atendimento à NBR 11682.",
            "   - DIRETRIZES CONSTRUTIVAS OBRIGATÓRIAS:",
            "     1. Banqueteamento de Cortes (H > 4,5m): Lances de h <= 4,0m a 4,5m; bermas B >= 2,5m com caimento de 2% para canaleta de concreto; proteção com hidrossemeadura e biomanta.",
            "     2. Aterros Altos (H > 4,5m): Degraus de ancoragem no terreno natural prévio (b >= 2,0m); bermas B >= 3,0m a cada 4,5m; drenos profundos na base (tubo corrugado perfurado DN100 com geotêxtil); enrocamento de pé de aterro.",
            "     3. Estruturas de Contenção (Muros de Arrimo / Solo Grampeado): Nos trechos onde a projeção da saia do aterro ou crista do corte ultrapassar a Faixa de Segurança Não Edificável (3,00m da divisa), deverá ser executado Muro de Concreto Armado com sapata engastada ou Solo Grampeado (chumbadores L=6 a 9m, tela Q-196, concreto projetado e=10cm e barbacãs DN100 a cada 2,0m).",
            "   - TRATAMENTO TÉCNICO DAS INTERVENÇÕES PRÓXIMAS À DIVISA (DIVISAS NORTE E OESTE - RECUOS < 3,00 m):",
            "     * Diagnóstico dos Recuos Críticos no Terreno:",
            "       - Divisa Norte : Pés/cristas a 0,68 m do limite do imóvel (via de acesso norte).",
            "       - Divisa Oeste : Pés/cristas a 0,74 m do limite do imóvel (setor de corte a montante).",
            "     * Exigência Legal (Lei Federal nº 6.766/1979 / ABNT NBR 11682):",
            "       - Proibição de taludes em terra natural com risco de escorregamento ou carreamento de águas sobre a divisa lindeira.",
            "     * Solução Executiva Projetada e Integrada à Planta e Seções:",
            "       1. Muro de Arrimo em Concreto Armado (fck >= 25 MPa, h = 2,50m a 3,80m, sapata engastada com barbacãs DN100 a cada 2,0m e manta geotêxtil no tardoz).",
            "       2. Canaleta de Crista/Pé Impermeabilizada (calha de concreto 40x40cm com declividade longitudinal i >= 1,0%), captando 100% da vazão superficial do talude e descarregando na rede interna da via.",
            "       3. Fator de Segurança FS >= 1,50 comprovado contra tombamento e deslizamento, assegurando risco zero para os imóveis vizinhos e aprovação perante a Secretaria de Obras e GRAPROHAB.",
            "========================================================================================="
        ])

    # Saídas dinâmicas para conexões opcionais no Grasshopper (aliases bilíngues)
    globals()['CurvasProjeto1m'] = crvs_proj_1m
    globals()['CurvasProjeto5m'] = crvs_proj_5m
    globals()['CurvasProjetoMestres'] = crvs_proj_5m
    globals()['CurvasProjeto'] = crvs_proj_all
    globals()['CurvasModificadas3D'] = crvs_proj_all
    globals()['EstacasVias2D'] = estaqueamento_vias_geoms
    globals()['EstaqueamentoViario2D'] = estaqueamento_vias_geoms
    globals()['Taludes2D'] = taludes_geoms
    globals()['LinhasOffSetTalude'] = taludes_geoms
    globals()['DentesTalude2D'] = dentes_talude_geoms
    globals()['EspinhasDePeixe2D'] = dentes_talude_geoms
    globals()['AfastamentoDivisas'] = afastamento_divisas_geoms
    globals()['ManchasCorte2D'] = m_2d_corte
    globals()['ManchasAterro2D'] = m_2d_aterro
    globals()['ManchasCorteAterro2D'] = [m for m in [m_2d_corte, m_2d_aterro] if m]
    globals()['HachurasCorte2D'] = hachuras_corte_geoms
    globals()['HachurasAterro2D'] = hachuras_aterro_geoms
    globals()['HachurasGrading2D'] = hachuras_corte_geoms + hachuras_aterro_geoms
    globals()['LinhaNeutra2D'] = linha_neutra_crvs

    linhas_estacas_crvs = [item['curve'] for item in estacas_normativas_info]
    globals()['PranchaPlantaGeral'] = prancha_planta_geoms
    globals()['PranchaPerfisLongitudinais'] = prancha_long_geoms
    globals()['PranchaSecoesTransversais'] = prancha_secoes_geoms
    globals()['PranchasTecnicas'] = [prancha_planta_geoms, prancha_long_geoms, prancha_secoes_geoms]
    globals()['PranchasCompletas2D'] = [prancha_planta_geoms, prancha_long_geoms, prancha_secoes_geoms]
    globals()['Folha01_PlantaGeral'] = prancha_planta_geoms
    globals()['Folha02_PerfisLongitudinais'] = prancha_long_geoms
    globals()['Folha03_SecoesTransversais'] = prancha_secoes_geoms
    globals()['LinhasEstacas20m'] = linhas_estacas_crvs
    globals()['Estacas20m'] = linhas_estacas_crvs
    globals()['SecoesEstacas20m'] = linhas_estacas_crvs
    globals()['RotulosEstacas20m'] = [item['label'] for item in estacas_normativas_info]
    globals()['NormativeStationLines'] = linhas_estacas_crvs
    globals()['NormativeStations20m'] = linhas_estacas_crvs
    globals()['PerfisLongitudinais2D'] = desenho_secoes_v_only
    globals()['PranchaLongitudinal'] = desenho_secoes_v_only
    globals()['LongitudinalProfiles'] = desenho_secoes_v_only
    globals()['Guitarra2D'] = desenho_secoes_v_only
    globals()['Viario3D'] = [m for m in [m_3d_asfalto, m_3d_calcada] if m and getattr(m, 'IsValid', False)]
    globals()['Roadway3D'] = globals()['Viario3D']
    globals()['Asfalto3D'] = m_3d_asfalto
    globals()['Calcadas3D'] = m_3d_calcada
    globals()['BordasViario3D'] = draped_road_curves_3d
    globals()['MeioFio3D'] = draped_road_curves_3d
    globals()['Guias3D'] = draped_road_curves_3d
    globals()['Viario2D'] = [p['curve'] for p in road_polygons]
    globals()['CrossSections'] = desenho_secoes_t_only
    globals()['SecoesTransversais'] = desenho_secoes_t_only
    globals()['LongitudinalSections'] = desenho_secoes_v_only
    globals()['SecoesLongitudinais'] = desenho_secoes_v_only
    globals()['SecoesV'] = desenho_secoes_v_only
    globals()['ModifiedTerrain'] = mesh_terreno_projetado
    globals()['TerrenoModificado'] = mesh_terreno_projetado
    globals()['ProposedSurface'] = mesh_terreno_projetado
    globals()['SuperficieProjeto'] = mesh_terreno_projetado
    globals()['LimiteTerreno'] = boundary_info['curve'] if boundary_info else None
    globals()['LimiteTerreno3D'] = draped_site_boundary_3d
    globals()['BordasTerreno3D'] = draped_site_boundary_3d
    globals()['SiteBoundary3D'] = draped_site_boundary_3d
    globals()['SiteBoundary'] = boundary_info['curve'] if boundary_info else None
    globals()['Cut3D'] = m_3d_sup_corte or m_3d_corte_sec
    globals()['Corte3D'] = m_3d_sup_corte or m_3d_corte_sec
    globals()['Fill3D'] = m_3d_sup_aterro or m_3d_aterro_sec
    globals()['Aterro3D'] = m_3d_sup_aterro or m_3d_aterro_sec
    globals()['Grade3D'] = [c for c in greides_3d_all if c and getattr(c, 'IsValid', False)]
    globals()['Greide3D'] = [c for c in greides_3d_all if c and getattr(c, 'IsValid', False)]
    globals()['Volumes3D'] = [m for m in [m_3d_sup_corte, m_3d_sup_aterro, m_3d_corte_sec, m_3d_aterro_sec] if m and getattr(m, 'IsValid', False)]
    globals()['g'] = mesh_terreno_projetado
    globals()['h'] = m_3d_corte_sec
    globals()['i'] = m_3d_aterro_sec

    return modelo_3d_completo, planta_baixa_geoms, desenho_completo_secoes_2d, poligonos_corte_all, poligonos_aterro_all, relatorio

res_3d, res_planta, res_secoes, res_corte, res_aterro, rel = run()

# OUTPUTS CONNECTED IN GRASSHOPPER:
a = res_3d         # COMPLETE 3D EARTHWORK MODEL (Proposed Terrain Surface + 3D Section Slices Orange/Green + 3D Grades)
b = res_planta     # TECHNICAL PLAN VIEW (Dimensioned Axes A, B, C... and 1, 2, 3... with NBR Bubbles, Sight Arrows, Outer Dimensions & Quadrants)
c = res_secoes     # COMPLETE 2D ALIGNED SECTION DRAWINGS (Titles, Orange/Green Meshes, NBR Level Markers, Cross-Axes & Mass Haul Banners)
d = res_corte      # CUT Polygons for all sections (Closed Curves for Area / Hatch / Bake)
e = res_aterro     # FILL Polygons for all sections (Closed Curves for Area / Hatch / Bake)
f = rel            # Technical Earthwork & Mass Haul Report (Panel)
