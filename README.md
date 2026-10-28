# Grasshopper Topographic & Earthwork Suite (NBR 6492 / AGPTEA) 📐🏔️🚜

[![Release](https://img.shields.io/badge/release-v3.2.0-brightgreen.svg)](https://github.com/yan-fab/grasshopper-topographic-section/releases/tag/v3.2.0)
[![Rhino 8](https://img.shields.io/badge/Rhino-8%20%7C%20Grasshopper-0080FF.svg)](https://www.rhino3d.com/)
[![Python](https://img.shields.io/badge/Python-3.9%2B%20%7C%20GhPython-yellow.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Professional parametric suite for **Rhinoceros 8 / Grasshopper (GhPython and Python 3 Script)** designed for topographic section generation, multi-axis executive earthwork grading, analytical cut & fill volume calculations, progressive mass haul balancing, and 3D terrain surface modeling in strict compliance with **ABNT NBR 6492** (Architectural Project Representation) and the classical **AGPTEA / UFPR Average End Area method**.

---

## 📑 Table of Contents

- [Module Overview](#-module-overview)
- [What's New in v3.1.0 & v3.0.0](#-whats-new-in-v310--v300)
- [Earthwork & Volumes Module (`corte_terraplenagem.py`)](#-earthwork--volumes-module-corteterraplenagempy)
  - [Bilingual Inputs](#inputs---earthwork-module)
  - [Outputs](#outputs---earthwork-module)
  - [The 15% Maximum Slope Rule](#-the-15-maximum-slope-rule)
  - [Mass Haul & Longitudinal Compensation](#-mass-haul--longitudinal-compensation)
  - [Complete 3D Earthwork Model](#-complete-3d-earthwork-model)
- [Architectural Section Module (`corte_arquitetonico.py`)](#-architectural-section-module-cortearquitetonicopy)
- [How to Use in Grasshopper](#-how-to-use-in-grasshopper)
- [Calculation Methodology & Standards](#-calculation-methodology--standards)
- [License](#-license)

---

## 🧭 Module Overview

The suite provides two specialized, production-ready modules:

| Module | Primary Script | Domain | Key Features |
| :---: | :--- | :--- | :--- |
| **Multi-Axis Earthwork & 3D Model** | [`corte_terraplenagem.py`](corte_terraplenagem.py) | **Civil Engineering & Surveying** | Multi-axis transverse (A, B, C...) and longitudinal (1, 2, 3...) sections, interactive grading curves with 15% slope ceiling, AGPTEA Average End Area volume calculation, internal mass haul compensation, dimensioned technical plan view, and full 3D color-coded earthwork mesh. |
| **Architectural Building Section** | [`corte_arquitetonico.py`](corte_arquitetonico.py) | **Architecture & Urban Design** | Natural terrain intersection, building footprint clipping, cantilever roof/canopies, structural foundations, graded pad, access ramp, NBR 6492 elevation markers, and dimension selector modes. |

---

## 🌟 What's New in v3.1.0 & v3.0.0

### Version 3.2.0
- **CAD Road Network & Drivable Street Engine (`Roadway` / `Viario`)**:
  - Direct integration of closed 2D CAD road polygons (curbs, roadway, sidewalks, and cul-de-sacs).
  - **Normative Drivability (DNIT / NBR)**: Enforces transversal leveling, 2.0% drainage crown cross-slope, 15cm curb step separation, and longitudinal grade limit ($i \le 15.0\%$).
  - **BIM 3D Pavement Meshes**: Generates dark charcoal asphalt roadway (`RGB 55, 55, 60`) and light concrete sidewalk (`RGB 200, 200, 205`) meshes on the proposed 3D terrain surface with 3D curb relief.
  - **2D Section Road Corridors**: Automatically identifies road crossings on cross/longitudinal sections, rendering road boundaries, crowned pavement, curb steps, callout badges, and NBR centerline level markers.
  - **Road Earthwork Quantities**: Discriminates road network pavement/sidewalk footprint areas in the AGPTEA calculation report.

### Version 3.1.1 (Hotfix)
- **Resolved TypeError in Stroke Vector Typography**: Fixed signature argument order in `draw_plan_axis_bubble` where direction vector and label arguments were inverted, preventing `TypeError: 'in <string>' requires string as left operand, not float`.
- **String Coercion & Dimension Hardening**: Enforced robust type-checking and string coercion across vector stroke text rendering and dimension formatting.

### Version 3.1.0
- **Full Internationalization (English)**: All source code, docstrings, technical drawing callouts, banners, and calculation reports translated into English.
- **Dual-Language Parameter Aliasing**: All Grasshopper inputs accept both **English** (`Terrain`, `SectionLines`, `GradingLine`, `BulkingFactor`, `MaxSlope`) and **Português** (`Terreno`, `LinhasCorte`, `CurvaProjeto`, `Empolamento`, `InclinacaoMaxima`), guaranteeing 100% backwards compatibility with existing `.gh` definitions.
- **Crash-Proof Stroke Vector Font Engine**: Completely autonomous Python vector typography engine replacing native Rhino text explosion routines, ensuring rock-solid stability in Rhino 8 on .NET Core without any external dependencies.

### Version 3.0.0
1. **Aligned Multi-Axis Transverse & Longitudinal System (NBR 6492)**:
   - Normative axis ordering: **top-to-bottom** (A, B, C... Z, AA...) and **left-to-right** (1, 2, 3... N).
   - 2D section drawings organized in **two parallel columns**:
     - **Column 1**: Cross Sections ($A - A$, $B - B$, $C - C$...).
     - **Column 2**: Longitudinal Profiles ($1 - 1$, $2 - 2$, $3 - 3$...).
   - Automatic cross-axis intersections with NBR bubble tags, elevation nodes, and alignment dimensions.
2. **Strict Terrain Boundary Truncation**:
   - Profiles strictly terminate at the true boundaries of contour lines / terrain mesh, eliminating artificial flat extensions.
3. **Technical Plan View with Quadrant Grid**:
   - Automatic dimensioned axes in plan view with NBR 6492 circular bubbles and sight arrows.
   - Quadrant centroid badges ($A1, A2, B1, B2...$) and exterior cumulative/partial dimension lines.
4. **Interactive Grade & 15% Maximum Slope Rule**:
   - Automatic recognition of project boundary curves drawn in Rhino (2D Top view or 3D).
   - Intelligent proximity snapping to corresponding section profiles.
   - Enforces a 15% maximum slope limit ($i \le 0.15$), clamping excessive slopes while preserving grade elevation.
5. **Internal Compensation & Progressive Mass Haul Balancing**:
   - Red arrows visualising intra-section mass compensation (cut supplying adjacent fill).
   - Inter-section mass haul transfer banners detailing station distance ($D$), cut volume ($V_c$), fill volume ($V_a$), net balance, and hauling destination (spoil disposal vs borrow pit import).
6. **Complete 3D Earthwork Model**:
   - Color-coded proposed terrain mesh:
     - **Orange** (`RGB 245, 130, 32`): Cut zones (Excavation).
     - **Green** (`RGB 46, 204, 113`): Fill zones (Embankment).
     - **Light Gray** (`RGB 205, 210, 205`): Neutral transition areas.
   - Real-world 3D vertical section slices positioned directly at world/UTM coordinates.

---

## 🚜 Earthwork & Volumes Module (`corte_terraplenagem.py`)

Designed for feasibility studies, executive subdivision earthwork grading, and precise contractor cubic volume accounting.

### Inputs - Earthwork Module:

| Parameter (Bilingual) | Type Hint | Access | Default | Description |
| :--- | :--- | :---: | :---: | :--- |
| `Terrain` / `Terreno` | `Curve` / `Mesh` | **List** | *Required* | 3D contour curves or topographic terrain mesh. |
| `SectionLines` / `LinhasCorte` | `Curve` | **List / Item** | *Required* | Primary cross-sectional cut lines (Sections A, B, C...). |
| `LongitudinalLines` / `EixosVerticais` | `Curve` | **List / Item** | `None` | Longitudinal cut axes (1, 2, 3...) for multi-axis 3D analysis. |
| `GradingLine` / `CurvaProjeto` / `BoundaryLine` | `Curve` | **List / Item** | `None` | Proposed grade curve(s) drawn directly in Rhino (2D or 3D). |
| `Roadway` / `Viario` | `Curve` | **List / Item** | `None` | Closed 2D CAD road network polygon(s) (calçada + pista + cul-de-sacs). |
| `MaxSlope` / `InclinacaoMaxima` | `float` | **Item** | `15.0` | Maximum allowable slope for grading lines (default: 15% = 0.15). |
| `ProjectElevation` / `NivelProjeto` | `float` / `list` | **Item / List** | `None` | Finished grade elevation per section or quadrant. |
| `Point` / `Ponto` | `Point3d` | **Item** | `(0, 0, 0)` | Base insertion point for 2D section drawings in Top View. |
| `Spacing` / `Espacamento` | `float` | **Item** | `Auto` | Uniform vertical spacing between 2D section drawings. |
| `Width` / `Largura` | `float` | **Item** | `1.0` | Influence width for single isolated section volume calculation ($m$). |
| `BulkingFactor` / `Empolamento` | `float` | **Item** | `1.20` | Soil bulking/swell factor for hauling volume (1.20 = 20% expansion). |
| `Selector` / `Seletor` | `int` | **Item** | `1` | `1`: Proposed Earthwork, `2`: Natural Terrain Only, `0`: Full with all dimensions. |
| `Scale` / `Escala` | `float` | **Item** | `1.0` | Scale multiplier for NBR symbols, text annotations, and bubbles. |

### Outputs - Earthwork Module:

| Output | Technical Name | Type | Description |
| :---: | :--- | :---: | :--- |
| **`a`** | `Complete3DModel` | `List[Geometry]` | **Complete 3D Earthwork Model**: Proposed terrain surface with color-coded meshes (Orange/Green/Neutral), 3D vertical section slices, and 3D grade/ground curves. |
| **`b`** | `PlanView` | `List[Geometry]` | **Technical Plan View**: Dimensioned axes A, B, C... and 1, 2, 3... with NBR circular bubbles, sight arrows, outer cumulative dimension chains, and quadrant labels (A1, A2...). |
| **`c`** | `SectionDrawings` | `List[Geometry]` | **Complete 2D Section Drawings**: Column 1 (Cross Sections) and Column 2 (Longitudinal Profiles) with Orange/Green hatch meshes, proposed grade, NBR level markers, cross-axis extension lines, and mass haul banners. |
| **`d`** | `CutPolygons` | `List[Curve]` | **2D Cut Polygons**: Clean closed curves for each cut area (for Grasshopper `Area`, `Hatch`, or baking into CAD layers). |
| **`e`** | `FillPolygons` | `List[Curve]` | **2D Fill Polygons**: Clean closed curves for each fill area (for Grasshopper `Area`, `Hatch`, or baking into CAD layers). |
| **`f`** | `Report` | `str` | **AGPTEA Earthwork Calculation Report**: Formatted analytical text report for `Panel` connection, summarizing station areas, partial and total volumes, global mass balance, and hauling diagnostics. |

---

### 🛣️ CAD Road Network & Drivable Street Standards (Viário Carroçável)

When integrating an executive 2D CAD road network (`Roadway` / `Viario`):

- **Closed Polygon Domain**: The algorithm detects closed road polylines (pavement, sidewalks, cul-de-sacs, and turnarounds), dividing the terrain into road corridors and residential/commercial lot areas.
- **Normative Drivability Standards (DNIT / NBR)**:
  1. **Transversal Leveling**: Overcomes hillside cross-tilting by establishing a leveled road platform.
  2. **2.0% Drainage Crown**: Pavement slopes down 2.0% from the centerline to gutters, preventing water ponding.
  3. **15cm Curb Step**: Standard $+0.15\,\text{m}$ curb separates the asphalt roadway from pedestrian sidewalks.
  4. **Longitudinal Slope ($\le 15\%$)**: Road grades strictly respect maximum slope limits with smooth vertical curvature.
- **BIM 3D Pavement**: Renders asphalt (`RGB 55, 55, 60`) and sidewalk (`RGB 200, 200, 205`) meshes on the proposed 3D surface with 3D curb relief.

---

### 📐 The 15% Maximum Slope Rule

In civil earthwork, road design, and lot grading, slopes exceeding 15% hinder heavy equipment operation and standard vehicular circulation:

- The algorithm calculates the effective slope of each grading segment:
  $$i = \frac{\Delta Z}{L}$$
- If the proposed boundary line exceeds $|i| > 15\%$, the grade curve is clamped to the **15.0%** threshold while retaining the base elevation point.
- The constraint status is explicitly labeled on the technical drawing:
  - `GRADE: i = +12.3% (RULE <= 15% OK)`
  - `GRADE: i = +15.0% [CLAMPED TO 15.0% MAX]`

---

### ⚖️ Mass Haul & Longitudinal Compensation

Between consecutive cross sections ($A - A$ and $B - B$), volumes are calculated using AGPTEA's Average End Area formulation:

$$V = \left(\frac{A_1 + A_2}{2}\right) \cdot D$$

- **Progressive Mass Haul**: Evaluates whether excavated soil from station $i$ satisfies the embankment requirement of station $i+1$.
- **Surplus**: When cumulative balance is positive, transfer banners indicate excess material hauled to the next section or to a **licensed spoil disposal site**.
- **Deficit**: When cumulative balance is negative, transfer banners specify the volume required from a **borrow pit**.

---

### 🧊 Complete 3D Earthwork Model

Viewing output **`a`** in Rhino's 3D Perspective viewport:
- The color-coded terrain surface dynamically reflects cut (orange), fill (green), and grade transitions.
- Evaluates visual and environmental impacts before ground-breaking.
- 3D vertical section slices provide direct spatial verification of elevation offsets.

---

## 🏗️ Architectural Section Module (`corte_arquitetonico.py`)

Designed for architectural presentation of residential or commercial buildings integrated with site topography:

- **Longitudinal Section**: Building walls, continuous foundation trenches, ground floor slab, cantilever roof/canopy, and access ramp embankment.
- **Cross Section**: Continuous graded pad, retaining slope/walls, and terrain profile.
- **NBR 6492 Level Notation**: Standard triangular level markers with sign prefixes (`+` / `-`).
- **Selector Modes**:
  - `Mode 0`: All dimensions & elevations (Natural Terrain + Proposed Project).
  - `Mode 1`: Proposed project elevations only (+ Natural Ground Profile) [Default].
  - `Mode 2`: Natural terrain elevations only.

---

## 🚀 How to Use in Grasshopper

1. Open **Rhinoceros 8** and launch **Grasshopper**.
2. Add a **Python 3 Script** (or **GhPython Script**) component to the canvas.
3. Double-click the component and paste the contents of [`corte_terraplenagem.py`](corte_terraplenagem.py) (or [`corte_arquitetonico.py`](corte_arquitetonico.py)).
4. Configure component inputs:
   - `Terrain` (or `Terreno`): Right-click -> **List Access** -> **Type Hint: GeometryBase** (or `Curve`).
   - `SectionLines` (or `LinhasCorte`): Right-click -> **List Access** -> **Type Hint: Curve**.
   - Other inputs set to **Item Access**.
5. Connect your Rhino geometry to the inputs.
6. Connect a **Panel** component to output **`f`** to inspect the calculation report.
7. **Interactive Grade Drawing**:
   - Draw a `Line` or `Polyline` directly over the 2D section in the Top viewport (or in 3D).
   - Connect it to `GradingLine` (or `CurvaProjeto`). Earthwork volumes and 3D meshes update in real time.

---

## 📚 Calculation Methodology & Standards

Earthwork formulas and architectural graphic representations follow recognized civil engineering and surveying standards:

- **ABNT NBR 6492**: Architectural Project Documentation (lines, conventions, coordinate axes, and elevation levels).
- **AGPTEA / UFPR**: *Topografia: Cálculo de Volumes (Notas de Aula)* — Prof. Luís Augusto Koenig Veiga.
  - [Download AGPTEA Technical Handout (PDF)](https://www.bibliotecaagptea.org.br/agricultura/topografia/livros/TOPOGRAFIA%20CALCULO%20DE%20VOLUMES%20NOTAS%20DE%20AULA.pdf)

---

## 📜 License

Distributed under the [MIT](LICENSE) License. Developed by **Yan Fabio**.
