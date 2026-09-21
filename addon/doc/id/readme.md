# WhatsApp Companion

WhatsApp Companion menghadirkan fitur aksesibilitas WhatsApp Web Plus ke aplikasi WhatsApp dari Microsoft Store. Add-on NVDA ini mendukung WhatsApp Stable dan WhatsApp Beta di Windows.

Anda tidak memerlukan Tampermonkey atau pengetahuan pemrograman.

## Mana yang perlu saya gunakan?

- **Aplikasi Microsoft Store:** gunakan WhatsApp Companion bersama NVDA.
- **Browser:** gunakan [WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus) bersama Tampermonkey.

Anda boleh menggunakan keduanya jika memakai WhatsApp di kedua tempat. Masing-masing diperbarui secara terpisah.

## Yang Anda perlukan

- Windows 10 atau Windows 11
- NVDA 2025.1 sampai NVDA 2026.2
- WhatsApp Stable atau WhatsApp Beta dari Microsoft Store
- Paket terbaru `whatsappWebPlusCompanion-<versi>.nvda-addon`

Jalankan NVDA seperti biasa. Perbaikan izin saat pemasangan pertama mungkin meminta persetujuan administrator. Penggunaan sehari-hari tidak memerlukan hak administrator.

## Memasang atau memperbarui WhatsApp Companion

1. Tutup WhatsApp sepenuhnya. Jika masih berada di area notifikasi, pilih **Keluar** atau **Exit**.
2. Buka file `.nvda-addon` yang sudah diunduh.
3. Periksa nama dan versi add-on, lalu setujui pemasangan.
4. Mulai ulang NVDA ketika diminta.

Paket yang lebih baru akan memperbarui Companion yang sudah terpasang. Anda tidak perlu menghapus versi lama terlebih dahulu. Biarkan WhatsApp tetap tertutup untuk langkah berikutnya.

## Pemasangan pertama: perbaiki izin WebView2

**Langkah ini wajib dilakukan sebelum membuka WhatsApp jika Anda baru pertama kali memasang Companion di komputer ini.** Langkah ini menyiapkan izin Windows yang dibutuhkan Companion.

1. Tekan `NVDA + N` untuk membuka menu NVDA.
2. Pilih **Peralatan**, lalu **WhatsApp Companion**.
3. Pilih **Diagnosa dan perbaiki izin kebijakan WebView2**.
4. Ikuti petunjuk yang diucapkan NVDA dan setujui perbaikan jika diperlukan.
5. Izinkan perbaikan ketika Windows meminta persetujuan administrator.

Jika NVDA mengatakan bahwa perbaikan tidak diperlukan, lanjutkan ke bagian berikutnya. Jika perbaikan diperlukan, tunggu sampai NVDA mengonfirmasi bahwa perbaikan berhasil.

Biasanya langkah ini cukup dilakukan sekali. Izin tetap berlaku setelah Windows dimulai ulang atau NVDA, Companion, dan WhatsApp diperbarui. Jalankan perbaikan lagi jika izin dihapus dari Registry Windows atau Windows dipasang ulang.

Jika Companion sudah pernah berfungsi di komputer ini, pembaruan biasa tidak memerlukan perbaikan izin ulang.

## Membuka WhatsApp dengan Companion

1. Pastikan WhatsApp sudah tertutup.
2. Tekan `NVDA + N`.
3. Pilih **Peralatan**, lalu **WhatsApp Companion**.
4. Pilih **Luncurkan WhatsApp Stable dengan WhatsApp Companion** atau **Luncurkan WhatsApp Beta dengan WhatsApp Companion**.
5. Tunggu sampai NVDA mengonfirmasi bahwa WhatsApp berjalan dengan Companion.

Jika WhatsApp terbuka tetapi fokus belum berpindah ke sana, tekan `Alt + Tab`.

Selalu buka WhatsApp dari menu Companion ketika ingin memakai fiturnya. Membuka WhatsApp dari menu Mulai tidak menyiapkannya untuk Companion.

## Memastikan Companion berfungsi

Buka sebuah chat, lalu coba pintasan berikut:

| Pintasan | Kegunaan |
| --- | --- |
| `Alt + 1` | Pindah ke daftar chat |
| `Alt + 2` | Pindah ke pesan terbaru |
| `Alt + 3` | Pindah ke pesan pertama yang belum dibaca |
| `Shift + F8` | Buka pengaturan WhatsApp Web Plus |

Jika pintasan tersebut berfungsi, Companion sudah terhubung dan siap digunakan. Anda boleh membiarkan pengaturan bawaan seperti adanya.

## Penggunaan sehari-hari

Buka **Menu NVDA > Peralatan > WhatsApp Companion** untuk membuka WhatsApp atau mengelola Companion.

- **Mengulang pesan:** pilih **Laporkan hasil WhatsApp Companion terakhir** jika Anda melewatkan hasil atau menggunakan mode ucapan Sesuai Permintaan di NVDA.
- **Menutup WhatsApp:** tutup seperti biasa. Jika masih berjalan, gunakan **Tutup paksa semua proses WhatsApp dari Microsoft Store**. Tindakan ini dapat memutus panggilan atau transfer dan menghilangkan teks yang belum dikirim.
- **Membaca pesan lengkap:** fokuskan sebuah pesan dan tekan `Alt + Shift + C` untuk membukanya di jendela baca NVDA. Tekan `Escape` untuk menutupnya.
- **Mengubah pengaturan:** tekan `Shift + F8` di WhatsApp.

### Label kontrol panggilan

Pilih **Menu NVDA > Peralatan > WhatsApp Companion > Label kontrol panggilan** untuk menambahkan label sesuai bahasa WhatsApp. Anda dapat menyesuaikan label jawab, tolak, kamera, mikrofon, reaksi, angkat/turunkan tangan, berbagi layar, dan akhiri panggilan.

1. Pilih **Tindakan panggilan**. Kolom **Label bawaan** yang hanya bisa dibaca menampilkan label yang sudah dikenali.
2. Masukkan **Label tambahan**, satu nama kontrol persis per baris sesuai ucapan NVDA. Jangan sertakan ucapan jenis atau status kontrol, seperti "tombol" atau "tidak dicentang". Untuk kontrol dengan dua status, masukkan keduanya, misalnya label untuk membisukan dan mengaktifkan mikrofon.
3. Pilih tindakan lain untuk mengedit labelnya, lalu pilih **Simpan** untuk langsung menerapkan semua perubahan. Tidak perlu memulai ulang NVDA. Pilih **Batal** untuk membuang perubahan yang belum disimpan.

Beberapa bahasa dapat dimasukkan sekaligus tanpa memilih bahasa secara manual. Label bawaan tetap aktif. Setiap tindakan menerima maksimal 20 label tambahan, masing-masing maksimal 128 karakter. Label yang sama tidak boleh digunakan untuk tindakan berbeda. Label mikrofon juga berlaku pada tampilan panggilan kecil. Masukkan juga label **Akhiri panggilan** sesuai bahasa WhatsApp, karena pintasan panggilan aktif lainnya memakai kontrol tersebut untuk mengenali panggilan.

Kolom kosong hanya memakai label bawaan. **Hapus semua label tambahan** mengosongkan isian di dialog; pilih **Simpan** untuk menerapkannya, atau **Batal** untuk mempertahankan label tersimpan.

Label disimpan secara global di `nvda.ini` milik NVDA, pada bagian `[whatsappCompanionCallLabels]`. Pengaturan berlaku untuk WhatsApp Stable dan Beta di semua profil NVDA, serta tetap tersimpan setelah add-on diperbarui atau dipasang ulang selama konfigurasi NVDA yang sama dipertahankan. Mengembalikan NVDA ke pengaturan bawaan pabrik atau menghapus konfigurasi tersebut menghapus label tersimpan.

### Pintasan panggilan

Lihat [daftar pintasan lengkap](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#pintasan-keyboard-whatsapp) untuk navigasi, panggilan masuk, dan fitur tambahan.

Perintah panggilan hanya muncul dalam **NVDA > Preferensi > Gestur Input > WhatsApp Companion** bila dialog dibuka dari WhatsApp. Fokuskan WhatsApp dahulu. Perintah global seperti Luncurkan WhatsApp tetap tersedia di aplikasi lain. Gestur kustom panggilan dari versi sebelumnya perlu ditetapkan ulang karena perintah berpindah ke app module.

| Tindakan | Shortcut |
| --- | --- |
| Jawab panggilan masuk | Ctrl+Alt+A |
| Tolak panggilan masuk | Ctrl+Alt+D |
| Aktifkan/nonaktifkan kamera | Ctrl+Alt+V |
| Bisukan/aktifkan mikrofon | Ctrl+Alt+M |
| Reaksi | Ctrl+Alt+R |
| Angkat/turunkan tangan | Ctrl+Alt+H |
| Mulai/hentikan berbagi layar | Ctrl+Alt+S |
| Akhiri panggilan | Ctrl+Alt+W |

## Memperbarui WhatsApp Web Plus di dalam Companion

1. Buka **Menu NVDA > Peralatan > WhatsApp Companion**.
2. Pilih **Periksa pembaruan userscript WhatsApp Web Plus**.
3. Tunggu sampai NVDA melaporkan hasilnya.
4. Tutup WhatsApp sepenuhnya, lalu buka kembali melalui Companion.

Langkah ini memperbarui salinan WhatsApp Web Plus yang digunakan Companion. Untuk memperbarui add-on Companion, pasang paket `.nvda-addon` yang lebih baru. Jika Anda juga memakai WhatsApp Web Plus di browser, perbarui pemasangan tersebut secara terpisah.

## Pemecahan masalah

- **WhatsApp sudah berjalan:** tutup sepenuhnya, lalu buka melalui Companion.
- **WhatsApp tidak ditemukan:** pastikan aplikasi Stable atau Beta yang dipilih sudah terpasang dari Microsoft Store.
- **WhatsApp terbuka tetapi belum siap:** tunggu sampai pesan selesai dimuat. Jika NVDA melaporkan kesalahan, gunakan **Laporkan hasil WhatsApp Companion terakhir** dan catat pesan lengkapnya.
- **Pintasan tidak berfungsi atau koneksi terputus:** tutup WhatsApp, lalu buka kembali dari menu Companion.
- **Masalah izin WebView2:** jalankan kembali **Diagnosa dan perbaiki izin kebijakan WebView2**. Jika kebijakan Windows atau pembatasan administrator menghalangi perbaikan, hubungi administrator Anda.

Baca [panduan pemecahan masalah lengkap](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#pemecahan-masalah) untuk pesan dan langkah pemulihan lainnya.

## Bantuan lainnya

Untuk panggilan native masuk, fokuskan jendela panggilan melalui Alt+Tab, lalu tekan **Ctrl+Alt+A** untuk menjawab atau **Ctrl+Alt+D** untuk menolak. Companion mensyaratkan satu pasangan tombol Accept/Decline yang terlihat dan aktif di jendela itu. Akhiri panggilan tidak dianggap Tolak. Pada aplikasi lain, editor, atau AltGr, tombol diteruskan seperti biasa. Sesi secure, terkunci, dan no-write juga meneruskan tombol. Penahanan/pengulangan tombol dibatasi agar tidak segera mengaktifkan lagi; WhatsApp memberikan umpan balik hasil panggilan.

Untuk diagnostik, buka Gestur Input dari WhatsApp dan tetapkan ulang gestur **Ambil diagnostik panggilan WhatsApp native** (tanpa shortcut bawaan). Saat panggilan terhubung, ambil satu snapshot; bagian `controls` pada `WWP-CALL-SNAPSHOT` memuat semua tombol yang dikenali tanpa mengaktifkannya. Ambil snapshot lagi setelah mikrofon/kamera berubah status atau tangan diangkat, bila diperlukan. Jika tombol tidak tercatat, fokuskan tombol itu dengan Tab, pastikan navigator NVDA berada pada tombol tersebut, lalu tekan NVDA+F1, lalu salin informasi objeknya setelah menghapus identitas pribadi. Tidak perlu mengambil NVDA+F1 untuk semua tombol sejak awal.

Diagnostik juga mencatat tombol yang belum terpetakan pada `controls.unmapped`, termasuk ID teknis, enabled/offscreen, serta ketersediaan pola Invoke/Toggle. Nama tombol yang tidak dikenal tetap dihilangkan. Status `complete` berarti penelusuran selesai, bukan semua tombol sudah dikenali. Ketersediaan Toggle bukan status nyala/mati. Periksa identifier sebelum membagikan log karena provider dapat menyisipkan data pribadi. Jika kamera/reaksi/tangan/berbagi layar masih belum dikenali, kirim satu snapshot baru dahulu; pemetaan aksi tidak ditambahkan hanya berdasarkan nama ID.

Jika tampilan panggilan kecil hanya memiliki checkbox mikrofon, shortcut yang tidak menemukan kontrol akan mencoba aksi aksesibilitas bawaan pada satu objek WhatsApp.PeerStreamVm yang terverifikasi. Tidak memakai posisi tetap atau navigasi relatif. Lepaskan tombol, periksa tampilan, lalu tekan shortcut lagi; perintah panggilan tidak dijalankan ulang otomatis. Jika objek tidak menawarkan default action atau hasilnya tidak pasti, buka tampilan penuh secara manual. Pemulihan ini tidak dijalankan setelah aksi panggilan gagal/meragukan. Uji dengan NVDA nyata: satu pemulihan, tombol ditahan, perpindahan jendela, serta aktivasi baru setelah tampilan kembali.

Ctrl+Alt+S mengaktifkan Start screen sharing atau Stop screen sharing sesuai kontrol yang tersedia. Pilihan layar/jendela dan konfirmasi tetap dilakukan pengguna; tidak ada layar yang dipilih otomatis. Uji mulai, batalkan pemilih dengan Escape, hentikan berbagi, lalu Ctrl+Alt+W saat berbagi aktif. Penelusuran tetap mencakup seluruh jendela dengan batas node/waktu, memakai cache properti UIA per objek untuk mengurangi permintaan antarproses; identitas dan keadaan kontrol diperiksa langsung lagi sebelum aktivasi. Log propertyCache menunjukkan apakah optimasi ini tersedia. Hasil partial tetap ditolak dan bukan izin mengaktifkan tombol.

Enam shortcut panggilan aktif mensyaratkan tombol End call dan target unik dalam host yang sama. Pemetaan awal memakai label Inggris dan InvokePattern; checkbox React (NewReactionButton) dan Start/Stop screen sharing (NewScreenShareButton) menggunakan satu aktivasi TogglePattern; kontrol Toggle-only lainnya belum didukung. Reaksi dan berbagi layar membuka kontrol WhatsApp; pilihan lanjut tetap dilakukan pengguna. Uji pada panggilan percobaan, karena label/status/provider pada instalasi nyata belum diverifikasi. Bila memakai WhatsAppNG, nonaktifkan sementara lalu restart NVDA agar app module tidak bertabrakan.

Panduan online berikut bersifat opsional. Anda tidak perlu membacanya untuk menyelesaikan pemasangan.

- [Perintah menu Companion](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#perintah-pada-menu-whatsapp-companion)
- [Rincian perbaikan izin WebView2](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#mendiagnosis-dan-memperbaiki-izin-webview2)
- [Privasi dan keamanan](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#privasi-dan-keamanan)
- [Panduan pengembang](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#untuk-pengembang)

## Menghapus WhatsApp Companion

Tutup WhatsApp, buka Add-on Store NVDA, cari **WhatsApp Companion** pada daftar add-on terpasang, lalu pilih **Hapus**. Mulai ulang NVDA ketika diminta.

WhatsApp dan pemasangan WhatsApp Web Plus di browser tetap terpasang. Izin WebView2 yang sudah diperbaiki juga tetap berlaku.

## Melaporkan masalah

Gunakan [pelacak masalah Companion](https://github.com/muhammadGagah/whatsapp-web-plus-companion/issues) untuk masalah pembukaan aplikasi, koneksi, integrasi NVDA, pembaruan, atau perbaikan izin. Sertakan versi NVDA dan Windows, pilihan Stable atau Beta, perintah yang digunakan, pesan lengkap NVDA, dan hal yang terjadi.

Gunakan [pelacak masalah WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus/issues) untuk masalah pintasan, label pesan, pembacaan Status, Mode Privasi, atau pengaturan.

Jangan sertakan isi pesan pribadi, nama kontak, atau nomor telepon.

## Lisensi

Companion menggunakan GPL-2.0-or-later di bawah lisensi NVDA yang dimodifikasi dalam `COPYING.txt`. Userscript WhatsApp Web Plus yang disertakan tetap menggunakan lisensi MIT. Rincian komponen tersedia di `THIRD_PARTY_NOTICES.md`.
