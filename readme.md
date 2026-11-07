# WhatsApp Companion

WhatsApp Companion brings WhatsApp Web Plus accessibility features to the Microsoft Store WhatsApp app. It is an NVDA add-on for WhatsApp Stable and WhatsApp Beta on Windows.

You do not need Tampermonkey.

## Which version should I use?

**Microsoft Store app:** use WhatsApp Companion with NVDA.

**Browser:** use [WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus) with Tampermonkey.

You can use both if you use WhatsApp in both places. Each installation is updated separately.

## What you need

Windows 10 or Windows 11

NVDA 2025.1 through NVDA 2026.2

WhatsApp Stable or WhatsApp Beta from Microsoft Store

The latest `whatsappWebPlusCompanion-<version>.nvda-addon` package

Run NVDA normally. The first-time permission repair may ask for administrator approval. Everyday use does not require administrator rights.

## Install or update WhatsApp Companion

1. Close WhatsApp completely. If it remains in the notification area, choose **Quit** or **Exit**.
2. Open the downloaded `.nvda-addon` file.
3. Check the add-on name and version, then confirm installation.
4. Restart NVDA when asked.

Installing a newer package updates the existing Companion. You do not need to remove the old version first. Keep WhatsApp closed for the next step.

## First installation: fix WebView2 permissions

**Run this step before starting WhatsApp if this is your first Companion installation on this computer.** It prepares the Windows permission that Companion needs.

1. Press `NVDA + N` to open the NVDA menu.
2. Choose **Tools**, then **WhatsApp Companion**.
3. Choose **Diagnose and repair WebView2 policy permissions**.
4. Follow the instructions spoken by NVDA and confirm the repair if it is needed.
5. Allow the repair when Windows asks for administrator permission.

If NVDA says that no repair is needed, continue to the next section. Otherwise, wait for confirmation that the repair succeeded.

You normally only need to do this once. The permission stays in place after restarting Windows or updating NVDA, Companion, or WhatsApp. Run the repair again if the permission is removed from the Windows Registry or Windows is reinstalled.

If Companion has already worked on this computer, an ordinary update does not require another repair.

## Start WhatsApp with Companion

1. Make sure WhatsApp is closed.
2. Press `NVDA + N`.
3. Choose **Tools**, then **WhatsApp Companion**.
4. Choose **Launch WhatsApp Stable with WhatsApp Companion** or **Launch WhatsApp Beta with WhatsApp Companion**.
5. Wait for NVDA to confirm that WhatsApp is running with Companion.

If WhatsApp opens without receiving focus, press `Alt + Tab`.

Launch WhatsApp from the Companion menu when you want its features. Opening WhatsApp from the Start menu does not prepare it for Companion, unless automatic connection is on.

### Using Stable and Beta at the same time

WhatsApp Stable and WhatsApp Beta can both run with Companion at the same time. Launch each one from the Companion menu. When both are open, NVDA speaks WhatsApp Web Plus announcements only from the WhatsApp that is in front. When another program is in front, announcements from both are spoken. **Force close Microsoft Store WhatsApp processes** lets you close only Stable, only Beta, or both.

### Connecting automatically

Turn on **Connect automatically when WhatsApp is opened** in the Companion menu. After that, when you open WhatsApp Stable or Beta from the Start menu, the taskbar or the desktop, Companion closes it and opens it again, prepared for Companion. NVDA says that WhatsApp is reopening, then confirms when Companion is connected. The setting is off by default.

- This only happens within 30 seconds after WhatsApp started. A WhatsApp that was already open, for example before NVDA started, is never closed automatically. Close it and open it again.
- If WhatsApp was opened by selecting a notification, the chat from that notification is not opened after the restart.
- If an automatic connection fails, Companion does not try again for that WhatsApp until you launch it from the menu or turn the setting off and on.
- You can assign a shortcut to **Turn automatic WhatsApp Companion connection on or off** in NVDA's Input Gestures dialog.

## Check that it works

Open a chat and try these commands:

| Shortcut | What it does |
| --- | --- |
| `Alt + 1` | Move to the chat list |
| `Alt + 2` | Move to the latest message |
| `Alt + 3` | Move to the first unread message |
| `Shift + F8` | Open WhatsApp Web Plus settings |

If these commands work, Companion is connected and ready to use. You can leave the default settings as they are.

## Everyday use

Open **NVDA menu > Tools > WhatsApp Companion** to launch WhatsApp or manage Companion.

**Repeat a message:** choose **Report the last WhatsApp Companion result** if you missed a result or use NVDA speech On-demand mode.

**Close WhatsApp:** close it normally. If it stays running, use **Force close Microsoft Store WhatsApp processes**, choose WhatsApp Stable, WhatsApp Beta or All, then select **Force close**. Pressing `Enter` keeps WhatsApp open. This can interrupt calls or transfers and lose unsent text.

**Read a full message:** focus a message and press `Alt + Shift + C` to open it in NVDA's reading window. Press `Escape` to close it.

**Change settings:** press `Shift + F8` inside WhatsApp.

### Reading messages

**Automatic reading of messages** announces new messages. **Chat activity monitor** announces delivery changes such as Sent, Delivered, and Read, along with chat activity. You can turn either setting on or off independently.

Alt+Shift+C opens unwrapped, read-only message text. Up and Down Arrow follow original message lines. Long lines scroll horizontally. Use **Copy message** for plain body text without the reader title or sent time. Use **Formatted view** for wrapped visual reading and clickable links. Escape closes the reader.

### Reviewing messages with NVDA

You can use NVDA's usual character, word, and line review commands on supported WhatsApp messages and controls while in Focus Mode. This helps when review used to say **blank** even though the message or button had a readable name. Use the commands for your NVDA keyboard layout.

Companion uses the accessible message or control name when needed. This includes supported buttons and filter tabs, even when an unread count changes. It respects Privacy mode and keeps typing fields working normally. It does not cover every menu item or control.

For a message with **Read more**, press `Shift+Enter` to expand it. The expanded text keeps its sender and time. Photo album captions are also read with the message details, preceded by **Caption:** or **Keterangan:**.

### Navigating chats and menus

`Alt+1` returns to the remembered chat in the chat list. Use the arrows to continue from there. When Escape closes a private chat, group, channel, or community announcement chat, NVDA announces **Chat is now closed**. Closing only a menu stays silent.

**Keep message menus within the window** helps menus stay open in smaller windows. It is on by default and can be changed under **Shift+F8 > Accessibility**.

### Following downloads

When WhatsApp shows progress for a document download, NVDA announces the percentage at intervals. Downloads use numbered labels instead of reading filenames aloud. Focus does not move. A 100 percent announcement describes WhatsApp's transfer indicator, not confirmation that the file was saved.

### Reading stickers with AI

Read Sticker sends the sticker you choose to an AI provider for a short description. It is off by default and has no assigned shortcut. Providers appear as Gemini, Groq, Cloudflare Workers AI, then Custom, OpenAI-compatible.

1. Open **Shift+F8 > Accessibility > Read Sticker** and enable it.
2. Choose **Configure provider and API key**, select a provider, and enter its credentials. Custom also needs an HTTPS address and an image-capable model.
3. Save your settings and assign **Read Sticker** in **Shortcut remapping**.
4. Focus a sticker message or its sticker button, press the shortcut, and wait for the description.

Only the stickers in the focused message are sent when you use the shortcut, up to six different ones. Identical stickers are described once with a count, and different ones are numbered Sticker 1, Sticker 2, and so on. Moving within the same chat is allowed. Switching chats, language, or settings cancels the old request. Results are read once and do not replace message labels. AI descriptions may be inaccurate.

Companion connects to the provider directly in the background. No browser extension or extra server is required. Keys are encrypted in the WhatsApp profile, separate from your browser profile. Leave the key field blank to keep a saved key. Clearing site data may remove it. Encryption does not protect the key from page scripts or malware. Saving settings does not test the provider.

Animation uses a few sampled images and depends on WebView2 support. Brief changes may be missed. If only a still image can be read, the result says so. Unsupported images and requests that time out produce an error. See the [Read Sticker technical limits and validation guide](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/read-sticker-validation.md) for details.

### Using Gemini

Open [Google AI Studio](https://aistudio.google.com/api-keys), sign in with your Google account, and complete the setup to get an API key. Copy the key, then open **Configure provider and API key** in Read Sticker settings. Select **Gemini**, paste the key into the API key field, and choose **Save**.

### Using Cloudflare

Open **Workers AI > Use REST API** in Cloudflare. Enter its **Account ID** and a **Workers AI API Token** in Read Sticker settings. R2 credentials are not used here.

**Llama 3.2 11B Vision** is the default. You can edit **Model ID** using a full model name, such as `@cf/meta/llama-4-scout-17b-16e-instruct`. Choose a vision model that accepts messages with image data URLs. Llama 3.2 uses its own image format. Changing only the model keeps the saved token. Changing accounts requires a token for the new account.

If the default Llama model needs agreement, read the linked terms and check both statements only if they apply to you. Choose **Agree and enable model**. Confirmed success closes the dialog and announces the result. Then use Read Sticker again. If confirmation does not arrive within 45 seconds, the dialog explains that the result is uncertain. Closing the dialog cannot undo an agreement already received by Cloudflare. Other model agreements are handled in Cloudflare.

**Preview Cloudflare agreement** lets you repeat the steps for a tutorial without sending an agreement. Close it or press Escape to return to settings with your unsaved entries preserved. Provider charges and usage limits still apply to real sticker requests.

### Automatic connection recovery

If Companion loses its connection, it tries to reconnect. NVDA announces when recovery starts and whether it succeeds. If it fails, you will hear what to do next. If WhatsApp closes during recovery, Companion reports that it has stopped. Closing WhatsApp normally stays silent.

These announcements describe the Companion connection. They do not confirm WhatsApp's internet connection or message delivery. Use **Report the last WhatsApp Companion result** if you miss a message.

### Default settings

Privacy mode, automatic new-message reading, Enter/Space voice playback, Clean Status, message-menu fitting, and Clean UI are on for a new installation. Total unread-chat announcements and Read Sticker are off. Updating keeps your saved choices.

### Call control labels

Choose **NVDA menu > Tools > WhatsApp Companion > Call control labels** to add labels for the language used by WhatsApp. You can customize answer, decline, camera, microphone, reactions, raise/lower hand, screen sharing, and end call.

1. Select a **Call action**. The read-only **Built-in labels** field shows labels already recognized.
2. Enter **Additional labels**, one exact control name per line, as spoken by NVDA. Do not include the role or state announcements, such as "button" or "not checked". For toggles, include both states, such as the labels for muting and unmuting the microphone.
3. Select other actions to edit their labels, then choose **Save** to apply all changes immediately. No restart is needed. Choose **Cancel** to discard your edits.

You can add labels in several languages at once. There is no need to choose a language. Built-in labels remain active. Each action accepts up to 20 additional labels, with at most 128 characters per label. A label cannot be assigned to different actions. Microphone labels also apply to the compact call view. Include the **End call** label in your language so Companion can recognize the call window.

Leave a field blank to use the built-in labels. To remove all your custom labels, choose **Reset all additional labels**, then **Save**. Choose **Cancel** to keep your saved labels.

Your labels are saved in NVDA's `nvda.ini`, in the `[whatsappCompanionCallLabels]` section, and shared by WhatsApp Stable and Beta across profiles. They remain available after updating or reinstalling Companion, as long as you keep your NVDA settings. Resetting or deleting those settings also removes your saved labels.

### Recording a call

During a call, open NVDA's Tools menu, then WhatsApp Companion, then Start call recording. Choose Stable or Beta, select the microphone used by WhatsApp, and choose a recording folder. Start recording after informing the participants. Use Stop recording in the same menu to stop at any time. You can assign shortcuts to both commands in NVDA's Input Gestures under WhatsApp Companion.

The WAV file contains WhatsApp audio on the left channel and your microphone on the right. Recordings are saved locally in the chosen folder, initially Documents/WhatsApp Recordings. The recorder captures only the selected WhatsApp process tree, not all speaker output. Other sounds produced by WhatsApp can still be included. NVDA output is excluded from that capture, but a microphone near speakers can pick it up. Use headphones to avoid this.

Start call recording is unavailable while a recording is running or being prepared, and when the last check found no call. If the call state is not known yet, it stays available and checks again when chosen. After you choose Start, the setup dialog closes and Companion opens the call window to verify that the call is connected. If needed, it restores the full view with one click on the participant area. Recording starts only after verification succeeds. Keep the call window active during this step. Stop recording also cancels pending preparation.

The microphone is recorded independently, including while muted in WhatsApp. When the call window has been gone for about 15 seconds, recording stops by itself and NVDA announces that the call ended and where the file was saved. A minimized call window or an uncertain check never stops recording. Recording also stops when the selected WhatsApp process exits, NVDA exits, the session locks, the secure desktop opens, or the four-hour limit is reached. An error may leave a partial WAV file, whose location is announced when available.

Recording requires Windows build 20348 or later, permission for desktop applications to access the microphone, and Windows PowerShell with Add-Type available. The helper runs with a Bypass execution policy for its own process only, so the default Restricted PowerShell policy does not block it, and no system setting is changed. No extra browser extension, encoder, or recorder installation is needed. If process capture fails, the recorder reports an error rather than switching to all system audio. Recording calls in the desktop app is available only through Companion. In a browser, WhatsApp Web Plus has its own Record call menu.

### Call shortcuts

See the [full shortcut list](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#whatsapp-keyboard-shortcuts) for navigation, incoming calls, and optional features.

Use these shortcuts while the WhatsApp call window is active. Press `Alt + Tab` to switch to it if needed.

Call commands appear in **NVDA > Preferences > Input Gestures > WhatsApp Companion** only when the dialog is opened from WhatsApp, so focus WhatsApp first. Global commands such as launching WhatsApp remain available from other applications. Reassign any custom call gestures from earlier versions, because these commands moved to the WhatsApp app module.

| Action | Shortcut |
| --- | --- |
| Answer incoming call | Ctrl+Alt+A |
| Decline incoming call | Ctrl+Alt+D |
| Toggle camera | Ctrl+Alt+V |
| Toggle mute | Ctrl+Alt+M |
| Reactions | Ctrl+Alt+R |
| Raise/lower hand | Ctrl+Alt+H |
| Start/stop screen sharing | Ctrl+Alt+S |
| End call | Ctrl+Alt+W |

If a call shortcut cannot find its control in the small call view, Companion can restore the full view with one click on the participant area. Release the keys and wait for the result, then press the shortcut again to perform the action. The click uses the current position of the verified call window. Switching windows cancels recovery. If recovery fails, open the full view manually.

The reactions shortcut opens WhatsApp's reaction controls. Choose the reaction you want to send. When starting screen sharing, choose what to share in WhatsApp. Press `Ctrl + Alt + S` again to stop sharing.

## Assigning shortcuts

Choose **Shift+F8 > Shortcut remapping**, then select **Read Sticker**, **Record voice message**, **Previous chat**, **Next chat**, **Start voice call**, or **Start video call**. Type a combination such as `Alt+C` or `Alt+V`, then choose **Save**. Use Ctrl or Alt, optionally Shift, followed by a letter, digit, punctuation key such as comma or period, F1–F12, or ArrowUp/Down/Left/Right. Letters refer to physical keyboard positions. Leave the field blank to disable an action. **Restore default** only changes the field. Choose Save to apply or Cancel/Escape to discard. Existing enabled/disabled remaps are preserved. New call shortcuts start unassigned. The recording default is Alt+M. Previous/next defaults are Alt+ArrowUp/Alt+ArrowDown, initially disabled.

Duplicate assignments, fixed script/Companion commands, and WhatsApp's own shortcuts are rejected. Browser, system, NVDA, or extension shortcuts can still take priority. AltGr is not supported. Voice/video calls use the available button in the current conversation header, identified by its icon rather than translated text. No custom language string is required. Unavailable or ambiguous buttons are reported without starting a call.

### Record a shortcut

In Shortcut remapping, select an action and choose **Record shortcut**. NVDA must be in **focus mode** so the script receives your combination. If it is still in browse mode, press **NVDA+Space** before recording. Press a combination such as **Alt+comma**, then choose **Save**. Escape cancels recording. Tab stops recording and moves to the next control. Typing a combination manually is still available. Browser, system, or NVDA commands that intercept the keys cannot be recorded by the script.

## Shortcut list in settings

Choose **Shift+F8 > Shortcut list** to read the script’s default shortcuts grouped by function. This reference shows defaults. Custom assignments remain visible in **Shortcut remapping**. Companion opens NVDA’s native reading window with navigable headings. Press Escape to close it.

## Default script shortcuts

These are defaults, not your saved remappings.

### Navigation

| Shortcut | Function |
| --- | --- |
| `Alt+Shift+1` | Open Chats |
| `Alt+Shift+2` | Open Status or Updates |
| `Alt+Shift+3` | Open Communities |
| `Alt+Shift+4` | Open Channels |
| `Alt+Shift+5` | Open Meta AI |
| `Alt+1` | Move to the chat list |
| `Alt+2` | Move to the latest message |
| `Alt+3` | Move to the first unread message |
| `Alt+Shift+D` | Move between messages and the editor |
| `Alt+T` | Read the chat title. Press twice quickly to toggle chat activity monitoring |
| `Alt+0` | Close the media player or desktop app promotion |

### Messages and formatting

| Shortcut | Function |
| --- | --- |
| `Alt+Shift+C` | Open the focused message in the message reader |
| `Shift+Enter` | Expand Read more in the focused message |
| `Alt+F10` | Open formatting options for selected text in the editor |
| `Enter / Space` | Play or pause the focused voice message when the optional keyboard playback setting is enabled (on by default) |

### Settings and appearance

| Shortcut | Function |
| --- | --- |
| `Shift+F8` | Open or close settings |
| `Alt+Shift+N` | Toggle Privacy Mode |
| `Alt+Shift+L` | Toggle automatic message reading |
| `Alt+Shift+8` | Toggle Clean UI |
| `Alt+Shift+9` | Toggle Original Dark Mode |

### Incoming calls

| Shortcut | Function |
| --- | --- |
| `Ctrl+Alt+A` | Accept an incoming call when its controls are visible |
| `Ctrl+Alt+D` | Decline an incoming call when its controls are visible |

### Remappable defaults

| Shortcut | Function |
| --- | --- |
| `Alt+M` | Record a voice message. Enabled by default |
| `Alt+ArrowUp` | Previous chat. Disabled until enabled in Shortcut remapping |
| `Alt+ArrowDown` | Next chat. Disabled until enabled in Shortcut remapping |
| Not assigned | Start voice call: no default shortcut. Assign in Shortcut remapping |
| Not assigned | Start video call: no default shortcut. Assign in Shortcut remapping |
| Not assigned | Read Sticker: no default shortcut. Assign in Shortcut remapping |

## WhatsApp built-in shortcuts

These are the WhatsApp WebView2 shortcuts. Some commands depend on the selected message or current panel.

| Shortcut | Function |
| --- | --- |
| `Ctrl+Shift+U` | Mark as unread |
| `Ctrl+Shift+M` | Mute chat |
| `Ctrl+Shift+A` | Archive chat |
| `Ctrl+Alt+Shift+P` | Pin chat |
| `Ctrl+Alt+/` | Search |
| `Ctrl+Shift+F` | Search chat |
| `Ctrl+Alt+N` | New chat |
| `Ctrl+]` | Next chat |
| `Ctrl+[` | Previous chat |
| `Ctrl+Cmd+Shift+L` | Add chat to list |
| `Escape` | Close chat |
| `Ctrl+Shift+N` | New group |
| `Ctrl+Alt+P` | Profile and About |
| `Shift+.` | Increase speed of selected voice message |
| `Shift+,` | Decrease speed of selected voice message |
| `Alt+S` | Settings |
| `Ctrl+Alt+E` | Emoji panel |
| `Ctrl+Alt+G` | GIF panel |
| `Ctrl+Alt+S` | Sticker panel |
| `Alt+K` | Extended search |
| `Alt+L` | Lock app |
| `Alt+I` | Open chat info |
| `Ctrl+Shift+B` | Block chat |
| `Alt+R` | Reply |
| `Ctrl+Alt+R` | Reply privately |
| `Ctrl+Alt+D` | Forward |
| `Alt+8` | Star message |
| `Alt+A` | Open attachment dropdown |
| `Ctrl+Alt+Shift+R` | Start PTT recording |
| `Alt+P` | Pause PTT recording |
| `Ctrl+Enter` | Send PTT |
| `Ctrl+ArrowUp` | Edit last message |
| `Ctrl++` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Zoom reset |
| `Ctrl+1..9` | Open chat |

### Calls

Use these shortcuts while call controls are available. The same key can have a different function in a chat.

| Shortcut | Function |
| --- | --- |
| `Ctrl+Alt+V` | Toggle camera |
| `Ctrl+Alt+M` | Toggle mute |
| `Ctrl+Alt+R` | Reactions |
| `Ctrl+Alt+H` | Raise hand |
| `Ctrl+Alt+S` | Screen share |
| `Ctrl+Alt+W` | End call |

## Updating WhatsApp Web Plus inside Companion

1. Open **NVDA menu > Tools > WhatsApp Companion**.
2. Choose **Check for WhatsApp Web Plus userscript updates**.
3. Wait for NVDA to report the result.
4. Close WhatsApp completely, then launch it through Companion again.

This updates the WhatsApp Web Plus copy used by Companion. To update the Companion add-on itself, install a newer `.nvda-addon` package. If you also use WhatsApp Web Plus in a browser, update that installation separately.

The current source version is **2026.11.07**, including WhatsApp Web Plus **2026.11.01**. Read the [Companion release history](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/changelog.md) for changes.

## Troubleshooting

**WhatsApp is already running:** close it completely, then launch it through Companion. To connect without closing it yourself, turn on **Connect automatically when WhatsApp is opened**.

**WhatsApp cannot be found:** check that the selected Stable or Beta app is installed from Microsoft Store.

**WhatsApp opens but is not ready:** allow time for messages to load. If NVDA reports an error, use **Report the last WhatsApp Companion result** and note the exact message.

**Shortcuts do not work or the connection was lost:** close WhatsApp and launch it again from the Companion menu.

**WebView2 permission problem:** run **Diagnose and repair WebView2 policy permissions** again. If Windows policy or administrator restrictions block the repair, contact your administrator.

Read the [detailed troubleshooting guide](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#troubleshooting) for other messages and recovery steps.

## More help

For a native incoming call, focus the call window with Alt+Tab, then press **Ctrl+Alt+A** to answer or **Ctrl+Alt+D** to decline. Companion requires one visible, enabled pair of Accept and Decline buttons in that window. End call is never treated as Decline. In other applications, in editable fields, or with AltGr, the keys pass through as usual. Secure, locked, and no-write sessions also pass the keys through. Holding or repeating a key does not activate a control again immediately. WhatsApp gives its own feedback about the call result.

For diagnostics, open Input Gestures from WhatsApp and assign a gesture to **Save WhatsApp call diagnostics to the NVDA log**, which has no default shortcut. During a connected call, capture one snapshot. The `controls` part of `WWP-CALL-SNAPSHOT` lists every recognized control without activating it. If needed, capture another snapshot after the microphone or camera changes state or after raising your hand. If a control is not recorded, focus it with Tab, make sure the NVDA navigator is on it, press NVDA+F1, and copy its object information after removing personal details. There is no need to collect NVDA+F1 output for every control in advance.

Diagnostics also list unmapped controls in `controls.unmapped`, including technical IDs, enabled and offscreen states, and whether the Invoke and Toggle patterns are available. Names of unknown controls are left out. The status `complete` means the scan finished, not that every control was recognized. Toggle availability is not an on or off state. Check identifiers before sharing a log, because providers can insert personal data. If the camera, reactions, raise hand, or screen sharing are still not recognized, send one new snapshot first. Actions are never mapped from ID names alone.

**Ctrl+Alt+S** activates Start screen sharing or Stop screen sharing, depending on the available control. You still choose the screen or window and confirm it; nothing is selected automatically. The scan covers the whole call window within node and time limits and uses a per-object UIA property cache to reduce cross-process requests. The identity and state of a control are checked again right before activation. The `propertyCache` log entry shows whether this optimization is available. A partial result is always rejected and never activates a control.

The six active-call shortcuts require the End call control and a unique target in the same window. Built-in labels are in English; add the labels used by your WhatsApp language under **Call control labels**. The React checkbox (NewReactionButton) and Start/Stop screen sharing (NewScreenShareButton) use one TogglePattern activation. Other toggle-only controls are not supported yet. Reactions and screen sharing open WhatsApp's controls, and you make the remaining choices. Try the shortcuts on a test call first. If you use WhatsAppNG, disable it temporarily and restart NVDA so the two app modules do not conflict.

These online guides are optional. You do not need them to complete installation.

[Companion menu commands](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#whatsapp-companion-menu-commands)

[WebView2 permission repair details](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#diagnose-and-repair-webview2-permissions)

[Privacy and security](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#privacy-and-security)

[Developer guide](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#for-developers)

## Remove WhatsApp Companion

Close WhatsApp, open the NVDA Add-on Store, find **WhatsApp Companion** under installed add-ons, and choose **Remove**. Restart NVDA when asked.

This leaves WhatsApp and any browser installation of WhatsApp Web Plus installed. It also leaves the repaired WebView2 permission in place.

## Reporting a problem

Use the [Companion issue tracker](https://github.com/muhammadGagah/whatsapp-web-plus-companion/issues) for launching, connection, NVDA integration, update, or permission repair problems. Include your NVDA and Windows versions, Stable or Beta, the command used, the exact NVDA message, and what happened.

Use the [WhatsApp Web Plus issue tracker](https://github.com/muhammadGagah/whatsapp-web-plus/issues) for shortcuts, message labels, Status reading, Privacy Mode, or settings problems.

Do not include private messages, contact names, or phone numbers.

## Special thanks

I am deeply grateful to the developers whose work helped me build WhatsApp Companion. I learned a great deal from their projects, and each one contributed something to the way this add-on took shape.

[Messenger Accessibility for NVDA](https://github.com/NVDATH/messengerAccess-for-nvda/), by the developers at NVDATH, introduced me to the idea of connecting an NVDA add-on with a userscript through a bridge. It was the first add-on I knew of that took this approach instead of handling everything in Python. Seeing those two parts work together helped me imagine what Companion could become.

[WhatsApp Desktop accessibility enhancements (WhatsAppNG)](https://github.com/nunotfc/WhatsAppNG), by Nuno Costa, was an important reference when I worked on call shortcuts. In the Microsoft Store version of WhatsApp, calls open in a separate native window that the userscript cannot reach. During my testing, shortcuts for ending calls, muting the microphone, and switching the camera did not work there. That led me to implement those controls in Companion itself, and studying WhatsAppNG helped me find my way.

[WhatsAppPlus](https://github.com/Kostya-Gladkiy/WhatsAppPlus), by Kostya Gladkiy, was perhaps my biggest inspiration. Many of the shortcuts and features in this project reflect the experience I appreciated in his add-on. I originally planned to call this add-on WhatsApp Web Plus Companion and had received Kostya's permission to use that name. Later, a friend suggested WhatsApp Companion to avoid confusing users, so that became its name. I am especially thankful to Kostya for his understanding and support.

Finally, I want to thank the developers and contributors behind [Instant Translate](https://github.com/addonFactory/instantTranslate). Although its purpose is different from this project, studying it taught me a great deal about developing NVDA add-ons. Those lessons stayed with me as I worked on Companion.

Thank you all for sharing your work and giving other developers, including me, something to learn from.

## License

Companion uses GPL-2.0-or-later under the modified NVDA license in `COPYING.txt`. The included WhatsApp Web Plus userscript keeps its MIT license. See `THIRD_PARTY_NOTICES.md` for details.
