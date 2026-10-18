#!/usr/bin/env python3
"""ctx-dispatch-router: print da tela -> fase 1 (qual destino?) -> fase 2 (inserção no destino, via CLAUDE.md dele).

Uso:
  router.py capture             seleciona região, salva em inbox/ e processa em segundo plano
  router.py run IMG [--dry-run] processa uma imagem (--dry-run: só fase 1, não move nada)
  router.py review              revisa inbox/pending/ (aprovar, trocar destino, descartar)
  router.py status [-n N]       resultado das últimas N execuções
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "inbox"
DONE = INBOX / "done"
PEND = INBOX / "pending"
LOG = ROOT / "log.jsonl"
CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
DESTINOS = Path(os.environ.get("DESTINOS", ROOT / "destinos.yaml"))  # outro arquivo para testes

# Fase 2: só editar arquivos (e commitar, se repo). dontAsk nega tudo que não estiver na lista.
FILE_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep"]
GIT_TOOLS = ["Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)",
             "Bash(git diff:*)", "Bash(git log:*)"]
TIPOS = ("repo", "folder")
ICON = {"inserido": "✅", "sem alteração": "➖", "pendente": "⏸", "erro": "❌",
        "descartado": "🗑", "dry-run": "🔍"}

ROUTE_PROMPT = """Você é o roteador do ctx-dispatch-router. Não escreva em nenhum arquivo.
Leia a imagem {img} com a ferramenta Read e decida para qual destino abaixo o conteúdo dela vai,
seguindo os critérios ("vai" e "NÃO vai") de cada um.

Destinos:
{destinos}

Regras:
- Exatamente um destino, ou "nenhum" se nada se encaixa claramente. "nenhum" é uma resposta normal.
- confianca "alta" só quando o conteúdo bate sem ambiguidade com o critério do destino.
- justificativa: uma frase.
- conteudo: transcrição fiel do que está na imagem (texto completo; resuma só o que não for texto)."""

INSERT_PROMPT = """Você recebeu um print via ctx-dispatch-router para inserir nesta pasta.

Imagem original: {img}
Conteúdo extraído pelo roteador:
---
{conteudo}
---

Siga a seção "Inserção via ctx-dispatch-router" do CLAUDE.md daqui (arquivo, formato, duplicatas).
Se o conteúdo já existir, não duplique: não altere nada e diga isso no resumo.{commit}
No campo resumo, descreva em até 60 caracteres o que foi inserido (ex: "adicionada experiência X")."""
COMMIT_LINE = """
Ao terminar, faça `git add` só dos arquivos que você alterou e `git commit -m "dispatch: <descrição curta>"`."""


def load_destinos():
    data = yaml.safe_load(DESTINOS.read_text()) or {}
    destinos = data.get("destinos") or []
    for d in destinos:
        missing = {"nome", "path", "criterio"} - d.keys()
        if missing:
            sys.exit(f"destinos.yaml: destino {d.get('nome', '?')} sem {', '.join(sorted(missing))}")
        d.setdefault("tipo", "repo")
        if d["tipo"] not in TIPOS:
            sys.exit(f"destinos.yaml: destino {d['nome']} com tipo {d['tipo']!r} (use {' ou '.join(TIPOS)})")
    return {d["nome"]: d for d in destinos}


def claude(prompt, cwd, schema, tools, allowed, add_dir=None, timeout=600):
    """Roda claude -p e devolve o structured_output (dict). Levanta RuntimeError se falhar."""
    cmd = [CLAUDE, "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(schema),
           "--tools", ",".join(tools), "--allowedTools", *allowed,
           "--permission-mode", "dontAsk", "--no-session-persistence"]
    if add_dir:
        cmd += ["--add-dir", str(add_dir)]
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude saiu {p.returncode}: {(p.stderr or p.stdout).strip()[:300]}")
    if out.get("is_error") or not out.get("structured_output"):
        raise RuntimeError(f"claude falhou: {str(out.get('result'))[:300]}")
    return out["structured_output"]


def route(img, destinos):
    """Fase 1: decide o destino. Não escreve em nada."""
    schema = {
        "type": "object",
        "properties": {
            "destino": {"enum": [*destinos, "nenhum"]},
            "confianca": {"enum": ["alta", "media", "baixa"]},
            "justificativa": {"type": "string"},
            "conteudo": {"type": "string"},
        },
        "required": ["destino", "confianca", "justificativa", "conteudo"],
    }
    lista = "\n\n".join(f"## {d['nome']}\n{d['criterio'].strip()}" for d in destinos.values())
    return claude(ROUTE_PROMPT.format(img=img, destinos=lista), ROOT, schema,
                  ["Read"], ["Read"], add_dir=img.parent, timeout=300)


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True).stdout.strip()


def insert_blocker(dest):
    """Motivo para não rodar a fase 2 nesse destino, ou None."""
    path = Path(dest["path"]).expanduser()
    if not path.is_dir():
        return f"path inexistente: {path}"
    if not (path / "CLAUDE.md").is_file():
        return f"destino sem CLAUDE.md: {path}"
    if dest["tipo"] == "repo" and not git(path, "rev-parse", "HEAD"):
        return f"tipo repo mas não é um repo git com commits: {path}"
    return None


def snapshot(path):
    """{arquivo relativo: (mtime, tamanho)} de tudo fora de .git."""
    return {str(p.relative_to(path)): (st.st_mtime_ns, st.st_size)
            for p in path.rglob("*") if ".git" not in p.parts and p.is_file() for st in [p.stat()]}


def insert(img, dest, conteudo):
    """Fase 2: roda claude -p dentro do destino. Devolve (resumo, hash do commit ou None, arquivos alterados).

    O resultado é medido no disco, não no que o agente diz: nada mudou = lista vazia.
    """
    path = Path(dest["path"]).expanduser()
    repo = dest["tipo"] == "repo"
    head, before = git(path, "rev-parse", "HEAD") if repo else None, snapshot(path)
    schema = {"type": "object", "properties": {"resumo": {"type": "string"}}, "required": ["resumo"]}
    prompt = INSERT_PROMPT.format(img=img, conteudo=conteudo, commit=COMMIT_LINE if repo else "")
    out = claude(prompt, path, schema, FILE_TOOLS + ["Bash"] * repo, FILE_TOOLS + GIT_TOOLS * repo,
                 add_dir=img.parent)
    after = snapshot(path)
    arquivos = sorted(f for f in after.keys() | before.keys() if before.get(f) != after.get(f))
    if not repo:
        return out["resumo"], None, arquivos
    if git(path, "status", "--porcelain"):
        raise RuntimeError(f"alterou sem commitar: {', '.join(arquivos) or 'veja git status'}")
    commit = git(path, "rev-parse", "HEAD")
    if commit == head:
        return out["resumo"], None, []
    if not git(path, "log", "-1", "--format=%s").startswith("dispatch:"):
        raise RuntimeError(f"commit {commit[:7]} sem prefixo dispatch:")
    return out["resumo"], commit, git(path, "show", "--name-only", "--format=", "HEAD").splitlines()


def notify(msg):
    subprocess.run(["osascript", "-e", "on run argv", "-e",
                    'display notification (item 1 of argv) with title "ctx-dispatch-router"',
                    "-e", "end run", msg], capture_output=True)


def log(img, decisao, resultado, motivo=None, commit=None, arquivos=None):
    entry = {"ts": datetime.now().isoformat(timespec="seconds"), "imagem": img.name,
             "destino": (decisao or {}).get("destino"), "confianca": (decisao or {}).get("confianca"),
             "resultado": resultado, "motivo": motivo, "commit": commit, "arquivos": arquivos or []}
    with LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def park(img, decisao, motivo, resultado="pendente"):
    """Move para pending/ com o .json da decisão ao lado. resultado: pendente (decisão) ou erro (falha)."""
    PEND.mkdir(parents=True, exist_ok=True)
    target = PEND / img.name
    shutil.move(img, target)
    target.with_suffix(".json").write_text(
        json.dumps({"decisao": decisao, "motivo": motivo}, ensure_ascii=False, indent=2))
    log(target, decisao, resultado, motivo)
    sugerido = f" ({decisao['destino']}?)" if decisao and decisao["destino"] != "nenhum" else ""
    msg = f"{ICON[resultado]} NÃO inserido{sugerido}: {motivo}"
    notify(msg)
    print(msg)


def dispatch(img, decisao, destinos):
    """Fase 2 + estados. img está em inbox/ ou inbox/pending/."""
    dest = destinos.get(decisao["destino"])
    motivo = insert_blocker(dest) if dest else f"destino desconhecido: {decisao['destino']}"
    resultado = "pendente"
    if not motivo:
        try:
            resumo, commit, arquivos = insert(img, dest, decisao["conteudo"])
        except Exception as e:
            motivo, resultado = f"erro na inserção: {e}", "erro"
    if motivo:
        if img.parent != PEND:
            return park(img, decisao, motivo, resultado)
        log(img, decisao, resultado, motivo)
        return print(f"{ICON[resultado]} NÃO inserido: {motivo}")
    DONE.mkdir(parents=True, exist_ok=True)
    shutil.move(img, DONE / img.name)
    img.with_suffix(".json").unlink(missing_ok=True)
    resultado = "inserido" if arquivos else "sem alteração"
    log(DONE / img.name, decisao, resultado, resumo, commit, arquivos)
    msg = (f"✅ {dest['nome']}: {resumo}" if arquivos else f"➖ {dest['nome']}: nada mudou ({resumo})")
    notify(msg)
    print(msg, *(f"\n   {f}" for f in arquivos), f"\n   commit {commit[:7]}" if commit else "")


def run(img, dry_run=False):
    destinos = load_destinos()
    img = img.resolve()
    if not dry_run and img.parent == PEND:  # reprocessar um pendente do zero
        img.with_suffix(".json").unlink(missing_ok=True)
        img = Path(shutil.move(img, INBOX / img.name))
    if not dry_run and img.parent != INBOX:
        INBOX.mkdir(exist_ok=True)
        img = Path(shutil.copy(img, INBOX / f"{datetime.now():%Y-%m-%dT%H-%M-%S}{img.suffix}"))
    try:
        decisao = route(img, destinos)
    except Exception as e:
        if dry_run:
            sys.exit(f"✗ fase 1: {e}")
        return park(img, None, f"erro na fase 1: {e}", "erro")
    print(json.dumps(decisao, ensure_ascii=False, indent=2))
    if dry_run:
        ok = decisao["destino"] != "nenhum" and decisao["confianca"] == "alta"
        log(img, decisao, "dry-run")
        return print(f"→ inseriria em {decisao['destino']}" if ok else "→ ficaria pendente")
    if decisao["destino"] == "nenhum":
        return park(img, decisao, "nenhum destino")
    if decisao["confianca"] != "alta":
        return park(img, decisao, f"confiança {decisao['confianca']}")
    dispatch(img, decisao, destinos)


def capture():
    INBOX.mkdir(exist_ok=True)
    img = INBOX / f"{datetime.now():%Y-%m-%dT%H-%M-%S}.png"
    subprocess.run(["screencapture", "-i", "-x", str(img)])
    if not img.exists():  # Esc
        return
    # Processa desacoplado: o atalho volta na hora. Saída em run.log para depuração.
    # ponytail: capturas simultâneas no mesmo destino podem disputar o git; fila se isso acontecer
    with (ROOT / "run.log").open("a") as out:
        subprocess.Popen([sys.executable, __file__, "run", str(img)], stdout=out, stderr=out,
                         stdin=subprocess.DEVNULL, start_new_session=True, cwd=ROOT)


def review():
    destinos = load_destinos()
    nomes = list(destinos)
    for img in sorted(PEND.glob("*.png")):
        meta_file = img.with_suffix(".json")
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        decisao = meta.get("decisao") or {}
        print(f"\n━━ {img.name}  ({meta.get('motivo', 'sem .json')})")
        print(f"   sugerido: {decisao.get('destino', '?')} [{decisao.get('confianca', '?')}]"
              f"  {decisao.get('justificativa', '')}")
        print(f"   conteúdo: {decisao.get('conteudo', '')[:300]}")
        while True:
            op = input("   [a]provar  [t]rocar destino  [d]escartar  [p]ular  [o]abrir  [s]air > ").strip().lower()
            if op == "o":
                subprocess.run(["open", str(img)])
                continue
            if op == "s":
                return
            if op == "p":
                break
            if op == "d":
                img.unlink()
                meta_file.unlink(missing_ok=True)
                log(img, decisao, "descartado")
                print("   descartado")
                break
            if op == "t":
                for i, n in enumerate(nomes, 1):
                    print(f"     {i}. {n}")
                escolha = input("   número > ").strip()
                if not (escolha.isdigit() and 1 <= int(escolha) <= len(nomes)):
                    continue
                decisao = {**decisao, "destino": nomes[int(escolha) - 1]}
                op = "a"
            if op == "a":
                if not decisao.get("conteudo"):
                    print("   sem conteúdo extraído (fase 1 falhou); rode `router.py run` de novo nesta imagem")
                    continue
                dispatch(img, decisao, destinos)
                break
    print("\nnenhum pendente restante" if not any(PEND.glob("*.png")) else "")


def status(n):
    linhas = LOG.read_text().splitlines()[-n:] if LOG.exists() else []
    if not linhas:
        return print("nenhuma execução registrada")
    for e in map(json.loads, linhas):
        destino = e["destino"] or "-"
        if e["resultado"] in ("pendente", "erro") and destino != "nenhum":
            destino += "?"
        detalhe = e["motivo"] or ""
        if e.get("commit"):
            detalhe += f" ({e['commit'][:7]})"
        print(f"{ICON.get(e['resultado'], '·')} {e['ts'][5:16].replace('T', ' ')}  {destino:<14} "
              f"{e['resultado']:<14} {detalhe}")
        for f in e.get("arquivos") or []:
            print(f"{'':<34}{f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("capture")
    r = sub.add_parser("run")
    r.add_argument("img", type=Path)
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("review")
    st = sub.add_parser("status")
    st.add_argument("-n", type=int, default=10)
    a = ap.parse_args()
    if a.cmd == "capture":
        capture()
    elif a.cmd == "run":
        run(a.img, a.dry_run)
    elif a.cmd == "status":
        status(a.n)
    else:
        review()


if __name__ == "__main__":
    main()
