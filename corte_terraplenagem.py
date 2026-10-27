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

def generate_stroke_text(text_str, pt, height, justification=None):
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

    start_x = pt.X
    start_y = pt.Y

    if justification == rg.TextJustification.MiddleCenter:
        start_x = pt.X - total_w / 2.0
        start_y = pt.Y - height / 2.0
    elif justification == rg.TextJustification.BottomCenter:
        start_x = pt.X - total_w / 2.0
        start_y = pt.Y
    elif justification == rg.TextJustification.TopCenter:
        start_x = pt.X - total_w / 2.0
        start_y = pt.Y - height
    elif justification == rg.TextJustification.TopLeft:
        start_x = pt.X
        start_y = pt.Y - height
    elif justification == rg.TextJustification.MiddleRight:
        start_x = pt.X - total_w
        start_y = pt.Y - height / 2.0
    elif justification == rg.TextJustification.BottomRight:
        start_x = pt.X - total_w
        start_y = pt.Y

    cur_x = start_x
    for strokes, accent_type, cw in char_data:
        scale_x = cw / 0.60
        if strokes:
            for stroke in strokes:
                if len(stroke) >= 2:
                    pts = [rg.Point3d(cur_x + sx * scale_x, start_y + sy * height, pt.Z) for sx, sy in stroke]
                    if len(pts) == 2:
                        curves.append(rg.LineCurve(pts[0], pts[1]))
                    else:
                        curves.append(rg.Polyline(pts).ToPolylineCurve())

        if accent_type and accent_type in ACCENT_STROKES:
            for a_stroke in ACCENT_STROKES[accent_type]:
                pts = [rg.Point3d(cur_x + sx * scale_x, start_y + sy * height, pt.Z) for sx, sy in a_stroke]
                if len(pts) == 2:
                    curves.append(rg.LineCurve(pts[0], pts[1]))
                else:
                    curves.append(rg.Polyline(pts).ToPolylineCurve())

        cur_x += cw + char_gap

    return curves

def make_text_geometry(text_str, pt, height, justification=None, s=1.0):
    if not text_str: return []
    curves = []

    # 1. Tenta Explode nativo do Rhino
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
    return generate_stroke_text(text_str, pt, height, justification)

make_text_entity = make_text_geometry

def make_callout_card(center_x, center_y, title_text, sub_text, s=1.0):
    """Cria uma caixa retangular técnica com textos vetoriais nítidos de volume e área."""
    txt_h1 = 1.10 * s
    txt_h2 = 0.75 * s
    pad_x  = 1.20 * s
    pad_y  = 0.60 * s
    gap_y  = 0.50 * s

    w_text1 = len(title_text) * (txt_h1 * 0.65 + txt_h1 * 0.15)
    w_text2 = len(sub_text) * (txt_h2 * 0.65 + txt_h2 * 0.15)
    w_content = max(w_text1, w_text2)
    w_box = max(w_content + pad_x * 2.0, 11.5 * s)
    h_box = txt_h1 + txt_h2 + gap_y + pad_y * 2.0

    p0 = rg.Point3d(center_x - w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p1 = rg.Point3d(center_x + w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p2 = rg.Point3d(center_x + w_box / 2.0, center_y + h_box / 2.0, 0.0)
    p3 = rg.Point3d(center_x - w_box / 2.0, center_y + h_box / 2.0, 0.0)
    box_crv = rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve()

    # Linha divisória horizontal interna técnica
    y_div = center_y + 0.05 * s
    p_div_l = rg.Point3d(center_x - w_box / 2.0 + 0.5 * s, y_div, 0.0)
    p_div_r = rg.Point3d(center_x + w_box / 2.0 - 0.5 * s, y_div, 0.0)
    div_crv = rg.LineCurve(p_div_l, p_div_r)

    y_t1 = center_y + h_box / 4.0 + 0.05 * s
    y_t2 = center_y - h_box / 4.0 + 0.05 * s

    pt_t1 = rg.Point3d(center_x, y_t1, 0.0)
    te1_crvs = make_text_geometry(title_text, pt_t1, txt_h1, rg.TextJustification.MiddleCenter, s)

    pt_t2 = rg.Point3d(center_x, y_t2, 0.0)
    te2_crvs = make_text_geometry(sub_text, pt_t2, txt_h2, rg.TextJustification.MiddleCenter, s)

    geoms = [box_crv, div_crv]
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
    r = 1.35 * s
    circ = rg.Circle(pt, r).ToNurbsCurve()
    geoms.append(circ)

    txt_crvs = make_text_geometry(label_str, pt, 1.15 * s, rg.TextJustification.MiddleCenter, s)
    if txt_crvs: geoms.extend(txt_crvs)

    if dir_vec and dir_vec.Length > 1e-4:
        v_norm = rg.Vector3d(dir_vec)
        v_norm.Unitize()
        n_view = rg.Vector3d(-v_norm.Y, v_norm.X, 0.0)
        p_base = pt + n_view * r
        p_tip = pt + n_view * (r + 1.2 * s)
        p_left = p_base - v_norm * (0.45 * s)
        p_right = p_base + v_norm * (0.45 * s)

        seta_mesh = make_filled_mesh_tri(p_tip, p_left, p_right)
        l_seta1 = rg.LineCurve(p_tip, p_left)
        l_seta2 = rg.LineCurve(p_tip, p_right)
        l_seta3 = rg.LineCurve(p_left, p_right)
        geoms.extend([seta_mesh, l_seta1, l_seta2, l_seta3])

    return geoms

def draw_plan_dimension(p1, p2, dist_val, s=1.0):
    """Desenha uma cota linear técnica com ticks e texto de distância entre dois eixos em planta."""
    geoms = []
    vec = p2 - p1
    d_len = vec.Length
    if d_len < 1e-3: return geoms

    u = rg.Vector3d(vec)
    u.Unitize()
    n = rg.Vector3d(-u.Y, u.X, 0.0)

    l_cota = rg.LineCurve(p1, p2)
    geoms.append(l_cota)

    tick_len = 0.6 * s
    t1_a = p1 - n * (tick_len / 2.0) - u * (0.2 * s)
    t1_b = p1 + n * (tick_len / 2.0) + u * (0.2 * s)
    t2_a = p2 - n * (tick_len / 2.0) - u * (0.2 * s)
    t2_b = p2 + n * (tick_len / 2.0) + u * (0.2 * s)
    geoms.append(rg.LineCurve(t1_a, t1_b))
    geoms.append(rg.LineCurve(t2_a, t2_b))

    p_mid = (p1 + p2) / 2.0 + n * (0.60 * s)
    txt_cota = make_text_geometry("D = {:.2f}m".format(dist_val).replace('.', ','), p_mid, 0.75 * s, rg.TextJustification.MiddleCenter, s)
    if txt_cota: geoms.extend(txt_cota)

    return geoms

def calculate_axis_distance(crv_a, crv_b):
    """Calcula a distância ortogonal média entre duas linhas de corte consecutivas em planta."""
    try:
        t_mid_a = crv_a.Domain.Min + 0.5 * (crv_a.Domain.Max - crv_a.Domain.Min)
        p_mid_a = crv_a.PointAt(t_mid_a)
        rc, t_b = crv_b.ClosestPoint(p_mid_a)
        d1 = p_mid_a.DistanceTo(crv_b.PointAt(t_b)) if rc else None

        t_mid_b = crv_b.Domain.Min + 0.5 * (crv_b.Domain.Max - crv_b.Domain.Min)
        p_mid_b = crv_b.PointAt(t_mid_b)
        rc2, t_a = crv_a.ClosestPoint(p_mid_b)
        d2 = p_mid_b.DistanceTo(crv_a.PointAt(t_a)) if rc2 else None

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
    w_box = max(len(transfer_note) * 0.70 * s + 2.5 * s, 26.0 * s)
    h_box = 3.6 * s

    p0 = rg.Point3d(center_x - w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p1 = rg.Point3d(center_x + w_box / 2.0, center_y - h_box / 2.0, 0.0)
    p2 = rg.Point3d(center_x + w_box / 2.0, center_y + h_box / 2.0, 0.0)
    p3 = rg.Point3d(center_x - w_box / 2.0, center_y + h_box / 2.0, 0.0)
    box_crv = rg.Polyline([p0, p1, p2, p3, p0]).ToPolylineCurve()
    geoms.append(box_crv)

    y_div = center_y
    l_div = rg.LineCurve(rg.Point3d(center_x - w_box/2.0 + 0.5*s, y_div, 0.0), rg.Point3d(center_x + w_box/2.0 - 0.5*s, y_div, 0.0))
    geoms.append(l_div)

    t1_str = "TRECHO {} - {} (D = {:.2f}m) | V.Corte: {:.1f}m³ | V.Aterro: {:.1f}m³ | Saldo: {:+.1f}m³".format(
        label_prev, label_next, dist_val, vol_corte, vol_aterro, saldo
    ).replace('.', ',')
    pt_t1 = rg.Point3d(center_x, center_y + h_box / 4.0 + 0.05 * s, 0.0)
    t1_crvs = make_text_geometry(t1_str, pt_t1, 0.75 * s, rg.TextJustification.MiddleCenter, s)
    if t1_crvs: geoms.extend(t1_crvs)

    pt_t2 = rg.Point3d(center_x, center_y - h_box / 4.0 + 0.05 * s, 0.0)
    t2_crvs = make_text_geometry(transfer_note, pt_t2, 0.70 * s, rg.TextJustification.MiddleCenter, s)
    if t2_crvs: geoms.extend(t2_crvs)

    # Seta vertical indicando sentido de transporte longitudinal para a próxima seção
    y_arr_top = center_y - h_box / 2.0
    y_arr_bot = center_y - h_box / 2.0 - 1.4 * s
    p_arr_top = rg.Point3d(center_x, y_arr_top, 0.0)
    p_arr_bot = rg.Point3d(center_x, y_arr_bot, 0.0)
    geoms.append(rg.LineCurve(p_arr_top, p_arr_bot))

    p_tip = p_arr_bot
    p_l = rg.Point3d(center_x - 0.40 * s, y_arr_bot + 0.55 * s, 0.0)
    p_r = rg.Point3d(center_x + 0.40 * s, y_arr_bot + 0.55 * s, 0.0)
    arrow_mesh = make_filled_mesh_tri(p_tip, p_l, p_r)
    geoms.extend([arrow_mesh, rg.LineCurve(p_tip, p_l), rg.LineCurve(p_tip, p_r), rg.LineCurve(p_l, p_r)])

    return geoms

# =============================================================================
# AVALIAÇÃO ANALÍTICA DE UMA SEÇÃO TRANSVERSAL INDIVIDUAL
# =============================================================================

def evaluate_section_data(crv_corte, lista_terreno, curva_greide_in, raw_nivel_proj, tol):
    """Calcula a geometria 3D, perfil de terreno natural e greide de terraplenagem para uma seção."""
    intersecoes_3d = []
    for item in lista_terreno:
        geom = to_rhino_geom(item)
        if geom is None: continue
        if isinstance(geom, rg.Curve):
            ev = rg.Intersect.Intersection.CurveCurve(crv_corte, geom, tol, tol)
            if ev:
                for cc in ev:
                    if cc.IsPoint:
                        t_val = cc.ParameterA
                        pt_corte = crv_corte.PointAt(t_val)
                        intersecoes_3d.append((t_val, rg.Point3d(pt_corte.X, pt_corte.Y, cc.PointB.Z)))
        elif isinstance(geom, rg.Mesh):
            ev_mc = rg.Intersect.Intersection.MeshPolyline(geom, rg.Polyline([crv_corte.PointAtStart, crv_corte.PointAtEnd]))
            if ev_mc:
                for pt in ev_mc[0]:
                    rc, t_val = crv_corte.ClosestPoint(pt, tol * 10)
                    if rc: intersecoes_3d.append((t_val, pt))

    num_amostras = 150
    t_start, t_end = crv_corte.Domain.Min, crv_corte.Domain.Max
    dt = (t_end - t_start) / float(num_amostras)

    pts_amostrados = []
    for i in range(num_amostras + 1):
        t_param = t_start + i * dt
        pt_eval = crv_corte.PointAt(t_param)
        z_found = None
        for item in lista_terreno:
            geom = to_rhino_geom(item)
            if isinstance(geom, rg.Mesh):
                ray = rg.Ray3d(rg.Point3d(pt_eval.X, pt_eval.Y, -10000.0), rg.Vector3d.ZAxis)
                h = rg.Intersect.Intersection.MeshRay(geom, ray)
                if h >= 0:
                    z_found = -10000.0 + h
                    break
        if z_found is not None:
            pts_amostrados.append((t_param, rg.Point3d(pt_eval.X, pt_eval.Y, z_found)))

    pts_totais = sorted(intersecoes_3d + pts_amostrados, key=lambda x: x[0])
    if not pts_totais:
        pts_totais = [
            (t_start, rg.Point3d(crv_corte.PointAtStart.X, crv_corte.PointAtStart.Y, 0.0)),
            (t_end, rg.Point3d(crv_corte.PointAtEnd.X, crv_corte.PointAtEnd.Y, 0.0))
        ]

    clean_pts = []
    d_acum = 0.0
    for idx_p, (t_val, pt) in enumerate(pts_totais):
        if idx_p == 0:
            clean_pts.append((0.0, pt))
        else:
            prev_pt = clean_pts[-1][1]
            dist_seg = rg.Point3d(pt.X, pt.Y, 0.0).DistanceTo(rg.Point3d(prev_pt.X, prev_pt.Y, 0.0))
            if dist_seg > 0.005:
                d_acum += dist_seg
                clean_pts.append((d_acum, pt))

    total_ext = clean_pts[-1][0] if clean_pts else 1.0
    crv_3d = rg.PolylineCurve([p[1] for p in clean_pts])

    z_min = min(p[1].Z for p in clean_pts)
    z_max = max(p[1].Z for p in clean_pts)

    def get_proj_z(d_val):
        if curva_greide_in is not None:
            c_dom = curva_greide_in.Domain
            t_greide = c_dom.Min + (d_val / total_ext) * (c_dom.Max - c_dom.Min)
            pt_g = curva_greide_in.PointAt(t_greide)
            if abs(pt_g.Z) < 0.001 and abs(pt_g.Y) > 0.001:
                return pt_g.Y
            return pt_g.Z
        elif raw_nivel_proj is not None:
            try: return float(raw_nivel_proj)
            except: pass
        return sum(p[1].Z for p in clean_pts) / float(len(clean_pts))

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

    # Processamento das linhas de corte transversais
    lista_linhas = [to_rhino_curve(c) for c in to_list(raw_linhas) if to_rhino_curve(c) is not None]
    if not lista_linhas:
        raise ValueError("LinhasCorte inválidas ou não conectadas. Forneça ao menos uma curva de corte.")

    # Processamento dos eixos longitudinais/verticais
    lista_verticais = [to_rhino_curve(c) for c in to_list(raw_verticais) if to_rhino_curve(c) is not None]

    # Processamento de curvas de projeto
    lista_projetos = [to_rhino_curve(c) for c in to_list(raw_projeto) if to_rhino_curve(c) is not None]

    ponto_base = to_rhino_point(raw_ponto)
    orig_x = ponto_base.X if ponto_base else 0.0
    orig_y = ponto_base.Y if ponto_base else 0.0

    try:
        fator_k = float(raw_empolamento) if raw_empolamento is not None else 1.20
        if fator_k <= 0.5: fator_k = 1.20
    except: fator_k = 1.20

    try:
        s = float(raw_escala) if raw_escala is not None else 1.0
        if s <= 0.05: s = 1.0
    except: s = 1.0

    modo_cotas = parse_seletor(raw_seletor)
    lista_terreno = to_list(raw_terreno)

    # 1. Avalia cada seção transversal individualmente
    num_secoes = len(lista_linhas)
    sec_data_list = []
    labels_t = [format_section_label(i) for i in range(num_secoes)]

    for idx_s, crv_c in enumerate(lista_linhas):
        crv_p = lista_projetos[idx_s] if idx_s < len(lista_projetos) else (lista_projetos[0] if lista_projetos else None)
        s_data = evaluate_section_data(crv_c, lista_terreno, crv_p, raw_nivel_proj, tol)
        sec_data_list.append(s_data)

    # 2. Datum e Espaçamento Uniforme para Alinhamento Perfeito
    all_z_min = min(sd['z_min'] for sd in sec_data_list)
    all_z_max = max(sd['z_max'] for sd in sec_data_list)
    datum_z = math.floor(all_z_min - 2.0)
    max_delta_z = all_z_max - datum_z

    if raw_espacamento is not None:
        try: espacamento_y = max(float(raw_espacamento), 5.0)
        except: espacamento_y = max(max_delta_z + 14.0 * s, 22.0 * s)
    else:
        espacamento_y = max(max_delta_z + 15.0 * s, 24.0 * s)

    # 3. Distâncias Reais entre Eixos Consecutivos (para Cubagem AGPTEA)
    distancias_eixos = []
    for i in range(num_secoes - 1):
        d_val = calculate_axis_distance(lista_linhas[i], lista_linhas[i+1])
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

        # Título da Seção
        p_tit = rg.Point3d(base_x, base_y + (s_data['z_max'] - datum_z) + 3.2 * s, 0.0)
        tit_crvs = make_text_geometry("SEÇÃO {} - {}".format(lbl, lbl), p_tit, 1.45 * s, rg.TextJustification.BottomLeft, s)
        desenho_completo_secoes_2d.extend(tit_crvs)

        sub_str = "Extensão: {:.2f}m | Cota Média: +{:.2f}m".format(total_ext, sum(p[1].Z for p in clean_pts)/len(clean_pts)).replace('.', ',')
        p_sub = rg.Point3d(base_x, base_y + (s_data['z_max'] - datum_z) + 1.8 * s, 0.0)
        sub_crvs = make_text_geometry(sub_str, p_sub, 0.75 * s, rg.TextJustification.BottomLeft, s)
        desenho_completo_secoes_2d.extend(sub_crvs)

        # Datum Line
        p_d_ini = rg.Point3d(base_x, base_y, 0.0)
        p_d_fim = rg.Point3d(base_x + total_ext, base_y, 0.0)
        desenho_completo_secoes_2d.append(rg.LineCurve(p_d_ini, p_d_fim))

        # Perfil Natural 2D
        pts_tn_2d = [rg.Point3d(base_x + d, base_y + (pt.Z - datum_z), 0.0) for d, pt in clean_pts]
        crv_tn_2d = rg.PolylineCurve(pts_tn_2d)
        desenho_completo_secoes_2d.append(crv_tn_2d)

        # Polígono de fechamento de solo sob TN
        p_solo = [p_d_ini, p_d_fim] + list(reversed(pts_tn_2d)) + [p_d_ini]
        desenho_completo_secoes_2d.append(rg.Polyline(p_solo).ToPolylineCurve())

        # Greide 2D
        pts_gr_2d = [rg.Point3d(base_x + d, base_y + (get_proj_z(d) - datum_z), 0.0) for d in s_data['estacas_finais']]
        crv_gr_2d = rg.PolylineCurve(pts_gr_2d)
        desenho_completo_secoes_2d.append(crv_gr_2d)

        # Malhas de Corte e Aterro
        quads_corte = []
        quads_aterro = []

        for r_type, d_list in s_data['regioes']:
            for j in range(len(d_list) - 1):
                d1, d2 = d_list[j], d_list[j+1]
                if d2 - d1 <= 1e-6: continue
                p_tn1 = rg.Point3d(base_x + d1, base_y + (interpolate_terrain_z(d1, clean_pts) - datum_z), 0.0)
                p_tn2 = rg.Point3d(base_x + d2, base_y + (interpolate_terrain_z(d2, clean_pts) - datum_z), 0.0)
                p_pr1 = rg.Point3d(base_x + d1, base_y + (get_proj_z(d1) - datum_z), 0.0)
                p_pr2 = rg.Point3d(base_x + d2, base_y + (get_proj_z(d2) - datum_z), 0.0)

                if r_type == "CORTE":
                    quads_corte.append([p_tn1, p_tn2, p_pr2, p_pr1])
                else:
                    quads_aterro.append([p_pr1, p_pr2, p_tn2, p_tn1])

            pts_poly = []
            if r_type == "CORTE":
                for d in d_list: pts_poly.append(rg.Point3d(base_x + d, base_y + (interpolate_terrain_z(d, clean_pts) - datum_z), 0.0))
                for d in reversed(d_list): pts_poly.append(rg.Point3d(base_x + d, base_y + (get_proj_z(d) - datum_z), 0.0))
                pts_poly.append(pts_poly[0])
                poly_c = rg.Polyline(pts_poly).ToPolylineCurve()
                poligonos_corte_all.append(poly_c)
            else:
                for d in d_list: pts_poly.append(rg.Point3d(base_x + d, base_y + (get_proj_z(d) - datum_z), 0.0))
                for d in reversed(d_list): pts_poly.append(rg.Point3d(base_x + d, base_y + (interpolate_terrain_z(d, clean_pts) - datum_z), 0.0))
                pts_poly.append(pts_poly[0])
                poly_a = rg.Polyline(pts_poly).ToPolylineCurve()
                poligonos_aterro_all.append(poly_a)

        m_c = create_colored_mesh(quads_corte, cor_corte)
        m_a = create_colored_mesh(quads_aterro, cor_aterro)
        if m_c: desenho_completo_secoes_2d.append(m_c)
        if m_a: desenho_completo_secoes_2d.append(m_a)

        # Cotas de Nível NBR 6492
        if modo_cotas in [0, 2]:
            for d, pt in clean_pts:
                cota_str = "+{:.2f}".format(pt.Z).replace('.', ',') if pt.Z > 0 else "{:.2f}".format(pt.Z).replace('.', ',')
                m_geoms, _ = draw_nbr_level_marker(base_x + d, base_y + (pt.Z - datum_z), cota_str, s)
                desenho_completo_secoes_2d.extend(m_geoms)

        if modo_cotas in [0, 1]:
            # Marcadores de início e fim do greide
            z_ini = get_proj_z(0.0)
            z_fim = get_proj_z(total_ext)
            m_g_ini, _ = draw_nbr_level_marker(base_x, base_y + (z_ini - datum_z), "GREIDE +{:.2f}".format(z_ini).replace('.', ','), s)
            m_g_fim, _ = draw_nbr_level_marker(base_x + total_ext, base_y + (z_fim - datum_z), "GREIDE +{:.2f}".format(z_fim).replace('.', ','), s)
            desenho_completo_secoes_2d.extend(m_g_ini)
            desenho_completo_secoes_2d.extend(m_g_fim)

            # Pontos de Passagem
            for dp, zp in s_data['pontos_passagem']:
                m_pp, _ = draw_nbr_level_marker(base_x + dp, base_y + (zp - datum_z), "P.P. +{:.2f}".format(zp).replace('.', ','), s)
                desenho_completo_secoes_2d.extend(m_pp)

            # Caixas de Área / Volume da Seção
            # 1. Caixa Superior: Corte
            d_c_all = [d for r_type, d_list in s_data['regioes'] if r_type == "CORTE" for d in d_list]
            if s_data['area_total_corte'] > 0.01 and d_c_all:
                d_c_mid = (min(d_c_all) + max(d_c_all)) / 2.0
                z_c_top = max(interpolate_terrain_z(d, clean_pts) for d in d_c_all)
                y_c_box = base_y + (z_c_top - datum_z) + 4.2 * s
                x_c_box = base_x + d_c_mid

                txt_v1 = "CORTE SEÇÃO {}: {:.2f} m²".format(lbl, s_data['area_total_corte']).replace('.', ',')
                txt_v2 = "Altura Máx: {:.2f}m".format(s_data['max_h_corte']).replace('.', ',')
                c_card, (wc, hc) = make_callout_card(x_c_box, y_c_box, txt_v1, txt_v2, s)
                desenho_completo_secoes_2d.extend(c_card)

                # Linha guia ao topo do relevo
                p_c_box_bot = rg.Point3d(x_c_box, y_c_box - hc / 2.0, 0.0)
                p_crest = rg.Point3d(x_c_box, base_y + (interpolate_terrain_z(d_c_mid, clean_pts) - datum_z), 0.0)
                desenho_completo_secoes_2d.append(rg.LineCurve(p_c_box_bot, p_crest))
                desenho_completo_secoes_2d.append(rg.Circle(p_crest, 0.28 * s).ToNurbsCurve())

            # 2. Caixa Inferior: Aterro
            d_a_all = [d for r_type, d_list in s_data['regioes'] if r_type == "ATERRO" for d in d_list]
            if s_data['area_total_aterro'] > 0.01 and d_a_all:
                d_a_mid = (min(d_a_all) + max(d_a_all)) / 2.0
                y_a_box = base_y - 3.8 * s
                x_a_box = base_x + d_a_mid

                txt_a1 = "ATERRO SEÇÃO {}: {:.2f} m²".format(lbl, s_data['area_total_aterro']).replace('.', ',')
                txt_a2 = "Altura Máx: {:.2f}m".format(s_data['max_h_aterro']).replace('.', ',')
                a_card, (wa, ha) = make_callout_card(x_a_box, y_a_box, txt_a1, txt_a2, s)
                desenho_completo_secoes_2d.extend(a_card)

                p_a_box_top = rg.Point3d(x_a_box, y_a_box + ha / 2.0, 0.0)
                p_datum_conn = rg.Point3d(x_a_box, base_y, 0.0)
                desenho_completo_secoes_2d.append(rg.LineCurve(p_a_box_top, p_datum_conn))
                desenho_completo_secoes_2d.append(rg.Circle(p_datum_conn, 0.28 * s).ToNurbsCurve())

        # Banner de Transferência de Massa entre Seção Atual e a Próxima
        if idx_s < num_secoes - 1:
            lbl_prox = labels_t[idx_s + 1]
            d_t, vc_t, va_t, s_t = vols_trechos[idx_s]
            nota_t = fluxo_transporte[idx_s]

            # Posição intermediária no espaçamento vertical entre as seções
            y_banner = base_y - espacamento_y / 2.0
            x_banner = base_x + total_ext / 2.0
            banner_geoms = make_mass_haul_banner(x_banner, y_banner, lbl, lbl_prox, d_t, vc_t, va_t, s_t, nota_t, s)
            desenho_completo_secoes_2d.extend(banner_geoms)

    # =========================================================================
    # 7. CONSTRUÇÃO DA PLANTA BAIXA TÉCNICA (TOP VIEW: EIXOS, BALÕES E QUADRANTES)
    # =========================================================================
    planta_baixa_geoms = []

    # 1. Eixos Transversais (Seções A, B, C...) em Planta
    for idx_s, crv_c in enumerate(lista_linhas):
        lbl = labels_t[idx_s]
        p_start = crv_c.PointAtStart
        p_end = crv_c.PointAtEnd
        vec_axis = p_end - p_start
        u_axis = rg.Vector3d(vec_axis)
        u_axis.Unitize()

        planta_baixa_geoms.append(crv_c)

        # Balão no início
        p_b_ini = p_start - u_axis * (2.8 * s)
        planta_baixa_geoms.append(rg.LineCurve(p_start, p_b_ini))
        b_ini_geoms = draw_plan_axis_bubble(p_b_ini, u_axis, lbl, s)
        planta_baixa_geoms.extend(b_ini_geoms)

        # Balão no fim
        p_b_fim = p_end + u_axis * (2.8 * s)
        planta_baixa_geoms.append(rg.LineCurve(p_end, p_b_fim))
        b_fim_geoms = draw_plan_axis_bubble(p_b_fim, u_axis, lbl, s)
        planta_baixa_geoms.extend(b_fim_geoms)

    # 2. Cotas de Distância entre Eixos Transversais Consecutivos em Planta
    for idx_s in range(num_secoes - 1):
        crv1 = lista_linhas[idx_s]
        crv2 = lista_linhas[idx_s + 1]
        dist_val = distancias_eixos[idx_s]

        # Ponto médio em ambas as linhas
        t_m1 = crv1.Domain.Min + 0.5 * (crv1.Domain.Max - crv1.Domain.Min)
        t_m2 = crv2.Domain.Min + 0.5 * (crv2.Domain.Max - crv2.Domain.Min)
        p_m1 = crv1.PointAt(t_m1)
        p_m2 = crv2.PointAt(t_m2)

        cota_planta = draw_plan_dimension(p_m1, p_m2, dist_val, s)
        planta_baixa_geoms.extend(cota_planta)

    # 3. Eixos Longitudinais/Verticais (1, 2, 3...) em Planta
    num_verticais = len(lista_verticais)
    labels_v = [str(i + 1) for i in range(num_verticais)]

    for idx_v, crv_v in enumerate(lista_verticais):
        lbl_v = labels_v[idx_v]
        p_start_v = crv_v.PointAtStart
        p_end_v = crv_v.PointAtEnd
        vec_v = p_end_v - p_start_v
        u_v = rg.Vector3d(vec_v)
        u_v.Unitize()

        planta_baixa_geoms.append(crv_v)

        # Balão numérico no início
        p_bv_ini = p_start_v - u_v * (2.8 * s)
        planta_baixa_geoms.append(rg.LineCurve(p_start_v, p_bv_ini))
        bv_ini = draw_plan_axis_bubble(p_bv_ini, None, lbl_v, s)
        planta_baixa_geoms.extend(bv_ini)

        # Balão numérico no fim
        p_bv_fim = p_end_v + u_v * (2.8 * s)
        planta_baixa_geoms.append(rg.LineCurve(p_end_v, p_bv_fim))
        bv_fim = draw_plan_axis_bubble(p_bv_fim, None, lbl_v, s)
        planta_baixa_geoms.extend(bv_fim)

    # 4. Malha de Quadrantes de Terraplenagem em Planta (Interseção Transversais x Verticais)
    if num_secoes >= 2 and num_verticais >= 2:
        grid_pts = [[None for _ in range(num_verticais)] for _ in range(num_secoes)]
        for i, ct in enumerate(lista_linhas):
            for j, cv in enumerate(lista_verticais):
                ev = rg.Intersect.Intersection.CurveCurve(ct, cv, tol * 10, tol * 10)
                if ev and ev.Count > 0:
                    grid_pts[i][j] = ev[0].PointA
                else:
                    rc_t, t_t = ct.ClosestPoint(cv.PointAtNormalizedLength(0.5))
                    rc_v, t_v = cv.ClosestPoint(ct.PointAt(t_t))
                    if rc_t and rc_v:
                        grid_pts[i][j] = ct.PointAt(t_t)

        for i in range(num_secoes - 1):
            for j in range(num_verticais - 1):
                p00 = grid_pts[i][j]
                p01 = grid_pts[i][j+1]
                p11 = grid_pts[i+1][j+1]
                p10 = grid_pts[i+1][j]
                if p00 and p01 and p11 and p10:
                    poly_q = rg.Polyline([p00, p01, p11, p10, p00]).ToPolylineCurve()
                    planta_baixa_geoms.append(poly_q)

                    p_cen = (p00 + p01 + p11 + p10) / 4.0
                    txt_q = "Q.{}-{}".format(labels_t[i], labels_v[j])
                    q_crvs = make_text_geometry(txt_q, p_cen, 0.75 * s, rg.TextJustification.MiddleCenter, s)
                    if q_crvs: planta_baixa_geoms.extend(q_crvs)

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
