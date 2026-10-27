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
  CurvaProjeto     [Item/List, Curve] : Greide/Linha de terraplenagem projetada [Opcional].
  NivelProjeto     [Item, float]      : Cota Z fixa caso projeto seja horizontal [Opcional].
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

def create_colored_mesh(quads_pts, color):
    """Cria uma malha 2D colorida (Shaded Mesh) a partir de quadriláteros formados pelos trapézios."""
    if not quads_pts: return None
    m = rg.Mesh()
    idx = 0
    for quad in quads_pts:
        if len(quad) == 4:
            p0, p1, p2, p3 = quad
            m.Vertices.Add(p0)
            m.Vertices.Add(p1)
            m.Vertices.Add(p2)
            m.Vertices.Add(p3)
            m.Faces.AddFace(idx, idx + 1, idx + 2, idx + 3)
            if color:
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
            idx += 4
        elif len(quad) == 3:
            p0, p1, p2 = quad
            m.Vertices.Add(p0)
            m.Vertices.Add(p1)
            m.Vertices.Add(p2)
            m.Faces.AddFace(idx, idx + 1, idx + 2)
            if color:
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
                m.VertexColors.Add(color)
            idx += 3
    m.Normals.ComputeNormals()
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
                        curves.append(rg.LineCurve(pts[0], pts[1]))
                    else:
                        curves.append(rg.Polyline(pts).ToPolylineCurve())

        if accent_type and accent_type in ACCENT_STROKES:
            for a_stroke in ACCENT_STROKES[accent_type]:
                pts = [p_origin + x_axis * (cur_x + sx * scale_x) + y_axis * (start_y + sy * height) for sx, sy in a_stroke]
                if len(pts) == 2:
                    curves.append(rg.LineCurve(pts[0], pts[1]))
                else:
                    curves.append(rg.Polyline(pts).ToPolylineCurve())

        cur_x += cw + char_gap

    return curves

def make_text_geometry(text_str, pt, height, justification=None, s=1.0, plane=None):
    if not text_str: return []
    curves = []

    # 1. Tenta Explode nativo do Rhino
    try:
        if plane is None:
            text_plane = rg.Plane(pt, rg.Vector3d.ZAxis)
        else:
            text_plane = rg.Plane(plane)
            text_plane.Origin = pt

        te = rg.TextEntity()
        te.PlainText = text_str
        te.Plane = text_plane
        te.TextHeight = height
        if justification is not None:
            te.Justification = justification
        else:
            te.Justification = rg.TextJustification.BottomLeft

        doc = Rhino.RhinoDoc.ActiveDoc
        if doc and hasattr(doc, 'DimStyles') and doc.DimStyles.Current:
            te.DimensionStyleId = doc.DimStyles.Current.Id

        exp = te.Explode()
        if exp and len(exp) > 0:
            for c in exp:
                if c and c.IsValid: curves.append(c)
            if len(curves) > 0: return curves
    except: pass

    # 2. Tenta CreateCurves
    try:
        doc = Rhino.RhinoDoc.ActiveDoc
        dim_style = doc.DimStyles.Current if (doc and hasattr(doc, 'DimStyles')) else None
        if dim_style:
            exp2 = te.CreateCurves(dim_style, False, 1.0, 1.0)
            if exp2 and len(exp2) > 0:
                for c in exp2:
                    if c and c.IsValid: curves.append(c)
                if len(curves) > 0: return curves
    except: pass

    # 3. Fallback: Stroke Vector Font integrado
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
    if color is None:
        color = System.Drawing.Color.FromArgb(252, 252, 252)
    m = rg.Mesh()
    m.Vertices.Add(p0)
    m.Vertices.Add(p1)
    m.Vertices.Add(p2)
    m.Vertices.Add(p3)
    m.Faces.AddFace(0, 1, 2, 3)
    m.VertexColors.Add(color)
    m.VertexColors.Add(color)
    m.VertexColors.Add(color)
    m.VertexColors.Add(color)
    m.Normals.ComputeNormals()
    return m

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

    geoms = [l1, l2, l_mid, mesh_dir, lr1, lr2, l_stem, l_shelf]
    if te_crvs:
        if isinstance(te_crvs, list):
            geoms.extend(te_crvs)
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
            geoms.extend([seta_mesh, l_seta1, l_seta2, l_seta3])

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
    geoms.append(bg_mesh)
    geoms.append(badge_crv)

    txt_crvs = make_text_geometry(txt_str, p_cen, txt_h, rg.TextJustification.MiddleCenter, s, plane_badge)
    if txt_crvs: geoms.extend(txt_crvs)

    return geoms

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
    geoms.append(bg_mesh)
    geoms.append(box_crv)

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
    geoms.extend([arrow_mesh, rg.LineCurve(p_tip, p_l), rg.LineCurve(p_tip, p_r), rg.LineCurve(p_l, p_r)])

    return geoms, (w_box, h_box)

# =============================================================================
# AVALIAÇÃO ANALÍTICA DE UMA SEÇÃO TRANSVERSAL INDIVIDUAL
# =============================================================================

def evaluate_section_data(crv_corte, geoms_terreno, curva_greide_in, raw_nivel_proj, tol):
    """Calcula a geometria 3D, perfil de terreno natural e greide de terraplenagem para uma seção."""
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
                            # Amostra a cota Z exata buscando o ponto mais próximo na curva 3D original
                            rc, t_real = geom.ClosestPoint(rg.Point3d(pt_c.X, pt_c.Y, geom.PointAtStart.Z))
                            z_val = geom.PointAt(t_real).Z if rc else geom.PointAtStart.Z
                            d = (pt_c.X - p_start.X) * ux + (pt_c.Y - p_start.Y) * uy
                            if -tol <= d <= L_horiz + tol:
                                d_clamped = max(0.0, min(L_horiz, d))
                                pts_with_d.append((d_clamped, rg.Point3d(p_start.X + ux * d_clamped, p_start.Y + uy * d_clamped, z_val)))
            except: pass

        # 2. Malha de Terreno (Mesh)
        elif isinstance(geom, rg.Mesh):
            # A. Fatiamento pelo plano vertical do corte
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

            # B. Amostragem contínua via Raios Verticais
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

    # Garantia de fechamento das pontas d = 0.0 e d = L_horiz sem extrapolação perigosa (Zero-Spike Clamping)
    if clean_pts:
        if clean_pts[0][0] > 0.01:
            z_ini = clean_pts[0][1].Z
            clean_pts.insert(0, (0.0, rg.Point3d(p_start.X, p_start.Y, z_ini)))
        else:
            clean_pts[0] = (0.0, clean_pts[0][1])

        if clean_pts[-1][0] < L_horiz - 0.01:
            z_fim = clean_pts[-1][1].Z
            clean_pts.append((L_horiz, rg.Point3d(p_end.X, p_end.Y, z_fim)))
        else:
            clean_pts[-1] = (L_horiz, clean_pts[-1][1])
    else:
        # Fallback inteligente: busca cota média real das curvas 3D da topografia
        valid_zs = []
        for g in geoms_terreno:
            bb = g.GetBoundingBox(True)
            if bb.IsValid and abs(bb.Max.Z - bb.Min.Z) > 0.01:
                valid_zs.append((bb.Min.Z + bb.Max.Z) / 2.0)
            elif bb.IsValid and abs(bb.Min.Z) > 1.0:
                valid_zs.append(bb.Min.Z)

        z_ref = (sum(valid_zs) / float(len(valid_zs))) if valid_zs else 0.0

        # Refina buscando o ponto mais próximo no relevo
        p_mid_c = crv_corte.PointAtNormalizedLength(0.5)
        best_d = 1e12
        for g in geoms_terreno:
            if isinstance(g, rg.Curve):
                rc, t_cl = g.ClosestPoint(p_mid_c)
                if rc:
                    pt_cl = g.PointAt(t_cl)
                    dist_xy = math.hypot(pt_cl.X - p_mid_c.X, pt_cl.Y - p_mid_c.Y)
                    if dist_xy < best_d:
                        best_d = dist_xy
                        z_ref = pt_cl.Z

        clean_pts = [
            (0.0, rg.Point3d(p_start.X, p_start.Y, z_ref)),
            (L_horiz, rg.Point3d(p_end.X, p_end.Y, z_ref))
        ]

    total_ext = clean_pts[-1][0] if clean_pts else L_horiz
    crv_3d = rg.PolylineCurve([p[1] for p in clean_pts])

    z_min = min(p[1].Z for p in clean_pts)
    z_max = max(p[1].Z for p in clean_pts)

    def get_proj_z(d_val):
        if curva_greide_in is not None:
            c_dom = curva_greide_in.Domain
            t_greide = c_dom.Min + (d_val / max(total_ext, 1e-6)) * (c_dom.Max - c_dom.Min)
            pt_g = curva_greide_in.PointAt(t_greide)
            if abs(pt_g.Z) > 1e-4:
                return pt_g.Z
            elif abs(pt_g.Y) > 1e-4 and z_min <= pt_g.Y <= z_max + 100.0:
                return pt_g.Y
            return pt_g.Z
        elif raw_nivel_proj is not None:
            try: return float(raw_nivel_proj)
            except: pass
        if clean_pts:
            return sum(p[1].Z for p in clean_pts) / float(len(clean_pts))
        return 0.0

    num_passos = max(int(total_ext / 0.25), 80)
    dx = total_ext / float(num_passos)
    estacas_d = [i * dx for i in range(num_passos + 1)]
    if estacas_d[-1] < total_ext: estacas_d.append(total_ext)

    pontos_passagem = []
    diff_sinais = []
    for d in estacas_d:
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

    return {
        'clean_pts': clean_pts,
        'total_ext': total_ext,
        'crv_3d': crv_3d,
        'z_min': z_min,
        'z_max': z_max,
        'get_proj_z': get_proj_z,
        'estacas_finais': estacas_finais,
        'regioes': regioes,
        'area_total_corte': area_total_corte,
        'area_total_aterro': area_total_aterro,
        'max_h_corte': max_h_corte,
        'd_max_corte': d_max_corte,
        'max_h_aterro': max_h_aterro,
        'd_max_aterro': d_max_aterro,
        'pontos_passagem': pontos_passagem
    }

# =============================================================================
# COORDENADOR PRINCIPAL: MULTI-EIXOS, ALINHAMENTO, CUBAGEM E BALANÇO DE MASSAS
# =============================================================================

def run():
    doc = Rhino.RhinoDoc.ActiveDoc
    tol = doc.ModelAbsoluteTolerance if doc else 0.001

    raw_terreno      = globals().get('Terreno', globals().get('x', None))
    raw_linhas       = globals().get('LinhasCorte', globals().get('LinhaCorte', globals().get('y', None)))
    raw_verticais    = globals().get('EixosVerticais', globals().get('LinhasLongitudinais', globals().get('Verticais', globals().get('Eixos', None))))
    raw_projeto      = globals().get('CurvaProjeto', globals().get('Greide', globals().get('Projeto', globals().get('LinhaProjeto', None))))
    raw_ponto        = globals().get('Ponto', globals().get('Point', globals().get('Origem', globals().get('Localizacao', None))))
    raw_espacamento  = globals().get('Espacamento', globals().get('DistanciaSecoes', globals().get('Pitch', None)))
    raw_largura      = globals().get('Largura', globals().get('Faixa', globals().get('FaixaInfluencia', 1.0)))
    raw_empolamento  = globals().get('Empolamento', globals().get('FatorK', globals().get('K', 1.20)))
    raw_seletor      = globals().get('Seletor', globals().get('Modo', globals().get('ModoCotas', 1)))
    raw_escala       = globals().get('Escala', globals().get('Scale', globals().get('S', 1.0)))
    raw_nivel_proj   = globals().get('NivelProjeto', globals().get('Plato', globals().get('CotaProjeto', None)))

    try:
        s = float(raw_escala) if raw_escala is not None else 1.0
        if s <= 0.05: s = 1.0
    except: s = 1.0

    try:
        fator_k = float(raw_empolamento) if raw_empolamento is not None else 1.20
        if fator_k <= 0.5: fator_k = 1.20
    except: fator_k = 1.20

    # Processamento das linhas de corte transversais
    lista_linhas_raw = [to_rhino_curve(c) for c in to_list(raw_linhas) if to_rhino_curve(c) is not None]
    if not lista_linhas_raw:
        raise ValueError("LinhasCorte inválidas ou não conectadas. Forneça ao menos uma curva de corte.")

    # 0. ALINHAMENTO AUTOMÁTICO DE TODOS OS EIXOS TRANSVERSAIS (CONFORME CROQUI)
    # Todos os eixos ganham a mesma direção, comprimento idêntico e partem de uma linha
    # de base comum perpendicular (linha de alinhamento vermelha na margem externa).
    
    # 0.1 Harmonização do sentido de direção (todos apontando do mesmo lado)
    lista_linhas = [c.DuplicateCurve() for c in lista_linhas_raw]
    vec_ref = lista_linhas[0].PointAtEnd - lista_linhas[0].PointAtStart
    for i in range(len(lista_linhas)):
        vec_i = lista_linhas[i].PointAtEnd - lista_linhas[i].PointAtStart
        if vec_i.X * vec_ref.X + vec_i.Y * vec_ref.Y < 0.0:
            lista_linhas[i].Reverse()

    # 0.2 Vetor diretor médio normalizado das seções transversais (U)
    ux_sum = 0.0
    uy_sum = 0.0
    for c in lista_linhas:
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

    # Vetor perpendicular em planta (V) - direção da linha de alinhamento
    v_perp = rg.Vector3d(-u_corte.Y, u_corte.X, 0.0)

    # 0.3 Envelopamento longitudinal do empreendimento ao longo de U
    u_proj_vals = []
    for c in lista_linhas:
        p0 = c.PointAtStart
        p1 = c.PointAtEnd
        u_proj_vals.append(p0.X * u_corte.X + p0.Y * u_corte.Y)
        u_proj_vals.append(p1.X * u_corte.X + p1.Y * u_corte.Y)

    # Margem extra de 6.0m para garantir que atravesse o relevo confortavelmente
    u_min_aligned = min(u_proj_vals) - 6.0 * s
    u_max_aligned = max(u_proj_vals) + 6.0 * s

    # 0.4 Construção dos eixos alinhados definitivos
    lista_alinhadas = []
    v_coords = []
    for c in lista_linhas:
        p_mid = c.PointAtNormalizedLength(0.5)
        v_c = p_mid.X * v_perp.X + p_mid.Y * v_perp.Y
        v_coords.append(v_c)

        p_ini_aln = rg.Point3d(u_min_aligned * u_corte.X + v_c * v_perp.X,
                               u_min_aligned * u_corte.Y + v_c * v_perp.Y,
                               0.0)
        p_fim_aln = rg.Point3d(u_max_aligned * u_corte.X + v_c * v_perp.X,
                               u_max_aligned * u_corte.Y + v_c * v_perp.Y,
                               0.0)
        lista_alinhadas.append(rg.LineCurve(p_ini_aln, p_fim_aln))

    # 0.5 ALINHAMENTO AUTOMÁTICO DOS EIXOS LONGITUDINAIS/VERTICAIS (1, 2, 3...)
    # Mesma metodologia paramétrica dos eixos transversais: harmonização de direção,
    # comprimento idêntico e linha de base comum perpendicular (A Linha Vermelha no topo).
    lista_verticais_raw = [to_rhino_curve(c) for c in to_list(raw_verticais) if to_rhino_curve(c) is not None]
    lista_verticais_alinhadas = []
    distancias_verticais = []
    u_vert = rg.Vector3d(-u_corte.Y, u_corte.X, 0.0)
    w_perp_v = rg.Vector3d(u_corte)

    if lista_verticais_raw:
        lista_vert_dups = [c.DuplicateCurve() for c in lista_verticais_raw]

        # Direção de referência relativa às seções transversais (do início das seções para o fim)
        if len(lista_alinhadas) >= 2:
            vec_dir_secoes = lista_alinhadas[-1].PointAtStart - lista_alinhadas[0].PointAtStart
        else:
            vec_dir_secoes = lista_vert_dups[0].PointAtEnd - lista_vert_dups[0].PointAtStart

        # Harmonização de sentido de todos os eixos verticais
        for i in range(len(lista_vert_dups)):
            vec_i = lista_vert_dups[i].PointAtEnd - lista_vert_dups[i].PointAtStart
            if vec_i.X * vec_dir_secoes.X + vec_i.Y * vec_dir_secoes.Y < 0.0:
                lista_vert_dups[i].Reverse()

        # Vetor diretor médio normalizado dos eixos verticais
        vx_sum, vy_sum = 0.0, 0.0
        for c in lista_vert_dups:
            dx = c.PointAtEnd.X - c.PointAtStart.X
            dy = c.PointAtEnd.Y - c.PointAtStart.Y
            l_len = math.hypot(dx, dy)
            if l_len > 1e-4:
                vx_sum += dx / l_len
                vy_sum += dy / l_len
        v_len = math.hypot(vx_sum, vy_sum)
        if v_len > 1e-4:
            u_vert = rg.Vector3d(vx_sum / v_len, vy_sum / v_len, 0.0)
        else:
            u_vert = rg.Vector3d(-u_corte.Y, u_corte.X, 0.0)

        # Vetor perpendicular aos eixos verticais (linha de base no topo)
        w_perp_v = rg.Vector3d(-u_vert.Y, u_vert.X, 0.0)

        # Envelopamento longitudinal ao longo de u_vert (abrangendo tanto os eixos quanto as seções de corte)
        v_proj_vals = []
        for c in lista_vert_dups:
            p0, p1 = c.PointAtStart, c.PointAtEnd
            v_proj_vals.append(p0.X * u_vert.X + p0.Y * u_vert.Y)
            v_proj_vals.append(p1.X * u_vert.X + p1.Y * u_vert.Y)

        for c in lista_alinhadas:
            p0, p1 = c.PointAtStart, c.PointAtEnd
            v_proj_vals.append(p0.X * u_vert.X + p0.Y * u_vert.Y)
            v_proj_vals.append(p1.X * u_vert.X + p1.Y * u_vert.Y)

        v_min_aln = min(v_proj_vals) - 6.0 * s
        v_max_aln = max(v_proj_vals) + 6.0 * s

        # Ordena os eixos verticais transversalmente da esquerda para a direita (ao longo de w_perp_v)
        v_items = []
        for c in lista_vert_dups:
            p_mid = c.PointAtNormalizedLength(0.5)
            w_c = p_mid.X * w_perp_v.X + p_mid.Y * w_perp_v.Y
            v_items.append((w_c, c))
        v_items.sort(key=lambda x: x[0])

        for w_c, _ in v_items:
            p_ini_v = rg.Point3d(v_min_aln * u_vert.X + w_c * w_perp_v.X,
                                 v_min_aln * u_vert.Y + w_c * w_perp_v.Y,
                                 0.0)
            p_fim_v = rg.Point3d(v_max_aln * u_vert.X + w_c * w_perp_v.X,
                                 v_max_aln * u_vert.Y + w_c * w_perp_v.Y,
                                 0.0)
            lista_verticais_alinhadas.append(rg.LineCurve(p_ini_v, p_fim_v))

        # Distâncias entre eixos verticais consecutivos
        for j in range(len(lista_verticais_alinhadas) - 1):
            d_v = calculate_axis_distance(lista_verticais_alinhadas[j], lista_verticais_alinhadas[j+1])
            distancias_verticais.append(max(d_v, 0.1))

    lista_verticais = lista_verticais_alinhadas

    # Processamento de curvas de projeto
    lista_projetos = [to_rhino_curve(c) for c in to_list(raw_projeto) if to_rhino_curve(c) is not None]

    ponto_base = to_rhino_point(raw_ponto)
    orig_x = ponto_base.X if ponto_base else 0.0
    orig_y = ponto_base.Y if ponto_base else 0.0

    modo_cotas = parse_seletor(raw_seletor)
    geoms_terreno = [to_rhino_geom(item) for item in to_list(raw_terreno) if to_rhino_geom(item) is not None]

    if not geoms_terreno:
        msg = "⚠️ Nenhuma geometria válida encontrada na entrada 'Terreno'. Conecte curvas de nível (Curves), malha (Mesh) ou superfície de terreno."
        return [], [], [], [], [], [msg]

    # 1. Avalia cada seção transversal individualmente (usando os eixos alinhados)
    num_secoes = len(lista_alinhadas)
    sec_data_list = []
    labels_t = [format_section_label(i) for i in range(num_secoes)]

    for idx_s, crv_c in enumerate(lista_alinhadas):
        crv_p = lista_projetos[idx_s] if idx_s < len(lista_projetos) else (lista_projetos[0] if lista_projetos else None)
        s_data = evaluate_section_data(crv_c, geoms_terreno, crv_p, raw_nivel_proj, tol)
        sec_data_list.append(s_data)

    # 2. Datum e Espaçamento Amplo para Alinhamento Perfeito e Separação Total dos Perfis
    sec_heights_above = []
    sec_heights_below = []
    for sd in sec_data_list:
        sec_datum_z = math.floor(sd['z_min'] - 2.0)
        sec_h = sd['z_max'] - sec_datum_z
        # Altura acima do DATUM: relevo + folga do título e caixa de corte
        sec_heights_above.append(sec_h + 16.0 * s)
        # Altura abaixo do DATUM: folga da caixa de aterro e cotas inferiores
        sec_heights_below.append(12.0 * s)

    max_h_above = max(sec_heights_above)
    max_h_below = max(sec_heights_below)
    banner_space = 18.0 * s  # Espaço reservado para o banner de balanço de massas e seta

    # Folga livre visível entre o fim de uma seção e o topo da próxima
    if raw_espacamento is not None:
        try:
            val_user = float(raw_espacamento)
            gap_livre = max(val_user, 45.0 * s)
        except:
            gap_livre = max(max_h_above * 0.85 + 50.0 * s, 75.0 * s)
    else:
        gap_livre = max(max_h_above * 0.85 + 50.0 * s, 75.0 * s)

    espacamento_y = max_h_below + banner_space + gap_livre + max_h_above

    # 3. Distâncias Reais entre Eixos Consecutivos (para Cubagem AGPTEA)
    distancias_eixos = []
    for i in range(num_secoes - 1):
        d_val = calculate_axis_distance(lista_alinhadas[i], lista_alinhadas[i+1])
        distancias_eixos.append(max(d_val, 0.1))

    # Caso haja apenas 1 seção isolada, usa Largura
    if num_secoes == 1:
        try: w_single = float(raw_largura) if raw_largura is not None else 1.0
        except: w_single = 1.0
        distancias_eixos = [w_single]

    # 4. Cálculo dos Volumes por Trecho (Método das Seções Transversais AGPTEA)
    # V = ((A1 + A2) / 2) * D
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

    # 5. Cadeia de Compensação de Massas (Rastreamento de Onde Sai e Para Onde Vai)
    saldo_acumulado = 0.0
    fluxo_transporte = []

    for i, (d_t, vc, va, s_local) in enumerate(vols_trechos):
        lbl_a = labels_t[i]
        lbl_b = labels_t[i+1]
        disp = saldo_acumulado + vc

        if disp >= va:
            sobra = disp - va
            if i < num_secoes - 2:
                lbl_prox_a = labels_t[i+1]
                lbl_prox_b = labels_t[i+2]
                nota = "SOBRA: {:+.1f}m³ -> TRANSFERIDA PARA COMPENSAR SEÇÃO {} - {}".format(sobra, lbl_prox_a, lbl_prox_b).replace('.', ',')
            else:
                nota = "SOBRA FINAL DE CORTE: {:+.1f}m³ (DESTINAR A BOTA-FORA)".format(sobra).replace('.', ',')
            saldo_acumulado = sobra
        else:
            falta = va - disp
            nota = "CORTE CONSUMIDO | DÉFICIT: -{:.1f}m³ (NECESSITA MATERIAL DE EMPRÉSTIMO)".format(falta).replace('.', ',')
            saldo_acumulado = -falta

        fluxo_transporte.append(nota)

    # =========================================================================
    # 6. CONSTRUÇÃO DO DESENHO DAS SEÇÕES 2D ALINHADAS
    # =========================================================================
    desenho_completo_secoes_2d = []
    poligonos_corte_all = []
    poligonos_aterro_all = []
    linhas_3d_all = []

    cor_corte  = System.Drawing.Color.FromArgb(245, 130, 32)
    cor_aterro = System.Drawing.Color.FromArgb(46, 204, 113)

    for idx_s, s_data in enumerate(sec_data_list):
        lbl = labels_t[idx_s]
        base_x = orig_x
        base_y = orig_y - idx_s * espacamento_y

        clean_pts = s_data['clean_pts']
        total_ext = s_data['total_ext']
        get_proj_z = s_data['get_proj_z']
        linhas_3d_all.append(s_data['crv_3d'])

        # Datum Local da Seção (Padrão Topografia / NBR 6492 / AGPTEA)
        sec_datum_z = math.floor(s_data['z_min'] - 2.0)
        sec_h = s_data['z_max'] - sec_datum_z

        # Título da Seção
        p_tit = rg.Point3d(base_x, base_y + sec_h + 8.5 * s, 0.0)
        tit_crvs = make_text_geometry("SEÇÃO {} - {}".format(lbl, lbl), p_tit, 1.50 * s, rg.TextJustification.BottomLeft, s)
        desenho_completo_secoes_2d.extend(tit_crvs)

        sub_str = "Extensão: {:.2f}m | Cota Média: +{:.2f}m".format(total_ext, sum(p[1].Z for p in clean_pts)/len(clean_pts)).replace('.', ',')
        p_sub = rg.Point3d(base_x, base_y + sec_h + 6.8 * s, 0.0)
        sub_crvs = make_text_geometry(sub_str, p_sub, 0.85 * s, rg.TextJustification.BottomLeft, s)
        desenho_completo_secoes_2d.extend(sub_crvs)

        # Linha e Rótulo de DATUM
        p_d_ini = rg.Point3d(base_x, base_y, 0.0)
        p_d_fim = rg.Point3d(base_x + total_ext, base_y, 0.0)
        desenho_completo_secoes_2d.append(rg.LineCurve(p_d_ini, p_d_fim))

        lbl_datum = "DATUM +{:.2f}".format(sec_datum_z).replace('.', ',')
        p_datum_txt = rg.Point3d(base_x - 1.2 * s, base_y, 0.0)
        datum_crvs = make_text_geometry(lbl_datum, p_datum_txt, 0.80 * s, rg.TextJustification.MiddleRight, s)
        desenho_completo_secoes_2d.extend(datum_crvs)

        # Perfil Natural 2D
        pts_tn_2d = [rg.Point3d(base_x + d, base_y + (pt.Z - sec_datum_z), 0.0) for d, pt in clean_pts]
        crv_tn_2d = rg.PolylineCurve(pts_tn_2d)
        desenho_completo_secoes_2d.append(crv_tn_2d)

        # Polígono de fechamento de solo sob TN
        p_solo = [p_d_ini, p_d_fim] + list(reversed(pts_tn_2d)) + [p_d_ini]
        desenho_completo_secoes_2d.append(rg.Polyline(p_solo).ToPolylineCurve())

        # Greide 2D
        pts_gr_2d = [rg.Point3d(base_x + d, base_y + (get_proj_z(d) - sec_datum_z), 0.0) for d in s_data['estacas_finais']]
        crv_gr_2d = rg.PolylineCurve(pts_gr_2d)
        desenho_completo_secoes_2d.append(crv_gr_2d)

        # Malhas de Corte e Aterro
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
                pts_poly.append(pts_poly[0])
                poly_c = rg.Polyline(pts_poly).ToPolylineCurve()
                poligonos_corte_all.append(poly_c)
            else:
                for d in d_list: pts_poly.append(rg.Point3d(base_x + d, base_y + (get_proj_z(d) - sec_datum_z), 0.0))
                for d in reversed(d_list): pts_poly.append(rg.Point3d(base_x + d, base_y + (interpolate_terrain_z(d, clean_pts) - sec_datum_z), 0.0))
                pts_poly.append(pts_poly[0])
                poly_a = rg.Polyline(pts_poly).ToPolylineCurve()
                poligonos_aterro_all.append(poly_a)

        m_c = create_colored_mesh(quads_corte, cor_corte)
        m_a = create_colored_mesh(quads_aterro, cor_aterro)
        if m_c: desenho_completo_secoes_2d.append(m_c)
        if m_a: desenho_completo_secoes_2d.append(m_a)

        # Cotas de Nível NBR 6492 (Com filtro de espaçamento horizontal mínimo para evitar poluição visual)
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
                desenho_completo_secoes_2d.extend(m_geoms)

        if modo_cotas in [0, 1]:
            # Marcadores de início e fim do greide
            z_ini = get_proj_z(0.0)
            z_fim = get_proj_z(total_ext)
            m_g_ini, _ = draw_nbr_level_marker(base_x, base_y + (z_ini - sec_datum_z), "GREIDE +{:.2f}".format(z_ini).replace('.', ','), s)
            m_g_fim, _ = draw_nbr_level_marker(base_x + total_ext, base_y + (z_fim - sec_datum_z), "GREIDE +{:.2f}".format(z_fim).replace('.', ','), s)
            desenho_completo_secoes_2d.extend(m_g_ini)
            desenho_completo_secoes_2d.extend(m_g_fim)

            # Pontos de Passagem
            for dp, zp in s_data['pontos_passagem']:
                m_pp, _ = draw_nbr_level_marker(base_x + dp, base_y + (zp - sec_datum_z), "P.P. +{:.2f}".format(zp).replace('.', ','), s)
                desenho_completo_secoes_2d.extend(m_pp)

            # Caixas de Área / Volume da Seção com enquadramento perfeito
            # 1. Caixa Superior: Corte
            d_c_all = [d for r_type, d_list in s_data['regioes'] if r_type == "CORTE" for d in d_list]
            if s_data['area_total_corte'] > 0.01 and d_c_all:
                d_c_mid = (min(d_c_all) + max(d_c_all)) / 2.0
                z_c_top = max(interpolate_terrain_z(d, clean_pts) for d in d_c_all)
                txt_v1 = "CORTE SEÇÃO {}: {:.2f} m²".format(lbl, s_data['area_total_corte']).replace('.', ',')
                txt_v2 = "Altura Máx: {:.2f}m".format(s_data['max_h_corte']).replace('.', ',')

                hc_est = 5.5 * s
                y_c_box = base_y + (z_c_top - sec_datum_z) + 6.0 * s + (hc_est / 2.0)
                x_c_box = base_x + d_c_mid

                c_card, (wc, hc) = make_callout_card(x_c_box, y_c_box, txt_v1, txt_v2, s, True)
                desenho_completo_secoes_2d.extend(c_card)

                # Linha guia ao topo do relevo
                p_c_box_bot = rg.Point3d(x_c_box, y_c_box - hc / 2.0, 0.0)
                p_crest = rg.Point3d(x_c_box, base_y + (interpolate_terrain_z(d_c_mid, clean_pts) - sec_datum_z), 0.0)
                desenho_completo_secoes_2d.append(rg.LineCurve(p_c_box_bot, p_crest))
                desenho_completo_secoes_2d.append(rg.Circle(p_crest, 0.30 * s).ToNurbsCurve())

            # 2. Caixa Inferior: Aterro
            d_a_all = [d for r_type, d_list in s_data['regioes'] if r_type == "ATERRO" for d in d_list]
            if s_data['area_total_aterro'] > 0.01 and d_a_all:
                d_a_mid = (min(d_a_all) + max(d_a_all)) / 2.0
                txt_a1 = "ATERRO SEÇÃO {}: {:.2f} m²".format(lbl, s_data['area_total_aterro']).replace('.', ',')
                txt_a2 = "Altura Máx: {:.2f}m".format(s_data['max_h_aterro']).replace('.', ',')

                ha_est = 5.5 * s
                y_a_box = base_y - 5.5 * s - (ha_est / 2.0)
                x_a_box = base_x + d_a_mid

                a_card, (wa, ha) = make_callout_card(x_a_box, y_a_box, txt_a1, txt_a2, s, False)
                desenho_completo_secoes_2d.extend(a_card)

                p_a_box_top = rg.Point3d(x_a_box, y_a_box + ha / 2.0, 0.0)
                p_datum_conn = rg.Point3d(x_a_box, base_y, 0.0)
                desenho_completo_secoes_2d.append(rg.LineCurve(p_a_box_top, p_datum_conn))
                desenho_completo_secoes_2d.append(rg.Circle(p_datum_conn, 0.30 * s).ToNurbsCurve())

        # Banner de Transferência de Massa entre Seção Atual e a Próxima (Espaçamento Amplo)
        if idx_s < num_secoes - 1:
            lbl_prox = labels_t[idx_s + 1]
            d_t, vc_t, va_t, s_t = vols_trechos[idx_s]
            nota_t = fluxo_transporte[idx_s]

            # Posição intermediária perfeitamente centrada no vão livre entre as seções
            next_sec = sec_data_list[idx_s + 1]
            next_datum = math.floor(next_sec['z_min'] - 2.0)
            next_h_top = (next_sec['z_max'] - next_datum) + 16.0 * s

            y_bot_current = base_y - 12.0 * s
            y_top_next = (base_y - espacamento_y) + next_h_top
            y_banner = (y_bot_current + y_top_next) / 2.0
            x_banner = base_x + total_ext / 2.0
            banner_geoms, _ = make_mass_haul_banner(x_banner, y_banner, lbl, lbl_prox, d_t, vc_t, va_t, s_t, nota_t, s)
            desenho_completo_secoes_2d.extend(banner_geoms)

    # =========================================================================
    # 7. CONSTRUÇÃO DA PLANTA BAIXA TÉCNICA (TOP VIEW: EIXOS, BALÕES E QUADRANTES)
    # =========================================================================
    planta_baixa_geoms = []

    # Recuos das cotas e balões para fora do desenho (fora da mancha do loteamento)
    offset_cota_fora = 8.5 * s
    offset_balao_fora = offset_cota_fora + 7.5 * s

    # Linha de Alinhamento de Referência Externa (A Linha Vermelha do croqui do usuário)
    if num_secoes >= 2:
        p_ref_1 = lista_alinhadas[0].PointAtStart
        p_ref_2 = lista_alinhadas[-1].PointAtStart
        v_ref = p_ref_2 - p_ref_1
        if v_ref.Length > 1e-4:
            u_ref = rg.Vector3d(v_ref)
            u_ref.Unitize()
            l_align_ref = rg.LineCurve(p_ref_1 - u_ref * (4.0 * s), p_ref_2 + u_ref * (4.0 * s))
            planta_baixa_geoms.append(l_align_ref)

    # 1. Eixos Transversais Alinhados em Planta com Balões NBR e Linhas de Chamada
    for idx_s, crv_aln in enumerate(lista_alinhadas):
        lbl = labels_t[idx_s]
        p_start = crv_aln.PointAtStart
        p_end = crv_aln.PointAtEnd

        planta_baixa_geoms.append(crv_aln)

        # Prolongamento e Balão no início (lado esquerdo, fora do desenho, além da linha de cota)
        p_b_ini = p_start - u_corte * offset_balao_fora
        planta_baixa_geoms.append(rg.LineCurve(p_start, p_b_ini))
        b_ini_geoms = draw_plan_axis_bubble(p_b_ini, u_corte, lbl, s)
        planta_baixa_geoms.extend(b_ini_geoms)

        # Prolongamento e Balão no fim (lado direito, fora do desenho)
        p_b_fim = p_end + u_corte * (4.0 * s)
        planta_baixa_geoms.append(rg.LineCurve(p_end, p_b_fim))
        b_fim_geoms = draw_plan_axis_bubble(p_b_fim, u_corte, lbl, s)
        planta_baixa_geoms.extend(b_fim_geoms)

    # 2. Cotas Técnicas de Distância entre Eixos FORA DO DESENHO (ao longo da linha vermelha)
    for idx_s in range(num_secoes - 1):
        p_start_1 = lista_alinhadas[idx_s].PointAtStart
        p_start_2 = lista_alinhadas[idx_s + 1].PointAtStart
        dist_val = distancias_eixos[idx_s]

        # Desenha a cota técnica fora do desenho, recuada ao longo de -u_corte
        cota_fora = draw_plan_dimension(p_start_1, p_start_2, dist_val, s, -u_corte, offset_cota_fora)
        planta_baixa_geoms.extend(cota_fora)

    # 3. Eixos Longitudinais/Verticais Alinhados em Planta com Linha de Referência e Balões
    num_verticais = len(lista_verticais)
    labels_v = [str(i + 1) for i in range(num_verticais)]

    offset_cota_v_fora = 8.5 * s
    offset_balao_v_fora = offset_cota_v_fora + 7.5 * s

    # Linha de Alinhamento de Referência Externa no Topo (A Linha Vermelha no topo do croqui)
    if num_verticais >= 2:
        p_vref_1 = lista_verticais[0].PointAtStart
        p_vref_2 = lista_verticais[-1].PointAtStart
        v_vref = p_vref_2 - p_vref_1
        if v_vref.Length > 1e-4:
            u_vref = rg.Vector3d(v_vref)
            u_vref.Unitize()
            l_align_v_ref = rg.LineCurve(p_vref_1 - u_vref * (4.0 * s), p_vref_2 + u_vref * (4.0 * s))
            planta_baixa_geoms.append(l_align_v_ref)

    # 3.1 Eixos verticais desenhados com balões NBR no início (topo) e no fim (base)
    for idx_v, crv_v in enumerate(lista_verticais):
        lbl_v = labels_v[idx_v]
        p_start_v = crv_v.PointAtStart
        p_end_v = crv_v.PointAtEnd

        planta_baixa_geoms.append(crv_v)

        # Prolongamento e Balão numérico no topo (além da linha de cota)
        p_bv_ini = p_start_v - u_vert * offset_balao_v_fora
        planta_baixa_geoms.append(rg.LineCurve(p_start_v, p_bv_ini))
        bv_ini = draw_plan_axis_bubble(p_bv_ini, u_vert, lbl_v, s)
        planta_baixa_geoms.extend(bv_ini)

        # Prolongamento e Balão numérico na base (fim do eixo)
        p_bv_fim = p_end_v + u_vert * (4.0 * s)
        planta_baixa_geoms.append(rg.LineCurve(p_end_v, p_bv_fim))
        bv_fim = draw_plan_axis_bubble(p_bv_fim, u_vert, lbl_v, s)
        planta_baixa_geoms.extend(bv_fim)

    # 3.2 Cotas Técnicas de Distância entre Eixos Verticais FORA DO DESENHO (ao longo do topo)
    for idx_v in range(num_verticais - 1):
        p_sv1 = lista_verticais[idx_v].PointAtStart
        p_sv2 = lista_verticais[idx_v + 1].PointAtStart
        dist_v_val = distancias_verticais[idx_v] if idx_v < len(distancias_verticais) else 0.0

        cota_v_fora = draw_plan_dimension(p_sv1, p_sv2, dist_v_val, s, -u_vert, offset_cota_v_fora)
        planta_baixa_geoms.extend(cota_v_fora)

    # 4. Malha de Quadrantes de Terraplenagem em Planta (Interseção Transversais x Verticais)
    if num_secoes >= 2 and num_verticais >= 2:
        grid_pts = [[None for _ in range(num_verticais)] for _ in range(num_secoes)]
        for i, ct in enumerate(lista_alinhadas):
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

        plane_grid = rg.Plane(rg.Point3d.Origin, u_corte, v_perp)

        for i in range(num_secoes - 1):
            for j in range(num_verticais - 1):
                p00 = grid_pts[i][j]
                p01 = grid_pts[i][j+1]
                p11 = grid_pts[i+1][j+1]
                p10 = grid_pts[i+1][j]
                if p00 and p01 and p11 and p10:
                    poly_q = rg.Polyline([p00, p01, p11, p10, p00]).ToPolylineCurve()
                    planta_baixa_geoms.append(poly_q)

                    # Cálculo analítico do Centroide Geométrico exato do quadrante
                    amp = rg.AreaMassProperties.Compute(poly_q)
                    if amp and amp.Centroid.IsValid:
                        p_cen = amp.Centroid
                    else:
                        # Fallback: Interseção das diagonais (o exato "X" desenhado no croqui)
                        l_diag1 = rg.Line(p00, p11)
                        l_diag2 = rg.Line(p01, p10)
                        rc, t1, t2 = rg.Intersect.Intersection.LineLine(l_diag1, l_diag2)
                        if rc:
                            p_cen = l_diag1.PointAt(t1)
                        else:
                            p_cen = (p00 + p01 + p11 + p10) / 4.0

                    txt_q = "Q.{}-{}".format(labels_t[i], labels_v[j])
                    badge_geoms = draw_quadrant_badge(p_cen, txt_q, s, plane_grid)
                    planta_baixa_geoms.extend(badge_geoms)

    # =========================================================================
    # 8. MEMORIAL TÉCNICO DE TERRAPLENAGEM E BALANÇO DE MASSAS (AGPTEA)
    # =========================================================================
    vol_total_corte_geo = sum(vt[1] for vt in vols_trechos) if vols_trechos else (sec_data_list[0]['area_total_corte'] * 1.0)
    vol_total_aterro_geo = sum(vt[2] for vt in vols_trechos) if vols_trechos else (sec_data_list[0]['area_total_aterro'] * 1.0)
    vol_total_corte_solto = vol_total_corte_geo * fator_k
    saldo_global = vol_total_corte_geo - vol_total_aterro_geo

    if abs(saldo_global) < 0.1:
        diag_global = "COMPENSAÇÃO EXATA (Balanço Neutro: Volume de Corte supre o Aterro)."
    elif saldo_global > 0:
        diag_global = "SOBRA GLOBAL DE TERRA (Bota-Fora necessário: {:.2f} m³ geométrico / {:.2f} m³ solto).".format(saldo_global, saldo_global * fator_k)
    else:
        diag_global = "DÉFICIT GLOBAL DE TERRA (Importação de Empréstimo necessária: {:.2f} m³).".format(abs(saldo_global))

    relatorio = [
        "=========================================================================================",
        "      MEMORIAL DE CÁLCULO DE TERRAPLENAGEM E BALANÇO DE MASSAS (NBR 6492 & AGPTEA)       ",
        "=========================================================================================",
        "1. QUADRO GERAL DE SEÇÕES TRANSVERSAIS:",
        "   Seção   | Extensão (m) | Cota Mín (m) | Cota Máx (m) | Área Corte (m²) | Área Aterro (m²)",
        "   -------------------------------------------------------------------------------------",
    ]
    for idx_s, sd in enumerate(sec_data_list):
        relatorio.append("   {:^7} | {:^12.2f} | {:^12.2f} | {:^12.2f} | {:^15.2f} | {:^16.2f}".format(
            labels_t[idx_s], sd['total_ext'], sd['z_min'], sd['z_max'], sd['area_total_corte'], sd['area_total_aterro']
        ))

    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "2. VOLUMES POR TRECHO (MÉTODO DAS SEÇÕES TRANSVERSAIS / MÉDIAS AGPTEA):",
        "   Trecho   | Distância (m) | Vol. Corte (m³) | Vol. Aterro (m³) | Saldo Local do Trecho",
        "   -------------------------------------------------------------------------------------",
    ])
    for i, (dt, vc, va, st) in enumerate(vols_trechos):
        lbl_trecho = "{} -> {}".format(labels_t[i], labels_t[i+1])
        status_s = "(Sobra)" if st >= 0 else "(Falta)"
        relatorio.append("   {:^8} | {:^13.2f} | {:^15.2f} | {:^16.2f} | {:^+12.2f} m³ {}".format(
            lbl_trecho, dt, vc, va, st, status_s
        ))

    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "3. BALANÇO PROGRESSIVO E COMPENSAÇÃO LONGITUDINAL DE MASSAS (ONDE SAI -> ONDE VAI):",
    ])
    for i, nota in enumerate(fluxo_transporte):
        relatorio.append("   - Trecho {} -> {}:".format(labels_t[i], labels_t[i+1]))
        relatorio.append("     " + nota)

    relatorio.extend([
        "-----------------------------------------------------------------------------------------",
        "4. TOTAIS GERAIS DO EMPREENDIMENTO:",
        "   - Número de Seções Transversais Analisadas: {}".format(num_secoes),
        "   - Fator de Empolamento Adotado (K)        : {:.2f} ({}% de expansão)".format(fator_k, int((fator_k - 1.0) * 100)),
        "   - Volume Total Geométrico de CORTE        : {:.2f} m³".format(vol_total_corte_geo),
        "   - Volume Total Geométrico de ATERRO       : {:.2f} m³".format(vol_total_aterro_geo),
        "   - Volume Total de Corte Solto (Transporte): {:.2f} m³".format(vol_total_corte_solto),
        "   - BALANÇO LÍQUIDO FINAL (Corte - Aterro)   : {:+.2f} m³".format(saldo_global),
        "   - Diagnóstico Operacional:",
        "     " + diag_global,
        "========================================================================================="
    ])

    return linhas_3d_all, planta_baixa_geoms, desenho_completo_secoes_2d, poligonos_corte_all, poligonos_aterro_all, relatorio

res_3d, res_planta, res_secoes, res_corte, res_aterro, rel = run()

# SAÍDAS CONECTADAS NO GRASSHOPPER:
a = res_3d         # Linhas 3D dos cortes sobre o terreno natural
b = res_planta     # PLANTA BAIXA TÉCNICA (Eixos cotados A, B, C... e 1, 2, 3... com balões NBR, setas e quadrantes)
c = res_secoes     # DESENHO COMPLETO DAS SEÇÕES 2D ALINHADAS (com títulos, malhas Laranja/Verde, cotas NBR e fluxo de massa)
d = res_corte      # Polígonos de CORTE de todas as seções (Curves para Area / Hatch / Bake)
e = res_aterro     # Polígonos de ATERRO de todas as seções (Curves para Area / Hatch / Bake)
f = rel            # Memorial Técnico de Terraplenagem e Balanço Progressivo AGPTEA (Panel)
