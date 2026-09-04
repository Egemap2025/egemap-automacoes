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

# Palavras de produto (fallback). O sinal PRINCIPAL de que uma linha e um item
# e ter o menu ☰ (fa-bars); os nomes abaixo sao so um reforco.
PALAVRAS_ITEM = ("JANELA", "PORTA", "MODULO", "MÓDULO", "GUARDA", "BOX",
                 "FIXO", "PAINEL", "FACHADA", "GRADIL", "PORTAO", "PORTÃO",
                 "TAMPO", "ESPELHO", "BASCULANTE", "MAXIM", "VENEZIANA",
                 "PIVOTANTE", "BANDEIRA", "CORRER", "SACADA", "VITRINE",
                 "ESQUADRIA", "SOLENE", "PELE DE VIDRO", "PERSIANA")


def _eh_linha_item(linha):
    """Diz se a linha da tabela e um ITEM de projeto. O sinal mais confiavel e
    ter o menu de acoes ☰ (fa-bars); se nao der, cai nos nomes de produto ou
    numa medida (LxA). Assim funciona para QUALQUER tipo de produto."""
    try:
        if linha.locator("[class*='fa-bars'], i[class*='bars']").count() > 0:
            return True
    except Exception:
        pass
    try:
        txt = linha.inner_text().upper()
    except Exception:
        return False
    if any(p in txt for p in PALAVRAS_ITEM):
        return True
    return bool(_re.search(r"\d+\s*[xX]\s*\d+", txt))


def _linhas_itens(page):
    """Retorna as linhas (locators) que sao itens de projeto do orcamento,
    na ordem em que aparecem."""
    resultado = []
    try:
        linhas = page.locator("table tbody tr")
        for i in range(linhas.count()):
            linha = linhas.nth(i)
            if _eh_linha_item(linha):
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
    # cadastro de cliente (tela 'Cadastro Rapido' / 'Cadastro Completo')
    "NOME":       ["NOME COMPLETO", "NOME"],
    "EMAIL":      ["EMAIL", "E-MAIL"],
    "TELEFONE":   ["TELEFONE FIXO", "TELEFONE"],
    "CELULAR":    ["CELULAR"],
    "CPF":        ["CPF/CNPJ", "CPF", "CNPJ"],
    "CEP":        ["CEP"],
    "RUA":        ["RUA", "ENDERECO", "ENDEREÇO", "LOGRADOURO"],
    "NUMERO":     ["NRO.", "NRO", "NÚMERO", "NUMERO"],
    "BAIRRO":     ["BAIRRO"],
    "COMPLEMENTO": ["COMPLEMENTO"],
    "CIDADE":     ["CIDADE", "MUNICIPIO", "MUNICÍPIO"],
    "UF":         ["UF", "ESTADO"],
    "VENDEDOR":   ["VENDEDOR", "RESPONSAVEL", "RESPONSÁVEL"],
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


def _clicar_forte(e):
    """Tenta clicar de varios jeitos (normal, forcado, via JS). Retorna True
    se algum funcionou. Usado quando um clique simples nao pega."""
    try:
        e.scroll_into_view_if_needed()
    except Exception:
        pass
    for metodo in ("normal", "forcado", "js"):
        try:
            if metodo == "normal":
                e.click(timeout=2500)
            elif metodo == "forcado":
                e.click(timeout=2000, force=True)
            else:
                e.evaluate("el => el.click()")
            return True
        except Exception:
            continue
    return False


def _clicar_confirmar_modal(page):
    """Clica no primeiro botao 'Confirmar' visivel de uma janela."""
    for e in _confirmares_visiveis(page):
        if _clicar_forte(e):
            return True
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
                           "SALVAR VARI", "Medidas em MM",
                           "ACIONAMENTO DA ESTEIRA", "PASSO DAS PALHETAS",
                           "TAMANHO DA PALHETA", "VOLTAGEM DO MOTOR")


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

        # Ao trocar cor/vidro sobram COPIAS MORTAS da janela, cada uma com um
        # 'Confirmar' fantasma. Por isso NAO clicamos so no primeiro: tentamos
        # CADA 'Confirmar' visivel e, apos cada clique, conferimos se o estado
        # mudou (alguma janela fechou). Assim uma hora acertamos o botao vivo.
        confirmares = _confirmares_visiveis(page)
        if not confirmares:
            page.wait_for_timeout(800)
            continue
        estado = (modal, vari)
        for e in confirmares:
            if not _clicar_forte(e):
                continue
            clicou_algo = True
            page.wait_for_timeout(1500)
            novo = (_modal_edicao_aberto(page), _janela_variaveis_aberta(page))
            if novo != estado:
                break  # algo mudou -- re-avalia do inicio do laco
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

# Nomes especiais de vidro (aparecem como cor/nome na lista do W-Vetro).
NOMES_VIDRO = [("mini-boreal", "MINI-BOREAL"), ("mini boreal", "MINI-BOREAL"),
               ("boreal", "BOREAL"), ("pontilhado", "PONTILHADO"),
               ("quadrato", "QUADRATO"), ("canelado", "CANELADO"),
               ("float", "FLOAT"), ("refletivo", "REFLETIVO"),
               ("laminado", "LAMINADO")]

# Palavras que indicam que a parte da mensagem e um VIDRO (nao ambiente/cor).
VIDRO_TIPOS = ("temperado", "comum", "laminado", "refletivo", "acidato", "insulado")
VIDRO_NOMES = ("incolor", "verde", "fume", "fumê", "bronze", "azul", "cinza",
               "boreal", "mini-boreal", "pontilhado", "quadrato", "canelado",
               "float", "antelio", "prata")


def _parece_spec_vidro(low):
    """Diz se a parte da mensagem parece a especificacao de um VIDRO, pelo
    conteudo (nao exige a palavra 'vidro'). Ex.: 'incolor 8mm temperado',
    'mini-boreal 04mm comum', 'vidro 6 temperado'."""
    if "vidro" in low:
        return True
    if _re.search(r"\d\s*mm", low):            # tem espessura em 'mm'
        return True
    if any(t in low for t in VIDRO_TIPOS):     # temperado/comum/laminado...
        return True
    # nome/cor de vidro + um numero (espessura sem 'mm', ex.: 'incolor 6')
    if any(n in low for n in VIDRO_NOMES) and _re.search(r"\d", low):
        return True
    return False


def _descreve_vidro(spec):
    """Descricao amigavel do vidro para o preview. Detecta nome/cor
    (incolor por padrao), espessura e tipo (temperado/comum/laminado)."""
    low = spec.lower()
    nome = None
    for k, v in NOMES_VIDRO:
        if k in low:
            nome = v
            break
    if nome is None:
        nome = "INCOLOR"
        for k, v in CORES_VIDRO.items():
            if k in low:
                nome = v
                break
    m = _re.search(r"(\d{1,2})", low)
    esp = m.group(1).zfill(2) if m else None
    if "comum" in low:
        tipo = "COMUM"
    elif "temperado" in low:
        tipo = "TEMPERADO"
    elif "laminado" in low:
        tipo = "LAMINADO"
    else:
        tipo = "TEMPERADO"  # padrao quando nao dito
    partes = [nome]
    if esp:
        partes.append(f"{esp}MM")
    desc = " ".join(partes)
    return f"{desc} - {tipo}"


# Palavras que identificam a LINHA na mensagem de substituicao.
LINHA_KWS = ("deluxe", "versatic", "solene", "intensive", "hydro", "perfisud",
             "guarda-corpo", "guarda corpo", "corrimão", "corrimao", "portão",
             "portao", "portões", "portoes", "ripados", "fachada", "citta",
             "vidro temperado", "l.30", "l. 30")


def _eh_linha(low):
    return any(k in low for k in LINHA_KWS)


def _eh_acionamento(low):
    return ("motor" in low) or ("recolhedor" in low) or low in ("fita", "cordao", "cordão")


def _norm_acionamento(low):
    """Normaliza o acionamento pedido para casar com a lista de variaveis."""
    if "fita" in low:
        return "RECOLHEDOR FITA"
    if "cordão" in low or "cordao" in low:
        return "RECOLHEDOR CORDÃO"
    if "motor" in low:
        return "MOTOR"
    if "recolhedor" in low:
        return "RECOLHEDOR FITA"
    return "MOTOR"


def _classificar_parte(p, mud, ambiente):
    """Classifica UMA parte da mensagem (medida/qtde/vidro/tipo/cor/ambiente)
    e guarda em mud/ambiente. Reutilizado na alteracao e na substituicao."""
    p = p.strip()
    if not p:
        return
    low = p.lower()
    # medida largura x altura
    md = _re.search(r"(\d{2,4})\s*[xX]\s*(\d{2,4})", p)
    if md:
        mud["largura"], mud["altura"] = md.group(1), md.group(2)
        return
    # quantidade: 2un / 2und / 2 unidades / 3 itens / 2 pecas / qtde 2
    mq = (_re.search(r"(\d+)\s*un[a-z]*\b", low)
          or _re.search(r"qtde?\s*[:]?\s*(\d+)", low)
          or _re.search(r"(\d+)\s*(?:itens?|item|pe[cç]as?|pcs?)\b", low))
    if mq:
        mud["qtde"] = mq.group(1)
        return
    # vidro: reconhecido pelo CONTEUDO (nao exige a palavra 'vidro')
    if _parece_spec_vidro(low):
        mud["vidro"] = _re.sub(r"\bvidro\b", "", low, flags=_re.I).strip()
        return
    # tipo (ex.: j01, pj01) -- ate 3 letras + numero
    if _re.match(r"^[a-z]{1,3}\s*\d{1,3}$", low):
        mud["tipo"] = _re.sub(r"\s+", "", p).upper()
        return
    # cor do perfil (pintura, anodizado, preto...)
    if any(w in low for w in CORES_PERFIL):
        mud["cor"] = p.strip()
        return
    # o que sobrar e ambiente/localizacao
    ambiente.append(p.strip())


def parse_mensagem(texto):
    """Le a mensagem e devolve (orcamento, {item: {campo: valor}}).
    Suporta ALTERAR campos e SUBSTITUIR o projeto do item ('substituir por')."""
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
        conteudo = mi.group(2)
        mud, ambiente = {}, []

        # SUBSTITUIR PROJETO. Aceita varios jeitos de escrever:
        #   'substituir projeto - <modelo> - ...' 'substituir por <modelo> - ...'
        #   'substituir - <modelo> - ...'         'substituir <modelo> - ...'
        #   'trocar projeto por/para <modelo>...' 'trocar por/para <modelo> - ...'
        # (o 'trocar' exige por/para p/ nao confundir com 'trocar vidro'.)
        # O '(?:projeto)?' consome a palavra 'Projeto' de 'Substituir Projeto'.
        m_sub = _re.match(r"^\s*substituir(?:\s+projeto)?\b\s*(?:por|para)?\s*[-–]?\s*(.*)$",
                          conteudo, _re.I)
        if not m_sub:
            m_sub = _re.match(r"^\s*troc(?:ar|a)(?:\s+projeto)?\b\s*(?:por|para)\s*[-–]?\s*(.*)$",
                              conteudo, _re.I)
        if m_sub:
            mud["substituir"] = True
            partes = [p.strip() for p in _re.split(r"\s+[-–]\s+", m_sub.group(1)) if p.strip()]
            # o 1o campo depois de 'substituir' e o MODELO (verbatim, sem
            # classificar -- pode ser 'vidro fixo', 'janela de correr...', etc.)
            mud["modelo"] = partes[0] if partes else ""
            for p in partes[1:]:
                low = p.lower()
                # 'linha 25' / 'linha versatic 25' -> linha (tira a palavra 'linha')
                ml = _re.match(r"^\s*linha\s+(.+)$", p, _re.I)
                if ml:
                    mud["linha"] = ml.group(1).strip()
                elif _eh_linha(low):
                    mud["linha"] = p
                elif _eh_acionamento(low):
                    mud["acionamento"] = _norm_acionamento(low)
                else:
                    _classificar_parte(p, mud, ambiente)
            if ambiente:
                mud["ambiente"] = " ".join(ambiente)
            # acionamento padrao MOTOR so faz sentido em item com persiana/esteira
            if _re.search(r"persiana|integrad|rol[oôõ]|esteira|motor",
                          mud.get("modelo", "").lower()):
                mud.setdefault("acionamento", "MOTOR")
        else:
            # ALTERAR campos do item existente.
            for p in _re.split(r"\s+[-–]\s+", conteudo):
                _classificar_parte(p, mud, ambiente)
            if ambiente:
                mud["ambiente"] = " ".join(ambiente)

        itens[num] = mud
    return orcamento, itens


def _spec_item_novo(descricao):
    """Le UMA linha de item novo (montar do zero) e devolve um 'mud'.
    Formato: '[codigo] descricao do modelo - cor - vidro - ambiente - ...'
    Ex.: 'j01 janela 02 folhas e tela com persiana com motor l32 -
          branco brilhante - incolor 6mm temperado - quartos'
    O 1o pedaco (antes do 1o ' - ') e a DESCRICAO/MODELO. Dela tiramos
    o codigo (j01), a linha (l32/linha 25) e o acionamento (motor).
    Os demais pedacos (separados por ' - ') sao classificados: cor, vidro,
    medida, quantidade, ambiente."""
    mud, ambiente = {}, []
    partes = [p.strip() for p in _re.split(r"\s+[-–]\s+", descricao) if p.strip()]
    if not partes:
        return None
    desc = partes[0]

    # codigo no comeco: j01 / pj02 / p3 (vira 'tipo' e sai da descricao)
    mcod = _re.match(r"^\s*([a-z]{1,3}\s*\d{1,3})\b\s*(.*)$", desc, _re.I)
    if mcod:
        mud["tipo"] = _re.sub(r"\s+", "", mcod.group(1)).upper()
        resto = mcod.group(2).strip()
        if resto:
            desc = resto

    # linha embutida na descricao: 'l32' / 'l25' / 'linha 25' / 'linha suprema 25'
    ml = _re.search(r"\blinha\s+([a-z0-9 ]+?)(?=\s+-|\s*$)", desc, _re.I)
    if ml:
        mud["linha"] = ml.group(1).strip()
        desc = _re.sub(r"\blinha\s+" + _re.escape(ml.group(1).strip()), "", desc,
                       flags=_re.I).strip()
    else:
        ml2 = _re.search(r"\bl\s*(\d{2})\b", desc, _re.I)
        if ml2:
            mud["linha"] = ml2.group(1)
            desc = _re.sub(r"\bl\s*" + ml2.group(1) + r"\b", "", desc,
                           flags=_re.I).strip()

    # 'sem persiana' -> tira 'persiana' da descricao (senao o card casaria com
    # um desenho COM persiana). Vira uma janela comum (vidro/moveis).
    if _re.search(r"\bsem\s+persiana\b", desc, _re.I):
        desc = _re.sub(r"\bsem\s+persiana\b", " ", desc, flags=_re.I).strip()

    # folhas por extenso -> numero (duas folhas -> 02 folhas), para casar tanto
    # o MODELO quanto o card certo (os cards mostram '02 FOLHAS', '03 FOLHAS'...)
    _NUMEXT = {"uma": "01", "um": "01", "duas": "02", "dois": "02",
               "tres": "03", "quatro": "04", "cinco": "05", "seis": "06"}
    def _rep_folhas(m):
        return _NUMEXT[_sem_acento(m.group(1).lower())] + " folhas"
    desc = _re.sub(r"\b(uma|um|duas|dois|tr[eê]s|quatro|cinco|seis)\s+folhas?\b",
                   _rep_folhas, desc, flags=_re.I)
    # numero de 1 digito -> 2 digitos ('4 folhas' -> '04 folhas'), igual aos cards
    desc = _re.sub(r"\b(\d)\s+folhas?\b",
                   lambda m: m.group(1).zfill(2) + " folhas", desc, flags=_re.I)

    # acionamento embutido: motor / manual (persiana SEM 'motor' fica sem
    # acionamento -> o W-Vetro usa o padrao, que e recolhedor).
    if _re.search(r"\bmotor(?:izad[oa])?\b", desc, _re.I):
        mud["acionamento"] = "MOTOR"
    elif _re.search(r"\bmanual\b", desc, _re.I):
        mud["acionamento"] = "MANUAL"

    # quantidade embutida na descricao: '2un' / '3 pecas' / 'qtd 2' (nao pega
    # '2 folhas' -- exige marcador un/peca/qtd para nao confundir com folhas).
    mqd = (_re.search(r"\b(\d+)\s*un[a-z]*\b", desc, _re.I)
           or _re.search(r"\bqtde?\s*[:]?\s*(\d+)\b", desc, _re.I)
           or _re.search(r"\b(\d+)\s*pe[cç]as?\b", desc, _re.I))
    if mqd:
        mud["qtde"] = mqd.group(1)
        desc = (desc[:mqd.start()] + " " + desc[mqd.end():]).strip()

    mud["modelo"] = _re.sub(r"\s+", " ", desc).strip()

    # demais campos (cor / vidro / medida / qtde / ambiente)
    for p in partes[1:]:
        low = p.lower()
        if _eh_linha(low):
            mud["linha"] = p
        elif _eh_acionamento(low):
            mud["acionamento"] = _norm_acionamento(low)
        else:
            _classificar_parte(p, mud, ambiente)
    if ambiente:
        mud["ambiente"] = " ".join(ambiente)

    # QUANTIDADE e obrigatoria no W-Vetro -- padrao 1 se nao vier na mensagem
    # (o vendedor ajusta depois se precisar de mais de 1).
    mud.setdefault("qtde", "1")
    return mud


def parse_montar(texto):
    """Le uma mensagem de MONTAR ORCAMENTO DO ZERO e devolve
    (orcamento, [lista de muds na ordem]). Cada linha (fora o cabecalho) e
    um item NOVO a ser adicionado. O cabecalho traz o numero do orcamento
    (ex.: 'Montar orcamento 2346')."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    orcamento = None
    itens = []
    for l in linhas:
        m = _re.search(r"or[çc]amento\s*[:#nºo\.]*\s*(\d{2,7})", l, _re.I)
        if m and orcamento is None:
            orcamento = m.group(1)
            # se a linha for SO o cabecalho (montar orcamento NNNN), pula
            if _re.match(r"^\s*montar\b", l, _re.I) or _re.search(
                    r"^\s*or[çc]amento\b", l, _re.I):
                continue
        if _re.match(r"^\s*(montar|novo)\s+or[çc]amento\b", l, _re.I):
            continue
        if orcamento is None and _re.match(r"^\d{2,7}$", l):
            orcamento = l
            continue
        if _campo_cliente(l):        # linha 'Cliente:'/'Rua:'... nao e item
            continue
        if _re.match(r"^\s*itens?\s*[:]?\s*$", l, _re.I):   # cabecalho 'Itens:'
            continue
        spec = _spec_item_novo(l)
        if spec and spec.get("modelo"):
            itens.append(spec)
    return orcamento, itens


# campos do cadastro do cliente reconhecidos na mensagem ('Campo: valor')
_CLI_CAMPOS = {
    "nome":        ["nome", "cliente", "nome completo"],
    "email":       ["email", "e-mail"],
    "telefone":    ["telefone", "tel fixo", "telefone fixo", "fixo"],
    "celular":     ["celular", "cel", "whatsapp", "zap", "fone", "telefone celular"],
    "cpf":         ["cpf", "cnpj", "cpf/cnpj"],
    "cep":         ["cep"],
    "rua":         ["rua", "endereco", "endereço", "logradouro"],
    "numero":      ["numero", "número", "nro", "nro.", "n", "num"],
    "bairro":      ["bairro"],
    "complemento": ["complemento", "referencia", "referência", "ponto de referencia", "obs"],
    "cidade":      ["cidade", "municipio", "município", "cidade/uf"],
    "uf":          ["uf", "estado"],
    "vendedor":    ["vendedor", "responsavel", "responsável"],
}

# sigla -> nome do estado (como aparece na lista UF do W-Vetro)
_UF_NOME = {
    "SC": "SANTA CATARINA", "RS": "RIO GRANDE DO SUL", "PR": "PARANA",
    "SP": "SAO PAULO", "RJ": "RIO DE JANEIRO", "MG": "MINAS GERAIS",
    "PA": "PARA", "BA": "BAHIA", "GO": "GOIAS", "ES": "ESPIRITO SANTO",
    "MS": "MATO GROSSO DO SUL", "MT": "MATO GROSSO", "DF": "DISTRITO FEDERAL",
}


def _campo_cliente(linha):
    """Se a linha for 'Campo: valor' de um dado de cliente, devolve (campo, valor);
    senao None. Ex.: 'Cliente: Natanael' -> ('nome','Natanael')."""
    m = _re.match(r"^\s*([A-Za-zÀ-ÿ/ ]{2,20}?)\s*[:=]\s*(.+?)\s*$", linha)
    if not m:
        return None
    rot = _sem_acento(m.group(1).strip().lower())
    val = m.group(2).strip()
    for campo, aliases in _CLI_CAMPOS.items():
        if rot in [_sem_acento(a) for a in aliases]:
            return (campo, val)
    return None


def parse_cliente(texto):
    """Le os dados do cliente da mensagem (linhas 'Campo: valor'). Devolve um
    dict (nome, celular, telefone, email, cpf, cep, rua, numero, bairro,
    complemento, cidade, vendedor) -- so com o que veio."""
    cli = {}
    for l in texto.splitlines():
        cv = _campo_cliente(l)
        if cv:
            cli[cv[0]] = cv[1]
    return cli


CAMPOS_PREVIEW = (("cor", "cor"), ("largura", "largura"), ("altura", "altura"),
                  ("qtde", "quantidade"), ("vidro", "vidro"),
                  ("tipo", "tipo"), ("ambiente", "ambiente"))


def _mostrar_preview(orc, itens):
    print()
    print("  " + "=" * 56)
    print(f"  ENTENDI ASSIM (orcamento {orc}):")
    print("  " + "=" * 56)
    for num, mud in itens.items():
        if mud.get("substituir"):
            print(f"\n  ITEM {num}: >>> SUBSTITUIR PROJETO <<<")
            print(f"     modelo      -> {mud.get('modelo') or '(nao informado!)'}")
            print(f"     linha       -> {mud.get('linha','(nao informada!)')}")
            if "acionamento" in mud:
                print(f"     acionamento -> {mud['acionamento']}")
            # campos informados que serao aplicados no projeto novo
            for chave, nome in CAMPOS_PREVIEW:
                if chave in mud:
                    val = _descreve_vidro(mud[chave]) if chave == "vidro" else mud[chave]
                    print(f"     {nome:11s} -> {val}")
            print("     (vidro/tipo/ambiente/medida: mantem o do item atual,")
            print("      exceto o que voce informou acima)")
            continue
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
    """Pontua o quanto uma opcao da lista casa com o termo do vidro pedido.
    Espessura (mm) e obrigatoria; pontua tambem tipo (temperado/comum/laminado)
    e nome/cor (incolor, verde, boreal, refletivo...)."""
    o = opcao.upper()
    ou = o.replace(" ", "")
    low = termo.lower()
    score = 0

    # espessura em mm (obrigatoria) -- ex.: '8' -> aceita '8MM' ou '08MM'
    m = _re.search(r"(\d{1,2})", low)
    tem_esp = False
    if m:
        d = m.group(1)
        if f"{d}MM" in ou or f"{d.zfill(2)}MM" in ou:
            score += 3
            tem_esp = True
    if not tem_esp:
        return -1

    # tipo
    for t in ("COMUM", "TEMPERADO", "LAMINADO"):
        if t.lower() in low and t in o:
            score += 2

    # nome/cor do vidro citado no termo e presente na opcao
    citou_nome = False
    for w in VIDRO_NOMES:
        if w in low:
            citou_nome = True
            if w.replace("-", "").upper() in ou or w.upper() in o:
                score += 2
    # se o termo nao citou nome/cor, prefere INCOLOR (padrao)
    if not citou_nome and "INCOLOR" in o:
        score += 1
    return score


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
            if not _eh_linha_item(linha):
                continue
            try:
                txt = linha.inner_text()
            except Exception:
                continue
            ordem, _ = _resumo_item(txt)
            if ordem and ordem not in mapa:
                mapa[ordem] = linha
    except Exception:
        pass
    return mapa


def _abrir_edicao_item(page, linha_item, num, tentativas=3):
    """Abre o menu do item, clica em 'Editar Item do Orc.' e devolve o frame
    da janela 'Dados do Item'. TENTA DE NOVO se a janela nao aparecer -- as
    vezes o 1o clique nao abre, ou a janela demora a carregar no iframe."""
    # Proteção: se sobrou alguma janela aberta do item anterior, fecha antes
    # de tentar abrir este item (senao o menu ☰ fica bloqueado).
    if _modal_edicao_aberto(page) or _janela_variaveis_aberta(page):
        print("     (fechando janela que ficou aberta antes de continuar...)")
        if not _confirmar_edicao(page):
            _fechar_modal(page)
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
        page.wait_for_timeout(1000)

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
    ok = _confirmar_edicao(page)
    if ok:
        print(f"     item {num} salvo. ✔")
    else:
        print(f"     [!] item {num}: alguma janela nao fechou sozinha.")
        print_tela(page, f"auto_confirmar_travou_{num}")
    page.wait_for_timeout(1500)
    return ok


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
    print(f"  ITEM {num} PREENCHIDO PELO ROBO. CONFIRA na tela do W-Vetro.")
    print("  " + "=" * 58)
    print("    ENTER = o ROBO confirma e vai para o proximo item")
    print("    M     = VOCE confirma na mao (ajustar algo antes)")
    resp = input("  Opcao (Enter = robo confirma): ").strip().lower()

    if resp == "m":
        input("  Confirme/salve na tela e aperte ENTER quando terminar...  ")
        # Garante que nao ficou nenhuma janela aberta antes do proximo item.
        if _modal_edicao_aberto(page) or _janela_variaveis_aberta(page):
            _confirmar_edicao(page)
        return True

    # ENTER: o robo confirma (janela de edicao + variaveis, se aparecer).
    if _confirmar_edicao(page):
        print(f"     item {num} salvo. ✔")
    else:
        print(f"     [!] item {num}: nao consegui fechar as janelas.")
        print_tela(page, f"semi_confirmar_travou_{num}")
        input("  Feche/confirme na tela e aperte ENTER p/ continuar...  ")
    page.wait_for_timeout(1500)
    return True


# ── Substituir Projeto (trocar o item por outro modelo) ──────────────────────────

def _clicar_botao(page, texto_regex, timeout=6000):
    """Clica em um botao/elemento VISIVEL cujo texto casa com o regex (qualquer
    frame). Ex.: 'Sim', 'Fechar', 'Pesquisar', 'Incluir item no orcamento'."""
    import time as _t
    alvo = _re.compile(texto_regex, _re.I)
    fim = _t.time() + timeout / 1000
    while _t.time() < fim:
        for fr in page.frames:
            for getter in ("role", "text"):
                try:
                    loc = (fr.get_by_role("button", name=alvo) if getter == "role"
                           else fr.get_by_text(alvo))
                    for i in range(loc.count()):
                        e = loc.nth(i)
                        try:
                            if e.is_visible() and _clicar_forte(e):
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue
        page.wait_for_timeout(300)
    return False


def _clicar_botao_real(page, texto_regex, timeout=6000):
    """Como _clicar_botao, mas com CLIQUE REAL de mouse no MEIO do botao.
    Alguns botoes do W-Vetro (ex.: 'Incluir item no orcamento', 'Calcular o
    Orcamento') so respondem a clique REAL, nao ao clique sintetico. Prefere o
    MENOR texto que casa (o botao em si, nao um container em volta), visivel."""
    import time as _t
    alvo = _re.compile(texto_regex, _re.I)
    fim = _t.time() + timeout / 1000
    while _t.time() < fim:
        melhor, melhor_len = None, 10 ** 9
        for fr in page.frames:
            for getter in ("role", "text"):
                try:
                    loc = (fr.get_by_role("button", name=alvo) if getter == "role"
                           else fr.get_by_text(alvo))
                    n = loc.count()
                except Exception:
                    continue
                for i in range(n):
                    e = loc.nth(i)
                    try:
                        if not e.is_visible():
                            continue
                        t = (e.inner_text() or "").strip()
                        if 0 < len(t) < melhor_len:
                            melhor, melhor_len = e, len(t)
                    except Exception:
                        continue
        if melhor is not None:
            try:
                melhor.scroll_into_view_if_needed(timeout=2000)
                box = melhor.bounding_box()
            except Exception:
                box = None
            if box:
                x = box["x"] + box["width"] * 0.5
                y = box["y"] + box["height"] * 0.5
                try:
                    page.mouse.click(x, y)
                    return True
                except Exception:
                    pass
            if _clicar_forte(melhor):
                return True
        page.wait_for_timeout(300)
    return False


def _sem_acento(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


_STOP = {"com", "de", "da", "do", "e", "ou", "a", "o", "em", "no", "na", "para"}


def _melhor_opcao_texto(opcoes, termo):
    """Escolhe a opcao que mais compartilha palavras com o termo pedido
    (ignora acentos e palavras-cola tipo 'com'/'de')."""
    palavras = [w for w in _re.split(r"[^a-z0-9]+", _sem_acento(termo.lower()))
                if len(w) >= 2 and w not in _STOP]
    melhor, melhor_score = None, 0
    for o in opcoes:
        ol = _sem_acento(o.lower())
        s = sum(1 for w in palavras if w in ol)
        if s > melhor_score:
            melhor, melhor_score = o, s
    return melhor


def _folha_sfx(n):
    """'01 FOLHA' (singular) ou 'NN FOLHAS' (plural), como aparece na lista MODELO."""
    n = str(n).zfill(2)
    return f"{n} FOLHA" if n == "01" else f"{n} FOLHAS"


def _modelo_dropdown(descricao):
    """A partir da descricao solta do usuario decide qual MODELO escolher na
    lista do W-Vetro. A lista (linha L.30) tem: JANELA DE CORRER, JANELA
    PIVOTANTE, MAXIM-AR, MODULO FIXO, PORTA CAMARAO, PORTA DE CORRER, PORTA DE
    GIRO 01/02 FOLHA(S), PORTA PIVOTANTE (+01/02 FOLHA(S)), PORTAO DE CORRER 01
    FOLHA, PORTAS DE GIRO, PORTINHOLA, VENEZIANA. O card certo vem depois pelo
    texto (ex.: 'ripada' escolhe o desenho RIPADO, mas o MODELO e PORTA
    PIVOTANTE)."""
    low = _sem_acento(descricao.lower())
    mf = _re.search(r"(\d{1,2})\s*folhas?", low)
    folhas = mf.group(1).zfill(2) if mf else None
    tem_porta = "porta" in low
    tem_janela = "janela" in low

    # tipos que nao dependem de folhas
    # 'basculante' a EGEMAP faz como MAXIM-AR (confirmado pelo usuario)
    if "maxim" in low or "basculante" in low or "bascul" in low:
        return "MAXIM-AR"
    if "portinhola" in low:
        return "PORTINHOLA"
    if "veneziana" in low:
        return "VENEZIANA"
    if "camarao" in low:
        return "PORTA CAMARAO"

    # pivotante (porta OU janela)
    if "pivotante" in low or "pivot" in low:
        if tem_janela and not tem_porta:
            return "JANELA PIVOTANTE"
        # porta pivotante: se disse folhas usa o numerado, senao o generico
        # (a 'ripada' e um CARD dentro de PORTA PIVOTANTE, nao um MODELO)
        if folhas:
            return f"PORTA PIVOTANTE {_folha_sfx(folhas)}"
        return "PORTA PIVOTANTE"

    if tem_porta:
        # PORTA-JANELA (tem 'porta' E 'janela') = porta de correr (corre no
        # trilho, tipo janela). Ex.: 'porta janela 3 folhas', '... sequencial'.
        # Inclui o Nr de folhas (02/03/04...) senao o W-Vetro pega sempre a 1a
        # opcao (02 FOLHAS). Sem folhas informadas, assume 02.
        if tem_janela and "giro" not in low and "abrir" not in low:
            return f"PORTA DE CORRER {_folha_sfx(folhas or '02')}"
        # porta de giro / porta de abrir (interna/externa de abrir) -> PORTA DE GIRO
        if "giro" in low or "abrir" in low or "batente" in low:
            return f"PORTA DE GIRO {_folha_sfx(folhas or '01')}"
        # porta de correr: 'pra tras da parede' / 'portao' -> PORTAO DE CORRER 01 FOLHA
        if "correr" in low:
            if "tras" in low or "parede" in low or "portao" in low or "embutir" in low:
                return "PORTAO DE CORRER 01 FOLHA"
            return "PORTA DE CORRER"
        # porta sem tipo claro: internas costumam ser de giro/abrir
        return f"PORTA DE GIRO {_folha_sfx(folhas or '01')}"

    # fixo/painel/modulo (sem ser janela/porta) -> Modulo Fixo
    if "modulo" in low or "painel" in low or \
       ("fixo" in low and not tem_janela and not tem_porta):
        return "MODULO FIXO"

    return f"JANELA DE CORRER {_folha_sfx(folhas or '02')}"


_JS_MARCAR_CALCORC = r"""
() => {
  const nd = s => (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
  document.querySelectorAll('[data-egerobo="calcorc"]').forEach(e=>e.removeAttribute('data-egerobo'));
  const cands = Array.from(document.querySelectorAll('button,a,input,div,span'));
  let best=null, bl=1e9;
  for (const e of cands){
    const t = nd(e.textContent) + ' ' + nd(e.value||'');
    if (t.includes('calcular o or')){
      const r = e.getBoundingClientRect();
      if (r.width < 10 || r.height < 8) continue;
      const len = ((e.textContent||'') + (e.value||'')).trim().length;
      if (len < bl){ best=e; bl=len; }
    }
  }
  if (!best) return false;
  best.setAttribute('data-egerobo','calcorc');
  best.scrollIntoView({block:'center'});
  return true;
}
"""


def _clicar_calcular_orcamento(page, timeout=9000):
    """Clica no botao 'Calcular o Orcamento' (tela de selecao/cards), que VOLTA
    para o orcamento. Localiza via JS (getBoundingClientRect) e clica com MOUSE
    REAL no centro -- mesma tecnica que funciona no card. Retorna True se saiu
    da tela de selecao (mudou de URL)."""
    import time as _t
    fim = _t.time() + timeout / 1000
    while _t.time() < fim:
        try:
            achou = page.evaluate(_JS_MARCAR_CALCORC)
        except Exception:
            achou = False
        if achou:
            loc = page.locator('[data-egerobo="calcorc"]').first
            try:
                loc.scroll_into_view_if_needed(timeout=2000)
                box = loc.bounding_box()
            except Exception:
                box = None
            clicou = False
            if box:
                x = box["x"] + box["width"] * 0.5
                y = box["y"] + box["height"] * 0.5
                try:
                    page.mouse.click(x, y)
                    clicou = True
                except Exception:
                    clicou = False
            if not clicou:
                try:
                    loc.click(timeout=2000, force=True)
                    clicou = True
                except Exception:
                    clicou = False
            if clicou:
                # confirma que saiu da tela de selecao/dados
                f2 = _t.time() + 8
                while _t.time() < f2:
                    try:
                        u = (page.url or "").lower()
                        if "selecioneprojeto" not in u and "confirmadadosprojeto" not in u:
                            return True
                    except Exception:
                        pass
                    page.wait_for_timeout(500)
        page.wait_for_timeout(400)
    return False


def _definir_acionamento(page, valor):
    """Define o ACIONAMENTO DA ESTEIRA na janela de variaveis. Em vez de achar
    pelo rotulo (fica em outra celula, quebrado em 3 linhas: ACIONAMENTO/DA/
    ESTEIRA), acha o <select> pelas OPCOES: o unico que tem 'MOTOR' e
    'RECOLHEDOR'. Escolhe a opcao que casa com 'valor'. Retorna True se definiu."""
    for fr in page.frames:
        try:
            selects = fr.locator("select")
            n = selects.count()
        except Exception:
            continue
        for i in range(n):
            sel = selects.nth(i)
            try:
                if not sel.is_visible():
                    continue
                opcoes = _opcoes_do_select(sel)
            except Exception:
                continue
            low = [_sem_acento(o.lower()) for o in opcoes]
            if not (any("motor" in o for o in low) and
                    any("recolhedor" in o for o in low)):
                continue
            validas = [o for o in opcoes if o.strip()
                       and "SELECIONE" not in o.upper()]
            escolha = _melhor_opcao_texto(validas, valor) or validas[0]
            try:
                sel.select_option(label=escolha)
                page.wait_for_timeout(400)
                print(f"     acionamento -> {escolha}")
                return True
            except Exception:
                continue
    return False


def _selecionar_select_rotulo(page, rotulo, valor, nome):
    """Acha um <select> pelo ROTULO (em qualquer frame), seleciona a opcao que
    melhor casa com 'valor' e dispara o change. Retorna a opcao ou None."""
    for fr in page.frames:
        loc = _campo_por_js(fr, rotulo, "select")
        if loc is None or not _visivel(loc):
            continue
        opcoes = [o for o in _opcoes_do_select(loc) if o.strip()
                  and "SELECIONE" not in o.upper()]
        if not opcoes:
            continue
        escolha = _melhor_opcao_texto(opcoes, valor)
        if not escolha:
            continue
        try:
            loc.select_option(label=escolha)
            page.wait_for_timeout(500)
            print(f"     {nome} -> {escolha}")
            return escolha
        except Exception:
            continue
    print(f"     [!] nao consegui definir {nome} ('{valor}') automaticamente.")
    return None


def _esperar_url_ou_texto(page, url_parte=None, texto=None, timeout=15000):
    """Espera a pagina navegar (URL contem X) ou um texto aparecer."""
    import time as _t
    fim = _t.time() + timeout / 1000
    while _t.time() < fim:
        try:
            if url_parte and url_parte in page.url.lower():
                return True
        except Exception:
            pass
        if texto and _tem_texto_visivel(page, texto):
            return True
        page.wait_for_timeout(400)
    return False


def _frame_dados_projeto(page):
    """Frame da tela 'Detalhes do Projeto' (onde estao COR/VIDRO/etc)."""
    for fr in page.frames:
        try:
            if _campo_por_js(fr, "VIDRO COR", "select") is not None:
                return fr
        except Exception:
            continue
    return page.main_frame


# JS que escolhe o melhor card e MARCA nele atributos data-egerobo para o
# Playwright clicar depois (clique real, com auto-scroll). Pontua por palavras
# do modelo; codigo (ex.: 'ijcr200') vale muito. Desempata pelo card mais curto.
_JS_MARCAR_CARD = r"""
(args) => {
  const nd = s => (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
  const pal = args.palavras.map(nd);
  const ehCodigo = w => w.length >= 5 && /[0-9]/.test(w) && /[a-z]/.test(w);
  // limpa marcacoes antigas
  document.querySelectorAll('[data-egerobo]').forEach(e => e.removeAttribute('data-egerobo'));
  const nodes = Array.from(document.querySelectorAll('div,li,article,a,td,section'));
  let best=null, bestScore=-1, bestLen=1e9;
  for (const b of nodes){
    const t = nd(b.textContent);
    if (t.length < 6 || t.length > 500) continue;
    const pareceCard = t.includes('ege-') || t.includes('perf-') || t.includes('projeto com');
    if (!pareceCard) continue;
    let s = 0;
    for (const w of pal){ if (w.length >= 2 && t.includes(w)) s += ehCodigo(w) ? 20 : 1; }
    if (s > bestScore || (s === bestScore && t.length < bestLen)){
      best=b; bestScore=s; bestLen=t.length;
    }
  }
  if (!best || bestScore <= 0) return null;
  // O texto que casou costuma ser o '.card-body' (so titulo + 'Mais opcoes'),
  // que NAO contem a foto. Sobe ate o CARD inteiro (o ancestral que TEM <img>),
  // para podermos clicar na FOTO -- e nao no texto nem no botao vermelho.
  for (let n = best, i = 0; n && i < 6; n = n.parentElement, i++){
    try { if (n.querySelector && n.querySelector('img')) { best = n; break; } }
    catch(e){}
  }
  best.setAttribute('data-egerobo','card');
  // FOTO GRANDE do desenho: a MAIOR imagem do card (nao o logo pequeno).
  let bigImg=null, bigArea=0;
  for (const im of best.querySelectorAll('img')){
    const r = im.getBoundingClientRect();
    const area = r.width * r.height;
    if (area > bigArea){ bigArea = area; bigImg = im; }
  }
  if (bigImg) bigImg.setAttribute('data-egerobo','img');
  // NOME do projeto (titulo) -- NAO a linha do codigo nem 'PROJETO COM'
  // (evita clicar no botao vermelho 'Mais N opcoes de desenhos').
  let titEl=null, titScore=-1;
  for (const el of best.querySelectorAll('div,span,p,a,h1,h2,h3,h4,b,strong')){
    const tt = nd(el.textContent);
    if (!tt || tt.length > 120) continue;
    if (tt.includes('projeto com') || tt.includes('opcoes') || tt.includes('opções')) continue;
    if (/ege-|perf-/.test(tt) && tt.length < 22) continue;
    let sc = 0; for (const w of pal){ if (tt.includes(w)) sc++; }
    if (sc > titScore){ titScore = sc; titEl = el; }
  }
  if (titEl) titEl.setAttribute('data-egerobo','titulo');
  // Botao 'Mais N opcoes de desenhos' (abre o popup de variacoes -- necessario
  // p/ painel fixo 'N modulos'). Marcamos para clicar SE a foto nao abrir.
  let maisEl=null;
  for (const el of best.querySelectorAll('a,button,span,div,[onclick]')){
    const tt = nd(el.textContent);
    if (tt.length <= 45 && (tt.includes('opcoes') || tt.includes('opes de desenho') ||
        (tt.includes('mais') && tt.includes('desenho')))){ maisEl = el; break; }
  }
  if (maisEl) maisEl.setAttribute('data-egerobo','mais');
  // Elemento de ACAO: um <a>/onclick dentro do card (ou o proprio card), que
  // costuma ser o que dispara a navegacao ao clicar.
  let acaoEl = null;
  if (best.tagName === 'A' || best.getAttribute('onclick')) acaoEl = best;
  if (!acaoEl){
    for (const el of best.querySelectorAll('a,[onclick]')){
      const tt = nd(el.textContent);
      if (tt.includes('opcoes') || tt.includes('projeto com')) continue; // pula o botao vermelho
      acaoEl = el; break;
    }
  }
  if (acaoEl) acaoEl.setAttribute('data-egerobo','acao');
  best.scrollIntoView({block:'center'});
  let titulo = (best.textContent||'').replace(/\s+/g,' ').trim();
  if (titulo.length > 90) titulo = titulo.slice(0,90) + '...';
  // estrutura do card (para diagnostico quando o clique nao pegar)
  let html = (best.outerHTML||'').replace(/\s+/g,' ');
  if (html.length > 2500) html = html.slice(0,2500) + '...';
  return {score: bestScore, titulo, html};
}
"""


def _escolher_card_auto(page, modelo, num=""):
    """Escolhe e clica AUTOMATICAMENTE no card cujo titulo/codigo mais casa com
    o modelo. Marca o card via JS e clica com o Playwright (clique real, com
    auto-scroll). Mostra qual card escolheu. Retorna True se conseguiu navegar."""
    palavras = [w for w in _re.split(r"[^a-z0-9]+", _sem_acento(modelo.lower()))
                if len(w) >= 2 and w not in _STOP]
    # espera os cards de desenho carregarem (aparecem 'PROJETO COM' / codigo)
    import time as _t
    fim = _t.time() + 10
    while _t.time() < fim:
        try:
            if page.evaluate(
                    "() => /projeto com|ege-|perf-/i.test(document.body.innerText||'')"):
                break
        except Exception:
            pass
        page.wait_for_timeout(500)
    try:
        res = page.evaluate(_JS_MARCAR_CARD, {"palavras": palavras})
    except Exception:
        res = None
    if not res or res.get("score", 0) <= 0:
        return False
    print(f"     card escolhido -> {res.get('titulo','?')}")

    # Clicar na FOTO GRANDE do card avanca direto (confirmado pelo usuario).
    # O desenho costuma ser imagem de FUNDO num quadro (nao um <img>), entao o
    # jeito certo e um CLIQUE REAL de mouse no MEIO do desenho (parte de cima do
    # card). Tambem tentamos o NOME. Nunca o botao vermelho 'Mais opcoes'.
    def _clicar_ponto(loc, fx, fy):
        try:
            loc.scroll_into_view_if_needed(timeout=2000)
            box = loc.bounding_box()
        except Exception:
            box = None
        if not box:
            return False
        x = box["x"] + box["width"] * fx
        y = box["y"] + box["height"] * fy
        for func in (page.mouse.click, page.mouse.dblclick):
            try:
                func(x, y)
            except Exception:
                continue
            if _esperar_url_ou_texto(page, "confirmadadosprojeto",
                                     "Detalhes do Projeto", 5000):
                return True
        return False

    # 1) FOTO GRANDE (a MAIOR imagem do card) -- clicar nela avanca direto.
    #    E o clique que o usuario confirmou funcionar.
    img = page.locator('[data-egerobo="img"]').first
    if img.count() > 0 and _clicar_ponto(img, 0.5, 0.5):
        return True

    # 2) elemento de ACAO (o <a>/onclick que envolve a foto) -- so se NAO for o
    #    botao vermelho 'Mais opcoes' (esse ja foi filtrado ao marcar 'acao').
    acao = page.locator('[data-egerobo="acao"]').first
    if acao.count() > 0:
        for forcar in (False, True):
            try:
                acao.click(timeout=2500, force=forcar)
            except Exception:
                continue
            if _esperar_url_ou_texto(page, "confirmadadosprojeto",
                                     "Detalhes do Projeto", 5000):
                return True

    # 3) area de cima do card (onde fica a foto) -- caso o desenho seja imagem
    #    de fundo (CSS), nao um <img>. So a PARTE DE CIMA, nunca o rodape (texto
    #    + botao vermelho 'Mais opcoes').
    card = page.locator('[data-egerobo="card"]').first
    for fy in (0.35, 0.45, 0.25, 0.55):
        if card.count() > 0 and _clicar_ponto(card, 0.5, fy):
            return True
    # clique FORCADO na imagem (ignora sobreposicoes)
    if img.count() > 0:
        try:
            img.click(timeout=2500, force=True)
            if _esperar_url_ou_texto(page, "confirmadadosprojeto",
                                     "Detalhes do Projeto", 4000):
                return True
        except Exception:
            pass
    # tenta o NOME do projeto
    tit = page.locator('[data-egerobo="titulo"]').first
    if tit.count() > 0:
        try:
            tit.click(timeout=3000)
            if _esperar_url_ou_texto(page, "confirmadadosprojeto",
                                     "Detalhes do Projeto", 5000):
                return True
        except Exception:
            pass
    # ultimo recurso: SO para modelos que dependem de escolher variacao/desenho
    # (painel/modulo fixo, maxim-ar com N modulos). Para janela/porta comum NAO
    # entra na lista de variacoes (evita escolher 'veneziana' por engano) -- e
    # melhor pausar p/ 1 clique manual do que montar o item errado.
    low_mod = _sem_acento(modelo.lower())
    if any(w in low_mod for w in ("modulo", "painel", "fixo", "maxim")):
        if _escolher_variacao_popup(page, modelo, num):
            return True
    # DIAGNOSTICO: salva E IMPRIME a estrutura (HTML) do card (cole aqui p/ eu
    # descobrir o clique certo).
    try:
        html = (res or {}).get("html", "")
        if html:
            PRINTS_DIR.mkdir(parents=True, exist_ok=True)
            (PRINTS_DIR / f"sub_card_html_{num}.txt").write_text(html, encoding="utf-8")
            print("     " + "-" * 54)
            print("     ESTRUTURA DO CARD (copie tudo abaixo e cole na conversa):")
            print("     " + "-" * 54)
            print(html[:1600])
            print("     " + "-" * 54)
    except Exception:
        pass
    return False


# JS que acha, DENTRO do popup de variacoes, a variacao que casa com a descricao.
_JS_MARCAR_VARIACAO = r"""
(args) => {
  const nd = s => (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');
  const pal = args.palavras.map(nd);
  document.querySelectorAll('[data-egevar]').forEach(e => e.removeAttribute('data-egevar'));
  // acha o container do popup pelo texto do cabecalho
  let modal = null;
  const marca = Array.from(document.querySelectorAll('*')).find(e => {
    const t = nd(e.textContent || '');
    return t.length < 400 && (t.includes('desenho desta tipologia') ||
           t.includes('variacoes') || t.includes('variaveis)'));
  });
  if (marca){ let n = marca; for (let i=0;i<7&&n;i++,n=n.parentElement){
    const r = n.getBoundingClientRect(); if (r.width>300 && r.height>200){ modal=n; break; } } }
  const raiz = modal || document;
  const nodes = Array.from(raiz.querySelectorAll('div,li,tr,td,article,a'));
  let best=null, bestScore=-1, bestLen=1e9;
  for (const b of nodes){
    const t = nd(b.textContent);
    if (!t || t.length < 4 || t.length > 140) continue;
    if (t.includes('projeto com')) continue;   // esses sao os cards de fundo
    if (!/modulo|painel|folhas|maxim|persiana|peitoril|bandeira|veneziana|tela/.test(t)) continue;
    const r = b.getBoundingClientRect();
    if (r.width < 20 || r.height < 10) continue;
    let s = 0; for (const w of pal){ if (w.length>=2 && t.includes(w)) s++; }
    if (s > bestScore || (s === bestScore && t.length < bestLen)){
      best=b; bestScore=s; bestLen=t.length;
    }
  }
  if (!best) return null;
  best.setAttribute('data-egevar','row');
  let big=null, area=0;
  for (const im of best.querySelectorAll('img')){
    const r = im.getBoundingClientRect(); const a = r.width*r.height;
    if (a > area){ area=a; big=im; }
  }
  if (big) big.setAttribute('data-egevar','img');
  best.scrollIntoView({block:'center'});
  let titulo = (best.textContent||'').replace(/\s+/g,' ').trim();
  if (titulo.length > 80) titulo = titulo.slice(0,80) + '...';
  // estrutura da variacao E do modal em volta (para diagnostico)
  let html = ((modal||best).outerHTML||'').replace(/\s+/g,' ');
  if (html.length > 3500) html = html.slice(0,3500) + '...';
  return {score: bestScore, titulo, viaModal: !!modal, html};
}
"""


def _escolher_variacao_popup(page, modelo, num=""):
    """Escolhe e clica a variacao certa no popup de variacoes (painel fixo etc.).
    Retorna True se conseguiu navegar para a tela do projeto."""
    palavras = [w for w in _re.split(r"[^a-z0-9]+", _sem_acento(modelo.lower()))
                if len(w) >= 2 and w not in _STOP]
    try:
        res = page.evaluate(_JS_MARCAR_VARIACAO, {"palavras": palavras})
    except Exception:
        res = None
    if not res:
        return False
    print(f"     variacao escolhida -> {res.get('titulo','?')}")
    # clique REAL de mouse no meio da variacao (row) e na imagem dela
    for sel, fy in (('[data-egevar="img"]', 0.5), ('[data-egevar="row"]', 0.5)):
        loc = page.locator(sel).first
        try:
            if loc.count() == 0:
                continue
            loc.scroll_into_view_if_needed(timeout=2000)
            box = loc.bounding_box()
        except Exception:
            box = None
        if box:
            x = box["x"] + box["width"] * 0.5
            y = box["y"] + box["height"] * fy
            for func in (page.mouse.click, page.mouse.dblclick):
                try:
                    func(x, y)
                except Exception:
                    continue
                if _esperar_url_ou_texto(page, "confirmadadosprojeto",
                                         "Detalhes do Projeto", 4000):
                    return True
        # tambem tenta o clique normal/forcado do Playwright
        for forcar in (False, True):
            try:
                loc.click(timeout=2500, force=forcar)
            except Exception:
                continue
            if _esperar_url_ou_texto(page, "confirmadadosprojeto",
                                     "Detalhes do Projeto", 4000):
                return True
    # DIAGNOSTICO: salva o HTML do popup de variacoes
    try:
        html = res.get("html", "")
        if html:
            PRINTS_DIR.mkdir(parents=True, exist_ok=True)
            caminho = PRINTS_DIR / f"sub_variacao_html_{num}.txt"
            caminho.write_text(html, encoding="utf-8")
            print(f"     (salvei a estrutura da variacao em: {caminho})")
    except Exception:
        pass
    return False


def _construir_na_selecao(page, num, mud, prefixo="sub"):
    """MOTOR compartilhado: a partir da tela 'ESCOLHA O DESENHO | PROJETO'
    (selecioneprojeto), escolhe LINHA/MODELO -> Pesquisa -> escolhe o card ->
    preenche 'Dados do Projeto' -> Inclui item -> variaveis (acionamento) ->
    Confirma. Usado TANTO pela SUBSTITUICAO quanto pelo MONTAR DO ZERO -- as
    duas caem nesta MESMA tela, so mudam a 'porta de entrada' antes dela.
    Retorna True se incluiu o item."""
    modelo = mud.get("modelo", "")
    linha = mud.get("linha", "")
    acion = mud.get("acionamento")

    # tela 'ESCOLHA O DESENHO | PROJETO'
    if not _esperar_url_ou_texto(page, "selecioneprojeto", "ESCOLHA O DESENHO", 15000):
        print("     [!] nao abriu a tela de selecao de projeto.")
        print_tela(page, f"{prefixo}_sem_selecao_{num}")
        return False
    page.wait_for_timeout(1000)

    # popup 'valores zerados' -> Fechar (se aparecer)
    if _tem_texto_visivel(page, "valores zerados") or _tem_texto_visivel(page, "sem valor"):
        _clicar_botao(page, r"^\s*fechar\s*$", timeout=4000)
        page.wait_for_timeout(600)

    # LINHA e MODELO. O MODELO e inferido da descricao (janela de correr /
    # modulo fixo / maxim-ar / porta), e o card certo vem depois pelo texto.
    if linha:
        _selecionar_select_rotulo(page, "LINHA", linha, "linha")
        page.wait_for_timeout(700)
    else:
        print("     [i] linha nao informada -- usando a linha PADRAO da tela (confira!).")
    _selecionar_select_rotulo(page, "MODELO", _modelo_dropdown(modelo), "modelo")
    page.wait_for_timeout(700)

    # Pesquisar
    _clicar_botao(page, r"^\s*pesquisar\s*$", timeout=6000)
    page.wait_for_timeout(2000)

    # escolher o card do desenho AUTOMATICAMENTE
    if not _escolher_card_auto(page, modelo, num):
        # Fallback: alguns cards (ex.: 'N MODULOS') abrem um popup de variacoes
        # e nao dao para clicar direto. Entao pausa SO aqui: voce da 1 clique no
        # desenho e o robo continua sozinho (preenche, inclui, variaveis, salva).
        print("     [!] nao consegui abrir o desenho sozinho (essa tela tem varias opcoes).")
        print_tela(page, f"{prefixo}_sem_card_{num}")
        print("     " + "=" * 54)
        print("     >> CLIQUE no desenho que voce quer, NA TELA do W-Vetro")
        print("        (na FOTO grande do desenho certo).")
        print("     " + "=" * 54)
        input("     Quando abrir a tela 'Dados do Projeto', aperte ENTER aqui...  ")

    # tela 'Detalhes do Projeto'
    if not _esperar_url_ou_texto(page, "confirmadadosprojeto", "Detalhes do Projeto", 15000):
        print("     [!] nao abriu a tela 'Dados do Projeto' apos escolher o card.")
        print_tela(page, f"{prefixo}_sem_dados_{num}")
        return False
    page.wait_for_timeout(1000)

    # preenche o que veio na mensagem
    frame = _frame_dados_projeto(page)
    if "qtde" in mud:
        _set_input_auto(frame, "QUANTIDADE", mud["qtde"], "quantidade")
    if "largura" in mud:
        _set_input_auto(frame, "LARGURA", mud["largura"], "largura")
    if "altura" in mud:
        _set_input_auto(frame, "ALTURA", mud["altura"], "altura")
    if "tipo" in mud:
        _set_input_auto(frame, "TIPO", mud["tipo"], "tipo", exato=True)
    if "ambiente" in mud:
        _set_input_auto(frame, "AMBIENTE", mud["ambiente"], "ambiente")
    if "cor" in mud:
        _set_select_auto(frame, "PERFIL", "cor", mud["cor"], "cor")
    if "vidro" in mud:
        _set_select_auto(frame, "VIDRO COR", "vidro", mud["vidro"], "vidro")
    print_tela(page, f"{prefixo}_dados_{num}")

    # Incluir item no orcamento -- CLIQUE REAL e CONFIRMA que a tela avancou
    # (abriu a janela de variaveis OU saiu da tela 'Detalhes do Projeto'). Se
    # nao avancar, tenta de novo -- esse botao as vezes ignora o 1o clique.
    import time as _t
    def _avancou_do_incluir():
        try:
            if "confirmadadosprojeto" not in (page.url or "").lower():
                return True
        except Exception:
            pass
        return _janela_variaveis_aberta(page) or _modal_edicao_aberto(page)

    incluiu = False
    for _tent in range(4):
        clicou = (_clicar_botao_real(page, r"incluir item no or", timeout=5000)
                  or _clicar_botao(page, r"incluir item no or", timeout=3000))
        if not clicou:
            page.wait_for_timeout(700)
            continue
        fim = _t.time() + 6
        while _t.time() < fim:
            if _avancou_do_incluir():
                incluiu = True
                break
            page.wait_for_timeout(500)
        if incluiu:
            break
        print(f"     (tentando 'Incluir item no orcamento' de novo... {_tent + 1})")
    print_tela(page, f"{prefixo}_apos_incluir_{num}")
    if not incluiu:
        print("     [!] cliquei em 'Incluir item no orcamento' mas a tela nao avancou.")
        print_tela(page, f"{prefixo}_incluir_travou_{num}")
        return False

    # janela 'Informe as variaveis' (itens com persiana/motor pedem o
    # ACIONAMENTO). ENQUANTO ela nao for CONFIRMADA o item NAO fica salvo --
    # se navegar antes, perde o item. Ela demora a surgir, entao esperamos.
    import time as _t
    fim = _t.time() + 9
    apareceu = False
    while _t.time() < fim:
        if _janela_variaveis_aberta(page) or _modal_edicao_aberto(page):
            apareceu = True
            break
        page.wait_for_timeout(500)
    if apareceu:
        print("     janela de variaveis aberta -- finalizando...")
        if acion:
            if not _definir_acionamento(page, acion):
                print(f"     [!] nao achei o campo ACIONAMENTO p/ definir '{acion}'.")
            page.wait_for_timeout(800)
        if not _confirmar_edicao(page):
            print("     [!] a janela de variaveis nao fechou sozinha.")
            print_tela(page, f"{prefixo}_variaveis_travou_{num}")

    page.wait_for_timeout(1500)
    return True


def substituir_item_projeto(page, linha_item, num, mud):
    """SUBSTITUIR o projeto de um item por outro modelo -- 100% AUTOMATICO.
    Abre Substituir Projeto -> Sim -> escolhe LINHA/MODELO -> Pesquisa ->
    escolhe o card (melhor match) -> preenche 'Dados do Projeto' -> Inclui ->
    variaveis (acionamento) -> Confirma. A troca APAGA o item antigo."""
    modelo = mud.get("modelo", "")
    linha = mud.get("linha", "")
    print(f"\n  >> Item {num}: SUBSTITUIR por '{modelo}'"
          + (f" (linha {linha})" if linha else ""))
    if not modelo:
        print("     [!] falta o MODELO na mensagem (ex.: 'maxim ar') -- pulando.")
        return False

    # 1) menu ☰ -> Substituir Projeto
    if not _abrir_menu_item(page, linha_item):
        print(f"     [!] nao abri o menu (☰) do item {num}")
        return False
    if not _clicar_texto_visivel(page, "Substituir Projeto", timeout=6000):
        print("     [!] nao achei 'Substituir Projeto' no menu.")
        print_tela(page, f"sub_sem_opcao_{num}")
        return False

    # 2) popup 'Deseja excluir este projeto...' -> Sim
    page.wait_for_timeout(1200)
    if not _clicar_botao(page, r"^\s*sim\s*$", timeout=6000):
        print("     [!] nao achei o botao 'Sim' da confirmacao.")
        print_tela(page, f"sub_sem_sim_{num}")
        return False

    # 3..9) motor compartilhado (a partir de 'ESCOLHA O DESENHO')
    if not _construir_na_selecao(page, num, mud, prefixo="sub"):
        return False

    print(f"     item {num} substituido. ✔")
    return True


def montar_item_novo(page, num, mud):
    """MONTAR DO ZERO um item novo no orcamento -- 100% AUTOMATICO.
    Clica 'Inserir Novo Projeto' -> cai na MESMA tela 'ESCOLHA O DESENHO' ->
    reaproveita o motor compartilhado (LINHA/MODELO -> card -> dados -> inclui).
    NAO apaga nada: so ADICIONA um item ao orcamento."""
    modelo = mud.get("modelo", "")
    linha = mud.get("linha", "")
    print(f"\n  >> Item {num}: MONTAR '{modelo}'"
          + (f" (linha {linha})" if linha else ""))
    if not modelo:
        print("     [!] falta o MODELO na descricao (ex.: 'janela 2 folhas') -- pulando.")
        return False

    # 1) botao 'Inserir Novo Projeto' (porta de entrada do MONTAR). Mas se JA
    #    estivermos na tela de selecao (ex.: 1o item logo apos 'Criar
    #    orcamento'), pula direto para escolher o desenho.
    ja_na_selecao = "selecioneprojeto" in (page.url or "").lower()
    if not ja_na_selecao:
        if not _clicar_botao(page, r"inserir novo projeto", timeout=8000):
            # fallbacks de rotulo que o W-Vetro usa nessa acao
            if not (_clicar_botao(page, r"novo projeto", timeout=4000)
                    or _clicar_botao(page, r"adicionar item", timeout=4000)
                    or _clicar_botao(page, r"incluir projeto", timeout=4000)):
                print("     [!] nao achei o botao 'Inserir Novo Projeto'.")
                print_tela(page, f"mon_sem_inserir_{num}")
                return False
        page.wait_for_timeout(1500)

    # 2..8) motor compartilhado (a partir de 'ESCOLHA O DESENHO')
    if not _construir_na_selecao(page, num, mud, prefixo="mon"):
        return False

    # 9) depois de incluir + variaveis, o robo fica na tela de selecao/cards.
    # O botao 'Calcular o Orcamento' VOLTA para o orcamento (SEM re-pesquisar).
    if _clicar_calcular_orcamento(page, timeout=10000):
        print("     'Calcular o Orcamento' -> voltou para o orcamento. ✔")
    else:
        print("     [!] nao consegui clicar em 'Calcular o Orcamento' sozinho.")
        print_tela(page, f"mon_sem_calcular_{num}")
    page.wait_for_timeout(1500)

    print(f"     item {num} montado. ✔")
    return True


def _set_input_page(page, rotulo, valor, nome):
    """Preenche um <input> pelo ROTULO em QUALQUER frame (silencioso)."""
    for fr in page.frames:
        try:
            inp = _achar_input(fr, rotulo)
        except Exception:
            inp = None
        if inp is not None and _visivel(inp):
            try:
                inp.scroll_into_view_if_needed(timeout=2000)
                inp.click(timeout=2000)
                inp.fill(str(valor))
                print(f"     {nome} -> {valor}")
                return True
            except Exception:
                continue
    print(f"     [!] nao achei o campo {nome}")
    return False


def cadastrar_cliente(page, cli):
    """Cadastra um cliente NOVO no W-Vetro: tela 'NOVO CLIENTE' -> preenche o
    'Cadastro Rapido/Completo' -> Salvar. Os dados vem do CRM (passados na
    mensagem). So o NOME e obrigatorio."""
    nome = cli.get("nome")
    if not nome:
        print("  [!] falta o NOME do cliente -- nao da pra cadastrar.")
        return False
    print(f"\n  >> Cadastrando cliente: {nome}")

    # 1) tile/botao 'NOVO CLIENTE'
    if not (_clicar_botao_real(page, r"novo\s+cliente", timeout=8000)
            or _clicar_botao(page, r"novo\s+cliente", timeout=4000)):
        print("  [!] nao achei 'NOVO CLIENTE' na tela (abra a tela inicial).")
        print_tela(page, "cli_sem_novo")
        return False
    page.wait_for_timeout(2000)

    # 2) espera o formulario de cadastro
    if not (_tem_texto_visivel(page, "NOME COMPLETO")
            or _tem_texto_visivel(page, "Cadastro")):
        print("  [!] a tela de cadastro do cliente nao abriu.")
        print_tela(page, "cli_sem_form")
        return False

    # 3) campos de TEXTO (CEP antes da rua: se o W-Vetro auto-preencher pelo
    #    CEP, a rua/numero que eu informar depois sobrescreve).
    _set_input_page(page, "NOME", nome, "nome")
    campos = [("celular", "CELULAR", "celular"),
              ("telefone", "TELEFONE", "telefone"),
              ("email", "EMAIL", "email"),
              ("cpf", "CPF", "cpf/cnpj"),
              ("cep", "CEP", "cep"),
              ("rua", "RUA", "rua"),
              ("numero", "NUMERO", "numero"),
              ("bairro", "BAIRRO", "bairro"),
              ("complemento", "COMPLEMENTO", "complemento")]
    for campo, rot, lbl in campos:
        if cli.get(campo):
            _set_input_page(page, rot, cli[campo], lbl)

    # 3b) CIDADE / UF sao LISTAS (dropdown). 'cidade: Ararangua/SC' -> separa UF.
    cidade = cli.get("cidade", "")
    uf = cli.get("uf", "")
    mcid = _re.match(r"^(.*?)[\s/-]+([A-Za-z]{2})\s*$", cidade)
    if mcid and not uf:
        cidade, uf = mcid.group(1).strip(), mcid.group(2).strip()
    if uf:
        _selecionar_select_rotulo(page, "UF", _UF_NOME.get(uf.upper(), uf), "uf")
        page.wait_for_timeout(600)
    if cidade:
        _selecionar_select_rotulo(page, "CIDADE", cidade, "cidade")
    print_tela(page, "cli_preenchido")

    # 4) Salvar -> o botao e 'Confirmar' (canto inferior direito).
    if not (_clicar_botao_real(page, r"^\s*confirmar\s*$", timeout=6000)
            or _clicar_botao(page, r"^\s*confirmar\s*$", timeout=4000)
            or _clicar_botao(page, r"salvar", timeout=3000)
            or _clicar_botao(page, r"cadastrar", timeout=3000)):
        print("  [!] nao achei o botao 'Confirmar'.")
        print_tela(page, "cli_sem_salvar")
        return False
    page.wait_for_timeout(2500)
    print_tela(page, "cli_apos_salvar")
    print(f"  cliente '{nome}' cadastrado. ✔")
    return True


def criar_orcamento_novo(page, cli):
    """Logo apos cadastrar o cliente, cria o ORCAMENTO NOVO:
    'Cadastrado novo cliente!' -> 'Criar um novo orcamento' -> escolhe o
    VENDEDOR -> 'Criar orcamento' -> cai na tela 'ESCOLHA O DESENHO'
    (selecioneprojeto), pronta para montar os itens. Retorna True se chegou la."""
    # 1) tela pos-cadastro: botao 'Criar um novo orcamento'
    if not (_clicar_botao_real(page, r"criar\s+um\s+novo\s+or", timeout=8000)
            or _clicar_botao(page, r"criar\s+um\s+novo\s+or", timeout=4000)):
        print("  [!] nao achei 'Criar um novo orcamento'.")
        print_tela(page, "orc_sem_criar_novo")
        return False
    page.wait_for_timeout(2000)

    # 2) tela 'CADASTRO DE ORCAMENTO': VENDEDOR (lista) + 'Criar orcamento'
    if not (_tem_texto_visivel(page, "CADASTRO DE OR") or _tem_texto_visivel(page, "VENDEDOR")):
        page.wait_for_timeout(1500)
    if cli.get("vendedor"):
        _selecionar_select_rotulo(page, "VENDEDOR", cli["vendedor"], "vendedor")
        page.wait_for_timeout(600)
    if not (_clicar_botao_real(page, r"^\s*criar\s+or[çc]amento\s*$", timeout=6000)
            or _clicar_botao(page, r"^\s*criar\s+or[çc]amento\s*$", timeout=4000)):
        print("  [!] nao achei o botao 'Criar orcamento'.")
        print_tela(page, "orc_sem_criar")
        return False
    page.wait_for_timeout(2500)

    # 3) deve cair na tela de selecao de projeto (ESCOLHA O DESENHO)
    if not _esperar_url_ou_texto(page, "selecioneprojeto", "ESCOLHA O DESENHO", 15000):
        print("  [!] nao abriu a tela de montar itens apos criar o orcamento.")
        print_tela(page, "orc_sem_selecao")
        return False
    print("  orcamento novo criado. ✔")
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


def _confere_item_na_linha(mud, row_up):
    """Compara o que foi pedido com o texto da LINHA do item na tabela (que
    mostra L/H, Qtd, Tipo, Localizacao e Vidro). Devolve lista de campos que
    NAO baterem. Comparacao lenient: o vidro na tabela vem truncado, entao
    conferimos nome + espessura (nao a string inteira)."""
    ruins = []
    sem_espaco = row_up.replace(" ", "")
    if "largura" in mud and "altura" in mud:
        med = f'{mud["largura"]}X{mud["altura"]}'.upper()
        if med not in sem_espaco:
            ruins.append("medida")
    if "tipo" in mud and mud["tipo"].upper() not in row_up:
        ruins.append("tipo")
    if "ambiente" in mud:
        # a localizacao vem TRUNCADA na tabela (ex.: 'SUITE MAST..'); por isso
        # conferimos so o inicio (4 letras) da 1a palavra do ambiente.
        palavras = [w for w in mud["ambiente"].upper().split() if len(w) >= 3]
        if palavras and palavras[0][:4] not in row_up:
            ruins.append("ambiente")
    if "vidro" in mud:
        desc = _descreve_vidro(mud["vidro"]).upper()   # ex.: INCOLOR 08MM - TEMPERADO
        nome = desc.split()[0]                          # INCOLOR / MINI-BOREAL
        mm = _re.search(r"\d{2}MM", desc)
        ok_nome = nome in row_up
        ok_mm = (mm.group(0) in sem_espaco) if mm else True
        if not (ok_nome and ok_mm):
            ruins.append("vidro")
    return ruins


def _resumo_final(page, itens, resultados):
    """Imprime um RESUMO do que foi aplicado e uma CONFERENCIA de cada item
    contra a linha atual da tabela (o que o W-Vetro esta mostrando)."""
    page.wait_for_timeout(1000)
    mapa = _itens_por_ordem(page)
    print()
    print("  " + "=" * 58)
    print("  RESUMO / CONFERENCIA")
    print("  " + "=" * 58)
    ok_n = aviso_n = falha_n = 0
    for num, mud in itens.items():
        st = resultados.get(num, "?")
        if mud.get("substituir"):
            if st == "ok":
                print(f"  Item {num}: ↻ SUBSTITUIDO por '{mud.get('modelo','?')}' (confira na tela)")
                ok_n += 1
            else:
                print(f"  Item {num}: ✗ substituicao NAO concluida ({st})")
                falha_n += 1
            continue
        if st == "nao_existe":
            print(f"  Item {num}: ✗ NAO EXISTE neste orcamento")
            falha_n += 1
            continue
        if st in ("falhou", "erro"):
            print(f"  Item {num}: ✗ NAO salvou (veja os prints/avisos acima)")
            falha_n += 1
            continue
        # aplicado: confere contra a linha da tabela
        linha = mapa.get(str(num))
        row_up = ""
        if linha is not None:
            try:
                row_up = " ".join(linha.inner_text().split()).upper()
            except Exception:
                row_up = ""
        ruins = _confere_item_na_linha(mud, row_up) if row_up else ["(nao li a linha)"]
        if not ruins:
            print(f"  Item {num}: ✔ salvo e conferido")
            ok_n += 1
        else:
            print(f"  Item {num}: ⚠ salvo, mas confira: {', '.join(ruins)}")
            aviso_n += 1
    print("  " + "-" * 58)
    print(f"  Total: {ok_n} OK  |  {aviso_n} conferir  |  {falha_n} falhou")
    print("  " + "=" * 58)
    print("\n  Pronto! Alteracoes da mensagem aplicadas. ✔")


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

    resultados = {}  # num -> "ok" | "falhou" | "nao_existe" | "erro"
    for num, mud in itens.items():
        mapa = _itens_por_ordem(page)
        # Se a tela nao esta mostrando os itens (ex.: acabamos de SUBSTITUIR e
        # o W-Vetro foi para outra tela), REABRE o orcamento para voltar a lista.
        if not mapa:
            print("  (voltando para a tela do orcamento...)")
            abrir_orcamento(page, orc)
            mapa = _itens_por_ordem(page)
        linha = mapa.get(str(num))
        if linha is None:
            achados = ", ".join(sorted(mapa, key=lambda x: int(x) if x.isdigit() else 0))
            print(f"  [!] item {num} nao existe neste orcamento.")
            print(f"      (itens encontrados na tela: {achados or 'nenhum'})")
            resultados[num] = "nao_existe"
            continue
        # SUBSTITUIR PROJETO -- modo GUIADO (a troca APAGA o item antigo, entao
        # o usuario confirma os passos delicados). Roda igual em S ou A.
        if mud.get("substituir"):
            try:
                ok = substituir_item_projeto(page, linha, num, mud)
                resultados[num] = "ok" if ok else "falhou"
            except Exception as e:
                print(f"  [!] erro inesperado ao substituir o item {num}: {e}")
                print_tela(page, f"sub_erro_{num}")
                resultados[num] = "erro"
            page.wait_for_timeout(1200)
            continue
        try:
            if semi:
                ok = aplicar_item_semi_auto(page, linha, num, mud)
            else:
                ok = aplicar_item_auto(page, linha, num, mud)
            resultados[num] = "ok" if ok else "falhou"
        except Exception as e:
            print(f"  [!] erro inesperado no item {num}: {e}")
            print_tela(page, f"erro_item_{num}")
            resultados[num] = "erro"
        page.wait_for_timeout(1200)

    # Ao final, o W-Vetro precisa RECALCULAR os valores do orcamento.
    # Se houve substituicao, a tela pode ter mudado -- volta para o orcamento.
    if any(m.get("substituir") for m in itens.values()):
        if not _itens_por_ordem(page):
            abrir_orcamento(page, orc)
    print("\n  Atualizando os valores (Calcular)...")
    if clicar_calcular(page):
        print("  Cliquei em Calcular -- valores atualizados. ✔")
    else:
        print("  (Nao achei o botao 'Calcular'. Se aparecer 'Orcamento Nao")
        print("   Calculado' na tela, clique em Calcular manualmente.)")

    # Resumo + conferencia: mostra como cada item ficou na tela do W-Vetro.
    _resumo_final(page, itens, resultados)


def _preview_montar(orc, itens):
    print()
    print("  " + "=" * 56)
    print(f"  VOU MONTAR ESTES ITENS (orcamento {orc}):")
    print("  " + "=" * 56)
    for i, mud in enumerate(itens, 1):
        cod = mud.get("tipo", "")
        print(f"\n  ITEM {i}{(' [' + cod + ']') if cod else ''}:")
        print(f"     modelo      -> {mud.get('modelo') or '(nao informado!)'}")
        print(f"     linha       -> {mud.get('linha','(padrao da tela)')}")
        if "acionamento" in mud:
            print(f"     acionamento -> {mud['acionamento']}")
        for chave, nome in CAMPOS_PREVIEW:
            if chave in mud:
                val = _descreve_vidro(mud[chave]) if chave == "vidro" else mud[chave]
                print(f"     {nome:11s} -> {val}")
        # SEM medida o W-Vetro NAO inclui o item (trava). Avisa bem claro.
        if "largura" not in mud or "altura" not in mud:
            print("     >>> [!] FALTA A MEDIDA (largura x altura)! Sem medida o")
            print("             W-Vetro nao inclui o item. Ex.: '1200x1200'.")
    print("  " + "=" * 56)


def modo_montar(page):
    """Monta um orcamento DO ZERO: cada linha da mensagem vira um item NOVO
    (Inserir Novo Projeto). Reaproveita o mesmo motor da substituicao."""
    print()
    print("MONTAR ORCAMENTO DO ZERO.")
    print("Cole o cabecalho com o numero do orcamento e uma linha por item.")
    print("IMPORTANTE: cada item PRECISA da medida (largura x altura em mm),")
    print("senao o W-Vetro nao inclui. Ex.: 1200x1200")
    print("A quantidade e 1 por padrao; p/ mais de 1 escreva ex.: '2un'.")
    print("Ex.:")
    print("   Montar orcamento 2346")
    print("   j01 janela 02 folhas e tela com persiana com motor l32 -"
          " branco brilhante - incolor 6mm temperado - 1200x1200 - quartos")
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

    orc, itens = parse_montar(texto)
    if not orc:
        print("  Nao achei o numero do orcamento na mensagem.")
        return
    if not itens:
        print("  Nao achei itens para montar na mensagem.")
        return

    _preview_montar(orc, itens)
    r = input("\n  Esta certo? ENTER para MONTAR  |  N para cancelar: ").strip().lower()
    if r == "n":
        print("  Cancelado.")
        return

    if not abrir_orcamento(page, orc):
        print("  Nao consegui abrir o orcamento.")
        return

    # Espera os itens do orcamento aparecerem na tela (ate 'seg' segundos)
    # antes de decidir reabrir. Depois de 'Incluir item no orcamento' o W-Vetro
    # volta para o orcamento, mas demora -- reabrir cedo demais PERDE o item.
    def _esperar_itens(seg=7):
        import time as _t
        fim = _t.time() + seg
        while _t.time() < fim:
            if _itens_por_ordem(page):
                return True
            page.wait_for_timeout(500)
        return bool(_itens_por_ordem(page))

    resultados = {}
    for i, mud in enumerate(itens, 1):
        # SEM medida o W-Vetro nao inclui e trava -- pula o item cedo (limpo).
        if "largura" not in mud or "altura" not in mud:
            print(f"\n  >> Item {i} [{mud.get('tipo','')}]: FALTA A MEDIDA "
                  "(largura x altura) -- pulando este item.")
            resultados[i] = "sem_medida"
            continue
        # depois de incluir um item o W-Vetro volta para o orcamento -- so
        # reabre (Consulta) se ele REALMENTE nao voltou (evita perder o item).
        if i > 1 and not _esperar_itens(7):
            print("  (voltando para a tela do orcamento...)")
            abrir_orcamento(page, orc)
        try:
            ok = montar_item_novo(page, i, mud)
            resultados[i] = "ok" if ok else "falhou"
        except Exception as e:
            print(f"  [!] erro inesperado ao montar o item {i}: {e}")
            print_tela(page, f"mon_erro_{i}")
            resultados[i] = "erro"
        page.wait_for_timeout(1200)

    # Cada item ja voltou para o orcamento via 'Calcular o Orcamento' (dentro
    # de montar_item_novo). O item ja esta SALVO -- entao NAO reabrimos pela
    # Consulta (era isso que voltava a 'procurar o orcamento' no fim).
    page.wait_for_timeout(1500)
    print("\n  Atualizando os valores (Calcular, se precisar)...")
    if clicar_calcular(page):
        print("  Cliquei em Calcular -- valores atualizados. ✔")
    else:
        print("  (valores ja calculados / ja no orcamento)")

    print()
    print("  " + "=" * 56)
    print("  RESUMO DO QUE MONTEI:")
    for i, mud in enumerate(itens, 1):
        st = resultados.get(i, "?")
        marca = {"ok": "✔", "falhou": "✘", "erro": "‼",
                 "sem_medida": "⚠ falta medida"}.get(st, "?")
        print(f"    item {i} [{mud.get('tipo','')}] -> {marca} {st}")
    print("  " + "=" * 56)


def modo_cadastro(page):
    """Cadastra um cliente NOVO no W-Vetro a partir dos dados colados (CRM)."""
    print()
    print("CADASTRAR CLIENTE NOVO.")
    print("Cole os dados do cliente (uma linha por campo). Ex.:")
    print("   Cliente: Francilene Maria Ribeiro Alves")
    print("   Celular: 48999287469")
    print("   Rua: Rua das Flores")
    print("   Numero: 30")
    print("   Bairro: Centro")
    print("   Cidade: Ararangua/SC")
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
    cli = parse_cliente("\n".join(linhas))
    if not cli.get("nome"):
        print("  Nao achei o NOME do cliente na mensagem.")
        return
    print("\n  " + "=" * 56)
    print("  VOU CADASTRAR ESTE CLIENTE:")
    for k in ("nome", "celular", "telefone", "email", "cpf", "cep", "rua",
              "numero", "bairro", "complemento", "cidade", "uf", "vendedor"):
        if cli.get(k):
            print(f"     {k:11s} -> {cli[k]}")
    print("  " + "=" * 56)
    r = input("\n  Cadastrar? ENTER = sim  |  N para cancelar: ").strip().lower()
    if r == "n":
        print("  Cancelado.")
        return
    cadastrar_cliente(page, cli)


def modo_novo(page):
    """ORCAMENTO NOVO COMPLETO: cadastra o cliente -> cria o orcamento ->
    monta os itens. Os dados do cliente e os itens vem na MESMA mensagem
    (dados do CRM em 'Campo: valor' e uma linha por item)."""
    print()
    print("ORCAMENTO NOVO (cliente + itens).")
    print("Cole os DADOS DO CLIENTE (Campo: valor) e depois os ITENS (1 por linha).")
    print("Ex.:")
    print("   Cliente: Francilene Maria Ribeiro Alves")
    print("   Celular: 554899287469")
    print("   Cidade: Ararangua/SC")
    print("   Vendedor: Sander Pacheco")
    print("   Itens:")
    print("   j01 janela 02 folhas com persiana l25 - preto - incolor 6mm temperado - 1200x1200 - quarto")
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

    cli = parse_cliente(texto)
    _, itens = parse_montar(texto)   # ignora o numero (o orcamento e NOVO)
    if not cli.get("nome"):
        print("  Nao achei o NOME do cliente na mensagem.")
        return
    if not itens:
        print("  Nao achei itens para montar na mensagem.")
        return

    # preview
    print("\n  " + "=" * 56)
    print("  VOU CRIAR ESTE ORCAMENTO NOVO:")
    print("  " + "-" * 56)
    print(f"  CLIENTE: {cli.get('nome')}")
    for k in ("celular", "telefone", "email", "cpf", "cep", "rua", "numero",
              "bairro", "complemento", "cidade", "uf", "vendedor"):
        if cli.get(k):
            print(f"     {k:11s} -> {cli[k]}")
    print("  " + "-" * 56)
    _preview_montar("(novo)", itens)
    r = input("\n  Esta certo? ENTER para FAZER  |  N para cancelar: ").strip().lower()
    if r == "n":
        print("  Cancelado.")
        return

    # 1) cadastra o cliente
    if not cadastrar_cliente(page, cli):
        print("  [!] parei: nao consegui cadastrar o cliente.")
        return
    # 2) cria o orcamento novo (vendedor) -> cai na tela de montar
    if not criar_orcamento_novo(page, cli):
        print("  [!] parei: nao consegui criar o orcamento novo.")
        return
    # 3) monta os itens (o 1o ja cai direto na selecao)
    resultados = {}
    for i, mud in enumerate(itens, 1):
        if "largura" not in mud or "altura" not in mud:
            print(f"\n  >> Item {i} [{mud.get('tipo','')}]: FALTA A MEDIDA -- pulando.")
            resultados[i] = "sem_medida"
            continue
        try:
            ok = montar_item_novo(page, i, mud)
            resultados[i] = "ok" if ok else "falhou"
        except Exception as e:
            print(f"  [!] erro inesperado ao montar o item {i}: {e}")
            print_tela(page, f"novo_erro_{i}")
            resultados[i] = "erro"
        page.wait_for_timeout(1200)

    print("\n  Atualizando os valores (Calcular, se precisar)...")
    if clicar_calcular(page):
        print("  Cliquei em Calcular. ✔")
    print()
    print("  " + "=" * 56)
    print("  RESUMO DO ORCAMENTO NOVO:")
    print(f"    cliente -> {cli.get('nome')}")
    for i, mud in enumerate(itens, 1):
        st = resultados.get(i, "?")
        marca = {"ok": "✔", "falhou": "✘", "erro": "‼",
                 "sem_medida": "⚠ falta medida"}.get(st, "?")
        print(f"    item {i} [{mud.get('tipo','')}] -> {marca} {st}")
    print("  " + "=" * 56)
    print("  (As portas de giro voce adiciona manualmente, como combinamos.)")


def modo_montar_aberto(page):
    """Monta os itens num orcamento que VOCE ja criou e deixou na tela
    'ESCOLHA O DESENHO' (ex.: cliente ja cadastrado -> NOVO ORCAMENTO ->
    escolheu o cliente -> Criar orcamento). O robo so monta os itens."""
    print()
    print("MONTAR ITENS (orcamento JA ABERTO na tela 'Escolha o desenho').")
    print("Deixe o W-Vetro na tela 'ESCOLHA O DESENHO | PROJETO' e cole os itens")
    print("(1 por linha). Ex.:")
    print("   j01 janela 02 folhas com persiana l25 - preto - incolor 6mm temperado - 1200x1200 - quarto")
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
    _, itens = parse_montar("\n".join(linhas))
    if not itens:
        print("  Nao achei itens para montar.")
        return
    _preview_montar("(aberto)", itens)
    r = input("\n  Esta certo? ENTER para MONTAR  |  N para cancelar: ").strip().lower()
    if r == "n":
        print("  Cancelado.")
        return
    if "selecioneprojeto" not in (page.url or "").lower():
        print("  [!] voce nao esta na tela 'Escolha o desenho'. Abra ela antes")
        print("      (NOVO ORCAMENTO -> escolha o cliente -> Criar orcamento).")
        return

    resultados = {}
    for i, mud in enumerate(itens, 1):
        if "largura" not in mud or "altura" not in mud:
            print(f"\n  >> Item {i} [{mud.get('tipo','')}]: FALTA A MEDIDA -- pulando.")
            resultados[i] = "sem_medida"
            continue
        try:
            ok = montar_item_novo(page, i, mud)
            resultados[i] = "ok" if ok else "falhou"
        except Exception as e:
            print(f"  [!] erro inesperado ao montar o item {i}: {e}")
            print_tela(page, f"aberto_erro_{i}")
            resultados[i] = "erro"
        page.wait_for_timeout(1200)

    print("\n  Atualizando os valores (Calcular, se precisar)...")
    if clicar_calcular(page):
        print("  Cliquei em Calcular. ✔")
    print()
    print("  " + "=" * 56)
    print("  RESUMO:")
    for i, mud in enumerate(itens, 1):
        st = resultados.get(i, "?")
        marca = {"ok": "✔", "falhou": "✘", "erro": "‼",
                 "sem_medida": "⚠ falta medida"}.get(st, "?")
        print(f"    item {i} [{mud.get('tipo','')}] -> {marca} {st}")
    print("  " + "=" * 56)
    print("  (As portas de giro voce adiciona manualmente.)")


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
                print("  3) MONTAR um orcamento DO ZERO (itens novos)")
                print("  4) CADASTRAR um cliente NOVO")
                print("  5) ORCAMENTO NOVO COMPLETO (cliente + itens)")
                print("  6) MONTAR itens (orcamento ja aberto na tela 'Escolha o desenho')")
                print("  0) Sair")
                op = input("Opcao: ").strip().lower()

                if op in ("0", "sair", "s", "exit", "q"):
                    break
                elif op == "1":
                    modo_mensagem(page)
                elif op == "3":
                    modo_montar(page)
                elif op == "4":
                    modo_cadastro(page)
                elif op == "5":
                    modo_novo(page)
                elif op == "6":
                    modo_montar_aberto(page)
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
