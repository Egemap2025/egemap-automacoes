#!/usr/bin/env python3
"""
EGEMAP - Integracao com o CRM

Quando a proposta comercial fica pronta, este modulo faz no CRM exatamente o
que voce fazia na mao:

  1. Acha o cliente pelo nome da pasta
  2. Lanca o orcamento (nome + valor) e anexa o PDF da proposta
  3. Preenche a composicao por material da linha
  4. Marca o orcamento como feito
  5. Arrasta o cliente para "Orcamento Pronto"

O PDF mais novo sempre fica no orcamento, em qualquer etapa do funil -- e
assim que o vendedor pega a proposta atual sozinho, sem precisar pedir.

Quem da nome a linha e o nome do arquivo: "Proposta Comercial Fulano 24-08
BRANCO.pdf" vira a linha "Branco". Entao duas opcoes do mesmo material
(BRANCO e CINZA) sao duas linhas e convivem, e renomear a proposta renomeia
a linha em vez de criar outra.

Desde 23/09/2026 quem calcula o valor do negocio e o PROPRIO CRM, num gatilho
do banco, com a regra que ja era a nossa: o pedido vigente manda e, sem
pedido, vale o MAIOR orcamento. O monitor so le e conta no log -- se
escrevesse tambem, os dois brigariam. Negocio ja marcado como ganho tem o
valor congelado pelo CRM, porque la o numero vem do fechamento.

Cada linha tem tambem a COMPOSICAO por material: quanto dela e de PVC, de
aluminio, de madeira. Linha sem composicao aparece no card com a etiqueta
"Composicao pendente". O monitor preenche sozinho quando sabe a divisao --
proposta de um material so, ou COMPLETO, onde ele ja leu os dois totais na
hora de juntar.

Os passos 4 e 5 tem freio:

  - marcar feito e mover so acontece com o card numa fila de trabalho
    ("Orcamentos a Fazer" ou "Atualizacoes"). Card ja adiantado no funil so
    recebe o PDF novo, e nao volta pra tras.
  - proposta que e so uma peca ("MAD ALM", que ainda vai ser juntada com o PVC
    num COMPLETO) entrega o PDF mas nao move o card.
  - mover para "Orcamento Pronto" so quando TODOS os orcamentos cadastrados
    no negocio estao feitos. Um orcamento cadastrado = uma proposta; quando o
    cliente pediu duas opcoes separadas (uma em PVC e outra em Aluminio), o
    card espera as duas sairem.

Depois que o contrato fecha, o mesmo modulo poe o PDF do PEDIDO no card, no
lugar proprio dele ("Pedido e contrato") -- so em quem esta na etapa
"Contrato", e sem tirar nada do que ja estava anexado. O CRM so aceita um
pedido vigente por negocio: pedido novo manda o anterior para o historico.

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


# ── Composicao por material (novidade do CRM em 23/09/2026) ──────────────────

# Cada linha de orcamento/pedido tem agora a "composicao": quanto dela e de
# cada material. Linha sem composicao aparece no CRM com a etiqueta vermelha
# "Composicao pendente" e alguem tem que preencher na mao.
#
# Os nomes tem que ser EXATAMENTE estes -- sao os que a tela oferece no
# seletor (src/lib/materials.ts). "Misto" nao e escolhivel: e a etiqueta que
# o proprio banco poe na linha quando ela tem mais de um material.
MATERIAL_NA_COMPOSICAO = {
    "pvc": "PVC",
    "aluminio": "Alumínio",
    "madeira": "Madeira",
    # Portao de rolo de ferro e o que mais nao for esquadria dos tres.
    "outro": "Outro",
}
# A ordem em que as linhas aparecem no card.
ORDEM_DA_COMPOSICAO = ("pvc", "aluminio", "madeira", "outro")
MATERIAL_DA_COMPOSICAO = {v: k for k, v in MATERIAL_NA_COMPOSICAO.items()}
MATERIAL_MISTO = "Misto"


def _agora():
    """Agora, no formato que o banco do CRM guarda."""
    return datetime.now(timezone.utc).isoformat()


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


def _palavras_em_comum(a, b):
    """Palavras que os dois nomes tem em comum, sem acento nem maiuscula.

    E o que diz o quanto a semelhanca vale: dois nomes em comum reconhecem
    uma pessoa, um so ("Alexandre") nao reconhece ninguem.
    """
    return set(normalizar(a).split()) & set(normalizar(b).split())


# Palavras que nao dizem de quem e o nome. As ligacoes nunca identificam
# ninguem, e as genericas aparecem em dezenas de cards de empresa -- duas
# delas em comum nao podem valer como reconhecimento.
LIGACOES = {"de", "da", "do", "das", "dos", "e", "di", "du", "del", "y"}


def _compativel(cliente, nome, palavras_do_card=None):
    """Os dois nomes podem ser da mesma pessoa (ou da mesma empresa)?

    Duas exigencias, as duas aprendidas errando:

    1. O PRIMEIRO NOME tem que bater. Sem isso, "Jose Santos" casava com
       "Nestor Jose Toigo dos Santos" (nome do meio + sobrenome comum) e
       "Marcelo Silva" casava com "Evandro Marcelo Flores da Silva".

    2. Nao pode haver CONTRADICAO: se a pasta tem sobrenome que o card nao tem
       E o card tem sobrenome que a pasta nao tem, sao duas pessoas. Sem isso,
       "Lara Menezes Duarte" casava com "Lara Castilho" (contato gravado so
       como "Lara") e "Casa de Repouso Bem Estar" casava com "Casa De Repouso
       Bem Viver".

    Sobrar nome de um lado so esta liberado: "Lara" e "Lara Castilho" podem
    ser a mesma pessoa, e "Silvana Pires da Silva" e "Silvana Pires da
    Silva/Deivede" tambem.

    A contradicao e conferida contra TODAS as palavras do card (titulo mais
    contato), nao so contra o nome que casou. O card tem dois nomes e o
    contato as vezes esta gravado so com o primeiro nome: olhando so pra ele,
    "Lara Menezes Duarte" parecia compativel com "Lara" e o titulo "Lara
    Castilho" -- o unico que dizia que era outra pessoa -- ficava de fora.
    """
    p, q = normalizar(cliente).split(), normalizar(nome).split()
    if not p or not q:
        return False
    if p == q:
        return True
    if p[0] != q[0]:
        return False
    do_card = set(q) if palavras_do_card is None else set(palavras_do_card)
    sobra_pasta = set(p[1:]) - do_card - LIGACOES
    sobra_card = do_card - set(p) - LIGACOES
    return not (sobra_pasta and sobra_card)


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
        """[(nome, e_o_titulo?)] do card: o titulo e o nome do contato.

        Saber qual dos dois casou importa: o titulo e o nome do negocio, e o
        contato as vezes esta gravado so com o primeiro nome.
        """
        nomes = [(negocio.get("title") or "", True)]
        contato = negocio.get("contacts") or {}
        if isinstance(contato, list):
            contato = contato[0] if contato else {}
        nome_contato = " ".join(
            p for p in [contato.get("first_name"), contato.get("last_name")] if p
        )
        if nome_contato:
            nomes.append((nome_contato, False))
        return [(n, e_titulo) for n, e_titulo in nomes if n]

    @classmethod
    def _palavras_do_card(cls, negocio):
        """Todas as palavras do card: as do titulo e as do contato."""
        palavras = set()
        for nome, _ in cls._nomes_do_negocio(negocio):
            palavras |= set(normalizar(nome).split())
        return palavras

    def _ranquear(self, cliente, candidatos):
        """[(nota, palavras_em_comum, e_titulo, negocio)], do melhor pro pior.

        Nome do card que nao e COMPATIVEL com o da pasta nem entra na conta.
        Isso importa porque o card tem dois nomes (o titulo e o contato) e
        antes valia o melhor dos dois: o contato do card "Lara Castilho" esta
        gravado so como "Lara", tirava 0,90 contra a pasta "Lara Menezes
        Duarte", e o titulo -- o unico que dizia "Castilho", ou seja, que era
        outra pessoa -- era jogado fora.
        """
        notas = []
        for neg in candidatos:
            do_card = self._palavras_do_card(neg)
            melhor = (0.0, set(), False)
            for nome, e_titulo in self._nomes_do_negocio(neg):
                if not _compativel(cliente, nome, do_card):
                    continue
                nota = _semelhanca(cliente, nome)
                if nota > melhor[0]:
                    melhor = (nota, _palavras_em_comum(cliente, nome), e_titulo)
            if melhor[0] > 0:
                notas.append((*melhor, neg))
        notas.sort(key=lambda x: x[0], reverse=True)
        return notas

    def _escolher(self, notas, candidatos=()):
        """Retorna (negocio, duvida). negocio None se nao deu pra decidir."""
        if not notas:
            return None, None
        melhor, comuns, e_titulo, negocio = notas[0]
        if melhor < LIMITE_SEMELHANCA:
            return None, None

        # Quando o reconhecimento e FORTE, a nota vale sozinha:
        #   - o nome da pasta e igualzinho ao TITULO do card (cliente de um
        #     nome so, como "Adriana" ou "Kawue", cai aqui); ou
        #   - os dois nomes tem duas palavras em comum -- nome e sobrenome
        #     ja reconhecem uma pessoa.
        forte = (melhor >= 1.0 and e_titulo) or len(comuns) >= 2

        if not forte:
            # Nenhuma palavra inteira em comum: e so parecenca de letras, e
            # letra trocada e outro cliente ("Marco" x "Marcio", "Bitencourt"
            # x "Bitencurt"). Nao lanca.
            if not comuns:
                return None, None

            # Um primeiro nome sozinho nao identifica ninguem. Quase metade
            # dos cards tem o contato gravado so com o primeiro nome
            # ("Alexandre"), e o nome da pasta cai dentro dele com nota alta.
            # Foi assim que a proposta do "Alexandre Fernandes Pereira" entrou
            # no card do "Alexandre Chistiano de Oliveira" em 24/09/2026.
            #
            # So vale quando nenhum outro card tem esse mesmo nome -- ai nao
            # ha com quem confundir. Esta conferencia vem ANTES do empate:
            # senao "Leticia Borges Nedel" sairia do empate escolhendo a
            # "Leticia" aberta, que e outra pessoa.
            #
            # Procura em TODOS os cards, nao so nos que sobraram no ranking.
            # Quem foi cortado por incompatibilidade e justamente quem torna o
            # nome ambiguo: "Marcelo Silva" cortava "Marcelo Borges" e
            # "Marcelo Correia Coelho" e depois se achava sozinho.
            outro = next(
                (n for n in candidatos
                 if n.get("id") != negocio.get("id")
                 and self._palavras_do_card(n) & comuns),
                None,
            )
            if outro is None:
                outro_nota = next((n for n in notas[1:] if n[1] & comuns), None)
                outro = outro_nota[3] if outro_nota else None
            if outro is not None:
                return None, (negocio, outro)

        empatados = [n for n in notas if melhor - n[0] < MARGEM_DESEMPATE]
        if len(empatados) > 1:
            # Mesmo nome em dois cards, um aberto e um ja ganho (acontece
            # quando o cliente volta e alguem refaz o card): o orcamento novo
            # e do aberto. Com dois abertos parecidos nao da pra decidir.
            #
            # Exige nota IGUAL a do primeiro, nao so parecida: "Cristiano
            # Paulo de Matos" e "Cristiano Mat" quase empatam e sao duas
            # pessoas -- ali o card aberto nao pode ganhar do exato.
            abertos = [n for n in empatados
                       if n[0] >= melhor - 1e-9 and n[3].get("status") == "open"]
            if len(abertos) == 1:
                return abertos[0][3], None
            return None, (negocio, empatados[1][3])

        return negocio, None

    def encontrar_negocio(self, cliente):
        """Acha o card do cliente entre os negocios que ainda valem.

        Procura em todas as etapas (e nao so na fila) porque o cliente certo
        pode ja ter passado: olhar so a coluna faria uma pasta "Samuel Neotti"
        cair no card "Samuel".

        Olha tambem os ja GANHOS, desde 24/09/2026. Nao e pra lancar proposta
        em negocio fechado -- e pra o homonimo aparecer. O card certo do
        "Alexandre Fernandes Pereira" estava ganho, ficava de fora da busca, e
        sem ele o "Alexandre" do card errado ganhava sozinho.
        """
        candidatos = self.negocios_que_valem()
        negocio, duvida = self._escolher(
            self._ranquear(cliente, candidatos), candidatos)

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

    def _trocar_composicao(self, linha_id, composicao):
        """Reescreve a composicao por material de uma linha de orcamento.

        Apaga a que estava e poe a nova, igual ao que a tela do CRM faz. O
        banco tem um gatilho que, depois disso, recalcula sozinho o valor e o
        material da linha a partir dos itens -- por isso os itens tem que
        somar exatamente o total da proposta.
        """
        if not composicao:
            return
        self._tabela("deal_budget_items", f"budget_id=eq.{linha_id}", "DELETE")
        self._tabela("deal_budget_items", "", "POST", [
            {"budget_id": linha_id, "material": material,
             "value": round(float(parcela), 2), "sort_order": i}
            for i, (material, parcela) in enumerate(composicao)
        ])

    @staticmethod
    def _material_da_linha(composicao):
        """O que vai na coluna 'material' da linha: um so, ou 'Misto'."""
        if not composicao:
            return None
        if len(composicao) == 1:
            return composicao[0][0]
        return MATERIAL_MISTO

    def enviar_orcamento(self, negocio, pdf_path, nome_orcamento, materiais,
                         valor, nome_antigo=None, composicao=None):
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

        # So linha de orcamento entra na conta: o pedido tem lugar proprio no
        # CRM e nunca pode ser substituido por uma proposta.
        existentes = self._tabela(
            "deal_budgets",
            "select=id,name,value,file_url,file_name,created_at"
            f"&deal_id=eq.{negocio_id}&tipo=eq.orcamento",
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
            "tipo": "orcamento",
            "created_by": self.user_id,
        }
        # So mexe no material quando sabemos a composicao. Mandar None
        # apagaria o que alguem tivesse preenchido na mao.
        if composicao:
            registro["material"] = self._material_da_linha(composicao)

        if substituir:
            linha_id = substituir[0]["id"]
            self._tabela("deal_budgets", f"id=eq.{linha_id}", "PATCH", registro)
            for antiga in substituir[1:]:
                self._tabela("deal_budgets", f"id=eq.{antiga['id']}", "DELETE")
            for antiga in substituir:
                arquivo = antiga.get("file_url")
                if arquivo and not str(arquivo).startswith("http"):
                    self._apagar_pdf(arquivo)
        else:
            criada = self._tabela("deal_budgets", "select=id", "POST",
                                  {**registro, "deal_id": negocio_id}, retornar=True)
            linha_id = criada[0]["id"] if criada else None

        if linha_id:
            self._trocar_composicao(linha_id, composicao)

        return len(substituir)

    def valor_do_negocio(self, negocio_id):
        """Le o valor do negocio e de onde ele veio. NAO escreve nada.

        Desde 23/09/2026 quem calcula isso e o proprio CRM, num gatilho do
        banco (recalcular_valor_negocio), com a regra que o Natanael pediu:
        o pedido vigente manda; sem pedido, vale o MAIOR orcamento. O monitor
        so le pra contar no log -- se escrevesse tambem, os dois brigariam.

        O CRM congela o valor de negocio ja marcado como GANHO, porque la o
        numero vem do fechamento (com desconto). Por isso o monitor avisa,
        em vez de passar por cima.

        Devolve (valor, "pedido" ou "orcamento", mexe_sozinho).
        """
        negocios = self._tabela("deals", f"select=value,status&id=eq.{negocio_id}")
        valor = float((negocios[0].get("value") or 0) if negocios else 0)
        aberto = bool(negocios) and negocios[0].get("status") == "open"

        pedidos = self._tabela(
            "deal_budgets",
            f"select=id&deal_id=eq.{negocio_id}&tipo=eq.pedido&substituido_em=is.null",
        )
        return valor, ("pedido" if pedidos else "orcamento"), aberto

    @staticmethod
    def _linhas_do_orcamento(item):
        """Os numeros das linhas de perfil que o orcamento cadastrado pede.

        O CRM guarda a linha em dois lugares: em materiais[].linhas ("L.25")
        e em tipos.J.linha / tipos.PJ.linha. Devolve so os numeros ({"25"}),
        porque o mesmo perfil aparece escrito de varios jeitos -- "L.25",
        "L. 25", "Solene 25".
        """
        linhas = set()
        for material in (item.get("materiais") or []):
            if isinstance(material, dict):
                linhas |= {str(l) for l in (material.get("linhas") or [])}
        tipos = item.get("tipos")
        if isinstance(tipos, dict):
            for tipo in tipos.values():
                if isinstance(tipo, dict) and tipo.get("linha"):
                    linhas.add(str(tipo["linha"]))
        return {n for linha in linhas for n in re.findall(r"\d+", linha)}

    def marcar_feito(self, negocio, materiais, detalhe=""):
        """Marca feitos tantos orcamentos quantas PROPOSTAS ja estao no card.

        Um orcamento cadastrado = uma proposta. Com dois orcamentos, o card so
        anda quando os dois PDFs sairem -- e e por isso que a conta e feita
        pelo NUMERO de propostas anexadas, e nao marcando um a cada envio:

          - a mesma proposta salva de novo, depois de corrigida, substitui a
            linha que ja existia. O total de linhas nao muda, entao nada e
            marcado a mais;
          - uma proposta nao marca mais de um orcamento. Antes, ela marcava
            TODOS os pendentes do mesmo material: no card da Projetar Studio,
            com dois orcamentos os dois em aluminio, o PDF "ALM" sozinho
            marcava os dois e mandava o card pra "Orcamento Pronto" sem o
            segundo orcamento ter saido.

        Pra escolher QUAL pendente marcar primeiro valem, nesta ordem:

          1. a LINHA DO PERFIL, quando voce escreveu ela no nome do arquivo
             ("... alm 25"). E o que resolve o caso de dois orcamentos do
             mesmo material: a Projetar Studio tem um na L.25 e outro na L.32;
          2. o material da proposta.

        Nenhum dos dois decide QUANTOS: o orcamento da Leticia pede
        Madeira + PVC e veio num arquivo "ALM".

        Retorna a lista do que ainda falta (vazia se nao falta nada).
        """
        # Se a consulta que trouxe o negocio esqueceu esse campo, nao da pra
        # saber se falta orcamento -- e ai o card NAO pode andar. Falhar assim,
        # travando, e o contrario do que acontecia: com a lista vazia o monitor
        # achava que nao faltava nada e movia na primeira proposta.
        if "orcamento_detalhes" not in negocio:
            return ["(nao consegui ler os orcamentos cadastrados)"]

        detalhes = negocio.get("orcamento_detalhes") or []
        if isinstance(detalhes, str):
            try:
                detalhes = json.loads(detalhes)
            except ValueError:
                detalhes = []

        if not (isinstance(detalhes, list) and detalhes):
            return []

        propostas = self._tabela(
            "deal_budgets",
            f"select=id&deal_id=eq.{negocio['id']}&tipo=eq.orcamento",
        )
        quantos_feitos = min(len(propostas), len(detalhes))

        itens = [i for i in detalhes if isinstance(i, dict)]
        pendentes = [i for i in itens if not i.get("feito")]
        faltam_marcar = quantos_feitos - (len(itens) - len(pendentes))

        def casa_pelo_material(item):
            do_item = {
                normalizar(m.get("material"))
                for m in (item.get("materiais") or []) if isinstance(m, dict)
            }
            do_item.discard("")
            return bool(do_item & materiais)

        numeros = set(re.findall(r"\d+", detalhe or ""))

        def prioridade(item):
            linhas = self._linhas_do_orcamento(item)
            # Linha exata na frente da parecida: a Projetar Studio tem um
            # orcamento so na L.25 e outro que cita L.32 e L.25 -- a proposta
            # "25" e do primeiro.
            exato = bool(numeros) and linhas == numeros
            parcial = bool(numeros) and bool(linhas & numeros)
            return (not exato, not parcial, not casa_pelo_material(item))

        # Entre iguais vale a ordem do cadastro (sorted e estavel).
        for item in sorted(pendentes, key=prioridade)[:max(0, faltam_marcar)]:
            item["feito"] = True

        self._tabela("deals", f"id=eq.{negocio['id']}", "PATCH",
                     {"orcamento_detalhes": detalhes})

        return [i.get("nome") or "orcamento" for i in itens if not i.get("feito")]

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

        O "orcamento_detalhes" tem que vir junto: e dele que o marcar_feito
        sabe quantos orcamentos o cliente pediu. Sem esse campo a lista chega
        vazia, o monitor acha que nao falta nada e manda o card pra "Orcamento
        Pronto" na PRIMEIRA proposta. Foi o que aconteceu de 24 a 25/09/2026,
        quando a busca da proposta passou a usar esta funcao.
        """
        return self._tabela(
            "deals",
            "select=id,title,value,status,orcamento_detalhes,stage_id,contact_id,"
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
        negocio, duvida = self._escolher(
            self._ranquear(cliente, negocios), negocios)

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

    def composicao_herdada(self, negocio_id, valor):
        """Composicao do pedido, copiada do orcamento quando nao ha duvida.

        O PDF do pedido nao diz de que material ele e. Quando todos os
        orcamentos do negocio sao de UM material so, o pedido e daquele
        material e o valor inteiro vai nele. Quando misturam materiais nao da
        pra dividir -- o pedido costuma vir negociado, e chutar a divisao
        seria pior do que deixar pendente pra alguem preencher.
        """
        if valor <= 0:
            return []
        linhas = self._tabela(
            "deal_budgets",
            f"select=id&deal_id=eq.{negocio_id}&tipo=eq.orcamento",
        )
        if not linhas:
            return []
        ids = ",".join(l["id"] for l in linhas)
        itens = self._tabela("deal_budget_items",
                             f"select=material&budget_id=in.({ids})")
        materiais = {i.get("material") for i in itens if i.get("material")}
        materiais.discard(MATERIAL_MISTO)
        if len(materiais) == 1:
            return [(materiais.pop(), valor)]
        return []

    def enviar_pedido(self, negocio, pdf_path, valor, arquivo_antigo=None,
                      composicao=None):
        """Poe o pedido de fabrica no card, no lugar proprio dele.

        NUNCA tira os orcamentos: a proposta anexada quando o orcamento saiu
        continua onde estava. So mexe na linha do PROPRIO pedido.

        O CRM so aceita UM pedido vigente por negocio (indice unico no banco).
        Entao, quando chega um pedido novo e ja existe outro vigente, o
        anterior e marcado como substituido -- ele nao some, fica guardado em
        "Ver pedidos anteriores" no card. E o mesmo que a tela do CRM faz.

        Retorna (nome_da_linha, atualizou, orcamentos_intactos, substituiu).
        """
        negocio_id = negocio["id"]
        arquivo = Path(pdf_path).name

        existentes = self._tabela(
            "deal_budgets",
            "select=id,name,value,file_url,file_name,tipo,substituido_em"
            f"&deal_id=eq.{negocio_id}",
        )
        pedidos = [b for b in existentes if b.get("tipo") == "pedido"]
        orcamentos = [b for b in existentes if b.get("tipo") != "pedido"]

        # A linha do pedido e reconhecida pelo nome do arquivo, e nao pelo
        # nome da linha: assim o mesmo pedido editado de novo cai na mesma
        # linha, em vez de virar um pedido novo.
        nomes = {arquivo.strip().lower()}
        if arquivo_antigo:
            nomes.add(Path(arquivo_antigo).name.strip().lower())
        anterior = next(
            (b for b in pedidos
             if (b.get("file_name") or "").strip().lower() in nomes),
            None,
        )
        vigente = next((b for b in pedidos if not b.get("substituido_em")), None)

        caminho = self._subir_pdf(negocio_id, pdf_path)
        registro = {
            "name": NOME_LINHA_PEDIDO,
            "value": valor,
            "file_url": caminho,
            "file_name": arquivo,
            "tipo": "pedido",
            "created_by": self.user_id,
        }
        if composicao:
            registro["material"] = self._material_da_linha(composicao)

        # O card mostra "feito a partir de <orcamento>". Quando o negocio tem
        # um orcamento so, nao ha duvida de qual e; com varios, quem escolhe e
        # quem sabe -- o monitor nao chuta.
        if len(orcamentos) == 1:
            registro["orcamento_base_id"] = orcamentos[0]["id"]

        substituiu = False
        if anterior:
            registro["name"] = anterior.get("name") or NOME_LINHA_PEDIDO
            self._tabela("deal_budgets", f"id=eq.{anterior['id']}", "PATCH", registro)
            linha_id = anterior["id"]
            velho = anterior.get("file_url")
            if velho and velho != caminho and not str(velho).startswith("http"):
                self._apagar_pdf(velho)
        else:
            if vigente:
                self._tabela("deal_budgets", f"id=eq.{vigente['id']}", "PATCH",
                             {"substituido_em": _agora()})
                substituiu = True
            criada = self._tabela("deal_budgets", "select=id", "POST",
                                  {**registro, "deal_id": negocio_id}, retornar=True)
            linha_id = criada[0]["id"] if criada else None

        if linha_id:
            self._trocar_composicao(linha_id, composicao)

        return registro["name"], bool(anterior), len(orcamentos), substituiu


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
                    nome_linha=None, nome_antigo=None, parcial=False,
                    composicao=None, materiais_reais=None, detalhe=""):
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
                                            materiais, valor, nome_antigo,
                                            composicao=composicao)
        acao = "Atualizado" if substituidos else "Lancado"
        log(f"[{cliente}] CRM: {acao} '{nome_linha}' em '{titulo}' "
            f"({_nome_etapa(negocio)}) — {_reais(valor)}")

        # 2. Valor do negocio: quem faz agora e o proprio CRM, assim que a
        #    linha entra. O monitor so le e conta no log.
        total, origem, aberto = crm.valor_do_negocio(negocio["id"])
        if not aberto:
            log(f"[{cliente}] CRM: valor do negocio continua {_reais(total)} "
                f"— negocio ja fechado, o CRM trava o valor.")
        elif origem == "pedido":
            log(f"[{cliente}] CRM: valor do negocio continua {_reais(total)} "
                f"— e o do pedido, que ja fechou.")
        elif total > valor:
            log(f"[{cliente}] CRM: valor do negocio ficou {_reais(total)} "
                f"(a maior das opcoes).")
        else:
            log(f"[{cliente}] CRM: valor do negocio atualizado para {_reais(total)}.")

        # 3. Marcar feito e mover: so quando o card esta numa fila de trabalho
        #    e a proposta e a final, nao uma peca esperando o COMPLETO.
        if parcial:
            log(f"[{cliente}] CRM: e peca para juntar num COMPLETO — card "
                f"continua em '{_nome_etapa(negocio)}'.")
            return True
        if not na_fila:
            return True

        # Pra escolher QUAL orcamento marcar, vale o que o PDF tem dentro; o
        # nome do arquivo so diz de que sistema a proposta veio.
        faltando = crm.marcar_feito(negocio, materiais_reais or materiais,
                                    detalhe=detalhe)
        if faltando:
            log(f"[{cliente}] CRM: card fica em '{_nome_etapa(negocio)}' — "
                f"ainda falta: {', '.join(faltando)}")
            return True

        crm.mover_para_pronto(negocio["id"])
        log(f"[{cliente}] CRM: movido de '{_nome_etapa(negocio)}' para "
            f"'{ETAPA_DESTINO}' — total {_reais(total)}")
        return True

    except ClienteNaoEncontrado as e:
        log(f"[{cliente}] CRM: nao lancei nada — {e}")
    except CRMErro as e:
        log(f"[{cliente}] CRM: falhou — {e}")
    except Exception as e:  # nunca derruba o monitor por causa do CRM
        log(f"[{cliente}] CRM: erro inesperado — {e}")
    return False


def lancar_pedido(pdf_path, cliente, valor, log=print, arquivo_antigo=None,
                  composicao=None):
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

        if not composicao:
            composicao = crm.composicao_herdada(negocio["id"], valor)

        nome, atualizou, intactas, substituiu = crm.enviar_pedido(
            negocio, pdf_path, valor, arquivo_antigo, composicao=composicao)

        acao = "Atualizado" if atualizou else "Lancado"
        junto = f", junto dos {intactas} orcamento(s) que ja estavam la" if intactas else ""
        log(f"[{cliente}] CRM: {acao} '{nome}' em '{negocio.get('title')}' "
            f"({ETAPA_PEDIDO}) — {_reais(valor)}{junto}")
        if substituiu:
            log(f"[{cliente}] CRM: o pedido anterior virou historico "
                f"('Ver pedidos anteriores' no card).")
        if not composicao:
            log(f"[{cliente}] CRM: nao da pra saber o material do pedido — "
                f"a composicao dele fica pendente no card.")

        total, _, aberto = crm.valor_do_negocio(negocio["id"])
        if aberto:
            log(f"[{cliente}] CRM: valor do negocio agora e {_reais(total)} "
                f"— pelo pedido.")
        else:
            log(f"[{cliente}] CRM: valor do negocio continua {_reais(total)} "
                f"— negocio ja fechado, o CRM trava o valor.")
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
