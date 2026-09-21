# Menyertakan rilis WhatsApp Web Plus yang sudah dipublikasikan

[English guide](update-bundled-userscript.md)

Untuk rilis Companion, unduh userscript yang sudah dipublikasikan di GreasyFork, verifikasi, lalu salin file tersebut ke project add-on lokal. Dengan begitu, bundle dalam paket cocok dengan rilis daring yang bertanda tangan.

Hasil build lokal bisa memiliki versi dan kode yang sama, tetapi format metadata berbeda. GreasyFork dapat mengubah spasi serta urutan `@downloadURL` dan `@updateURL`. Hash ikut berubah, sehingga Companion bisa melaporkan pembaruan ulang pada versi yang sama.

## 1. Selesaikan publikasi userscript terlebih dahulu

Publikasikan userscript, manifest bertanda tangan, dan signature mengikuti `docs/RELEASE-SIGNING-CHEATSHEET-ID.md` di project script. Tunggu sampai ketiga file publik sesuai dengan rilis yang dimaksud.

**Panduan ini tidak memerlukan langkah build userscript.** Jika rilis sudah dibangun dan dipublikasikan, lanjutkan ke bawah. Jika perubahan source belum dipublikasikan, selesaikan rilis tersebut dahulu.

Siapkan Node.js/npm, dependensi build Companion termasuk `uv`, dan `update-public-key.pem` tepercaya di project script. Gunakan key rilis yang sudah ditetapkan. Pastikan fingerprint dan key ID cocok dengan key berstatus active atau transition dalam `addon/globalPlugins/whatsappWebPlusCompanion/resources/update-public-keys.json` milik Companion, serta sequence berada dalam rentang yang diizinkan key tersebut. Jangan mengunduh key pengganti hanya agar verifikasi lolos. Perubahan key memerlukan proses rotasi key tersendiri.

## 2. Tentukan path dan rilis yang akan disertakan

Gunakan terminal PowerShell yang sama untuk semua langkah. Semua path lokal di bawah hanya contoh. Kedua project boleh berada di lokasi mana pun. Ganti versi dan sequence dengan rilis yang ingin Anda sertakan. Keduanya mencegah rilis publik lama yang masih valid ikut terambil tanpa sengaja.

```powershell
$scriptRoot = 'D:\whatsapp\whatsapp-web-plus'
$companionRoot = 'D:\whatsapp\whatsapp-web-plus-companion'
$expectedVersion = '2.6.83'
$expectedSequence = 2026092101
```

URL unduhan pada blok berikut adalah URL resmi project, bukan contoh path lokal. Untuk fork, perubahan publikasi dan verifikasi harus disesuaikan bersama.

## 3. Unduh, verifikasi, dan sinkronkan

Tempel seluruh blok berikut ke PowerShell. Jika diakhiri prompt `>>` yang kosong, tekan Enter sekali lagi. Berhenti jika ada perintah yang melaporkan kegagalan.

Blok ini mengunduh file ke folder sementara baru, lalu memverifikasi signature, versi, hash, dan ukuran sebelum memperbarui `upstream.json`. Setelah itu, file unduhan disalin ke Companion. Hasil build lokal di project script tidak dibangun ulang atau ditimpa.

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

Jika berhasil, muncul `verified=true`, kemudian `Embedded bundle`, diikuti rincian rilis yang disertakan. Versi, hash, ukuran, key ID, dan release sequence sekarang berasal dari rilis publik yang sudah diverifikasi. Kolom lain dalam lock tetap dipertahankan.

Jika verifikasi gagal, jangan lanjutkan atau menggantinya dengan build lokal. File publik mungkin masih dalam proses pembaruan. Periksa publikasinya, lalu jalankan ulang seluruh blok setelah file cocok. Jika sinkronisasi gagal setelah lock disimpan, lock mungkin sudah memuat metadata baru. Perbaiki penyebabnya dan jalankan ulang blok ini sebelum membangun Companion.

## 4. Uji dan build Companion

```powershell
npm --prefix "$companionRoot" test
```

Perintah ini menjalankan tes Python, memeriksa lint dan format, lalu membangun add-on. Setelah berhasil, pasang paket `.nvda-addon` yang baru dihasilkan dan mulai ulang NVDA. Selesaikan juga pemeriksaan rilis project menggunakan NVDA yang terpasang.

Jangan menjalankan perintah `sync:userscript` tanpa sumber setelahnya, karena perintah itu membaca hasil build lokal dari project di folder sebelah. Jika perlu sinkronisasi lagi, ulangi langkah 3 dengan unduhan yang diverifikasi.

Selama rilis publik belum berubah dan tidak ada pembaruan berbeda dari cache yang dipilih, pemeriksa pembaruan seharusnya menyatakan bundle sudah terbaru. Rilis baru yang dipublikasikan kemudian tetap dapat memicu pembaruan.

## Pengembangan lokal sebelum publikasi

Anda tetap bisa membangun dan menyinkronkan userscript lokal untuk menguji perubahan yang belum dipublikasikan. Itu merupakan bundle pengembangan dan dapat berbeda dari GreasyFork meskipun versinya sama. Jangan mengharapkan pemeriksa pembaruan daring menyatakannya identik.

Jika hasil build lokal sudah terbaru, build tidak perlu diulang. Untuk paket Companion yang akan dirilis ke publik, kembali ke panduan ini setelah publikasi dan ganti bundle pengembangan dengan file publik yang sudah diverifikasi.

## File yang berubah

- `upstream.json` mencatat versi, hash, ukuran, key ID, dan release sequence yang sudah diverifikasi.
- `addon/globalPlugins/whatsappWebPlusCompanion/resources/whatsapp_web_plus.user.js` berisi file unduhan yang sama persis.
- `addon/globalPlugins/whatsappWebPlusCompanion/resources/bundle.json` mencatat metadata hasil sinkronisasi.

Build juga membuat ulang file pengemasan. Langkah-langkah ini tidak memublikasikan apa pun atau mengubah add-on terpasang sampai Anda memasang paket baru.
