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
montar_orcamento.py       # Utilitário de montagem/testes
drive_watcher.ps1         # Envia as propostas prontas para o Google Drive (rclone)
.github/workflows/build-exe.yml  # Build automático do .exe (PyInstaller)
```

## Envio automático para o Google Drive (`drive_watcher.ps1`)

Script PowerShell que fica monitorando a pasta de orçamentos e envia para o
Drive apenas os PDFs finais: `... PVC.pdf`, `... ALM.pdf` (ou `MAD`/`MAD ALM`)
e o completo `... DD-MM.pdf`. Ao enviar, apaga no Drive o PDF anterior **do
mesmo dia e do mesmo tipo** (PVC substitui PVC, ALM substitui ALM, completo
substitui completo); PDFs de outros dias nunca são apagados.

### Configuração

1. Copie `config.json.example` para `config.json` e ajuste `pasta_orcamentos`
   (raiz no formato `Orcamentos/Ano/Estado/Cidade/Cliente/arquivo.pdf`) e `ano`.
2. Coloque `rclone.exe` e um `rclone.conf` (com o remote `egemap` configurado
   para o Google Drive) na mesma pasta do script.
3. Rode `drive_watcher.bat` (ou `drive_watcher.ps1` diretamente).

`config.json`, `rclone.conf`, `rclone.exe`, `watcher.log` e `enviados.json`
não são versionados (contêm credenciais/caminhos locais ou são gerados em
runtime).
