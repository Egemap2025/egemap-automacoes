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
.github/workflows/build-exe.yml  # Build automático do .exe (PyInstaller)
```

---

# Agente de Drive (watcher.ps1)

Agente Windows (PowerShell) que monitora a pasta local de orçamentos e envia os PDFs finais automaticamente para o Google Drive via `rclone`.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `watcher.ps1` | O agente em si (loop de monitoramento) |
| `EGEMAP_INSTALAR.bat` | Instala o agente do zero (baixa rclone, autoriza o Drive, configura início automático) |
| `EGEMAP_ATUALIZAR.bat` | Atualiza o `watcher.ps1` sem reinstalar tudo |
| `EGEMAP_INICIAR.bat` | Cria atalho na área de trabalho e inicia o agente manualmente |
| `EGEMAP_LOGIN.bat` | Reautentica com o Google Drive (client_id compartilhado / "object not found") |
| `config.json` | Configuração local (`pasta_orcamentos`, `ano`) |
| `enviados.json` | Rastreamento de arquivos já enviados (mtime por caminho) — gerado em runtime |
| `rclone.exe` / `rclone.conf` | Ferramenta de upload para o Drive — gerados na instalação |

## Instalação

- Pasta local: `%USERPROFILE%\EgemapDrive`
- Instalar do zero: baixar `EGEMAP_INSTALAR.bat` do GitHub e executar
- Atualizar: baixar `EGEMAP_ATUALIZAR.bat` do GitHub e executar (para o agente, reinstala o `watcher.ps1` e reinicia)

## Estrutura de pastas local esperada

```
ORÇAMENTOS \ 2026 \ {ESTADO} \ {CIDADE} \ {CLIENTE} \ arquivo.pdf
```

`p[0]` = ano, `p[1]` = estado (ignorado), `p[2]` = cidade, `p[3]` = cliente, `p[-1]` = nome do arquivo.

## Estrutura no Drive

```
egemap:{ANO}/{CIDADE}/{CLIENTE}/arquivo.pdf
```

- Drive root ID: `1P0EpUNY7F6-j2FX0MmJ0hQZxIQq9nvN5`
- Remote rclone chamado `egemap:`

## Tipos de PDF reconhecidos (pelo nome do arquivo)

| Tipo | Padrão do nome | Exemplo |
|---|---|---|
| Completo (PVC+ALM merged) | termina com `DD-MM` | `Proposta Comercial Joao 17-07.pdf` |
| Material PVC | termina com `pvc` ou `PVC` | `Proposta Comercial Joao 20-07 PVC.pdf` |
| Material ALM | termina com `alm` ou `ALM` | `Proposta Comercial Joao 20-07 ALM.pdf` |
| Ignorado | qualquer outro nome | não enviado |

Aceita tanto espaços (`Proposta Comercial`) quanto underscores (`Proposta_Comercial`) no nome.

## Lógica de envio

- Loop a cada 10 segundos varre todos os `*.pdf` recursivamente
- Arquivo novo → avalia e envia
- Arquivo modificado (mtime mudou) → reenvia
- Arquivo "ignorado" → pula sempre
- Inicialização (`enviados.json` vazio): marca todos os existentes como "ignorado" e só monitora arquivos novos dali em diante

### Limpeza automática no Drive (mesmo dia)

Antes de subir, verifica PDFs do mesmo dia na pasta do cliente no Drive e apaga apenas os do mesmo tipo:

- Subindo PVC → apaga só PVC antigo do dia (ALM e completo ficam)
- Subindo ALM → apaga só ALM antigo do dia (PVC e completo ficam)
- Subindo completo → apaga só completo antigo do dia (PVC e ALM ficam)

Isso permite que os três coexistam quando o cliente pede as três opções.

## Observações técnicas

- `rclone copyto` com `--ignore-times` para forçar reenvio mesmo sem mudança de tamanho
- `rclone lsjson` retorna `ModTime` em UTC (RFC3339) — convertido para hora local com `.ToLocalTime()`
- O agente usa `enviados.json` como estado persistente; deletar esse arquivo força reinicialização
- Se o `rclone` falhar com "object not found" ou aviso sobre client_id compartilhado, executar `EGEMAP_LOGIN.bat` para re-autenticar
