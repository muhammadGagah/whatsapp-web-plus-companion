# WhatsApp Companion changelog

## 2026.09.21

### Added

- Native WhatsApp call shortcuts for answering, declining, camera, microphone,
  reactions, raising/lowering a hand, screen sharing, and ending calls. Call
  commands appear in Input Gestures when opened from WhatsApp.
- A Call control labels menu with English and Indonesian help. Add labels in
  several languages, one per line, while keeping built-in labels. Settings apply
  across NVDA profiles and survive add-on updates in the same NVDA configuration.
- Native NVDA message reading for `Alt+Shift+C`, preserving message paragraphs,
  lists, safe links, and sent time without opening a desktop browser window.
- Signed userscript update verification with trusted Ed25519 keys. If
  verification fails or is unavailable, the existing bundle stays unchanged.

### Improved

- Recovery from the compact call view when a requested control is unavailable.
  Once the full call view is restored, press the shortcut again to perform the action.
- Recognition of reaction and screen-sharing checkbox controls, including call
  controls while sharing a screen.
- Delayed command feedback in NVDA speech On-demand mode.
- Startup recovery when WhatsApp reloads, without duplicate userscript injection
  into the same document.
- Permission diagnosis stops when the WhatsApp process state cannot be verified,
  instead of treating an unknown state as closed.

### Compatibility and bundled script

- Raised the minimum NVDA version to 2025.1 to use its bundled cryptography library
  for signed updates. The manifest's last-tested version is set to 2026.2.
- Bundled WhatsApp Web Plus 2.6.83, including text-formatting toolbar navigation,
  message-reader improvements, corrected media-close feedback, and incoming
  video-call shortcuts. Companion continues to handle native call-window commands.
- Moved publisher signing guides into the script repository, with English and
  Indonesian versions and configurable example paths.
