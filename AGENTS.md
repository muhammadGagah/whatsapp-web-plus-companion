# WhatsApp Companion — agent guide

This repository contains the NVDA companion add-on. The maintained JavaScript
source lives in the sibling `whatsapp-web-plus` repository. The embedded bundle
must match the canonical userscript update URL, version, and SHA-256 recorded in
`upstream.json`.

## Accessibility first

Users are blind or visually impaired. Judge every change by what NVDA speaks
and brailles, whether commands remain usable in speech On-demand mode, and
where keyboard focus lands. Never perform blocking network, process, registry,
or Chrome DevTools Protocol work on NVDA's GUI thread.

Use **WhatsApp Companion** for every user-visible add-on name: the manifest,
Input Gestures category, commands, lifecycle messages, and help. Keep the
published repository name, package filename, source directory, and
`addon_name="whatsappWebPlusCompanion"` unchanged so existing installations
continue to upgrade in place. Use **WhatsApp Web Plus userscript** only for the
embedded upstream JavaScript project.

## Repository layout

- `addon/globalPlugins/whatsappWebPlusCompanion/` — maintained add-on source.
- `addon/locale/{en,id}/` — localized strings; keep catalogs in parity.
- `readme.md` — English help source and repository README.
- `addon/doc/id/readme.md` — Indonesian help source.
- `addon/doc/**/readme.html` — generated help; never edit directly.
- `scripts/sync-userscript.mjs` — imports the exact upstream bundle.
- `upstream.json` — version and SHA-256 lock for the embedded userscript.
- `tests/` — standard-library tests and manual validation gates.
- `site_scons/`, `sconstruct`, templates, `prek.toml`, and `uv.lock` — official
  NV Access Add-on Template infrastructure. Do not replace them with custom
  build logic when `buildVars.py` can express the requirement.

## Formatting

Follow the official template configuration in `pyproject.toml`. Python uses
tabs, LF line endings, and a 110-character line length. Run Ruff rather than
manually reformatting around the template.

## Commands

Synchronize and verify the embedded userscript from the sibling repository:

```powershell
npm run sync:userscript
```

Run Python tests, Ruff lint and format checks, then build the add-on:

```powershell
npm test
```

Run the complete official template hook set:

```powershell
$env:PREK_SKIP = "no-commit-to-branch"
uv run prek run --all-files
```

Pyright is an optional local check that requires prepared NVDA source at
`../nvda/source`. Install it with `uv sync --group typecheck`, then run
`uv run pyright`; it is not a clean-checkout release gate until committed NVDA
and wx stubs are available.

Remove generated manifests, compiled translations, SCons state, generated
English help, and add-on package outputs:

```powershell
uv run scons -c
```

Before a public release, confirm the canonical userscript update URL, version,
and SHA-256 in `upstream.json`, synchronize again, run all automated checks, and
complete every installed-NVDA manual gate.
