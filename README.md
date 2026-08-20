# Egemap Automações

Monitor de Propostas Comerciais — roda em segundo plano no Windows observando a pasta de orçamentos e monta a proposta comercial final automaticamente.

## Fluxo

```
Salva PVC (Sintegra) e/ou ALM/MAD (W-Vetro) na pasta do cliente
                       ↓
          Cada um ganha Capa + Contra Capa (wrap individual)
                       ↓
        Salva um PDF com "COMPLETO" no nome para disparar
                       ↓
   Junta Capa + PVC + ALM/MAD + Resumo Geral (totais) + Contra Capa
                       ↓
        Proposta Comercial [cliente] [DD-MM].pdf pronta
                       ↓
   Lança sozinho no CRM: valor + PDF anexado + card em "Orçamento Pronto"
```

## Lançamento automático no CRM

Assim que a proposta fica pronta, o monitor faz no [CRM EGEMAP](https://crm.egemapesquadrias.com.br)
exatamente o que era feito na mão:

1. Acha o cliente na coluna **Orçamentos a Fazer** (pelo nome da pasta)
2. Lança o orçamento com o valor e anexa o PDF da proposta
3. Atualiza o valor do negócio (soma dos orçamentos)
4. Marca o orçamento como feito
5. Move o card para **Orçamento Pronto**

**Quando o card NÃO é movido:** se o negócio pede mais de um orçamento (ex.: PVC
e Alumínio) e só um ficou pronto, o valor e o PDF são lançados, o orçamento sai
como feito, mas o card fica em *Orçamentos a Fazer* até o último sair. O monitor
avisa no log o que ainda falta.

**Proposta refeita:** a proposta nova substitui a linha que ela já contém, em vez
de somar em cima. O `COMPLETO` (PVC + Alumínio) toma o lugar dos dois PDFs
individuais, e um orçamento refeito depois substitui o anterior — assim o valor do
negócio nunca dobra. PVC e Alumínio pedidos separados continuam sendo duas linhas.

**Quando o monitor não mexe no CRM** (e avisa no log, sem travar nada):
- nenhum cliente parecido em *Orçamentos a Fazer*
- o nome da pasta ficou parecido com dois cards ao mesmo tempo
- não deu para ler o valor do PDF
- internet fora ou CRM inacessível

Nesses casos é só lançar na mão, como antes.

### Conectar ao CRM

Na primeira execução o monitor pergunta se quer conectar. Para conectar depois,
abra o **`CONECTAR_CRM.bat`** (ou rode `python crm.py configurar`) e informe o
mesmo email e senha que você usa no CRM — o monitor age com a sua permissão. A
senha fica guardada só nesta máquina, protegida pelo Windows (DPAPI).

Para conferir sem escrever nada no CRM:

```bash
python crm.py testar                  # lista os negócios em "Orçamentos a Fazer"
python crm.py testar "Lara Castilho"  # mostra com qual card esse nome casaria
```

## Uso

1. Baixe o `EGEMAP-Monitor.exe` (gerado automaticamente pelo GitHub Actions a cada push, veja a aba Actions do repositório).
2. Abra o `.exe`. Na primeira execução ele pede:
   - Caminho do PDF de Capa (3 páginas: Capa / Resumo / Contra Capa)
   - Caminho da pasta raiz de orçamentos
3. A partir daí ele salva a configuração e abre sozinho com o Windows.

## Desenvolvimento local

```bash
pip install -r requirements.txt
python monitorar.py
```

## Estrutura do projeto

```
monitorar.py              # Monitor principal (watchdog + PyMuPDF)
crm.py                    # Lançamento automático no CRM (só biblioteca padrão)
montar_orcamento.py       # Utilitário de montagem/testes
.github/workflows/build-exe.yml  # Build automático do .exe (PyInstaller)
```
