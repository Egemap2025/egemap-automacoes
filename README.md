# egemap-automacoes — W-vetro

Automação para alteração de orçamentos no sistema W-vetro via Chrome.

---

## O que faz

- Abre o W-vetro no Chrome automaticamente
- Vai até o orçamento pelo número
- Para cada item que você informar, clica nos **3 pontos (⋮)** e executa:
  - **Substituir projeto** — troca a linha/modelo da janela ou porta
  - **Editar item** — altera vidro, cor/madeira ou persiana (motor/fita)

---

## Pré-requisitos

- [Node.js 18+](https://nodejs.org/) instalado
- Google Chrome instalado
- Windows / Mac / Linux

---

## Instalação (primeira vez)

```bash
# 1. Instale as dependências
npm install

# 2. (Opcional) Configure a senha para login automático
cp .env.example .env
# Abra o arquivo .env e coloque sua senha do W-vetro
```

> **Sem o `.env`**: o script abre o Chrome e aguarda você fazer login manualmente antes de continuar.

---

## Como usar

```bash
npm start
```

O terminal vai perguntar:

1. **Número do orçamento**
2. **Tipo de alteração** — 1 para Substituir projeto / 2 para Editar item
3. **Número do item** dentro do orçamento (1, 2, 3…)
4. **Dados da alteração** (novo projeto, vidro, cor, persiana etc.)
5. Se quiser fazer mais alterações no mesmo orçamento, responda **s**

O Chrome abre automaticamente, faz todas as alterações e fica aberto para você revisar.

---

## Campos suportados em "Editar item"

| Campo | Exemplos de valor |
|---|---|
| Vidro | `temperado 6mm`, `laminado 8mm`, `jateado` |
| Cor / Madeira | `branco`, `nogueira`, `cinza textura` |
| Persiana | `motor`, `recolher fita`, `sem persiana` |

---

## Problemas comuns

| Situação | O que fazer |
|---|---|
| "Botão de opções não encontrado" | Verifique se o número do item está certo e se o orçamento está aberto |
| Campo não preenchido automaticamente | O script pausa e pede que você preencha manualmente no navegador |
| Erro de login | Configure `WVETRO_SENHA` no arquivo `.env` ou faça login manualmente quando pedido |
| Screenshot de erro | O arquivo `erro-wvetro.png` é salvo na pasta do projeto |
