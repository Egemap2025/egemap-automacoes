#!/usr/bin/env python3
"""
EGEMAP - Robo de Alteracao de Orcamentos (W-Vetro)
===================================================

Automacao do sistema web W-Vetro (sistema.wvetro.com.br) para alterar
orcamentos sozinho, a partir dos pedidos que os vendedores mandam.

Esta e a ETAPA 1 (base). Ela NAO altera nada ainda -- so:
  1. Abre o navegador (Google Chrome) e faz login no W-Vetro (uma vez so)
  2. Abre um orcamento pelo numero
  3. Le e mostra os itens do orcamento (para conferir que o robo "enxerga")

Assim confirmamos que o robo navega certo ANTES de deixar ele mexer em algo.
As alteracoes (trocar vidro / substituir projeto) entram na proxima etapa.

Como usar:
  1. Rode "instalar_robo.bat" uma vez (instala o Playwright).
  2. Rode "iniciar_robo.bat".
  3. Na primeira vez, faca login no W-Vetro na janela que abrir e volte aqui.
"""

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("\nO Playwright nao esta instalado.")
    print('Rode o arquivo "instalar_robo.bat" primeiro (ou: pip install playwright).\n')
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────

URL_LOGIN    = "https://sistema.wvetro.com.br/concept/app.wvetro.login"
URL_HOME     = "https://sistema.wvetro.com.br/concept/app.wvetro.home"
URL_CONSULTA = "https://sistema.wvetro.com.br/concept/app.core.wworcamento"

# Perfil dedicado do robo. O login fica salvo aqui, entao voce so loga uma vez.
# (Nao usamos o seu Chrome normal para nao dar conflito de "perfil em uso".)
PERFIL_DIR = Path.home() / ".egemap_wvetro_perfil"

# Pasta onde o robo salva prints de cada passo (para depurar juntos).
PRINTS_DIR = Path.home() / "EGEMAP_robo_prints"


# ── Utilidades ──────────────────────────────────────────────────────────────────

def log(msg):
    hora = time.strftime("%H:%M:%S")
    print(f"[{hora}] {msg}", flush=True)


def print_tela(page, nome):
    """Salva um print da tela atual para conferencia."""
    try:
        PRINTS_DIR.mkdir(parents=True, exist_ok=True)
        caminho = PRINTS_DIR / f"{nome}.png"
        page.screenshot(path=str(caminho), full_page=False)
        log(f"   (print salvo: {caminho})")
    except Exception as e:
        log(f"   (nao consegui salvar print: {e})")


def esta_logado(page):
    """Considera logado se, ao abrir a consulta, NAO cair na tela de login."""
    try:
        page.goto(URL_CONSULTA, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
        url = page.url.lower()
        if "login" in url:
            return False
        # Se aparece o titulo da consulta, esta logado
        try:
            page.get_by_text("CONSULTA DE ORCAMENTOS", exact=False).wait_for(timeout=4000)
        except PWTimeout:
            # As vezes o texto vem com acento; confia na URL entao
            return "login" not in page.url.lower()
        return True
    except Exception:
        return False


def garantir_login(page):
    """Garante que estamos logados. Se nao, pede para o usuario logar na janela."""
    if esta_logado(page):
        log("Ja esta logado no W-Vetro. ✔")
        return

    log("Precisa fazer login.")
    page.goto(URL_LOGIN, wait_until="domcontentloaded")
    print()
    print("=" * 60)
    print("  FACA LOGIN NA JANELA DO NAVEGADOR QUE ABRIU")
    print("  (usuario, senha e codigo -- os mesmos de sempre)")
    print("  O login fica salvo, entao voce so faz isso UMA vez.")
    print("=" * 60)
    input("\n  Depois que entrar no sistema, aperte ENTER aqui...  ")

    if not esta_logado(page):
        log("Ainda nao detectei o login. Tente de novo (aperte ENTER apos entrar).")
        input("\n  Aperte ENTER quando ja estiver dentro do sistema...  ")


# ── Abrir orcamento e ler itens ──────────────────────────────────────────────────

def abrir_orcamento(page, numero):
    """Abre a Consulta, procura pelo numero do orcamento e abre o detalhe.
    Retorna True se conseguiu abrir o detalhe do orcamento."""
    log(f"Abrindo a Consulta de Orcamentos...")
    page.goto(URL_CONSULTA, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    # 1) Garante que o filtro "Filtrar por" esteja em Nro.Orcamento (costuma ja estar)
    #    e escreve o numero no campo "valor".
    log(f"Procurando o orcamento n. {numero}...")
    preenchido = _preencher_numero(page, numero)
    if not preenchido:
        print_tela(page, f"consulta_sem_campo_{numero}")
        log("Nao encontrei o campo de numero automaticamente.")
        log("Me manda o print salvo que eu ajusto o robo.")
        return False

    # 2) Clica em Procurar
    try:
        page.get_by_role("button", name="Procurar").click(timeout=8000)
    except PWTimeout:
        try:
            page.get_by_text("Procurar", exact=True).click(timeout=5000)
        except PWTimeout:
            page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    print_tela(page, f"consulta_resultado_{numero}")

    # 3) Abre o orcamento (clica no nome do cliente / na linha do resultado)
    if not _abrir_linha_resultado(page, numero):
        log("Achei a busca, mas nao consegui abrir a linha do orcamento sozinho.")
        log("Me manda o print salvo que eu ajusto.")
        return False

    page.wait_for_timeout(3500)
    # Confirma que estamos no detalhe
    try:
        page.get_by_text("DETALHE DO ORCAMENTO", exact=False).wait_for(timeout=8000)
    except PWTimeout:
        # tenta pela URL
        if "detalheorcamento" not in page.url.lower():
            print_tela(page, f"apos_abrir_{numero}")
            log("Cliquei, mas nao tenho certeza que abriu o detalhe. Print salvo.")
            return False

    print_tela(page, f"detalhe_{numero}")
    log(f"Orcamento {numero} aberto. ✔")
    return True


def _escrever_no_campo(campo, numero):
    """Escreve o numero de forma robusta e confere se ficou certo.
    Usa fill() (preenche de uma vez, sem perder digito) e, se falhar,
    tenta limpar e digitar de novo."""
    numero = str(numero)
    campo.scroll_into_view_if_needed()
    campo.click()
    # limpa qualquer conteudo anterior
    try:
        campo.press("Control+a")
        campo.press("Delete")
    except Exception:
        pass
    # fill preenche o valor inteiro de uma vez (nao perde o 1o digito)
    campo.fill(numero)
    campo.wait_for(timeout=1000)
    if (campo.input_value() or "").strip() == numero:
        return True
    # 2a tentativa: limpa e digita de novo
    try:
        campo.press("Control+a")
        campo.press("Delete")
        campo.fill(numero)
        campo.wait_for(timeout=800)
    except Exception:
        pass
    return numero in (campo.input_value() or "")


def _preencher_numero(page, numero):
    """Escreve o numero no campo 'valor' da busca (o input imediatamente
    antes do botao 'Procurar'), evitando a busca do menu no canto esquerdo."""
    numero = str(numero)

    # Estrategia A (a boa): o input mais proximo ANTES do botao Procurar.
    try:
        campo = page.locator(
            "xpath=//button[normalize-space()='Procurar']/preceding::input[1]"
        ).first
        campo.wait_for(timeout=5000)
        if _escrever_no_campo(campo, numero):
            log(f"   (numero {numero} escrito no campo de busca certo)")
            return True
    except Exception:
        pass

    # Estrategia B: input logo apos o seletor de operador "=" na linha de filtro.
    try:
        campo = page.locator(
            "xpath=//select[option[normalize-space()='=']]/following::input[1]"
        ).first
        campo.wait_for(timeout=4000)
        if _escrever_no_campo(campo, numero):
            return True
    except Exception:
        pass

    # Estrategia C: campo do tipo spinbox (numero) -- ultimo recurso.
    try:
        campo = page.get_by_role("spinbox").last
        campo.wait_for(timeout=3000)
        campo.fill(numero)
        return True
    except Exception:
        pass

    return False


def _abrir_linha_resultado(page, numero):
    """Abre o detalhe do orcamento clicando no NOME DO CLIENTE (link azul
    sublinhado) da linha do resultado -- com clique REAL (mouse), que e o
    que o W-Vetro reconhece."""
    numero = str(numero)

    # Localiza a linha do resultado que contem o numero.
    linha = None
    try:
        cand = page.get_by_role("row").filter(has_text=numero).first
        cand.wait_for(timeout=6000)
        linha = cand
    except Exception:
        try:
            cand = page.locator("tr").filter(has_text=numero).first
            cand.wait_for(timeout=4000)
            linha = cand
        except Exception:
            linha = None

    # A) Clique REAL no link <a> (nome do cliente) dentro da linha.
    if linha is not None:
        try:
            a = linha.locator("a").first
            a.wait_for(timeout=4000)
            a.scroll_into_view_if_needed()
            a.click()
            log("   (cliquei no nome do cliente)")
            return True
        except Exception:
            pass
        # A2) qualquer texto sublinhado/clicavel na linha
        try:
            linha.locator("a, u, [style*='underline'], [onclick]").first.click(timeout=3000)
            return True
        except Exception:
            pass

    # B) Fallback: primeiro link da area de resultado (fora do cabecalho).
    try:
        a = page.locator("tbody a").first
        a.wait_for(timeout=4000)
        a.scroll_into_view_if_needed()
        a.click()
        return True
    except Exception:
        pass

    # C) Fallback: pega o nome do cliente e clica por texto (clique real).
    try:
        nome = page.evaluate(
            """(numero) => {
                for (const t of document.querySelectorAll('table')) {
                    const ths = Array.from(t.querySelectorAll('th'));
                    let idx = ths.findIndex(th => /cliente/i.test(th.textContent) && !/perfil/i.test(th.textContent));
                    if (idx < 0) continue;
                    for (const tr of t.querySelectorAll('tbody tr')) {
                        if (!tr.textContent.includes(numero)) continue;
                        const tds = Array.from(tr.querySelectorAll('td'));
                        const offset = Math.max(0, tds.length - ths.length);
                        const cel = tds[idx + offset] || tds[idx];
                        if (cel) return (cel.textContent || '').trim();
                    }
                }
                return null;
            }""",
            numero,
        )
        if nome:
            page.get_by_text(nome, exact=False).first.click(timeout=4000)
            return True
    except Exception:
        pass

    # D) Fallback: duplo clique na linha.
    try:
        if linha is not None:
            linha.dblclick(timeout=3000)
            return True
    except Exception:
        pass

    return False


def _resumo_item(texto):
    """Transforma o texto cru da linha (que vem com o menu ☰) num resumo
    legivel: nome do projeto, medida e vidro. Retorna (ordem, resumo)."""
    import re
    tokens = [t.strip() for t in re.split(r"\s*\|\s*|\n", texto) if t.strip()]
    # remove entradas do menu (icones fa-)
    tokens = [t for t in tokens if "fa-" not in t and "fa fa" not in t.lower()]
    ordem, lh, vidro = "", "", ""
    projeto_parts = []
    for t in tokens:
        if not ordem and t.isdigit():
            ordem = t
            continue
        if re.search(r"\d+\s*[xX]\s*\d+", t):
            lh = t
            continue
        if "MM" in t.upper() and any(v in t.upper() for v in (
            "INCOLOR", "BRONZE", "FUME", "FUMÊ", "VERDE", "AZUL",
            "ACIDATO", "REFLETIVO", "TEMPERADO", "COMUM")):
            vidro = t
            continue
        if lh:  # nome do projeto vem ANTES da medida; depois sao Tipo/Local/etc
            continue
        if re.search(r"[A-Za-zÁÉÍÓÚÂÊÔÃÕÇ]", t) and not re.match(r"^[\d.,]+$", t):
            projeto_parts.append(t)
    projeto = " ".join(projeto_parts).strip(" .")
    partes = []
    if projeto:
        partes.append(projeto)
    if lh:
        partes.append(f"medida {lh}")
    if vidro:
        partes.append(f"vidro {vidro}")
    return ordem, ("  |  ".join(partes) if partes else texto)


def ler_itens(page):
    """Le a tabela 'DETALHE DO ORCAMENTO' e mostra os itens encontrados."""
    log("Lendo os itens do orcamento...")
    page.wait_for_timeout(1500)

    itens = []
    try:
        linhas = page.locator("table tbody tr")
        total = linhas.count()
        for i in range(total):
            texto = linhas.nth(i).inner_text().strip()
            # linhas de item tem "JANELA", "PORTA", etc. Filtro simples:
            if texto and any(p in texto.upper() for p in ("JANELA", "PORTA", "VIDRO", "MODULO", "GUARDA")):
                _ordem, resumo = _resumo_item(texto)
                itens.append(resumo)
    except Exception as e:
        log(f"Nao consegui ler a tabela: {e}")

    print()
    print("-" * 60)
    if itens:
        print(f"  Itens encontrados no orcamento ({len(itens)}):")
        print("-" * 60)
        for idx, it in enumerate(itens, 1):
            print(f"  Item {idx}: {it}")
    else:
        print("  Nao consegui identificar os itens automaticamente.")
        print("  (Um print foi salvo -- me manda que eu ajusto o robo.)")
    print("-" * 60)
    print()
    return itens


# ── Alteracoes: trocar vidro de um item ───────────────────────────────────────────

def _linhas_itens(page):
    """Retorna as linhas (locators) que sao itens de projeto do orcamento,
    na ordem em que aparecem."""
    resultado = []
    try:
        linhas = page.locator("table tbody tr")
        for i in range(linhas.count()):
            linha = linhas.nth(i)
            try:
                txt = linha.inner_text().upper()
            except Exception:
                continue
            if any(p in txt for p in ("JANELA", "PORTA", "MODULO", "GUARDA")):
                resultado.append(linha)
    except Exception:
        pass
    return resultado


def _abrir_menu_item(page, linha_item):
    """Abre o menu ☰ da linha do item."""
    for sel in ("i[class*='fa-bars']", "[class*='fa-bars']", "button", "td"):
        try:
            linha_item.locator(sel).first.click(timeout=2500)
            page.wait_for_timeout(700)
            return True
        except Exception:
            continue
    return False


def _clicar_texto_visivel(page, texto, timeout=6000):
    """Clica no PRIMEIRO elemento VISIVEL que contem o texto. O W-Vetro mantem
    uma copia escondida do menu para cada item; so a aberta fica visivel."""
    import time as _t
    fim = _t.time() + timeout / 1000
    while _t.time() < fim:
        loc = page.get_by_text(texto, exact=False)
        try:
            n = loc.count()
        except Exception:
            n = 0
        for i in range(n):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    el.scroll_into_view_if_needed()
                    el.click(timeout=2000)
                    return True
            except Exception:
                continue
        page.wait_for_timeout(300)
    return False


def _achar_select_vidro(page):
    """Localiza o <select> do campo 'VIDRO COR'. Procura em TODOS os frames,
    porque a janela de edicao do W-Vetro abre dentro de um iframe."""
    # espera um pouco para o iframe carregar
    page.wait_for_timeout(1500)
    for fr in page.frames:
        # A) o select logo apos o texto "VIDRO COR"
        try:
            s = fr.locator(
                "xpath=//*[contains(text(),'VIDRO COR')]/following::select[1]"
            ).first
            if s.count() > 0:
                return s
        except Exception:
            pass
        # B) qualquer select cujas opcoes pareçam de vidro
        try:
            selects = fr.locator("select")
            total = selects.count()
            for i in range(min(total, 80)):
                s = selects.nth(i)
                try:
                    txt = (s.inner_text() or "").upper()
                except Exception:
                    txt = ""
                if any(v in txt for v in ("TEMPERADO", "COMUM", "INCOLOR")):
                    return s
        except Exception:
            pass
    return None


def editar_item(page, linha_item, indice=None):
    """Abre 'Editar Item do Orc.' e permite alterar varios campos do mesmo
    item (vidro, cor, largura, altura, quantidade, tipo, ambiente) num menu.
    No fim, confirma e salva (passando pela janela de variaveis se aparecer)."""
    rotulo = f"item {indice}" if indice else "item"
    log(f"Abrindo o {rotulo} para editar...")
    if not _abrir_menu_item(page, linha_item):
        log("Nao consegui abrir o menu (☰) do item.")
        return False

    # Clica em "Editar Item do Orç." (a opcao VISIVEL do menu que abriu).
    if not _clicar_texto_visivel(page, "Editar Item do Or", timeout=6000):
        log("Nao encontrei a opcao 'Editar Item do Orç.' visivel.")
        print_tela(page, "sem_editar_item")
        return False

    page.wait_for_timeout(1800)
    print_tela(page, "editar_item_modal")

    frame = _frame_do_modal(page)
    if frame is None:
        log("Nao encontrei a janela de edicao do item.")
        print_tela(page, "sem_modal_edicao")
        return False

    mudou = False
    while True:
        print()
        print("  O que alterar neste item?")
        print("    1) Vidro")
        print("    2) Cor (aluminio/perfil)")
        print("    3) Largura")
        print("    4) Altura")
        print("    5) Quantidade")
        print("    6) Tipo (ex: J01)")
        print("    7) Ambiente / Localizacao")
        print("    0) Terminar e SALVAR")
        op = input("  Opcao: ").strip()

        if op == "1":
            mudou = _trocar_select_campo(frame, "VIDRO COR", "vidro", "vidro") or mudou
        elif op == "2":
            mudou = _trocar_select_campo(frame, "PERFIL", "cor (aluminio/perfil)", "cor") or mudou
        elif op == "3":
            mudou = _trocar_input_campo(frame, "LARGURA", "largura") or mudou
        elif op == "4":
            mudou = _trocar_input_campo(frame, "ALTURA", "altura") or mudou
        elif op == "5":
            mudou = _trocar_input_campo(frame, "QTDE", "quantidade") or mudou
        elif op == "6":
            mudou = _trocar_input_campo(frame, "TIPO", "tipo", exato=True) or mudou
        elif op == "7":
            mudou = _trocar_input_campo(frame, "AMBIENTE", "ambiente/localizacao") or mudou
        elif op == "0":
            break
        else:
            print("  Opcao invalida.")

    if not mudou:
        print("  Nenhuma alteracao feita -- fechando sem salvar.")
        _fechar_modal(page)
        return False

    print()
    print("  >> CONFIRA as alteracoes na tela do W-Vetro.")
    resp = input("  ENTER para CONFIRMAR e salvar  |  N para cancelar: ").strip().lower()
    if resp == "n":
        print("  Cancelado -- fechando sem salvar.")
        _fechar_modal(page)
        return False

    # Confirma a janela de edicao e, se aparecer, a janela de variaveis
    # ('Informar Medidas/Quantidades' nos itens com motor/persiana).
    if not _confirmar_edicao(page):
        log("Alguma janela nao fechou sozinha (edicao ou variaveis).")
        print_tela(page, "variaveis_travou")
        input("  Confira/feche na tela e aperte ENTER...  ")

    log("Alteracoes confirmadas e salvas. ✔")
    page.wait_for_timeout(1500)
    return True


def _frame_do_modal(page, esperar=True, diagnostico=False):
    """Retorna o frame (pagina ou iframe) cujos campos da janela de edicao
    estao VISIVEIS. Exigir a visibilidade descarta as copias antigas/mortas
    que ficam na memoria apos recarregar (elas existem mas nao aparecem).

    IMPORTANTE: quando o W-Vetro recalcula (troca de cor/vidro) sobram varias
    copias do MESMO texto ('VIDRO COR', 'PERFIL'...). Por isso testamos a
    visibilidade de TODAS as ocorrencias, nao so da primeira -- se olhassemos
    so a primeira e ela fosse uma copia morta, perderiamos a janela viva."""
    # Varias ancoras (basta UMA visivel). Assim, se um rotulo mudar de nome,
    # ainda achamos a janela por outro.
    chaves = ("VIDRO COR", "ALUMINIO/PERFIL", "PERFIL", "QTDE",
              "Dados do Item", "FERRAGENS", "NOME PROJETO")
    tentativas = 15 if esperar else 3
    for t in range(tentativas):
        if esperar and t == 0:
            page.wait_for_timeout(1500)
        for fr in page.frames:
            for chave in chaves:
                try:
                    loc = fr.locator(f"xpath=//*[contains(text(),'{chave}')]")
                    n = loc.count()
                    for i in range(min(n, 25)):
                        try:
                            if loc.nth(i).is_visible():
                                return fr
                        except Exception:
                            continue
                except Exception:
                    continue
        page.wait_for_timeout(800)
    if diagnostico:
        _diagnostico_frames(page)
    return None


def _diagnostico_frames(page):
    """Quando NAO achamos a janela, imprime o que o robo esta vendo em cada
    frame -- ajuda a descobrir por que a janela de edicao nao foi detectada."""
    marcas = ("VIDRO COR", "ALUMINIO/PERFIL", "PERFIL", "QTDE", "Dados do Item",
              "FERRAGENS", "NOME PROJETO", "Confirmar", "Fechar", "Editar Item")
    print("     ---- diagnostico (o que o robo ve) ----")
    try:
        frames = page.frames
    except Exception:
        frames = []
    print(f"     frames abertos: {len(frames)}")
    for idx, fr in enumerate(frames):
        achados = []
        for m in marcas:
            try:
                loc = fr.locator(f"xpath=//*[contains(text(),'{m}')]")
                n = loc.count()
                if n == 0:
                    continue
                vis = 0
                for i in range(min(n, 25)):
                    try:
                        if loc.nth(i).is_visible():
                            vis += 1
                    except Exception:
                        pass
                achados.append(f"{m}({vis}vis/{n})")
            except Exception:
                continue
        if achados:
            try:
                url = fr.url[-45:]
            except Exception:
                url = "?"
            print(f"     frame[{idx}] ...{url}: " + ", ".join(achados))
    print("     ----------------------------------------")


def _esperar_recalculo(page, timeout=9000):
    """Depois de trocar cor/vidro o W-Vetro RECALCULA e RECARREGA a janela.
    Em vez de esperar um tempo fixo (que as vezes e curto demais, as vezes
    longo demais), esperamos ativamente a janela viva reaparecer e devolvemos
    o frame novo. Assim o proximo campo ja e aplicado na janela certa."""
    import time as _t
    # da um instante para o recalculo COMECAR (a janela some por um momento)
    page.wait_for_timeout(900)
    fim = _t.time() + timeout / 1000
    while _t.time() < fim:
        fr = _frame_do_modal(page, esperar=False)
        if fr is not None:
            # confirma estabilidade: continua visivel depois de um respiro
            page.wait_for_timeout(400)
            if _frame_do_modal(page, esperar=False) is not None:
                return fr
        page.wait_for_timeout(400)
    return _frame_do_modal(page, esperar=False)


def _opcoes_do_select(sel):
    """Le os textos das opcoes de um <select>."""
    try:
        return [o.strip() for o in sel.locator("option").all_inner_texts() if o.strip()]
    except Exception:
        return []


FINISH_WORDS = ("PINTURA", "ANODIZADO", "BRANCO", "PRETO", "BRONZE", "MADEIRA",
                "NATURAL", "FOSCO", "CINZA", "GRAFITE", "CHAMPAGNE", "CORTEN",
                "BRILHANTE", "AMADEIRADO", "BICOLOR", "LOURO")


def _parece_vidro(opcoes):
    """True se as opcoes parecem de vidro (tem espessura 'MM' + tipo)."""
    if not opcoes:
        return False
    n = sum(1 for o in opcoes if "MM" in o.upper()
            and any(t in o.upper() for t in ("TEMPERADO", "COMUM", "LAMINADO", "REFLETIVO")))
    return n >= max(3, len(opcoes) // 2)


def _parece_cor(opcoes):
    """True se as opcoes parecem de cor/perfil (varias opcoes de acabamento)."""
    if len(opcoes) < 3:
        return False
    return any(any(w in o.upper() for w in FINISH_WORDS) for o in opcoes)


def _candidatos_campo(frame, rotulo, tag, exato=False):
    """Devolve locators candidatos ao campo (input/select) do rotulo, olhando
    primeiro DENTRO do mesmo bloco do rotulo e depois vizinhos (antes/depois)."""
    base = (f"//*[normalize-space(text())='{rotulo}']" if exato
            else f"//*[contains(text(),'{rotulo}')]")
    cands = []
    for xp in (f"xpath={base}/ancestor::*[.//{tag}][1]//{tag}[1]",
               f"xpath={base}/following::{tag}[1]",
               f"xpath={base}/preceding::{tag}[1]",
               f"xpath={base}/following::{tag}[2]"):
        try:
            loc = frame.locator(xp).first
            if loc.count() > 0:
                cands.append(loc)
        except Exception:
            pass
    return cands


def _visivel(loc):
    """True se o locator existe e esta visivel (sem estourar excecao)."""
    try:
        return loc.count() > 0 and loc.first.is_visible()
    except Exception:
        return False


# Variantes de rotulo (o nome exato pode variar no W-Vetro).
ROTULOS = {
    "LARGURA":  ["LARGURA"],
    "ALTURA":   ["ALTURA"],
    "QTDE":     ["QTDE", "QUANTIDADE"],
    "TIPO":     ["TIPO"],
    "AMBIENTE": ["AMBIENTE/LOCALIZACAO", "AMBIENTE/LOCALIZAÇÃO", "AMBIENTE"],
    "PERFIL":   ["ALUMINIO/PERFIL", "ALUMÍNIO/PERFIL", "PERFIL"],
    "VIDRO COR": ["VIDRO COR", "VIDRO/COR", "VIDRO"],
}

# JS que acha o campo (input/select/textarea) mais proximo de um rotulo.
# Robusto a: texto aninhado, espaco nao-quebravel, ordem invertida (campo
# ANTES do rotulo) e rotulos-cabecalho (ex.: secao "Largura" com MINIMA/MAXIMA).
_JS_CAMPO = r"""
(args) => {
  const {rotulos, tag} = args;
  const norm = s => (s||'').replace(/ /g,' ').replace(/\s+/g,' ').trim().toUpperCase();
  const alvos = rotulos.map(norm);
  const vis = el => {
    if(!el) return false;
    const s = getComputedStyle(el);
    if (s.display==='none' || s.visibility==='hidden') return false;
    return el.getClientRects().length > 0;
  };
  // 1) escolhe o melhor elemento-rotulo (pontuando especificidade)
  let melhores = [];
  const cand = document.querySelectorAll('label,span,div,td,th,p,b,strong,font,li');
  for (const el of cand){
    const t = norm(el.textContent);
    if(!t || t.length>45) continue;
    for (const a of alvos){
      if(!t.includes(a)) continue;
      let score = 2;
      if (t===a || t===a+' *') score += 12;
      else if (t.startsWith(a+' ') || t.startsWith(a+'/') || t.startsWith(a+':')) score += 8;
      else if (t.startsWith(a)) score += 6;
      if (t.includes('*')) score += 3;
      score -= el.querySelectorAll('*').length*0.2 + t.length*0.03;
      melhores.push({el, score});
      break;
    }
  }
  if(!melhores.length) return null;
  melhores.sort((a,b)=> b.score - a.score);
  // 2) do melhor rotulo, sobe ancestrais ate achar um campo visivel
  const globalList = Array.prototype.slice.call(document.querySelectorAll(tag));
  for (const m of melhores.slice(0,6)){
    let node = m.el;
    for (let up=0; up<6 && node; up++, node=node.parentElement){
      const fs = Array.prototype.slice.call(node.querySelectorAll(tag))
                  .filter(f => vis(f) && !f.disabled && !f.readOnly);
      if(fs.length){
        const idx = globalList.indexOf(fs[0]);
        if(idx>=0) return idx;
      }
    }
  }
  return null;
}
"""


def _campo_por_js(frame, rotulo_chave, tag):
    """Acha o campo via JS (mais confiavel). Retorna locator Playwright ou None."""
    rotulos = ROTULOS.get(rotulo_chave, [rotulo_chave])
    try:
        idx = frame.evaluate(_JS_CAMPO, {"rotulos": rotulos, "tag": tag})
    except Exception:
        idx = None
    if idx is None or idx < 0:
        return None
    try:
        loc = frame.locator(tag).nth(idx)
        return loc if loc.count() > 0 else None
    except Exception:
        return None


def _achar_select(frame, rotulo, esperado):
    """Acha o <select> certo do rotulo. 1o tenta pelo ROTULO via JS (o vizinho
    do texto 'VIDRO COR' / 'ALUMINIO/PERFIL'); confere pelo CONTEUDO. Se nao
    der, cai no metodo antigo por conteudo das opcoes."""
    # 1) pelo rotulo (JS) -- so aceita se o conteudo confere com o esperado
    loc = _campo_por_js(frame, rotulo, "select")
    if loc is not None and _visivel(loc):
        ops = _opcoes_do_select(loc)
        if (esperado == "vidro" and _parece_vidro(ops)) or \
           (esperado == "cor" and _parece_cor(ops)) or not ops:
            return loc

    # 2) metodo antigo (por conteudo das opcoes)
    cands = _candidatos_campo(frame, rotulo, "select")
    batem = []
    for c in cands:
        ops = _opcoes_do_select(c)
        if esperado == "vidro" and _parece_vidro(ops):
            batem.append(c)
        elif esperado == "cor" and _parece_cor(ops):
            batem.append(c)
    for c in batem:
        if _visivel(c):
            return c
    if batem:
        return batem[0]
    # 3) por ULTIMO: varre TODOS os selects do frame pelo conteudo
    if loc is not None:
        return loc
    try:
        todos = frame.locator("select")
        for i in range(min(todos.count(), 80)):
            s = todos.nth(i)
            ops = _opcoes_do_select(s)
            if esperado == "vidro" and _parece_vidro(ops) and _visivel(s):
                return s
            if esperado == "cor" and _parece_cor(ops) and _visivel(s):
                return s
    except Exception:
        pass
    for c in cands:
        if _visivel(c):
            return c
    return cands[0] if cands else None


def _achar_input(frame, rotulo, exato=False):
    """Acha o <input> do rotulo. 1o tenta pelo ROTULO via JS (robusto),
    senao cai no metodo antigo por xpath."""
    loc = _campo_por_js(frame, rotulo, "input")
    if loc is not None and _visivel(loc):
        return loc
    cands = _candidatos_campo(frame, rotulo, "input", exato=exato)
    for c in cands:
        if _visivel(c):
            return c
    if loc is not None:
        return loc
    return cands[0] if cands else None


def _trocar_select_campo(frame, rotulo, nome, esperado):
    """Troca um campo do tipo lista (select) mostrando as opcoes numeradas."""
    sel = _achar_select(frame, rotulo, esperado)
    if sel is None or sel.count() == 0:
        print(f"  Nao encontrei o campo {nome}.")
        return False

    opcoes = [o for o in _opcoes_do_select(sel) if "SELECIONE" not in o.upper()]
    if not opcoes:
        print(f"  Nao consegui ler as opcoes de {nome}.")
        return False

    print(f"\n  Opcoes de {nome}:")
    for i, o in enumerate(opcoes, 1):
        print(f"    {i:2d}) {o}")
    esc = input(f"  Numero do(a) {nome} (Enter cancela): ").strip()
    if not esc.isdigit() or not (1 <= int(esc) <= len(opcoes)):
        print("  (cancelado)")
        return False

    escolhido = opcoes[int(esc) - 1]
    try:
        sel.select_option(label=escolhido)
    except Exception as e:
        print(f"  Nao consegui selecionar: {e}")
        return False
    print(f"  {nome} -> {escolhido}")
    return True


def _trocar_input_campo(frame, label, nome, exato=False):
    """Troca um campo de digitacao (largura, altura, qtde, tipo, ambiente)."""
    inp = _achar_input(frame, label, exato)
    if inp is None:
        print(f"  Nao encontrei o campo {nome}.")
        return False

    atual = ""
    try:
        atual = inp.input_value()
    except Exception:
        pass
    novo = input(f"  Novo valor de {nome} (atual: '{atual}', Enter cancela): ").strip()
    if not novo:
        print("  (cancelado)")
        return False
    try:
        inp.scroll_into_view_if_needed()
        inp.click()
        inp.fill(novo)
    except Exception as e:
        print(f"  Nao consegui alterar: {e}")
        return False
    print(f"  {nome} -> {novo}")
    return True


def _confirmares_visiveis(page):
    """Retorna a lista de elementos 'Confirmar'/'CONFIRMAR' VISIVEIS de todos
    os frames (ignora 'CONFIRMAR VENDA', pois casa so com 'confirmar')."""
    import re
    alvo = re.compile(r"^\s*confirmar\s*$", re.I)
    encontrados = []
    for fr in page.frames:
        for getter in ("role", "text"):
            try:
                loc = (fr.get_by_role("button", name=alvo) if getter == "role"
                       else fr.get_by_text(alvo))
                for i in range(loc.count()):
                    e = loc.nth(i)
                    try:
                        if e.is_visible():
                            encontrados.append(e)
                    except Exception:
                        pass
            except Exception:
                pass
    return encontrados


def _clicar_confirmar_modal(page):
    """Clica no primeiro botao 'Confirmar' visivel de uma janela."""
    for e in _confirmares_visiveis(page):
        try:
            e.scroll_into_view_if_needed()
            e.click(timeout=3000)
            return True
        except Exception:
            continue
    return False


def _tem_texto_visivel(page, texto):
    """Diz se algum elemento com esse texto esta visivel (em qualquer frame)."""
    for fr in page.frames:
        try:
            loc = fr.get_by_text(texto, exact=False)
            for i in range(loc.count()):
                if loc.nth(i).is_visible():
                    return True
        except Exception:
            pass
    return False


# Marcas de texto que identificam cada janela (confirmadas no sistema real).
MARCAS_MODAL_EDICAO = ("VIDRO COR", "ALUMINIO/PERFIL", "Dados do Item")
# A janela de variaveis pode se chamar de dois jeitos, dependendo do item:
#   - itens com motor/persiana: "Informar Medidas/Quantidades"
#   - outros casos: "Informe as variaveis"
# Por isso reconhecemos VARIAS marcas (uma basta).
MARCAS_JANELA_VARIAVEIS = ("Informar Medidas", "Informe as vari",
                           "SALVAR VARI", "Medidas em MM")


def _modal_edicao_aberto(page):
    return any(_tem_texto_visivel(page, m) for m in MARCAS_MODAL_EDICAO)


def _janela_variaveis_aberta(page):
    return any(_tem_texto_visivel(page, m) for m in MARCAS_JANELA_VARIAVEIS)


def _confirmar_edicao(page, max_tentativas=8):
    """Confirma a edicao do item ate TODAS as janelas fecharem:
      1) a janela 'Dados do Item' (edicao), e
      2) a janela de variaveis, que em itens com motor/persiana se chama
         'Informar Medidas/Quantidades' (nao 'Informe as variaveis'!).
    O botao pode ser 'Confirmar' ou 'CONFIRMAR' -- os dois casam. Damos um
    respiro apos o 1o clique porque a janela de variaveis demora a aparecer."""
    clicou_algo = False
    for i in range(max_tentativas):
        modal = _modal_edicao_aberto(page)
        vari = _janela_variaveis_aberta(page)
        if not modal and not vari:
            # Ja fechou tudo? Se acabamos de clicar, espera um pouco para ver
            # se a janela de variaveis ainda vai surgir (itens com motor).
            if clicou_algo and i <= 2:
                page.wait_for_timeout(1500)
                if _janela_variaveis_aberta(page):
                    continue
            return True
        if _clicar_confirmar_modal(page):
            clicou_algo = True
            page.wait_for_timeout(1800)
        else:
            page.wait_for_timeout(800)
    return not _modal_edicao_aberto(page) and not _janela_variaveis_aberta(page)


def _fechar_modal(page):
    """Fecha a janela de edicao sem salvar (botao 'Fechar' ou o X)."""
    for fr in page.frames:
        try:
            btn = fr.get_by_role("button", name="Fechar", exact=True)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click(timeout=2500)
                return True
        except Exception:
            pass
    return False


# ── Modo mensagem: aplicar varias alteracoes a partir de um texto colado ─────────

import re as _re

CORES_PERFIL = ("pintura", "anodizado", "anod", "branco", "preto", "bronze",
                "natural", "fosco", "madeira", "cinza", "grafite", "champagne",
                "amadeirado", "corten", "brilhante", "bicolor", "louro")

CORES_VIDRO = {"incolor": "INCOLOR", "verde": "VERDE", "bronze": "BRONZE",
               "fume": "FUME", "fumê": "FUME", "azul": "AZUL", "acidato": "ACIDATO"}


def _descreve_vidro(spec):
    """Descricao amigavel do vidro (cor=INCOLOR e tipo=TEMPERADO por padrao)."""
    low = spec.lower()
    cor = "INCOLOR"
    for k, v in CORES_VIDRO.items():
        if k in low:
            cor = v
            break
    m = _re.search(r"(\d{1,2})", low)
    esp = m.group(1).zfill(2) if m else None
    tipo = "COMUM" if "comum" in low else "TEMPERADO"
    return f"{cor} {esp}MM - {tipo}" if esp else spec.upper()


def parse_mensagem(texto):
    """Le a mensagem e devolve (orcamento, {item: {campo: valor}})."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    orcamento = None
    itens = {}
    for l in linhas:
        m = _re.search(r"or[çc]amento\s*[:#nºo\.]*\s*(\d{2,7})", l, _re.I)
        if m and orcamento is None:
            orcamento = m.group(1)
            continue
        mi = _re.match(r"^\s*(\d{1,3})\s*[-–:]\s*(.+)$", l)
        if not mi:
            if orcamento is None and _re.match(r"^\d{2,7}$", l):
                orcamento = l
            continue
        num = mi.group(1)
        mud, ambiente = {}, []
        for p in _re.split(r"\s*[-–]\s*", mi.group(2)):
            p = p.strip()
            if not p:
                continue
            low = p.lower()
            md = _re.search(r"(\d{2,4})\s*[xX]\s*(\d{2,4})", p)
            if md:
                mud["largura"], mud["altura"] = md.group(1), md.group(2)
                continue
            mq = _re.search(r"(\d+)\s*un\b", low) or _re.search(r"qtde?\s*[:]?\s*(\d+)", low)
            if mq:
                mud["qtde"] = mq.group(1)
                continue
            if "vidro" in low:
                mud["vidro"] = _re.sub(r"vidro", "", low, flags=_re.I).strip()
                continue
            if _re.match(r"^[a-z]{1,2}\s*\d{1,3}$", low):
                mud["tipo"] = _re.sub(r"\s+", "", p).upper()
                continue
            if any(w in low for w in CORES_PERFIL):
                mud["cor"] = p.strip()
                continue
            ambiente.append(p.strip())
        if ambiente:
            mud["ambiente"] = " ".join(ambiente)
        itens[num] = mud
    return orcamento, itens


CAMPOS_PREVIEW = (("cor", "cor"), ("largura", "largura"), ("altura", "altura"),
                  ("qtde", "quantidade"), ("vidro", "vidro"),
                  ("tipo", "tipo"), ("ambiente", "ambiente"))


def _mostrar_preview(orc, itens):
    print()
    print("  " + "=" * 56)
    print(f"  ENTENDI ASSIM (orcamento {orc}):")
    print("  " + "=" * 56)
    for num, mud in itens.items():
        print(f"\n  ITEM {num}:")
        for chave, nome in CAMPOS_PREVIEW:
            if chave in mud:
                val = _descreve_vidro(mud[chave]) if chave == "vidro" else mud[chave]
                print(f"     {nome:11s}-> {val}")
        mantem = [n for c, n in CAMPOS_PREVIEW if c not in mud]
        if mantem:
            print(f"     (mantem: {', '.join(mantem)})")
    print("  " + "=" * 56)


def _pontua_vidro(opcao, termo):
    ou = opcao.upper().replace(" ", "")
    low = termo.lower()
    cor = "INCOLOR"
    for k, v in CORES_VIDRO.items():
        if k in low:
            cor = v
            break
    score = 0
    if cor in opcao.upper():
        score += 2
    m = _re.search(r"(\d{1,2})", low)
    tem_esp = False
    if m:
        d = m.group(1)
        if f"{d}MM" in ou or f"{d.zfill(2)}MM" in ou:
            score += 3
            tem_esp = True
    tipo = "COMUM" if "comum" in low else "TEMPERADO"
    if tipo in opcao.upper():
        score += 2
    return score if tem_esp else -1


def _melhor_opcao(opcoes, termo, esperado):
    if esperado == "vidro":
        pont = [(o, _pontua_vidro(o, termo)) for o in opcoes]
    else:
        palavras = [w for w in _re.split(r"\s+", termo.upper()) if len(w) > 2]
        pont = [(o, sum(1 for w in palavras if w in o.upper())) for o in opcoes]
    pont = [x for x in pont if x[1] > 0]
    if not pont:
        return None, False
    pont.sort(key=lambda x: x[1], reverse=True)
    melhor, s1 = pont[0]
    s2 = pont[1][1] if len(pont) > 1 else -1
    return melhor, (s1 > s2)


def _set_select_auto(frame, rotulo, esperado, termo, nome):
    sel = _achar_select(frame, rotulo, esperado)
    if sel is None:
        print(f"     [!] nao achei o campo {nome}")
        return False
    opcoes = [o for o in _opcoes_do_select(sel) if "SELECIONE" not in o.upper()]
    if not opcoes:
        print(f"     [!] sem opcoes de {nome}")
        return False
    escolha, claro = _melhor_opcao(opcoes, termo, esperado)
    if escolha is None or not claro:
        print(f"\n     Em duvida no {nome} para '{termo}'. Escolha:")
        for i, o in enumerate(opcoes, 1):
            print(f"       {i:2d}) {o}")
        r = input("       Numero (Enter pula): ").strip()
        if not r.isdigit() or not (1 <= int(r) <= len(opcoes)):
            print(f"     ({nome} nao alterado)")
            return False
        escolha = opcoes[int(r) - 1]
    try:
        sel.select_option(label=escolha)
    except Exception as e:
        print(f"     [!] {nome}: {e}")
        return False

    # Confere se a escolha realmente ficou marcada (o recalculo as vezes reverte).
    try:
        marcado = (sel.locator("option:checked").first.inner_text() or "").strip()
    except Exception:
        marcado = ""
    if marcado and marcado != escolha:
        print(f"     [!] {nome}: pedi '{escolha}' mas ficou '{marcado}'.")
        return False
    print(f"     {nome} -> {escolha}")
    return True


def _set_input_auto(frame, rotulo, valor, nome, exato=False):
    inp = _achar_input(frame, rotulo, exato)
    if inp is None:
        print(f"     [!] nao achei o campo {nome}")
        return False
    try:
        inp.scroll_into_view_if_needed()
        inp.click()
        inp.fill(str(valor))
        print(f"     {nome} -> {valor}")
        return True
    except Exception as e:
        print(f"     [!] {nome}: {e}")
        return False


def _itens_por_ordem(page):
    """Mapa {numero_do_item (coluna Ord.): linha_locator}."""
    mapa = {}
    try:
        linhas = page.locator("table tbody tr")
        for i in range(linhas.count()):
            linha = linhas.nth(i)
            try:
                txt = linha.inner_text()
            except Exception:
                continue
            if not any(p in txt.upper() for p in ("JANELA", "PORTA", "MODULO", "GUARDA")):
                continue
            ordem, _ = _resumo_item(txt)
            if ordem:
                mapa[ordem] = linha
    except Exception:
        pass
    return mapa


def _abrir_edicao_item(page, linha_item, num, tentativas=3):
    """Abre o menu do item, clica em 'Editar Item do Orc.' e devolve o frame
    da janela 'Dados do Item'. TENTA DE NOVO se a janela nao aparecer -- as
    vezes o 1o clique nao abre, ou a janela demora a carregar no iframe."""
    for tent in range(1, tentativas + 1):
        if tent > 1:
            print(f"     (tentativa {tent} de abrir a janela do item {num}...)")
        if not _abrir_menu_item(page, linha_item):
            print(f"     [!] nao abri o menu (☰) do item {num}")
            page.wait_for_timeout(800)
            continue
        if not _clicar_texto_visivel(page, "Editar Item do Or", timeout=6000):
            print(f"     [!] nao achei 'Editar Item do Orç.' do item {num}")
            print_tela(page, f"auto_sem_editar_{num}")
            page.wait_for_timeout(800)
            continue
        # Espera a janela abrir (paciente) e diagnostica na ultima tentativa.
        frame = _frame_do_modal(page, esperar=True, diagnostico=(tent == tentativas))
        if frame is not None:
            return frame
        # nao abriu: tira print, fecha o que tiver e tenta outra vez.
        print_tela(page, f"auto_sem_modal_{num}_t{tent}")
        _fechar_modal(page)
        page.wait_for_timeout(1200)
        # fecha tambem por ESC, caso o Fechar nao pegue
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(800)
    return None


def _preencher_campos_item(page, frame, mud):
    """Preenche os campos do item na janela 'Dados do Item'. Antes de CADA
    campo reencontra a janela VIVA, para nunca escrever numa copia morta."""
    def _frame_vivo():
        return _frame_do_modal(page, esperar=False) or frame

    # Campos DIGITADOS primeiro: a janela esta fresca e eles nao recarregam.
    if "largura" in mud:
        _set_input_auto(_frame_vivo(), "LARGURA", mud["largura"], "largura")
    if "altura" in mud:
        _set_input_auto(_frame_vivo(), "ALTURA", mud["altura"], "altura")
    if "qtde" in mud:
        _set_input_auto(_frame_vivo(), "QTDE", mud["qtde"], "quantidade")
    if "tipo" in mud:
        _set_input_auto(_frame_vivo(), "TIPO", mud["tipo"], "tipo", exato=True)
    if "ambiente" in mud:
        _set_input_auto(_frame_vivo(), "AMBIENTE", mud["ambiente"], "ambiente")

    # Cor e vidro por ULTIMO (recarregam a janela). Reencontra a janela ANTES
    # de cada um e ESPERA o recalculo terminar DEPOIS de cada um.
    if "cor" in mud:
        _set_select_auto(_frame_vivo(), "PERFIL", "cor", mud["cor"], "cor")
        frame = _esperar_recalculo(page) or frame
    if "vidro" in mud:
        _set_select_auto(_frame_vivo(), "VIDRO COR", "vidro", mud["vidro"], "vidro")
        frame = _esperar_recalculo(page) or frame
    return frame


def aplicar_item_auto(page, linha_item, num, mud):
    """Modo AUTOMATICO: preenche e confirma sozinho."""
    print(f"\n  >> Item {num}:")
    frame = _abrir_edicao_item(page, linha_item, num)
    if frame is None:
        print(f"     [!] nao achei a janela de edicao do item {num}")
        print(f"         (veja o diagnostico acima e o print auto_sem_modal_{num}*)")
        return False

    _preencher_campos_item(page, frame, mud)

    print_tela(page, f"auto_item_{num}")
    # Confirma a janela de edicao e, se aparecer, a de variaveis
    # ('Informar Medidas/Quantidades') -- clica ate tudo fechar.
    if _confirmar_edicao(page):
        print(f"     item {num} salvo. ✔")
    else:
        print(f"     [!] item {num}: alguma janela nao fechou sozinha.")
        print_tela(page, f"auto_confirmar_travou_{num}")
    page.wait_for_timeout(1500)
    return True


def aplicar_item_semi_auto(page, linha_item, num, mud):
    """Modo SEGURO: o robo abre e PREENCHE os campos, mas VOCE confere e
    clica Confirmar (e passa pela janela de variaveis). Bem mais confiavel,
    porque a parte que mais falha (confirmar/variaveis) fica com voce."""
    print(f"\n  >> Item {num}: abrindo e preenchendo...")
    frame = _abrir_edicao_item(page, linha_item, num)
    if frame is None:
        print(f"     [!] nao achei a janela de edicao do item {num}")
        print(f"         (veja o diagnostico acima e o print auto_sem_modal_{num}*)")
        return False

    _preencher_campos_item(page, frame, mud)
    print_tela(page, f"semi_item_{num}")

    print()
    print("  " + "=" * 58)
    print(f"  ITEM {num} PREENCHIDO PELO ROBO. Agora, NA TELA DO W-VETRO:")
    print("    1) CONFIRA os campos (ajuste na mao se algo ficou errado).")
    print("    2) Clique em CONFIRMAR.")
    print("    3) Se abrir 'Informar Medidas/Quantidades',")
    print("       clique CONFIRMAR nela tambem.")
    print("  " + "=" * 58)
    input("  Quando o item estiver SALVO, aperte ENTER aqui p/ o proximo...  ")
    return True


def clicar_calcular(page):
    """Depois de alterar itens, o W-Vetro mostra 'Orcamento Nao Calculado --
    clique em Calcular'. Esta funcao clica no botao 'Calcular' VISIVEL (em
    qualquer frame) para atualizar os valores. Retorna True se conseguiu."""
    alvo = _re.compile(r"^\s*calcular\s*$", _re.I)
    for _tent in range(3):
        for fr in page.frames:
            for getter in ("role", "text"):
                try:
                    loc = (fr.get_by_role("button", name=alvo) if getter == "role"
                           else fr.get_by_text(alvo))
                    for i in range(loc.count()):
                        e = loc.nth(i)
                        try:
                            if e.is_visible():
                                e.scroll_into_view_if_needed()
                                e.click(timeout=3000)
                                page.wait_for_timeout(3000)
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue
        page.wait_for_timeout(800)
    return False


def modo_mensagem(page):
    """Le uma mensagem colada, mostra o que entendeu, confirma e aplica."""
    print()
    print("Cole a mensagem (pode ter varias linhas).")
    print("Ao terminar, deixe uma linha VAZIA e aperte ENTER (ou digite FIM):")
    linhas = []
    while True:
        try:
            ln = input()
        except EOFError:
            break
        if ln.strip().upper() == "FIM":
            break
        if ln.strip() == "" and linhas:
            break
        if ln.strip():
            linhas.append(ln)
    texto = "\n".join(linhas)
    if not texto.strip():
        print("  (mensagem vazia)")
        return

    orc, itens = parse_mensagem(texto)
    if not orc:
        print("  Nao achei o numero do orcamento na mensagem.")
        return
    if not itens:
        print("  Nao achei itens para alterar na mensagem.")
        return

    _mostrar_preview(orc, itens)
    r = input("\n  Esta certo? ENTER para APLICAR  |  N para cancelar: ").strip().lower()
    if r == "n":
        print("  Cancelado.")
        return

    # Escolha do modo. O SEGURO e mais confiavel: o robo preenche e voce
    # confere/confirma. Recomendado enquanto o automatico nao esta 100%.
    print()
    print("  Como aplicar?")
    print("    S) Modo SEGURO  - o robo preenche, VOCE confere e clica Confirmar (recomendado)")
    print("    A) Modo AUTOMATICO - o robo faz tudo sozinho (pode falhar no Confirmar)")
    modo = input("  Opcao [S/A] (Enter = S): ").strip().lower()
    semi = (modo != "a")
    print(f"  -> Modo {'SEGURO' if semi else 'AUTOMATICO'} escolhido.")

    if not abrir_orcamento(page, orc):
        print("  Nao consegui abrir o orcamento.")
        return

    for num, mud in itens.items():
        mapa = _itens_por_ordem(page)
        linha = mapa.get(str(num))
        if linha is None:
            print(f"  [!] item {num} nao existe neste orcamento.")
            continue
        try:
            if semi:
                aplicar_item_semi_auto(page, linha, num, mud)
            else:
                aplicar_item_auto(page, linha, num, mud)
        except Exception as e:
            print(f"  [!] erro inesperado no item {num}: {e}")
            print_tela(page, f"erro_item_{num}")
        page.wait_for_timeout(1200)

    # Ao final, o W-Vetro precisa RECALCULAR os valores do orcamento.
    print("\n  Atualizando os valores (Calcular)...")
    if clicar_calcular(page):
        print("  Cliquei em Calcular -- valores atualizados. ✔")
    else:
        print("  (Nao achei o botao 'Calcular'. Se aparecer 'Orcamento Nao")
        print("   Calculado' na tela, clique em Calcular manualmente.)")

    print("\n  Pronto! Alteracoes da mensagem aplicadas. ✔")


def menu_alteracoes(page):
    """Depois de abrir o orcamento, oferece editar um item."""
    while True:
        itens = _linhas_itens(page)
        if not itens:
            return
        print()
        resp = input(f"Editar algum item? (numero 1 a {len(itens)}, ou Enter para sair): ").strip()
        if not resp:
            return
        if not resp.isdigit() or not (1 <= int(resp) <= len(itens)):
            print("  Numero de item invalido.")
            continue
        editar_item(page, itens[int(resp) - 1], int(resp))
        # volta ao detalhe do orcamento para poder editar outro item
        page.wait_for_timeout(1200)


# ── Programa principal ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("   EGEMAP - Robo de Alteracao de Orcamentos")
    print("   Abre o orcamento e edita o item: vidro, cor, largura, altura,")
    print("   quantidade, tipo e ambiente. Voce confirma antes de salvar.")
    print("=" * 60)
    print()

    with sync_playwright() as p:
        # Usa o Google Chrome ja instalado (channel="chrome") com um perfil
        # dedicado, para nao precisar baixar navegador nem mexer no seu Chrome.
        try:
            contexto = p.chromium.launch_persistent_context(
                user_data_dir=str(PERFIL_DIR),
                channel="chrome",
                headless=False,
                args=["--start-maximized"],
                no_viewport=True,
            )
        except Exception as e:
            log(f"Nao consegui abrir o Chrome (channel=chrome): {e}")
            log("Tentando com o navegador padrao do Playwright...")
            contexto = p.chromium.launch_persistent_context(
                user_data_dir=str(PERFIL_DIR),
                headless=False,
                no_viewport=True,
            )

        page = contexto.pages[0] if contexto.pages else contexto.new_page()

        try:
            garantir_login(page)

            while True:
                print()
                print("O que deseja fazer?")
                print("  1) Colar uma MENSAGEM (varias alteracoes de uma vez)")
                print("  2) Editar um orcamento MANUALMENTE (passo a passo)")
                print("  0) Sair")
                op = input("Opcao: ").strip().lower()

                if op in ("0", "sair", "s", "exit", "q"):
                    break
                elif op == "1":
                    modo_mensagem(page)
                elif op == "2":
                    numero = input("Numero do orcamento: ").strip()
                    if not numero.isdigit():
                        print("  Digite so o numero (ex: 2346).")
                        continue
                    if abrir_orcamento(page, numero):
                        ler_itens(page)
                        menu_alteracoes(page)
                    else:
                        print("  Nao consegui abrir esse orcamento sozinho.")
                        print(f"  Veja os prints em: {PRINTS_DIR}")
                else:
                    print("  Opcao invalida.")

        finally:
            print()
            input("Aperte ENTER para fechar o navegador...")
            contexto.close()

    print("\nRobo encerrado.")


if __name__ == "__main__":
    main()
