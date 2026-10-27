# Grasshopper Topographic Section Generator (NBR 6492) 📐🏔️

Gerador paramétrico de cortes topográficos arquitetônicos e de terraplanagem para **Rhinoceros 8 / Grasshopper (GhPython)**, compatível com a norma brasileira **NBR 6492** (Representação de Projetos de Arquitetura).

Projetado especificamente para lidar com levantamentos topográficos reais em coordenadas georreferenciadas (**UTM**), calculando automaticamente a interseção de linhas de corte com curvas de nível 3D, platôs de terraplanagem, rampas de acesso/aterro e implantação da edificação.

---

## 🌟 Funcionalidades Principais

- **Corte Topográfico 3D $\rightarrow$ 2D Automático**: Intersecta a linha de corte com qualquer conjunto de curvas de nível (`Curve`) ou malhas de terreno (`Mesh`).
- **Posicionamento Local no Top View**: Projeta o perfil 2D diretamente na vista superior (`Top View` / plano XY) através de um ponto de referência (`Point3d`), evitando perda de escala em coordenadas UTM com offsets milionários.
- **Símbolos de Nível NBR 6492**:
  - Triângulo invertido com preenchimento sólido à direita e contorno aberto à esquerda.
  - Haste vertical e linha horizontal de apoio.
  - Texto vetorial nativo (`TextEntity`) limpo e legível com prefixo de sinal e vírgula decimal (ex: `+921,00`).
- **Corte Universal Inteligente**:
  - **Cortes Longitudinais (Passando pela Edificação)**: Desenha a casa (paredes, piso, fundações), a laje de cobertura com beirais em balanço, o platô horizontal e a rampa inclinada de aterro conectando ao terreno natural.
  - **Cortes Transversais (Fora da Edificação)**: Gera o platô de forma contínua, nivelada e sem buracos ou quebras artificiais.
- **Massa de Terraplanagem (Corte & Aterro)**: Gera polígonos fechados contornando o terreno natural sob os platôs e rampas, prontos para cálculo de volume ou aplicação de hachura (`Hatch`).
- **Seletor de Modos de Cotas**:
  - Permite alternar instantaneamente entre a visualização de cotas do projeto e do terreno natural.

---

## 🎛️ Modos do Seletor de Cotas (`Seletor`)

O componente conta com um seletor flexível para controle de sobreposição e limpeza gráfica do desenho:

| Valor / Entrada | Modo de Exibição | Descrição |
| :---: | :--- | :--- |
| **`1`** *(ou `True` / `"projetado"`)* **[Padrão]** | **Apenas Terreno Projetado** | Mantém a linha guia do perfil natural (TN) e exibe **apenas as cotas do Projeto** (`PLATÔ`, `ATERRO`, `PISO`, `COB`). Oculta as cotas intermediárias do relevo natural para manter o desenho limpo. |
| **`2`** *(ou `False` / `"natural"`)* | **Apenas Terreno Natural** | Exibe o perfil natural acompanhado de **todas as cotas das curvas de nível** (+918, +919, +920...). Oculta as cotas de projeto. |
| **`0`** *(ou `"tudo"` / `"completo"`)* | **Completo (Ambos)** | Exibe **todas as cotas simultaneamente** (Terreno Natural + Projeto). |

---

## 🔌 Entradas (Inputs) do Componente

No Grasshopper, configure os seguintes nomes e tipos de acesso no componente **Python Script**:

| Parâmetro | Tipo / Type Hint | Acesso | Descrição |
| :--- | :--- | :---: | :--- |
| `Terreno` | `Curve` / `Mesh` | **List Access** | Curvas de nível 3D do terreno ou malha topográfica. |
| `LinhaCorte` | `Curve` | **Item Access** | Linha do corte desenhada no Rhino. |
| `Ponto` | `Point3d` | **Item Access** | Ponto de inserção onde o corte 2D será gerado na vista Top. |
| `Retangulo` | `Curve` *(Opcional)* | **Item Access** | Contorno em planta da edificação (casa). |
| `Cobertura` | `Curve` *(Opcional)* | **Item Access** | Contorno em planta da cobertura circular ou laje. |
| `Plato` | `Curve` *(Opcional)* | **Item Access** | Contorno em planta do platô / aterro (ex: círculo ou polígono). |
| `Descida` | `Curve` *(Opcional)* | **Item Access** | Contorno da rampa ou acesso de entrada do lote. |
| `Seletor` | `int` / `str` / `bool` | **Item Access** | Modo de cotas (`1`: Projetado, `2`: Natural, `0`: Todos). |
| `NivelPiso` | `float` *(Opcional)* | **Item Access** | Cota Z exata do piso da casa (calcula automaticamente se omitido). |
| `NivelPlato` | `float` *(Opcional)* | **Item Access** | Cota Z do platô (alinha com o piso se omitido). |
| `NivelAterro`| `float` *(Opcional)* | **Item Access** | Cota Z do topo do aterro / greide. |
| `Altura` | `float` *(Opcional)* | **Item Access** | Pé-direito da casa (padrão: `3.0` m). |
| `Espessura`| `float` *(Opcional)* | **Item Access** | Espessura da laje de cobertura (padrão: `0.20` m). |
| `Escala` | `float` *(Opcional)* | **Item Access** | Fator de escala dos símbolos e textos NBR (padrão: `1.0`). |

---

## 📤 Saídas (Outputs) do Componente

| Saída | Descrição |
| :---: | :--- |
| **`a`** | Linha 3D sobre o relevo natural (para visualização na perspectiva/axonometria). |
| **`b`** | Polilinha 2D do terreno natural na vista Top. |
| **`c`** | **DESENHO COMPLETO**: Terreno + Platôs + Rampa de Aterro + Edificação + Cotas NBR ativas. |
| **`d`** | Apenas as Cotas do Projeto isoladas (para camadas/layers independentes). |
| **`e`** | Apenas as Cotas do Terreno Natural isoladas. |
| **`f`** | **Relatório Técnico** (Painel de texto com declividade média, cotas mín/máx, extensões e volumes). |

---

## 🚀 Como Usar no Grasshopper

1. Abra o **Grasshopper** no Rhinoceros 8.
2. Adicione um componente **Python 3 Script** (ou **GhPython Script**).
3. Clique duas vezes no componente para abrir o editor de código.
4. Cole o conteúdo de [`corte_topografico.py`](corte_topografico.py).
5. No componente no canvas, clique com o botão direito nos parâmetros de entrada e configure os nomes e **Type Hints** conforme a tabela acima (garanta que `Terreno` esteja em **List Access**).
6. Conecte as geometrias referenciadas do Rhino aos respectivos inputs.
7. Conecte um `Panel` na saída `f` para visualizar o memorial técnico de cálculo.

---

## 📐 Estrutura do Relatório Técnico (`f`)

O componente emite um memorial técnico instantâneo formatado para visualização em `Panel`:

```text
=== CORTE TOPOGRÁFICO - PROJETO COMPLETO ===
Localização do Corte: X=293140.20, Y=7387210.50
Extensão do Terreno : 48.35 m
Cota Inicial / Final: 918.00 m / 926.00 m (Aclive)
Cota Mín / Máx (TN) : 917.40 m / 926.80 m (ΔZ = 9.40 m)
Declividade Média   : 19.44% (11.00°)
----------------------------------------
SELETOR DE COTAS ATIVO:
Modo 1: Apenas Cotas do Terreno Projetado (+ Perfil Natural)
----------------------------------------
PLATÔ / ATERRO:
Corte Longitudinal: Platô +921.00m com Casa e Rampa
----------------------------------------
CASA (RETÂNGULO):
Casa: d=18.20m a 26.20m | Piso: +921.00m
----------------------------------------
COBERTURA CIRCULAR (CÍRCULO):
Cobertura: d=15.50m a 28.90m | Cota: +924.20m
========================================
```

---

## 📜 Licença

Distribuído sob a licença [MIT](LICENSE). Desenvolvido por Yan Fabio.
