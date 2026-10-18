# ctx-dispatch-router

Aperte **⌘⇧D**, selecione uma região da tela e o print vai sozinho para o repo certo
(candidaturas, faculdade, planos...). O Claude Code decide o destino e insere o conteúdo seguindo o
CLAUDE.md daquele destino. Destinos `repo` ganham um commit `dispatch:` (reversível); destinos
`folder` são pastas comuns, sem git.

## Instalação (macOS)

Requisitos: Python 3, Claude Code (`claude`) logado e Xcode Command Line Tools (`swiftc`).

```bash
./install.sh
```

O script instala o PyYAML, cria `/Applications/CtxDispatch.app` e registra o atalho como LaunchAgent,
que sobe sozinho no login. Na primeira captura, o macOS pede **Gravação de Tela** para o CtxDispatch.
Libere a permissão e capture de novo.

Depois:

1. Edite `destinos.yaml` com os seus destinos (`nome`, `tipo: repo|folder`, `path`, `criterio` com "Vai" e "NÃO vai").
2. Em cada repo de destino, cole `templates/insercao-claude-md.md` no CLAUDE.md e preencha os
   trechos `EDITE` (arquivo e formato). Um destino sem CLAUDE.md fica sempre como pendente.

## Uso

| Comando | O que faz |
|---|---|
| ⌘⇧D | captura a região (Esc cancela), processa em segundo plano e mostra uma notificação |
| `./router.py run img.png --dry-run` | só a fase 1: mostra a decisão sem mover nem inserir nada |
| `./router.py run img.png` | pipeline completo para uma imagem já existente |
| `./router.py review` | revisa os pendentes: aprovar, trocar destino, descartar, abrir a imagem |
| `./router.py status [-n 10]` | resultado das últimas execuções, com os arquivos alterados e o commit |

Resultados (na notificação e no `status`):

| | Significado |
|---|---|
| ✅ inserido | algo foi gravado no destino (arquivos listados, mais o commit se for repo) |
| ➖ sem alteração | o destino foi certo, mas nada mudou (ex.: já existia) |
| ⏸ pendente | não inserido por decisão: `nenhum`, confiança média/baixa, path ou CLAUDE.md ausente |
| ❌ erro | não inserido por falha (claude falhou, alterou sem commitar...) |

As notificações não aparecem com Foco/Não Perturbe ativo. O `status` sempre mostra o resultado.

Para onde vai cada captura:
- **`inbox/done/`**: inserida com sucesso.
- **`inbox/pending/`**: algo impediu a inserção. O `.json` ao lado traz a decisão e o motivo.
- **`log.jsonl`**: histórico com o hash do commit.
- **`run.log`**: erros das execuções em segundo plano.

Desfazer uma inserção: `git revert <hash>` no destino `repo`. Em `folder`, os arquivos alterados
aparecem no `status` e precisam ser revertidos à mão.

## Desinstalar

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.ctx-dispatch-router.hotkey.plist
rm ~/Library/LaunchAgents/com.ctx-dispatch-router.hotkey.plist
rm -rf /Applications/CtxDispatch.app
```
