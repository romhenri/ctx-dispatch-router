#!/bin/bash
# Instala o CtxDispatch.app (captura + pipeline) e o atalho global ⌘⇧D (LaunchAgent, sobe sozinho no login)
set -e
cd "$(dirname "$0")" && DIR=$(pwd)
[ "$(uname)" = Linux ] && exec ./install-linux.sh
PY=$(python3 -c 'import sys; print(sys.executable)')
CLAUDE_BIN=${CLAUDE_BIN:-$(type -ap claude | grep -v cmux-cli-shims | head -1)}  # pula o shim temporário do cmux
"$PY" -m pip install -q pyyaml
mkdir -p inbox/done inbox/pending

# O .app guarda a permissão de Gravação de Tela; PATH mínimo do do shell script, por isso os caminhos absolutos
mkdir -p /Applications
osacompile -o /Applications/CtxDispatch.app -e "do shell script \"CLAUDE_BIN='$CLAUDE_BIN' '$PY' '$DIR/router.py' capture\""
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.ctx-dispatch-router.app" /Applications/CtxDispatch.app/Contents/Info.plist
codesign -f -s - /Applications/CtxDispatch.app
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f /Applications/CtxDispatch.app

swiftc -swift-version 5 -O hotkey.swift -o dispatch-hotkey
PLIST=~/Library/LaunchAgents/com.ctx-dispatch-router.hotkey.plist
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.ctx-dispatch-router.hotkey</string>
<key>ProgramArguments</key><array><string>$DIR/dispatch-hotkey</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
</dict></plist>
PL
launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST"
echo "Pronto: ⌘⇧D em qualquer app, selecione a região (Esc cancela). Na 1ª vez, libere Gravação de Tela para o CtxDispatch."
