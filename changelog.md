# WhatsApp Companion changelog

## 2026.11.07 - 2026-11-07

### Stable and Beta at the same time

Run WhatsApp Stable and WhatsApp Beta with WhatsApp Companion at the same time. Each one has its own connection, recovery and announcements. While one WhatsApp is in front, announcements from the other are not spoken. Launching a WhatsApp that is already connected now says so. When both are launched at once, their temporary WebView2 settings are changed one after the other.

**Force close Microsoft Store WhatsApp processes** now asks whether to close WhatsApp Stable, WhatsApp Beta or both. It suggests the only WhatsApp connected to WhatsApp Companion, and `Enter` still keeps WhatsApp open. Closing one WhatsApp leaves the other connected.

### Automatic connection

Add **Connect automatically when WhatsApp is opened** to the WhatsApp Companion menu, with a command you can assign in Input Gestures. It is off by default. When it is on, WhatsApp Stable or Beta opened from the Start menu, taskbar or desktop in the last 30 seconds is closed and opened again with WhatsApp Companion. A WhatsApp that was already open is never closed. After a failed automatic connection, that WhatsApp is not reopened again until you launch it from the menu.

### More reliable launch

Check WhatsApp's processes and its local debugging port directly through Windows instead of starting PowerShell several times per launch. On a computer that has just started or is busy, or when WMI is unhealthy, these checks could use up the whole launch time and end with "WhatsApp Companion could not start". PowerShell is still used if the direct check is unavailable.

Check the listener again against WhatsApp's current processes when WhatsApp replaces its first process during launch, instead of retrying with the old process list until time runs out.

When a launch step runs out of time, the NVDA log now shows the check that kept failing, how many attempts were made and when each step finished.

### Clearer messages

Rewrite WhatsApp Companion messages, menu help and dialogs in English and Indonesian so they are shorter and easier to understand. Call commands in Input Gestures no longer say "native".

## 2026.11.01 - 2026-11-01

Run the recording helper with a process-scoped execution policy, so microphone listing, call detection, recording and compact call-view restore also work on computers that keep the default Restricted PowerShell policy.

Stop recording automatically when the call window has been gone for about 15 seconds, and announce where the file was saved. A minimized call window or an uncertain check never stops recording. Stop cleanly at the 4-hour limit, announce a recording that was stopped by a session lock or secure desktop after unlocking, and report Stop during preparation as cancelled. Do not leave behind or announce an empty WAV file when recording fails to start, and keep the other microphones listed when one has no name.

Start recording with the window that is in front once NVDA's setup dialog has closed, so a dialog still closing is not mistaken for a focus change. If the call window really loses focus during setup, say so instead of reporting that no call was found. Report Stop or a session lock during preparation as cancelled, and say that preparation is being cancelled rather than that the file is being saved. Report a busy sticker transport as busy instead of as a network error. When no call controls can be found, pass call shortcuts through to WhatsApp as before instead of reporting a failed action. Keep a recording outcome for after unlock when the session locks while it is being announced.

Read PowerShell output as UTF-8, so launching works when any running program's path contains accented or other non-English characters. End a restore as closed when WhatsApp exits while the connection is being restored. Restore the temporary WebView2 setting when NVDA starts if a previous launch was interrupted. Treat a failed reply to a connection check and a failed journal encryption as recoverable errors. Report a recording only once when Stop arrives just after the recorder finished by itself. Read call labels without changing NVDA's configuration from the call worker. Try every verified address when describing stickers, so broken IPv6 routing can fall back to IPv4. Send the restore click with its own screen position, so it never lands where the mouse pointer was left.

Let a slow sticker provider use the whole request time instead of failing after 10 seconds, and allow up to 2048 tokens for its answer, so a model that reasons first still has room for the description. Do not reinstall an update that already failed its startup check, and quarantine an update that hangs or crashes WhatsApp after it was loaded. Report a truncated update download as a network problem. Pass Stop to the recorder immediately, so Stop pressed at the end of preparation does not still record. Use the names NVDA shows for its Tools and Preferences menus in the Indonesian help.

Reuse recent call checks while the menu or recording dialog is open instead of starting a PowerShell probe every two seconds, and report a failed check as unknown rather than as no call. Say that call controls are being restored when a call shortcut has to wait, translate the channel names in the recording dialog, and run call diagnostics on the call worker.

Include WhatsApp Web Plus 2026.11.01. Its new browser tab recording menu is hidden in Companion, which keeps its native call recorder.

Run native call-control discovery and activation on a dedicated COM worker so slow accessibility providers do not block NVDA. Reject expired actions and changed call windows without replaying shortcuts. Protect recording preparation and queued worker announcements across lock and secure-desktop transitions.

Move embedded userscript delivery-status announcements to Chat activity monitor, independent of automatic new-message reading. Automatically read messages no longer end with their delivery status; the first status of a message you just sent is announced by Chat activity monitor instead.

Fix cancellation during the final native call check, suppress delayed recording results across lock transitions, and keep new call checks separate from cancelled workers. Restore compact controls when WhatsApp reports the verified microphone checkbox as offscreen. Accept the current official userscript grant while rejecting unexpected permissions. Verify signed bundle metadata during synchronization and source/package release checks.

Recognize both full and compact native call windows. Restore compact controls with one verified click when a call shortcut needs them, then ask the user to press the shortcut again without replaying the action. Recording setup closes before restoring the call window and requires a fresh connected-call check before capture. Stop cancels pending preparation as well as active recording. Announce changes in call availability and cancel recovery on focus changes, session lock, or unloading.

Add manual call recording from the Companion menu and assignable NVDA gestures. Capture the selected WhatsApp process tree and a chosen microphone into separate channels of a local WAV file. Keep audio processing outside NVDA, stop on shutdown or session lock, and never fall back to system-wide loopback. Requires Windows build 20348 or later. Microphone recording is independent of WhatsApp mute. Recording stops by itself after the call ends, or earlier with Stop recording.

Route Companion announcements through NVDA's speech function used by Speech History, so bridged announcements such as sticker descriptions and message status can be recorded. Preserve language commands, braille output, and existing output guards, with one speech call per announcement. This routing change affects Companion only, not the browser userscript.

Included WhatsApp Web Plus 2026.11.01 changes:

Help load older messages when Arrow Up stalls at the first available message. Scroll only after native navigation leaves focus unchanged, with bounded movement and no continuous polling.

Announce how many times each identical sticker appears, including mixed messages with repeated and different stickers. Put each sticker description on a new line after its heading.

Read up to six unique stickers in the focused message with one AI request and numbered descriptions. Filter duplicate images and keep the existing single-sticker reading behavior.

Read existing sticker image descriptions in Focus Mode when WhatsApp leaves the message unnamed. Preserve the sender and time, avoid repeated descriptions, and update the label when the image description changes.

Recognize the Indonesian message status Dikirim as Sent so delivery changes are announced in group chats as well.

Restore Enter and Space voice-message playback for the new WhatsApp microphone icons while preserving support for the previous layout.

## 2026.10.19 - 2026-10-19

Clean UI now recognizes the Indonesian desktop promotion description, so the promotion is hidden without a custom title.

### NVDA review and connection feedback

- Make empty-text message and chat cells readable through NVDA's standard character, word, and line review commands in Focus Mode.
- Use complete accessible names for supported buttons, toggle buttons, and tabs, including changing unread counts and content-derived labels. Preserve native activation, states, usable cell text, and editable-field text handling.
- Scope review overlays to the WhatsApp app module and respect privacy-masked accessible names.
- Announce connection recovery success, failure, or app closure after recovery starts, rather than leaving users with only a restoring message. Preserve speech, braille, foreground, and cancellation guards.

### Read Sticker and embedded userscript

- Include WhatsApp Web Plus 2026.10.19 with Gemini, Groq, Cloudflare Workers AI, and Custom, OpenAI-compatible providers in that order.
- Add bounded native HTTPS sticker transport without a browser extension or changes to the announcement bridge. Validate endpoints, payloads, deadlines, response limits, and cancellation.
- Keep provider credentials encrypted in the WhatsApp profile. Changing Cloudflare models retains the token for the same account. Support Llama 3.2 image input and multimodal-message input for compatible alternative models.
- Include explicit Llama 3.2 model agreement and local preview, with completion/timeout feedback and no automatic sticker resend.
- Include menu fitting in small windows, download progress, photo album captions, Read more expansion, Alt+1 arrow-navigation fixes, and chat/channel/community closure announcements.
- Update defaults: Privacy mode, automatic message reading, Enter/Space voice playback, Clean Status, menu fitting, and Clean UI on; total unread-chat announcements off. Existing settings are retained.

### Documentation and validation

- Refresh English and Indonesian help, document provider setup and limitations, and summarize object review and recovery results.
- Add regression coverage for review overlays, native sticker transport, and recovery outcomes. Add-on packaging and installed-NVDA validation remain separate steps.
- Align the embedded script with year.month.day version 2026.10.19, which compares higher than 2.6.91. Signed publishing remains a separate step and anti-rollback checks remain unchanged.

## 2026.10.04

### Connection recovery

- Retry connection recovery for up to 90 seconds on busy systems, instead of stopping after three attempts within 20 seconds.
- Retry temporary PowerShell failures while checking whether WhatsApp is still running, using the same overall recovery deadline. Treat WhatsApp as closed only after a successful check returns no running processes.
- Announce recovery progress once when retrying a failed process check or reconnecting to a running app. Preserve the last completed operation result and keep normal app closure quiet.
- Recognize cancellation even when it coincides with a failed probe reaching its deadline.
- Preserve underlying PowerShell stage and timeout details in reconnect logs. Identify discovery that completes after the deadline as a timeout instead of reporting that no target was found.

## 2026.09.25

### Reliability fixes

- Release the registry lease and report a recovery error when deleting the recovery journal fails.
- Discard queued braille output when braille messages are disabled, including timer retries and context-clear notices.
- Verify release tags, source versions, packaged manifests, artifact names, and repair-helper integrity before publishing.
- Verify the embedded userscript version, exact bytes, hash, and bundle metadata against the upstream lock before publishing.

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
