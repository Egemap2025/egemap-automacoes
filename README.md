# Egemap — Agente de Orçamentos no Drive

Sobe automaticamente os PDFs de orçamento para o Google Drive assim que entram na pasta do computador. Roda em segundo plano, sem precisar abrir nada, sem precisar fazer nada.

---

## Como funciona

Você salva o PDF na pasta normalmente:
```
Orçamentos \ Sombrio \ João Silva \ orcamento.pdf
```

O agente detecta e envia para o Drive automaticamente:
```
Pedidos e Contratos / 2026 / Sombrio / João Silva / orcamento.pdf
```

---

## Instalação (só uma vez)

### O que você precisa ter no computador

Só uma coisa: **conexão com a internet**.

O instalador baixa tudo que precisa automaticamente.

---

### Passo único: clique duas vezes em `INSTALAR.bat`

O que vai acontecer automaticamente:

1. Baixa o **rclone** (programa que faz a ponte com o Google Drive)
2. Pergunta o **caminho da sua pasta** de orçamentos no computador
3. Abre o **navegador para você fazer login** no Google e clicar em "Permitir"
4. Configura o agente para **iniciar junto com o Windows**
5. Inicia o agente imediatamente

Depois desse único clique, nunca mais precisa fazer nada.

---

## Testar se está funcionando

Clique duas vezes em `TESTAR.bat` — se aparecer a mensagem verde, está tudo certo.

---

## Estrutura de pastas

O agente lê a **cidade** e o **cliente** pelo nome das pastas:

```
📁 Orçamentos               ← pasta que você configurou no INSTALAR
 └── 📁 Sombrio             ← cidade
      └── 📁 João Silva     ← cliente
           └── 📄 arq.pdf  ← detectado aqui → vai pro Drive na hora
```

---

## Acompanhar o que aconteceu

Abra `watcher.log` para ver o histórico:

```
2026-06-30 08:15  Novo arquivo: orcamento_001.pdf
2026-06-30 08:15    Cidade:  Sombrio
2026-06-30 08:15    Cliente: João Silva
2026-06-30 08:15    [ENVIADO] orcamento_001.pdf
```

---

## Arquivos

| Arquivo | O que faz |
|---|---|
| `INSTALAR.bat` | **Instala tudo — execute uma vez** |
| `TESTAR.bat` | Confirma que está funcionando |
| `INICIAR.bat` | Inicia o agente manualmente (se necessário) |
| `PARAR.bat` | Para o agente |
| `watcher.ps1` | O agente em si |
| `config.json` | Caminho da pasta e configurações |
| `watcher.log` | Registro de atividade |
| `rclone.exe` | Baixado automaticamente pelo instalador |
| `rclone.conf` | Credenciais do Drive — não compartilhar |
