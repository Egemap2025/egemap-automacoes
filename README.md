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

1. Acha o cliente pelo nome da pasta e confere se ele está na coluna **Orçamentos a Fazer**
2. Lança o orçamento com o valor e anexa o PDF da proposta
3. Atualiza o valor do negócio (a **maior** das opções)
4. Marca o orçamento como feito
5. Move o card para **Orçamento Pronto**

**O nome do arquivo vira o nome da linha no CRM.** `Proposta Comercial Fulano
24-08 BRANCO.pdf` vira a linha **Branco**. Então o fluxo é:

1. O monitor monta a proposta com Capa e Página Final
2. Você renomeia o arquivo pronto como quiser (`BRANCO`, `CINZA`, ...)
3. Esse nome vira o nome da linha, e o card recebe o PDF

Duas opções do mesmo material (BRANCO e CINZA) viram **duas linhas** e
convivem. Renomear de novo **renomeia a linha**, não cria outra. Refazer a
proposta troca o PDF da mesma linha.

**`MAD ALM` é peça, não proposta.** Quando o arquivo tem os dois materiais no
nome, ele saiu do W-Vetro para ser juntado com o PVC num `COMPLETO` — o PDF vai
pro CRM, mas o card **não anda**, porque o orçamento ainda não acabou. Já `ALM`,
`MAD` ou `PVC` sozinho é obra só daquele material: proposta final, card anda.

**Só proposta completa vai para o CRM.** Antes de enviar, o monitor confere se
o PDF tem mesmo Capa e Página Final comparando com a Capa configurada —
orçamento cru do Sintegra ou do W-Vetro é barrado e fica registrado no log.

**O valor do negócio é o maior das opções, não a soma.** Quando o cliente
recebe duas opções ele fecha uma só; somar inflaria a previsão de vendas.

**Freios nas etapas mais adiantadas.** Trocar o PDF é sempre seguro; mexer no
resto nem sempre:

| O que o monitor faz | Onde acontece |
|---|---|
| Troca o PDF e o valor da linha do orçamento | Em qualquer etapa |
| Atualiza o **valor do negócio** (o maior das opções) | Até *Orçamento Pronto*. De *Orçamento Apresentado* em diante o número é do vendedor (pode ter negociado desconto) e não é tocado |
| Marca o orçamento como **feito** | Só nas filas de trabalho: *Orçamentos a Fazer* e *Atualizações* |
| **Move o card** para *Orçamento Pronto* | Saindo das filas: *Orçamentos a Fazer* e *Atualizações* |

Card já adiantado no funil (*Orçamento Apresentado* em diante) só recebe o PDF
novo — nunca volta pra trás.

**Um orçamento cadastrado = uma proposta.** Quando o negócio tem um só
orçamento em *Detalhes do orçamento*, a proposta que chegar fecha ele e o card
anda — não importa se o arquivo se chama `ALM`, `PVC` ou `MAD`, porque esse
sufixo não corresponde aos materiais do CRM (o orçamento da Leticia pede
Madeira + PVC e saiu num arquivo `ALM`).

**Quando o card NÃO é movido:** se o negócio tem *duas ou mais* opções
cadastradas (ex.: uma em PVC e outra em Alumínio) e só uma ficou pronta, o valor
e o PDF são lançados, aquela opção sai como feita, mas o card espera a última.
O monitor avisa no log o que ainda falta.

**Proposta refeita:** a proposta nova substitui a linha que ela já contém, em vez
de somar em cima. O `COMPLETO` (PVC + Alumínio) toma o lugar dos dois PDFs
individuais, e um orçamento refeito depois substitui o anterior — assim o valor do
negócio nunca dobra. PVC e Alumínio pedidos separados continuam sendo duas linhas.

**Quando o monitor não mexe no CRM** (e avisa no log, sem travar nada):
- o cliente já passou de *Orçamentos a Fazer* (é alteração, não primeiro orçamento)
- nenhum cliente parecido no CRM
- o nome da pasta ficou parecido com dois cards ao mesmo tempo
- o PDF não tem Capa e Página Final (orçamento cru)
- não deu para ler o valor na Página Final
- internet fora ou CRM inacessível

Nesses casos é só lançar na mão, como antes.

### Conectar ao CRM

Abra o `EGEMAP-Monitor.exe`. Enquanto o CRM não estiver conectado, ele pergunta
na abertura: **digite `1` e ENTER**, e informe o mesmo email e senha que você usa
no CRM — o monitor age com a sua permissão. Se ninguém responder em 20 segundos
ele segue monitorando normalmente, então nunca trava quando abre junto com o
Windows. Depois de conectado a pergunta some.

A senha fica guardada só nesta máquina, protegida pelo Windows (DPAPI).

Para conferir sem escrever nada no CRM:

```bash
python crm.py testar                  # lista os negócios em "Orçamentos a Fazer"
python crm.py testar "Lara Castilho"  # mostra com qual card esse nome casaria
```

## Uso

1. Baixe o **[EGEMAP-Monitor.exe](https://github.com/Egemap2025/egemap-automacoes/releases/latest/download/EGEMAP-Monitor.exe)** — link fixo, sempre a versão mais nova.
2. Abra o `.exe`. Na primeira execução ele pede:
   - Caminho do PDF de Capa (3 páginas: Capa / Resumo / Contra Capa)
   - Caminho da pasta raiz de orçamentos
   - Se quer conectar o CRM (digite `1` e ENTER)
3. A partir daí ele salva tudo e abre sozinho com o Windows.

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
