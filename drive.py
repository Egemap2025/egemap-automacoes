#!/usr/bin/env python3
"""
EGEMAP - Integracao com o Google Drive

Sobe a proposta pronta para o Google Drive assim que ela fica pronta,
espelhando a mesma estrutura de pastas que voce ja usa no computador
(Cidade/Cliente, ou o que quer que seja a pasta raiz de orcamentos).

So biblioteca padrao do Python -- nada extra pra instalar. Quem faz a
ponte de verdade com o Drive e o "rclone", baixado sozinho na primeira
vez (fica guardado em C:\\Users\\voce\\EgemapDrive).

Modulo independente, do mesmo jeito que o crm.py: o monitor funciona sem
ele (import fica dentro de um try/except) e ele nao sabe nada sobre o
resto do programa.
"""

import json
import os
import re
import subprocess
import threading
import unicodedata
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

DRIVE_DIR   = Path.home() / "EgemapDrive"
RCLONE_EXE  = DRIVE_DIR / "rclone.exe"
RCLONE_CONF = DRIVE_DIR / "rclone.conf"

# Pasta fixa da Egemap no Google Drive -- a mesma de sempre.
ROOT_FOLDER_ID = "1P0EpUNY7F6-j2FX0MmJ0hQZxIQq9nvN5"

RCLONE_URL = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"

TAREFA_AGENTE_ANTIGO = "EgemapDriveWatcher"


def configurado():
    """Ja da pra usar o Drive (rclone baixado e login feito)?

    Se voce ja usava o agente separado do Drive antes, ele guardava o
    rclone e o login exatamente nesta mesma pasta -- entao esta funcao ja
    volta True sozinha, sem precisar logar de novo.
    """
    return RCLONE_EXE.exists() and RCLONE_CONF.exists()


def _baixar_rclone():
    DRIVE_DIR.mkdir(parents=True, exist_ok=True)
    if RCLONE_EXE.exists():
        return
    zip_path = DRIVE_DIR / "rclone.zip"
    urllib.request.urlretrieve(RCLONE_URL, zip_path)
    try:
        with zipfile.ZipFile(zip_path) as z:
            membro = next(n for n in z.namelist() if n.endswith("rclone.exe"))
            with z.open(membro) as origem, open(RCLONE_EXE, "wb") as destino:
                destino.write(origem.read())
    finally:
        zip_path.unlink(missing_ok=True)


def _escrever_conf():
    if RCLONE_CONF.exists():
        return
    RCLONE_CONF.write_text(
        f"[egemap]\ntype = drive\nscope = drive\nroot_folder_id = {ROOT_FOLDER_ID}\n",
        encoding="ascii",
    )


def configurar():
    """Conecta ao Google Drive: baixa o rclone (se precisar) e abre o
    navegador para o login. So precisa fazer uma vez -- fica salvo aqui
    na maquina, do mesmo jeito que a senha do CRM."""
    print("  Preparando a conexao com o Google Drive...")
    try:
        _baixar_rclone()
        _escrever_conf()
    except Exception as e:
        print(f"  Nao consegui preparar a conexao: {e}")
        return False

    print()
    print("  Agora vai abrir o NAVEGADOR para voce fazer login no Google.")
    print("  Clique em PERMITIR quando aparecer. So precisa uma vez.")
    print()
    try:
        r = subprocess.run(
            [str(RCLONE_EXE), "config", "reconnect", "egemap:", "--config", str(RCLONE_CONF)]
        )
    except Exception as e:
        print(f"  Erro ao conectar: {e}")
        return False

    if r.returncode != 0:
        print("  Login nao concluido. Tente de novo mais tarde.")
        return False
    print("  Conectado ao Google Drive!")
    return True


def desativar_agente_antigo(log=None):
    """O agente antigo (so-Drive, rodava em PowerShell numa tarefa
    agendada) fazia esse mesmo trabalho sozinho. Com tudo junto neste
    programa agora, desliga a tarefa antiga -- senao cada proposta subiria
    duas vezes."""
    if os.name != "nt":
        return
    try:
        subprocess.run(
            ["schtasks", "/Query", "/TN", TAREFA_AGENTE_ANTIGO],
            capture_output=True, timeout=10, check=True,
        )
    except Exception:
        return  # tarefa nao existe -- nunca teve o agente antigo instalado

    try:
        subprocess.run(["schtasks", "/End", "/TN", TAREFA_AGENTE_ANTIGO],
                        capture_output=True, timeout=10)
        subprocess.run(["schtasks", "/Delete", "/TN", TAREFA_AGENTE_ANTIGO, "/F"],
                        capture_output=True, timeout=10)
        if log:
            log("Encontrei o agente antigo do Drive rodando separado e desliguei "
                "-- agora e so este programa que cuida do Drive.")
    except Exception:
        pass


def _remote(destino, nome=""):
    partes = [p for p in (destino, nome) if p]
    return "egemap:" + "/".join(partes)


# Um envio por vez. Dois envios ao mesmo tempo (uma proposta de PVC e uma de
# aluminio saindo juntas, por exemplo) rodavam dois rclone em paralelo, e cada
# um criava a pasta do cliente por conta -- foi assim que apareceram tres
# pastas iguais "Felipe Dos Santos Coelho" dentro de Balneario Gaivota.
_ENVIO_LOCK = threading.Lock()


def _normalizar(texto):
    """Reduz o nome ao essencial pra comparar: sem acento, sem pontuacao,
    tudo minusculo. "Passo De Torres" e "Passo de Torres" viram a mesma
    coisa."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _rclone(*args, **kw):
    return subprocess.run(
        [str(RCLONE_EXE), *args, "--config", str(RCLONE_CONF)],
        capture_output=True, text=True, timeout=kw.get("timeout", 30),
    )


def _listar(caminho, so_pastas=False):
    """Conteudo de uma pasta do Drive. Lista vazia se ela ainda nao existe."""
    args = ["lsjson", _remote(caminho)]
    if so_pastas:
        args.append("--dirs-only")
    try:
        r = _rclone(*args)
    except Exception:
        return []
    if r.returncode != 0 or not r.stdout.strip().startswith("["):
        return []
    try:
        return json.loads(r.stdout)
    except Exception:
        return []


def _pasta_equivalente(caminho_pai, nome):
    """Pasta que ja existe no Drive e quer dizer a mesma coisa que 'nome'.

    E o que impede o monitor de criar uma "Passo De Torres" ao lado da
    "Passo de Torres" que voce ja usa ha meses -- pro Google Drive a
    maiuscula faz outra pasta, e a proposta some da vista. Vale tambem pra
    acento ("Morro Da Fumaca" x "Morro da Fumaça").

    Quando ja existe mais de uma grafia da mesma pasta -- e existe: hoje ha
    uma "Passo de Torres" com 22 clientes e uma "Passo De Torres" com um so
    --, fica com a que tem mais coisa dentro, que e a que voce vem usando de
    verdade. E fica sempre com a mesma, pra nao alternar entre elas.
    """
    alvo = _normalizar(nome)
    iguais = sorted({f.get("Name", "") for f in _listar(caminho_pai, so_pastas=True)
                     if _normalizar(f.get("Name", "")) == alvo})
    if not iguais:
        return None
    if len(iguais) == 1:
        return iguais[0]

    def quanto_tem(n):
        return len(_listar("/".join(x for x in (caminho_pai, n) if x)))

    return max(iguais, key=lambda n: (quanto_tem(n), n == nome))


def _resolver_destino(destino):
    """Percorre o caminho nivel por nivel (Ano/Cidade/Cliente) trocando cada
    pedaco pela pasta que ja existe la. So o que realmente nao existe e que
    vai ser criado."""
    resolvido = []
    for parte in destino.split("/"):
        if not parte:
            continue
        resolvido.append(_pasta_equivalente("/".join(resolvido), parte) or parte)
    return "/".join(resolvido)


_DATA_NO_NOME = re.compile(r"\b\d{2}-\d{2}\b")


def _materiais_do_nome(nome_arquivo):
    """Copia minima da regra do monitor, so para comparar nomes de
    arquivos que ja estao no Drive -- este modulo nao importa o monitor.

    Palavra inteira e so depois da data, igual ao monitor: senao um cliente
    "Almeida" contaria como aluminio e a proposta dele apagaria a do dia
    da categoria errada.
    """
    stem = Path(nome_arquivo).stem
    m = _DATA_NO_NOME.search(stem)
    sufixo = stem[m.end():] if m else stem
    palavras = set(re.split(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ]+", sufixo.upper()))
    return {m_ for c, m_ in (("PVC", "pvc"), ("ALM", "aluminio"), ("MAD", "madeira"))
            if c in palavras}


def _categoria(materiais):
    """PVC substitui so PVC, Aluminio/Madeira substitui so Aluminio/Madeira,
    e a proposta final (sem sufixo de material) substitui outra final."""
    if materiais == {"pvc"}:
        return "pvc"
    if materiais and "pvc" not in materiais:
        return "alm"
    return "completo"


def enviar(pdf_path, destino, materiais, client="", log=None):
    """Sobe a proposta pronta para o Drive, dentro de 'destino' (caminho
    relativo a pasta raiz da Egemap no Drive, espelhando a pasta local).

    Antes de enviar, apaga qualquer PDF do mesmo tipo enviado hoje na
    mesma pasta -- assim uma proposta refeita no mesmo dia substitui a
    anterior em vez de acumular.
    """
    def _log(msg):
        if log:
            log(f"[{client}] Drive: {msg}")

    nome = Path(pdf_path).name
    hoje = date.today().isoformat()
    categoria = _categoria(materiais)

    # Um envio de cada vez, e a pasta criada de uma vez so antes de copiar:
    # dois rclone em paralelo criavam a mesma pasta duas vezes.
    with _ENVIO_LOCK:
        try:
            resolvido = _resolver_destino(destino)
            if resolvido != destino:
                _log(f"usando a pasta que ja existe: {resolvido}")
            destino = resolvido
            _rclone("mkdir", _remote(destino))
        except Exception as e:
            _log(f"aviso ao localizar a pasta no Drive — {e}")

        try:
            for f in _listar(destino):
                fname = f.get("Name", "")
                if not fname.lower().endswith(".pdf") or fname == nome:
                    continue
                if (f.get("ModTime") or "")[:10] != hoje:
                    continue
                if _categoria(_materiais_do_nome(fname)) != categoria:
                    continue
                _rclone("deletefile", _remote(destino, fname))
                _log(f"removi versao anterior de hoje ({fname})")
        except Exception as e:
            _log(f"aviso ao verificar pasta antes de enviar — {e}")

        try:
            r2 = _rclone("copyto", str(pdf_path), _remote(destino, nome),
                         "--ignore-times", timeout=120)
            if r2.returncode == 0:
                _log(f"{nome} enviado em {destino}.")
            else:
                detalhe = (r2.stderr or r2.stdout or "").strip().splitlines()
                _log(f"falha ao enviar {nome}" + (f" — {detalhe[-1]}" if detalhe else ""))
        except Exception as e:
            _log(f"erro ao enviar {nome} — {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "testar":
        print("Configurado:", configurado())
    else:
        configurar()
