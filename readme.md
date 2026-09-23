# WhatsApp Companion

WhatsApp Companion brings WhatsApp Web Plus accessibility features to the Microsoft Store WhatsApp app. It is an NVDA add-on for WhatsApp Stable and WhatsApp Beta on Windows.

You do not need Tampermonkey or any programming knowledge.

## Which version should I use?

- **Microsoft Store app:** use WhatsApp Companion with NVDA.
- **Browser:** use [WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus) with Tampermonkey.

You can use both if you use WhatsApp in both places. Each installation is updated separately.

## What you need

- Windows 10 or Windows 11
- NVDA 2025.1 through NVDA 2026.2
- WhatsApp Stable or WhatsApp Beta from Microsoft Store
- The latest `whatsappWebPlusCompanion-<version>.nvda-addon` package

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

Always launch WhatsApp from the Companion menu when you want its features. Opening WhatsApp from the Start menu does not prepare it for Companion.

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

- **Repeat a message:** choose **Report the last WhatsApp Companion result** if you missed a result or use NVDA speech On-demand mode.
- **Close WhatsApp:** close it normally. If it stays running, use **Force close all Microsoft Store WhatsApp processes**. This can interrupt calls or transfers and lose unsent text.
- **Read a full message:** focus a message and press `Alt + Shift + C` to open it in NVDA's reading window. Press `Escape` to close it.
- **Change settings:** press `Shift + F8` inside WhatsApp.

### Reading messages

Alt+Shift+C opens unwrapped, read-only message text. Up and Down Arrow follow original message lines. Long lines scroll horizontally. Use **Copy message** for plain body text without the reader title or sent time. Use **Formatted view** for wrapped visual reading and clickable links. Escape closes the reader.

### Call control labels

Choose **NVDA menu > Tools > WhatsApp Companion > Call control labels** to add labels for the language used by WhatsApp. You can customize answer, decline, camera, microphone, reactions, raise/lower hand, screen sharing, and end call.

1. Select a **Call action**. The read-only **Built-in labels** field shows labels already recognized.
2. Enter **Additional labels**, one exact control name per line, as spoken by NVDA. Do not include the role or state announcements, such as "button" or "not checked". For toggles, include both states, such as the labels for muting and unmuting the microphone.
3. Select other actions to edit their labels, then choose **Save** to apply all changes immediately. No restart is needed. Choose **Cancel** to discard your edits.

You can add labels in several languages at once. There is no need to choose a language. Built-in labels remain active. Each action accepts up to 20 additional labels, with at most 128 characters per label. A label cannot be assigned to different actions. Microphone labels also apply to the compact call view. Include the **End call** label in your language so Companion can recognize the call window.

Leave a field blank to use the built-in labels. To remove all your custom labels, choose **Reset all additional labels**, then **Save**. Choose **Cancel** to keep your saved labels.

Your labels are saved in your NVDA settings and shared by WhatsApp Stable and Beta across profiles. They remain available after updating or reinstalling Companion, as long as you keep your NVDA settings. Resetting or deleting those settings also removes your saved labels.

### Call shortcuts

See the [full shortcut list](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#whatsapp-keyboard-shortcuts) for navigation, incoming calls, and optional features.

Use these shortcuts while the WhatsApp call window is active. Press `Alt + Tab` to switch to it if needed.

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

If a shortcut opens the full call window from the small call view, release the keys and press the shortcut again to perform the action. If the full window does not open, open it manually and try again.

The reactions shortcut opens WhatsApp's reaction controls. Choose the reaction you want to send. When starting screen sharing, choose what to share in WhatsApp. Press `Ctrl + Alt + S` again to stop sharing.

## Assigning shortcuts

Choose **Shift+F8 > Shortcut remapping**, then select **Record voice message**, **Previous chat**, **Next chat**, **Start voice call**, or **Start video call**. Type a combination such as `Alt+C` or `Alt+V`, then choose **Save**. Use Ctrl or Alt, optionally Shift, followed by a letter, digit, punctuation key such as comma or period, F1–F12, or ArrowUp/Down/Left/Right. Letters refer to physical keyboard positions. Leave the field blank to disable an action. **Restore default** only changes the field. Choose Save to apply or Cancel/Escape to discard. Existing enabled/disabled remaps are preserved. New call shortcuts start unassigned. The recording default is Alt+M. Previous/next defaults are Alt+ArrowUp/Alt+ArrowDown, initially disabled.

Duplicate assignments and fixed script/Companion commands are rejected. Browser, system, NVDA, or extension shortcuts can still take priority. AltGr is not supported. Voice/video calls use the available button in the current conversation header, identified by its icon rather than translated text. No custom language string is required. Unavailable or ambiguous buttons are reported without starting a call.

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
| `Enter / Space` | Play or pause the focused voice message when the optional keyboard playback setting is enabled (off by default) |

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

## Troubleshooting

- **WhatsApp is already running:** close it completely, then launch it through Companion.
- **WhatsApp cannot be found:** check that the selected Stable or Beta app is installed from Microsoft Store.
- **WhatsApp opens but is not ready:** allow time for messages to load. If NVDA reports an error, use **Report the last WhatsApp Companion result** and note the exact message.
- **Shortcuts do not work or the connection was lost:** close WhatsApp and launch it again from the Companion menu.
- **WebView2 permission problem:** run **Diagnose and repair WebView2 policy permissions** again. If Windows policy or administrator restrictions block the repair, contact your administrator.

Read the [detailed troubleshooting guide](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#troubleshooting) for other messages and recovery steps.

## More help

These online guides are optional. You do not need them to complete installation.

- [Companion menu commands](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#whatsapp-companion-menu-commands)
- [WebView2 permission repair details](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#diagnose-and-repair-webview2-permissions)
- [Privacy and security](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#privacy-and-security)
- [Developer guide](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.md#for-developers)

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
