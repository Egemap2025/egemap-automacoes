#!/usr/bin/env python3
"""
EGEMAP - Pedidos

O passo depois da proposta. Quando o contrato fecha, o pedido de fabrica e
salvo em PDF numa pasta so dele (ex.: "Pedidos 2026"). Este modulo pega esse
PDF e poe no card do cliente no CRM, na mesma lista em que a proposta ja esta:

  1. Le o nome do cliente no NOME DO ARQUIVO
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
}

# "12.345,67", "1234,56", "R$ 12.345,67" -- exige os centavos com virgula pra
# nao confundir numero de pedido ou data com dinheiro.
VALOR_ESCRITO = re.compile(r"R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})")


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c))


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

# Do mais especifico para o mais generico: o primeiro que casar manda.
ROTULOS_DE_VALOR = (
    (r"TOTAL\s+GERAL\s*\(\s*R\$\s*\)\s*:?\s*R?\$?\s*([\d.,]+)", "TOTAL GERAL"),
    (r"(?:VALOR|TOTAL)\s+D[OA]\s+PEDIDO\s*:?\s*R?\$?\s*([\d.,]+)", "VALOR DO PEDIDO"),
    (r"VALOR\s+D[OA]\s+CONTRATO\s*:?\s*R?\$?\s*([\d.,]+)", "VALOR DO CONTRATO"),
    (r"VALOR\s+TOTAL\s*:?\s*R?\$?\s*([\d.,]+)", "VALOR TOTAL"),
    (r"TOTAL\s+GERAL\s*:?\s*R?\$?\s*([\d.,]+)", "TOTAL GERAL"),
    (r"TOTAL\s*:\s*R?\$?\s*([\d.,]+)", "TOTAL"),
)

DINHEIRO_NO_TEXTO = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")


def para_numero(texto):
    """"12.345,67" -> 12345.67. Zero quando nao da pra ler."""
    bruto = (texto or "").replace("R$", "").replace("\xa0", "").strip().strip(".,-")
    bruto = bruto.replace(" ", "")
    if not bruto or not any(c.isdigit() for c in bruto):
        return 0.0
    if "," in bruto:                                    # 12.345,67 ou 1234,56
        bruto = bruto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", bruto):   # 12.345 e milhar
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


def valor_do_pedido(pdf_path):
    """Valor do pedido. Retorna (valor, de onde saiu).

    Procura em tres lugares, nesta ordem:

      1. no nome do arquivo -- se voce escreveu o valor ali, e ele que vale,
         porque foi escolha sua;
      2. num rotulo dentro do PDF ("VALOR TOTAL:", "TOTAL GERAL (R$)"...);
      3. no maior valor em reais do documento, que num pedido e o total.
    """
    no_nome = VALOR_ESCRITO.search(Path(pdf_path).stem)
    if no_nome:
        valor = para_numero(no_nome.group(1))
        if valor > 0:
            return valor, "escrito no nome do arquivo"

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

    return crm_egemap.lancar_pedido(pdf_path, cliente, valor, log=log,
                                    arquivo_antigo=arquivo_antigo)


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
        cliente = nome_do_cliente(pdf)
        valor, de_onde = valor_do_pedido(pdf)
        print(f"  {pdf.name}")
        print(f"    cliente lido : {cliente or '(nao consegui ler)'}")
        print(f"    valor        : {_reais(valor)}" + (f"  ({de_onde})" if de_onde else "  (nao achei)"))

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
