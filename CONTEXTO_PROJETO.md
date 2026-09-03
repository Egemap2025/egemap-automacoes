# EGEMAP — Robô de Alteração de Orçamentos (W-Vetro) — CONTEXTO

Documento de contexto para continuar o projeto numa conversa nova.
**Código mais recente na branch:** `claude/orcamento-2346-alteracao-fmwarh-7top10`
(a versão anterior estava em `claude/orcamento-2346-alteracao-fmwarh`)
Repositório: `Egemap2025/egemap-automacoes`

---

## O que é

Um robô (Python + Playwright) que roda **no PC do usuário** e automatiza o
sistema **web W-Vetro** (`sistema.wvetro.com.br`) para **alterar orçamentos**
a partir dos pedidos que os vendedores mandam no WhatsApp.

Arquivo principal: **`alterar_orcamento.py`**
Auxiliares: `instalar_robo.bat` (instala o Playwright), `iniciar_robo.bat` (roda).
Usa o **Google Chrome instalado** (`channel="chrome"`) com um **perfil dedicado**
(`~/.egemap_wvetro_perfil`), então o login no W-Vetro é feito **uma vez só**.
Prints de depuração são salvos em `~/EGEMAP_robo_prints`.

> Observação: o repositório também tem outro sistema já pronto e funcionando
> (`monitorar.py`) — um monitor de pastas que monta a Proposta Comercial em PDF.
> É separado deste robô. Não mexer nele.

---

## O que JÁ FUNCIONA 100% (testado de verdade no orçamento teste 2346)

1. **Login** no W-Vetro (perfil dedicado; login manual só na 1ª vez).
2. **Abrir orçamento pelo número**: vai na Consulta, escreve o número no campo
   "valor" (o input logo antes do botão "Procurar"), clica Procurar, e abre o
   orçamento **clicando no nome do cliente** (link azul) — com **clique real**.
3. **Ler e listar os itens** do orçamento (nome, medida, vidro), limpo.
4. **Editar Item (modo manual, menu passo a passo)** — TODOS os campos:
   - **Vidro** (lista) · **Cor / ALUMÍNIO-PERFIL** (lista)
   - **Largura, Altura, Quantidade, Tipo (J01), Ambiente** (digitados)
   - Confirma e salva, passando pela janela **"Informe as variáveis"** quando
     aparece (itens com persiana/motor).
5. **Modo mensagem — LEITURA e PREVIEW**: cola a mensagem, o robô entende e
   mostra um resumo do que vai fazer (testado, perfeito).

### Formato da mensagem (flexível — reconhece por conteúdo)
```
Orçamento 2346
1 - 2und - incolor 8mm temperado - pintura preto - j02
5 - 3und - 600x600 - mini-boreal 04mm comum - pintura preto - j04 - bwc
```
- Campos separados por **" - "** (traço COM espaços dos dois lados). Traço
  dentro de palavra (ex.: `mini-boreal`) NÃO quebra o campo.
- `1300x1500` = **largura x altura** (largura primeiro).
- **Vidro reconhecido pelo conteúdo** (não exige a palavra "vidro"): basta ter
  espessura (`8mm`/`6`), tipo (`temperado`/`comum`/`laminado`) ou nome/cor
  (`incolor`, `verde`, `mini-boreal`, `refletivo`...). Sem cor = **INCOLOR**;
  sem dizer comum = **TEMPERADO**. Ex.: "incolor 8mm temperado" →
  `INCOLOR 08MM - TEMPERADO`; "mini-boreal 04mm comum" → `MINI-BOREAL 04MM - COMUM`.
- Quantidade: **"2un" / "2und" / "2 unidades" / "qtde 2"**.
- Tipo no formato **j01 / j02 / pj01**.
- **O que não estiver escrito, mantém o que já está no orçamento.**

---

## Modo mensagem — APLICAR ✅ FUNCIONANDO 100% (teste com vários itens)

> **STATUS:** rodou perfeito no W-Vetro real, modo AUTOMÁTICO, com vários
> itens de tipos diferentes: leu a mensagem, abriu o orçamento, preencheu
> TODOS os campos (largura, altura, qtde, tipo, ambiente, cor, vidro),
> confirmou a janela de edição E a de variáveis, passou item a item e clicou
> Calcular no final. Itens são achados pelo menu ☰ (qualquer tipo de produto).
> **Confirmado pelo usuário: "funcionou perfeitamente".**

**Sintomas que existiam:** às vezes o robô dizia "não achei a janela de
edição" mesmo com a janela ABERTA, ou aplicava a cor mas falhava no vidro.

**Causa raiz:** quando muda **cor/vidro**, o W-Vetro **recarrega a janela**
(recalcular) e sobram "cópias mortas" do texto/campos na memória. O
`_frame_do_modal` só olhava a **primeira** ocorrência do texto — se ela fosse
uma cópia morta (invisível), o robô perdia a janela viva e continuava usando a
janela velha.

**O que foi corrigido (`aplicar_item_auto` e ajudantes):**
- `_frame_do_modal` agora testa a visibilidade de **TODAS** as ocorrências do
  texto (não só a primeira) → acha a janela viva mesmo com cópias mortas.
- Novo `_esperar_recalculo`: depois de trocar cor/vidro, **espera ativamente**
  a janela viva reaparecer (em vez de um tempo fixo) e devolve o frame novo.
- `aplicar_item_auto` **reencontra a janela viva ANTES de cada campo**
  (`_frame_vivo()`), então nunca escreve numa cópia morta. Ordem mantida:
  digitados primeiro, **cor e vidro por último**.
- `_achar_select` / `_achar_input` preferem o campo **VISÍVEL**.
- `_set_select_auto` agora **confere** se a opção realmente ficou marcada
  (avisa se o recálculo reverteu).
- Novo `clicar_calcular`: ao final do modo mensagem o robô clica em
  **Calcular** para atualizar os valores do orçamento.

### Correção extra (a partir de um vídeo do sistema real, 05/08)

O usuário mandou um vídeo editando o item 1 à mão. Isso revelou um **bug**:
- A janela de edição real se chama **"Dados do Item"** (não "Altera Medida da
  Esquadria"). Campos confirmados: QTDE, LARGURA, ALTURA, ALUMINIO/PERFIL,
  VIDRO COR, TIPO, AMBIENTE/LOCALIZACAO, NOME PROJETO. Botões: Confirmar/Fechar.
- **A janela de variáveis NÃO se chama "Informe as variáveis"!** Em itens com
  motor/persiana ela se chama **"Informar Medidas/Quantidades"** (tem o botão
  "SALVAR VARIÁVEIS COMO PADRÃO" e um **CONFIRMAR**). O robô procurava só por
  "Informe as vari" → **ignorava essa janela**, que ficava aberta e travava o
  próximo item.

**Correção:** novo `_confirmar_edicao` reconhece as DUAS janelas
(`MARCAS_MODAL_EDICAO` e `MARCAS_JANELA_VARIAVEIS`) e clica CONFIRMAR até
**todas** fecharem. Ao final aparece "Orçamento Não Calculado" → `clicar_calcular`.

> Ainda falta **testar o ROBÔ de verdade** no 2346 (o vídeo era manual). As
> correções são baseadas nas telas reais do vídeo + causa raiz documentada.

---

## TRUQUES DO W-VETRO já descobertos (não reaprender!)

- A janela de edição chama-se **"Dados do Item"** e pode estar num **iframe** —
  procurar em `page.frames`.
- **Ordem invertida no DOM:** vários campos vêm ANTES do rótulo. Por isso a
  localização é feita **dentro do mesmo bloco do rótulo** (`ancestor::*[.//tag]`)
  e não "o próximo da tela". Ver `_candidatos_campo`, `_achar_input`, `_achar_select`.
- **Cor = "ALUMÍNIO/PERFIL"** — tem **acento no Í**. Buscar por **"PERFIL"** (sem acento).
- **Distinguir selects pelo conteúdo:** vidro tem espessuras ("06MM" + TEMPERADO/
  COMUM); cor tem acabamentos (PINTURA, ANODIZADO...). Ver `_parece_vidro` / `_parece_cor`.
- **Menus ☰ dos itens:** há uma cópia escondida por item; clicar sempre na opção
  **VISÍVEL** (`_clicar_texto_visivel`).
- **Confirmar:** o texto exato "Confirmar"/"CONFIRMAR" (regex `^confirmar$`, ignora
  "CONFIRMAR VENDA"). Depois pode aparecer a janela de variáveis —
  **"Informar Medidas/Quantidades"** (motor/persiana) ou "Informe as variáveis" —
  com outro CONFIRMAR. Usar `_confirmar_edicao`, que clica até **todas** as
  janelas sumirem (há dois "Confirmar" na tela ao mesmo tempo).
- **Campo de busca do orçamento:** input imediatamente antes do botão "Procurar"
  (não a busca do menu no canto). Preencher com `fill()` (não digitar letra a letra).
- Depois de aplicar tudo, o W-Vetro mostra **"Orçamento Não Calculado — clique
  em Calcular"** — o robô agora clica em **Calcular** ao final (`clicar_calcular`).

---

## Próximos passos

1. ✅ FEITO — alterar orçamento (modo mensagem) 100%.
2. ✅ FEITO — resumo/conferência ao final (`_resumo_final` /
   `_confere_item_na_linha`): mostra OK / conferir / falhou por item,
   comparando com a linha da tabela (lenient p/ texto truncado).
3. **EM ANDAMENTO: Substituir Projeto** (trocar o item por outro modelo /
   "adicionar persiana/tela" = trocar por modelo INTEGRADA/COM TELA).
   Fluxo mapeado pelos prints do usuário (05/08):
   - Menu ☰ do item → **"Substituir Projeto"** (última opção do menu).
   - Popup **"Substituir Novo Projeto — Deseja excluir este projeto e incluir
     outro na mesma posição?"** → botão **Sim**.
   - Tela **"ESCOLHA O DESENHO | PROJETO"** (`app.wvetro.selecioneprojeto`):
     dropdowns **LINHA** (Versatic 25, Deluxe 32, Solene..., Guarda-corpo,
     Portão...) e **MODELO** (Janela de Correr 02/03/04/06 Folhas, Janela
     Maxim-ar, Módulo Fixo, Porta de Correr..., Porta de Giro, Portinhola...);
     botão **Pesquisar**.
     Também há NOME FORNECEDOR, BITOLA e um campo PESQUISA (texto).
   - Aparecem **cards de desenho** com código (ex.: `*EGE-VER25-IJCR200A`),
     imagem e título (ex.: `JANELA DE CORRER INTEGRADA 02 FOLHAS | PERFISUD`);
     cada card tem "Mais N opções de desenhos". Clicar no card certo.
   - Cai na tela **"Detalhes do Projeto"** (`app.wvetro.confirmadadosprojeto`)
     — é DIFERENTE da janela "Dados do Item" da edição! Campos:
     NOMENCLATURA, **QUANTIDADE**, **LARGURA (MM)**, **ALTURA (MM)**,
     **COR ACESSÓRIOS**, **COR ALUMINIO | PERFIL**, **VIDRO** (não "VIDRO COR"),
     **AMBIENTE**, **TIPO**, CONTRAMARCO, ARREMATE, ARREM.PISO, ORDEM.
     A MEDIDA vem preenchida do item antigo; VIDRO/TIPO/AMBIENTE **resetam** →
     precisam ser repostos iguais ao que era (+ mudanças pedidas).
     Botões: **"Incluir item no orçamento"**, "Incluir mesmo item e informar
     nova medida", "Escolher outro projeto".
   - Após "Incluir item no orçamento" abre **"Informe as variáveis"**. Para
     itens com persiana, a variável-chave é **AE — ACIONAMENTO DA ESTEIRA**:
     opções **MOTOR COM CONTROLE / RECOLHEDOR CORDÃO / RECOLHEDOR FITA**.
     Se MOTOR → aparecem VM (VOLTAGEM DO MOTOR 220V), AM (ACIONAMENTO DO
     MOTOR: CONTROLE REMOTO), RC (LADO DO RECOLHEDOR/MOTOR). Outras: PP (PASSO
     DAS PALHETAS), TP (TAMANHO DA PALHETA), MD (USA MANCAL DIVISOR), etc.
     Depois **CONFIRMAR**.
   - **Falta definir com o usuário:** (a) formato da mensagem p/ substituir;
     (b) como escolher o card quando há vários; (c) a LINHA vem na mensagem ou
     é padrão; (d) valor padrão do ACIONAMENTO (motor x recolhedor fita).
   - **Popup "Atenção! Existem itens com valores zerados"** (botões "CONFERIR
     ITENS SEM VALOR" e **"Fechar"**) pode aparecer na tela de seleção → o robô
     deve só clicar **Fechar** e continuar (confirmado pelo usuário).
   - **ATENÇÃO / RISCO:** substituir EXCLUI o projeto antigo antes de incluir o
     novo. Construir primeiro em modo SEGURO (robô navega/preenche, usuário
     confirma os passos críticos) para não perder item por engano.
   - **v1 IMPLEMENTADA (modo guiado):** `substituir_item_projeto`. Formato da
     mensagem: `N - substituir - <modelo> - <linha> - <acionamento> - <overrides>`
     (também aceita `substituir por <modelo>`). O robô: abre ☰→Substituir
     Projeto→Sim→fecha popup valores zerados→seleciona LINHA e MODELO (melhor
     match)→**pausa p/ conferir**→Pesquisar→**usuário clica o card**→preenche
     Detalhes do Projeto (cor/vidro/tipo/ambiente/medida da mensagem)→**usuário
     finaliza** (Incluir item + variáveis/acionamento + Confirmar). LINHA e
     acionamento vêm na mensagem; acionamento padrão MOTOR (só p/ persiana).
   - **v2 (a fazer):** preservar automaticamente vidro/tipo/ambiente do item
     antigo quando não vierem na mensagem; automatizar a escolha do card e as
     variáveis (acionamento) ponta a ponta.
4. Possível: **ler o pedido direto do WhatsApp Web** (hoje cola-se a mensagem).

---

## MONTAR ORÇAMENTO DO ZERO ✅ v1 IMPLEMENTADA (menu opção 3)

O usuário quer **montar orçamentos do zero** (achou mais fácil que alterar).
O fluxo do W-Vetro é o MESMO da substituição — só muda a **porta de entrada**:
em vez de ☰→"Substituir Projeto", clica no botão **"Inserir Novo Projeto"** e
cai na mesma tela `selecioneprojeto`. Por isso o motor foi **refatorado**:

- **`_construir_na_selecao(page, num, mud, prefixo)`** — motor compartilhado a
  partir de "ESCOLHA O DESENHO": LINHA/MODELO → Pesquisar → escolhe card →
  preenche Dados do Projeto (agora inclui **QUANTIDADE**) → Incluir item →
  variáveis/acionamento → Confirmar. Usado por `substituir_item_projeto` e por
  `montar_item_novo`.
- **`montar_item_novo(page, num, mud)`** — clica "Inserir Novo Projeto"
  (fallbacks: "novo projeto"/"adicionar item"/"incluir projeto") e chama o motor.
- **`parse_montar(texto)`** + **`_spec_item_novo(linha)`** — lê a mensagem:
  cabeçalho `Montar orçamento NNNN` e **uma linha por item novo**. Cada linha:
  `[código] descrição do modelo - cor - vidro - ambiente - ...`
  Ex.: `j01 janela 02 folhas e tela com persiana com motor l32 - branco
  brilhante - incolor 6mm temperado - quartos`.
  Extrai: código→TIPO (`j01`), linha embutida (`l32`→32 / `linha 25`),
  acionamento (`motor`/`manual`), MODELO (resto da descrição), e classifica
  cor/vidro/medida(`900x2100`)/qtde/ambiente pelos pedaços com ` - `.
- **`modo_montar(page)`** — menu opção 3: cola a mensagem, mostra preview,
  abre o orçamento, monta item a item (reabre o orçamento entre itens), Calcular,
  resumo final.

### MODELO (dropdown) — mapa das PORTAS (confirmado por prints do usuário 03/09)
Lista real da LINHA **L.30**: JANELA DE CORRER, JANELA PIVOTANTE, MAXIM-AR,
MÓDULO FIXO, PORTA CAMARÃO, PORTA DE CORRER, **PORTA DE GIRO 01/02 FOLHA(S)**,
**PORTA PIVOTANTE** (+ 01/02 FOLHA(S)), **PORTÃO DE CORRER 01 FOLHA**, PORTAS DE
GIRO, PORTINHOLA, VENEZIANA. `_modelo_dropdown` mapeia:
- `maxim`→MAXIM-AR · `portinhola`→PORTINHOLA · `veneziana`→VENEZIANA ·
  `camarão`→PORTA CAMARÃO.
- `pivotante`: com "janela"→JANELA PIVOTANTE; com "porta"→PORTA PIVOTANTE (ou
  `PORTA PIVOTANTE NN FOLHA(S)` se disser folhas). **Pivotante ripada** = MODELO
  PORTA PIVOTANTE + **card "RIPADA/RIPADO VERTICAL"** (a "ripada" é o desenho,
  não o modelo). Também existe LINHA "RIPADOS" com MODELO "PORTA PIVOTANTE 01
  FOLHA" (cards RIP-PP1).
- `porta` + `giro/abrir/batente`→PORTA DE GIRO 01/02 FOLHA(S) (portas internas
  de abrir; default 01 folha). `porta de abrir` = porta de giro.
- `porta` + `correr`: com "tras/parede/portão/embutir"→PORTÃO DE CORRER 01 FOLHA
  (cards "porta de correr pra trás da parede"); senão PORTA DE CORRER.
- `01 FOLHA` singular / `NN FOLHAS` plural (`_folha_sfx`).
- fixo/painel/módulo→MÓDULO FIXO · resto→JANELA DE CORRER NN FOLHAS.

### Ainda a fazer no MONTAR
- **Solucionar o clique no card "N módulos"** (fallback ainda pede 1 clique).
- **Ler o CRM** (`crm.egemapesquadrias.com.br/deals`): nome, telefone, cidade,
  rua/bairro/número, responsável (vendedor) e "Resumo do orçamento".
- **Ler o PDF arquitetônico** (tabela de esquadrias, texto legível via pymupdf)
  para pré-preencher a **tabela do vendedor** (PDF + CRM). Protótipo em
  `/tmp/ler_esq.py` (extraiu J1–J6, P1–P6 de um PDF real).
- **Definir como o orçamento/cliente é criado** no W-Vetro (os vídeos reusam o
  orçamento vazio 2346 via "Inserir Novo Projeto"; falta o fluxo de Novo Orçamento
  + cadastro do cliente/endereço).
- Confirmar formato da tabela do vendedor: planilha vs texto (recomendei planilha).

---

## Como rodar (no PC do usuário, Windows)

1. Baixar a branch (ZIP) e extrair.
2. `instalar_robo.bat` (uma vez) — instala Playwright (usa o Chrome já instalado).
3. `iniciar_robo.bat` — menu: 1) colar mensagem  2) editar manual
   3) MONTAR do zero.
4. Login no Chrome só na 1ª vez.

> Mais fácil: **`EGEMAP_ROBO.bat`** — lançador único que baixa sozinho a versão
> mais nova do robô do GitHub (repo público) e roda. Só 2 cliques.
