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
monitorar.py    Programa principal. Vigia a pasta, monta a proposta com
                Capa/Página Final, e chama crm.py e drive.py.
crm.py          Lança no CRM. Só biblioteca padrão.
drive.py        Sobe pro Google Drive (via rclone). Só biblioteca padrão.
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

`crm.py` e `drive.py` são **independentes**: o monitor os importa dentro de
`try/except` e funciona sem eles. Eles não sabem nada do monitor. Mantenha
assim — foi o que permitiu acrescentar cada um sem quebrar o que já rodava.

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

### O valor do negócio é o MAIOR, não a soma

**Por quê:** duas opções são alternativas — o cliente fecha uma. A Maria
Teresa tinha R$ 113.711 e R$ 162.717; somar daria R$ 276.428 e inflaria a
previsão de vendas. Na mão, o Natanael preenchia com a maior.

### O valor só é mexido até "Orçamento Pronto"

**Por quê:** havia 97 negócios abertos em *Apresentado*, *Negociação* e
*Contrato* com valor preenchido — números que o vendedor já negociou.
Sobrescrever seria apagar o desconto fechado sem ninguém perceber. Dessas
etapas em diante o monitor **só troca o PDF**.

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
```

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
