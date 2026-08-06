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
   - Cai na janela **"Dados do Item"** → daí o robô JÁ sabe preencher/confirmar.
   - **Falta definir com o usuário:** formato da mensagem p/ substituir e como
     escolher o card (por MODELO + palavras do título). Pedir um VÍDEO de UMA
     substituição completa.
4. Possível: **ler o pedido direto do WhatsApp Web** (hoje cola-se a mensagem).

---

## Como rodar (no PC do usuário, Windows)

1. Baixar a branch (ZIP) e extrair.
2. `instalar_robo.bat` (uma vez) — instala Playwright (usa o Chrome já instalado).
3. `iniciar_robo.bat` — menu: 1) colar mensagem  2) editar manual.
4. Login no Chrome só na 1ª vez.
