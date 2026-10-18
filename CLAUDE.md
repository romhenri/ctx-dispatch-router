# ctx-dispatch-router

Print da tela → decide para qual destino (repo git ou pasta comum) o conteúdo vai → um `claude -p`
dentro daquele destino faz a inserção (e commita, se for repo). Tudo está em `router.py` (Python + PyYAML).

## Fluxo

```
⌘⇧D → dispatch-hotkey (LaunchAgent, Carbon) → /Applications/CtxDispatch.app
    → router.py capture: screencapture -i → inbox/AAAA-MM-DDTHH-MM-SS.png, depois roda `run` desacoplado
    → fase 1 route():  claude -p no ROOT, só Read, --json-schema → {destino, confianca, justificativa, conteudo}
    → fase 2 insert(): claude -p com cwd = path do destino, --add-dir inbox/, ferramentas mínimas
    → done/ ou pending/ (+ .json), log.jsonl, notificação (osascript)
```

## Invariantes (não quebre)

- **O router decide só QUANDO, nunca COMO.** Arquivo, formato e duplicatas são decididos pela seção
  "Inserção via ctx-dispatch-router" do CLAUDE.md do destino (template em `templates/`). Não coloque
  regras de formato em `INSERT_PROMPT`.
- **A fase 1 não escreve nada.** `--tools Read`.
- **A fase 2 é restrita:** `INSERT_TOOLS` + `--permission-mode dontAsk` (nega tudo que não estiver
  na lista). Bash só para `git add/commit/status/diff/log`. Sem push.
- **Tipos de destino** (`tipo` no yaml, padrão `repo`):
  - `repo`: exige git com commits. A fase 2 ganha `GIT_TOOLS` e precisa terminar com um commit `dispatch:`
    e a árvore limpa; alterar sem commitar vira `erro`. É reversível com `git revert`.
  - `folder`: sem git e sem Bash. O que mudou é medido por `snapshot()` (mtime e tamanho) antes e depois.
    Não há desfazer automático; os arquivos alterados ficam no log.
- **O resultado é medido no disco, nunca no que o agente diz.** Se nada mudou, o resultado é `sem alteração`,
  mesmo que o resumo afirme o contrário.
- **A fase 2 só roda com confiança alta**, a não ser que o usuário aprove pelo `review`.

## Estados

| Onde | Quando |
|---|---|
| `inbox/` | recém-capturado, em processamento |
| `inbox/done/` | inserido (ou já existia) |
| `inbox/pending/` + `.json` | `nenhum`, confiança média/baixa, erro, path inexistente, sem CLAUDE.md, sem git. O `.json` traz `{decisao, motivo}` |

`log.jsonl`: uma linha por evento, com `resultado` em `inserido`, `sem alteração`, `pendente`
(decisão: nenhum, confiança, destino inválido), `erro` (falha do claude ou da inserção), `descartado`
ou `dry-run`, e com `arquivos` alterados e `commit`. Para ver: `router.py status`.
`run.log`: stdout/stderr das execuções em segundo plano. É o primeiro lugar para olhar quando uma captura some.

## Testar

Nunca rode a fase 2 nos repos reais para testar. Use `DESTINOS=<yaml de teste>` apontando para repos
descartáveis. `--dry-run` roda só a fase 1 e não move nada. `CLAUDE_BIN` escolhe o binário do claude
(o `.app` roda com PATH mínimo, por isso o `install.sh` grava o caminho absoluto).

## Mexendo no atalho

A tecla fica em `hotkey.swift` (`kVK_ANSI_D`, `cmdKey | shiftKey`). Depois de alterar, rode `./install.sh`.
