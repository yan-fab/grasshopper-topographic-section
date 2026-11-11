# Grasshopper Topographic, Earthwork & Urban Drainage Suite 📐🏔️🚜🌧️

[![Rhino 8](https://img.shields.io/badge/Rhino-8%20%7C%20Grasshopper-0080FF.svg)](https://www.rhino3d.com/)
[![Python](https://img.shields.io/badge/Python-3.9%2B%20%7C%20GhPython-yellow.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Standards: ABNT NBR 6492 / 13133 / 8882](https://img.shields.io/badge/Normas-ABNT%20%7C%20DNIT%20%7C%20GRAPROHAB%20%7C%20PBH-green.svg)](#-calculation-methodology--standards)

Parametric suite for **Rhinoceros 8 / Grasshopper (GhPython and Python 3 Script)** designed for multi-axis topographic section generation, executive earthwork grading, analytical cut & fill volume calculations (AGPTEA / UFPR Average End Area method), progressive mass haul balancing, urban lot slope auditing, official A0 municipal permit sheets, and **automatic stormwater drainage network synthesis** by guide lines over graded terrain in strict compliance with **ABNT NBR 6492**, **NBR 13133**, **NBR 8882**, **Manual GRAPROHAB** (Items 12 & 13), **DAEE-SP**, and the **PBH Drainage Specifications Manual (SUDECAP Cap. 19)**.

---

## 📑 Table of Contents

- [Module Architecture](#-module-architecture)
- [Module 1: Multi-Axis Earthwork & Grading (`corte_terraplenagem_pt.py`)](#-module-1-multi-axis-earthwork--grading)
- [Module 2: Automatic Stormwater Drainage System (`corte_drenagem_pt.py`)](#-module-2-automatic-stormwater-drainage-system)
  - [Guide Line Automatic Drainage Engine](#guide-line-automatic-drainage-engine)
  - [PBH Standard Details (Capítulo 19 - SUDECAP)](#pbh-standard-details-capítulo-19---sudecap)
  - [Dynamic Manning Hydraulics & Excel Export](#dynamic-manning-hydraulics--excel-export)
- [Module 3: Architectural Building Section (`corte_arquitetonico.py`)](#-module-3-architectural-building-section)
- [Official A0 Municipal Permit Sheets (Folhas 01 a 03 & DREN-01)](#-official-a0-municipal-permit-sheets)
- [Component Inputs Reference](#-component-inputs-reference)
- [Component Outputs Reference](#-component-outputs-reference)
- [Automated Rhino Baking & Layer Hierarchy](#-automated-rhino-baking--layer-hierarchy)
- [Normative Standards & Calculation Methodology](#-normative-standards--calculation-methodology)
- [How to Use in Grasshopper](#-how-to-use-in-grasshopper)
- [License](#-license)

---

## 🧭 Module Architecture

The suite provides three specialized, production-ready modules with synchronized Portuguese and English script variants:

| Module | Primary File | Domain | Key Features |
| :--- | :--- | :--- | :--- |
| **Earthwork & Volumes** | [`corte_terraplenagem_pt.py`](corte_terraplenagem_pt.py) / [`corte_topografico_pt.py`](corte_topografico_pt.py) | **Civil & Surveying** | Multi-axis transverse (A–M) & longitudinal (1–5) sections, interactive grading curves with 15% slope clamping, AGPTEA Average End Area volume calculation, mass haul balance, 20m stationing, lot slope auditing (GRAPROHAB Item 12), and complete 3D BIM terrain/road meshes. |
| **Urban Stormwater Drainage** | [`corte_drenagem_pt.py`](corte_drenagem_pt.py) / [`sistema_drenagem_pt.py`](sistema_drenagem_pt.py) | **Hydraulic & Infrastructure** | Automatic drainage network generation by pulling guide lines (`LinhaGuia`) over the graded terrain (`sample_surface_proj_z`), gravity flow inversion, automatic >50m manhole subdivision (Rule 2), Manning hydraulics ($n=0.013$), scaled diameters (DN 400–800mm), paired catch basins with 1.50m gutter depressions, 450m³ detention pond, stepped energy dissipator, and PBH Cap. 19 standard details. |
| **Architectural Section** | [`corte_arquitetonico_pt.py`](corte_arquitetonico_pt.py) / [`corte_arquitetonico.py`](corte_arquitetonico.py) | **Architecture & Urban Design** | Natural terrain intersection, building footprint clipping, cantilever roof/canopies, structural foundations, graded pad, access ramp, NBR 6492 elevation markers, and dimension selector modes. |

---

## 🚜 Module 1: Multi-Axis Earthwork & Grading

### 1. Multi-Axis Dynamic Grading & Slope Clamping
- Evaluates transversal and longitudinal alignments simultaneously.
- Clamps grade curves exceeding $|i| > 15.0\%$ to preserve heavy-machinery drivability and regulatory safety limits.
- Generates 3D color-coded meshes: **Cut (Orange - RGB 235, 120, 30)**, **Fill (Green - RGB 80, 185, 100)**, and **Neutral Line (Cota Zero)**.

### 2. Normative 20m Stationing (DNIT 108/2009-ES / ABNT NBR 13133)
- Strictly enforces 1 station = exactly 20.00 meters (`Estaca 0+00,00`, `Estaca 1+00,00`, `Estaca 2+00,00`...).
- Sub-station metric increments are strictly $< 20.00\,\text{m}$ (e.g., $238.73\,\text{m} = \text{Estaca } 11+18,73$).

### 3. Progressive Mass Haul & Deficit/Borrow-Pit Diagnostics
- Calculates cumulative cut & fill volumes using the **Average End Area Method (AGPTEA / UFPR)**.
- Strictly accounts for soil compaction/shrinkage factor ($F_h = 1.15$) and swell/bulking factor ($K = 1.20$).
- When the net mass balance is negative, reports mandatory importation from a **Licensed External Borrow Pit** (*Jazida de Empréstimo Licenciada*), eliminating contradictory spoil disposal (*bota-fora*) claims.

### 4. Lot Slope Auditing (Manual GRAPROHAB Item 12 & Federal Law 6.766/79)
- Automatically audits all 2D lot boundaries against terrain slope thresholds:
  - **Gentle Slopes ($S \le 15\%$)**: Buildable without restrictions.
  - **Moderate Slopes ($15\% < S \le 30\%$)**: Conventional lot grading with stepped pads.
  - **Critical Slopes ($30\% < S \le 47\%$)**: Special earthwork and geotechnical retaining walls required.
  - **Severe Slopes ($S > 47\% / \approx 25^\circ$)**: Non-buildable zone pursuant to Federal Law 6.766/79 Art. 3.

---

## 🌧️ Module 2: Automatic Stormwater Drainage System

The 3rd variation (`corte_drenagem_pt.py`) receives the newly graded terrain surface and automatically models the complete urban drainage network.

### Guide Line Automatic Drainage Engine
1. **Graded Surface Elevation Sampling (`sample_surface_proj_z`)**:
   - Any 2D or 3D curve connected to `LinhaGuia` projects its vertices onto the finished proposed surface (asphalt, sidewalks, and graded pads), automatically reading exact rim elevations ($Z_T = CT$).
2. **Gravity Flow Auto-Orientation**:
   - If a guide line is drawn backwards against topography, the engine automatically flips it from highest $Z_T$ to lowest $Z_T$, applying a minimum longitudinal slope $S_{\min} = 0.50\%$ ($0.005\,\text{m/m}$).
3. **Automatic Subdivision for Maximum Manhole Spacing (Rule 2)**:
   - Any segment longer than $50.0\,\text{m}$ is automatically subdivided with intermediate manholes (PVs) inserted at $\le 50.0\,\text{m}$ intervals.
4. **Topological Node Clustering & Drop Manholes**:
   - Vertices within a $4.5\,\text{m}$ radius are clustered into single topological junctions (`PV-01`, `PV-02`...).
   - Evaluates elevation drops ($\Delta Z$) and classifies manholes as **Tipo A** ($\Delta Z \le 10\,\text{cm}$), **Tipo B** ($\Delta Z \le 50\,\text{cm}$ with internal ramp), or **Tipo C** ($\Delta Z \le 100\,\text{cm}$ with drop pipe).
5. **Progressive Pipe Sizing & Manning Hydraulics ($n = 0.013$)**:
   - Accumulates upstream catchments and scales commercial reinforced concrete pipes (ABNT NBR 8882):
     - **$\text{DN } 400\,\text{mm}$ (PA-1)**: Starting branch lines / headwaters;
     - **$\text{DN } 500\,\text{mm}$ (PA-1)**: Intermediate collector branches;
     - **$\text{DN } 600\,\text{mm}$ (PA-2)**: Main trunk collectors;
     - **$\text{DN } 800\,\text{mm}$ (PA-2)**: Final outfall emissary pipe.
6. **Paired Catch Basins (Bocas de Lobo) & 1.50m Gutter Depressions**:
   - Places paired catch basins ($0.80 \times 0.40 \times 0.20\,\text{m}$) on both road gutters ($\pm 3.60\,\text{m}$ from road centerline) every $25\text{--}35\,\text{m}$ (reduced to $24\,\text{m}$ where $S > 10\%$) with $\varnothing 200/300\,\text{mm}$ lateral leads.
7. **Detention Basin ($450\,\text{m}^3$, $TR = 25\text{ years}$) & Stepped Energy Dissipator**:
   - Placed automatically at the lowest outfall node, damping peak discharge and limiting exit velocity ($V_{\text{out}} < 1.50\,\text{m/s}$) into environmental buffer streams (APP).

### PBH Standard Details (Capítulo 19 - SUDECAP)
The drawing engine incorporates the technical standards of the **Caderno de Encargos PBH (4ª Edição / Novembro 2022)**:
- **PV Details (Cap. 19.12)**: Types A, B, and C with $\varnothing 80\,\text{cm}$ chimney, galvanized safety ladder every $30\,\text{cm}$, and $\varnothing 600\,\text{mm}$ ductile iron frame/cover (Class D400 - NBR 10160).
- **Catch Basin Details (Cap. 19.8–19.10)**: Type A frame with ductile iron grate, concrete hood, and $1.50\,\text{m}$ gutter transition ramp with $5\,\text{cm}$ depression to prevent roadway water bypass.
- **Trench & Bedding Details (Cap. 19.4)**: Normative trench width $B$ (NBR 17015), 1:3:6 concrete cradle ($120^\circ$ cradle, Table 1 PBH), and $H \ge 1.00\,\text{m}$ minimum cover under roadbeds.
- **Headwall & Wingwalls (Cap. 19.7 - Tabela 7)**: Concrete headwall with $45^\circ$ wingwalls and stepped energy dissipation cascade.

### Dynamic Manning Hydraulics & Excel Export
The drainage calculations generate both interactive text reports and formatted spreadsheets:
- **`Dimensionamento_Drenagem_CABE_VGP.xlsx`**: Professional workbook with 2 sheets (*Dimensionamento Hidráulico* and *Resumo Executivo & Normas*), dynamic Excel formulas (`SUM`, `AVERAGE`, `MAX`), and complete quantity take-offs for trench excavation and concrete bedding.
- **`Dimensionamento_Drenagem_CABE_VGP.xls`**: Native BIFF8 Excel file for legacy compatibility.

---

## 🏛️ Official A0 Municipal Permit Sheets

The suite automatically composes **4 full ISO A0 sheets (1189 x 841 mm)** formatted with official borders, folding marks, title blocks, and legends:

```
+---------------------------------------------------------------------------------------------+
|                                    A0 SHEET ARCHITECTURE                                    |
+---------------------------------------------------------------------------------------------+
|                                                                                             |
|                     UPPER VIEWPORT: TECHNICAL 2D PLAN (SCALE 1:500)                         |
|        - Graded Contours / Topography                                                       |
|        - Roadways, Curbs & Sidewalks                                                        |
|        - Cut (Orange) & Fill (Green) Hatches / Drainage Network                             |
|        - 20m Stationing & Manholes (PV-01 to PV-31)                                         |
|                                                                                             |
+-------------------------------------------------------------------------+-------------------+
|  CARD 1..5: STANDARD TECHNICAL DETAILS                                  | CARIMBO / TITLE   |
|  - PBH Notes / Headwalls / Trenches / Catch Basins / Manholes / Manning | - City Hall Data  |
|  - Sizing & Quantities Tables / Lot Slope Summary Table                 | - Technical Resp. |
+-------------------------------------------------------------------------+-------------------+
```

| Output Name | Sheet Number | Title | Scale | Primary Content |
| :--- | :---: | :--- | :---: | :--- |
| **`Folha01_PlantaGeral`** / `PranchaPlantaGeral` | **FOLHA 01/03** | Planta Geral de Terraplenagem & Grading | 1:500 | Graded contours, cut/fill patches, neutral line, slope hatching, 20m road stationing, and GRAPROHAB Lot Slope Table. |
| **`Folha02_PerfisLongitudinais`** / `PranchaPerfisLongitudinais` | **FOLHA 02/03** | Perfis Longitudinais Viários com Guitarras | H=1:1.000 / V=1:100 | Roadway profiles (Axes 1–5) with 10x vertical exaggeration, natural ground vs. grade curves, parabolic vertical curves (PIVs), and full data guitars. |
| **`Folha03_SecoesTransversais`** / `PranchaSecoesTransversais` | **FOLHA 03/03** | Seções Transversais de Terraplenagem | 1:200 | Transverse cut/fill cross sections (A–M) with offset dimensions, grade elevations, and individual area tables. |
| **`PranchaDrenagem`** / `FolhaDrenagem` | **FOLHA DREN-01/01** | Projeto Executivo de Drenagem Pluvial | 1:500 | Full drainage network plan, 16-column Manning hydraulic sizing table, and the 6 PBH Cap. 19 standard construction details. |

---

## 🎛️ Component Inputs Reference

| Input (Bilingual) | Type | Access | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `Terrain` / `Terreno` | `Curve`/`Mesh` | **List** | *Required* | Natural terrain 3D contour curves or surface mesh. |
| `SectionLines` / `LinhasCorte` | `Curve` | **List** | *Required* | Transverse cut axes (Sections A, B, C...). |
| `LongitudinalLines` / `EixosVerticais` | `Curve` | **List** | `None` | Longitudinal roadway cut axes (Axes 1, 2, 3...). |
| `GradingLine` / `CurvaProjeto` | `Curve` | **List** | `None` | Proposed grade or boundary curves. |
| `Roadway` / `Viario` | `Curve` | **List** | `None` | Closed 2D polylines of road network (pavement + sidewalks). |
| `Lots` / `Lotes` | `Curve` | **List** | `None` | 2D lot boundaries for GRAPROHAB slope analysis. |
| `LinhaGuia` / `LinhaGuiaDrenagem` | `Curve` | **List** | `None` | Drainage collector centerlines drawn over the graded terrain. |
| `CobrimentoMinimo` / `MinCover` | `float` | **Item** | `1.00` | Minimum soil cover over pipe crown ($m$). |
| `EspacamentoBL` / `CatchBasinSpacing` | `float` | **Item** | `30.0` | Maximum spacing between paired catch basins ($m$). |
| `MaxSlope` / `InclinacaoMaxima` | `float` | **Item** | `15.0` | Maximum allowable road/grade slope (%). |
| `BulkingFactor` / `Empolamento` | `float` | **Item** | `1.20` | Soil bulking factor for hauling calculations ($K$). |
| `HomogenizationFactor` / `Fh` | `float` | **Item** | `1.15` | Soil compaction shrinkage factor ($F_h$). |
| `StationInterval` / `PassoEstacas` | `float` | **Item** | `20.0` | Station interval along alignment ($m$). |
| `VerticalExaggeration` / `Exagero` | `float` | **Item** | `10.0` | Vertical scale multiplier for profile guitars. |
| `Scale` / `Escala` | `float` | **Item** | `1.0` | Scale multiplier for text, bubbles, and notes. |
| `Bake` / `GravarRhino` | `bool` | **Item** | `False` | When `True`, automatically bakes all categorized geometry into Rhino layers. |
| `GroupMode` / `ModoGrupo` | `int` | **Item** | `0` | `0`: Hierarchical parent/child groups; `1`: Independent groups. |

---

## 📤 Component Outputs Reference

### Standard Master Outputs
- **`a`**: Complete 3D BIM Model (Proposed terrain mesh + Roadway asphalts/sidewalks + 3D Section slices).
- **`b`** / `PlantaBaixa`: Technical Plan View (Dimensioned axes A–M and 1–5, sight arrows, bubbles, and outer dimensions).
- **`c`** / `DesenhoCompletoSecoes2D`: Complete 2D Aligned Section and Profile drawings.
- **`d`**: Closed 2D Cut polygons for area calculations and CAD hatching.
- **`e`**: Closed 2D Fill polygons for area calculations and CAD hatching.
- **`f`**: Complete Technical Earthwork, Mass Haul & Bruckner Report (`Panel`).

### Specialized 2D Drafting & Layer Outputs
- **`Textos2D`**: Isolated list of all native text entities (`Rhino.Geometry.TextEntity`) for dedicated text layer management (100% CAD editable, zero stroke lines).
- **`Tabelas2D`**: All technical tables and summary cards.
- **`PerfisTopograficos2D`**: Natural ground profiles and proposed grade lines.
- **`EstacasVias2D`** / `EstaqueamentoViario2D`: Normative 20m station labels on roadways.
- **`ManchasCorte2D`** / `ManchasAterro2D`: 2D boundary polygons of cut and fill zones.
- **`HachurasGrading2D`**: 2D vector hatching for cut and fill areas.
- **`LinhaNeutra2D`**: The zero-elevation cut/fill transition curve.
- **`Taludes2D`** / `EspinhasDePeixe2D`: Embankment slope crests, toes, and directional tick lines.
- **`Viario2D`**: Clean 2D roadway outlines (curbs, pavement edges, and sidewalks).
- **`CurvasProjeto`** / `CurvasProjeto1m`: Proposed finished grade contour curves.

### 🔤 Conformidade Normativa de Textos CAD (ABNT NBR 6492 / NBR 8402 / Prefeituras)
- **100% `Rhino.Geometry.TextEntity`**: Todos os textos (carimbos A0, tabelas hidráulicas PBH, cotas, estacas viárias e fichas de seções) são gerados estritamente como entidades de texto nativas CAD. O motor de geração vetorial em traços (*stroke line curves*) foi completamente desativado na saída geométrica.
- **Aprovação Municipal sem Exigências**: Atende à exigência das Prefeituras (como PBH, Cotia e Vargem Grande Paulista) e do GRAPROHAB, onde textos desenhados como polilinhas/linhas explodidas são rejeitados.
- **Exportação DWG/DXF Limpa**: Ao exportar para AutoCAD ou Civil 3D, todos os textos são lidos como entidades editáveis (`TEXT` ou `MTEXT`), permitindo busca (`FIND`), seleção por filtro (`QSELECT`) e ajuste de escala de anotação.
- **Seleção Rápida no Rhino**: Os textos podem ser selecionados instantaneamente via comando `_SelText` e editados pelo painel de propriedades do Rhino.

### Specialized Urban Drainage Outputs
- **`Drenagem3D`**: Full 3D model of pipes, manholes, catch basins, and detention basin.
- **`Drenagem2D`**: Unified 2D drainage network for overlay on the master plan.
- **`Galerias2D`**: Pipe centerlines with flow arrows and normative annotations (`T-XX | DN | L | i%`).
- **`PocosVisita2D`**: Manhole circles with elevation labels ($CT$, $ZF$, and depth $H$).
- **`BocasDeLobo2D`**: Paired catch basins on gutters with lateral connection leads.
- **`BaciaDetencao2D`**: Detention pond boundary and stepped energy dissipator geometry.
- **`PranchaDrenagem`** / `FolhaDrenagem`: Dedicated A0 Sheet (**FOLHA DREN-01/01**).
- **`TabelaManning2D`**: 16-column hydraulic and earthwork sizing table.
- **`MemorialDrenagem`**: Full text report with Manning calculations and PBH/DAEE diagnostics (`Panel`).

---

## 🗂️ Automated Rhino Baking & Layer Hierarchy

When setting `Bake = True`, the suite automatically organizes all elements into structured Rhino layers and groups:

```
PROJETO_LEGAL
├── PRANCHAS
│   ├── MOLDURAS
│   ├── CARIMBO
│   └── TEXTOS
├── SECOES
│   ├── PERFIS
│   ├── TABELAS
│   └── TEXTOS
├── PERFIS_LONGITUDINAIS
│   ├── GEOMETRIA
│   ├── GUITARRA
│   └── TEXTOS
├── LOTES
│   ├── DECLIVIDADE_ATE_30PCT
│   ├── ALERTAS_GRAPROHAB_30PCT
│   ├── ALERTAS_LEI_6766_47PCT
│   ├── SETAS_DRENAGEM
│   └── TABELA_DECLIVIDADES
└── DRENAGEM
    ├── GALERIAS_2D / GALERIAS_3D
    ├── PVS_2D / PVS_3D
    ├── BOCAS_LOBO_2D / BOCAS_LOBO_3D
    ├── SETAS_FLUXO
    ├── BACIA_DETENCAO_2D / BACIA_DETENCAO_3D
    └── TEXTOS_2D
```

---

## 📚 Normative Standards & Calculation Methodology

1. **ABNT NBR 6492**: Representation of Architecture Projects (Line conventions, symbols, cuts, and elevation notation).
2. **ABNT NBR 13133 / DNIT 108/2009-ES**: Topographic surveys and roadway stationing ($20.00\,\text{m}$ integer intervals).
3. **AGPTEA / UFPR**: *Cálculo de Volumes – Método das Seções Transversais e Balanço de Massas* (Prof. Luís Augusto Koenig Veiga).
4. **Manual GRAPROHAB (Governo de SP)**:
   - **Item 12**: Diretrizes para Projetos de Terraplenagem e Declividade de Lotes.
   - **Item 13**: Diretrizes para Projetos de Drenagem de Águas Pluviais.
5. **DAEE-SP (Departamento de Águas e Energia Elétrica)**: Tempos de retorno normativos ($TR = 10\text{ anos}$ para microdrenagem / $TR = 25\text{ anos}$ para bacias de detenção) e velocidade de deságue controlada ($V < 1.50\,\text{m/s}$).
6. **Prefeitura Municipal de Belo Horizonte (PBH / SUDECAP)**: *Caderno de Encargos – Capítulo 19: Drenagem* (4ª Edição / Novembro 2022).
7. **ABNT NBR 8882 & NBR 15645**: Tubos de concreto armado para águas pluviais (Classes PA-1 a PA-4 e juntas elásticas).
8. **ABNT NBR 10160**: Tampões e grelhas de ferro fundido dúctil (Classe D400 — 40 toneladas).
9. **ABNT NBR 17015**: Diretrizes para dimensionamento de valas e assentamento de tubulações.

---

## 🚀 How to Use in Grasshopper

1. Open **Rhinoceros 8** and launch **Grasshopper**.
2. Add a **GhPython Script** (or **Python 3 Script**) component to your canvas.
3. Choose the appropriate script for your workflow:
   - For complete grading and earthwork: [`corte_terraplenagem_pt.py`](corte_terraplenagem_pt.py)
   - For stormwater drainage network: [`corte_drenagem_pt.py`](corte_drenagem_pt.py)
4. Configure component inputs:
   - `Terrain` (`Terreno`): Right-click -> **List Access** -> **Type Hint: GeometryBase**.
   - `SectionLines` (`LinhasCorte`): Right-click -> **List Access** -> **Type Hint: Curve**.
   - `LinhaGuia`: Right-click -> **List Access** -> **Type Hint: Curve**.
5. Connect your project curves and preview the real-time 3D models and 2D A0 sheets.
6. Connect a **Panel** to `MemorialDrenagem` or `f` to verify structural calculations.
7. To bake everything into organized Rhino layers, toggle `Bake = True`.

---

## 📜 License

Distributed under the [MIT](LICENSE) License. Developed by **Yan Fabio**.
