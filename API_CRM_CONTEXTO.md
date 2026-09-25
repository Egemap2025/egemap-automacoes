# Contexto para a API do CRM EGEMAP (FlowCRM)

## Objetivo (o que vamos fazer com a API)
Temos um **robô** (programa em Python, rodando no PC da EGEMAP) que monta orçamentos
de esquadrias automaticamente em outro sistema (o W-Vetro). Hoje o robô já monta tudo
sozinho a partir de uma lista de esquadrias.

Queremos que esse robô **leia o CRM sozinho**: de tempos em tempos ele consulta a API,
pega os **negócios novos que estão na etapa "Orçamentos a Fazer"** e, pra cada um, lê
os **dados do cliente** e a **tabela do Levantamento de Aberturas** daquele negócio.
Com isso ele pré-monta o orçamento no W-Vetro.

**Importante:** o robô só **LÊ** o CRM (read-only). Ele **não escreve, não move etapa,
não altera nada** no CRM. Toda a escrita acontece no outro sistema (W-Vetro).

Precisamos, então, de **endpoints de leitura (GET)** que devolvam JSON.

---

## 1. Autenticação
Precisamos saber:
- **URL base** da API (ex.: `https://crm.egemapesquadrias.com.br/api/v1`)
- **Como autenticar**: token/chave e onde vai (ex.: header `Authorization: Bearer <TOKEN>`
  ou `x-api-key: <TOKEN>`).
- **Como gerar/obter** o token (e se ele expira).

> A chave fica guardada só no PC do robô, num arquivo de config local. Não precisa ser
> pública.

---

## 2. Listar negócios de uma etapa (o gatilho do robô)
Um endpoint para **listar os negócios de uma etapa específica** — no caso, a etapa
**"Orçamentos a Fazer"**.

Ideal:
- Filtrar por **etapa** (nome ou id da etapa/coluna do Kanban).
- Filtrar/ordenar por **data** (pra pegar só os que entraram depois de uma data/hora),
  ou devolver a data de criação e a data de entrada na etapa pra o robô decidir.
- Devolver, pra cada negócio, pelo menos: **id do negócio**, nome do cliente,
  data de criação, data de entrada na etapa atual, e se **tem levantamento**.

Exemplo de chamada:
```
GET /deals?stage=Orçamentos a Fazer&updated_after=2026-09-25T00:00:00Z
```

Exemplo de resposta:
```json
{
  "deals": [
    {
      "id": "830056cf-86b4-4b1c-8797-23b90f03341c",
      "cliente": "Magda Silveira Cardoso Bona",
      "etapa": "Orçamentos a Fazer",
      "criado_em": "2026-09-23T15:05:00Z",
      "entrou_na_etapa_em": "2026-09-23T15:12:00Z",
      "tem_levantamento": true
    }
  ]
}
```

---

## 3. Ler os dados de UM negócio
Um endpoint para pegar o detalhe de um negócio pelo **id**, com os **dados do cliente**
que o robô precisa pra cadastrar no W-Vetro:

- **nome** do cliente (obrigatório)
- **celular** e/ou **telefone**
- **cidade** (e **UF/estado**, se tiver)
- **vendedor / responsável** (nome — o robô casa esse nome com a lista de vendedores
  do W-Vetro, então quanto mais parecido com o nome real, melhor)
- (se tiver) **e-mail, endereço, número, bairro, CEP, complemento**
- **etapa** atual

Exemplo de chamada:
```
GET /deals/830056cf-86b4-4b1c-8797-23b90f03341c
```

Exemplo de resposta:
```json
{
  "id": "830056cf-86b4-4b1c-8797-23b90f03341c",
  "cliente": "Magda Silveira Cardoso Bona",
  "celular": "48 9680-0792",
  "telefone": null,
  "email": null,
  "cidade": "Sombrio",
  "uf": "SC",
  "endereco": null,
  "numero": null,
  "bairro": null,
  "cep": null,
  "vendedor": "Aliel Fernandes",
  "etapa": "Orçamentos a Fazer"
}
```

---

## 4. Ler o Levantamento de Aberturas do negócio  ← O MAIS IMPORTANTE
Cada negócio tem um **Levantamento de aberturas** (aquela tabela estruturada que já
existe no CRM). Precisamos de um endpoint que devolva **a lista de esquadrias (itens)**
desse levantamento, com **um campo por coluna da tabela**.

Campos de cada esquadria (usar exatamente estes nomes de coluna já existentes):
- **codigo** (ex.: "J1", "PJ1", "P1")
- **ambiente** (ex.: "Dormitório 1")
- **esquadria** (a descrição/tipo, ex.: "Correr 2 folhas com persiana", "Maxim-ar",
  "Porta de giro", "Portinhola ventilada", "Porta pivotante PM28")
- **material** (Alumínio / Madeira / PVC)
- **linha** (ex.: "25", "32", "30", "Colonial", "MDF Ultra", "Ripados"...)
- **cor** (ex.: "Preto", "Madeira Grápia", "Tauari", "Branca")
- **largura** (número, em cm ou mm — **ver observação abaixo**)
- **altura** (número, em cm ou mm)
- **quantidade** (número)
- **vidro** (ex.: "Temperado 6mm incolor", "Mini boreal 4mm", "Sem vidro")
- **tela** (Sim / Não)
- **persiana** (Sim / Não)
- **acionamento** (Manual / Automática / Não se aplica)
- **observacao** (texto livre)

Exemplo de chamada:
```
GET /deals/830056cf-86b4-4b1c-8797-23b90f03341c/levantamento
```

Exemplo de resposta:
```json
{
  "deal_id": "830056cf-86b4-4b1c-8797-23b90f03341c",
  "escopo": "Esquadrias externas e portas internas",
  "sistema": "Alumínio Linha 25",
  "itens": [
    {
      "codigo": "J1",
      "ambiente": "Dormitório 1",
      "esquadria": "Correr 2 folhas com persiana",
      "material": "Alumínio",
      "linha": "25",
      "cor": "Preto",
      "largura": 160,
      "altura": 110,
      "quantidade": 1,
      "vidro": "Temperado 6mm incolor",
      "tela": "Não",
      "persiana": "Manual",
      "acionamento": "Manual",
      "observacao": "Peitoril 100"
    },
    {
      "codigo": "PJ1",
      "ambiente": "Área gourmet / Sala",
      "esquadria": "Porta-janela de correr 3 folhas",
      "material": "Alumínio",
      "linha": "32",
      "cor": "Preto",
      "largura": 240,
      "altura": 210,
      "quantidade": 1,
      "vidro": "Temperado incolor",
      "tela": "Não",
      "persiana": "Não",
      "acionamento": "Não se aplica",
      "observacao": "Folhas sequenciais"
    }
  ]
}
```

### Observação sobre as MEDIDAS
Diga **em qual unidade** as medidas vêm (centímetros ou milímetros). Hoje a tabela do
Levantamento mostra em **centímetros**. O robô converte pra mm internamente — só
precisamos saber a unidade certa pra não errar por 10x.

### IMPORTANTE: precisamos de TODAS as esquadrias do negócio
O robô decide o que fazer **item por item, pelo campo `material`**:
- **Alumínio** e **Madeira** (inclui portas internas de madeira e portinholas) → o robô faz.
- **PVC** (linhas **Confort** / **Elegance**) → o robô **NÃO faz** (é feito em outro sistema),
  ele só ignora esses itens.

Por isso precisamos que a API devolva **todas as esquadrias do negócio**, inclusive as
que o vendedor eventualmente agrupou como "PVC" — porque no meio delas costuma ter
**portas internas de madeira e portinholas que SÃO do W-Vetro** e o robô precisa fazer.
Se um mesmo negócio tiver **mais de um levantamento** (ex.: um de PVC e um de alumínio),
precisamos de **todos**, com o `material` de cada item, pra o robô filtrar sozinho.

---

## Resumo do que precisamos do colega
1. **URL base** + **como autenticar** (token e header) + como gerar o token.
2. **GET lista de negócios** por etapa (ex.: "Orçamentos a Fazer"), com data de
   criação/entrada na etapa.
3. **GET detalhe do negócio** (dados do cliente + vendedor).
4. **GET levantamento do negócio** (lista de esquadrias com os campos acima).
5. **Unidade das medidas** (cm ou mm).

> Se for mais fácil, pode mandar **1 exemplo real de resposta JSON** de um negócio +
> o levantamento dele (com dados fictícios, tudo bem). Com isso a gente já implementa
> a leitura sem precisar de mais nada.

Tudo é **somente leitura**. O robô não altera nada no CRM.
