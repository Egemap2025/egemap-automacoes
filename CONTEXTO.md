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
montar_orcamento.py   Utilitário de teste, fora do fluxo automático.
```

`crm.py`, `drive.py` e `pedidos.py` são **independentes**: o monitor os importa
dentro de `try/except` e funciona sem eles. Eles não sabem nada do monitor.
Mantenha assim — foi o que permitiu acrescentar cada um sem quebrar o que já
rodava.

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

### O valor do negócio é o MAIOR, não a soma

**Por quê:** duas opções são alternativas — o cliente fecha uma. A Maria
Teresa tinha R$ 113.711 e R$ 162.717; somar daria R$ 276.428 e inflaria a
previsão de vendas. Na mão, o Natanael preenchia com a maior.

### O valor só é mexido até "Orçamento Pronto"

**Por quê:** havia 97 negócios abertos em *Apresentado*, *Negociação* e
*Contrato* com valor preenchido — números que o vendedor já negociou.
Sobrescrever seria apagar o desconto fechado sem ninguém perceber. Dessas
etapas em diante o monitor **só troca o PDF**.

### "MAD ALM" não move o card

**Por quê:** é peça esperando o `COMPLETO`; o orçamento ainda não acabou. O
PDF vai pro CRM (o vendedor já vê alguma coisa), mas o card fica parado.

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

### As duas pastas não podem se misturar

Se a pasta dos pedidos ficar dentro da pasta de orçamentos, o mesmo PDF cairia
nos dois vigias — e o da proposta **apaga o arquivo original** depois de montar.
O `PropostaHandler` ignora tudo que estiver dentro da pasta de pedidos
(`_dentro_de`), e na hora de escolher a pasta o programa recusa a mesma pasta
dos orçamentos. Não tire nenhuma das duas proteções.

### Senha invisível

O `getpass` do Python não mostra nada ao digitar — nem asterisco — e a pessoa
acha que o teclado travou. Hoje cada tecla vira `*`.

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
