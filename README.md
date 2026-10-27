# Grasshopper Topographic Section & Earthwork Volume Calculator 📐🚜

Gerador paramétrico de cortes topográficos e cálculo analítico de **movimentação de terra (terraplenagem: corte e aterro)** para **Rhinoceros 8 / Grasshopper (GhPython)**, compatível com a norma brasileira **NBR 6492** e fundamentado na metodologia clássica de cálculo de volumes por seções transversais.

O algoritmo analisa a interseção do terreno natural com um **greide projetado (definido por uma curva desenhada livremente)**, calculando de forma analítica e visual:
- Áreas exatas de **Corte** (escavação) e **Aterro** (preenchimento);
- Localização e cotas exatas de todos os **Pontos de Passagem (P.P.)** (cota neutra / cota zero de terraplenagem);
- Cubação volumétrica ($m^3$) com consideração de largura de faixa de influência e fator de empolamento do solo ($K$);
- Diagnóstico de balanço de massas (Compensação total, excesso para bota-fora ou déficit para empréstimo de jazida);
- Representação gráfica imediata com **malhas coloridas (Laranja = Corte, Verde = Aterro)** e simbologia técnica de cotas de nível em corte (**NBR 6492**).

---

## 📚 Fundamentação Teórica e Normativa

O cálculo volumétrico é estruturado segundo as formulações didáticas do livro de referência:
> **"TOPOGRAFIA: CÁLCULO DE VOLUMES – NOTAS DE AULA"**  
> *Prof. Luís Augusto Koenig Veiga (Universidade Federal do Paraná - UFPR / AGPTEA)*  
> [Repositório AGPTEA](https://www.bibliotecaagptea.org.br/agricultura/topografia/livros/TOPOGRAFIA%20CALCULO%20DE%20VOLUMES%20NOTAS%20DE%20AULA.pdf)

### Principais Fórmulas Empregadas:

1. **Diferença de Altura / Cota Vermelha ($h$)**:
   $$h(d) = Z_{terreno}(d) - Z_{projetado}(d)$$
   - $h > 0$: **Corte** (relevo natural acima do greide $\rightarrow$ escavação necessária).
   - $h < 0$: **Aterro** (relevo natural abaixo do greide $\rightarrow$ preenchimento necessário).
   - $h = 0$: **Ponto de Passagem (P.P.)** (cota neutra).

2. **Determinação Analítica do Ponto de Passagem ($x_P$)**:
   Quando há transição de corte para aterro entre duas estacas $x_1$ e $x_2$ (onde $h_1 \cdot h_2 < 0$), o ponto neutro exato é obtido por interpolação linear (*AGPTEA, pág. 41*):
   $$x_P = x_1 + \left( \frac{|h_1|}{|h_1| + |h_2|} \right) \cdot (x_2 - x_1)$$
   $$Z_P = Z_{proj}(x_P) = Z_{terreno}(x_P)$$

3. **Cálculo de Áreas pelo Método dos Trapézios**:
   Para cada sub-intervalo entre estacas $\Delta x = x_{i+1} - x_i$ (*AGPTEA, pág. 30, 42–44*):
   $$A_i = \left( \frac{|h_i| + |h_{i+1}|}{2} \right) \cdot \Delta x$$
   $$\text{Área Total de Corte: } A_{corte} = \sum A_{corte\_i} \quad (m^2)$$
   $$\text{Área Total de Aterro: } A_{aterro} = \sum A_{aterro\_i} \quad (m^2)$$

4. **Cubação Volumétrica e Empolamento**:
   $$V_{corte} = A_{corte} \cdot L_f \quad (m^3)$$
   $$V_{aterro} = A_{aterro} \cdot L_f \quad (m^3)$$
   $$V_{solto} = V_{corte} \cdot K \quad (m^3)$$
   *(onde $L_f$ é a largura da faixa de influência e $K$ é o fator de empolamento do solo, padrão $1,20$)*.

5. **Balanço de Movimentação de Terra**:
   $$\Delta V = V_{corte} - V_{aterro}$$
   - Se $\Delta V > 0$: **Excesso de Terra (Sobra)** $\rightarrow$ Bota-fora de $\Delta V \cdot K$ ($m^3$ solto).
   - Se $\Delta V < 0$: **Falta de Terra (Déficit)** $\rightarrow$ Empréstimo de jazida de $|\Delta V|$ ($m^3$).
   - Se $\Delta V \approx 0$: **Compensação Total** $\rightarrow$ Movimentação equilibrada de terra.

---

## 🔌 Entradas (Inputs) do Componente

No Grasshopper, configure as seguintes entradas no componente **Python Script**:

| Parâmetro | Tipo / Type Hint | Acesso | Padrão | Descrição |
| :--- | :--- | :---: | :---: | :--- |
| `Terreno` | `Curve` / `Mesh` | **List** | *Obrigatório* | Curvas de nível 3D do terreno ou malha topográfica. |
| `LinhaCorte` | `Curve` | **Item** | *Obrigatório* | Linha do corte desenhada no Rhino. |
| `CurvaProjeto` | `Curve` | **Item** | *Opcional* | **Curva ou linha do greide projetado.** Pode ser desenhada em 2D diretamente sobre o corte na vista Top (como na imagem de referência) ou em 3D sobre o terreno. |
| `Ponto` | `Point3d` | **Item** | *Auto* | Ponto de inserção da seção 2D na vista Top. |
| `Largura` | `float` | **Item** | `1.0` | Largura da faixa de influência em metros para cálculo de volume ($m^3$). |
| `Empolamento`| `float` | **Item** | `1.20` | Fator de empolamento do solo ($K$) para cálculo de transporte/bota-fora (ex: 1.20 = 20%). |
| `Seletor` | `int` / `str` | **Item** | `1` | Modo de exibição: `0` (Completo), `1` (Terraplenagem / Projetado), `2` (Apenas TN). |
| `Escala` | `float` | **Item** | `1.0` | Escala dos símbolos NBR 6492 e textos técnicos. |
| `NivelProjeto`| `float` | **Item** | *Auto* | Cota Z horizontal fixa caso nenhuma curva de projeto seja conectada. Se omitido, calcula a cota de equilíbrio automático da AGPTEA. |

---

## 📤 Saídas (Outputs) do Componente

| Saída | Tipo de Dado | Descrição |
| :---: | :--- | :--- |
| **`a`** | `PolylineCurve` | Linha 3D do corte sobre o relevo natural (coordenadas de projeto / UTM). |
| **`b`** | `PolylineCurve` | Polilinha 2D do perfil do terreno natural na vista Top. |
| **`c`** | `List[Geometry]` | **DESENHO COMPLETO**: Perfil TN + Greide Projetado + **Malhas Coloridas (Laranja = Corte, Verde = Aterro)** + Símbolos de Nível NBR 6492 + Textos de Alturas Máximas e P.P. |
| **`d`** | `List[Curve]` | **Polígonos Fechados de CORTE**: Curvas fechadas prontas para uso em componentes nativos de `Area`, `Hatch` ou Bake em camadas CAD. |
| **`e`** | `List[Curve]` | **Polígonos Fechados de ATERRO**: Curvas fechadas prontas para uso em `Area`, `Hatch` ou Bake. |
| **`f`** | `List[str]` | **Memorial Técnico de Terraplenagem**: Relatório detalhado para visualização em `Panel`. |

---

## 🎛️ Modos do Seletor (`Seletor`)

- **`1` [Padrão]**: **Foco em Terraplenagem** — Perfil natural limpo (linha guia) + Greide do projeto + Áreas coloridas de corte/aterro + Cotas do projeto, alturas máximas e pontos de passagem.
- **`2`**: **Apenas Terreno Natural** — Perfil natural acompanhado de todas as cotas NBR das curvas de nível (+918, +919, +920...).
- **`0`**: **Completo** — Todas as cotas e anotações simultâneas.

---

## 📋 Exemplo de Relatório Técnico Emitido (`f`)

Ao conectar um `Panel` na saída `f`, o componente exibe o memorial instantâneo de cálculo:

```text
=================================================================
      MEMORIAL DE CÁLCULO DE TERRAPLENAGEM (NBR 6492 & AGPTEA)    
=================================================================
1. DADOS DA SEÇÃO TOPOGRÁFICA:
   - Localização no Top View : X = 293140.20, Y = 7387210.50
   - Extensão da Linha de Corte: 50.00 m
   - Cota Mín / Máx (TN)     : +918.00 m / +926.00 m (ΔZ = 8.00 m)
   - Declividade Média do TN : 16.00% (9.09°)
-----------------------------------------------------------------
2. GREIDE PROJETADO:
   - Tipo de Definição       : Curva 2D no Corte
   - Cota Inicial / Final    : +925.00 m / +920.00 m (Declive)
   - Inclinação do Greide    : -10.00% (5.71°)
-----------------------------------------------------------------
3. PONTOS DE PASSAGEM (P.P. - TRANSIÇÃO CORTE/ATERRO):
  - P.P. 1: d = 20.00 m | Cota = +923.00 m
-----------------------------------------------------------------
4. QUADRO DE ÁREAS DA SEÇÃO (MÉTODO DOS TRAPÉZIOS AGPTEA):
   - Área Total de CORTE  : 10.00 m²
   - Área Total de ATERRO : 36.20 m²
   - Altura Máxima de Corte : 1.00 m (em d = 0.00 m)
   - Altura Máxima de Aterro: 2.00 m (em d = 50.00 m)
-----------------------------------------------------------------
5. CUBAÇÃO VOLUMÉTRICA:
   - Faixa de Influência (L) : 1.00 m
   - Fator de Empolamento (K): 1.20 (20% de expansão)
   - Volume Geométrico de CORTE : 10.00 m³
   - Volume Geométrico de ATERRO: 36.20 m³
   - Volume de Corte Solto (Transporte): 12.00 m³
-----------------------------------------------------------------
6. BALANÇO DE MOVIMENTAÇÃO DE MASSA (COMPENSAÇÃO):
   - Saldo Líquido (Corte - Aterro): -26.20 m³
   - Diagnóstico Operacional:
     FALTA DE TERRA (DÉFICIT): Necessário EMPRÉSTIMO DE JAZIDA de 26.20 m³ (compactado).
-----------------------------------------------------------------
7. CONFIGURAÇÃO DE VISUALIZAÇÃO:
   - Modo 1: Apenas Cotas do Greide e Terraplenagem (Perfil Natural Limpo)
=================================================================
```

---

## 🚀 Como Usar no Rhinoceros 8 / Grasshopper

1. No Grasshopper, crie um componente **Python 3 Script** (ou **GhPython Script**).
2. Cole o código do arquivo [`corte_topografico.py`](corte_topografico.py).
3. Configure os parâmetros de entrada com os nomes e acessos descritos na tabela.
4. Conecte o seu `Terreno` e a sua `LinhaCorte`.
5. Desenhe uma linha ou curva no Rhino (no Top View sobre a seção ou em 3D no terreno) e conecte ao parâmetro `CurvaProjeto`.
6. Conecte um `Panel` na saída `f` para auditar a movimentação de terra e volumes em tempo real!

---

## 📜 Licença

Distribuído sob a licença [MIT](LICENSE). Desenvolvido por Yan Fabio.
