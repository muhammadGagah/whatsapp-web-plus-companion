# WhatsApp Companion detailed guide

[Back to the installation guide](../readme.md). This guide covers everyday commands, troubleshooting, security, and development.

## Everyday use

### Start WhatsApp

Always start the supported WhatsApp app from the Companion submenu. If you use
only one WhatsApp channel, you can later assign a keyboard gesture to its
launch command.

### Stop WhatsApp

Close WhatsApp normally. Do not run the launch command again to stop it.

If WhatsApp stays open in the background, use **Force close all Microsoft Store
WhatsApp processes**. The Companion asks for confirmation because force
closing WhatsApp can interrupt calls and file transfers. Text that you have not
sent may also be lost.

### Hear the last result again

Use **Report the last WhatsApp Companion result** if you missed a
message or use NVDA speech On-demand mode. This command repeats the latest
launch, connection, closure, repair, or update result.

## WhatsApp Companion menu commands

Open the NVDA menu, choose **Tools**, then choose **WhatsApp Companion**. Use
the arrow keys to move, `Enter` to run a command, and `Escape` to close the
menu.

### Launch commands

- **Launch WhatsApp Stable with WhatsApp Companion** starts the
  Microsoft Store Stable app.
- **Launch WhatsApp Beta with WhatsApp Companion** starts the
  Microsoft Store Beta app.
- **Launch the last selected WhatsApp channel with WhatsApp Companion**
  repeats the Stable or Beta choice that you used most recently.

WhatsApp Stable and WhatsApp Beta are separate Microsoft Store apps. You may
install either one or both.

### Recovery commands

- **Force close all Microsoft Store WhatsApp processes** closes every running
  Stable and Beta process after you confirm the warning. Use it only when
  WhatsApp did not close normally.
- **Diagnose and repair WebView2 policy permissions** checks a Windows
  permission that the Companion needs. Run it after your first installation on
  this computer, before launching WhatsApp. Run it again if that permission is
  removed or Windows is reinstalled, or if Companion reports a permission problem.

### Result and update commands

- **Report the last WhatsApp Companion result** repeats the most
  recent result.
- **Check for WhatsApp Web Plus userscript updates** checks the fixed official
  source. If it finds a newer or changed copy that passes its checks, it installs
  that copy for the next Companion launch. It does not open a browser.

## Assign an optional keyboard gesture

The Companion's global commands, such as launching WhatsApp and reporting the
last result, have no default keyboard gestures. You can assign gestures that
fit your setup. Native call commands have the default shortcuts listed below.

To add your own gesture:

1. Open the NVDA menu.
2. Choose **Preferences**, then **Input Gestures**.
3. Type `WhatsApp Companion` in the filter box.
4. Expand the **WhatsApp Companion** category.
5. Select a command.
6. Choose **Add**, press the gesture that you want, and confirm the dialog.

A simple setup is one gesture for your usual launch command and one for
**Report the last WhatsApp Companion result**.

To assign a call gesture, focus WhatsApp before opening **Input Gestures**.
Call commands appear in the **WhatsApp Companion** category only when the
dialog is opened from WhatsApp. Reassign any custom call gestures from earlier
versions because these commands have moved to the WhatsApp app module.

## WhatsApp keyboard shortcuts

The Companion starts and connects WhatsApp, provides native call shortcuts, and
opens messages in NVDA's reading window. Navigation and optional features
inside WhatsApp come from the WhatsApp Web Plus userscript.

You can use WhatsApp without memorizing these shortcuts. Learn only the ones
you need.

### Move around WhatsApp

| Shortcut | Action |
| --- | --- |
| `Alt + Shift + 1` | Open Chats |
| `Alt + Shift + 2` | Open Status or Updates |
| `Alt + Shift + 3` | Open Communities |
| `Alt + Shift + 4` | Open Channels |
| `Alt + Shift + 5` | Open Meta AI |
| `Alt + Shift + D` | Move between the message history and message writing area |
| `Alt + 1` | Move to the chat list |
| `Alt + 2` | Move to the latest message |
| `Alt + 3` | Move to the first unread message |
| `Alt + Up Arrow` | Open the previous chat when enabled in Shortcut remapping |
| `Alt + Down Arrow` | Open the next chat when enabled in Shortcut remapping |
| `Alt + T` | Read the current chat title. Press twice quickly to turn Chat activity monitor on or off |
| `Alt + 0` | Close the open WhatsApp audio or video player, or dismiss the desktop app promotion |
| `Alt + M` | Start recording a voice message when enabled in Shortcut remapping |

### Incoming call controls

These shortcuts work only while an incoming voice or video call is ringing and
WhatsApp is showing its **Accept** and **Decline** buttons. They press those
same buttons for you. If a shortcut does nothing, move to the buttons and press
them directly.

| Shortcut | Action |
| --- | --- |
| `Ctrl + Alt + A` | Accept the incoming voice or video call |
| `Ctrl + Alt + D` | Decline the incoming voice or video call |

For a native incoming call, focus the call window with Alt+Tab before using
these shortcuts. Companion needs one visible, enabled pair of Accept and
Decline buttons in that window.

### Active call controls

During a connected call, use these shortcuts in the call window:

| Shortcut | Action |
| --- | --- |
| Ctrl+Alt+V | Turn the camera on or off |
| Ctrl+Alt+M | Mute or unmute the microphone |
| Ctrl+Alt+R | Open reactions |
| Ctrl+Alt+H | Raise or lower your hand |
| Ctrl+Alt+S | Start or stop screen sharing |
| Ctrl+Alt+W | End the call |

Reactions and screen sharing open WhatsApp's controls. You choose the reaction
or the screen to share. If a shortcut restores the full call view from the
compact view, release the keys, check the view, then press the shortcut again
to perform the action.

Use **NVDA menu > Tools > WhatsApp Companion > Call control labels** to add
labels for your WhatsApp language. Enter one exact control name per line, as
spoken by NVDA, without its role or state. Built-in labels remain active.

### Optional features

| Shortcut | Action |
| --- | --- |
| `Alt + Shift + N` | Turn Privacy Mode on or off |
| `Alt + Shift + L` | Turn Automatic reading of messages on or off |
| `Shift + F8` | Open or close WhatsApp Web Plus settings |
| `Alt + Shift + 8` | Turn Clean UI on or off |
| `Alt + Shift + 9` | Turn Original Dark Mode on or off |

Your optional feature choices are remembered after WhatsApp reloads.

### More WhatsApp Web Plus help

- [First use of WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#first-use)
  gives a guided introduction.
- [WhatsApp Web Plus settings menu](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#settings-menu)
  explains the `Shift+F8` menu.
- [Privacy Mode](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#what-each-setting-does)
  explains what is hidden when privacy filtering is enabled.
- [Opening a message context menu with NVDA](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#open-a-message-context-menu-with-nvda)
  explains the keyboard and NVDA mouse methods.

## Update the built-in WhatsApp Web Plus copy

Run **Check for WhatsApp Web Plus userscript updates** when you want the
Companion to check for a newer WhatsApp Web Plus copy.

The command works in the background:

1. The Companion contacts the fixed official Greasy Fork address.
2. It checks the version and file details.
3. If a newer version is available, it downloads and validates it, including
   signature verification with trusted Ed25519 keys.
4. If the official content changed without a version change, it validates and
   refreshes that copy.
5. NVDA tells you whether the copy was current, updated, refreshed, or left
   unchanged because of an error.

The update applies the next time you launch WhatsApp through the Companion. It
does not replace code that is already running. Close WhatsApp completely and
launch it again to use the new copy.

This command updates only the Companion copy. A browser copy installed through
Tampermonkey or another userscript manager must be updated in the browser.

The Companion keeps its packaged copy as a safe fallback. If a downloaded copy
is damaged, incomplete, older, or fails its startup check, the Companion uses
the packaged copy on a later launch.

## Diagnose and repair WebView2 permissions

Run **Diagnose and repair WebView2 policy permissions** after installing
Companion for the first time on this computer, before launching WhatsApp.
If the permission already works, no repair is needed. The permission remains
until it is removed from the Registry or Windows is reinstalled. Updates to
NVDA, Companion, and WhatsApp normally do not require another repair.

The following details explain what the command checks and changes.

### What is being checked?

Before it starts WhatsApp, the Companion writes a small temporary setting in
the Windows Registry. The Registry is a Windows settings database. The
Companion removes its temporary setting after it connects.

Some computers protect this location so that NVDA cannot write the setting.
Restarting NVDA does not change this permission. The diagnosis command checks
the permission without changing anything.

### What happens when I run the command?

1. The Companion checks whether Windows allows the required Registry access.
2. If WhatsApp is running, the Companion offers to force close Stable and Beta
   and continue the diagnosis. **Keep WhatsApp open** is the safe default.
3. If the permission already works, NVDA says that no repair is needed.
4. If a repair may help, a separate dialog explains the change.
5. Only after you agree does Windows show a User Account Control prompt.

Closing WhatsApp does not approve the permission repair. These are two separate
decisions. The Companion never runs NVDA or WhatsApp as administrator.

### What does the repair change?

The repair gives your Windows account permission to read and update one
WebView2 policy key. A policy key is a Registry location used for application
settings.

The repair does not change a Registry value. It does not change a computer-wide
policy, remove an administrator deny rule, take ownership, or touch
`HKEY_LOCAL_MACHINE`.

Windows grants permission to the whole key, not to one value inside it. As a
result, programs running under your Windows account can change other values in
that WebView2 policy key. The dialog explains this before you approve the
repair.

The permission remains after NVDA or Windows restarts and after the add-on is
removed. Only an administrator can change it later. The exact location is:

`HKEY_CURRENT_USER\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments`

Contact your administrator if a Windows policy, a deny rule, or insufficient
administrator rights prevents the repair.

## Privacy and security

You can skip this section during everyday use. It explains how the Companion
limits its access to WhatsApp.

- The Companion works only with the supported Microsoft Store WhatsApp Stable
  and Beta apps.
- Its temporary connection stays on your computer and is limited to the
  WhatsApp app that the Companion started.
- It connects only to the expected internal WhatsApp page.
- It does not send chats, contacts, or WhatsApp session data to the update
  service.
- It downloads JavaScript only after you run the update command and only from
  the fixed official Greasy Fork addresses.
- It checks the userscript identity, version, addresses, permission mode,
  SHA-256 fingerprint, and file size before selecting a download.
- The userscript packaged inside the add-on is never overwritten.
- The temporary Windows launch setting is removed after the local connection
  is ready.
- The permission repair runs only after a separate confirmation and Windows
  approval.

Updates use HTTPS and signed userscript verification with trusted Ed25519
keys. If signature verification fails or is unavailable, Companion keeps the
existing bundle unchanged.

Developer and reviewer information about the packaged userscript appears in
`upstream.json`, `bundle.json`, and `THIRD_PARTY_NOTICES.md`.

## How the Companion works

This section is optional. You do not need it to operate the add-on.

For each launch, the Companion:

1. Checks that Windows is unlocked and NVDA is running normally.
2. Checks that the selected Microsoft Store WhatsApp app is installed and
   closed.
3. Creates a temporary connection that is available only on your computer.
4. Starts WhatsApp and confirms that it connected to the correct app.
5. Removes the temporary launch setting.
6. Waits until the WhatsApp navigation and chat list are ready.
7. Loads and verifies the WhatsApp Web Plus copy.
8. Reconnects automatically if the internal WhatsApp page reloads.

This work happens in the background so the NVDA interface stays responsive.
NVDA continues to read normal WhatsApp controls, menus, dialogs, and focus.
The Companion passes only selected WhatsApp Web Plus announcements to speech
and braille and discards announcements that no longer match the current chat,
language, privacy setting, or session.

## Troubleshooting

### NVDA says WhatsApp is already running

Close WhatsApp normally. If it remains in the notification area, use the
WhatsApp **Quit** or **Exit** command. If it still does not close, use **Force
close all Microsoft Store WhatsApp processes** from the Companion submenu.

### The selected WhatsApp channel was not found

Install the correct app from Microsoft Store. WhatsApp Stable and WhatsApp Beta
are separate apps. Installing one does not install the other.

### The Companion cannot run in the current context

Unlock Windows and run NVDA normally. Do not run NVDA as administrator. The
Companion does not operate on the secure desktop, from a locked Windows
session, or in a read-only NVDA configuration.

### WhatsApp opened but the Companion did not become ready

Wait for NVDA to confirm that WhatsApp is running with the Companion. Loading
may take longer while WhatsApp downloads messages. If NVDA reports an error,
run **Report the last WhatsApp Companion result** and note the exact
message.

### WhatsApp is ready but does not have focus

Press `Alt+Tab` once to move to WhatsApp.

### WhatsApp Web Plus commands do not work

Make sure you launched WhatsApp from the Companion submenu, not from the Start
menu. Run **Report the last WhatsApp Companion result** and check that
the latest launch succeeded. Then read
[WhatsApp keyboard shortcuts](#whatsapp-keyboard-shortcuts) for current
commands and optional remapping.

### NVDA says the connection was lost

Close WhatsApp completely and launch it again through the Companion. The
Companion normally recovers a simple internal page reload automatically. This
error means that repeated reconnection attempts did not restore a valid
session.

### NVDA reports a WebView2 permission problem

Run **Diagnose and repair WebView2 policy permissions** and follow the spoken
instructions. The diagnosis does not change anything. If a computer policy or
administrator deny rule is responsible, contact your administrator.

### The repair helper is missing or not trusted

Install the Companion again from a trusted package. The Companion checks the
repair helper before it runs and rejects a file that does not match the
packaged record.

### The repair could not restore the previous setting

Do not launch WhatsApp through the Companion. Ask an administrator to review
the per-user WebView2 policy key shown in the permission section before trying
again.

### A background result was not spoken

NVDA speech On-demand mode may suppress background speech. Run **Report the
last WhatsApp Companion result**. Braille output remains available
according to your NVDA settings.

### An update failed

The Companion keeps using the currently selected copy that passed its checks.
Check your internet connection and try the update command again later. A failed
update leaves the packaged copy intact.

## Remove the Companion

1. Close WhatsApp.
2. Open NVDA Add-on Store.
3. Find **WhatsApp Companion** under installed add-ons.
4. Choose **Remove**, then restart NVDA when asked.

Removing the Companion does not remove WhatsApp or a separate browser
userscript. It also does not remove a WebView2 permission added by the permission
repair. An administrator must change that permission.

## Plain-language glossary

- **Add-on:** A small program that adds features to NVDA.
- **Userscript:** A small JavaScript program that changes how a web page works.
  WhatsApp Web Plus is a userscript.
- **Browser userscript manager:** A browser extension such as Tampermonkey that
  runs userscripts in a browser. The Companion does not need one.
- **WhatsApp channel:** Either the Stable app or the Beta app from Microsoft
  Store.
- **Registry:** A Windows settings database.
- **Policy key:** A Registry location used for application or administrator
  settings.
- **WebView2:** A Windows component that WhatsApp Desktop uses to display its
  interface.
- **Bundle or built-in copy:** The WhatsApp Web Plus JavaScript copy selected
  by the Companion.
- **SHA-256:** A file fingerprint used to check that file content matches an
  expected record.
- **Administrator or elevated:** A program running with extra Windows rights.
- **Renderer:** The internal page that draws the WhatsApp interface.
- **Announcement:** A short message spoken by NVDA or shown on braille.

## For developers

This section is not needed for normal installation or use.

The repository uses the
[official NV Access Add-on Template](https://github.com/nvaccess/AddonTemplate).
Python files use tabs, LF line endings, and a maximum line length of 110
characters.

Install the locked development environment:

```powershell
uv sync
```

Synchronize the exact built userscript from the sibling source repository:

```powershell
npm run sync:userscript
```

Run linting, tests, translated documentation generation, and packaging:

```powershell
npm test
```

Run all official template hooks:

```powershell
$env:PREK_SKIP = "no-commit-to-branch"
uv run prek run --all-files
```

Pyright is optional. It requires prepared NVDA source in `../nvda/source`:

```powershell
uv sync --group typecheck
uv run pyright
```

The permission repair helper is packaged as `registryRepair.ps1` and
`registryRepair.bat`. Its SHA-256 record is stored in
`resources/registry-repair.json`. Regenerate that record after changing either
helper file.

Before release, verify `upstream.json`, synchronize the userscript, run the
full tests, build the `.nvda-addon` package, install it, and complete the required
manual NVDA and WhatsApp tests.

Generated HTML help, translated manifests, compiled message catalogs, SCons
state, and `.nvda-addon` packages must be produced by the build and must not be
edited manually.

## Get help or report a problem

Report launch, connection, update, repair, or NVDA integration problems in the
[WhatsApp Companion issue tracker](https://github.com/muhammadGagah/whatsapp-web-plus-companion/issues).

Report WhatsApp shortcut, label, Status reading, privacy filtering, or
userscript setting problems in the
[WhatsApp Web Plus issue tracker](https://github.com/muhammadGagah/whatsapp-web-plus/issues).

Include your NVDA version, WhatsApp channel, Windows version, command used,
exact NVDA message, and what happened. Do not include private chat text,
contact names, or phone numbers.

## Read a message in NVDA

When WhatsApp is launched through Companion, focus a message and press
**Alt+Shift+C**. Companion opens the complete message in NVDA's browseable text
window, including links, lists, and its sent time. A shortened message is expanded
first. This avoids the desktop app's unsupported browser pop-up.

Press **Escape** to close the reader. Close and Copy buttons are included when
supported by your NVDA version. The message is not also queued for a separate
speech or braille announcement. In an ordinary browser, the same shortcut still
opens the existing reader tab.

Keep WhatsApp in the foreground while the message loads. Switching applications,
changing the chat, or locking Windows cancels stale requests. If a message exceeds
the reader's size limit, you get an error instead of text cut short without warning.
Update Companion and restart WhatsApp through it to load the bundled reader.

## License

The Companion add-on uses GPL-2.0-or-later under the modified NVDA license in
`COPYING.txt`. The embedded WhatsApp Web Plus userscript keeps its MIT license.
Component sources and license boundaries are described in
`THIRD_PARTY_NOTICES.md`.
