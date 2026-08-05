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


def _preencher_numero(page, numero):
    """Tenta varias estrategias para escrever o numero no campo de valor da busca."""
    # Estrategia A: campo do tipo spinbox (numero)
    try:
        campo = page.get_by_role("spinbox").first
        campo.wait_for(timeout=4000)
        campo.fill(str(numero))
        return True
    except Exception:
        pass
    # Estrategia B: input de texto proximo ao rotulo "valor"
    try:
        # pega todos os inputs visiveis e usa um heuristico simples
        inputs = page.locator("input:visible")
        n = inputs.count()
        for i in range(n):
            inp = inputs.nth(i)
            tipo = (inp.get_attribute("type") or "").lower()
            if tipo in ("number", "text", ""):
                # tenta o que estiver mais a direita na linha de filtro
                pass
        # fallback direto: ultimo input costuma ser o "valor"
        if n > 0:
            inputs.nth(n - 1).fill(str(numero))
            return True
    except Exception:
        pass
    return False


def _abrir_linha_resultado(page, numero):
    """Clica na linha do resultado para abrir o detalhe do orcamento."""
    # A) clica no proprio numero do orcamento
    try:
        page.get_by_text(str(numero), exact=True).first.click(timeout=5000)
        return True
    except Exception:
        pass
    # B) clica no link do nome do cliente (fica sublinhado na tabela)
    try:
        link = page.locator("table a").first
        link.wait_for(timeout=4000)
        link.click()
        return True
    except Exception:
        pass
    # C) clica no icone de menu (☰) da primeira linha e depois em algo de abrir
    try:
        page.locator("table tbody tr").first.click(timeout=4000)
        return True
    except Exception:
        pass
    return False


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
                # normaliza espacos/tabs
                limpo = " | ".join(c.strip() for c in texto.split("\n") if c.strip())
                itens.append(limpo)
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


# ── Programa principal ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("   EGEMAP - Robo de Alteracao de Orcamentos (ETAPA 1)")
    print("   (por enquanto so LE o orcamento -- ainda nao altera nada)")
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
                numero = input("Numero do orcamento (ou 'sair'): ").strip()
                if numero.lower() in ("sair", "s", "exit", "q", ""):
                    break
                if not numero.isdigit():
                    print("  Digite so o numero (ex: 2346).")
                    continue

                if abrir_orcamento(page, numero):
                    ler_itens(page)
                    print("  >> Confira: os itens acima batem com o orcamento no sistema?")
                    print("  >> Se sim, a base esta funcionando e partimos para as alteracoes.")
                else:
                    print("  Nao consegui abrir esse orcamento sozinho.")
                    print(f"  Veja os prints em: {PRINTS_DIR}")

        finally:
            print()
            input("Aperte ENTER para fechar o navegador...")
            contexto.close()

    print("\nRobo encerrado.")


if __name__ == "__main__":
    main()
