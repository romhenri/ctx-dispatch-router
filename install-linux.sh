#!/bin/bash
# Instala o atalho global Super+Shift+D no GNOME. A captura usa o xdg-desktop-portal (funciona em Wayland).
set -e
cd "$(dirname "$0")" && DIR=$(pwd)
PY=$(python3 -c 'import sys; print(sys.executable)')
CLAUDE_BIN=${CLAUDE_BIN:-$(command -v claude)}
[ -n "$CLAUDE_BIN" ] || { echo "claude não encontrado no PATH"; exit 1; }
"$PY" -c 'import yaml, gi' || { echo "Faltam dependências: sudo apt install python3-yaml python3-gi"; exit 1; }
command -v notify-send >/dev/null || echo "Aviso: sem notify-send, as notificações não vão aparecer."
mkdir -p inbox/done inbox/pending

# O atalho roda com o PATH do gnome-shell (sem nvm), por isso os caminhos absolutos
SCHEMA=org.gnome.settings-daemon.plugins.media-keys
KEY=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/ctx-dispatch-router/
gsettings set "$SCHEMA.custom-keybinding:$KEY" name 'ctx-dispatch-router'
gsettings set "$SCHEMA.custom-keybinding:$KEY" command "env CLAUDE_BIN='$CLAUDE_BIN' '$PY' '$DIR/router.py' capture"
gsettings set "$SCHEMA.custom-keybinding:$KEY" binding '<Super><Shift>d'

# Acrescenta à lista sem tocar nos atalhos que já existem
LIST=$(gsettings get "$SCHEMA" custom-keybindings)
case "$LIST" in
  *"$KEY"*) ;;
  "@as []") gsettings set "$SCHEMA" custom-keybindings "['$KEY']" ;;
  *) gsettings set "$SCHEMA" custom-keybindings "${LIST%]}, '$KEY']" ;;
esac
echo "Pronto: Super+Shift+D em qualquer app, selecione a região (Esc cancela)."
