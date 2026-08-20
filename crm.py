#!/usr/bin/env python3
"""
EGEMAP - Integracao com o CRM

Quando a proposta comercial fica pronta, este modulo faz no CRM exatamente o
que voce fazia na mao:

  1. Acha o cliente na coluna "Orcamentos a Fazer"
  2. Lanca o orcamento (nome + valor) e anexa o PDF da proposta
  3. Atualiza o valor do negocio (soma dos orcamentos)
  4. Marca o orcamento como feito
  5. Arrasta o cliente para "Orcamento Pronto"

O passo 5 so acontece quando TODOS os orcamentos pedidos no negocio estao
feitos -- se o cliente pediu PVC e Aluminio e so o PVC ficou pronto, o card
continua em "Orcamentos a Fazer" ate o segundo sair.

Conversa com o CRM usando o seu proprio login (mesma permissao que voce tem na
tela). Sem dependencia externa: so a biblioteca padrao do Python.
"""

import json
import os
import re
import ssl
import sys
import unicodedata
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

# ── Endereco do CRM ───────────────────────────────────────────────────────────

SUPABASE_URL = "https://wmxrporvjizjikmzvnna.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndteHJwb3J2aml6amlrbXp2bm5hIiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3Nzg4NjM3NzksImV4cCI6MjA5NDQzOTc3OX0."
    "HSrORvsT9vcYgWEXRI91Gm_LDj5bvw9VwN9CA9Gfq5o"
)
BUCKET = "deal-budgets"

ETAPA_ORIGEM = "Orcamentos a Fazer"
ETAPA_DESTINO = "Orcamento Pronto"

CONFIG_FILE = Path.home() / ".egemap_crm_config.json"

TIMEOUT = 60

# Nao mexe no CRM quando a semelhanca entre o nome da pasta e o nome do card
# fica abaixo disso -- melhor avisar do que lancar no cliente errado.
LIMITE_SEMELHANCA = 0.82
# O primeiro colocado precisa ganhar do segundo por esta margem, senao a
# escolha e considerada duvidosa (ex.: "Samuel" x "Samuel Neotti").
MARGEM_DESEMPATE = 0.08


class CRMErro(Exception):
    """Falha ao falar com o CRM (rede, login, permissao...)."""


class ClienteNaoEncontrado(CRMErro):
    """Nenhum card corresponde ao nome -- ou mais de um corresponde."""


# ── Guarda a senha protegida pelo Windows (DPAPI) ─────────────────────────────

def _dpapi(funcao, dados):
    """Chama CryptProtectData/CryptUnprotectData. So funciona no Windows."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    entrada = BLOB(len(dados), ctypes.cast(ctypes.create_string_buffer(dados),
                                           ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    api = getattr(ctypes.windll.crypt32, funcao)
    if not api(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)):
        raise OSError(f"{funcao} falhou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _proteger(senha):
    """Embaralha a senha pra ela nao ficar legivel no arquivo de config.

    No Windows usa a protecao do proprio sistema (DPAPI): so a sua conta de
    usuario consegue ler de volta. Fora do Windows guarda como texto.
    """
    if os.name == "nt":
        try:
            return {"modo": "dpapi", "dados": _dpapi("CryptProtectData", senha.encode()).hex()}
        except Exception:
            pass
    return {"modo": "texto", "dados": senha}


def _desproteger(guardado):
    if not isinstance(guardado, dict):
        return ""
    if guardado.get("modo") == "dpapi":
        try:
            return _dpapi("CryptUnprotectData", bytes.fromhex(guardado["dados"])).decode()
        except Exception:
            return ""
    return guardado.get("dados", "")


def carregar_config():
    """Retorna (email, senha). Strings vazias se ainda nao configurou."""
    if not CONFIG_FILE.exists():
        return "", ""
    try:
        dados = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return "", ""
    return dados.get("email", ""), _desproteger(dados.get("senha"))


def salvar_config(email, senha):
    CONFIG_FILE.write_text(
        json.dumps({"email": email, "senha": _proteger(senha)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass


def configurado():
    email, senha = carregar_config()
    return bool(email and senha)


# ── Comparacao de nomes ───────────────────────────────────────────────────────

def normalizar(texto):
    """Tira acento, pontuacao e maiuscula pra comparar nomes de gente."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def _semelhanca(a, b):
    """0 a 1. Nome contido no outro conta como bem parecido (ex.: 'Lara'
    dentro de 'Lara Castilho')."""
    a, b = normalizar(a), normalizar(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    base = SequenceMatcher(None, a, b).ratio()

    # "lara" x "lara castilho": todas as palavras da menor aparecem na maior
    palavras_a, palavras_b = set(a.split()), set(b.split())
    menor, maior = (palavras_a, palavras_b) if len(palavras_a) <= len(palavras_b) else (palavras_b, palavras_a)
    if menor and menor.issubset(maior):
        base = max(base, 0.88 + 0.02 * len(menor))

    return min(base, 1.0)


def _sanitizar_arquivo(nome):
    """Mesma regra que o CRM usa na tela ao subir arquivo."""
    return re.sub(r"[^\w.\-]+", "_", nome)[-120:]


def _reais(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Conversa com o CRM ────────────────────────────────────────────────────────

class CRM:
    def __init__(self, email=None, senha=None):
        if email is None or senha is None:
            email, senha = carregar_config()
        self.email = email
        self.senha = senha
        self.token = None
        self.user_id = None
        self.org_id = None

    # -- transporte --

    def _chamar(self, metodo, caminho, corpo=None, headers=None, binario=None, tipo=None):
        url = f"{SUPABASE_URL}{caminho}"
        cabecalho = {"apikey": ANON_KEY, "Accept": "application/json"}
        if self.token:
            cabecalho["Authorization"] = f"Bearer {self.token}"
        if headers:
            cabecalho.update(headers)

        if binario is not None:
            dados = binario
            cabecalho["Content-Type"] = tipo or "application/octet-stream"
        elif corpo is not None:
            dados = json.dumps(corpo).encode("utf-8")
            cabecalho["Content-Type"] = "application/json"
        else:
            dados = None

        req = urllib.request.Request(url, data=dados, headers=cabecalho, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
                bruto = r.read().decode("utf-8") or "null"
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", "replace")[:400]
            raise CRMErro(f"CRM respondeu {e.code} em {caminho}: {detalhe}") from None
        except urllib.error.URLError as e:
            raise CRMErro(f"Sem conexao com o CRM: {e.reason}") from None

        try:
            return json.loads(bruto)
        except ValueError:
            return bruto

    def _tabela(self, tabela, params, metodo="GET", corpo=None, retornar=False):
        headers = {}
        if retornar:
            headers["Prefer"] = "return=representation"
        return self._chamar(metodo, f"/rest/v1/{tabela}?{params}", corpo=corpo, headers=headers)

    # -- login --

    def entrar(self):
        if not self.email or not self.senha:
            raise CRMErro("CRM ainda nao configurado (rode: python crm.py configurar).")

        sessao = self._chamar(
            "POST", "/auth/v1/token?grant_type=password",
            corpo={"email": self.email, "password": self.senha},
        )
        self.token = sessao.get("access_token")
        if not self.token:
            raise CRMErro("Login recusado pelo CRM. Confira email e senha.")
        self.user_id = (sessao.get("user") or {}).get("id")

        perfil = self._tabela("profiles", f"select=org_id&id=eq.{self.user_id}")
        if not perfil:
            raise CRMErro("Seu usuario nao esta ligado a nenhuma organizacao no CRM.")
        self.org_id = perfil[0]["org_id"]
        return self

    # -- etapas do funil --

    def etapa(self, nome):
        """Acha a etapa pelo nome, ignorando acento e maiuscula."""
        etapas = self._tabela("pipeline_stages", f"select=id,name&org_id=eq.{self.org_id}")
        alvo = normalizar(nome)
        for e in etapas:
            if normalizar(e["name"]) == alvo:
                return e["id"]
        raise CRMErro(f"Etapa '{nome}' nao existe no funil do CRM.")

    # -- achar o cliente --

    def negocios_a_fazer(self):
        etapa_id = self.etapa(ETAPA_ORIGEM)
        return self._tabela(
            "deals",
            "select=id,title,value,orcamento_detalhes,stage_id,contact_id,"
            "contacts(first_name,last_name)"
            f"&org_id=eq.{self.org_id}&stage_id=eq.{etapa_id}&status=eq.open",
        )

    def encontrar_negocio(self, cliente):
        """Acha o card do cliente em 'Orcamentos a Fazer'.

        Levanta ClienteNaoEncontrado quando nao acha ninguem parecido, ou
        quando dois cards empatam -- nesse caso e mais seguro avisar do que
        lancar no cliente errado.
        """
        candidatos = self.negocios_a_fazer()
        if not candidatos:
            raise ClienteNaoEncontrado("Nao ha nenhum negocio em 'Orcamentos a Fazer'.")

        notas = []
        for negocio in candidatos:
            nomes = [negocio.get("title") or ""]
            contato = negocio.get("contacts") or {}
            if isinstance(contato, list):
                contato = contato[0] if contato else {}
            nome_contato = " ".join(
                p for p in [contato.get("first_name"), contato.get("last_name")] if p
            )
            if nome_contato:
                nomes.append(nome_contato)
            notas.append((max(_semelhanca(cliente, n) for n in nomes), negocio))

        notas.sort(key=lambda x: x[0], reverse=True)
        melhor, negocio = notas[0]

        if melhor < LIMITE_SEMELHANCA:
            achados = ", ".join(f"'{n['title']}'" for _, n in notas[:3])
            raise ClienteNaoEncontrado(
                f"Nenhum cliente parecido com '{cliente}' em 'Orcamentos a Fazer'. "
                f"Os mais proximos: {achados}."
            )

        if len(notas) > 1 and melhor - notas[1][0] < MARGEM_DESEMPATE:
            raise ClienteNaoEncontrado(
                f"'{cliente}' ficou parecido com mais de um card "
                f"('{negocio['title']}' e '{notas[1][1]['title']}'). "
                f"Renomeie a pasta com o nome completo do cliente."
            )

        return negocio

    # -- lancar o orcamento --

    def _subir_pdf(self, negocio_id, pdf_path):
        caminho = f"{self.org_id}/{negocio_id}/{uuid.uuid4()}-{_sanitizar_arquivo(Path(pdf_path).name)}"
        self._chamar(
            "POST", f"/storage/v1/object/{BUCKET}/{caminho}",
            binario=Path(pdf_path).read_bytes(), tipo="application/pdf",
        )
        return caminho

    def _apagar_pdf(self, caminho):
        try:
            self._chamar("DELETE", f"/storage/v1/object/{BUCKET}/{caminho}")
        except CRMErro:
            pass  # arquivo orfao no storage nao quebra nada

    def enviar_orcamento(self, negocio, pdf_path, materiais, valor):
        """Sobe o PDF e cria a linha de orcamento do negocio.

        A proposta nova substitui as linhas que ela ja contem, em vez de somar
        em cima. Isso cobre os dois casos que fariam o valor do negocio ficar
        errado: o COMPLETO, que junta PVC + Aluminio e toma o lugar dos dois
        arquivos individuais, e o orcamento refeito dias depois porque o
        cliente mudou o projeto.

        PVC e Aluminio pedidos separadamente continuam sendo duas linhas --
        um nao contem o outro.
        """
        negocio_id = negocio["id"]
        nome_orcamento = nome_do_orcamento(materiais)

        existentes = self._tabela(
            "deal_budgets",
            f"select=id,name,value,file_url,created_at&deal_id=eq.{negocio_id}",
        )

        substituir = [
            b for b in existentes
            if materiais_do_nome(b.get("name"))
            and materiais_do_nome(b.get("name")) <= materiais
        ]

        caminho = self._subir_pdf(negocio_id, pdf_path)
        registro = {
            "name": nome_orcamento,
            "value": valor,
            "file_url": caminho,
            "file_name": Path(pdf_path).name,
            "created_by": self.user_id,
        }

        if substituir:
            self._tabela("deal_budgets", f"id=eq.{substituir[0]['id']}", "PATCH", registro)
            for velho in substituir[1:]:
                self._tabela("deal_budgets", f"id=eq.{velho['id']}", "DELETE")
            for velho in substituir:
                arquivo = velho.get("file_url")
                if arquivo and not str(arquivo).startswith("http"):
                    self._apagar_pdf(arquivo)
        else:
            self._tabela("deal_budgets", "", "POST", {**registro, "deal_id": negocio_id})

        return nome_orcamento, len(substituir)

    def atualizar_valor(self, negocio_id):
        """Valor do negocio = soma dos orcamentos lancados (igual ao que voce
        digitava na mao)."""
        linhas = self._tabela("deal_budgets", f"select=value&deal_id=eq.{negocio_id}")
        total = sum(float(b["value"]) for b in linhas if b.get("value") is not None)
        self._tabela("deals", f"id=eq.{negocio_id}", "PATCH", {"value": total})
        return total

    def marcar_feito_e_mover(self, negocio, materiais):
        """Marca o orcamento como feito e move pra 'Orcamento Pronto' quando
        nao sobrar nenhum pendente.

        Retorna (moveu, pendentes).
        """
        detalhes = negocio.get("orcamento_detalhes") or []
        if isinstance(detalhes, str):
            try:
                detalhes = json.loads(detalhes)
            except ValueError:
                detalhes = []

        if isinstance(detalhes, list) and detalhes:
            marcou = False
            sem_material = []
            for item in detalhes:
                if not isinstance(item, dict) or item.get("feito"):
                    continue
                do_item = {
                    normalizar(m.get("material"))
                    for m in (item.get("materiais") or []) if isinstance(m, dict)
                }
                do_item.discard("")
                if not do_item:
                    sem_material.append(item)
                    continue
                # So da o orcamento por feito quando a proposta cobre TUDO que
                # ele pede. Um orcamento de "PVC + Aluminio" nao fica pronto so
                # porque o PVC saiu -- senao o card iria embora cedo demais.
                if do_item <= materiais:
                    item["feito"] = True
                    marcou = True

            # Orcamento sem material anotado: nao da pra conferir. Se e o unico
            # que falta, e esse mesmo.
            if not marcou and len(sem_material) == 1:
                sem_material[0]["feito"] = True

            self._tabela("deals", f"id=eq.{negocio['id']}", "PATCH",
                         {"orcamento_detalhes": detalhes})

            faltando = [i.get("nome") or "orcamento"
                        for i in detalhes if isinstance(i, dict) and not i.get("feito")]
            if faltando:
                return False, faltando

        self._tabela("deals", f"id=eq.{negocio['id']}", "PATCH", {
            "stage_id": self.etapa(ETAPA_DESTINO),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return True, []


# ── Ponto de entrada usado pelo monitor ───────────────────────────────────────

# Como o orcamento aparece no CRM, conforme o material da proposta.
NOMES_ORCAMENTO = {
    frozenset({"pvc"}): "Pvc",
    frozenset({"aluminio"}): "Aluminio",
    frozenset({"madeira"}): "Madeira",
    frozenset({"madeira", "aluminio"}): "Madeira + Aluminio",
    frozenset({"pvc", "aluminio"}): "Pvc + Aluminio",
}


MATERIAIS_CONHECIDOS = ("pvc", "aluminio", "madeira")


def nome_do_orcamento(materiais):
    return NOMES_ORCAMENTO.get(frozenset(materiais), " + ".join(sorted(m.title() for m in materiais)))


def materiais_do_nome(nome):
    """Le de volta os materiais a partir do nome da linha no CRM
    ('Pvc + Aluminio' -> {'pvc', 'aluminio'})."""
    texto = normalizar(nome)
    return {m for m in MATERIAIS_CONHECIDOS if m in texto}


def lancar_proposta(pdf_path, cliente, valor, materiais, log=print):
    """Faz o fluxo inteiro no CRM. Nunca levanta excecao: registra no log.

    pdf_path  -- proposta comercial ja pronta
    cliente   -- nome da pasta do cliente
    valor     -- total da proposta (float)
    materiais -- conjunto tipo {"pvc"}, {"aluminio"}, {"pvc","aluminio"}
    """
    if not configurado():
        return False

    materiais = {normalizar(m) for m in materiais if m}

    try:
        crm = CRM().entrar()
        negocio = crm.encontrar_negocio(cliente)

        titulo = negocio.get("title") or cliente
        nome_orcamento, substituidos = crm.enviar_orcamento(negocio, pdf_path, materiais, valor)
        acao = "Atualizado" if substituidos else "Lancado"
        log(f"[{cliente}] CRM: {acao} '{nome_orcamento}' em '{titulo}' — {_reais(valor)}")

        total = crm.atualizar_valor(negocio["id"])
        moveu, faltando = crm.marcar_feito_e_mover(negocio, materiais)

        if moveu:
            log(f"[{cliente}] CRM: movido para '{ETAPA_DESTINO}' — total {_reais(total)}")
        else:
            log(f"[{cliente}] CRM: orcamento lancado, mas o card fica em "
                f"'{ETAPA_ORIGEM}' — ainda falta: {', '.join(faltando)}")
        return True

    except ClienteNaoEncontrado as e:
        log(f"[{cliente}] CRM: nao lancei nada — {e}")
    except CRMErro as e:
        log(f"[{cliente}] CRM: falhou — {e}")
    except Exception as e:  # nunca derruba o monitor por causa do CRM
        log(f"[{cliente}] CRM: erro inesperado — {e}")
    return False


# ── Uso pela linha de comando ─────────────────────────────────────────────────

def configurar():
    print("=" * 55)
    print("   EGEMAP - Conectar o monitor ao CRM")
    print("=" * 55)
    print()
    print("Use o mesmo email e senha que voce usa para entrar no CRM.")
    print("A senha fica protegida pelo Windows, so nesta maquina.")
    print()

    email = input("Email do CRM: ").strip()
    try:
        from getpass import getpass
        senha = getpass("Senha do CRM: ")
    except Exception:
        senha = input("Senha do CRM: ")

    if not email or not senha:
        print("\nERRO: email e senha sao obrigatorios.")
        return 1

    print("\nTestando o login...")
    try:
        crm = CRM(email, senha).entrar()
        quantos = len(crm.negocios_a_fazer())
    except CRMErro as e:
        print(f"\nERRO: {e}")
        return 1

    salvar_config(email, senha)
    print(f"\nConectado! Encontrei {quantos} negocio(s) em '{ETAPA_ORIGEM}'.")
    print("A partir de agora, toda proposta pronta vai sozinha para o CRM.")
    return 0


def testar(nome=None):
    """Mostra o que o monitor faria -- sem escrever nada no CRM."""
    if not configurado():
        print("CRM ainda nao configurado. Rode: python crm.py configurar")
        return 1
    try:
        crm = CRM().entrar()
        negocios = crm.negocios_a_fazer()
    except CRMErro as e:
        print(f"ERRO: {e}")
        return 1

    print(f"\n{len(negocios)} negocio(s) em '{ETAPA_ORIGEM}':\n")
    for n in negocios:
        detalhes = n.get("orcamento_detalhes") or []
        pendentes = [d.get("nome") or "orcamento"
                     for d in detalhes if isinstance(d, dict) and not d.get("feito")]
        situacao = f"falta: {', '.join(pendentes)}" if pendentes else "sem orcamento pendente"
        print(f"  - {n['title']}  ({situacao})")

    if nome:
        print(f"\nProcurando '{nome}'...")
        try:
            achado = crm.encontrar_negocio(nome)
            print(f"  -> casaria com: '{achado['title']}'  (id {achado['id']})")
        except ClienteNaoEncontrado as e:
            print(f"  -> {e}")
    print()
    return 0


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "testar"
    if comando == "configurar":
        sys.exit(configurar())
    elif comando == "testar":
        sys.exit(testar(sys.argv[2] if len(sys.argv) > 2 else None))
    else:
        print(__doc__)
        print("Comandos:  python crm.py configurar   |   python crm.py testar [nome do cliente]")
        sys.exit(1)
