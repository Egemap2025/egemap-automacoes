# Contexto do projeto

Documento de passagem de bastão. Numa conversa nova com o Claude, diga
**"leia o CONTEXTO.md"** e ele se situa por completo, sem precisar recontar
nada.

O `README.md` conta **o que** o programa faz. Este arquivo conta **por quê** —
as decisões, o que já foi tentado e não funcionou, e as armadilhas que só
apareceram usando de verdade. É o que se perde quando uma conversa acaba.

---

## O problema que isso resolve

A EGEMAP faz esquadrias (PVC, alumínio, madeira). O Natanael monta os
orçamentos. Antes, para cada orçamento ele fazia na mão:

1. Pegava o PDF cru do **Sintegra** (PVC) e/ou do **W-Vetro** (alumínio/madeira)
2. Juntava com a Capa e a Contra Capa da empresa
3. Ia no CRM, digitava o valor, anexava o PDF e arrastava o card de coluna
4. Subia a proposta no Google Drive

Hoje ele só salva o orçamento cru na pasta do cliente. O resto acontece
sozinho.

---

## O dia a dia (importante entender isso antes de mexer)

A pasta raiz fica no **OneDrive**:
`C:\Users\T-GAMER\OneDrive\Desktop\ORÇAMENTOS\<ano>\<UF>\<cidade>\<cliente>\`

**A pasta do cliente tem o mesmo nome do card no CRM** — ele copia e cola. É
assim que o monitor liga um ao outro.

Fluxo típico:

1. Salva o orçamento cru na pasta do cliente
2. O monitor monta `Proposta Comercial <cliente> <DD-MM> <sufixo>.pdf`
3. **Às vezes ele renomeia** esse arquivo pronto para o nome final. Nem sempre —
   boa parte já sai com o nome certo
4. A proposta vai para o CRM e para o Drive

Depois que o contrato fecha vem o **pedido**, que é outro fluxo e outra pasta:

`C:\Users\T-GAMER\OneDrive\Desktop\Pedidos 2026\` — plana, sem subpastas,
um PDF por pedido, todos no formato **`Pedido - Nome do Cliente.pdf`** (foi ele
quem confirmou: *"os pdf dos pedido são todos nesse formato"*). Ele salva o PDF
ali, **edita com as informações necessárias e salva de novo com o mesmo nome**.
Aí o pedido vai para o card do cliente no CRM, na etapa `Contrato`, como mais
uma linha ao lado da proposta.

**Um cliente pode ter mais de um pedido** — *"às vezes o cliente vai ter mais de
um pdf de pedido por ser uma adição"*. O segundo arquivo vira a linha `Pedido
2`, sem encostar no primeiro.

### O que cada sufixo significa (regra do negócio, não invenção)

| Sufixo | Significado |
|---|---|
| `PVC` | Obra só de PVC → **proposta final** |
| `ALM` | Obra só de alumínio → **proposta final** |
| `MAD` | Obra só de madeira → **proposta final** |
| `MAD ALM` | **Peça** que ainda vai ser juntada com o PVC num `COMPLETO` |
| sem sufixo | Saiu do `COMPLETO` → proposta final |
| renomeado (`BRANCO`, `CINZA`) | Proposta final, nome escolhido por ele |

**Dois materiais no nome = peça, não entrega.** É o único sinal confiável, e
veio direto do Natanael: *"quando dá MAD ALM é para juntar com outro"*.

---

## Arquitetura

```
monitorar.py    Programa principal. Vigia as pastas, monta a proposta com
                Capa/Página Final, e chama crm.py, drive.py e pedidos.py.
crm.py          Lança no CRM. Só biblioteca padrão.
drive.py        Sobe pro Google Drive (via rclone). Só biblioteca padrão.
pedidos.py      Lê o nome do cliente e o valor no PDF do pedido e manda pro
                CRM (etapa Contrato). Usa o PyMuPDF que já está lá.
limpar_drive.py Faxina as pastas repetidas do Drive. O monitor oferece na
                abertura (uma vez so); tambem roda por
                `EGEMAP-Monitor.exe --limpar-drive` ou LIMPAR_DRIVE.bat.
montar_orcamento.py   Utilitário de teste, fora do fluxo automático.
```

### A faxina tem que rodar pelo rclone, não por fora

O Drive do Natanael (`egemapesquadrias@gmail.com`) **enxerga** as pastas mas
não consegue mexer nelas: quem criou, e portanto quem é dona, é a conta do
rclone (`orcamentosegemap@gmail.com`). Tentar mover pela API com a conta dele
devolve `The caller does not have permission`. Por isso a faxina roda pelo
mesmo rclone que o monitor já usa — é a única credencial que tem o direito.

O `limpar_drive.py` mostra tudo antes e só aplica com um `1` digitado.
Nunca usa `purge`: só `rmdir` em pasta já vazia, e apagar é sempre para a
Lixeira. Duas pastas com o nome **idêntico** (o Drive permite) não dá para
tratar por caminho — quem resolve é `rclone dedupe --dedupe-mode merge`.

`crm.py`, `drive.py`, `pedidos.py` e `limpar_drive.py` são **independentes**: o
monitor os importa dentro de `try/except` e funciona sem eles. Eles não sabem
nada do monitor. Mantenha assim — foi o que permitiu acrescentar cada um sem
quebrar o que já rodava.

O `.exe` sai por GitHub Actions a cada push e é publicado numa release. O link
fixo é sempre a versão mais nova:

```
https://github.com/Egemap2025/egemap-automacoes/releases/latest/download/EGEMAP-Monitor.exe
```

---

## O CRM

É um app **próprio da EGEMAP**, feito no Lovable (React + Supabase), em
`crm.egemapesquadrias.com.br`. Projeto Lovable: `egemapcrmflow`
(`bdfb78cf-b7ce-4a79-baf5-6f03829164bd`). Dá para consultar o banco pelas
ferramentas do Lovable — foi assim que quase toda decisão aqui foi validada
contra dados reais, em vez de chute.

**Nenhuma alteração foi feita no CRM.** O monitor entra com o login do próprio
usuário (`orcamentosegemap@gmail.com`) e faz exatamente o que ele faria na
tela — as regras de permissão do banco (RLS) já liberam isso para qualquer
membro da organização. A senha fica só na máquina dele, protegida pelo DPAPI
do Windows.

### Tabelas que interessam

| Tabela | Para quê |
|---|---|
| `deals` | O card. `title`, `value`, `stage_id`, `orcamento_detalhes` |
| `deal_budgets` | As linhas de orçamento: `name`, `value`, `file_url`, `file_name` |
| `pipeline_stages` | As colunas do funil |
| storage `deal-budgets` | Os PDFs, em `{org_id}/{deal_id}/{uuid}-{arquivo}` |

`orcamento_detalhes` é um JSON com a lista de orçamentos pedidos, cada um com
`nome`, `materiais[]` e `feito`.

### As colunas do funil

`Novo Lead` → `Contato Realizado` → `Orçamento a Definir` →
**`Orçamentos a Fazer`** → **`Atualizações`** → **`Orçamento Pronto`** →
`Orçamento Apresentado` → `Em Negociação` → `Contrato`

`Contrato` é a última: é lá que o pedido entra.

As duas primeiras em negrito são **filas de trabalho**: card parado ali é
orçamento esperando ser feito. `Atualizações` é onde entra quem pediu
alteração — os cards de lá têm o orçamento remarcado como não feito e ficam
sem PDF anexado, que era exatamente a dor que originou tudo isso.

---

## Regras e por que elas são assim

Cada uma dessas custou uma rodada de conversa. Não desfaça sem entender o
caso que a motivou.

### O nome do arquivo dá nome à linha do CRM

`Proposta Comercial Maria Teresa 24-08 BRANCO.pdf` → linha **Branco**.

**Por quê:** a Maria Teresa recebeu dois orçamentos de PVC que só diferem na
cor. Batizando a linha pelo material, os dois virariam "Pvc" e o segundo
apagaria o primeiro. Como o nome vem do arquivo, as duas opções convivem — e
renomear a proposta renomeia a linha em vez de criar outra (o rename é
detectado e o nome anterior vai junto para o CRM saber qual linha atualizar).

### Sem pedido, o valor do negócio é o MAIOR orçamento, não a soma

**Por quê:** duas opções são alternativas — o cliente fecha uma. A Maria
Teresa tinha R$ 113.711 e R$ 162.717; somar daria R$ 276.428 e inflaria a
previsão de vendas. Na mão, o Natanael preenchia com a maior.

### Com pedido, o valor do negócio é o do PEDIDO

**Por quê:** o pedido de fábrica é o número que fechou. Enquanto é orçamento
o valor é estimativa; quando o pedido entra no card, ele manda, e proposta
nova não mexe mais nisso (`atualizar_valor` devolve `"pedido"` e o
`lancar_proposta` só registra no log que não mexeu).

Dois pedidos no mesmo contrato **somam** — são pedidos diferentes do mesmo
fechamento (a fábrica separou PVC e alumínio, por exemplo). Um pedido
reeditado não cria linha nova: o `enviar_pedido` acha a linha pelo nome do
arquivo, então "Pedido 2" só aparece quando é outro pedido mesmo.

### O valor é atualizado em QUALQUER etapa

Foi o contrário até 04/09/2026: o valor só era mexido até "Orçamento Pronto",
porque havia 97 negócios em *Apresentado*, *Negociação* e *Contrato* com valor
preenchido e a ideia era não apagar o desconto que o vendedor tinha negociado.

O Natanael viu no log da Ana Ivonete (`valor do negocio nao foi mexido —
'Orçamento Apresentado' e numero do vendedor`), não entendeu, e decidiu:
**"pode sempre atualizar o valor lá independente de onde estiver"**. A regra
do desconto virou a regra do pedido: o número do vendedor deixa de ser
sobrescrito quando o pedido chega, que é quando ele realmente é definitivo.

Hoje toda proposta escreve uma linha no log dizendo o que aconteceu com o
valor — não existe mais o caso silencioso.

### "MAD ALM" não vai pro CRM nem pro Drive

**Por quê:** é peça esperando o `COMPLETO`; o orçamento ainda não acabou.

A primeira versão mandava o PDF da peça pro CRM (só não movia o card), com a
ideia de que o vendedor já visse alguma coisa. Na prática atrapalhou: a peça
ficava anexada no card sem servir pra nada e depois tinha que ser limpa na
mão. Hoje peça não sai da pasta — quem vai é a proposta final, quando o
`COMPLETO` ficar pronto. O `parcial=True` do `crm.py` continua existindo, mas
o monitor não usa mais.

### Os códigos PVC/ALM/MAD só valem como palavra inteira, depois da data

**Por quê:** o nome do cliente entrava na conta. `"ALM" in nome` casa com
**Almeida**, **Palmeira**, **Salma**; `"MAD"` casa com **Madalena**,
**Amadeu**. A proposta de um cliente desses era lida como madeira + alumínio,
virava peça, o card nunca andava e nada subia pro Drive. Pior: o
`detect_pdf_type` decidia PVC/ALM **pelo nome antes de abrir o PDF**, então
numa pasta "Ricardo Almeida" até o PVC do Sintegra era classificado como
alumínio e entrava no lugar errado do `COMPLETO`.

Duas correções: o código de material só conta como palavra inteira e só no
pedaço do nome **depois da data** (`codigos_no_nome`), e o `detect_pdf_type`
passou a olhar o **conteúdo primeiro**, usando o nome só quando o conteúdo não
diz nada.

O `crm.py` já fazia essa comparação por palavra inteira desde o começo — o
`materiais_do_nome` de lá tem até o comentário sobre a "Madalena". A correção
tinha sido feita num arquivo e não no outro.

### O COMPLETO só junta arquivo do mesmo dia, e o mais novo

**Por quê:** a pasta do cliente guarda as propostas dos dias anteriores. O
`_process_completo` pegava `pdfs["pvc"][0]` e `pdfs["alm"][0]` — o primeiro
que o Windows entregasse, de qualquer dia. Reproduzido: pasta com um
`MAD ALM` de seis dias atrás (R$ 999.999) e um PVC novo de hoje; o monitor
juntou os dois calado, apagou a peça velha e gerou uma proposta de
R$ 1.099.999.

Hoje `find_pdfs_in_folder` devolve do mais novo para o mais antigo, e só entra
no `COMPLETO` o arquivo cujo dia é hoje. O dia vem da data escrita no nome
(`DD-MM`) e não da data de gravação — a data no nome não muda quando o
OneDrive mexe no arquivo pra sincronizar. Arquivo cru, que ainda não tem data
no nome, aí sim vale a gravação.

O que ficou de fora aparece no log com o motivo, e o que foi escolhido também
("usando como PVC -> ...").

**Efeito colateral conhecido:** virar o dia no meio de um orçamento (peça
salva 23h55, `COMPLETO` 00h05) deixa a peça de fora. O log avisa; é só salvar
a peça de novo. Preferiu-se isso a abrir uma janela de horas que traria de
volta o risco de juntar arquivo velho.

### O COMPLETO espera o orçamento cru da mesma pasta ser envolvido

**Por quê:** as duas filas tinham tempos diferentes (6s pra envolver, 8s pro
`COMPLETO`) contados a partir de eventos diferentes. Salvando o `COMPLETO`
logo antes do W-Vetro terminar de chegar, o `COMPLETO` disparava primeiro e
lia um arquivo ainda sendo gravado — ou envolvia depois um arquivo que já
tinha virado proposta final, deixando uma proposta solta na pasta.

Hoje o `COMPLETO` só roda quando não há nada da mesma pasta na fila de
envolver (com teto de 2 minutos, pra nunca ficar preso), e o que ele consome
sai da fila (`_descartar_single`).

### Um orçamento cadastrado = uma proposta

**Por quê:** a primeira versão exigia que a proposta cobrisse todos os
materiais listados no CRM, deduzindo o material pelo sufixo do arquivo. Não
funciona — o sufixo não corresponde:

- Leticia: arquivo `ALM`, orçamento pede **Madeira + PVC**
- Dionatan: arquivo `Pvc`, orçamento pedia **Alumínio + Madeira + PVC**

Com aquela regra o card nunca andaria. O Dionatan mostra como é na prática:
um único PDF fechou o orçamento inteiro. Quando há **duas ou mais** opções
cadastradas, aí sim o material serve para saber qual delas saiu, e o card
espera todas.

### O cliente é escolhido entre TODOS os negócios abertos

**Por quê:** procurando só na coluna "Orçamentos a Fazer", uma pasta
**"Samuel Neotti"** era lançada no card do **"Samuel"** — cliente errado,
valor errado — só porque o "Samuel" por acaso estava na fila. Agora ranqueia
todos os abertos e só age se o vencedor estiver numa fila.

A comparação ignora acento e pontuação, e exige margem sobre o segundo
colocado. Se empatar, **não adivinha**: avisa no log e não mexe em nada.
Nomes com barra (`Silvana Pires da Silva/Deivede`) não podem virar pasta no
Windows, e casam de qualquer jeito.

### Só proposta completa vai pro CRM e pro Drive

**Por quê:** pedido explícito — *"não pode ser enviado os pdf que não estão
com capa e contra capa"*. Antes de enviar, compara a primeira e a última
página com a Capa configurada. Se a Capa for desenhada em imagem e não der
para comparar texto, cai para o formato da página em vez de barrar tudo.

### O pedido só acrescenta, nunca substitui

**Por quê:** pedido explícito — *"nunca tirando o pdf que já vai estar lá, no
caso seria só para adicionar junto"*. A proposta anexada quando o orçamento
saiu continua onde está. A única linha que o pedido substitui é a **dele
mesmo**, achada pelo `file_name`: o mesmo arquivo salvo de novo depois de
editado cai na mesma linha em vez de virar um `Pedido 2`. Contrato com mais de
um pedido vira `Pedido 2`, `Pedido 3` — nenhum toma o lugar do outro.

O `enviar_orcamento` (proposta) apaga linhas; o `enviar_pedido` **não apaga
nenhuma**. São métodos separados de propósito. Não junte os dois.

### Contrato também procura entre os negócios GANHOS

**Por quê:** dos 52 cards em `Contrato`, só **7** estão `open` — os outros 45
estão `won`. O `negocios_abertos()` da proposta (`status=eq.open`) deixaria 45
contratos de fora e o pedido quase nunca acharia o cliente. Por isso o pedido
usa `negocios_que_valem()`, que é `status=in.(open,won)`.

### O pedido ranqueia fora do Contrato também, e só age dentro

**Por quê:** é o mesmo caso do "Samuel x Samuel Neotti", e ele existe de
verdade aqui: **"ivan Candiotto"** está em `Contrato` e **"Ivan Candioto casa
Noeli"** está em `Orçamento Apresentado` (também **"Maria Teresinha silveira"**
x **"Maria Teresa Silva"**). Procurando só dentro da coluna, um pedido do
segundo cairia no contrato do primeiro — outra pessoa, outro contrato.

Então ranqueia entre todos os que valem e **exige que o vencedor esteja em
`Contrato`**. Se o vencedor está em outra etapa, não mexe em nada e o log diz
onde ele está.

### Só pedido novo é lançado

**Por quê:** pedido explícito — *"só quero que comece a fazer isso nos pdf
novos, não os que já estão lá"* (a pasta já tinha 109). Ao abrir, o monitor
anota os PDFs que já estavam na pasta e os ignora enquanto estiver rodando.

Isso também protege de algo pior: o OneDrive toca nos arquivos ao sincronizar
e dispara evento sem nada ter mudado — sem essa lista, uma sincronização
despejaria a pasta inteira no CRM de uma vez. Para mandar um antigo de
propósito, é só renomear o arquivo.

### Só arquivo que começa com "Pedido" é pedido

**Por quê:** a pasta guarda outros PDFs além dos pedidos —
`EGEMAP_Solene_Material_Comercial.pdf` está lá no meio dos 113. Sem essa regra
o nome dele viraria o "cliente Solene Material", e se existisse uma Solene em
`Contrato` o material comercial cairia no card dela. Rodando os nomes reais da
pasta contra os contratos reais, esse arquivo foi o **único** caso de risco: os
`Pedido - ...` casaram todos entre 0.91 e 1.00, e quem não é de `Contrato` ficou
abaixo de 0.65.

### O nome do cliente vem do nome do arquivo, não da pasta

**Por quê:** a pasta dos pedidos é plana — todos os clientes juntos. Então o
nome sai do próprio arquivo: tira tudo que tem número (número do pedido, data,
valor) e as palavras do dia a dia (`PEDIDO`, `PVC`, `ASSINADO`...), e o que
sobra é o nome. As letras soltas também saem (o `J.` de "Ezequiel J. de
Biasi") — a comparação do CRM casa o nome sem elas, e sozinhas só atrapalham.

### O valor do pedido tem três fontes, nessa ordem

**Por quê:** o layout do PDF do pedido não é fixo (ele edita o arquivo antes de
salvar). Então: **1.** valor escrito no nome do arquivo (é escolha dele, então
manda em tudo); **2.** rótulo dentro do PDF (`VALOR TOTAL:`, `TOTAL GERAL
(R$)`...), inclusive o que foi digitado em campo de formulário, que não aparece
no texto normal da página; **3.** o maior valor em reais do documento, que num
pedido é o total. Não achando nada, **anexa o PDF assim mesmo** e avisa no log
— o PDF no card é o que mais importa; o valor dá pra escrever no nome do
arquivo depois.

---

### O Drive procura a pasta que já existe antes de criar uma nova

**Por quê:** o monitor montava o nome da pasta e mandava o rclone gravar
nela. Para o Google Drive `Passo De Torres` e `Passo de Torres` são **pastas
diferentes**, então ele criava uma nova ao lado da que o Natanael usava desde
janeiro — a proposta ia embora certinha, mas para um lugar que ninguém olha.
Achado no Drive de verdade, três pares:

| Criada pelo monitor | Já existia |
|---|---|
| `Passo De Torres` (1 cliente) | `Passo de Torres` (22 clientes) |
| `Morro Da Fumaça` | `Morro da Fumaça` |
| `Morrinhos Do Sul` | `Morrinhos do Sul` |

A culpa era do `_nome_canonico_cliente`, que punha inicial maiúscula em toda
palavra e transformava "de" em "De".

Hoje o `drive.py` percorre `Ano/Cidade/Cliente` nível por nível e, em cada
um, **reaproveita a pasta que já está lá** quando ela só difere por
maiúscula, acento ou pontuação (`_pasta_equivalente`). Quando as duas
grafias existem, fica com a que tem mais coisa dentro — a que está em uso de
verdade — e sempre com a mesma, para não alternar. O
`_nome_canonico_cliente` também deixou de subir "de/da/dos", mas isso é só
cosmético: quem garante o acerto é a busca antes de criar.

### Dois envios ao mesmo tempo criavam a pasta duas vezes

**Por quê:** cada proposta sobe numa thread própria. Duas saindo juntas
(PVC e alumínio, por exemplo) rodavam dois `rclone` em paralelo, e cada um
criava a pasta do cliente por conta — o Google Drive aceita duas pastas com
o **nome idêntico** no mesmo lugar. Foi assim que apareceram três
`Felipe Dos Santos Coelho` dentro de `Balneario Gaivota`.

Hoje o `enviar` inteiro roda sob um lock (`_ENVIO_LOCK`), e a pasta é criada
de uma vez só com `rclone mkdir` antes de copiar o arquivo.

### Proposta salva direto na pasta da cidade não vira cidade "SC"

**Por quê:** a pasta local é `ORÇAMENTOS/<ano>/<UF>/<cidade>/<cliente>`, e o
destino no Drive sai de `pasta do PDF` = cliente, `pasta de cima` = cidade.
Quando o PDF era salvo direto na pasta da cidade (sem pasta de cliente), a
"pasta de cima" virava o **estado**, e nascia uma cidade chamada `SC` no
Drive. Hoje, se a pasta de cima tem duas letras, o monitor entende que é o
UF e manda para a própria cidade (`2026/Balneario Gaivota`).

Vale lembrar: a árvore do Drive é `Ano/Cidade/Cliente` — **não tem o nível do
UF**, diferente do computador. É assim desde o agente antigo e foi
confirmado com o Natanael.

### Houve duas linhas de trabalho em paralelo — hoje são uma só

Entre 26/08 e 02/09 o projeto correu em **duas branches ao mesmo tempo**, cada
uma numa conversa diferente, e as duas mexendo em `monitorar.py` e `crm.py`:

| Branch | O que tinha de único |
|---|---|
| `egemap-proposal-monitor-dp611t` | correções do `MAD ALM`/`COMPLETO`, do Drive (pasta duplicada, UTF-8, `ALM`×`MAD`), da Capa, e a faxina |
| `automate-pdf-orders-crm-vgkgkb` | o `pedidos.py` — PDF de pedido vai pro card em *Contrato* |

Deu para notar o desperdício: **as duas acharam e corrigiram o mesmo bug do
acento** (`'ascii' codec can't encode`), separadamente, com um dia de
diferença. Uma delas fez `re.sub(..., flags=re.ASCII)`, a outra escreveu o
conjunto ASCII na mão — mesma coisa, trabalho dobrado.

Foram unidas em 02/09 num merge de verdade (as duas histórias preservadas).
A resolução foi: partir da branch das correções e enxertar as peças dos
pedidos inteiras, em vez de emendar marcador de conflito — o git tinha
embaralhado duas funções diferentes que nasceram no mesmo ponto do arquivo.

**Antes de abrir uma conversa nova para mexer aqui, confira se já não existe
uma branch com trabalho em andamento** (`git ls-remote --heads origin`). Duas
frentes no mesmo arquivo custam caro.

## Armadilhas conhecidas (todas já custaram caro uma vez)

### OneDrive travando arquivo

A pasta fica dentro do OneDrive, que **segura o arquivo enquanto sincroniza**.
Refazer uma proposta quebrava com `Permission denied`, e a montagem morria
sem chegar no CRM.

Hoje a proposta é gravada num temporário `.pdf.tmp` (fora do que o monitor
vigia, que só olha `.pdf`) e trocada de uma vez só com `os.replace`,
insistindo enquanto não libera. **Nunca volte a gravar direto por cima.**

### A armadilha que quase apagou proposta pronta

O caminho de saída era apagado *antes* da gravação. Quando esse apagar
falhava, o arquivo entrava na fila de retentativa em segundo plano — que
minutos depois apagaria justamente a proposta nova, gravada no mesmo caminho,
sem erro nenhum no log. Hoje não se apaga nada antes; a troca cuida disso.

### Evento sem mudança nenhuma

O OneDrive toca nos arquivos ao sincronizar e dispara evento à toa. O monitor
guarda o que já enviou (caminho, data e tamanho) e não reenvia igual.

### Acento no nome do arquivo derrubava o envio inteiro

```
CRM: erro inesperado — 'ascii' codec can't encode character '\xe9'
```

O endereço do arquivo no storage viaja no cabeçalho do HTTP, que **só aceita
ASCII**. Um `é` ali derruba o envio antes de qualquer coisa chegar no CRM.

A causa era sutil: o `_sanitizar_arquivo` nasceu como tradução da regra do
navegador (`[^\w.\-]+` → `_`), mas **o `\w` do Python aceita letra com acento e
o do JavaScript não**. O acento atravessava a limpeza intacto e ia parar na
URL. Hoje o acento vira letra simples antes, e a limpeza roda com `re.ASCII`.

Isso valia para a **proposta também** — não era coisa do pedido. Todo cliente
com acento no nome vinha falhando calado desde o começo, e dá para ver no
banco: o `file_url` desses arquivos tem a marca da limpeza do navegador
(`Valdir_Jos_Coppini`, com o "é" sumido), e não a do monitor — ou seja, foram
anexados na mão. São 31 clientes com acento no nome espalhados pelo funil,
8 deles em `Contrato`.

**Lição:** ao traduzir uma regra do front para o Python, `\w` não é a mesma
coisa nos dois lugares.

### As duas pastas não podem se misturar

Se a pasta dos pedidos ficar dentro da pasta de orçamentos, o mesmo PDF cairia
nos dois vigias — e o da proposta **apaga o arquivo original** depois de montar.
O `PropostaHandler` ignora tudo que estiver dentro da pasta de pedidos
(`_dentro_de`), e na hora de escolher a pasta o programa recusa a mesma pasta
dos orçamentos. Não tire nenhuma das duas proteções.

### Senha invisível

O `getpass` do Python não mostra nada ao digitar — nem asterisco — e a pessoa
acha que o teclado travou. Hoje cada tecla vira `*`.

### A faxina foi parar na abertura do monitor

**Por quê:** o `.bat` obrigava a baixar um segundo arquivo e deixar na mesma
pasta do `.exe`. Pedido dele: *"manda o link direto, simplifica mais pra mim"*.
Hoje o monitor oferece a faxina na abertura, no mesmo formato das outras
perguntas (20 segundos e segue), e um arquivo `~/.egemap_faxina_drive_ok`
marca que ja foi feita para nao perguntar de novo.

A marca **só é gravada se ele realmente aplicou**. Ver a prévia e desistir
devolve `2` do `limpar_drive.main`, e aí a pergunta volta na próxima abertura
— senão, quem quisesse pensar melhor perdia o atalho.

### Toda leitura de saída de programa tem que dizer UTF-8 na marra

`subprocess.run(..., text=True)` no Windows decodifica com **cp1252**, não
com UTF-8. O rclone responde em UTF-8, então basta um cliente chamado
**Álvaro** (`Á` = `0xC3 0x81`) para estourar:

```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x81
```

E o pior: o erro acontece numa **thread interna** do `subprocess`, então
`subprocess.run` **não levanta exceção** — ele volta com `stdout = None`. Quem
não esperava isso quebra depois, longe da causa (`'NoneType' object has no
attribute 'strip'`).

Isso derrubou a faxina e, calado, também o `drive.py`: o `_listar` voltava
vazio, o `_pasta_equivalente` não achava a pasta existente e o monitor criava
`Passo De Torres` de novo — justamente o problema que ele tinha acabado de
corrigir. Não apareceu nos meus testes porque aqui o padrão é UTF-8; só
aparece no Windows dele.

Sempre `encoding="utf-8", errors="replace"`, nunca `text=True` sozinho.

### O "dedupe" do rclone não tem modo "merge"

Os modos são `interactive|skip|first|newest|oldest|largest|smallest|rename`.
Juntar pastas de nome igual o `dedupe` faz **sozinho, sempre** — o modo só
decide o que fazer com arquivo repetido. Por isso a 1ª passada usa `skip`
(junta as pastas, não toca em arquivo).

A 2ª passada usa `newest` **sem `--by-hash`**. Com `--by-hash` o rclone
procura arquivo idêntico na árvore inteira e apagaria o PDF de um cliente só
porque outro cliente tem um igual. Sem ele, só considera mesmo nome na mesma
pasta — que é exatamente o caso das duplicatas do Drive.

### As duas contas se bloqueiam: nenhuma consegue limpar tudo sozinha

As pastas do Drive têm **dois donos misturados**:

| Conta | O que ela criou | O que ela NÃO consegue mexer |
|---|---|---|
| `orcamentosegemap` (o rclone do monitor) | quase tudo | o que o Natanael subiu pelo navegador |
| `egemapesquadrias` (o navegador dele) | o que ele subiu na mão | o que o rclone criou |

No Google Drive, ser dono da **pasta** não dá direito de apagar **arquivo dos
outros** dentro dela. Por isso a faxina de 26/08 fez tudo, menos apagar duas
cópias na pasta do Felipe Dos Santos Coelho: `Error 403
insufficientFilePermissions`.

E pelo lado de cá é o espelho: o connector do Drive (que entra como
`egemapesquadrias`) **renomeia e move**, mas **não apaga** — `trash_file`
devolve "The caller does not have permission" mesmo em arquivo dele.

Conclusão prática: resto de duplicata com dono trocado tem que ser apagado
**pelo Natanael, no navegador**. O jeito de ajudar é renomear com um prefixo
`APAGAR - ...`, porque as cópias têm nome idêntico e ele não conseguiria
distinguir uma da outra na tela.

### No Drive, só a MESMA proposta substitui a anterior

**Por quê:** o `drive.py` agrupava os materiais em três "categorias" — PVC,
Alumínio/Madeira, e final. Alumínio e madeira na mesma categoria significa que
uma proposta só de `ALM` e uma só de `MAD`, do mesmo cliente no mesmo dia, se
apagavam: a segunda a subir levava a primeira embora.

Pego pelo Natanael num teste real (Luciano Pereira de Oliveira, 26/08): o
monitor subiu o `MAD` às 18:44:44 e apagou o `ALM`; ele repôs o `ALM` na mão
às 18:45:25. No log aparecia `removi versao anterior de hoje`.

Hoje a regra é: substitui só quando os materiais são **exatamente os mesmos**
(`_mesma_opcao`). E nome **sem** código de material nunca conta como igual —
proposta renomeada para `BRANCO`/`CINZA`, ou a final do `COMPLETO`. É o mesmo
espírito do CRM, onde duas opções viram duas linhas que convivem. Se for mesmo
a mesma proposta refeita, o nome do arquivo é o mesmo e o envio passa por cima
dela, sem precisar apagar nada antes.

Regra geral que vale a pena manter: **na dúvida, não apague.** Acumular um PDF
a mais é barato; perder a proposta do cliente não.

### O `\w` do Python aceita acento — e isso derrubava o CRM

O `_sanitizar_arquivo` do `crm.py` usava `re.sub(r"[^\w.\-]+", "_", nome)`,
com o comentário "mesma regra que o CRM usa na tela". **Não é a mesma.** No
JavaScript do CRM, `\w` é só `[A-Za-z0-9_]`; no Python 3 ele aceita letra
acentuada. Então o "ç" passava batido.

Esse nome vai dentro da **URL** do envio, e o Python monta a linha do pedido
HTTP em ASCII. Resultado:

```
CRM: erro inesperado — 'ascii' codec can't encode characters in position 184-185
```

Pego pelo Natanael em 27/08 com "Ricardo da Conceição Rezende" (o `çã` de
"Conceição" são dois caracteres seguidos, daí as duas posições).

**Está assim desde o primeiro commit do CRM (`00d875d`).** Ou seja: todo
cliente com acento no nome da pasta — Conceição, João, Assunção, Álvaro,
Roldão — nunca conseguiu ter a proposta lançada. O log avisava, mas com uma
mensagem que não dizia nada.

Duas correções:

1. O nome do arquivo no storage agora sai só com ASCII, trocando acento pela
   letra sem acento (`Conceição` → `Conceicao`), não por `_`. O nome bonito
   continua no `file_name`, que é o que aparece na tela do CRM.
2. Trava geral no `_chamar`: qualquer caractere fora do ASCII na URL vira
   `%XX` antes de sair. Só o que está fora do ASCII — `?`, `&` e `=`
   continuam valendo como sintaxe.

Lição que vale para o projeto todo: **`\w`, `\d` e `\s` em Python são
Unicode.** Onde o resultado precisa ser ASCII, escreva o conjunto na mão.

### Os campos da Capa mudam de nome quando o layout é refeito

A montagem escreve vendedor, cliente e nº do pedido por cima de placeholders
entre colchetes na Capa. A busca era por **texto exato e minúsculo**
(`[nome do vendedor]`).

Em 02/09 o Natanael passou a usar uma Capa nova ("PROPOSTA COMERCIAL ·
SETEMBRO 2026"), e nela os campos viraram `[NOME DO VENDEDOR]`,
`[NOME DO CLIENTE]` e `[N°]`. Nenhum casou. Resultado: a proposta saiu para o
cliente com **`[NOME DO CLIENTE]` escrito na capa**, e ninguém foi avisado —
a Página Final continuou certa porque lá o marcador já era maiúsculo.

O monitor **lia** tudo direito (`ALIEL FERNANDES`, `NATANAEL VIEIRA
MARCELINO`, pedido `2346`); só não achava onde escrever.

Hoje a comparação ignora maiúscula, acento e pontuação, e cada campo aceita
várias grafias (`MARCAS_VENDEDOR` e companhia). O valor sai no estilo do
campo: placeholder em maiúscula → nome em maiúscula. E **quando um campo não
é encontrado, o log avisa** com o nome do arquivo da Capa — era o pior do
problema, falhar calado numa coisa que vai para o cliente.

Exige os colchetes de propósito: sem eles, o rótulo "Vendedor" impresso na
Capa seria confundido com o campo a preencher.

### O mês da Capa é escrito na hora de montar, não fica guardado

A Capa tem `EGEMAP · PROPOSTA COMERCIAL · <MÊS> <ANO>` num canto da primeira
página. Isso envelhece sozinho: vira o mês e toda proposta sai com o mês
passado, porque ninguém lembra de reabrir a Capa no LibreOffice só para
trocar uma palavra. Quando o Natanael pediu (02/09), a Capa dele ainda dizia
`AGOSTO 2026`.

Hoje o `atualizar_mes_da_capa` reescreve essa linha na montagem, com o mês de
hoje. Aceita as formas usuais (`AGOSTO 2026`, `Agosto de 2026`,
`agosto/2026`), respeita como estava escrito (caixa alta continua caixa alta)
e troca o ano junto.

Usa a **DM Sans** porque é a fonte dessa linha — a Capa 1 usa News Cycle nos
campos grandes, mas o rodapé é DM Sans. Conferido que o `·` existe na fonte
empacotada antes de reescrever a linha inteira.

Quando a Capa não tem mês nenhum, não faz nada e **não avisa** — não é erro.

### Duas cópias do monitor rodando ao mesmo tempo

Descoberto em 02/09, investigando por que existiam duas pastas
`Silvana Pires Da Silva` / `Silvana Pires da Silva` no Drive. A pasta com
`Da` maiúsculo foi criada em 01/09 17:06 — e o código de hoje escreve `da`
minúsculo. Rodei as duas versões lado a lado para confirmar:

    b2f5cb8 (versão antiga) -> Silvana Pires Da Silva
    e0cea19 (versão de hoje) -> Silvana Pires da Silva

Ou seja: quem criou aquela pasta foi uma **cópia velha do monitor**, rodando
ao mesmo tempo que a nova.

A causa: o `registrar_inicio_automatico()` só era chamado dentro do
`if not config_ok:` — a primeira configuração. Depois disso, a chave do
Windows (`...\CurrentVersion\Run`) continuava apontando para o **primeiro
`.exe`** que ele configurou, para sempre. Toda vez que ele baixava uma versão
nova e abria pelo Downloads, o Windows continuava abrindo a velha no boot.
Duas cópias vigiando a mesma pasta, cada uma mandando o mesmo PDF pro Drive.

Isso provavelmente também explica duplicações antigas que foram atribuídas
só à corrida entre threads (as três pastas iguais do `Felipe Dos Santos
Coelho`, por exemplo).

Três coisas mudaram:

1. `registrar_inicio_automatico()` roda em **toda abertura**, não só na
   primeira. A cópia que ele abriu por último é a que passa a abrir no boot.
   Se o caminho mudou, o monitor avisa na tela qual era o antigo.
2. `fechar_copias_antigas()` procura, na abertura, qualquer outro
   `EGEMAP-Monitor*.exe` rodando e fecha. O `LIKE` no filtro pega cópias que o
   navegador renomeou (`EGEMAP-Monitor (1).exe`).
3. O cabeçalho mostra o caminho do `.exe` que está rodando, para essa
   confusão ser visível de cara.
Cheguei a reativar a pergunta da faxina para juntar as duas pastas da
Silvana, e ele respondeu que **não quer** — só queria entender o motivo da
duplicação. Voltei a marca para `.egemap_faxina_drive_ok`. Lição: ele pergunta
para entender, não para pedir serviço. Responder a pergunta e parar.

As duas pastas continuam lá, e tudo bem: o `_resolver_destino` escolhe a
equivalente com mais conteúdo, então proposta nova da Silvana cai na certa
(4 arquivos contra 1).

**Cuidado com o exe de arquivo único:** o PyInstaller `--onefile` roda em
**dois processos com o mesmo nome** (o de fora, que descompacta, e o de
dentro, que é o Python). Por isso o `fechar_copias_antigas()` pula
`os.getpid()` **e** `os.getppid()` — sem isso, o monitor fecharia a si mesmo
na abertura.

### Proposta de ontem voltando pro CRM por cima da de hoje

04/09, cliente Ana Ivonete. O log mostrou duas linhas no mesmo segundo:

    CRM: Atualizado 'Pvc + Aluminio' em 'Ana Ivonete' — R$ 90.800,25
    CRM: Atualizado 'Pvc + Aluminio' em 'Ana Ivonete' — R$ 79.510,88

A primeira é a proposta de 04-09 (68.375,26 de PVC + 22.424,99 de ALM). A
segunda é a de **03-09**, que estava parada na pasta e foi reenviada. Como a
linha do CRM se chama pelos materiais (`Pvc + Aluminio`), as duas caem na
mesma linha — então a proposta de ontem tomou o lugar da de hoje, com o valor
de ontem.

Por que ela foi reenviada: o `_JA_ENVIADO` mora na memória do programa. Depois
de reabrir o monitor ele está vazio, e qualquer toque do OneDrive numa
proposta antiga vira evento de "modificado" — o `_queue` põe toda
`Proposta Comercial *.pdf` de volta na fila do CRM e do Drive.

Agora `_lancar_no_crm` e `_lancar_no_drive` recusam proposta cuja data no nome
não é a de hoje (`dia_do_arquivo`), e o CRM diz no log que recusou. Renomear
continua funcionando: quando vem `origem_antiga`, a intenção é justamente
mexer numa proposta antiga.

Isso vale também depois de trocar de versão: reabrir o monitor não relança
mais o que já foi lançado nos dias anteriores.

### Nunca travar esperando resposta

O monitor abre junto com o Windows. Toda pergunta na abertura (conectar CRM,
conectar Drive) **desiste sozinha em 20 segundos**. Se um dia isso virar um
`input()` normal, o monitor para de funcionar no boot e ninguém percebe.

---

## Como conferir as coisas

```bash
python crm.py testar                  # lista os negócios em "Orçamentos a Fazer"
python crm.py testar "Lara Castilho"  # com qual card esse nome casaria
python drive.py testar                # se o Drive está conectado

python crm.py contratos               # lista quem está em "Contrato"
python crm.py contratos "Fulano"      # para qual contrato o pedido iria
python pedidos.py testar "<pasta>"    # confere a pasta inteira de pedidos:
                                      # nome lido, valor lido e para onde iria
```

O `python pedidos.py testar` não escreve nada no CRM — é o jeito de conferir se
os nomes dos arquivos estão casando com os contratos antes de confiar nele.

O log na janela preta do monitor conta tudo: o que montou, o que mandou pro
CRM, e por que não mandou quando não mandou. **Peça o print dessa janela antes
de teorizar** — foi assim que se achou o problema do OneDrive.

Para validar contra dados reais, consulte o banco pelo Lovable (projeto
`egemapcrmflow`). Vale muito mais do que supor.

---

## O que está pausado

O **alterar orçamento** (robô que aplica alterações pedidas pelo cliente) está
parado de propósito, e vai ser um projeto **separado**:

```
branch: claude/orcamento-2346-alteracao-fmwarh-7top10
arquivo: alterar_orcamento.py (~2.400 linhas)
último commit: 17/08/2026
```

Não está na `main` e **não deve ser mexido** junto com o monitor. Para
retomar, abra uma conversa nova e aponte para essa branch.

As branches `claude/budget-folder-drive-automation-*` são a tentativa antiga
com PowerShell (`watcher.ps1`), substituída pelo `drive.py`. Podem ser
ignoradas.

---

## Como trabalhar aqui

- Fale em **português**, direto, sem jargão. O Natanael não é programador.
- Ao mudar comportamento, **valide contra os dados reais do CRM** antes.
- Erro no CRM ou no Drive **nunca pode derrubar a montagem da proposta** —
  tudo roda em segundo plano, dentro de `try/except`.
- Na dúvida entre errar calado e avisar, **avise no log e não mexa**. Lançar
  no cliente errado é pior do que não lançar.
- Depois de mexer, o `.exe` novo sai sozinho pelo Actions. Mande o link
  `releases/latest/download/EGEMAP-Monitor.exe` — não peça para procurar
  artefato na aba Actions, é confuso.
