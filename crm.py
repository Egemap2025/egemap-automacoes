#!/usr/bin/env python3
"""
EGEMAP - Integracao com o CRM

Quando a proposta comercial fica pronta, este modulo faz no CRM exatamente o
que voce fazia na mao:

  1. Acha o cliente pelo nome da pasta
  2. Lanca o orcamento (nome + valor) e anexa o PDF da proposta
  3. Atualiza o valor do negocio (a maior das opcoes)
  4. Marca o orcamento como feito
  5. Arrasta o cliente para "Orcamento Pronto"

O PDF mais novo sempre fica no orcamento, em qualquer etapa do funil -- e
assim que o vendedor pega a proposta atual sozinho, sem precisar pedir.

Quem da nome a linha e o nome do arquivo: "Proposta Comercial Fulano 24-08
BRANCO.pdf" vira a linha "Branco". Entao duas opcoes do mesmo material
(BRANCO e CINZA) sao duas linhas e convivem, e renomear a proposta renomeia
a linha em vez de criar outra.

Os passos 3, 4 e 5 tem freio:

  - o valor do negocio so e mexido enquanto ele ainda e do orcamento. Depois
    de "Orcamento Apresentado" o numero e do vendedor (pode ter negociado
    desconto), e o monitor so troca o PDF.
  - marcar feito e mover so acontece com o card numa fila de trabalho
    ("Orcamentos a Fazer" ou "Atualizacoes"). Card ja adiantado no funil so
    recebe o PDF novo, e nao volta pra tras.
  - proposta que e so uma peca ("MAD ALM", que ainda vai ser juntada com o PVC
    num COMPLETO) entrega o PDF mas nao move o card.
  - mover para "Orcamento Pronto" so quando TODOS os orcamentos cadastrados
    no negocio estao feitos. Um orcamento cadastrado = uma proposta; quando o
    cliente pediu duas opcoes separadas (uma em PVC e outra em Aluminio), o
    card espera as duas sairem.

Depois que o contrato fecha, o mesmo modulo poe o PDF do PEDIDO no card, como
mais uma linha ("Pedido") ao lado da proposta -- so em quem esta na etapa
"Contrato", e sem tirar nada do que ja estava anexado.

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
import urllib.parse
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
# Comparado sem acento/maiuscula, entao casa com "Orçamentos a Fazer" do CRM
ETAPA_ORIGEM_NORM = "orcamentos a fazer"

# Filas de trabalho: card parado aqui esperando o orcamento sair. A proposta
# que chega e o orcamento sendo feito, entao marca como feito.
ETAPAS_FILA = {"orcamentos a fazer", "atualizacoes"}

# Etapas em que o valor do negocio ainda e do orcamento. Depois que a proposta
# foi apresentada, o numero passa a ser do vendedor (pode ter negociado
# desconto), entao o monitor nunca sobrescreve -- so troca o PDF.
ETAPAS_VALOR_DO_ORCAMENTO = {
    "novo lead", "contato realizado", "orcamento a definir",
    "orcamentos a fazer", "atualizacoes", "orcamento pronto",
}

# ── Pedido (etapa "Contrato") ─────────────────────────────────────────────────

# Quando o contrato fecha, o pedido de fabrica vira mais uma linha na mesma
# lista de orcamentos do card -- do lado da proposta, sem tomar o lugar dela.
ETAPA_PEDIDO = "Contrato"
ETAPA_PEDIDO_NORM = "contrato"
NOME_LINHA_PEDIDO = "Pedido"

# Card em "Contrato" quase sempre esta marcado como ganho: dos 52 que existem
# hoje, so 7 estao "open" e 45 estao "won". Procurar so entre os abertos
# deixaria 45 contratos de fora, e o pedido nunca acharia o cliente.
STATUS_QUE_VALEM = ("open", "won")

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
    """Nome do arquivo dentro do storage do CRM. Sai SO com ASCII.

    Esse nome entra na URL do envio, e o Python monta a linha do pedido HTTP
    em ASCII -- um "ç" derruba o envio inteiro com
    "'ascii' codec can't encode characters". Foi o que aconteceu com o
    cliente "Ricardo da Conceição Rezende" ("çã" em "Conceição").

    O `\\w` do Python engana: diferente do JavaScript do CRM (onde esta regra
    nasceu), ele aceita letra com acento -- por isso o "ç" passava batido por
    este filtro. Aqui o conjunto e escrito na mao, so com ASCII, pra nao
    depender desse detalhe.

    Acento vira a letra sem acento ("Conceição" -> "Conceicao") em vez de
    virar "_", pra continuar dando pra ler. O nome bonito, com acento, e
    guardado a parte (file_name) e e esse que aparece na tela do CRM.
    """
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9._-]+", "_", sem_acento)[-120:]


def _reais(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _nome_etapa(negocio):
    """Nome da etapa vindo junto do negocio na consulta."""
    etapa = negocio.get("pipeline_stages") or {}
    if isinstance(etapa, list):
        etapa = etapa[0] if etapa else {}
    return etapa.get("name") or "outra etapa"


def _etapa_de(negocio):
    return normalizar(_nome_etapa(negocio))


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
        # Trava geral: a URL tem que sair em ASCII puro, senao o Python
        # levanta "'ascii' codec can't encode characters" ao montar a linha do
        # pedido -- um erro que nao diz o que aconteceu e derruba o
        # lancamento inteiro. Aqui so o que esta fora do ASCII vira %XX; tudo
        # que ja e ASCII fica intocado, entao ?, & e = continuam valendo como
        # sintaxe da consulta.
        url = "".join(c if ord(c) < 128 else urllib.parse.quote(c)
                      for c in f"{SUPABASE_URL}{caminho}")
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

    def negocios_abertos(self):
        """Todos os negocios abertos, com o nome da etapa em que estao.

        Busca todo mundo de uma vez (e nao so a coluna 'Orcamentos a Fazer')
        porque o cliente certo pode ja ter passado de etapa: procurar so na
        coluna faria uma pasta "Samuel Neotti" cair no card "Samuel".
        """
        return self._tabela(
            "deals",
            "select=id,title,value,orcamento_detalhes,stage_id,contact_id,"
            "pipeline_stages(name),contacts(first_name,last_name)"
            f"&org_id=eq.{self.org_id}&status=eq.open",
        )

    def negocios_a_fazer(self):
        return [n for n in self.negocios_abertos() if _etapa_de(n) == ETAPA_ORIGEM_NORM]

    @staticmethod
    def _nomes_do_negocio(negocio):
        nomes = [negocio.get("title") or ""]
        contato = negocio.get("contacts") or {}
        if isinstance(contato, list):
            contato = contato[0] if contato else {}
        nome_contato = " ".join(
            p for p in [contato.get("first_name"), contato.get("last_name")] if p
        )
        if nome_contato:
            nomes.append(nome_contato)
        return [n for n in nomes if n]

    def _ranquear(self, cliente, candidatos):
        notas = [
            (max(_semelhanca(cliente, n) for n in self._nomes_do_negocio(neg)), neg)
            for neg in candidatos if self._nomes_do_negocio(neg)
        ]
        notas.sort(key=lambda x: x[0], reverse=True)
        return notas

    @staticmethod
    def _escolher(notas):
        """Retorna (negocio, duvida). negocio None se nao deu pra decidir."""
        if not notas:
            return None, None
        melhor, negocio = notas[0]
        if melhor < LIMITE_SEMELHANCA:
            return None, None
        if len(notas) > 1 and melhor - notas[1][0] < MARGEM_DESEMPATE:
            return None, (negocio, notas[1][1])
        return negocio, None

    def encontrar_negocio(self, cliente):
        """Acha o card do cliente entre todos os negocios abertos.

        Procura em todas as etapas (e nao so na fila) porque o cliente certo
        pode ja ter passado: olhar so a coluna faria uma pasta "Samuel Neotti"
        cair no card "Samuel".
        """
        negocio, duvida = self._escolher(self._ranquear(cliente, self.negocios_abertos()))

        if duvida:
            raise ClienteNaoEncontrado(
                f"'{cliente}' ficou parecido com dois cards "
                f"('{duvida[0]['title']}' e '{duvida[1]['title']}'). "
                f"Confira o nome da pasta."
            )
        if not negocio:
            raise ClienteNaoEncontrado(f"nenhum cliente parecido com '{cliente}' no CRM.")

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
        except Exception:
            pass  # arquivo orfao no storage nao quebra nada

    def enviar_orcamento(self, negocio, pdf_path, nome_orcamento, materiais,
                         valor, nome_antigo=None):
        """Sobe o PDF e cria (ou atualiza) a linha de orcamento do negocio.

        Quem identifica a linha e o NOME, que vem do nome do arquivo. Assim
        duas opcoes do mesmo material -- "Pvc Branco" e "Pvc Cinza" -- viram
        duas linhas e convivem, e renomear a proposta renomeia a linha em vez
        de criar outra.

        A linha e substituida quando:
          - tem o mesmo nome (proposta refeita, ou reenviada);
          - tem o nome antigo, no caso de um rename;
          - a proposta nova contem tudo o que ela tinha e mais alguma coisa --
            e o COMPLETO, que junta PVC + Aluminio e toma o lugar dos dois
            arquivos individuais que sairam antes.

        O terceiro caso exige conter ESTRITAMENTE mais: duas opcoes de PVC
        cobrem o mesmo material e por isso nao se atropelam.
        """
        negocio_id = negocio["id"]

        existentes = self._tabela(
            "deal_budgets",
            f"select=id,name,value,file_url,file_name,created_at&deal_id=eq.{negocio_id}",
        )

        def substitui(linha):
            nome = linha.get("name") or ""
            if normalizar(nome) == normalizar(nome_orcamento):
                return True
            if nome_antigo and normalizar(nome) == normalizar(nome_antigo):
                return True
            do_linha = materiais_do_nome(linha.get("file_name") or nome)
            return bool(do_linha) and do_linha < materiais

        substituir = [b for b in existentes if substitui(b)]

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

        return len(substituir)

    def atualizar_valor(self, negocio_id):
        """Valor do negocio = o MAIOR dos orcamentos lancados.

        Quando o cliente recebe duas opcoes (ex.: PVC branco e PVC cinza), ele
        vai fechar uma so -- somar as duas inflaria a previsao de vendas. O
        maior mostra o teto do negocio, que e como isso vinha sendo preenchido
        na mao.
        """
        linhas = self._tabela("deal_budgets", f"select=value&deal_id=eq.{negocio_id}")
        valores = [float(b["value"]) for b in linhas if b.get("value") is not None]
        maior = max(valores, default=0.0)
        self._tabela("deals", f"id=eq.{negocio_id}", "PATCH", {"value": maior})
        return maior

    def marcar_feito(self, negocio, materiais):
        """Marca como feitos os orcamentos que esta proposta cobre.

        Retorna a lista do que ainda falta (vazia se nao falta nada).
        """
        detalhes = negocio.get("orcamento_detalhes") or []
        if isinstance(detalhes, str):
            try:
                detalhes = json.loads(detalhes)
            except ValueError:
                detalhes = []

        if isinstance(detalhes, list) and detalhes:
            pendentes = [i for i in detalhes if isinstance(i, dict) and not i.get("feito")]

            # Um orcamento cadastrado = uma proposta. O material do nome do
            # arquivo (ALM/PVC/MAD) nao serve pra conferir: o orcamento da
            # Leticia pede Madeira + PVC e veio num arquivo "ALM"; o do
            # Dionatan pedia Alumínio + Madeira + PVC e saiu num "Pvc" so.
            if len(detalhes) == 1:
                detalhes[0]["feito"] = True

            else:
                # Varios orcamentos no mesmo negocio sao opcoes separadas (ex.:
                # uma em PVC e outra em Aluminio). Ai o material ajuda a saber
                # qual delas acabou de sair.
                marcou = False
                for item in pendentes:
                    do_item = {
                        normalizar(m.get("material"))
                        for m in (item.get("materiais") or []) if isinstance(m, dict)
                    }
                    do_item.discard("")
                    if do_item & materiais:
                        item["feito"] = True
                        marcou = True

                # Nenhum casou pelo material, mas so falta um: e esse.
                if not marcou and len(pendentes) == 1:
                    pendentes[0]["feito"] = True

            self._tabela("deals", f"id=eq.{negocio['id']}", "PATCH",
                         {"orcamento_detalhes": detalhes})

            return [i.get("nome") or "orcamento"
                    for i in detalhes if isinstance(i, dict) and not i.get("feito")]

        return []

    def mover_para_pronto(self, negocio_id):
        self._tabela("deals", f"id=eq.{negocio_id}", "PATCH", {
            "stage_id": self.etapa(ETAPA_DESTINO),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    # -- pedido (etapa "Contrato") --

    def negocios_que_valem(self):
        """Negocios que ainda valem: os abertos e os ja ganhos.

        O pedido chega depois do contrato assinado, e nessa altura o card
        costuma estar marcado como ganho. Se olhasse so os abertos, quase
        todo contrato ficaria de fora.
        """
        return self._tabela(
            "deals",
            "select=id,title,value,status,stage_id,contact_id,"
            "pipeline_stages(name),contacts(first_name,last_name)"
            f"&org_id=eq.{self.org_id}&status=in.({','.join(STATUS_QUE_VALEM)})",
        )

    def contratos(self):
        return [n for n in self.negocios_que_valem() if _etapa_de(n) == ETAPA_PEDIDO_NORM]

    def encontrar_contrato(self, cliente, negocios=None):
        """Acha o card do cliente e exige que ele esteja em "Contrato".

        Ranqueia entre TODOS os negocios que ainda valem -- nao so os de
        "Contrato" -- pelo mesmo motivo do fluxo da proposta: procurando so
        dentro da coluna, um pedido do "Ivan Candioto casa Noeli" cairia no
        contrato do "ivan Candiotto", que e outra pessoa. Ganhando alguem de
        fora do Contrato, nao mexe em nada e diz onde o card esta.

        negocios ja consultados podem ser passados de fora, pra conferir uma
        pasta inteira sem perguntar a lista ao CRM a cada arquivo.
        """
        if negocios is None:
            negocios = self.negocios_que_valem()
        negocio, duvida = self._escolher(self._ranquear(cliente, negocios))

        if duvida:
            raise ClienteNaoEncontrado(
                f"'{cliente}' ficou parecido com dois cards "
                f"('{duvida[0]['title']}' e '{duvida[1]['title']}'). "
                f"Confira o nome do arquivo."
            )
        if not negocio:
            raise ClienteNaoEncontrado(f"nenhum cliente parecido com '{cliente}' no CRM.")
        if _etapa_de(negocio) != ETAPA_PEDIDO_NORM:
            raise ClienteNaoEncontrado(
                f"'{negocio['title']}' esta em '{_nome_etapa(negocio)}', e pedido "
                f"so entra em '{ETAPA_PEDIDO}'."
            )
        return negocio

    @staticmethod
    def _nome_livre_pedido(existentes):
        """"Pedido" quando ainda nao tem nenhum; senao "Pedido 2", "Pedido 3"...

        Um contrato pode receber mais de um pedido, e nenhum pode tomar o
        lugar do outro.
        """
        usados = {normalizar(b.get("name")) for b in existentes}
        if normalizar(NOME_LINHA_PEDIDO) not in usados:
            return NOME_LINHA_PEDIDO
        n = 2
        while normalizar(f"{NOME_LINHA_PEDIDO} {n}") in usados:
            n += 1
        return f"{NOME_LINHA_PEDIDO} {n}"

    def enviar_pedido(self, negocio, pdf_path, valor, arquivo_antigo=None):
        """Acrescenta o pedido na lista de orcamentos do contrato.

        NUNCA tira o que ja esta la: a proposta anexada quando o orcamento
        saiu continua no lugar dela. A unica linha que este metodo substitui
        e a do PROPRIO pedido -- quando o mesmo arquivo e salvo de novo
        depois de editado, ou quando ele so foi renomeado.

        Retorna (nome_da_linha, atualizou, quantas_ficaram_intactas).
        """
        negocio_id = negocio["id"]
        arquivo = Path(pdf_path).name

        existentes = self._tabela(
            "deal_budgets",
            f"select=id,name,value,file_url,file_name&deal_id=eq.{negocio_id}",
        )

        # A linha do pedido e reconhecida pelo nome do arquivo, e nao pelo
        # nome da linha: assim o mesmo pedido editado de novo cai na mesma
        # linha, em vez de virar "Pedido 2".
        nomes = {arquivo.strip().lower()}
        if arquivo_antigo:
            nomes.add(Path(arquivo_antigo).name.strip().lower())
        anterior = next(
            (b for b in existentes
             if (b.get("file_name") or "").strip().lower() in nomes),
            None,
        )

        caminho = self._subir_pdf(negocio_id, pdf_path)
        registro = {
            "value": valor,
            "file_url": caminho,
            "file_name": arquivo,
            "created_by": self.user_id,
        }

        if anterior:
            # Mantem o nome que a linha ja tinha: "Pedido 2" continua "Pedido 2"
            registro["name"] = anterior.get("name") or NOME_LINHA_PEDIDO
            self._tabela("deal_budgets", f"id=eq.{anterior['id']}", "PATCH", registro)
            velho = anterior.get("file_url")
            if velho and velho != caminho and not str(velho).startswith("http"):
                self._apagar_pdf(velho)
        else:
            registro["name"] = self._nome_livre_pedido(existentes)
            self._tabela("deal_budgets", "", "POST", {**registro, "deal_id": negocio_id})

        return registro["name"], bool(anterior), len(existentes) - (1 if anterior else 0)


# ── Ponto de entrada usado pelo monitor ───────────────────────────────────────

# Como o orcamento aparece no CRM, conforme o material da proposta.
NOMES_ORCAMENTO = {
    frozenset({"pvc"}): "Pvc",
    frozenset({"aluminio"}): "Aluminio",
    frozenset({"madeira"}): "Madeira",
    frozenset({"madeira", "aluminio"}): "Madeira + Aluminio",
    frozenset({"pvc", "aluminio"}): "Pvc + Aluminio",
}


# Como cada material pode aparecer escrito: por extenso no nome da linha
# ("Pvc + Aluminio") ou no codigo curto que a montagem usa no nome do arquivo
# ("Proposta Comercial X 24-08 MAD ALM.pdf").
CODIGOS_MATERIAL = {
    "pvc": "pvc",
    "aluminio": "aluminio", "alm": "aluminio",
    "madeira": "madeira", "mad": "madeira",
}


def nome_do_orcamento(materiais):
    return NOMES_ORCAMENTO.get(frozenset(materiais), " + ".join(sorted(m.title() for m in materiais)))


def materiais_do_nome(nome):
    """Le de volta os materiais a partir do nome da linha ou do arquivo.

    'Pvc + Aluminio' e 'Proposta Comercial X 24-08 MAD ALM.pdf' dao o mesmo
    resultado. Compara palavra inteira, senao um cliente chamado "Madalena"
    viraria madeira.
    """
    palavras = set(normalizar(nome).split())
    return {CODIGOS_MATERIAL[p] for p in palavras if p in CODIGOS_MATERIAL}


def lancar_proposta(pdf_path, cliente, valor, materiais, log=print,
                    nome_linha=None, nome_antigo=None, parcial=False):
    """Faz o fluxo inteiro no CRM. Nunca levanta excecao: registra no log.

    pdf_path    -- proposta comercial ja pronta (com Capa e Pagina Final)
    cliente     -- nome da pasta do cliente
    valor       -- total lido na Pagina Final (float)
    materiais   -- conjunto tipo {"pvc"}, {"aluminio"}, {"pvc","aluminio"}
    nome_linha  -- como a linha aparece no CRM; vem do nome do arquivo
    nome_antigo -- nome anterior, quando a proposta acabou de ser renomeada
    parcial     -- proposta e so uma peca (ex.: "MAD ALM", que ainda vai ser
                   juntada com o PVC num COMPLETO): o PDF entra, mas o card
                   nao anda porque o orcamento nao acabou
    """
    if not configurado():
        return False

    materiais = {normalizar(m) for m in materiais if m}
    nome_linha = nome_linha or nome_do_orcamento(materiais)

    try:
        crm = CRM().entrar()
        negocio = crm.encontrar_negocio(cliente)

        titulo = negocio.get("title") or cliente
        etapa = _etapa_de(negocio)
        na_fila = etapa in ETAPAS_FILA

        # 1. O PDF mais novo sempre fica no orcamento, em qualquer etapa --
        #    e assim que o vendedor pega a proposta atual sozinho.
        substituidos = crm.enviar_orcamento(negocio, pdf_path, nome_linha,
                                            materiais, valor, nome_antigo)
        acao = "Atualizado" if substituidos else "Lancado"
        log(f"[{cliente}] CRM: {acao} '{nome_linha}' em '{titulo}' "
            f"({_nome_etapa(negocio)}) — {_reais(valor)}")

        # 2. Valor do negocio: so enquanto ele ainda e do orcamento.
        if etapa in ETAPAS_VALOR_DO_ORCAMENTO:
            total = crm.atualizar_valor(negocio["id"])
            if total > valor:
                log(f"[{cliente}] CRM: valor do negocio ficou {_reais(total)} "
                    f"(a maior das opcoes).")
        else:
            total = None
            log(f"[{cliente}] CRM: valor do negocio nao foi mexido — "
                f"'{_nome_etapa(negocio)}' e numero do vendedor.")

        # 3. Marcar feito e mover: so quando o card esta numa fila de trabalho
        #    e a proposta e a final, nao uma peca esperando o COMPLETO.
        if parcial:
            log(f"[{cliente}] CRM: e peca para juntar num COMPLETO — card "
                f"continua em '{_nome_etapa(negocio)}'.")
            return True
        if not na_fila:
            return True

        faltando = crm.marcar_feito(negocio, materiais)
        if faltando:
            log(f"[{cliente}] CRM: card fica em '{_nome_etapa(negocio)}' — "
                f"ainda falta: {', '.join(faltando)}")
            return True

        crm.mover_para_pronto(negocio["id"])
        log(f"[{cliente}] CRM: movido de '{_nome_etapa(negocio)}' para "
            f"'{ETAPA_DESTINO}'"
            + (f" — total {_reais(total)}" if total is not None else ""))
        return True

    except ClienteNaoEncontrado as e:
        log(f"[{cliente}] CRM: nao lancei nada — {e}")
    except CRMErro as e:
        log(f"[{cliente}] CRM: falhou — {e}")
    except Exception as e:  # nunca derruba o monitor por causa do CRM
        log(f"[{cliente}] CRM: erro inesperado — {e}")
    return False


def lancar_pedido(pdf_path, cliente, valor, log=print, arquivo_antigo=None):
    """Poe o PDF do pedido no card do cliente. Nunca levanta excecao.

    E o passo depois da proposta: contrato fechado, o pedido de fabrica entra
    no mesmo lugar em que a proposta esta, como mais uma linha.

    So mexe em quem esta em "Contrato" -- pedido de quem ainda esta em
    orcamento nao existe, e cair no card errado seria pior do que nao fazer
    nada. E so acrescenta: nada do que ja estava anexado sai dali.

    pdf_path       -- PDF do pedido, do jeito que esta na pasta
    cliente        -- nome do cliente lido do nome do arquivo
    valor          -- valor do pedido (float)
    arquivo_antigo -- nome anterior, quando o pedido acabou de ser renomeado
    """
    if not configurado():
        return False

    try:
        crm = CRM().entrar()
        negocio = crm.encontrar_contrato(cliente)

        nome, atualizou, intactas = crm.enviar_pedido(
            negocio, pdf_path, valor, arquivo_antigo)

        acao = "Atualizado" if atualizou else "Lancado"
        junto = f", junto das {intactas} linha(s) que ja estavam la" if intactas else ""
        log(f"[{cliente}] CRM: {acao} '{nome}' em '{negocio.get('title')}' "
            f"({ETAPA_PEDIDO}) — {_reais(valor)}{junto}")
        return True

    except ClienteNaoEncontrado as e:
        log(f"[{cliente}] CRM: nao lancei o pedido — {e}")
    except CRMErro as e:
        log(f"[{cliente}] CRM: falhou — {e}")
    except Exception as e:  # nunca derruba o monitor por causa do CRM
        log(f"[{cliente}] CRM: erro inesperado — {e}")
    return False


# ── Uso pela linha de comando ─────────────────────────────────────────────────

def _ler_senha(rotulo):
    """Le a senha mostrando * a cada tecla.

    O getpass normal do Python nao mostra absolutamente nada enquanto se
    digita, e quem nao conhece acha que o teclado travou.
    """
    print(rotulo, end="", flush=True)

    if os.name == "nt":
        import msvcrt
        senha = ""
        while True:
            tecla = msvcrt.getwch()
            if tecla in ("\r", "\n"):
                print()
                return senha
            if tecla == "\x03":            # Ctrl+C
                raise KeyboardInterrupt
            if tecla == "\b":
                if senha:
                    senha = senha[:-1]
                    print("\b \b", end="", flush=True)
            elif tecla in ("\x00", "\xe0"):  # setas, F1..F12: ignora
                msvcrt.getwch()
            else:
                senha += tecla
                print("*", end="", flush=True)

    try:
        from getpass import getpass
        return getpass("")
    except Exception:
        return input()


def configurar():
    print("=" * 55)
    print("   EGEMAP - Conectar o monitor ao CRM")
    print("=" * 55)
    print()
    print("Use o mesmo email e senha que voce usa para entrar no CRM.")
    print("A senha fica protegida pelo Windows, so nesta maquina.")
    print()

    # Erro de digitacao no email ou na senha e comum: deixa tentar de novo
    # em vez de fechar e obrigar a abrir o programa outra vez.
    for tentativa in range(1, 4):
        email = input("Email do CRM: ").strip()
        senha = _ler_senha("Senha do CRM (aparece como ***): ")

        if not email or not senha:
            print("\nPreencha os dois campos.\n")
            continue

        print(f"\nTestando o login de {email}...")
        try:
            crm = CRM(email, senha).entrar()
            quantos = len(crm.negocios_a_fazer())
        except CRMErro as e:
            print(f"\nNao deu certo: {e}")
            if tentativa < 3:
                print("\nConfira se o email esta escrito exatamente igual ao do")
                print("CRM e se a senha e a mesma do site. Vamos de novo:\n")
                continue
            print("\nDeixa pra la por enquanto -- o monitor funciona sem o CRM.")
            print("Da pra tentar quando quiser, e so abrir o programa de novo.")
            return 1

        salvar_config(email, senha)
        print(f"\nConectado! Encontrei {quantos} negocio(s) em '{ETAPA_ORIGEM}'.")
        print("A partir de agora, toda proposta pronta vai sozinha para o CRM.")
        return 0

    return 1


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


def testar_contrato(nome=None):
    """Mostra em qual contrato um pedido cairia -- sem escrever no CRM."""
    if not configurado():
        print("CRM ainda nao configurado. Rode: python crm.py configurar")
        return 1
    try:
        crm = CRM().entrar()
        contratos = crm.contratos()
    except CRMErro as e:
        print(f"ERRO: {e}")
        return 1

    print(f"\n{len(contratos)} cliente(s) em '{ETAPA_PEDIDO}':\n")
    for n in sorted(contratos, key=lambda x: (x.get("title") or "").lower()):
        print(f"  - {n['title']}")

    if nome:
        print(f"\nProcurando '{nome}'...")
        try:
            achado = crm.encontrar_contrato(nome)
            print(f"  -> o pedido iria para: '{achado['title']}'  (id {achado['id']})")
        except ClienteNaoEncontrado as e:
            print(f"  -> nao iria pra lugar nenhum: {e}")
    print()
    return 0


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "testar"
    argumento = sys.argv[2] if len(sys.argv) > 2 else None
    if comando == "configurar":
        sys.exit(configurar())
    elif comando == "testar":
        sys.exit(testar(argumento))
    elif comando in ("contratos", "pedido"):
        sys.exit(testar_contrato(argumento))
    else:
        print(__doc__)
        print("Comandos:")
        print("  python crm.py configurar")
        print("  python crm.py testar [nome do cliente]      (fila de orcamentos)")
        print("  python crm.py contratos [nome do cliente]   (para onde o pedido iria)")
        sys.exit(1)
