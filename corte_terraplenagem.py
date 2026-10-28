# -*- coding: utf-8 -*-
"""
===============================================================================
CÁLCULO DE TERRAPLENAGEM E VOLUMES MULTI-EIXOS (NBR 6492 & AGPTEA)
===============================================================================
Algoritmo paramétrico para Grasshopper (Rhinoceros 8 / GhPython).
Unifica múltiplos eixos de corte transversais (A, B, C...) e longitudinais (1, 2, 3...),
calcula automaticamente as distâncias entre eixos consecutivos, calcula as metragens
cúbicas de corte e aterro pelo Método das Seções Transversais da AGPTEA, alinha todas
as seções com espaçamento uniforme e realiza a COMPENSAÇÃO PROGRESSIVA DE MASSAS
(rastreando de onde sai a terra excedente para abastecer o aterro da próxima seção).

Metodologia baseada em:
- "TOPOGRAFIA: CÁLCULO DE VOLUMES – NOTAS DE AULA"
  Prof. Luís Augusto Koenig Veiga (UFPR / AGPTEA)
  Cap. 3.2 (Método das Seções Transversais) e Cap. 3.3 (Balanço de Massas)
- NBR 6492: Representação de Projetos de Arquitetura (Simbologia de Cortes e Níveis)

ENTRADAS (INPUTS):
  Terreno          [List, Curve/Mesh] : Curvas de nível 3D ou Malha topográfica.
  LinhasCorte      [List, Curve]      : Eixos de corte transversais (Seções A, B, C, D...).
  EixosVerticais   [List, Curve]      : Eixos longitudinais/verticais (1, 2, 3...) [Opcional].
  CurvaProjeto     [Item/List, Curve] : Curva(s) de greide ou projeto / LinhaDelimitadora [Opcional].
  LinhaDelimitadora[Item/List, Curve] : Alias direto para CurvaProjeto / Greide delimitador [Opcional].
  InclinacaoMaxima [Item, float]      : Inclinação máxima permitida para a linha delimitadora/greide [Opcional, Padrão = 15.0 (%)].
  NivelProjeto     [Item/List/Tree]   : Cota(s) de platô individual por trecho/quadrante (float único, lista [102.0, 105.0] ou DataTree por seção) [Opcional].
  Ponto            [Item, Point3d]    : Ponto base de inserção das seções 2D no Top View.
  Espacamento      [Item, float]      : Distância vertical uniforme entre as seções 2D.
  Largura          [Item, float]      : Faixa de influência para seção unitária (padrão: 1.0 m).
  Empolamento      [Item, float]      : Fator de empolamento do solo para transporte (padrão: 1.20).
  Seletor          [Item, int]        : Modo de exibição:
                                        0 = Completo (TN + Greide + Áreas + Todas as Cotas)
                                        1 = Terraplenagem / Projetado [Padrão]
                                        2 = Apenas Terreno Natural
  Escala           [Item, float]      : Fator de escala dos símbolos, textos e balões NBR (padrão: 1.0).

SAÍDAS (OUTPUTS):
  a : Linhas 3D dos cortes sobre o terreno natural (Coordenadas de Mundo / UTM).
  b : PLANTA BAIXA TÉCNICA (Eixos A, B, C... e 1, 2, 3... com balões NBR, setas de corte, cotas de distância e quadrantes).
  c : DESENHO COMPLETO DAS SEÇÕES 2D ALINHADAS (com títulos, malhas coloridas Laranja/Verde, cotas NBR e banners de transferência de terra).
  d : Polígonos de CORTE de todas as seções (Closed Curves para Área / Hatch / Bake).
  e : Polígonos de ATERRO de todas as seções (Closed Curves para Área / Hatch / Bake).
  f : Memorial Técnico Completo de Terraplenagem e Balanço Progressivo de Massas (Panel).
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
        # Desempacota coleções iteráveis (List, Array, Tuple, Set), excluindo strings e geometrias Rhino
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
    """Gera identificadores de seção alfabéticos: A, B, C... Z, AA, AB..."""
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
    """Cria uma curva fechada válida de Polyline, verificando número mínimo de vértices e validade."""
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
    """Cria uma malha RhinoCommon 100% válida, sanitizada e livre de degenerações.
    Elimina vértices duplicados, descarta faces de área nula e decompõe
    quadriláteros em triângulos limpos para garantir estabilidade absoluta no Rhino 8 / .NET Core.
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
# TABELAS VETORIAIS DE ALTA DEFINIÇÃO PARA TEXTO (STROKE VECTOR FONT ENGINE)
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
    if not text_str: return curves

    char_widths = []
    char_data = []

    for ch in text_str:
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
    """Gera curvas vetoriais 2D limpas e leves para textos técnicos (Stroke Vector Font Engine).
    Execução 100% autônoma em Python, imune a falhas de Viewport nulo ou DimStyle no Rhino 8 / .NET Core.
    """
    if not text_str: return []
    return generate_stroke_text(text_str, pt, height, justification, plane)

make_text_entity = make_text_geometry

def get_stroke_text_width(text_str, height):
    """Calcula a largura horizontal exata que o texto vetorial ocupará."""
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
    """Gera uma malha 2D retangular que serve como fundo/máscara (wipeout) sob os textos."""
    if p0 is None or p1 is None or p2 is None or p3 is None:
        return None
    if color is None:
        color = System.Drawing.Color.FromArgb(252, 252, 252)
    m = rg.Mesh()
    m.Vertices.Add(p0)
    m.Vertices.Add(p1)
    m.Vertices.Add(p2)
    m.Vertices.Add(p3)
    m.Faces.AddFace(0, 1, 2)
    m.Faces.AddFace(0, 2, 3)
    m.VertexColors.Add(color)
    m.VertexColors.Add(color)
    m.VertexColors.Add(color)
    m.VertexColors.Add(color)
    m.Compact()
    try:
        m.Normals.ComputeNormals()
    except:
        pass
    return m if m.IsValid else None

def make_callout_card(center_x, center_y, title_text, sub_text, s=1.0, is_corte=True):
    """Cria uma caixa retangular técnica com textos perfeitamente enquadrados e margens amplas."""
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
    """Gera o símbolo de cota de nível padrão NBR 6492 com texto vetorial nítido e estante dinâmica."""
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
# FUNÇÕES DE APOIO MULTI-EIXOS: PLANTA BAIXA, BALÕES NBR E DISTÂNCIAS
# =============================================================================

def draw_plan_axis_bubble(pt, dir_vec, label_str, s=1.0):
    """Gera o balão circular NBR 6492 nas extremidades das linhas de corte em planta com seta de visada."""
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
    Desenha uma cota linear técnica com linhas de chamada, ticks NBR a 45° e texto
    alinhado perfeitamente paralelo à linha de cota fora do desenho.
    """
    geoms = []
    p1_2d = rg.Point3d(p1.X, p1.Y, 0.0)
    p2_2d = rg.Point3d(p2.X, p2.Y, 0.0)
    vec = p2_2d - p1_2d
    d_len = vec.Length
    if d_len < 1e-3: return geoms

    u_dim = rg.Vector3d(vec)
    u_dim.Unitize()

    # Se offset for fornecido, desloca a linha de cota para fora do desenho
    if offset_dir is not None and abs(offset_dist) > 1e-4:
        off_v = rg.Vector3d(offset_dir.X, offset_dir.Y, 0.0)
        off_v.Unitize()
        p1_cota = p1_2d + off_v * offset_dist
        p2_cota = p2_2d + off_v * offset_dist

        # Linhas de chamada (extension lines)
        l_ext1 = rg.LineCurve(p1_2d + off_v * (0.8 * s), p1_cota + off_v * (1.2 * s))
        l_ext2 = rg.LineCurve(p2_2d + off_v * (0.8 * s), p2_cota + off_v * (1.2 * s))
        geoms.extend([l_ext1, l_ext2])
    else:
        p1_cota = p1_2d
        p2_cota = p2_2d
        off_v = rg.Vector3d(-u_dim.Y, u_dim.X, 0.0)

    # Linha principal de cota
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

    # Ponto do texto levemente afastado da linha de cota (no lado de fora)
    p_mid = (p1_cota + p2_cota) / 2.0 + off_v * (0.85 * s)
    plane_txt = rg.Plane(p_mid, u_txt, v_txt)
    txt_str = "D = {:.2f}m".format(dist_val).replace('.', ',')
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

def draw_section_vertical_axis_marker(base_x, base_y, d_ax, sec_h, sec_datum_z, z_terrain, z_proj, lbl_v, s=1.0):
    """
    Desenha no perfil 2D da seção a linha vertical do eixo, o balão circular NBR no topo
    com cruz central e o nó quadrado técnico na interseção com o relevo.
    """
    geoms = []
    x_ax = base_x + d_ax
    y_datum = base_y
    y_top_line = base_y + sec_h + 6.0 * s
    y_bubble = base_y + sec_h + 8.2 * s

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

    # 3. Marcador / Nó quadrado técnico na interseção com o relevo (conforme croqui)
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

    # 4. Nó circular na interseção com o greide se houver desnível com o terreno
    if abs(z_proj - z_terrain) > 0.05:
        y_greide = base_y + (z_proj - sec_datum_z)
        p_gr_node = rg.Point3d(x_ax, y_greide, 0.0)
        geoms.append(rg.Circle(p_gr_node, 0.35 * s).ToNurbsCurve())

    return geoms

def draw_section_internal_transfer_arrow(p_start, p_end, vol_or_area_str="", s=1.0):
    """
    Desenha no perfil 2D a seta vermelha indicativa de compensação interna de massa
    (terra saindo do trecho de corte para o trecho de aterro adjacente).
    """
    geoms = []
    # 1. Ponto / Círculo de origem preenchido no corte (como desenhado no croqui: nó vermelho circular)
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
    u_arrow = rg.Vector3d(vec)
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
        p_txt = (p_start + p_end) / 2.0 + v_arrow * (1.1 * s)
        txt_crvs = make_text_geometry(vol_or_area_str, p_txt, 0.75 * s, rg.TextJustification.BottomCenter, s)
        if txt_crvs: geoms.extend(txt_crvs)

    return geoms

def parse_nivel_projeto(raw_nivel_proj, idx_s, num_secoes, num_trechos):
    """
    Interpreta NivelProjeto com suporte a cota única, lista por trecho ou lista por seção.
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
        t_mid_a = ca_xy.Domain.Min + 0.5 * (ca_xy.Domain.Max - ca_xy.Domain.Min)
        p_mid_a = ca_xy.PointAt(t_mid_a)
        rc, t_b = cb_xy.ClosestPoint(p_mid_a)
        d1 = p_mid_a.DistanceTo(cb_xy.PointAt(t_b)) if rc else None

        t_mid_b = cb_xy.Domain.Min + 0.5 * (cb_xy.Domain.Max - cb_xy.Domain.Min)
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
    Desenha o banner técnico entre seções com o volume do trecho, saldo e seta indicativa
    de transferência de massa de onde sai para onde vai a terra na próxima seção.
    """
    geoms = []
    txt_h1 = 0.95 * s
    txt_h2 = 0.85 * s
    pad_x  = 4.00 * s   # Margem lateral ampla para garantir que a linha de texto nunca estoure a caixa
    pad_y  = 1.30 * s   # Margem vertical
    gap_y  = 1.30 * s   # Folga entre os textos e a divisória central

    t1_str = "TRECHO {} - {} (D = {:.2f}m) | V.Corte: {:.1f}m³ | V.Aterro: {:.1f}m³ | Saldo: {:+.1f}m³".format(
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

    # Seta vertical indicando sentido de transporte longitudinal para a próxima seção
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
    """Calcula a extensão mínima e máxima das curvas de nível/terreno projetadas no vetor transversal u_corte."""
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
# AMETRADOR UNIVERSAL DE GREIDE E MAPEAMENTO DE CURVAS DE PROJETO
# =============================================================================

def make_project_grade_sampler(curva_greide_in, base_x, base_y, sec_datum_z, z_min, z_max, total_ext, curve_base_y=None, p_start_3d=None, u_sec_3d=None, d_terrain_start=0.0, max_slope=0.15):
    """
    Amostrador universal e robusto de greide de projeto com restrição de inclinação máxima.
    Detecta automaticamente se a curva foi desenhada:
    1. Sobre o desenho 2D da seção (Viewport Top, Z ~ 0, Y no espaço do desenho)
    2. Com cotas Z absolutas no espaço 3D (Z real do modelo)
    3. Com cotas Y absolutas no espaço 2D (Y ~ Z real)
    4. Com vetorização invertida (Direita para Esquerda) ou parcial.
    Garante mapeamento exato com o relevo natural e aplica a REGRA NORMATIVA DE INCLINAÇÃO MÁXIMA:
    Nenhum trecho da linha delimitadora pode exceder max_slope (padrão 15% = 0.15).
    Se a inclinação exceder o limite, ela é automaticamente limitada a 15%, preservando a cota de referência.
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

    # 1. Caso Curva 3D no espaço de modelo (Z representa a cota real)
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
        # Detecta se os pontos usam a coordenada X do desenho 2D ou se usam X relativo [0, total_ext]
        use_drawing_x = False
        if abs(min_x - base_x) < total_ext * 0.8 or            abs(max_x - (base_x + total_ext)) < total_ext * 0.8 or            (min_x >= base_x - 10.0 and max_x <= base_x + total_ext + 10.0):
            use_drawing_x = True

        sec_h = max(z_max - sec_datum_z, 1.0)
        ref_by = curve_base_y if curve_base_y is not None else base_y

        # Detecção de posição em relação ao desenho 2D da seção
        z_terrain_med = (z_min + z_max) / 2.0
        y_terrain_section_2d = ref_by + (z_terrain_med - sec_datum_z)
        dist_to_section = abs(avg_y - y_terrain_section_2d)

        # Se o usuário desenhou a curva diretamente sobre o perfil 2D da seção:
        # dist_to_section é pequena (a menos de 2x sec_h ou 15m do terreno)
        is_drawn_on_section = (dist_to_section <= max(sec_h * 2.0, 15.0))

        # Se não foi desenhada sobre a seção, checa se é cota absoluta Y (ex: Y ~ 900)
        is_abs_y = (not is_drawn_on_section) and (z_min - 50.0 <= avg_y <= z_max + 100.0)

        # Se estiver no vão livre (nem sobre a seção nem em cota absoluta)
        is_floating_in_void = (not is_drawn_on_section) and (not is_abs_y)

        for p in pts:
            d_p = (p.X - base_x) if use_drawing_x else p.X
            if is_drawn_on_section:
                # Caso prioritário: desenhada sobre a seção 2D com precisão milimétrica
                z_p = sec_datum_z + (p.Y - ref_by)
            elif is_abs_y:
                # Coordenada Y representa a cota absoluta real
                z_p = p.Y
            elif is_floating_in_void:
                # Ancoragem inteligente na cota média do relevo, preservando inclinação e forma da linha
                delta_shape = p.Y - avg_y
                z_p = z_terrain_med + delta_shape
            else:
                z_p = sec_datum_z + (p.Y - ref_by)
            d_z_pairs.append((d_p, z_p))

    d_z_pairs.sort(key=lambda item: item[0])

    # Remove pontos com distância horizontal insignificante para evitar divisão por zero
    clean_d_z = [d_z_pairs[0]]
    for item in d_z_pairs[1:]:
        if item[0] - clean_d_z[-1][0] > 1e-4:
            clean_d_z.append(item)

    # Aplicação estrita da Regra de Inclinação Máxima de 15% (max_slope)
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
    Cria um amostrador contínuo de greide para seções longitudinais (1, 2, 3...)
    a partir das cotas de projeto dos cruzamentos com as seções transversais (A, B, C...).
    Garante perfeita sincronia física e geométrica entre os cortes transversais e longitudinais.
    Aplica a regra normativa de inclinação máxima de 15%.
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

    # Aplica verificação de inclinação máxima entre os pontos de cruzamento
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

def match_project_curves_to_sections(curves_raw, sec_targets, espacamento_y=None):
    """
    Mapeia curvas de projeto / linhas delimitadoras fornecidas para suas respectivas seções com base
    na proximidade 2D (coordenadas X e Y no desenho) ou na ordem de entrada.
    Suporta tanto seções transversais (A, B, C...) quanto longitudinais (1, 2, 3...),
    garantindo que uma linha desenhada sobre a SEÇÃO 1 - 1 seja mapeada para a SEÇÃO 1 - 1,
    e uma linha desenhada sobre a SEÇÃO A - A seja mapeada para a SEÇÃO A - A.
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
        # Testa se a curva está desenhada sobre alguma seção específica em 2D
        try:
            bb = c.GetBoundingBox(True) if hasattr(c, 'GetBoundingBox') else c.GetBoundingBox()
            cx = (bb.Min.X + bb.Max.X) / 2.0 if bb.IsValid else c.PointAtNormalizedLength(0.5).X
            cy = (bb.Min.Y + bb.Max.Y) / 2.0 if bb.IsValid else c.PointAtNormalizedLength(0.5).Y
        except:
            pm = c.PointAtNormalizedLength(0.5)
            cx, cy = pm.X, pm.Y

        # Procura a seção mais próxima do ponto
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

        # Se a curva está nitidamente sobre uma seção (ex: a menos de 50m)
        if best_d < 60.0 and best_t is not None:
            res_dict = {t['key']: (None, t['base_y']) for t in targets_list}
            res_dict[best_t['key']] = (c, best_t['base_y'])
            if is_legacy_list:
                return [res_dict[t['key']] for t in targets_list]
            return res_dict
        else:
            # Aplica como template para todas as seções (preservando suas bases Y)
            if is_legacy_list:
                return [(c, t['base_y']) for t in targets_list]
            return {t['key']: (c, t['base_y']) for t in targets_list}

    # Múltiplas curvas: associa cada curva à sua respectiva seção transversal ou longitudinal
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

        if best_c is not None and best_d < 120.0:
            matched_dict[t['key']] = (best_c, by)
            used_curves.add(best_c_idx)
        else:
            matched_dict[t['key']] = (None, by)

    if is_legacy_list:
        return [matched_dict[t['key']] for t in targets_list]
    return matched_dict

# =============================================================================
# AVALIAÇÃO ANALÍTICA DE UMA SEÇÃO TRANSVERSAL INDIVIDUAL
# =============================================================================

def extract_section_terrain(crv_corte, geoms_terreno, tol, intersec_axes=None, s=1.0):
    """Extrai com precisão milimétrica a interseção do terreno natural com a linha de corte 3D."""
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

        # 1. Curvas de Nível (Curves)
        if isinstance(geom, rg.Curve):
            # A. Interseção com o plano vertical do corte (3D)
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

            # B. Interseção das curvas projetadas no plano XY (2D)
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

        # 2. Malha de Terreno (Mesh)
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

    # DELIMITAÇÃO ESTRITA ÀS CURVAS DE NÍVEL (Fim das Curvas de Nível é o Limite Real do Perfil)
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

    # Identificação dos divisores internos de trecho (eixos verticais dentro do corte)
    d_divs = []
    eixos_secao = []
    if axes_filtered:
        for item in axes_filtered:
            d_ax = item[0]
            if 0.5 * s <= d_ax <= total_ext - 0.5 * s:
                eixos_secao.append(item)
                if 2.0 * s <= d_ax <= total_ext - 2.0 * s:
                    d_divs.append(item)

    # Delimitação dos trechos/quadrantes ao longo da extensão da seção
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

def evaluate_section_grade_and_volumes(t_info, curva_greide_in, raw_nivel_proj, label_sec="A", s=1.0, base_x=0.0, base_y=0.0, curve_base_y=None, max_slope=0.15):
    """Calcula greide, classificação de corte/aterro, áreas e volumes de uma seção a partir de t_info."""
    clean_pts = t_info['clean_pts']
    total_ext = t_info['total_ext']
    crv_3d = t_info['crv_3d']
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

    def get_proj_z(d_val):
        # 1. Se CurvaProjeto for fornecida e sampler estiver ativo
        if sampler is not None:
            try:
                z_res = sampler(d_val)
                if z_res is not None:
                    return z_res
            except:
                pass

        # 2. Localiza a qual trecho d_val pertence
        k_found = 0
        for i_div, item in enumerate(d_divs):
            if d_val >= item[0]:
                k_found = i_div + 1
            else:
                break

        # 3. Se raw_nivel_proj for fornecido (valor único ou lista por trecho)
        if raw_nivel_proj is not None:
            if isinstance(raw_nivel_proj, (list, tuple)) and len(raw_nivel_proj) > 0:
                try: return float(raw_nivel_proj[min(k_found, len(raw_nivel_proj) - 1)])
                except: pass
            else:
                try: return float(raw_nivel_proj)
                except: pass

        # 4. Fallback: cota média calculada para aquele trecho específico
        if trecho_avg_zs and k_found < len(trecho_avg_zs):
            return trecho_avg_zs[k_found]
        if clean_pts:
            return sum(p[1].Z for p in clean_pts) / float(len(clean_pts))
        return (z_min + z_max) / 2.0

    # Amostragem com discretização fina
    num_passos = max(int(total_ext / 0.25), 80)
    dx = total_ext / float(num_passos)
    estacas_d = [i * dx for i in range(num_passos + 1)]
    if estacas_d[-1] < total_ext: estacas_d.append(total_ext)

    # Adiciona divisores com epsilon para degrau vertical perfeito no greide
    for item in d_divs:
        d_ax = item[0]
        estacas_d.append(max(0.0, d_ax - 1e-4))
        estacas_d.append(min(total_ext, d_ax + 1e-4))

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
        tipo = "CORTE" if z_tn_m >= z_pr_m else "ATERRO"

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

    # Dados e estatísticas por trecho/quadrante individual
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

    # Rastreamento de compensação interna entre trechos adjacentes da seção
    internal_transfers = []
    for k in range(len(trechos_data) - 1):
        tr1 = trechos_data[k]
        tr2 = trechos_data[k+1]
        d_boundary = tr1['d_end']

        # Corte no Trecho 1 suprindo Aterro no Trecho 2
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
        'clean_pts': clean_pts,
        'total_ext': total_ext,
        'crv_3d': crv_3d,
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
        'effective_slope': getattr(sampler, 'effective_slope', 0.0) if sampler else 0.0
    }

def evaluate_section_data(crv_corte, geoms_terreno, curva_greide_in, raw_nivel_proj, tol, intersec_axes=None, label_sec="A", s=1.0, base_x=0.0, base_y=0.0, curve_base_y=None, max_slope=0.15):
    """Calcula a geometria 3D, perfil de terreno natural e greide de terraplenagem para uma seção."""
    t_info = extract_section_terrain(crv_corte, geoms_terreno, tol, intersec_axes, s)
    return evaluate_section_grade_and_volumes(t_info, curva_greide_in, raw_nivel_proj, label_sec, s, base_x, base_y, curve_base_y, max_slope=max_slope)

# =============================================================================
# COORDENADOR PRINCIPAL: MULTI-EIXOS, ALINHAMENTO, CUBAGEM E BALANÇO DE MASSAS
# =============================================================================

def render_single_section_2d_and_3d(s_data, lbl, base_x, base_y, s, modo_cotas, cor_corte, cor_aterro, crv_aln_3d=None, is_longitudinal=False, axis_title_prefix="SEÇÃO "):
    """
    Renderiza todos os elementos gráficos 2D e geometrias 3D de uma seção individual
    (seja transversal A, B, C... ou longitudinal 1, 2, 3...).
    Retorna dicionário completo com geometrias 2D, polígonos de corte/aterro e geometrias 3D.
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

    # 3D: Posição espacial real da seção no modelo 3D (UTM / World Coordinates)
    if crv_aln_3d is not None:
        p_s3d = crv_aln_3d.PointAtStart
        p_e3d = crv_aln_3d.PointAtEnd
        dx_3d = p_e3d.X - p_s3d.X
        dy_3d = p_e3d.Y - p_s3d.Y
        L_3d = math.hypot(dx_3d, dy_3d)
        ux_3d = dx_3d / max(L_3d, 1e-4)
        uy_3d = dy_3d / max(L_3d, 1e-4)

        # Curva 3D do Greide de Projeto
        pts_gr_3d = []
        for d in s_data['estacas_finais']:
            pts_gr_3d.append(rg.Point3d(p_s3d.X + ux_3d * d, p_s3d.Y + uy_3d * d, get_proj_z(d)))
        if len(pts_gr_3d) >= 2:
            crv_temp = rg.PolylineCurve(pts_gr_3d)
            if crv_temp and crv_temp.IsValid:
                crv_gr_3d = crv_temp

        # Fatias verticais 3D em cada seção
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

    # Datum Local da Seção
    sec_datum_z = math.floor(s_data['z_min'] - 2.0)
    sec_h = s_data['z_max'] - sec_datum_z

    # Título da Seção
    p_tit = rg.Point3d(base_x, base_y + sec_h + 8.5 * s, 0.0)
    tit_crvs = make_text_geometry("{}{} - {}".format(axis_title_prefix, lbl, lbl), p_tit, 1.50 * s, rg.TextJustification.BottomLeft, s)
    geoms_2d.extend(tit_crvs)

    sub_str = "Extensão: {:.2f}m | Cota Média: +{:.2f}m".format(total_ext, sum(p[1].Z for p in clean_pts)/len(clean_pts)).replace('.', ',')
    p_sub = rg.Point3d(base_x, base_y + sec_h + 6.8 * s, 0.0)
    sub_crvs = make_text_geometry(sub_str, p_sub, 0.85 * s, rg.TextJustification.BottomLeft, s)
    geoms_2d.extend(sub_crvs)

    # Linha e Rótulo de DATUM
    p_d_ini = rg.Point3d(base_x, base_y, 0.0)
    p_d_fim = rg.Point3d(base_x + total_ext, base_y, 0.0)
    geoms_2d.append(rg.LineCurve(p_d_ini, p_d_fim))

    lbl_datum = "DATUM +{:.2f}".format(sec_datum_z).replace('.', ',')
    p_datum_txt = rg.Point3d(base_x - 1.2 * s, base_y, 0.0)
    datum_crvs = make_text_geometry(lbl_datum, p_datum_txt, 0.80 * s, rg.TextJustification.MiddleRight, s)
    geoms_2d.extend(datum_crvs)

    # Perfil Natural 2D
    pts_tn_2d = [rg.Point3d(base_x + d, base_y + (pt.Z - sec_datum_z), 0.0) for d, pt in clean_pts]
    crv_tn_2d = rg.PolylineCurve(pts_tn_2d) if len(pts_tn_2d) >= 2 else None
    if crv_tn_2d and crv_tn_2d.IsValid: geoms_2d.append(crv_tn_2d)

    # Polígono de fechamento de solo sob TN
    p_solo = [p_d_ini, p_d_fim] + list(reversed(pts_tn_2d)) + [p_d_ini]
    crv_solo = make_safe_closed_polyline(p_solo)
    if crv_solo: geoms_2d.append(crv_solo)

    # Greide 2D
    pts_gr_2d = [rg.Point3d(base_x + d, base_y + (get_proj_z(d) - sec_datum_z), 0.0) for d in s_data['estacas_finais']]
    crv_gr_2d = rg.PolylineCurve(pts_gr_2d) if len(pts_gr_2d) >= 2 else None
    if crv_gr_2d and crv_gr_2d.IsValid: geoms_2d.append(crv_gr_2d)

    # Rótulo de inclinação do greide (com regra de 15%)
    if s_data.get('sampler') is not None or s_data.get('was_clamped') is not None:
        eff_i = s_data.get('effective_slope', 0.0)
        was_c = s_data.get('was_clamped', False)
        d_gr_mid = total_ext * 0.5
        z_gr_mid = get_proj_z(d_gr_mid)
        p_gr_lbl = rg.Point3d(base_x + d_gr_mid, base_y + (z_gr_mid - sec_datum_z) + 1.8 * s, 0.0)

        if was_c:
            lbl_gr_str = "GREIDE: i = {:+.1f}% [LIMITADO A 15,0% MÁX]".format(eff_i).replace('.', ',')
        else:
            lbl_gr_str = "GREIDE: i = {:+.1f}% (REGRA <= 15% OK)".format(eff_i).replace('.', ',')

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

    # Linhas e Balões dos Eixos que Cruzam a Seção
    for (d_ax, idx_cross, lbl_cross) in s_data.get('eixos_secao', []):
        z_tn_ax = interpolate_terrain_z(d_ax, clean_pts)
        z_pr_ax = get_proj_z(d_ax)
        ax_geoms = draw_section_vertical_axis_marker(base_x, base_y, d_ax, sec_h, sec_datum_z, z_tn_ax, z_pr_ax, lbl_cross, s)
        geoms_2d.extend(ax_geoms)

    # Seta Vermelha de Compensação Interna
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

        # Caixas Técnicas de Área por Trecho/Quadrante
        trechos = s_data.get('trechos_data', [])
        if trechos and len(trechos) > 1:
            for tr in trechos:
                d_mid_tr = (tr['d_start'] + tr['d_end']) / 2.0
                x_box_tr = base_x + d_mid_tr
                lbl_q = tr['label_q']

                p_q_badge = rg.Point3d(x_box_tr, base_y + sec_h + 3.0 * s, 0.0)
                q_badge = draw_quadrant_badge(p_q_badge, lbl_q, s * 0.9)
                geoms_2d.extend(q_badge)

                if tr['area_corte'] > 0.01:
                    z_sub_corte = [interpolate_terrain_z(d, clean_pts) for d, _ in clean_pts if tr['d_start'] <= d <= tr['d_end']]
                    z_c_top = max(z_sub_corte) if z_sub_corte else (sec_datum_z + 2.0)
                    txt_v1 = "CORTE {}: {:.2f} m²".format(lbl_q, tr['area_corte']).replace('.', ',')
                    txt_v2 = "H.Máx: {:.2f}m | Platô: +{:.2f}m".format(tr['max_h_corte'], tr['z_proj']).replace('.', ',')
                    hc_est = 5.5 * s
                    y_c_box = base_y + (z_c_top - sec_datum_z) + 6.0 * s + (hc_est / 2.0)
                    c_card, (wc, hc) = make_callout_card(x_box_tr, y_c_box, txt_v1, txt_v2, s, True)
                    geoms_2d.extend(c_card)
                    p_c_box_bot = rg.Point3d(x_box_tr, y_c_box - hc / 2.0, 0.0)
                    p_crest = rg.Point3d(x_box_tr, base_y + (interpolate_terrain_z(d_mid_tr, clean_pts) - sec_datum_z), 0.0)
                    geoms_2d.append(rg.LineCurve(p_c_box_bot, p_crest))
                    geoms_2d.append(rg.Circle(p_crest, 0.30 * s).ToNurbsCurve())

                if tr['area_aterro'] > 0.01:
                    txt_a1 = "ATERRO {}: {:.2f} m²".format(lbl_q, tr['area_aterro']).replace('.', ',')
                    txt_a2 = "H.Máx: {:.2f}m | Platô: +{:.2f}m".format(tr['max_h_aterro'], tr['z_proj']).replace('.', ',')
                    ha_est = 5.5 * s
                    y_a_box = base_y - 5.5 * s - (ha_est / 2.0)
                    a_card, (wa, ha) = make_callout_card(x_box_tr, y_a_box, txt_a1, txt_a2, s, False)
                    geoms_2d.extend(a_card)
                    p_a_box_top = rg.Point3d(x_box_tr, y_a_box + ha / 2.0, 0.0)
                    p_datum_conn = rg.Point3d(x_box_tr, base_y, 0.0)
                    geoms_2d.append(rg.LineCurve(p_a_box_top, p_datum_conn))
                    geoms_2d.append(rg.Circle(p_datum_conn, 0.30 * s).ToNurbsCurve())
        else:
            d_c_all = [d for r_type, d_list in s_data['regioes'] if r_type == "CORTE" for d in d_list]
            if s_data['area_total_corte'] > 0.01 and d_c_all:
                d_c_mid = (min(d_c_all) + max(d_c_all)) / 2.0
                z_c_top = max(interpolate_terrain_z(d, clean_pts) for d in d_c_all)
                txt_v1 = "CORTE {}: {:.2f} m²".format(lbl, s_data['area_total_corte']).replace('.', ',')
                txt_v2 = "Altura Máx: {:.2f}m".format(s_data['max_h_corte']).replace('.', ',')
                hc_est = 5.5 * s
                y_c_box = base_y + (z_c_top - sec_datum_z) + 6.0 * s + (hc_est / 2.0)
                x_c_box = base_x + d_c_mid
                c_card, (wc, hc) = make_callout_card(x_c_box, y_c_box, txt_v1, txt_v2, s, True)
                geoms_2d.extend(c_card)
                p_c_box_bot = rg.Point3d(x_c_box, y_c_box - hc / 2.0, 0.0)
                p_crest = rg.Point3d(x_c_box, base_y + (interpolate_terrain_z(d_c_mid, clean_pts) - sec_datum_z), 0.0)
                geoms_2d.append(rg.LineCurve(p_c_box_bot, p_crest))
                geoms_2d.append(rg.Circle(p_crest, 0.30 * s).ToNurbsCurve())

            d_a_all = [d for r_type, d_list in s_data['regioes'] if r_type == "ATERRO" for d in d_list]
            if s_data['area_total_aterro'] > 0.01 and d_a_all:
                d_a_mid = (min(d_a_all) + max(d_a_all)) / 2.0
                txt_a1 = "ATERRO {}: {:.2f} m²".format(lbl, s_data['area_total_aterro']).replace('.', ',')
                txt_a2 = "Altura Máx: {:.2f}m".format(s_data['max_h_aterro']).replace('.', ',')
                ha_est = 5.5 * s
                y_a_box = base_y - 5.5 * s - (ha_est / 2.0)
                x_a_box = base_x + d_a_mid
                a_card, (wa, ha) = make_callout_card(x_a_box, y_a_box, txt_a1, txt_a2, s, False)
                geoms_2d.extend(a_card)
                p_a_box_top = rg.Point3d(x_a_box, y_a_box + ha / 2.0, 0.0)
                p_datum_conn = rg.Point3d(x_a_box, base_y, 0.0)
                geoms_2d.append(rg.LineCurve(p_a_box_top, p_datum_conn))
                geoms_2d.append(rg.Circle(p_datum_conn, 0.30 * s).ToNurbsCurve())

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


def run():
    doc = Rhino.RhinoDoc.ActiveDoc
    tol = doc.ModelAbsoluteTolerance if doc else 0.001

    raw_terreno      = globals().get('Terreno', globals().get('x', None))
    raw_linhas       = globals().get('LinhasCorte', globals().get('LinhaCorte', globals().get('y', None)))
    raw_verticais    = globals().get('EixosVerticais', globals().get('LinhasLongitudinais', globals().get('Verticais', globals().get('Eixos', None))))
    raw_projeto      = globals().get('LinhaDelimitadora', globals().get('CurvaDelimitadora', globals().get('Delimitadora',
                       globals().get('CurvaProjeto', globals().get('Greide', globals().get('Projeto',
                       globals().get('LinhaProjeto', globals().get('LinhaCorteAterro', globals().get('CorteAterro',
                       globals().get('LinhaGrade', globals().get('GreideProjeto', None)))))))))))
    raw_ponto        = globals().get('Ponto', globals().get('Point', globals().get('Origem', globals().get('Localizacao', None))))
    raw_espacamento  = globals().get('Espacamento', globals().get('DistanciaSecoes', globals().get('Pitch', None)))
    raw_largura      = globals().get('Largura', globals().get('Faixa', globals().get('FaixaInfluencia', 1.0)))
    raw_empolamento  = globals().get('Empolamento', globals().get('FatorK', globals().get('K', 1.20)))
    raw_seletor      = globals().get('Seletor', globals().get('Modo', globals().get('ModoCotas', 1)))
    raw_escala       = globals().get('Escala', globals().get('Scale', globals().get('S', 1.0)))
    raw_nivel_proj   = globals().get('NivelProjeto', globals().get('Plato', globals().get('CotaProjeto', None)))
    raw_inclinacao   = globals().get('InclinacaoMaxima', globals().get('MaxSlope', globals().get('RampaMaxima', globals().get('Inclinacao', globals().get('Imax', 15.0)))))

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

    geoms_terreno = [to_rhino_geom(item) for item in to_list(raw_terreno) if to_rhino_geom(item) is not None]
    if not geoms_terreno:
        msg = "⚠️ Nenhuma geometria válida encontrada na entrada 'Terreno'. Conecte curvas de nível (Curves), malha (Mesh) ou superfície de terreno."
        return [], [], [], [], [], [msg]

    # Processamento das linhas de corte transversais
    lista_linhas_raw = [to_rhino_curve(c) for c in to_list(raw_linhas) if to_rhino_curve(c) is not None]
    if not lista_linhas_raw:
        raise ValueError("LinhasCorte inválidas ou não conectadas. Forneça ao menos uma curva de corte.")

    # =========================================================================
    # 0. ALINHAMENTO E ORGANIZAÇÃO NORMATIVA DOS EIXOS (NBR 6492)
    #    "DE CIMA PARA BAIXO E DA ESQUERDA PARA A DIREITA"
    # =========================================================================

    # 0.1 Determinação do vetor transversal médio (U)
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
    # A seção mais ao topo (norte / início do loteamento) é a Seção A.
    # Conforme avançamos ao longo de u_long_down (para baixo), a projeção aumenta.
    # Ordenar em ordem crescente de projeção em u_long_down coloca a seção do TOPO em primeiro lugar (A).
    def get_sec_proj_down(crv):
        p_mid = crv.PointAtNormalizedLength(0.5)
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

        p_ini_aln = rg.Point3d(u_min_aligned * u_corte.X + v_coord * u_long_down.X,
                               u_min_aligned * u_corte.Y + v_coord * u_long_down.Y,
                               0.0)
        p_fim_aln = rg.Point3d(u_max_aligned * u_corte.X + v_coord * u_long_down.X,
                               u_max_aligned * u_corte.Y + v_coord * u_long_down.Y,
                               0.0)
        lista_alinhadas.append(rg.LineCurve(p_ini_aln, p_fim_aln))

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
            p_mid = crv.PointAtNormalizedLength(0.5)
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

            p_ini_v = rg.Point3d(w_coord * u_corte.X + v_min_aln * u_long_down.X,
                                 w_coord * u_corte.Y + v_min_aln * u_long_down.Y,
                                 0.0)
            p_fim_v = rg.Point3d(w_coord * u_corte.X + v_max_aln * u_long_down.X,
                                 w_coord * u_corte.Y + v_max_aln * u_long_down.Y,
                                 0.0)
            lista_verticais_alinhadas.append(rg.LineCurve(p_ini_v, p_fim_v))

        # Distâncias reais entre eixos verticais consecutivos (1-2, 2-3...)
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
                if ev and ev.Count > 0:
                    pt_inter = ev[0].PointA
                    grid_pts[i][j] = rg.Point3d(pt_inter.X, pt_inter.Y, 0.0)
                else:
                    rc_t, t_t = ct_xy.ClosestPoint(cv_xy.PointAtNormalizedLength(0.5))
                    rc_v, t_v = cv_xy.ClosestPoint(ct_xy.PointAt(t_t))
                    if rc_t and rc_v:
                        pt_c = ct_xy.PointAt(t_t)
                        grid_pts[i][j] = rg.Point3d(pt_c.X, pt_c.Y, 0.0)
                if grid_pts[i][j] is not None:
                    pt_g = grid_pts[i][j]
                    d_ax = (pt_g.X - p_start_i.X) * u_sec_i.X + (pt_g.Y - p_start_i.Y) * u_sec_i.Y
                    secao_eixos_intersec[i].append((d_ax, j, labels_v[j]))
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
    # 2. DEFINIÇÃO DE COORDENADAS 2D E ESPAÇAMENTOS DAS COLUNAS (NBR 6492)
    #    COLUNA 1: SEÇÕES TRANSVERSAIS (A, B, C...)
    #    COLUNA 2: SEÇÕES LONGITUDINAIS (1, 2, 3...)
    # =========================================================================
    banner_space = 18.0 * s

    # Espaçamento vertical da Coluna 1 (Transversais)
    max_h_above = max(sec_heights_above) if sec_heights_above else (20.0 * s)
    max_h_below = max(sec_heights_below) if sec_heights_below else (12.0 * s)
    if raw_espacamento is not None:
        try:
            val_user = float(raw_espacamento)
            gap_livre = max(val_user, 45.0 * s)
        except:
            gap_livre = max(max_h_above * 0.85 + 50.0 * s, 75.0 * s)
    else:
        gap_livre = max(max_h_above * 0.85 + 50.0 * s, 75.0 * s)

    espacamento_y = max_h_below + banner_space + gap_livre + max_h_above
    sec_base_ys = [orig_y - i * espacamento_y for i in range(num_secoes)]
    max_w_t = max([t['total_ext'] for t in sec_terrain_info] or [120.0])

    # Espaçamento vertical da Coluna 2 (Longitudinais)
    max_h_above_v = max(sec_v_heights_above) if sec_v_heights_above else (20.0 * s)
    max_h_below_v = max(sec_v_heights_below) if sec_v_heights_below else (12.0 * s)
    espacamento_y_v = max_h_below_v + banner_space + gap_livre + max_h_above_v
    sec_v_base_ys = [orig_y - j * espacamento_y_v for j in range(num_verticais)]
    max_w_v = max([t['total_ext'] for t in sec_v_terrain_info] or [120.0])

    # Posição X da Coluna 2 (à direita da Coluna 1 com folga ampla de visualização)
    col2_x = orig_x + max_w_t + max(65.0 * s, 45.0)

    # =========================================================================
    # 3. MAPEAMENTO UNIVERSAL DE CURVAS DE PROJETO / LINHAS DELIMITADORAS
    #    (Associa cada curva desenhada à sua respectiva seção 2D com base no X e Y)
    # =========================================================================
    all_targets = []
    for i in range(num_secoes):
        all_targets.append({
            'key': ('T', i),
            'base_x': orig_x,
            'base_y': sec_base_ys[i],
            'total_ext': sec_terrain_info[i]['total_ext'],
            'sec_h': sec_terrain_info[i]['sec_h']
        })
    for j in range(num_verticais):
        all_targets.append({
            'key': ('V', j),
            'base_x': col2_x,
            'base_y': sec_v_base_ys[j],
            'total_ext': sec_v_terrain_info[j]['total_ext'],
            'sec_h': sec_v_terrain_info[j]['sec_h']
        })

    raw_projeto_long = globals().get('LinhaDelimitadoraLongitudinal', globals().get('ProjetoLongitudinal', globals().get('DelimitadoraLongitudinal', globals().get('GreideLongitudinal', None))))
    all_project_curves = [to_rhino_curve(c) for c in (to_list(raw_projeto) + to_list(raw_projeto_long)) if to_rhino_curve(c) is not None]

    matched_curves_map = match_project_curves_to_sections(all_project_curves, all_targets)

    # =========================================================================
    # 4. AVALIAÇÃO ANALÍTICA DAS SEÇÕES TRANSVERSAIS (A, B, C...)
    # =========================================================================
    sec_data_list = []
    for idx_s, t_info in enumerate(sec_terrain_info):
        lbl = labels_t[idx_s]
        base_x = orig_x
        base_y = sec_base_ys[idx_s]
        crv_p, curve_base_y = matched_curves_map.get(('T', idx_s), (None, base_y))

        num_tr = len(t_info['d_divs']) + 1
        sec_levels = parse_nivel_projeto(raw_nivel_proj, idx_s, num_secoes, num_tr)

        s_data = evaluate_section_grade_and_volumes(
            t_info, crv_p, sec_levels, lbl, s, base_x, base_y, curve_base_y, max_slope=max_slope
        )
        sec_data_list.append(s_data)

    # =========================================================================
    # 5. AVALIAÇÃO ANALÍTICA DAS SEÇÕES LONGITUDINAIS (1, 2, 3...)
    #    (Sincronização 3D com as seções transversais ou curva individual)
    # =========================================================================
    sec_v_data_list = []
    for idx_v, t_info_v in enumerate(sec_v_terrain_info):
        lbl_v = labels_v[idx_v]
        base_x_v = col2_x
        base_y_v = sec_v_base_ys[idx_v]
        crv_p_v, curve_base_y_v = matched_curves_map.get(('V', idx_v), (None, base_y_v))

        # Se o usuário desenhou/forneceu uma linha delimitadora individual sobre esta seção longitudinal
        if crv_p_v is not None:
            num_tr_v = len(t_info_v['d_divs']) + 1
            sec_levels_v = parse_nivel_projeto(raw_nivel_proj, idx_v, num_verticais, num_tr_v)
            s_data_v = evaluate_section_grade_and_volumes(
                t_info_v, crv_p_v, sec_levels_v, lbl_v, s, base_x_v, base_y_v, curve_base_y_v, max_slope=max_slope
            )
        else:
            # Sincronização automática contínua com os greides projetados nas seções transversais
            cross_pairs = []
            for (d_ax, i_cross, lbl_t) in vertical_eixos_intersec[idx_v]:
                if i_cross < len(sec_data_list):
                    d_trans_list = [it[0] for it in secao_eixos_intersec[i_cross] if it[1] == idx_v]
                    if d_trans_list:
                        d_trans_val = d_trans_list[0]
                        z_pr_cross = sec_data_list[i_cross]['get_proj_z'](d_trans_val)
                        cross_pairs.append((d_ax, z_pr_cross))

            sampler_v = make_cross_interpolated_grade(
                cross_pairs, t_info_v['total_ext'], t_info_v['z_min'], t_info_v['z_max'], max_slope=max_slope
            )
            s_data_v = evaluate_section_grade_and_volumes(
                t_info_v, None, None, lbl_v, s, base_x_v, base_y_v, base_y_v, max_slope=max_slope
            )
            s_data_v['sampler'] = sampler_v
            s_data_v['get_proj_z'] = sampler_v
            s_data_v['effective_slope'] = getattr(sampler_v, 'effective_slope', 0.0)
            s_data_v['was_clamped'] = getattr(sampler_v, 'was_clamped', False)

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

        sec_v_data_list.append(s_data_v)

    # =========================================================================
    # 6. VOLUMES E BALANÇO DE MASSAS (MÉTODO AGPTEA / SEÇÕES MÉDIAS)
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

    vols_trechos = []
    for i in range(num_secoes - 1):
        d_trecho = distancias_eixos[i]
        a_c1 = sec_data_list[i]['area_total_corte']
        a_c2 = sec_data_list[i+1]['area_total_corte']
        a_a1 = sec_data_list[i]['area_total_aterro']
        a_a2 = sec_data_list[i+1]['area_total_aterro']

        vc = ((a_c1 + a_c2) / 2.0) * d_trecho
        va = ((a_a1 + a_a2) / 2.0) * d_trecho
        saldo = vc - va
        vols_trechos.append((d_trecho, vc, va, saldo))

    saldo_acumulado = 0.0
    fluxo_transporte = []
    for i, (d_t, vc, va, s_local) in enumerate(vols_trechos):
        disp = saldo_acumulado + vc
        if disp >= va:
            sobra = disp - va
            if i < num_secoes - 2:
                nota = "SOBRA: {:+.1f}m³ -> TRANSFERIDA PARA COMPENSAR SEÇÃO {} - {}".format(sobra, labels_t[i+1], labels_t[i+2]).replace('.', ',')
            else:
                nota = "SOBRA FINAL DE CORTE: {:+.1f}m³ (DESTINAR A BOTA-FORA)".format(sobra).replace('.', ',')
            saldo_acumulado = sobra
        else:
            falta = va - disp
            nota = "CORTE CONSUMIDO | DÉFICIT: -{:.1f}m³ (NECESSITA MATERIAL DE EMPRÉSTIMO)".format(falta).replace('.', ',')
            saldo_acumulado = -falta
        fluxo_transporte.append(nota)

    # 6.2 Distâncias e Volumes Longitudinais (1 -> 2 -> 3...)
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
                    nota_v = "SOBRA FINAL LONGITUDINAL: {:+.1f}m³ (BOTA-FORA)".format(sobra_v).replace('.', ',')
                saldo_acum_v = sobra_v
            else:
                falta_v = va_v - disp_v
                nota_v = "DÉFICIT LONGITUDINAL: -{:.1f}m³ (EMPRÉSTIMO)".format(falta_v).replace('.', ',')
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

    # 7.1 Cabeçalho da Coluna 1: SEÇÕES TRANSVERSAIS
    p_hdr_col1 = rg.Point3d(orig_x, orig_y + max_h_above + 14.5 * s, 0.0)
    t_hdr1 = make_text_geometry("SEÇÕES TRANSVERSAIS (A - A, B - B...)", p_hdr_col1, 2.0 * s, rg.TextJustification.BottomLeft, s)
    p_sub_hdr1 = rg.Point3d(orig_x, orig_y + max_h_above + 12.0 * s, 0.0)
    sub_hdr1 = make_text_geometry("Perfis Transversais | Visualização e Edição de Greide", p_sub_hdr1, 0.90 * s, rg.TextJustification.BottomLeft, s)
    desenho_completo_secoes_2d.extend(t_hdr1)
    desenho_completo_secoes_2d.extend(sub_hdr1)
    desenho_secoes_t_only.extend(t_hdr1)
    desenho_secoes_t_only.extend(sub_hdr1)

    # Renderização de cada Seção Transversal
    for idx_s, s_data in enumerate(sec_data_list):
        lbl = labels_t[idx_s]
        base_x = orig_x
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

        # Banner de Transferência de Massa entre Seções Transversais Consecutivas
        if idx_s < num_secoes - 1:
            lbl_prox = labels_t[idx_s + 1]
            d_t, vc_t, va_t, s_t = vols_trechos[idx_s]
            nota_t = fluxo_transporte[idx_s]

            next_sec = sec_data_list[idx_s + 1]
            next_datum = math.floor(next_sec['z_min'] - 2.0)
            next_h_top = (next_sec['z_max'] - next_datum) + 16.0 * s
            y_bot_current = base_y - 12.0 * s
            y_top_next = (base_y - espacamento_y) + next_h_top
            y_banner = (y_bot_current + y_top_next) / 2.0
            x_banner = base_x + s_data['total_ext'] / 2.0

            banner_geoms, _ = make_mass_haul_banner(x_banner, y_banner, lbl, lbl_prox, d_t, vc_t, va_t, s_t, nota_t, s)
            desenho_completo_secoes_2d.extend(banner_geoms)
            desenho_secoes_t_only.extend(banner_geoms)

    # 7.2 Cabeçalho e Renderização da Coluna 2: SEÇÕES LONGITUDINAIS (1, 2, 3...)
    if num_verticais >= 1:
        p_hdr_col2 = rg.Point3d(col2_x, orig_y + max_h_above_v + 14.5 * s, 0.0)
        t_hdr2 = make_text_geometry("SEÇÕES LONGITUDINAIS (1 - 1, 2 - 2...)", p_hdr_col2, 2.0 * s, rg.TextJustification.BottomLeft, s)
        p_sub_hdr2 = rg.Point3d(col2_x, orig_y + max_h_above_v + 12.0 * s, 0.0)
        sub_hdr2 = make_text_geometry("Perfis Longitudinais | Visualização e Edição de Greide", p_sub_hdr2, 0.90 * s, rg.TextJustification.BottomLeft, s)
        desenho_completo_secoes_2d.extend(t_hdr2)
        desenho_completo_secoes_2d.extend(sub_hdr2)
        desenho_secoes_v_only.extend(t_hdr2)
        desenho_secoes_v_only.extend(sub_hdr2)

        for idx_v, s_data_v in enumerate(sec_v_data_list):
            lbl_v = labels_v[idx_v]
            base_x_v = col2_x
            base_y_v = sec_v_base_ys[idx_v]
            crv_aln_3d_v = lista_verticais[idx_v]

            res_sec_v = render_single_section_2d_and_3d(
                s_data_v, lbl_v, base_x_v, base_y_v, s, modo_cotas, cor_corte, cor_aterro,
                crv_aln_3d=crv_aln_3d_v, is_longitudinal=True, axis_title_prefix="SEÇÃO "
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

            # Banner de Transferência de Massa entre Seções Longitudinais Consecutivas
            if idx_v < num_verticais - 1 and idx_v < len(vols_trechos_v):
                lbl_v_prox = labels_v[idx_v + 1]
                d_tv, vc_tv, va_tv, s_tv = vols_trechos_v[idx_v]
                nota_tv = fluxo_transporte_v[idx_v]

                next_sec_v = sec_v_data_list[idx_v + 1]
                next_datum_v = math.floor(next_sec_v['z_min'] - 2.0)
                next_h_top_v = (next_sec_v['z_max'] - next_datum_v) + 16.0 * s
                y_bot_current_v = base_y_v - 12.0 * s
                y_top_next_v = (base_y_v - espacamento_y_v) + next_h_top_v
                y_banner_v = (y_bot_current_v + y_top_next_v) / 2.0
                x_banner_v = base_x_v + s_data_v['total_ext'] / 2.0

                banner_geoms_v, _ = make_mass_haul_banner(x_banner_v, y_banner_v, lbl_v, lbl_v_prox, d_tv, vc_tv, va_tv, s_tv, nota_tv, s)
                desenho_completo_secoes_2d.extend(banner_geoms_v)
                desenho_secoes_v_only.extend(banner_geoms_v)

    # =========================================================================
    # 8. PLANTA BAIXA TÉCNICA (EIXOS, BALÕES E QUADRANTES)
    # =========================================================================
    planta_baixa_geoms = []

    offset_cota_fora = 8.5 * s
    offset_balao_fora = offset_cota_fora + 7.5 * s

    if num_secoes >= 2:
        p_ref_1 = lista_alinhadas[0].PointAtStart
        p_ref_2 = lista_alinhadas[-1].PointAtStart
        v_ref = p_ref_2 - p_ref_1
        if v_ref.Length > 1e-4:
            u_ref = rg.Vector3d(v_ref)
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

    # Identificação dos Quadrantes (Centroides)
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
    # 9. MEMORIAL TÉCNICO DE TERRAPLENAGEM (RELATÓRIO FORMATADO AGPTEA)
    # =========================================================================
    vol_total_corte_geo = sum(item[1] for item in vols_trechos)
    vol_total_aterro_geo = sum(item[2] for item in vols_trechos)
    vol_total_corte_solto = vol_total_corte_geo * fator_k
    saldo_global = vol_total_corte_geo - vol_total_aterro_geo

    if saldo_global > 0.01:
        diag_global = "SOBRA DE MATERIAL (+{:.2f} m³): Terraplenagem superavitária. Necessário bota-fora ou espalhamento.".format(saldo_global)
    elif saldo_global < -0.01:
        diag_global = "DÉFICIT DE MATERIAL ({:.2f} m³): Necessário empréstimo de terra para atingir as cotas de projeto.".format(saldo_global)
    else:
        diag_global = "EQUILÍBRIO PERFEITO: Corte e Aterro rigorosamente balanceados no loteamento."

    relatorio = [
        "=========================================================================================",
        "            MEMORIAL TÉCNICO E PLANILHA DE TERRAPLENAGEM (NORMA AGPTEA / DER)            ",
        "=========================================================================================",
        "1. RESUMO GERAL DAS SEÇÕES TRANSVERSAIS (EIXOS {} A {}):".format(labels_t[0], labels_t[-1]),
        "-----------------------------------------------------------------------------------------",
        "{:<10} | {:<12} | {:<14} | {:<14} | {:<12} | {:<12}".format("SEÇÃO", "EXTENSÃO", "ÁREA CORTE", "ÁREA ATERRO", "H.MÁX CORTE", "H.MÁX ATERRO"),
        "-----------------------------------------------------------------------------------------"
    ]

    for sd in sec_data_list:
        relatorio.append("{:<10} | {:<10.2f} m | {:<12.2f} m² | {:<12.2f} m² | {:<10.2f} m | {:<10.2f} m".format(
            sd['label'], sd['total_ext'], sd['area_total_corte'], sd['area_total_aterro'], sd['max_h_corte'], sd['max_h_aterro']
        ))

    sec_num_bal = 2
    if num_verticais >= 1:
        relatorio.extend([
            "-----------------------------------------------------------------------------------------",
            "2. RESUMO DAS SEÇÕES LONGITUDINAIS (EIXOS {} A {}):".format(labels_v[0], labels_v[-1]),
            "-----------------------------------------------------------------------------------------",
            "{:<10} | {:<12} | {:<14} | {:<14} | {:<12} | {:<12}".format("EIXO", "EXTENSÃO", "ÁREA CORTE", "ÁREA ATERRO", "H.MÁX CORTE", "H.MÁX ATERRO"),
            "-----------------------------------------------------------------------------------------"
        ])
        for sdv in sec_v_data_list:
            relatorio.append("{:<10} | {:<10.2f} m | {:<12.2f} m² | {:<12.2f} m² | {:<10.2f} m | {:<10.2f} m".format(
                "EIXO " + sdv['label'], sdv['total_ext'], sdv['area_total_corte'], sdv['area_total_aterro'], sdv['max_h_corte'], sdv['max_h_aterro']
            ))
        sec_num_bal = 3

    sec_num_tot = sec_num_bal + 1

    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "{}. BALANÇO PROGRESSIVO E COMPENSAÇÃO LONGITUDINAL DE MASSAS (ONDE SAI -> ONDE VAI):".format(sec_num_bal),
    ])
    for i, nota in enumerate(fluxo_transporte):
        relatorio.append("   - Trecho {} -> {}:".format(labels_t[i], labels_t[i+1]))
        relatorio.append("     " + nota)

    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "{}. TOTAIS GERAIS DO EMPREENDIMENTO:".format(sec_num_tot),
        "   - Número de Seções Transversais Analisadas: {}".format(num_secoes),
        "   - Número de Seções Longitudinais Analisadas : {}".format(num_verticais),
        "   - Fator de Empolamento Adotado (K)        : {:.2f} ({}% de expansão)".format(fator_k, int((fator_k - 1.0) * 100)),
        "   - Regra da Linha Delimitadora (Greide)    : Inclinação Máxima {:.1f}% ({})".format(
            max_slope * 100.0,
            "Ajustada para o teto de 15% onde excedeu" if any(sd.get('was_clamped') for sd in (sec_data_list + sec_v_data_list)) else "Atendida em todas as seções"
        ),
        "   - Volume Total Geométrico de CORTE        : {:.2f} m³".format(vol_total_corte_geo),
        "   - Volume Total Geométrico de ATERRO       : {:.2f} m³".format(vol_total_aterro_geo),
        "   - Volume Total de Corte Solto (Transporte): {:.2f} m³".format(vol_total_corte_solto),
        "   - BALANÇO LÍQUIDO FINAL (Corte - Aterro)   : {:+.2f} m³".format(saldo_global),
        "   - Diagnóstico Operacional:",
        "     " + diag_global,
        "========================================================================================="
    ])

    # =========================================================================
    # 10. CONSTRUÇÃO DA SUPERFÍCIE E FATIAS 3D DE TERRAPLENAGEM (TERRENO PROJETADO)
    # =========================================================================
    quads_sup_3d_corte = []
    quads_sup_3d_aterro = []
    quads_sup_3d_neutro = []

    cor_neutro = System.Drawing.Color.FromArgb(205, 210, 205)

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

            n_divs = max(int(max(La, Lb) / 1.5), 25)

            for k in range(n_divs):
                ta = k / float(n_divs)
                tb = (k + 1) / float(n_divs)

                da0 = ta * La; da1 = tb * La
                db0 = ta * Lb; db1 = tb * Lb

                p00 = rg.Point3d(p_sa.X + ux_a * da0, p_sa.Y + uy_a * da0, s_data_a['get_proj_z'](da0))
                p10 = rg.Point3d(p_sa.X + ux_a * da1, p_sa.Y + uy_a * da1, s_data_a['get_proj_z'](da1))
                p11 = rg.Point3d(p_sb.X + ux_b * db1, p_sb.Y + uy_b * db1, s_data_b['get_proj_z'](db1))
                p01 = rg.Point3d(p_sb.X + ux_b * db0, p_sb.Y + uy_b * db0, s_data_b['get_proj_z'](db0))

                t00 = rg.Point3d(p00.X, p00.Y, interpolate_terrain_z(da0, s_data_a['clean_pts']))
                t10 = rg.Point3d(p10.X, p10.Y, interpolate_terrain_z(da1, s_data_a['clean_pts']))
                t11 = rg.Point3d(p11.X, p11.Y, interpolate_terrain_z(db1, s_data_b['clean_pts']))
                t01 = rg.Point3d(p01.X, p01.Y, interpolate_terrain_z(db0, s_data_b['clean_pts']))

                z_pr_m = (p00.Z + p10.Z + p11.Z + p01.Z) / 4.0
                z_tn_m = (t00.Z + t10.Z + t11.Z + t01.Z) / 4.0
                diff_z = z_tn_m - z_pr_m

                if diff_z > 0.03:
                    quads_sup_3d_corte.append([p00, p10, p11, p01])
                elif diff_z < -0.03:
                    quads_sup_3d_aterro.append([p00, p10, p11, p01])
                else:
                    quads_sup_3d_neutro.append([p00, p10, p11, p01])

    m_3d_corte_sec  = create_colored_mesh(quads_3d_corte_secoes, cor_corte)
    m_3d_aterro_sec = create_colored_mesh(quads_3d_aterro_secoes, cor_aterro)
    m_3d_sup_corte  = create_colored_mesh(quads_sup_3d_corte, cor_corte)
    m_3d_sup_aterro = create_colored_mesh(quads_sup_3d_aterro, cor_aterro)
    m_3d_sup_neutro = create_colored_mesh(quads_sup_3d_neutro, cor_neutro)

    mesh_terreno_projetado = rg.Mesh()
    for m_part in [m_3d_sup_corte, m_3d_sup_aterro, m_3d_sup_neutro]:
        if m_part and getattr(m_part, 'IsValid', False):
            mesh_terreno_projetado.Append(m_part)
    if mesh_terreno_projetado.Faces.Count > 0:
        mesh_terreno_projetado.Compact()
        try:
            mesh_terreno_projetado.Normals.ComputeNormals()
        except:
            pass
        if not mesh_terreno_projetado.IsValid:
            mesh_terreno_projetado = None
    else:
        mesh_terreno_projetado = None

    # Compilação do Modelo 3D Completo (Visualização em Perspectiva 3D)
    modelo_3d_completo = []
    for m_part in [m_3d_sup_corte, m_3d_sup_aterro, m_3d_sup_neutro, m_3d_corte_sec, m_3d_aterro_sec]:
        if m_part and getattr(m_part, 'IsValid', False):
            modelo_3d_completo.append(m_part)

    for crv in greides_3d_all:
        if crv and getattr(crv, 'IsValid', False):
            modelo_3d_completo.append(crv)

    for crv in linhas_3d_all:
        if crv and getattr(crv, 'IsValid', False):
            modelo_3d_completo.append(crv)

    # Atribuição de saídas dinâmicas para conexões opcionais no Grasshopper
    globals()['SecoesTransversais'] = desenho_secoes_t_only
    globals()['SecoesLongitudinais'] = desenho_secoes_v_only
    globals()['SecoesV'] = desenho_secoes_v_only
    globals()['TerrenoModificado'] = mesh_terreno_projetado
    globals()['SuperficieProjeto'] = mesh_terreno_projetado
    globals()['Corte3D'] = m_3d_sup_corte or m_3d_corte_sec
    globals()['Aterro3D'] = m_3d_sup_aterro or m_3d_aterro_sec
    globals()['Greide3D'] = [c for c in greides_3d_all if c and getattr(c, 'IsValid', False)]
    globals()['Volumes3D'] = [m for m in [m_3d_sup_corte, m_3d_sup_aterro, m_3d_corte_sec, m_3d_aterro_sec] if m and getattr(m, 'IsValid', False)]
    globals()['g'] = mesh_terreno_projetado
    globals()['h'] = m_3d_corte_sec
    globals()['i'] = m_3d_aterro_sec

    return modelo_3d_completo, planta_baixa_geoms, desenho_completo_secoes_2d, poligonos_corte_all, poligonos_aterro_all, relatorio

res_3d, res_planta, res_secoes, res_corte, res_aterro, rel = run()

# SAÍDAS CONECTADAS NO GRASSHOPPER:
a = res_3d         # MODELO 3D COMPLETO DE TERRAPLENAGEM (Superfície Projetada + Fatias 3D Laranja/Verde + Greides 3D)
b = res_planta     # PLANTA BAIXA TÉCNICA (Eixos cotados A, B, C... e 1, 2, 3... com balões NBR, setas e quadrantes)
c = res_secoes     # DESENHO COMPLETO DAS SEÇÕES 2D ALINHADAS (com títulos, malhas Laranja/Verde, cotas NBR e fluxo de massa)
d = res_corte      # Polígonos de CORTE de todas as seções (Curves para Area / Hatch / Bake)
e = res_aterro     # Polígonos de ATERRO de todas as seções (Curves para Area / Hatch / Bake)
f = rel            # Memorial Técnico de Terraplenagem e Balanço Progressivo AGPTEA (Panel)
