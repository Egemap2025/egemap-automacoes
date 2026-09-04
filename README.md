# Egemap Automações

> **Trabalhando nisso com o Claude?** Comece pedindo *"leia o CONTEXTO.md"* —
> lá está o porquê de cada regra, as armadilhas já descobertas e o que está
> pausado. Este README conta o **que** o programa faz; o `CONTEXTO.md` conta
> **por quê**.

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
                       ↓
        Sobe sozinho para o Google Drive (mesma pasta do cliente)
```

Depois, quando o contrato fecha:

```
     Salva o PDF do pedido na pasta dos pedidos (com o nome do cliente)
                       ↓
   Entra no card daquele cliente, em "Contrato", como a linha "Pedido"
                       ↓
        Junto da proposta que ja estava la — nada e removido
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
nome, ele saiu do W-Vetro para ser juntado com o PVC num `COMPLETO`. Peça **não
vai pro CRM nem pro Drive** — ela não é a proposta do cliente, e só ficava
anexada no card sem servir pra nada. Quem vai é a proposta final, quando o
`COMPLETO` ficar pronto. Já `ALM`, `MAD` ou `PVC` sozinho é obra só daquele
material: proposta final, vai pro CRM e pro Drive, e o card anda.

**O mês da Capa se atualiza sozinho.** A Capa traz num canto algo como
`EGEMAP · PROPOSTA COMERCIAL · AGOSTO 2026`. Esse texto envelhece sozinho, e é
fácil esquecer de trocar. O monitor põe o mês de hoje ali na hora de montar —
você não precisa mexer na Capa quando virar o mês. Funciona escrito de
qualquer jeito (`AGOSTO 2026`, `Agosto de 2026`, `agosto/2026`), e o ano vira
junto.

**Os códigos só valem como palavra inteira, e só depois da data.** `PVC`, `ALM`
e `MAD` são lidos como palavras separadas no fim do nome — o nome do cliente
fica de fora. Antes não era assim, e um cliente chamado **Almeida** (tem "ALM"
dentro) ou **Madalena** (tem "MAD") tinha toda proposta lida como
madeira + alumínio: virava peça, o card nunca andava e nada subia pro Drive.

**O `COMPLETO` só junta arquivo do mesmo dia.** A pasta do cliente guarda as
propostas dos dias anteriores, e elas ficam lá — mas não entram mais na
montagem. Se sobrou mais de um do mesmo dia (você refez o orçamento), vale o
mais novo. O monitor escreve no log qual arquivo usou como PVC e qual usou como
alumínio, e qual deixou de fora por ser de outro dia — dá pra conferir na
janela preta sem abrir a pasta.

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
| Atualiza o **valor do negócio** | Em qualquer etapa. Sem pedido, vale o maior dos orçamentos; com pedido de fábrica no card, vale o pedido — foi nele que fechou |
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
- o arquivo é uma peça `MAD ALM`, esperando o `COMPLETO`
- o cliente já passou de *Orçamentos a Fazer* (é alteração, não primeiro orçamento)
- nenhum cliente parecido no CRM
- o nome da pasta ficou parecido com dois cards ao mesmo tempo
- o PDF não tem Capa e Página Final (orçamento cru)
- não deu para ler o valor na Página Final
- internet fora ou CRM inacessível

Nesses casos é só lançar na mão, como antes.

## Pedido automático no CRM (etapa Contrato)

É o passo final, depois que o contrato fecha. Você salva o PDF do pedido numa
pasta só dele (ex.: `Pedidos 2026`), edita como precisar e salva de novo com o
mesmo nome. O monitor faz o resto:

1. Lê o **nome do cliente no nome do arquivo**
2. Lê o **valor do pedido** (do nome do arquivo, ou de dentro do PDF)
3. Acha o cliente no CRM — **só entre os que estão em `Contrato`**
4. Anexa o PDF como a linha **`Pedido`**, ao lado do que já está lá

**Nada é removido.** A proposta anexada quando o orçamento saiu continua no
lugar dela; o pedido entra junto, como mais uma linha. A única linha que o
pedido substitui é a **dele mesmo** — quando você salva o mesmo arquivo de
novo depois de editar, ou quando só renomeia. Editar quantas vezes precisar
não duplica nada.

**Só pedidos novos.** Os PDFs que já estavam na pasta quando o monitor abriu
ficam como estão — o monitor só age no que chegar depois. (Isso também evita
que uma sincronização do OneDrive despeje a pasta inteira no CRM de uma vez.)
Se precisar mandar um antigo, renomeie o arquivo: ele passa a valer como novo.

**Um contrato pode receber vários pedidos.** O segundo vira `Pedido 2`, o
terceiro `Pedido 3` — nenhum toma o lugar do outro.

**O valor do negócio não é tocado.** Em `Contrato` o número já é do vendedor
(pode ter negociado desconto). O pedido só acrescenta a linha dele.

### O nome do arquivo

O padrão da pasta é **`Pedido - Nome do Cliente.pdf`**, e é dele que sai o
cliente. Tudo que é número (número do pedido, data, valor) e as palavras do dia
a dia (`Pedido`, `PVC`, `adição`...) são ignoradas — o que sobra é o nome:

```
Pedido - Adriano Antonio Stuart.pdf       -> card "Adriano Stuart"
Pedido - Alexandre Fernandes Pereira.pdf  -> card "Alexandre Pereira"
Pedido - Altrix LTDA.pdf                  -> card "Altris Ltda"
```

**Só entra arquivo que começa com `Pedido`.** A pasta guarda outros PDFs
(material comercial, por exemplo) e eles ficam de fora — sem essa regra, o nome
de um deles seria lido como se fosse um cliente. O log avisa quando pula um.

**Mais de um pedido pro mesmo cliente** (uma adição, por exemplo): é só salvar
o segundo PDF com um nome um pouco diferente (`Pedido - Fulano de Tal 2.pdf`,
`... adição.pdf`) — o Windows já obriga isso. Ele cai no mesmo cliente e vira a
linha `Pedido 2`, sem encostar no primeiro.

O valor é procurado em três lugares, nesta ordem: **escrito no nome do
arquivo** (`... R$ 98.052,29.pdf`), num rótulo dentro do PDF (`VALOR TOTAL:`,
`TOTAL GERAL (R$)`, `VALOR DO PEDIDO:`...), ou no maior valor em reais do
documento. Se não achar nenhum, o PDF é anexado assim mesmo e o log avisa —
escrever o valor no nome do arquivo resolve.

**Quando o pedido NÃO é lançado** (e o log diz o porquê):
- o arquivo não começa com `Pedido` (não é um pedido)
- o cliente não está em `Contrato` — o log mostra em que etapa ele está
- nenhum cliente parecido no CRM
- o nome ficou parecido com dois cards ao mesmo tempo
- não deu para ler o nome do cliente no nome do arquivo

### Escolher a pasta dos pedidos

O monitor pergunta na abertura, do mesmo jeito que pergunta do CRM e do Drive:
digite `1` e ENTER e cole o caminho da pasta. Se ninguém responder em 20
segundos ele segue normalmente. Depois de configurada, a pergunta some.

Para escolher (ou trocar) sem esperar a pergunta, use o
`CONFIGURAR_PEDIDOS.bat` — ou:

```bash
python monitorar.py --pedidos
```

Para conferir, sem escrever nada no CRM:

```bash
python pedidos.py testar "C:\Users\T-GAMER\OneDrive\Desktop\Pedidos 2026"
python pedidos.py testar "C:\...\Pedidos 2026\PEDIDO 1234 Fulano.pdf"
python crm.py contratos                    # lista quem está em "Contrato"
python crm.py contratos "Ivan Candiotto"   # mostra para onde o pedido iria
```

## Envio automático para o Google Drive

Assim que a proposta fica pronta, o monitor sobe o PDF sozinho para o Google
Drive, na mesma estrutura de pastas que você já usa no computador (cidade,
cliente, etc. — o que tiver dentro da pasta raiz de orçamentos vira a mesma
pasta lá no Drive).

- Vai só a proposta pronta (com Capa e Página Final) — orçamento cru fica de
  fora, mesma regra do CRM.
- Uma peça isolada esperando o `COMPLETO` (arquivo `MAD ALM`) não sobe
  sozinha — sobe é a proposta final, quando ela ficar pronta.
- Proposta refeita no mesmo dia substitui a anterior no Drive, e **só a
  mesma**: uma proposta de PVC substitui a de PVC, uma de alumínio substitui a
  de alumínio. `ALM` e `MAD` são obras diferentes e **convivem** na pasta.
  Proposta que você renomeou (`BRANCO`, `CINZA`) nunca é apagada — as duas
  ficam, igual às duas linhas no CRM.
- **Usa a pasta que já existe.** Antes de gravar, o monitor procura a pasta
  no Drive ignorando maiúscula e acento, então `Passo de Torres` continua
  sendo `Passo de Torres` — ele não cria mais uma `Passo De Torres` ao lado.
  Só cria pasta quando ela realmente não existe.
- A estrutura no Drive é **Ano / Cidade / Cliente** (sem o nível do estado,
  diferente do computador). Proposta salva direto na pasta da cidade, sem
  pasta de cliente, vai para a própria cidade.

**Se você já usava o agente separado do Drive:** pode continuar — ele fica
conectado sozinho, sem pedir login de novo (usa a mesma pasta de configuração
de antes). O monitor também desliga a tarefa agendada do agente antigo na
primeira vez que abre, para não subir cada proposta duas vezes.

### Conectar ao Drive

Se ainda não tiver conectado, o monitor pergunta na abertura, do mesmo jeito
que pergunta do CRM: digite `1` e ENTER, e vai abrir o navegador para você
fazer login no Google e clicar em "Permitir" — só precisa uma vez. Se
ninguém responder em 20 segundos, ele segue monitorando normalmente.

Para conectar (ou reconectar) sem esperar a pergunta na abertura:

```bash
python drive.py            # abre o navegador para conectar/reconectar
python drive.py testar     # mostra se ja esta conectado
```

### Arrumar as pastas do Drive (uma vez só)

Enquanto o monitor criava pasta nova por causa de maiúscula, o Drive ficou com
pastas repetidas: uma `Passo De Torres` ao lado da `Passo de Torres` que você
usa, por exemplo. O monitor já não faz mais isso.

Para arrumar o que ficou para trás, **é só abrir o `EGEMAP-Monitor.exe`**: na
primeira vez ele pergunta se você quer arrumar, do mesmo jeito que pergunta do
CRM e do Drive. Digite `1` e ENTER. A pergunta some depois de feita, e se
ninguém responder em 20 segundos ele segue monitorando normalmente.

(Se preferir rodar fora da abertura, o `LIMPAR_DRIVE.bat` faz a mesma coisa, ou
`EGEMAP-Monitor.exe --limpar-drive` no Prompt de Comando.)

Ele junta as repetidas numa só, leva os clientes que estavam na pasta errada
para a certa, e tira as cópias iguais. Antes de mexer em qualquer coisa ele
**mostra a lista inteira do que vai fazer** e espera você digitar `1` e ENTER.
Se você só apertar ENTER, ele sai sem tocar em nada.

O que for apagado vai para a **Lixeira do Drive** e dá para recuperar por 30
dias. Arquivo que ele não souber de quem é fica onde está, com um aviso.

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
   - Se quer conectar o Google Drive (digite `1` e ENTER)
   - Caminho da pasta dos pedidos (digite `1` e ENTER, ou pule)
3. A partir daí ele salva tudo e abre sozinho com o Windows.

## Desenvolvimento local

```bash
pip install -r requirements.txt
python monitorar.py
```

## Estrutura do projeto

```
CONTEXTO.md               # Passagem de bastão: decisões, armadilhas, o que está pausado
monitorar.py              # Monitor principal (watchdog + PyMuPDF)
crm.py                    # Lançamento automático no CRM (só biblioteca padrão)
drive.py                  # Envio automático para o Google Drive (só biblioteca padrão)
pedidos.py                # PDF de pedido -> card do cliente em "Contrato"
limpar_drive.py           # Faxina nas pastas repetidas do Drive (LIMPAR_DRIVE.bat)
montar_orcamento.py       # Utilitário de montagem/testes
.github/workflows/build-exe.yml  # Build automático do .exe (PyInstaller)
```
