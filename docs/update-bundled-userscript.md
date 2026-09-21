# Bundle the published WhatsApp Web Plus release

[Panduan Bahasa Indonesia](update-bundled-userscript.id.md)

For a Companion release, download the published userscript from GreasyFork, verify it, and copy that exact file into the local add-on project. This keeps the packaged bundle consistent with the signed online release.

A local build can have the same version and code but different metadata formatting. GreasyFork may change spacing and the order of `@downloadURL` and `@updateURL`. That changes the hash and can cause Companion to report that it refreshed the same version.

## 1. Finish publishing the userscript first

Publish the userscript and its signed manifest and signature using `docs/RELEASE-SIGNING-CHEATSHEET.md` in the script project. Wait until all three public files match the intended release.

**There is no userscript build step in this guide.** If you already built and published the release, continue below. If source changes are still unpublished, finish that release first.

You need Node.js/npm, the Companion build dependencies including `uv`, and the trusted `update-public-key.pem` in the script project. Use the established release key. Confirm that its fingerprint and key ID match an active or transition key in Companion's `addon/globalPlugins/whatsappWebPlusCompanion/resources/update-public-keys.json`, within that key's permitted sequence range. Do not download a replacement key just to make verification pass. A key change requires the separate key rotation process.

## 2. Set paths and the intended release

Use the same PowerShell terminal for all steps. All local paths below are examples. The projects can be located anywhere. Replace the expected version and sequence with the release you intend to package. They prevent an old but valid public release from being accepted accidentally.

```powershell
$scriptRoot = 'D:\whatsapp\whatsapp-web-plus'
$companionRoot = 'D:\whatsapp\whatsapp-web-plus-companion'
$expectedVersion = '2.6.83'
$expectedSequence = 2026092101
```

The download URLs in the next block are the official project URLs, not example local paths. A fork requires coordinated publishing and verification changes.

## 3. Download, verify, and synchronize

Paste the whole block below into PowerShell. If it ends with an empty `>>` prompt, press Enter once more. Stop if any command reports an error.

The block downloads into a new temporary folder and verifies the signature, version, hash, and size before updating `upstream.json`. It then copies the downloaded file into Companion. It does not rebuild or overwrite the script project's local userscript.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $stage = Join-Path $env:TEMP ('wwp-bundle-' + [guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $stage
    $assetPath = Join-Path $stage 'whatsapp_web_plus.user.js'
    $manifestPath = Join-Path $stage 'update-manifest.json'
    $signaturePath = Join-Path $stage 'update-manifest.json.sig'
    $publicKeyPath = Join-Path $scriptRoot 'update-public-key.pem'
    $rawBase = 'https://raw.githubusercontent.com/muhammadGagah/whatsapp-web-plus/main'
    $downloadUrl = 'https://update.greasyfork.org/scripts/587557/WhatsApp%20Web%20Plus.user.js'

    Invoke-WebRequest -UseBasicParsing -Uri "$rawBase/update-manifest.json" -Headers @{ 'Cache-Control' = 'no-cache' } -OutFile $manifestPath
    Invoke-WebRequest -UseBasicParsing -Uri "$rawBase/update-manifest.json.sig" -Headers @{ 'Cache-Control' = 'no-cache' } -OutFile $signaturePath
    Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -Headers @{ 'Cache-Control' = 'no-cache' } -OutFile $assetPath

    node "$scriptRoot\scripts\verify-signed-update.mjs" --manifest "$manifestPath" --signature "$signaturePath" --public-key "$publicKeyPath" --asset "$assetPath"
    if ($LASTEXITCODE -ne 0) {
        throw 'Verification failed. No bundle was synchronized.'
    }

    $release = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($release.version -ne $expectedVersion -or $release.releaseSequence -ne $expectedSequence) {
        throw 'The public release does not match the intended version and sequence.'
    }

    $lockPath = Join-Path $companionRoot 'upstream.json'
    $lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($release.keyId -ne $lock.keyId) {
        throw 'The signing key changed. Complete the key rotation checks first.'
    }
    if ($release.releaseSequence -lt $lock.releaseSequence) {
        throw 'The public release sequence is older than the current bundle.'
    }
    if ([version]$release.version -lt [version]$lock.version) {
        throw 'The public userscript version is older than the current bundle.'
    }

    $lock.version = $release.version
    $lock.sha256 = $release.sha256
    $lock.bytes = $release.bytes
    $lock.keyId = $release.keyId
    $lock.releaseSequence = $release.releaseSequence
    $json = $lock | ConvertTo-Json -Depth 10
    $encoding = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($lockPath, $json + "`n", $encoding)

    npm --prefix "$companionRoot" run sync:userscript -- --source "$assetPath"
    if ($LASTEXITCODE -ne 0) {
        throw 'Synchronization failed. Do not build the package yet.'
    }

    $bundlePath = Join-Path $companionRoot 'addon\globalPlugins\whatsappWebPlusCompanion\resources\whatsapp_web_plus.user.js'
    $bundleHash = (Get-FileHash -LiteralPath $bundlePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($bundleHash -ne $release.sha256 -or (Get-Item -LiteralPath $bundlePath).Length -ne $release.bytes) {
        throw 'The copied bundle does not match the verified release.'
    }
    $lock | Select-Object version, sha256, bytes, keyId, releaseSequence
}
```

A successful run prints `verified=true`, then `Embedded bundle`, followed by the bundled release details. Version, hash, size, key ID, and release sequence now come from the verified public release. Other lock fields remain unchanged.

If verification fails, do not continue or use a local build as a substitute. Public files may still be updating. Check the publication and run the whole block again when the files are consistent. If synchronization fails after the lock was saved, the lock may already contain the new metadata. Fix the cause and rerun this block before building Companion.

## 4. Test and build Companion

```powershell
npm --prefix "$companionRoot" test
```

This runs Python tests, lint and formatting checks, and builds the add-on. After success, install the newly generated `.nvda-addon` package and restart NVDA. Complete the project's installed-NVDA release checks.

Do not run the default `sync:userscript` command afterward, because it reads the sibling project's local build. If synchronization is needed again, repeat step 3 with the verified download.

As long as the public release remains the same and no different cached update is selected, the update checker should report that the bundle is current. A later published release can legitimately trigger another update.

## Local development before publication

You can still build and synchronize a local userscript to test unpublished changes. That is a development bundle, and it may differ from GreasyFork even at the same version. Do not expect the online update checker to report it as identical.

If that local build is already current, there is no need to build it again. For the final public Companion package, return to this guide after publishing and replace the development bundle with the verified public file.

## Files affected

- `upstream.json` records the verified version, hash, size, key ID, and release sequence.
- `addon/globalPlugins/whatsappWebPlusCompanion/resources/whatsapp_web_plus.user.js` contains the exact downloaded file.
- `addon/globalPlugins/whatsappWebPlusCompanion/resources/bundle.json` records the synchronized metadata.

The build also regenerates packaging outputs. These steps do not publish anything or change an already installed add-on until you install the new package.
