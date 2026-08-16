# WhatsApp Companion

WhatsApp Companion is an NVDA add-on for the Microsoft Store versions of
WhatsApp Stable and WhatsApp Beta. It brings the keyboard commands and
screen-reader improvements from WhatsApp Web Plus into the WhatsApp desktop
application.

The Companion is designed for people who use NVDA with speech or braille. You
do not need to understand JavaScript, the Windows Registry, or browser developer
tools to use it.

This guide starts with the steps most people need. Technical and security
details appear later and are clearly marked as optional reading.

When NVDA uses Indonesian, the Help button in Add-on Manager opens the
Indonesian version of this guide.

## Start here: which project do you need?

First decide where you use WhatsApp.

- If you use WhatsApp Web in Chrome, Edge, or another browser, use
  [WhatsApp Web Plus for browsers](https://github.com/muhammadGagah/whatsapp-web-plus).
  You will also need a browser userscript manager such as Tampermonkey.
- If you use WhatsApp Stable or WhatsApp Beta installed from Microsoft Store,
  use this Companion add-on. You do not need Tampermonkey for the desktop app.

You may use both projects if you use WhatsApp in both places. They are updated
separately.

In simple terms, WhatsApp Web Plus contains the accessibility features. The
Companion starts the desktop WhatsApp app, loads a checked copy of WhatsApp Web
Plus, and passes selected messages to NVDA.

## What you need

Before installing the Companion, make sure you have:

- Windows 10 or Windows 11.
- NVDA 2024.1 through NVDA 2026.1.
- WhatsApp Stable, WhatsApp Beta, or both from Microsoft Store.
- The latest file named
  `whatsappWebPlusCompanion-<version>.nvda-addon`.

Normal use does not require administrator rights. Windows asks for
administrator approval only if you choose an optional permission repair that
is explained later in this guide.

## Install or upgrade the Companion

1. Close WhatsApp completely.
2. If WhatsApp is still in the notification area, use its **Quit** or **Exit**
   command.
3. Open the downloaded `.nvda-addon` file.
4. Check the add-on name and version, then confirm the installation or upgrade.
5. Restart NVDA when it asks.
6. Keep WhatsApp closed until you launch it through the Companion.

Installing a newer Companion package replaces the older Companion add-on and
its built-in WhatsApp Web Plus copy. It does not change a WhatsApp Web Plus
userscript that you installed separately in a browser.

The visible add-on name is now **WhatsApp Companion**. Its package filename,
internal add-on ID, installation folder, and GitHub repository retain the
`whatsappWebPlusCompanion` or `whatsapp-web-plus-companion` name so existing
installations continue to upgrade in place.

## Launch WhatsApp for the first time

1. Make sure WhatsApp is closed.
2. Press `NVDA+N` to open the NVDA menu.
3. Choose **Tools**.
4. Choose **WhatsApp Companion**.
5. Choose **Launch WhatsApp Stable with WhatsApp Companion** or
   **Launch WhatsApp Beta with WhatsApp Companion**.
6. NVDA says that WhatsApp is launching. Wait until NVDA confirms that
   WhatsApp is running with the Companion.
7. If WhatsApp opens without receiving focus, press `Alt+Tab` once.

After that confirmation, use the commands in
[WhatsApp keyboard shortcuts](#whatsapp-keyboard-shortcuts).

Do not open WhatsApp from the Start menu when you want to use the Companion.
The Companion must prepare a temporary local setting before WhatsApp starts.

### What should happen?

- WhatsApp opens normally.
- NVDA remains responsive while the Companion works in the background.
- The Companion waits if WhatsApp is still loading or downloading messages.
- NVDA confirms when WhatsApp and WhatsApp Web Plus are ready.
- The regular WhatsApp interface is still read by NVDA in the usual way.

If this does not happen, read the
[Troubleshooting](#troubleshooting) section.

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

Use **Report the last WhatsApp Companion result** when you missed a
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
  normal closing did not work.
- **Diagnose and repair WebView2 policy permissions** checks a Windows
  permission that the Companion needs. Most users never need this command. Run
  it only when the Companion asks you to or when the related troubleshooting
  section tells you to.

### Result and update commands

- **Report the last WhatsApp Companion result** repeats the most
  recent result.
- **Check for WhatsApp Web Plus userscript updates** checks the fixed official
  source. If it finds a newer or changed valid copy, it installs that copy for
  the next Companion launch. It does not open a browser.

## Assign an optional keyboard gesture

The Companion has no default keyboard gestures. This avoids conflicts with
NVDA, Windows, WhatsApp, and other add-ons.

To add your own gesture:

1. Open the NVDA menu.
2. Choose **Preferences**, then **Input Gestures**.
3. Type `WhatsApp Companion` in the filter box.
4. Expand the **WhatsApp Companion** category.
5. Select a command.
6. Choose **Add**, press the gesture that you want, and confirm the dialog.

A simple setup is one gesture for your usual launch command and one for
**Report the last WhatsApp Companion result**.

## WhatsApp keyboard shortcuts

The Companion only starts and connects WhatsApp. The commands that you use
inside WhatsApp belong to the main WhatsApp Web Plus project.

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
| `Alt + T` | Read the current chat title; press twice quickly to turn Chat activity monitor on or off |
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

- [First use of WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus#first-use)
  gives a guided introduction.
- [WhatsApp Web Plus settings menu](https://github.com/muhammadGagah/whatsapp-web-plus#settings-menu)
  explains the `Shift+F8` menu.
- [Privacy Mode](https://github.com/muhammadGagah/whatsapp-web-plus#what-each-setting-does)
  explains what is hidden when privacy filtering is enabled.
- [Opening a message context menu with NVDA](https://github.com/muhammadGagah/whatsapp-web-plus#open-a-message-context-menu-with-nvda)
  explains the keyboard and NVDA mouse methods.

## Update the built-in WhatsApp Web Plus copy

Run **Check for WhatsApp Web Plus userscript updates** when you want the
Companion to check for a newer WhatsApp Web Plus copy.

The command works in the background:

1. The Companion contacts the fixed official Greasy Fork address.
2. It checks the version and file details.
3. If a newer version is available, it downloads and validates it.
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

Most users can skip this section. Use it only when the Companion reports a
WebView2 permission problem.

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

### What does the optional repair change?

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

You may skip this section during normal use. It explains the limits that keep
the Companion focused on WhatsApp.

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

The update source uses HTTPS and a fixed Greasy Fork account. It does not
currently provide a separate publisher signature. Running the update command
means that you trust that account and service to provide executable code. File
checks and safe storage can detect damaged or unexpected content, but they
cannot prove the publisher's identity if the upstream account or service is
taken over.

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

The currently selected valid copy remains in use. Check your internet
connection and try the update command again later. A failed update does not
partly replace the packaged copy.

## Remove the Companion

1. Close WhatsApp.
2. Open NVDA Add-on Store.
3. Find **WhatsApp Companion** under installed add-ons.
4. Choose **Remove**, then restart NVDA when asked.

Removing the Companion does not remove WhatsApp or a separate browser
userscript. It also does not remove a WebView2 permission added by the optional
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
full tests, build the `.nvda-addon` package, install it, and complete the manual
NVDA and WhatsApp test gates.

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

## License

The Companion add-on uses GPL-2.0-or-later under the modified NVDA license in
`COPYING.txt`. The embedded WhatsApp Web Plus userscript keeps its MIT license.
Component sources and license boundaries are described in
`THIRD_PARTY_NOTICES.md`.
