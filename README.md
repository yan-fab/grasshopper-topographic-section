# Grasshopper Topographic Section Suite (NBR 6492) 📐🏔️

Suíte completa de scripts paramétricos para **Rhinoceros 8 / Grasshopper (GhPython)** voltados para geração de cortes topográficos técnicos, compatíveis com a norma brasileira **NBR 6492** (Representação de Projetos de Arquitetura).

O repositório disponibiliza **duas versões especializadas**, permitindo escolher a ferramenta ideal para cada etapa do projeto:

| Versão | Arquivo Principal | Finalidade | Principais Recursos |
| :---: | :--- | :--- | :--- |
| **Versão 1** | [`corte_arquitetonico.py`](corte_arquitetonico.py) | **Implantação Arquitetônica** | Casa/Edificação, laje de cobertura em balanço, platô contínuo, rampa de aterro de acesso e cotas NBR de piso e cobertura. |
| **Versão 2** | [`corte_terraplenagem.py`](corte_terraplenagem.py) | **Movimentação de Terra & Volumes** | Curva de greide livre (`CurvaProjeto`), cálculo de áreas de corte e aterro (**Método dos Trapézios AGPTEA**), Pontos de Passagem (P.P.), malhas coloridas (Laranja/Verde) e cubação com empolamento ($m^3$). |

---

## 🏗️ Versão 1: Corte com Implantação Arquitetônica

> **Arquivo:** [`corte_arquitetonico.py`](corte_arquitetonico.py) (ou [`src/corte_arquitetonico.py`](src/corte_arquitetonico.py))

Projetado para apresentar a implantação da edificação inserida diretamente no relevo topográfico, resolvendo cortes longitudinais e transversais sem artefatos ou fendas.

### Recursos da Versão 1:
- **Corte Universal Automático**:
  - **Corte Longitudinal**: Desenha as paredes da casa, fundações conectadas ao terreno natural, laje do piso, beiral da cobertura circular e rampa de aterro conectando ao terreno alto.
  - **Corte Transversal**: Quando a linha não cruza a edificação, gera o platô de forma contínua, nivelada e com muros de contenção nas extremidades.
- **Simbologia NBR 6492**:
  - Marcadores de nível triangulares sólidos (`Mesh`) com haste e prateleira.
  - Textos vetoriais nativos (`TextEntity`) com prefixo de sinal (`+921,00`).
  - Cotas específicas de `PISO`, `COB.` e `PLATÔ`.
- **Seletor de Cotas**:
  - `1`: Apenas cotas do projeto arquitetônico (+ perfil natural como linha guia).
  - `2`: Apenas cotas do terreno natural.
  - `0`: Todas as cotas simultâneas.

### Entradas (Inputs) - Versão 1:
| Parâmetro | Tipo / Type Hint | Acesso | Descrição |
| :--- | :--- | :---: | :--- |
| `Terreno` | `Curve` / `Mesh` | **List** | Curvas de nível 3D ou malha topográfica. |
| `LinhaCorte` | `Curve` | **Item** | Linha do corte desenhada no Rhino. |
| `Ponto` | `Point3d` *(Opcional)* | **Item** | Ponto de inserção da seção 2D na vista Top. |
| `Retangulo` | `Curve` *(Opcional)* | **Item** | Contorno em planta da casa / edificação. |
| `Cobertura` | `Curve` *(Opcional)* | **Item** | Contorno em planta da cobertura circular. |
| `Plato` | `Curve` *(Opcional)* | **Item** | Contorno do platô de terraplanagem. |
| `Descida` | `Curve` *(Opcional)* | **Item** | Contorno da rampa de acesso/aterro. |
| `Seletor` | `int` *(Opcional)* | **Item** | Modo de cotas (`1`: Projeto, `2`: TN, `0`: Ambos). |
| `NivelPiso` | `float` *(Opcional)* | **Item** | Cota Z exata do piso da residência. |
| `Altura` | `float` *(Opcional)* | **Item** | Pé-direito da edificação (padrão: `3.0` m). |
| `Espessura`| `float` *(Opcional)* | **Item** | Espessura da laje de cobertura (padrão: `0.20` m). |
| `Escala` | `float` *(Opcional)* | **Item** | Escala dos símbolos e textos NBR (padrão: `1.0`). |

### Saídas (Outputs) - Versão 1:
| Saída | Descrição |
| :---: | :--- |
| **`a`** | Linha 3D do corte sobre o relevo natural (modelo 3D). |
| **`b`** | Polilinha 2D do terreno natural na vista Top. |
| **`c`** | **DESENHO COMPLETO**: Terreno + Platôs + Casa + Cobertura + Cotas ativas. |
| **`d`** | Apenas as Cotas do Projeto isoladas. |
| **`e`** | Apenas as Cotas do Terreno Natural isoladas. |
| **`f`** | Relatório Técnico no Panel com dados geométricos e declividades. |

---

## 🚜 Versão 2: Movimentação de Terra e Volumes (Corte & Aterro)

> **Arquivo:** [`corte_terraplenagem.py`](corte_terraplenagem.py) (ou [`src/corte_terraplenagem.py`](src/corte_terraplenagem.py))

Projetado exclusivamente para **estudos de terraplenagem e quantificação volumétrica**, eliminando elementos de casa e implementando as formulações analíticas clássicas de topografia:

> **Referência Metodológica:**  
> *"TOPOGRAFIA: CÁLCULO DE VOLUMES – NOTAS DE AULA"* — Prof. Luís Augusto Koenig Veiga (UFPR / AGPTEA).  
> [Acessar Apostila da AGPTEA](https://www.bibliotecaagptea.org.br/agricultura/topografia/livros/TOPOGRAFIA%20CALCULO%20DE%20VOLUMES%20NOTAS%20DE%20AULA.pdf)

### Recursos da Versão 2:
- **Entrada `CurvaProjeto`**:
  - Aceita qualquer linha ou curva desenhada livremente no Rhino.
  - Pode ser desenhada **em 2D diretamente sobre a seção na vista Top** (como um corte analítico) ou **em 3D sobre o relevo**.
  - Possui cálculo automático da **Cota de Passagem Ponderada de Compensação (AGPTEA pág. 40-41)** caso nenhuma curva seja conectada.
- **Cálculo Analítico de Áreas (Método dos Trapézios)**:
  - Localiza os **Pontos de Passagem (P.P.)** por interpolação linear exata ($h = 0$).
  - Decompõe a seção em trapézios e triângulos para calcular $A_{corte}$ e $A_{aterro}$ ($m^2$).
- **Cubação Volumétrica e Balanço de Massas**:
  - Volume Geométrico: $V = A \cdot \text{Largura}$ ($m^3$).
  - Volume de Transporte: $V_{solto} = V_{corte} \cdot K$ (fator de empolamento, padrão $1,20$).
  - Saldo Líquido ($\Delta V = V_{corte} - V_{aterro}$): diagnóstico imediato de excesso para **Bota-Fora**, déficit para **Empréstimo de Jazida** ou **Compensação Total**.
- **Representação Gráfica Visual**:
  - Malha colorida em **Laranja** (`RGB 245, 130, 32`) para as zonas de **Corte**.
  - Malha colorida em **Verde** (`RGB 46, 204, 113`) para as zonas de **Aterro**.
  - Polígonos fechados nas saídas `d` e `e` prontos para componentes nativos de `Area`, `Hatch` ou envio para camadas CAD.

### Entradas (Inputs) - Versão 2:
| Parâmetro | Tipo / Type Hint | Acesso | Descrição |
| :--- | :--- | :---: | :--- |
| `Terreno` | `Curve` / `Mesh` | **List** | Curvas de nível 3D ou malha topográfica. |
| `LinhaCorte` | `Curve` | **Item** | Linha do corte desenhada no Rhino. |
| `CurvaProjeto` | `Curve` *(Opcional)* | **Item** | **Linha ou curva do greide desenhada no corte (2D) ou no relevo (3D).** |
| `Ponto` | `Point3d` *(Opcional)* | **Item** | Ponto de inserção da seção 2D na vista Top. |
| `Largura` | `float` *(Opcional)* | **Item** | Largura da faixa de influência em metros para volume $m^3$ (padrão: `1.0` m). |
| `Empolamento`| `float` *(Opcional)* | **Item** | Fator de expansão do solo para transporte (padrão: `1.20` = 20%). |
| `Seletor` | `int` *(Opcional)* | **Item** | `1`: Terraplenagem [Padrão], `2`: Apenas TN, `0`: Completo. |
| `Escala` | `float` *(Opcional)* | **Item** | Fator de escala dos símbolos e textos NBR (padrão: `1.0`). |
| `NivelProjeto`| `float` *(Opcional)* | **Item** | Cota Z fixa se não desenhar a curva (senão calcula automático). |

### Saídas (Outputs) - Versão 2:
| Saída | Descrição |
| :---: | :--- |
| **`a`** | Linha 3D do corte sobre o relevo natural. |
| **`b`** | Polilinha 2D do terreno natural. |
| **`c`** | **DESENHO COMPLETO**: Perfil TN + Greide Projetado + **Malhas Coloridas (Laranja/Verde)** + Cotas NBR + P.P. |
| **`d`** | **Polígonos Fechados de CORTE** (Curvas fechadas para `Area`, `Hatch` ou layers). |
| **`e`** | **Polígonos Fechados de ATERRO** (Curvas fechadas para `Area`, `Hatch` ou layers). |
| **`f`** | **Memorial Técnico AGPTEA** (Quadro analítico com áreas, volumes, pontos de passagem e balanço). |

---

## 🚀 Como Usar no Grasshopper

1. Abra o **Grasshopper** no Rhinoceros 8.
2. Adicione um componente **Python 3 Script** (ou **GhPython Script**).
3. Abra o editor de código e cole o código da versão desejada:
   - Para projetos com arquitetura/casa: use [`corte_arquitetonico.py`](corte_arquitetonico.py).
   - Para estudos de terraplenagem e movimentação de terra: use [`corte_terraplenagem.py`](corte_terraplenagem.py).
4. Clique com o botão direito nos parâmetros de entrada e configure os nomes e **Type Hints** conforme as tabelas acima (`Terreno` sempre em **List Access**).
5. Conecte as geometrias referenciadas do Rhino.
6. Conecte um `Panel` na saída `f` para visualizar o memorial técnico em tempo real.

---

## 📜 Licença

Distribuído sob a licença [MIT](LICENSE). Desenvolvido por Yan Fabio.
