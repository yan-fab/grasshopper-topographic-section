# Grasshopper Topographic & Earthwork Suite (NBR 6492 / AGPTEA) 📐🏔️🚜

[![Release](https://img.shields.io/badge/release-v3.0.0-brightgreen.svg)](https://github.com/yan-fab/grasshopper-topographic-section/releases/tag/v3.0.0)
[![Rhino 8](https://img.shields.io/badge/Rhino-8%20%7C%20Grasshopper-0080FF.svg)](https://www.rhino3d.com/)
[![Python](https://img.shields.io/badge/Python-3.9%2B%20%7C%20GhPython-yellow.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Suíte paramétrica profissional para **Rhinoceros 8 / Grasshopper (GhPython e Python 3 Script)** destinada ao desenvolvimento de cortes topográficos, projetos executivos de terraplenagem multi-eixos, cálculo analítico de volumes de corte/aterro e geração de superfícies 3D em conformidade rigorosa com a **ABNT NBR 6492** (Representação de Projetos de Arquitetura) e o método clássico de cubação **AGPTEA / UFPR**.

---

## 📑 Sumário

- [Visão Geral dos Módulos](#-visão-geral-dos-módulos)
- [Novidades da Versão 3.0.0](#-novidades-da-versão-300-v300)
- [Módulo de Terraplenagem & Volumes (`corte_terraplenagem.py`)](#-módulo-de-terraplenagem--volumes-corteterraplenagempy)
  - [Entradas (Inputs)](#entradas-inputs---terraplenagem)
  - [Saídas (Outputs)](#saídas-outputs---terraplenagem)
  - [Regra dos 15% para a Linha Delimitadora](#-regra-dos-15-para-a-linha-delimitadora)
  - [Balanço de Massas e Diagrama de Transporte (*Mass Haul*)](#-balanço-de-massas-e-diagrama-de-transporte-mass-haul)
  - [Modelo 3D de Terraplenagem](#-modelo-3d-de-terraplenagem)
- [Módulo Arquitetônico (`corte_arquitetonico.py`)](#-módulo-arquitetônico-cortearquitetonicopy)
- [Como Utilizar no Grasshopper](#-como-utilizar-no-grasshopper)
- [Metodologia Técnica de Cálculo](#-metodologia-técnica-de-cálculo)
- [Licença](#-licença)

---

## 🧭 Visão Geral dos Módulos

O repositório fornece duas ferramentas especializadas independentes:

| Módulo | Arquivo Principal | Finalidade | Principais Destaques |
| :---: | :--- | :--- | :--- |
| **Terraplenagem Multi-Eixos & Modelo 3D** | [`corte_terraplenagem.py`](corte_terraplenagem.py) | **Engenharia & Topografia** | Multi-eixos transversais (A, B, C...) e longitudinais (1, 2, 3...), greides interativos com regra de 15% máx, cálculo de áreas e cubação prismoidal (AGPTEA), compensação interna, banners de transporte, planta técnica cotada e modelo 3D colorido. |
| **Implantação Arquitetônica** | [`corte_arquitetonico.py`](corte_arquitetonico.py) | **Arquitetura & Urbanismo** | Inserção de residência no relevo, lajes de piso e cobertura em balanço, fundações adaptadas, platô nivelado, rampa de acesso, cotas de nível NBR e linha do perfil natural. |

---

## 🌟 Novidades da Versão 3.0.0 (v3.0.0)

A versão **3.0.0** consolida um avanço estrutural e operacional na suíte, transformando o script em uma solução completa de terraplenagem para loteamentos, platôs e obras de contenção:

1. **Sistema Multi-Eixos Transversais e Longitudinais Alinhados (NBR 6492)**:
   - Ordenação dos eixos normativos: **de cima para baixo** (A, B, C... Z, AA...) e **da esquerda para a direita** (1, 2, 3... N).
   - Desenho 2D organizado em **duas colunas paralelas**:
     - **Coluna 1**: Seções Transversais ($A - A$, $B - B$, $C - C$...).
     - **Coluna 2**: Seções Longitudinais ($1 - 1$, $2 - 2$, $3 - 3$...).
   - Intersecções espaciais automatizadas: identificação de eixos transversais cruzando seções longitudinais (e vice-versa), com balões de chamada NBR, cotas Z do terreno e greide e nós de cruzamento.

2. **Delimitação Estrita pelo Relevo**:
   - Os perfis são limitados rigorosamente até o término das curvas de nível/relevo, eliminando pontas artificiais ou extensões planas fictícias fora do terreno.

3. **Planta Baixa Técnica com Grade de Quadrantes**:
   - Identificação automática dos eixos ordenados em planta com balões NBR 6492 e setas indicativas do sentido de visada.
   - Cálculo automático dos centroides dos quadrantes ($A1, A2, B1, B2...$) com insígnias técnicas.
   - Cadeia de cotas acumuladas e parciais ao longo de linha de alinhamento perpendicular aos eixos.

4. **Greide Interativo e Regra dos 15% de Inclinação Máxima**:
   - Reconhecimento automático de linhas delimitadoras desenhadas no Rhino (`CurvaProjeto` / `LinhaDelimitadora`), tanto sobre as seções 2D na vista Top quanto no relevo 3D.
   - *Snapping* inteligente por proximidade para curvas desenhadas soltas sobre a área da seção.
   - **Regra dos 15%**: Verificação automática da rampa máxima. Se a inclinação da linha delimitadora exceder 15%, o greide é automaticamente limitado a 15,0% e destacado visualmente no desenho técnico e no memorial.

5. **Compensação Interna e Balanço Progressivo (*Mass Haul*)**:
   - Seta vermelha indicativa de compensação interna entre trecho de corte e trecho de aterro adjacente na mesma seção.
   - Banners técnicos automáticos entre seções consecutivas informando: distância entre eixos ($D$), volume de corte ($V_c$), volume de aterro ($V_a$), saldo do trecho e destino das massas (sobra para bota-fora vs déficit para empréstimo).

6. **Modelo 3D Completo de Terraplenagem**:
   - Superfície 3D do terreno modificado com coloração técnica:
     - **Laranja** (`RGB 245, 130, 32`): Zonas de **Corte**.
     - **Verde** (`RGB 46, 204, 113`): Zonas de **Aterro**.
     - **Cinza Claro** (`RGB 205, 210, 205`): Zonas Neutras / Passagem.
   - Fatias verticais 3D dos perfis diretamente na posição UTM/mundo do relevo.
   - Linhas e greides 3D sobre o terreno.

7. **Estabilidade Absoluta no Rhino 8 (.NET Core 8)**:
   - Sanitização de topologia de malhas (`rg.Mesh`), eliminando faces degeneradas de espessura nula nos pontos de passagem ($Z_{\text{TN}} = Z_{\text{PR}}$).
   - Decomposição triangular limpa, filtragem de vértices duplicados e validação estrita de polilinhas (`IsValid`), prevenindo falhas de acesso de memória nativa (`coreclr.dll`).

---

## 🚜 Módulo de Terraplenagem & Volumes (`corte_terraplenagem.py`)

Projetado para estudos de viabilidade, projetos executivos de terraplenagem e quantificação de terra.

### Entradas (Inputs) - Terraplenagem:

| Parâmetro | Type Hint | Acesso | Padrão | Descrição |
| :--- | :--- | :---: | :---: | :--- |
| `Terreno` | `Curve` / `Mesh` | **List** | *Obrigatório* | Curvas de nível 3D ou malha topográfica do relevo. |
| `LinhasCorte` *(ou `LinhaCorte`)* | `Curve` | **List / Item** | *Obrigatório* | Linhas de corte principais transversais (A, B, C...). |
| `LinhasLongitudinais` *(ou `EixosV`)* | `Curve` | **List / Item** | `None` | Eixos longitudinais de corte (1, 2, 3...) para análise tridimensional. |
| `CurvaProjeto` *(ou `LinhaDelimitadora`)* | `Curve` | **List / Item** | `None` | Linha(s) do greide desenhada(s) no Rhino (2D na seção ou 3D no terreno). |
| `Ponto` | `Point3d` | **Item** | `(0, 0, 0)` | Origem de inserção das seções 2D no plano Top. |
| `FatorEmpolamento` *(ou `Empolamento`)* | `float` | **Item** | `1.20` | Fator de expansão volumétrica do solo para transporte (1,20 = 20%). |
| `LarguraFaixa` *(ou `Largura`)* | `float` | **Item** | `1.0` | Largura de influência para cubação de seção única isolada ($m$). |
| `InclinacaoMaxima` | `float` | **Item** | `0.15` | Inclinação máxima permitida para o greide (padrão: 15% = 0,15). |
| `ModoVisualizacao` *(ou `Seletor`)* | `int` | **Item** | `1` | `1`: Terraplenagem completa, `2`: Apenas TN, `0`: Ambos com cotas. |
| `Escala` | `float` | **Item** | `1.0` | Escala técnica para símbolos, balões e textos NBR. |

### Saídas (Outputs) - Terraplenagem:

| Saída | Nome Técnico | Tipo | Descrição |
| :---: | :--- | :---: | :--- |
| **`a`** | `Modelo3D` | `List[Geometry]` | **Modelo 3D Completo**: Superfície projetada com malhas coloridas (Laranja/Verde/Neutro), fatias 3D das seções e curvas 3D de greide/terreno. |
| **`b`** | `PlantaBaixa` | `List[Geometry]` | **Planta Baixa Técnica**: Eixos cotados A, B, C... e 1, 2, 3... com balões circulares NBR, setas de visada, linha de cota exterior e quadrantes A1, A2... |
| **`c`** | `DesenhoSecoes` | `List[Geometry]` | **Desenho Completo das Seções 2D**: Coluna 1 (Seções Transversais) e Coluna 2 (Seções Longitudinais) com hachuras Laranja/Verde, greide, cotas NBR, eixos cruzados e banners de fluxo de massa. |
| **`d`** | `PoligonosCorte` | `List[Curve]` | **Polígonos 2D de CORTE**: Curvas fechadas e limpas para cálculo de `Area`, aplicação de `Hatch` ou envio para layers CAD. |
| **`e`** | `PoligonosAterro` | `List[Curve]` | **Polígonos 2D de ATERRO**: Curvas fechadas e limpas para cálculo de `Area`, aplicação de `Hatch` ou envio para layers CAD. |
| **`f`** | `MemorialTecnico` | `str` | **Memorial Técnico AGPTEA**: Quadro analítico em texto para conexão em `Panel`, contendo volumes parciais e totais, balanço global e diagnóstico operacional (Bota-fora / Empréstimo). |

---

### 📐 Regra dos 15% para a Linha Delimitadora

Em projetos de terraplenagem e arruamento, inclinações superiores a 15% inviabilizam o tráfego regular de máquinas e veículos pesados:

- O algoritmo analisa a declividade efetiva $i = \frac{\Delta Z}{L}$ de cada segmento da linha delimitadora.
- Se a linha desenhada pelo projetista apresentar inclinação $|i| > 15\%$, ela é suavemente ajustada ao teto de **15,0%**, mantendo o ponto inicial e recalculando a altura máxima.
- A restrição é explicitada diretamente no desenho da seção:
  - `GREIDE: i = +12.3% (REGRA <= 15% OK)`
  - `GREIDE: i = +15.0% [LIMITADO A 15,0% MÁX]`

---

### ⚖️ Balanço de Massas e Diagrama de Transporte (*Mass Haul*)

Entre duas seções sucessivas (ex: $A - A$ e $B - B$), o algoritmo calcula o volume prismoidal:

$$V_{trecho} = \left(\frac{A_1 + A_2}{2}\right) \cdot D$$

- O saldo progressivo indica se o material escavado é suficiente para suprir os aterros das estacas seguintes.
- Quando o saldo acumulado for positivo, o banner técnico indica a sobra a ser transferida ou destinada a **bota-fora**.
- Quando o saldo for negativo, o banner aponta o déficit a ser suprido por **área de empréstimo (jazida)**.

---

### 🧊 Modelo 3D de Terraplenagem

Ao visualizar o modelo na perspectiva 3D do Rhino:
- A saída **`a`** projeta a nova topografia resultante diretamente sobre o relevo original.
- Permite analisar o impacto visual dos cortes e aterros antes de enviar para execução no canteiro de obras.
- As fatias verticais 3D cortam o relevo ao longo de cada eixo, proporcionando uma leitura intuitiva do desnível.

---

## 🏗️ Módulo Arquitetônico (`corte_arquitetonico.py`)

Projetado para apresentar a inserção da edificação no terreno com desenho arquitetônico completo:

- **Corte Longitudinal**: Paredes em corte, fundações contínuas, laje de piso, beiral curvo e rampa de acesso em aterro.
- **Corte Transversal**: Platô contínuo, nivelado e protegido por muros de contenção nas extremidades.
- **Simbologia NBR 6492**: Símbolos triangulares de nível preenchidos, linhas de chamada e textos vetoriais com indicação de sinal (+ / -).

---

## 🚀 Como Utilizar no Grasshopper

1. Abra o **Rhinoceros 8** e inicie o **Grasshopper**.
2. Adicione na tela um componente **Python 3 Script** (ou **GhPython Script**).
3. Abra o editor de código (duplo clique) e cole o código de [`corte_terraplenagem.py`](corte_terraplenagem.py) (ou [`corte_arquitetonico.py`](corte_arquitetonico.py)).
4. Configure as entradas no componente do Grasshopper:
   - `Terreno`: clique com o botão direito -> **List Access** -> **Type Hint: GeometryBase** (ou Curve).
   - `LinhasCorte`: clique com o botão direito -> **List Access** -> **Type Hint: Curve**.
   - Demais entradas em **Item Access**.
5. Conecte as curvas do Rhino nas entradas.
6. Conecte um componente **Panel** na saída **`f`** para visualizar o relatório de volumes.
7. Para desenhar o greide livremente:
   - Desenhe uma `Line` ou `Polyline` diretamente sobre a seção 2D desenhada na vista Top (ou no relevo 3D).
   - Conecte essa curva na entrada `CurvaProjeto` (ou `LinhaDelimitadora`). A terraplenagem e os volumes serão recalculados em tempo real.

---

## 📚 Metodologia Técnica de Cálculo

As formulações de cálculo de áreas e cubação de terraplenagem implementadas seguem as referências consagradas da literatura técnica de engenharia:

- **ABNT NBR 6492**: Representação de projetos de arquitetura (linhas, convenções, eixos e níveis).
- **AGPTEA / UFPR**: *Topografia: Cálculo de Volumes (Notas de Aula)* — Prof. Luís Augusto Koenig Veiga.
  - [Download da Apostila Técnica da AGPTEA](https://www.bibliotecaagptea.org.br/agricultura/topografia/livros/TOPOGRAFIA%20CALCULO%20DE%20VOLUMES%20NOTAS%20DE%20AULA.pdf)

---

## 📜 Licença

Distribuído sob a licença [MIT](LICENSE). Desenvolvido por **Yan Fabio**.
