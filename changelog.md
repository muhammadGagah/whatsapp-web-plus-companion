# WhatsApp Companion changelog

## 2026.08.16

* Renamed the user-visible add-on to **WhatsApp Companion** while preserving the
published package filename, internal add-on ID, source directory, and GitHub
repository so existing installations continue to upgrade in place. The
English and Indonesian guides now include the complete WhatsApp keyboard
shortcut reference directly.
* Added random per-launch session tokens, per-context nonces, and semantic
health validation so a replaced WhatsApp renderer cannot reuse stale Companion
state.
* Hardened speech and braille announcement invalidation across renderer,
language, and Privacy Mode changes so stale queued output is not delivered.
* Updated the verified embedded WhatsApp Web Plus userscript to version 2.6.76.

## 2026.08.14

* Simplified the force-close confirmation title and action button so the dialog
is faster to understand with speech and braille while keeping the safe action
selected by default.
* Reworded computer-policy, Registry coordination, force-close, update, and
permission-request guidance as shorter, more natural sentences in both
English and Indonesian.
* Reorganized the English and Indonesian guides around a beginner-friendly
first-launch workflow, everyday tasks, plain-language explanations, and
optional technical sections.

## 2026.08.13

* The userscript update command now downloads, validates, and atomically selects
newer official bundles or changed content at the same version for the next
Companion launch. Store transactions are serialized, failed runtime health
checks quarantine the downloaded manifest, and the packaged bundle remains a
verified fallback. The separate browser installer command and confirmation
flow have been removed.
* When permission diagnosis finds WhatsApp running, it now offers an accessible
confirmation to force close Store Stable and Beta processes and continue the
diagnosis automatically after a verified close.
* Hardened the WebView2 policy permission repair helper: exact stage error
codes, real effective-access verification, parent-process identity binding
through the process token, and diagnostic logging. Any helper failure is
reported honestly instead of being mistaken for success.

## 2026.08.12

* Added stage-specific Registry error codes so every failed read, write,
restore, or mutex operation reports exactly what happened instead of a
generic restore message.
* Added a read-only WebView2 policy permission diagnosis and a confirmed
**Diagnose and repair WebView2 policy permissions** command that requests
User Account Control approval for a fixed-purpose helper only when needed.
* Added compare-and-restore lease restoration, a DPAPI-protected recovery
journal, and pre-launch recovery so a temporary WebView2 value is never
lost or overwritten after a crash or interrupted restore.
* Restarting NVDA is no longer suggested as a fix for a permission problem.

## 2026.08.11

* Added runtime compatibility for NVDA 2024.1 through 2026.1, covering Python
3.11 32-bit and Python 3.13 64-bit NVDA releases.
* Added separate launch commands for Microsoft Store WhatsApp Stable and Beta.
* Bundled and verified the WhatsApp Web Plus userscript without downloading or
executing remote JavaScript at runtime.
* Added a native WhatsApp Companion submenu under NVDA Tools with the
same seven actions available in Input Gestures.
* Added a confirmed command that force closes verified Microsoft Store WhatsApp
Stable and Beta processes, including instances left running in the background.
* Added a background metadata-only userscript update check and a separate,
confirmed action for opening the fixed official browser installer.
* Added automatic recovery when WhatsApp replaces its renderer.
* Delayed userscript activation until the WhatsApp document, application shell,
navigation, and chat list are structurally ready, without using a fixed
loading delay.
* Treat normal WhatsApp closure as a clean companion shutdown instead of a connection failure.
* Added English and Indonesian messages and beginner instructions.
