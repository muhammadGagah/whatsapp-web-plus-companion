# WhatsApp Companion manual validation

The current release is not complete until these checks pass in NVDA 2024.1
32-bit and NVDA 2026.1.1 64-bit using synthetic WhatsApp accounts and synthetic
chat content. Do not collect or share logs from a real account.

## Before each channel

1. Install the current `whatsappWebPlusCompanion-*.nvda-addon` package and
   restart NVDA.
2. Confirm no WhatsApp Companion command has a default gesture.
3. Assign temporary gestures to all seven commands: Stable, Beta,
   selected-channel, force-close, permission diagnosis, last-result, and
   check-update.
4. Close WhatsApp normally. Confirm no WhatsApp or associated WebView2 process
   remains.

## Stable and Beta checks

Repeat the following for Stable and Beta. A Stable failure blocks the current
release and must not be reclassified as Beta-only support.

1. Launch through the assigned NVDA command in Talk mode. Confirm immediate
   speech and braille feedback and that NVDA remains responsive.
2. Repeat in On-demand mode. The immediate script result must speak. After the
   asynchronous operation completes, invoke **Report the last WhatsApp
   Companion result** and confirm that the final result speaks and is brailled.
3. Confirm the package identity, AUMID, registry lease, loopback-only listener,
   process ancestry, one eligible target, direct WebSocket, MAIN-world context,
   embedded hash, and required-node health checks all pass.
4. Start with a synthetic account that remains on **Downloading messages** for
   longer than 15 seconds. Confirm readiness remains `waiting`, the userscript
   creates no menu/status/log nodes, and the Companion does not report active.
   When the connected WhatsApp navigation and chat-list shell appears, confirm
   readiness changes to `ready`, the userscript starts exactly once, and its
   health reports `readyStateAtInstall` as `complete`. Repeat after a controlled
   internal reload; readiness must depend on the observed shell, not elapsed time.
5. Confirm the userscript owns exactly one settings menu, status region, and
   message log. Confirm semantic health reports `pass` for those owned nodes;
   unrelated WhatsApp live regions must not affect health. With no conversation
   open, grid and composer checks must report `notApplicable` without blocking
   activation. Open a populated synthetic conversation with announcement
   reduction enabled and confirm the message grid has one accessible name, one
   tab stop, and one usable focus target. Confirm the composer has an accessible
   name and usable focus target. Repeat with announcement reduction disabled;
   only the message-grid checks may become `notApplicable`.
6. In the signed-out state, confirm readiness remains `waiting` and the add-on
   does not move focus or report active. Complete sign-in, then confirm the
   signed-in shell activates without re-foregrounding WhatsApp or moving focus
   during delayed health completion or reconnect.
7. Trigger a renderer or target replacement. Confirm no reload or focus
   movement, at most three reconnect attempts in 20 seconds, one userscript
   instance, semantic health returning to `pass`, and working keyboard
   navigation afterward.
8. Close WhatsApp normally with `Alt+F4` or its Quit command. Confirm the
   companion does not reconnect, relaunch, or announce a connection failure;
   the worker returns to idle, the next launch is accepted immediately, and
   **Report the last result** says WhatsApp is closed and the companion is not
   active.
9. Reload plugins and exit NVDA during endpoint wait, initial attach, and the
   attached state. Confirm the GUI does not freeze, no stale announcement is
   delivered, the registry value is restored by the worker, and WhatsApp is
   not terminated unless the separate force-close command is explicitly
   confirmed.
10. Confirm rejection while NVDA is elevated, Windows is locked, the secure
   desktop is active, writes are disallowed, or WhatsApp is already running.
   Each result must provide an actionable English and Indonesian message.
11. Inspect any retained diagnostic record before sharing. It may contain only
    channel IDs, booleans, timing, sanitized error codes, versions, and a short
    hash prefix—never DOM, accessibility trees, messages, names, phone numbers,
    cookies, storage, tokens, QR data, target paths, or bundle source.

Repeat the lifecycle checks with portable NVDA. Cover both NVDA 2024.1/Python
3.11 32-bit and NVDA 2026.1.1/Python 3.13 64-bit. Record exact NVDA, Python,
WhatsApp Stable, WhatsApp Beta, WebView2, add-on, and embedded userscript
versions. Preserve only privacy-safe pass/fail evidence.

## NVDA Tools submenu and userscript update check

1. Open NVDA menu > Tools > WhatsApp Companion. Confirm exactly one
   submenu exists after startup and after using Reload plugins three times.
2. Confirm Up/Down moves through all seven commands, Right/Left enters and leaves
   the submenu, Enter activates a command, and Escape closes the menu and
   returns focus to the previously focused application.
3. Confirm all seven submenu actions have matching commands under Input Gestures
   and none has a default global gesture.
4. In Talk and On-demand speech modes, run the update command from both the menu
   and an assigned gesture. Confirm progress and final text appear on braille.
   In On-demand mode, confirm Report last result speaks the saved final result.
5. Test current with an identical digest, current with a different digest,
   newer, older upstream, offline, redirect, slow response, malformed metadata,
   invalid UTF-8, wrong userscript identity, metadata/script version mismatch,
   oversized metadata, and oversized script cases. Confirm NVDA speech,
   braille, keyboard input, and focus never freeze. Every failure must say that
   the existing bundle was not changed.
6. With a newer version available, confirm the command downloads and installs
   it without opening a dialog or browser and without moving focus. Confirm the
   result reports both versions and says the update will be used on the next
   Companion launch. With changed content at the same version, confirm the
   result calls it a refresh and explains why.
7. Inspect the active NVDA configuration directory. Confirm the packaged add-on
   resources remain unchanged, the update store contains a content-addressed
   script, and `bundle-update.json` selects it. Corrupt or remove either update
   file and confirm the next launch safely uses the packaged fallback.
   Separately install a syntactically valid bundle that fails the Companion
   health contract. Confirm the first launch reports that the download was
   disabled, no second bundle is injected into that renderer, and the next
   clean launch uses the packaged fallback.
8. Keep WhatsApp open while updating. Confirm the current session continues to
   use its existing injected script. Fully close WhatsApp, launch it through
   the Companion, and confirm the newly selected version is injected. Install
   a Companion package containing an equal or newer userscript and confirm the
   packaged version takes precedence over the older update store.
9. Deny access or simulate write, flush, replace, and validation failures at
   each commit stage. Confirm the previously selected bundle remains launchable
   and no temporary file is selected. Interrupt the command by reloading plugins
   during metadata download, script download, asset write, and immediately
   before manifest replacement; confirm no stale announcement or partial commit.
10. Activate the command repeatedly during a slow request. Confirm only one
   worker and one terminal result occur. If the request completes before the
   delayed progress message, confirm the terminal result is not followed by a
   stale "Checking" announcement.
11. Confirm the submenu and update command are absent in secure, launcher, and
   no-write NVDA contexts. Confirm no update files are created in those contexts.

## Force-close command

1. Open the force-close command from the Tools submenu and from an assigned
   gesture. Confirm both paths open one confirmation dialog and do not close a
   process before confirmation.
2. Confirm **Keep WhatsApp open** has initial focus. Press `Escape`, `Alt+F4`,
   and the window Close button in separate attempts; each must cancel safely
   and leave WhatsApp running. Repeated activation while the dialog is open
   must raise the existing dialog instead of creating another one.
   Confirm the title is **Force close WhatsApp applications?** and pressing
   `Enter` on the initially focused safe button also cancels.
3. With an active call, file transfer, or unsent text, confirm the warning names
   the possible interruption or loss before **Force close** is chosen.
4. Test Stable only, Beta only, and both channels together, including a visible
   window and background-only instances. Confirm every process belonging to
   the installed Microsoft Store Stable and Beta packages ends, then confirm
   the final spoken and brailled result reports the verified total.
5. Run the command when neither channel is running. Confirm the result says no
   supported WhatsApp process was running and does not imply that anything was
   closed.
6. Keep an unrelated process whose executable name contains `WhatsApp` running
   as a negative control. Confirm it is not closed; matching must remain scoped
   to the exact Stable and Beta package installation directories.
7. Start a Companion launch and immediately confirm force close. Confirm the
   launch is cancelled before process termination, no stale launch or normal
   closure result replaces the force-close result, and a new launch is accepted
   after force close completes.
8. Repeat in Talk and On-demand speech modes. Confirm progress and final output
   are available on braille, and **Report the last WhatsApp Companion
   result** repeats the force-close outcome.
9. Reload plugins or exit NVDA while force close is pending. Confirm NVDA stays
   responsive and no result is announced after the add-on has been disposed.
10. Repeat the entire menu/update workflow with Indonesian NVDA and record the
    exact spoken, brailled, dialog, and focus results.

## Registry permission diagnosis and repair

The current release is not complete until the general gates above and the gates
below pass with the packaged helper (`registryRepair.bat` +
`registryRepair.ps1`, SHA-256 locked in `registry-repair.json`).

### Platform matrix

1. Clean Windows 10 Enterprise LTSC 2019 x64 and LTSC 2021 x64: reproduce the
   default denial, then verify the full diagnosis and repair flow.
2. Windows 11 x64 with normal permissions: diagnosis must report not needed and
   never show UAC.
3. NVDA 2024.1 32-bit and NVDA 2026.1.1 64-bit, each installed and portable,
   English and Indonesian.
4. Administrator account running normally with UAC filtering, and a standard
   user approving UAC with different administrator credentials.

### Permission scenarios

1. Start from the clean-LTSC denial. Launch WhatsApp through the Companion and
   confirm the result names the exact Registry stage (for example
   `registry.user.openCreateAccessDenied`) and directs to the diagnosis
   command; it must not suggest restarting NVDA.
2. Run **Diagnose and repair WebView2 policy permissions**. Confirm exactly one
   announcement **Checking WebView2 policy permissions.** and a read-only
   diagnosis: no Registry value is created, changed, or deleted.
3. When access is already usable, confirm the result says the permissions are
   already available, no changes were made, no dialog opens, and no UAC prompt
   appears.
4. When machine policy controls the channel or wildcard, confirm repair is not
   offered and the administrator guidance is announced in English and
   Indonesian.
5. With WhatsApp running, confirm one dialog explains that all Microsoft Store
   Stable and Beta processes must be force closed, warns about active calls,
   file transfers, and unsent text, and says a separate confirmation is still
   required if repair is needed. Confirm **Keep WhatsApp open** has initial
   focus; Enter on initial focus, Escape, Alt+F4, and window Close leave
   WhatsApp running. Choose **Force close WhatsApp and continue** and confirm
   diagnosis resumes only after every supported process is closed or none are
   found. A partial or failed close must report its result and must not resume
   diagnosis. Repeated activation must not create duplicate dialogs or workers.
6. In secure, locked, no-write, and elevated NVDA contexts, confirm the
   diagnosis reports the context restriction without attempting any change.
7. With a repairable denial, confirm the confirmation dialog announces title,
   dialog role, body, and the focused safe button; **Keep current permissions**
   has initial focus; Enter on initial focus, Escape, Alt+F4, and window Close
   all cancel without UAC; repeated activation raises the single existing
   dialog; Tab and Shift+Tab stay within the two buttons.
8. Confirm the dialog body discloses: key-wide `KEY_SET_VALUE` consequence,
   durability after restart and uninstall, only the helper elevated, machine
   policy and deny rules untouched, no Registry value changes.
9. Choose **Continue to User Account Control**. Confirm **Opening the Windows
   permission request. NVDA itself will remain unelevated.**, then UAC shows
   only the helper. After approval, confirm one final result announces the
   repair and **Report the last WhatsApp Companion result** repeats it
   in speech On-demand mode and on braille.
10. Cancel UAC: confirm **No permission change was made.** and that no DACL or
    value changed.
11. Approve UAC with alternate administrator credentials: confirm the
    requesting user's SID is repaired, not the administrator's `HKEY_CURRENT_USER`.
12. Run the repair twice: the second run must report not needed, with a
    byte-equivalent DACL and no duplicate ACE.
13. Apply an explicit deny ACE for the user: confirm the helper preserves it
    and returns the managed-deny result with administrator guidance.
14. After repair, confirm the only lasting change is the minimum allow ACE on
    the exact leaf; values, value types, owner, group, SACL, inheritance state,
    unrelated allow ACEs, `HKEY_LOCAL_MACHINE`, and all ancestors and siblings
    are unchanged.
15. Restart NVDA and Windows: confirm a normal launch works without another
    repair. Remove the add-on: confirm the ACE remains and the documentation
    predicted this.

### Lease and recovery scenarios

1. Revoke user write permission after the temporary value is written but before
   restoration: confirm the urgent restore result, a retained encrypted
   journal, and that no foreign value is overwritten.
2. Close WhatsApp, run the repair, and confirm the prior WebView2 value is
   restored exactly (recovery-restored result) and the journal is cleared.
3. Exit or reload NVDA after the temporary write: confirm the next launch runs
   journal recovery before applying a new temporary value.
4. Change the value externally during the lease: confirm a conflict result and
   no overwrite.
5. Pre-configure a foreign `--remote-debugging-port` value: confirm the
   Companion does not delete or adopt it.
6. Corrupt or replace the journal with another user's payload: confirm a
   non-destructive failure and no Registry change.

### Helper trust and failure scenarios

1. Delete or modify `registryRepair.bat`/`.ps1` or `registry-repair.json`:
   confirm the add-on refuses to run the helper with the missing or untrusted
   result.
2. Block elevation with application control: confirm the blocked result and
   administrator guidance.
3. Keep UAC open for several minutes: confirm NVDA's GUI stays responsive and
   the helper has a bounded transaction deadline.
4. Reload plugins while the helper is pending: confirm no stale announcement,
   no dead menu binding, and that the helper is not killed.

### Keyboard, speech, and braille

1. Navigate NVDA menu > Tools > WhatsApp Companion entirely by
   keyboard; confirm seven items with correct names and non-conflicting
   mnemonics.
2. Confirm the diagnosis progress and every repair result speak once in Talk
   and On-demand modes and appear in braille.
3. Confirm focus returns to the invoking application after cancellation and is
   not forced to WhatsApp after UAC.
4. Repeat every user-visible flow with Indonesian NVDA and verify terminology,
   pronunciation, mnemonics, and placeholder correctness.

Record exact Windows build, NVDA, Python, WebView2, WhatsApp, add-on, and
userscript versions. Use synthetic WhatsApp accounts and privacy-safe logs
only; retained diagnostics must contain channel IDs, booleans, timing, and
sanitized error codes, never registry data, DACLs, SIDs, usernames, messages,
or browser arguments.
