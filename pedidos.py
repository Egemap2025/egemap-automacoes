#!/usr/bin/env python3
"""
EGEMAP - Pedidos

O passo depois da proposta. Quando o contrato fecha, o pedido de fabrica e
salvo em PDF numa pasta so dele (ex.: "Pedidos 2026"). Este modulo pega esse
PDF e poe no card do cliente no CRM, na mesma lista em que a proposta ja esta:

  1. Le o nome do cliente no NOME DO ARQUIVO ("Pedido - Fulano de Tal.pdf")
  2. Le o valor do pedido (do nome do arquivo ou de dentro do PDF)
  3. Acha o cliente no CRM -- so entre os que estao em "Contrato"
  4. Anexa o PDF como a linha "Pedido", ao lado do que ja estava la

Duas coisas que este modulo nunca faz, de proposito:

  - nunca tira nada do CRM. A proposta anexada quando o orcamento saiu fica
    onde esta; o pedido entra junto, como mais uma linha.
  - nunca mexe no arquivo. O PDF continua na pasta, com o mesmo nome. Salvar
    de novo depois de editar so atualiza a mesma linha la no CRM.

Sem dependencia nova: usa o PyMuPDF que o monitor ja usa e o crm.py.
"""

import re
import sys
import time
import unicodedata
from pathlib import Path

import fitz

import crm as crm_egemap


# ── Nome do cliente (vem do nome do arquivo) ──────────────────────────────────

# Palavras que aparecem no nome do arquivo mas nao sao o nome de ninguem.
PALAVRAS_DE_SISTEMA = {
    "PEDIDO", "PEDIDOS", "PED", "ORCAMENTO", "ORCAMENTOS", "PROPOSTA",
    "COMERCIAL", "CONTRATO", "EGEMAP", "COMPLETO", "FINAL", "ASSINADO",
    "COPIA", "REV", "REVISAO", "OS", "NF", "NUM", "NUMERO",
    "PVC", "ALM", "MAD", "ALUMINIO", "MADEIRA", "OBRA", "CLIENTE",
    # um segundo pedido do mesmo cliente costuma ganhar uma dessas
    "ADICAO", "ADICIONAL", "COMPLEMENTO", "COMPLEMENTAR", "EXTRA", "PARTE",
}

# So arquivo que comeca com "Pedido" e pedido. A pasta tambem guarda outros
# PDFs (ex.: "EGEMAP_Solene_Material_Comercial.pdf") -- sem esta regra, o
# nome de um deles seria lido como se fosse o nome de um cliente.
PRIMEIRA_PALAVRA_DE_PEDIDO = {"PEDIDO", "PEDIDOS", "PED"}

# "12.345,67", "1234,56", "R$ 12.345,67" -- exige os centavos com virgula pra
# nao confundir numero de pedido ou data com dinheiro. E nao pode ter letra
# grudada depois: "Pedido - Ana 1,50m x 2,00m.pdf" e medida, nao dinheiro.
VALOR_ESCRITO = re.compile(
    r"R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})(?![\dA-Za-zÀ-ÖØ-öø-ÿ])")


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c))


def _palavras_do_nome(pdf_path):
    return [p for p in re.split(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ]+",
                                _sem_acento(Path(pdf_path).stem)) if p]


def e_pedido(pdf_path):
    """Diz se o arquivo e mesmo um pedido: "Pedido - Nome do Cliente.pdf"."""
    palavras = _palavras_do_nome(pdf_path)
    return bool(palavras) and palavras[0].upper() in PRIMEIRA_PALAVRA_DE_PEDIDO


def nome_do_cliente(pdf_path):
    """Le o nome do cliente no nome do arquivo.

    "PEDIDO 1234 - Joao da Silva 15-08 R$ 12.345,67.pdf" -> "Joao da Silva"

    Sai fora tudo que tem numero (numero do pedido, data, valor) e as palavras
    do dia a dia ("PEDIDO", "PVC", "ASSINADO"). O que sobra e o nome. As
    letras soltas tambem saem ("J." de "Ezequiel J. de Biasi"): o CRM casa o
    nome mesmo sem elas, e sozinhas so atrapalhariam a comparacao.
    """
    stem = VALOR_ESCRITO.sub(" ", Path(pdf_path).stem)

    palavras = []
    for parte in re.split(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ]+", stem):
        if not parte or len(parte) == 1:
            continue
        if any(c.isdigit() for c in parte):
            continue
        if _sem_acento(parte).upper() in PALAVRAS_DE_SISTEMA:
            continue
        palavras.append(parte)

    return " ".join(palavras).strip()


# ── Valor do pedido ───────────────────────────────────────────────────────────

# Do mais especifico para o mais generico: o primeiro que casar manda. Isto
# aqui e a leitura ANTIGA, de texto corrido. Hoje ela so entra quando a
# leitura por posicao (totais_do_pedido) nao acha rotulo nenhum.
ROTULOS_DE_VALOR = (
    (r"TOTAL\s+GERAL\s*\(\s*R\$\s*\)\s*:?\s*R?\$?\s*([\d.,]+)", "TOTAL GERAL"),
    (r"(?:VALOR|TOTAL)\s+D[OA]\s+PEDIDO\s*:?\s*R?\$?\s*([\d.,]+)", "VALOR DO PEDIDO"),
    (r"VALOR\s+D[OA]\s+CONTRATO\s*:?\s*R?\$?\s*([\d.,]+)", "VALOR DO CONTRATO"),
    (r"VALOR\s+TOTAL\s*:?\s*R?\$?\s*([\d.,]+)", "VALOR TOTAL"),
    (r"TOTAL\s+GERAL\s*:?\s*R?\$?\s*([\d.,]+)", "TOTAL GERAL"),
    (r"TOTAL\s*:\s*R?\$?\s*([\d.,]+)", "TOTAL"),
)

DINHEIRO_NO_TEXTO = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")

# So dinheiro: exige os centavos com virgula, pra nao pegar numero de pedido,
# CNPJ, data ou medida.
SO_DINHEIRO = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")

def para_numero(texto):
    """"12.345,67" -> 12345.67. Zero quando nao da pra ler.

    Aceita sujeira em volta ("16.000,00 (=)", "R$ 1.234,56"): pega o primeiro
    dinheiro que encontrar. O Archicentro imprime o total com um "(+)" ou um
    "(=)" grudado, e sem isto o valor virava zero.
    """
    achado = SO_DINHEIRO.search(str(texto or "").replace("\xa0", " "))
    if achado:
        try:
            return float(achado.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            return 0.0

    bruto = (texto or "").replace("R$", "").replace("\xa0", "").strip().strip(".,-")
    bruto = bruto.replace(" ", "")
    if not bruto or not any(c.isdigit() for c in bruto):
        return 0.0
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", bruto):     # 12.345 e milhar
        bruto = bruto.replace(".", "")
    try:
        return float(bruto)
    except ValueError:
        return 0.0


def texto_do_pdf(pdf_path):
    """Texto do PDF, incluindo o que foi digitado nos campos de formulario.

    O pedido e editado antes de ser salvo, e o que se digita num campo de
    formulario nao aparece no texto normal da pagina -- por isso os campos
    sao lidos a parte.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return ""
    try:
        partes = []
        for pagina in doc:
            partes.append(pagina.get_text())
            try:
                for campo in pagina.widgets() or []:
                    if campo.field_value:
                        partes.append(str(campo.field_value))
            except Exception:
                pass
        return "\n".join(partes)
    except Exception:
        return ""
    finally:
        doc.close()

# Os rotulos que fecham um pedido. Dois sistemas imprimem o pedido e os dois
# usam a palavra "TOTAL" -- mas querendo dizer coisas diferentes:
#
#   Archicentro (PVC)   escreve o rotulo com "(R$)" do lado:
#       TOTAL DAS ABERTURAS (R$)  17.091,14 (+)     <- bruto
#       DESCONTO (R$)              1.091,14 (-)
#       TOTAL (R$)                16.000,00 (=)     <- e ESTE que vale
#
#   W-Vetro (aluminio/madeira)  escreve com dois pontos:
#       TOTAL:                     8.383,45         <- bruto
#       DESCONTO:                    383,45
#       TOTAL COM DESCONTO:        8.000,00         <- e ESTE que vale
#       VALOR TOTAL DO PEDIDO:     8.000,00
#
#   e as vezes chama o fechado de "TOTAL GERAL:", com mais de um desconto:
#       TOTAL:                    32.406,48         <- bruto
#       DESCONTO                   2.685,00
#       DESCONTO                   5.721,48
#       TOTAL GERAL:              24.000,00         <- e ESTE que vale
#
# De cada sistema vale sempre o ULTIMO total impresso: a folha fecha de cima
# pra baixo, entao o de baixo ja tem todos os descontos.
#
# Por isso o "(R$)" decide de que sistema o rotulo e. Sem isso, o "TOTAL" do
# Archicentro (que ja tem o desconto) seria lido como o "TOTAL" do W-Vetro
# (que ainda nao tem).
#
# "VALOR TOTAL (R$)" fica de fora de proposito: ele aparece em CADA item do
# Archicentro e nao e total de nada.
FECHAMENTO_PVC = ("TOTAL COM DESCONTO", "TOTAL GERAL", "TOTAL")
FECHAMENTO_ALM = ("VALOR TOTAL DO PEDIDO", "VALOR TOTAL DO ORCAMENTO",
                  "TOTAL COM DESCONTO", "TOTAL GERAL")

ROTULOS_PVC = FECHAMENTO_PVC + ("TOTAL DAS ABERTURAS", "DESCONTO")
ROTULOS_ALM = FECHAMENTO_ALM + ("TOTAL", "DESCONTO")

# O resumo que o vendedor escreve a mao no fim do pedido do W-Vetro:
#
#       Alumínio: 70.370,04
#       PVC: 117.969,06
#       Desconto: 28.339,10
#       Total: 160.000,00
#
# Quando ele existe, e a melhor fonte que ha: ja traz o valor fechado E a
# divisao por material, escrita por quem fez o pedido.
MATERIAL_NO_RESUMO = {
    "ALUMINIO": "aluminio",
    "ALUMINO": "aluminio",
    "PVC": "pvc",
    "MADEIRA": "madeira",
    "OUTRO": "outro",
    "OUTROS": "outro",
}
LINHA_DO_RESUMO = re.compile(
    r"^([A-Za-zÀ-ÖØ-öø-ÿ]+)\s*:?\s*(?:R\$)?\s*"
    r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s*$")


def _limpo(texto):
    """MAIUSCULA, sem acento, sem ":" e sem "(R$)" -- so o rotulo."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    t = t.replace("(R$)", " ").replace("R$", " ")
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", t).split())


def _e_do_pvc(texto):
    """O rotulo veio do sistema de PVC? E o "(R$)" que diz."""
    return "R$" in (texto or "").upper()


def _linhas_com_posicao(pagina):
    """[(altura, esquerda, texto)] da pagina, de cima pra baixo."""
    saida = []
    for bloco in pagina.get_text("dict").get("blocks", []):
        if bloco.get("type") != 0:
            continue
        for linha in bloco.get("lines", []):
            texto = "".join(s["text"] for s in linha.get("spans", [])).strip()
            if texto:
                saida.append((round(linha["bbox"][1]), round(linha["bbox"][0]), texto))
    return sorted(saida)


# "16.000,00 (=)" -- o Archicentro gruda o sinal da conta no valor.
SINAL_DA_CONTA = ("", "(+)", "(-)", "(=)", "+", "-", "=")


def _rotulo_e_valor(texto):
    """Separa o rotulo do valor quando os dois vem na MESMA caixa de texto.

        "TOTAL GERAL: 66.000,00"  ->  ("TOTAL GERAL", 66000.0)
        "TOTAL DAS ABERTURAS (R$)" -> ("TOTAL DAS ABERTURAS (R$)", 0.0)

    Em alguns pedidos o rotulo e o valor sao duas caixas lado a lado; em
    outros sao a mesma caixa. Sem isto, "TOTAL GERAL: 66.000,00" nao era
    reconhecido como rotulo nenhum e o pedido ia pro CRM so com a parte de
    PVC -- foi o caso do pedido do Bruno Luiz Salvan.
    """
    achado = None
    for m in SO_DINHEIRO.finditer(texto):
        achado = m
    if not achado or texto[achado.end():].strip() not in SINAL_DA_CONTA:
        return texto, 0.0
    return texto[:achado.start()], para_numero(achado.group(1))


def _dinheiro_na_mesma_altura(linhas, i):
    """O dinheiro impresso na mesma altura do rotulo, do lado direito.

    E assim que estes PDFs sao montados: o rotulo numa caixa de texto e o
    valor em outra, lado a lado. Ler o texto corrido nao serve, porque a
    ordem em que as caixas foram desenhadas nao e a ordem em que elas
    aparecem na folha -- as vezes o valor vem ANTES do rotulo.

    A altura do valor cai ate uns 3 pontos fora da do rotulo (o numero e
    impresso numa fonte menor), por isso a folga.
    """
    y, x, _ = linhas[i]
    for yy, xx, texto in linhas:
        if abs(yy - y) > 3 or xx <= x:
            continue
        achado = SO_DINHEIRO.search(texto)
        if achado:
            return para_numero(achado.group(1))
    return 0.0


def _paginas(pdf_path):
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return []
    try:
        return [_linhas_com_posicao(p) for p in doc]
    except Exception:
        return []
    finally:
        doc.close()


def resumo_do_pedido(pdf_path, paginas=None):
    """O resumo por material escrito no fim do pedido. {} quando nao ha.

        {"materiais": {"aluminio": 70370.04, "pvc": 117969.06},
         "desconto": 28339.10, "total": 160000.00}

    So aceita quando a conta fecha: a soma dos materiais menos o desconto
    tem que dar o total. Texto parecido que nao fecha e ignorado -- e melhor
    nao ter resumo do que ter um resumo inventado.
    """
    if paginas is None:
        paginas = _paginas(pdf_path)

    materiais, desconto, total = {}, 0.0, 0.0
    for linhas in paginas:
        for i, (_, _, texto) in enumerate(linhas):
            achado = LINHA_DO_RESUMO.match(texto.strip())
            if achado:
                rotulo, valor = _limpo(achado.group(1)), para_numero(achado.group(2))
            else:
                rotulo = _limpo(texto)
                if not rotulo or rotulo not in MATERIAL_NO_RESUMO or not texto.rstrip().endswith(":"):
                    continue
                valor = _dinheiro_na_mesma_altura(linhas, i)
            if valor <= 0:
                continue
            if rotulo in MATERIAL_NO_RESUMO:
                materiais[MATERIAL_NO_RESUMO[rotulo]] = valor
            elif rotulo == "DESCONTO":
                desconto = valor
            elif rotulo == "TOTAL":
                total = valor

    if not materiais or total <= 0:
        return {}
    if abs(sum(materiais.values()) - desconto - total) > 0.02:
        return {}
    return {"materiais": materiais, "desconto": desconto, "total": total}


def totais_do_pedido(pdf_path, paginas=None):
    """Os totais que o pedido imprime, lidos pela posicao na folha.

    Um pedido pode trazer DUAS partes no mesmo PDF: a do sistema de PVC e a
    do W-Vetro (aluminio/madeira). Cada uma fecha com o seu proprio total, e
    o valor do pedido e a soma das duas.

    Devolve so o que o PDF trouxer:

        {"pvc": 16000.0, "pvc_bruto": 17091.14,
         "alm": 8000.0,  "alm_bruto": 8383.45, "desconto": 383.45}

    De cada sistema vale o ULTIMO total impresso: a folha fecha de cima pra
    baixo (bruto, desconto, fechado), entao o de baixo ja tem o desconto.
    """
    if paginas is None:
        paginas = _paginas(pdf_path)

    achados = []            # (pagina, altura, sistema, rotulo, valor)
    for n, linhas in enumerate(paginas):
        for i, (y, _, texto) in enumerate(linhas):
            so_rotulo, junto = _rotulo_e_valor(texto)
            rotulo = _limpo(so_rotulo)
            if not rotulo:
                continue
            sistema = "pvc" if _e_do_pvc(so_rotulo) else "alm"
            conhecidos = ROTULOS_PVC if sistema == "pvc" else ROTULOS_ALM
            if rotulo not in conhecidos:
                continue
            valor = junto or _dinheiro_na_mesma_altura(linhas, i)
            if valor > 0:
                achados.append((n, y, sistema, rotulo, valor))

    totais = {}
    for sistema, fechamento, bruto in (("pvc", FECHAMENTO_PVC, "TOTAL DAS ABERTURAS"),
                                       ("alm", FECHAMENTO_ALM, "TOTAL")):
        do_sistema = [a for a in achados if a[2] == sistema]
        if not do_sistema:
            continue
        fecha = [a for a in do_sistema if a[3] in fechamento]
        if fecha:
            totais[sistema] = fecha[-1][4]
        brutos = [a for a in do_sistema if a[3] == bruto]
        if brutos:
            totais[f"{sistema}_bruto"] = brutos[-1][4]
        if sistema not in totais and brutos:
            totais[sistema] = brutos[-1][4]
        descontos = [a for a in do_sistema if a[3] == "DESCONTO"]
        if descontos:
            totais.setdefault("desconto", 0.0)
            totais["desconto"] += descontos[-1][4]
    return totais


def _soma_das_esquadrias(pdf_path):
    """Quanto as esquadrias do quadro do W-Vetro somam. Zero se nao der."""
    try:
        return round(sum(i["valor"] for i in _leitor().itens_do_orcamento(pdf_path)), 2)
    except Exception:
        return 0.0


def _fechamento(totais, resumo=None, bruto_alm=0.0):
    """(valor do pedido, de onde saiu). Zero quando nao da pra saber.

    bruto_alm -- quanto as esquadrias do W-Vetro somam, quando da pra ler.
    Serve pra reconhecer o caso em que o "TOTAL GERAL:" escrito no fim da
    folha do W-Vetro ja e o total do pedido INTEIRO, PVC junto. Quando isso
    acontece, somar o PVC de novo dobraria essa parte.
    """
    if resumo:
        return resumo["total"], "resumo por material escrito no pedido"

    pvc = totais.get("pvc", 0.0)
    alm = totais.get("alm", 0.0)
    com_desconto = totais.get("desconto", 0.0) > 0

    cheio_alm = totais.get("alm_bruto") or bruto_alm or 0.0
    if pvc > 0 and alm > cheio_alm + 0.02 > 0:
        return alm, "total geral do pedido, ja com desconto"

    if pvc > 0 and alm > 0:
        return pvc + alm, ("PVC + aluminio, ja com desconto" if com_desconto
                           else "PVC + aluminio")
    if pvc > 0:
        return pvc, "total do PVC" + (", ja com desconto" if com_desconto else "")
    if alm > 0:
        return alm, "total" + (" com desconto" if com_desconto else "")
    return 0.0, ""


def valor_do_pedido(pdf_path):
    """Valor do pedido. Retorna (valor, de onde saiu).

    Procura nesta ordem:

      1. no nome do arquivo -- se voce escreveu o valor ali, e ele que vale,
         porque foi escolha sua;
      2. no resumo por material escrito no fim do pedido ("Alumínio: ... /
         PVC: ... / Desconto: ... / Total: ..."), quando a conta fecha;
      3. nos totais impressos, lidos pela POSICAO na folha: o do PVC mais o
         do aluminio, cada um ja com o seu desconto;
      4. num rotulo dentro do PDF, lendo o texto corrido (jeito antigo);
      5. no maior valor em reais do documento.

    Os passos 2 e 3 sao novos. Antes o 4 era o primeiro, e ele pegava o
    "TOTAL GERAL (R$)" -- que num pedido de PVC + aluminio e o total de SO a
    parte de PVC, e que num pedido com desconto e o valor ANTES do desconto.
    Foi o que aconteceu com o pedido do Jardel Pires Coelho em 30/09/2026:
    foi pro CRM 28.130,67, que era so o PVC, faltando 10.141,86 de aluminio.
    """
    no_nome = VALOR_ESCRITO.search(Path(pdf_path).stem)
    if no_nome:
        valor = para_numero(no_nome.group(1))
        if valor > 0:
            return valor, "escrito no nome do arquivo"

    paginas = _paginas(pdf_path)
    valor, de_onde = _fechamento(totais_do_pedido(pdf_path, paginas),
                                 resumo_do_pedido(pdf_path, paginas),
                                 _soma_das_esquadrias(pdf_path))
    if valor > 0:
        return valor, de_onde

    texto = texto_do_pdf(pdf_path)
    if not texto:
        return 0.0, ""

    for padrao, rotulo in ROTULOS_DE_VALOR:
        achados = re.findall(padrao, texto, re.IGNORECASE)
        if achados:
            # O ultimo, como no orcamento do W-Vetro: o total fecha o documento
            valor = para_numero(achados[-1])
            if valor > 0:
                return valor, f"lido em '{rotulo}'"

    valores = [para_numero(v) for v in DINHEIRO_NO_TEXTO.findall(texto)]
    maior = max(valores, default=0.0)
    if maior > 0:
        return maior, "maior valor do documento"

    return 0.0, ""

# ── Divisao por material ──────────────────────────────────────────────────────

def _leitor():
    """O leitor de esquadrias do monitor, pego so na hora de usar.

    Nao da pra importar o monitor aqui em cima: ele importa este modulo na
    abertura, e os dois ficariam se esperando.

    Dentro do EGEMAP-Monitor.exe o monitor nao se chama "monitorar" -- ele e
    o programa principal, e se chama "__main__". Por isso a procura comeca
    pelos modulos que ja estao carregados: sem isso, a divisao por material
    funcionaria aqui no teste e nunca no .exe.
    """
    for nome in ("monitorar", "__main__"):
        modulo = sys.modules.get(nome)
        if modulo is not None and hasattr(modulo, "itens_do_orcamento"):
            return modulo
    import monitorar
    return monitorar


def _repartir(fatias, total):
    """Arredonda as fatias pra que elas somem EXATAMENTE o total.

    O gatilho do CRM recalcula o valor da linha somando a composicao. Se as
    fatias somarem um centavo a mais, o valor do pedido muda no card.
    """
    arredondadas = {m: round(v, 2) for m, v in fatias.items()}
    sobra = round(total - sum(arredondadas.values()), 2)
    if sobra and arredondadas:
        maior = max(arredondadas, key=lambda m: arredondadas[m])
        arredondadas[maior] = round(arredondadas[maior] + sobra, 2)
    return arredondadas


def composicao_do_pedido(pdf_path, valor, log=print, cliente=""):
    """Quanto do pedido e de cada material, pro CRM preencher a composicao.

    Duas fontes, nesta ordem:

      1. o resumo escrito no fim do pedido ("Alumínio: ... / PVC: ... /
         Desconto: ... / Total: ..."). Quem fez o pedido ja separou -- nada
         melhor do que isso;
      2. as esquadrias UMA A UMA no quadro do W-Vetro, somadas por material.
         E a mesma leitura da proposta, entao uma porta de madeira dentro de
         um pedido de aluminio cai no material certo. A parte de PVC vem de
         outro sistema, que nao tem esse quadro, e entra inteira pelo total
         dela.

    O desconto de cada sistema e aplicado na parte dele, proporcionalmente.
    E se o valor fechado foi escrito no nome do arquivo, a divisao inteira e
    ajustada pra somar esse valor.

    Devolve vazio em qualquer duvida -- ai a composicao fica pendente no card
    e alguem preenche na mao. Preencher na mao custa um minuto; mandar uma
    divisao errada muda o valor do pedido no CRM, porque o banco recalcula a
    linha somando a composicao.
    """
    try:
        monitor = _leitor()
    except Exception:
        return []
    if getattr(monitor, "crm_egemap", None) is None or valor <= 0:
        return []

    paginas = _paginas(pdf_path)
    resumo = resumo_do_pedido(pdf_path, paginas)
    if resumo:
        soma = dict(resumo["materiais"])
        cheio = sum(soma.values())
        if resumo["desconto"] > 0:
            log(f"[{cliente}] Pedido: o resumo do pedido ja separa por material "
                f"— apliquei o desconto de {_reais(resumo['desconto'])} na mesma "
                f"proporcao.")
        return _fatiar(monitor, soma, cheio, valor, log, cliente)

    totais = totais_do_pedido(pdf_path, paginas)
    try:
        itens = monitor.itens_do_orcamento(pdf_path)
    except Exception:
        itens = []

    soma, por_eliminacao = {}, []
    for item in itens:
        material, como = monitor.material_do_item(item)
        if material is None:
            log(f"[{cliente}] Pedido: nao sei de que material e o item "
                f"{item['tipo'] or '?'} ({item['linha']}) — composicao pendente.")
            return []
        if como == "padrao":
            por_eliminacao.append(f"{item['tipo'] or '?'} ({item['linha']})")
        soma[material] = soma.get(material, 0.0) + item["valor"]

    # A divisao e montada com os valores CHEIOS (antes do desconto), que e o
    # que as esquadrias somam, e depois encolhida de uma vez pro valor
    # fechado. Assim o desconto cai em cada material na mesma proporcao.
    cheio_alm = sum(soma.values())
    if cheio_alm > 0:
        impresso = totais.get("alm_bruto") or totais.get("alm") or 0.0
        if impresso > 0 and abs(cheio_alm - impresso) > 0.02 and impresso >= cheio_alm:
            log(f"[{cliente}] Pedido: as esquadrias somam {_reais(cheio_alm)} e o "
                f"total impresso e {_reais(impresso)} — composicao pendente.")
            return []

    pvc = totais.get("pvc_bruto") or totais.get("pvc") or 0.0
    if pvc > 0:
        soma["pvc"] = soma.get("pvc", 0.0) + pvc

    if por_eliminacao:
        log(f"[{cliente}] Pedido: contei como aluminio, pela cor do perfil: "
            + ", ".join(por_eliminacao))

    return _fatiar(monitor, soma, sum(soma.values()), valor, log, cliente)


def _fatiar(monitor, soma, cheio, valor, log, cliente):
    """Ajusta a divisao pra somar exatamente o valor do pedido."""
    if cheio <= 0:
        return []

    if abs(cheio - valor) > 0.02:
        if abs(cheio - valor) > cheio * 0.5:
            log(f"[{cliente}] Pedido: os materiais somam {_reais(cheio)} e o "
                f"pedido e de {_reais(valor)} — diferenca grande demais, "
                f"composicao pendente.")
            return []
        log(f"[{cliente}] Pedido: os materiais somam {_reais(cheio)} e o pedido "
            f"fechou em {_reais(valor)} — dividi a diferenca entre eles na "
            f"mesma proporcao.")

    fator = valor / cheio
    fatias = _repartir({m: v * fator for m, v in soma.items()}, valor)

    crm = monitor.crm_egemap
    desconhecidos = [m for m in fatias if m not in crm.MATERIAL_NA_COMPOSICAO]
    if desconhecidos:
        log(f"[{cliente}] Pedido: nao conheco o material {desconhecidos} — "
            f"composicao pendente.")
        return []
    return [(crm.MATERIAL_NA_COMPOSICAO[m], fatias[m])
            for m in crm.ORDEM_DA_COMPOSICAO if fatias.get(m)]

# ── Envio para o CRM ──────────────────────────────────────────────────────────

def _reais(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def esperar_arquivo(pdf_path, tentativas=8, espera=3):
    """Espera o arquivo liberar antes de ler.

    A pasta fica no OneDrive, que segura o arquivo enquanto sincroniza. Isso
    roda em segundo plano, entao esperar aqui nao atrapalha o monitor.
    """
    for tentativa in range(tentativas):
        try:
            with open(pdf_path, "rb") as arquivo:
                arquivo.read(1)
            return True
        except OSError:
            if tentativa < tentativas - 1:
                time.sleep(espera)
    return False


def enviar(pdf_path, log=print, arquivo_antigo=None):
    """Manda um PDF de pedido para o card do cliente no CRM.

    Nunca levanta excecao: o que der errado vira uma linha no log.
    """
    arquivo = Path(pdf_path).name

    if not e_pedido(pdf_path):
        log(f"[pedido] {arquivo}: nao comeca com \"Pedido\" — deixei quieto. "
            f"So os arquivos \"Pedido - Nome do Cliente.pdf\" vao pro CRM.")
        return False

    cliente = nome_do_cliente(pdf_path)

    if not esperar_arquivo(pdf_path):
        log(f"[pedido] {arquivo}: o arquivo esta em uso (OneDrive sincronizando?) — "
            f"nao consegui ler. Salve ele de novo daqui a pouco.")
        return False

    if not cliente:
        log(f"[pedido] {arquivo}: nao consegui ler o nome do cliente no nome do "
            f"arquivo — nao enviei nada.")
        return False

    valor, de_onde = valor_do_pedido(pdf_path)
    if valor > 0:
        log(f"[{cliente}] Pedido: {arquivo} — {_reais(valor)} ({de_onde}).")
    else:
        log(f"[{cliente}] Pedido: nao achei o valor em {arquivo} — vou anexar o PDF "
            f"assim mesmo. Pra ir com valor, escreva ele no nome do arquivo "
            f"(ex.: '... R$ 12.345,67').")

    composicao = composicao_do_pedido(pdf_path, valor, log=log, cliente=cliente)
    if composicao:
        log(f"[{cliente}] Pedido: "
            + ", ".join(f"{m} {_reais(v)}" for m, v in composicao) + ".")

    return crm_egemap.lancar_pedido(pdf_path, cliente, valor, log=log,
                                    arquivo_antigo=arquivo_antigo,
                                    composicao=composicao)


# ── Uso pela linha de comando (so mostra, nao escreve nada) ───────────────────

def testar(alvo=None):
    """Mostra o que aconteceria com um PDF -- ou com a pasta inteira.

    Nao escreve nada no CRM: serve pra conferir se os nomes dos arquivos estao
    casando com os contratos antes de deixar rodando sozinho.
    """
    if not alvo:
        print("Use: python pedidos.py testar \"caminho do PDF ou da pasta de pedidos\"")
        return 1

    caminho = Path(alvo.strip().strip('"').strip("'"))
    if caminho.is_dir():
        pdfs = sorted(caminho.glob("*.pdf"))
    elif caminho.exists():
        pdfs = [caminho]
    else:
        print(f"Nao encontrei: {caminho}")
        return 1

    if not pdfs:
        print(f"Nenhum PDF em {caminho}")
        return 1

    crm = None
    contratos = None
    if not crm_egemap.configurado():
        print("CRM ainda nao conectado — mostrando so a leitura do nome e do valor.\n")
    else:
        try:
            crm = crm_egemap.CRM().entrar()
            contratos = crm.negocios_que_valem()
        except crm_egemap.CRMErro as e:
            print(f"Nao consegui falar com o CRM ({e}) — mostrando so a leitura.\n")

    print(f"{len(pdfs)} arquivo(s):\n")
    iriam = 0
    for pdf in pdfs:
        if not e_pedido(pdf):
            print(f"  {pdf.name}")
            print(f"    nao e pedido : nao comeca com \"Pedido\" — fica de fora\n")
            continue
        cliente = nome_do_cliente(pdf)
        valor, de_onde = valor_do_pedido(pdf)
        print(f"  {pdf.name}")
        print(f"    cliente lido : {cliente or '(nao consegui ler)'}")
        print(f"    valor        : {_reais(valor)}" + (f"  ({de_onde})" if de_onde else "  (nao achei)"))
        totais = totais_do_pedido(pdf)
        if totais:
            print(f"    totais lidos : "
                  + ", ".join(f"{k}={_reais(v)}" for k, v in sorted(totais.items())))
        composicao = composicao_do_pedido(pdf, valor, log=lambda m: None)
        if composicao:
            print(f"    por material : "
                  + ", ".join(f"{m} {_reais(v)}" for m, v in composicao))
        elif valor > 0:
            print(f"    por material : (nao deu pra separar — ficaria pendente no card)")

        if contratos is not None and cliente:
            try:
                achado = crm.encontrar_contrato(cliente, contratos)
                print(f"    iria para    : '{achado['title']}'  ({crm_egemap.ETAPA_PEDIDO})")
                iriam += 1
            except crm_egemap.ClienteNaoEncontrado as e:
                print(f"    NAO iria     : {e}")
        print()

    if contratos is not None:
        print(f"{iriam} de {len(pdfs)} arquivo(s) iriam para um contrato.\n")
    return 0


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "testar"
    if comando == "testar":
        sys.exit(testar(sys.argv[2] if len(sys.argv) > 2 else None))
    print(__doc__)
    print("Comando:  python pedidos.py testar \"caminho do PDF ou da pasta\"")
    sys.exit(1)
