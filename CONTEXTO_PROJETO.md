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

### Formato da mensagem (regras já definidas com o usuário)
```
Orçamento 2346
1 - Pintura preto - 1300x1500 - vidro 6 temperado - j01 - quartos
5 - Pintura Branco Brilhante - Vidro 8 temperado - Sala de jantar
```
- `1300x1500` = **largura x altura** (largura primeiro).
- Vidro sem cor = **INCOLOR**; sem dizer comum = **TEMPERADO** (escreve "comum"
  quando for comum). Ex.: "vidro 6 temperado" → `INCOLOR 06MM - TEMPERADO`.
- Quantidade escrita como **"3un"**.
- Tipo no formato **j01 / j02**.
- **O que não estiver escrito, mantém o que já está no orçamento.**

---

## Modo mensagem — APLICAR (CORRIGIDO nesta rodada)

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

> Falta **testar de verdade** no orçamento 2346 (os 2 itens ponta a ponta) —
> as correções são baseadas na causa raiz documentada, mas não deu para rodar
> contra o W-Vetro real nesta rodada.

---

## TRUQUES DO W-VETRO já descobertos (não reaprender!)

- A janela de edição ("Altera Medida da Esquadria") pode estar num **iframe** —
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
  "CONFIRMAR VENDA"). Depois pode aparecer **"Informe as variáveis"** com outro
  CONFIRMAR — clicar e **verificar se a janela sumiu** (`_confirmar_ate_sumir`),
  porque há dois "Confirmar" na tela ao mesmo tempo.
- **Campo de busca do orçamento:** input imediatamente antes do botão "Procurar"
  (não a busca do menu no canto). Preencher com `fill()` (não digitar letra a letra).
- Depois de aplicar tudo, o W-Vetro mostra **"Orçamento Não Calculado — clique
  em Calcular"** — o robô agora clica em **Calcular** ao final (`clicar_calcular`).

---

## Próximos passos

1. **Testar no PC** o modo mensagem ponta a ponta no orçamento 2346 (os 2
   itens) e confirmar que ficou estável com as correções desta rodada.
2. Se algum campo ainda falhar, mandar os **prints** salvos em
   `~/EGEMAP_robo_prints` (`auto_item_*`, `auto_sem_modal_*`) para ajustar.
3. Futuro (visão do usuário): robô **montar orçamentos do zero** (já que terá
   toda a navegação dominada) — ex.: "Substituir Projeto" / "Novo Orçamento".

---

## Como rodar (no PC do usuário, Windows)

1. Baixar a branch (ZIP) e extrair.
2. `instalar_robo.bat` (uma vez) — instala Playwright (usa o Chrome já instalado).
3. `iniciar_robo.bat` — menu: 1) colar mensagem  2) editar manual.
4. Login no Chrome só na 1ª vez.
