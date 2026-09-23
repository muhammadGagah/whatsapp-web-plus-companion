# WhatsApp Companion changelog

## 2026.09.23

### Message reading

- Open Alt+Shift+C in a native NVDA reader without launching a browser window.
- Read authored message lines in a read-only text field without visual line wrapping. Switch to formatted view for links and lists.
- Copy only message text without viewer headings or timestamps. Preserve original line breaks and explicit blank lines.
- Validate reader content and reject malformed lists while preserving valid nested lists and headings.

### Shortcuts and calls

- Include WhatsApp Web Plus 2.6.84 with shortcut recording, manual remapping, and optional shortcuts to start voice and video calls.
- Open the Shift+F8 Shortcut list in an NVDA reading window with section headings. Include script defaults and WhatsApp built-in shortcuts for browser and WebView2 versions.
- Provide native call shortcuts for answering, declining, microphone, camera, reactions, raising or lowering a hand, screen sharing, and ending calls.
- Customize call-control labels in multiple languages while retaining built-in labels. Settings survive add-on updates in the same NVDA configuration.
- Improve recovery from the compact call view and recognition of controls during screen sharing.
- Prevent recursive dispatch when a remapped shortcut overlaps native chat navigation.

### Startup and compatibility

- Allow slower listener checks up to 30 seconds per query within a 60-second listener budget and the overall launch deadline. Log port and process queries separately. Keep endpoint ownership checks before connecting.

- Narrow package discovery to the selected WhatsApp app and allow more time for initial package and process checks while preserving cancellation and overall deadlines.
- Include the PowerShell stage, elapsed time, and time budget in failure logs.

- Preserve the built-in WhatsApp app module on NVDA 2026.2 and later, including its default focus interaction and manual browse-mode selection.
- Retain compatibility with earlier supported NVDA versions and keep native call shortcuts available.
- Improve startup recovery after WhatsApp reloads without injecting the userscript twice into the same document.
- Improve delayed command feedback in NVDA speech On-demand mode.

### Registry permissions and repair

- Fix permission diagnosis reporting success when the per-user WebView2 policy keys are missing, even though launching WhatsApp cannot create them. Offer setup through Diagnose and repair WebView2 policy permissions.
- Verify registry access from the normal NVDA session after repair, including when the elevated helper reports that permissions already exist. Retry any pending restoration of the temporary launch setting.
- Stop permission diagnosis when the WhatsApp process state cannot be verified.
- Fix repair stopping before the administrator prompt because the packaged batch helper did not match its expected hash. Correct the integrity metadata and stabilize helper line endings.
- Verify both repair helpers inside the built add-on package to catch integrity mismatches before release.

### Updates
- Verify signed userscript updates with trusted Ed25519 keys. Keep the installed bundle when verification fails or is unavailable.

### Requirements

- Requires NVDA 2025.1 or later. The manifest's last-tested version is NVDA 2026.2.
- Bundles WhatsApp Web Plus 2.6.84. Publisher signing guides are available in the script repository in English and Indonesian.
