// dispatch-hotkey: atalho global ⌘⇧D que abre o CtxDispatch.app (Carbon, funciona em qualquer app e não pede Acessibilidade)
import AppKit
import Carbon

var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
    NSWorkspace.shared.open(URL(fileURLWithPath: "/Applications/CtxDispatch.app"))
    return noErr
}, 1, &spec, nil, nil)
var ref: EventHotKeyRef?
RegisterEventHotKey(UInt32(kVK_ANSI_D), UInt32(cmdKey | shiftKey), EventHotKeyID(signature: OSType(0x4354_5844), id: 0),
                    GetApplicationEventTarget(), 0, &ref)
NSApplication.shared.run()
