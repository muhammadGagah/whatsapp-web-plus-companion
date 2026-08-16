# WhatsApp Companion

WhatsApp Companion adalah add-on NVDA untuk WhatsApp Stable dan
WhatsApp Beta versi Microsoft Store. Add-on ini membawa perintah keyboard dan
peningkatan pembaca layar dari WhatsApp Web Plus ke aplikasi WhatsApp desktop.

Companion dirancang untuk pengguna NVDA yang memakai ucapan atau braille. Anda
tidak perlu memahami JavaScript, Registry Windows, atau alat pengembang browser
untuk menggunakannya.

Panduan ini dimulai dari langkah yang paling sering diperlukan. Penjelasan
teknis dan keamanan diletakkan di bagian selanjutnya dan ditandai sebagai
bacaan opsional.

Ketika NVDA menggunakan bahasa Indonesia, tombol Bantuan di Pengelola Add-on
akan membuka panduan berbahasa Indonesia ini.

## Mulai di sini: proyek mana yang Anda perlukan?

Pertama, tentukan tempat Anda menggunakan WhatsApp.

- Jika Anda menggunakan WhatsApp Web di Chrome, Edge, atau browser lain,
  gunakan
  [WhatsApp Web Plus untuk browser](https://github.com/muhammadGagah/whatsapp-web-plus).
  Anda juga memerlukan pengelola userscript browser seperti Tampermonkey.
- Jika Anda menggunakan WhatsApp Stable atau WhatsApp Beta dari Microsoft
  Store, gunakan add-on Companion ini. Anda tidak memerlukan Tampermonkey untuk
  aplikasi desktop.

Anda boleh memakai kedua proyek jika menggunakan WhatsApp di kedua tempat.
Keduanya diperbarui secara terpisah.

Secara sederhana, WhatsApp Web Plus berisi fitur aksesibilitas. Companion
membuka aplikasi WhatsApp desktop, memuat salinan WhatsApp Web Plus yang sudah
diperiksa, lalu meneruskan pesan tertentu ke NVDA.

## Yang Anda perlukan

Sebelum memasang Companion, pastikan Anda memiliki:

- Windows 10 atau Windows 11.
- NVDA 2024.1 sampai NVDA 2026.1.
- WhatsApp Stable, WhatsApp Beta, atau keduanya dari Microsoft Store.
- File terbaru bernama
  `whatsappWebPlusCompanion-<versi>.nvda-addon`.

Penggunaan normal tidak memerlukan hak administrator. Windows hanya meminta
persetujuan administrator jika Anda memilih perbaikan izin opsional yang
dijelaskan nanti dalam panduan ini.

## Memasang atau meningkatkan Companion

1. Tutup WhatsApp sepenuhnya.
2. Jika WhatsApp masih berada di area notifikasi, gunakan perintah **Keluar**
   atau **Exit** dari WhatsApp.
3. Buka file `.nvda-addon` yang sudah diunduh.
4. Periksa nama dan versi add-on, lalu setujui pemasangan atau peningkatan.
5. Mulai ulang NVDA ketika diminta.
6. Biarkan WhatsApp tetap tertutup sampai Anda membukanya melalui Companion.

Memasang paket Companion yang lebih baru akan menggantikan add-on lama dan
salinan WhatsApp Web Plus bawaannya. Tindakan ini tidak mengubah userscript
WhatsApp Web Plus yang Anda pasang secara terpisah di browser.

Nama add-on yang terlihat sekarang adalah **WhatsApp Companion**. Nama file
paket, ID add-on internal, folder pemasangan, dan repositori GitHub tetap
menggunakan `whatsappWebPlusCompanion` atau `whatsapp-web-plus-companion` agar
instalasi yang sudah ada tetap dapat ditingkatkan tanpa menjadi add-on baru.

## Membuka WhatsApp untuk pertama kali

1. Pastikan WhatsApp sudah tertutup.
2. Tekan `NVDA+N` untuk membuka menu NVDA.
3. Pilih **Peralatan**.
4. Pilih **WhatsApp Companion**.
5. Pilih **Luncurkan WhatsApp Stable dengan WhatsApp Companion** atau
   **Luncurkan WhatsApp Beta dengan WhatsApp Companion**.
6. NVDA akan mengatakan bahwa WhatsApp sedang dibuka. Tunggu sampai NVDA
   memastikan bahwa WhatsApp sudah berjalan dengan Companion.
7. Jika WhatsApp terbuka tetapi tidak menerima fokus, tekan `Alt+Tab` sekali.

Setelah mendengar konfirmasi tersebut, gunakan perintah pada bagian
[Pintasan keyboard WhatsApp](#pintasan-keyboard-whatsapp).

Jangan buka WhatsApp dari menu Mulai ketika Anda ingin memakai Companion.
Companion perlu menyiapkan pengaturan lokal sementara sebelum WhatsApp dibuka.

### Apa yang seharusnya terjadi?

- WhatsApp terbuka seperti biasa.
- NVDA tetap responsif selama Companion bekerja di latar belakang.
- Companion menunggu jika WhatsApp masih memuat atau mengunduh pesan.
- NVDA mengonfirmasi ketika WhatsApp dan WhatsApp Web Plus sudah siap.
- Antarmuka WhatsApp biasa tetap dibaca oleh NVDA seperti biasanya.

Jika hal tersebut tidak terjadi, baca bagian
[Pemecahan masalah](#pemecahan-masalah).

## Penggunaan sehari-hari

### Membuka WhatsApp

Selalu buka aplikasi WhatsApp yang didukung dari submenu Companion. Jika Anda
hanya menggunakan satu kanal WhatsApp, Anda dapat menetapkan gestur keyboard
untuk perintah pembukanya nanti.

### Menutup WhatsApp

Tutup WhatsApp seperti biasa. Jangan menjalankan perintah pembuka lagi untuk
menghentikannya.

Jika WhatsApp tetap berjalan di latar belakang, gunakan **Tutup paksa semua
proses WhatsApp dari Microsoft Store**. Companion meminta konfirmasi karena
penutupan paksa dapat memutus panggilan dan transfer file. Teks yang belum Anda
kirim juga mungkin hilang.

### Mendengar kembali hasil terakhir

Gunakan **Laporkan hasil WhatsApp Companion terakhir** jika Anda
melewatkan sebuah pesan atau memakai mode ucapan Sesuai Permintaan. Perintah
ini mengulangi hasil pembukaan, koneksi, penutupan, perbaikan, atau pembaruan
terakhir.

## Perintah pada menu WhatsApp Companion

Buka menu NVDA, pilih **Peralatan**, lalu pilih **WhatsApp Companion**. Gunakan
tombol panah untuk berpindah, `Enter` untuk menjalankan perintah, dan `Escape`
untuk menutup menu.

### Perintah untuk membuka WhatsApp

- **Luncurkan WhatsApp Stable dengan WhatsApp Companion** membuka
  aplikasi Stable dari Microsoft Store.
- **Luncurkan WhatsApp Beta dengan WhatsApp Companion** membuka
  aplikasi Beta dari Microsoft Store.
- **Luncurkan kanal WhatsApp terakhir yang dipilih dengan WhatsApp Companion**
  mengulangi pilihan Stable atau Beta yang terakhir Anda gunakan.

WhatsApp Stable dan WhatsApp Beta adalah dua aplikasi Microsoft Store yang
terpisah. Anda boleh memasang salah satu atau keduanya.

### Perintah untuk mengatasi masalah

- **Tutup paksa semua proses WhatsApp dari Microsoft Store** menutup semua
  proses Stable dan Beta setelah Anda menyetujui peringatannya. Gunakan hanya
  jika penutupan biasa tidak berhasil.
- **Diagnosa dan perbaiki izin kebijakan WebView2** memeriksa izin Windows yang
  diperlukan Companion. Sebagian besar pengguna tidak akan memerlukan
  perintah ini. Jalankan hanya ketika Companion memintanya atau bagian
  pemecahan masalah menyarankannya.

### Perintah hasil dan pembaruan

- **Laporkan hasil WhatsApp Companion terakhir** mengulangi hasil
  terbaru.
- **Periksa pembaruan userscript WhatsApp Web Plus** memeriksa sumber resmi
  yang sudah ditentukan. Jika salinan resmi yang lebih baru atau berbeda lolos
  pemeriksaan, Companion akan memasangnya untuk pembukaan berikutnya. Perintah
  ini tidak membuka browser.

## Menetapkan gestur keyboard opsional

Companion tidak memiliki gestur keyboard bawaan. Hal ini mencegah benturan
dengan NVDA, Windows, WhatsApp, dan add-on lain.

Untuk menambahkan gestur sendiri:

1. Buka menu NVDA.
2. Pilih **Preferensi**, lalu **Gestur Input**.
3. Ketik `WhatsApp Companion` di kotak penyaring.
4. Buka kategori **WhatsApp Companion**.
5. Pilih sebuah perintah.
6. Pilih **Tambah**, tekan gestur yang Anda inginkan, lalu setujui dialog.

Pengaturan sederhana yang berguna adalah satu gestur untuk perintah pembuka
yang biasa Anda gunakan dan satu gestur untuk **Laporkan hasil WhatsApp
Companion terakhir**.

## Pintasan keyboard WhatsApp

Companion hanya membuka dan menghubungkan WhatsApp. Perintah yang Anda gunakan
di dalam WhatsApp berasal dari proyek utama WhatsApp Web Plus.

Anda tidak perlu menghafal semua pintasan ini. Pelajari hanya pintasan yang
Anda perlukan.

### Berpindah di WhatsApp

| Pintasan | Tindakan |
| --- | --- |
| `Alt + Shift + 1` | Buka Chat |
| `Alt + Shift + 2` | Buka Status atau Pembaruan |
| `Alt + Shift + 3` | Buka Komunitas |
| `Alt + Shift + 4` | Buka Saluran |
| `Alt + Shift + 5` | Buka Meta AI |
| `Alt + Shift + D` | Berpindah antara riwayat pesan dan area penulisan pesan |
| `Alt + 1` | Pindah ke daftar chat |
| `Alt + 2` | Pindah ke pesan terbaru |
| `Alt + 3` | Pindah ke pesan pertama yang belum dibaca |
| `Alt + Up Arrow` | Buka chat sebelumnya jika diaktifkan pada Pemetaan ulang pintasan |
| `Alt + Down Arrow` | Buka chat berikutnya jika diaktifkan pada Pemetaan ulang pintasan |
| `Alt + T` | Baca judul chat saat ini; tekan dua kali dengan cepat untuk mengaktifkan atau menonaktifkan pemantau aktivitas chat |
| `Alt + 0` | Tutup pemutar audio atau video WhatsApp, atau tutup promosi aplikasi desktop |
| `Alt + M` | Mulai merekam pesan suara jika diaktifkan pada Pemetaan ulang pintasan |

### Kontrol panggilan masuk

Pintasan ini hanya bekerja ketika panggilan suara atau video masuk sedang
berdering dan WhatsApp menampilkan tombol **Terima** dan **Tolak**. Pintasan
akan menekan tombol yang sama. Jika pintasan tidak bekerja, pindah ke tombol
tersebut dan tekan secara langsung.

| Pintasan | Tindakan |
| --- | --- |
| `Ctrl + Alt + A` | Terima panggilan suara atau video masuk |
| `Ctrl + Alt + D` | Tolak panggilan suara atau video masuk |

### Fitur opsional

| Pintasan | Tindakan |
| --- | --- |
| `Alt + Shift + N` | Aktifkan atau nonaktifkan Mode Privasi |
| `Alt + Shift + L` | Aktifkan atau nonaktifkan pembacaan pesan otomatis |
| `Shift + F8` | Buka atau tutup pengaturan WhatsApp Web Plus |
| `Alt + Shift + 8` | Aktifkan atau nonaktifkan Bersihkan Antarmuka |
| `Alt + Shift + 9` | Aktifkan atau nonaktifkan Mode Gelap Asli |

Pilihan fitur opsional Anda diingat setelah WhatsApp dimuat ulang.

### Bantuan WhatsApp Web Plus lainnya

- [Penggunaan pertama WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus#first-use)
  memberikan pengenalan terpandu.
- [Menu pengaturan WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus#settings-menu)
  menjelaskan menu `Shift+F8`.
- [Mode Privasi](https://github.com/muhammadGagah/whatsapp-web-plus#what-each-setting-does)
  menjelaskan data yang disembunyikan ketika penyaringan privasi aktif.
- [Membuka menu konteks pesan dengan NVDA](https://github.com/muhammadGagah/whatsapp-web-plus#open-a-message-context-menu-with-nvda)
  menjelaskan metode keyboard dan mouse NVDA.

## Memperbarui salinan WhatsApp Web Plus bawaan

Jalankan **Periksa pembaruan userscript WhatsApp Web Plus** ketika Anda ingin
Companion mencari salinan WhatsApp Web Plus yang lebih baru.

Perintah ini bekerja di latar belakang:

1. Companion menghubungi alamat resmi Greasy Fork yang sudah ditentukan.
2. Companion memeriksa versi dan rincian file.
3. Jika ada versi lebih baru, Companion mengunduh dan memeriksanya.
4. Jika isi resmi berubah tanpa perubahan versi, Companion memeriksa lalu
   menyegarkan salinan tersebut.
5. NVDA memberi tahu apakah salinan sudah terbaru, diperbarui, disegarkan, atau
   tidak diubah karena terjadi kesalahan.

Pembaruan digunakan saat Anda membuka WhatsApp melalui Companion berikutnya.
Pembaruan tidak mengganti kode yang sedang berjalan. Tutup WhatsApp sepenuhnya
lalu buka kembali untuk memakai salinan baru.

Perintah ini hanya memperbarui salinan milik Companion. Salinan browser yang
dipasang melalui Tampermonkey atau pengelola userscript lain harus diperbarui
melalui browser.

Companion mempertahankan salinan di dalam paket sebagai cadangan aman. Jika
salinan hasil unduhan rusak, tidak lengkap, lebih lama, atau gagal saat
diperiksa ketika dimulai, Companion memakai salinan paket pada pembukaan
berikutnya.

## Mendiagnosis dan memperbaiki izin WebView2

Sebagian besar pengguna boleh melewati bagian ini. Gunakan hanya ketika
Companion melaporkan masalah izin WebView2.

### Apa yang diperiksa?

Sebelum membuka WhatsApp, Companion menulis pengaturan sementara kecil di
Registry Windows. Registry adalah tempat Windows menyimpan pengaturan.
Companion menghapus pengaturan sementara tersebut setelah berhasil terhubung.

Beberapa komputer melindungi lokasi ini sehingga NVDA tidak dapat menulis
pengaturannya. Memulai ulang NVDA tidak mengubah izin tersebut. Perintah
diagnosis memeriksa izin tanpa mengubah apa pun.

### Apa yang terjadi ketika saya menjalankan perintah ini?

1. Companion memeriksa apakah Windows mengizinkan akses Registry yang
   diperlukan.
2. Jika WhatsApp sedang berjalan, Companion menawarkan untuk menutup paksa
   Stable dan Beta lalu melanjutkan diagnosis. **Biarkan WhatsApp tetap
   terbuka** adalah pilihan aman bawaan.
3. Jika izin sudah berfungsi, NVDA mengatakan bahwa perbaikan tidak diperlukan.
4. Jika perbaikan mungkin membantu, dialog terpisah menjelaskan perubahannya.
5. Hanya setelah Anda setuju, Windows menampilkan permintaan User Account
   Control.

Menutup WhatsApp tidak berarti Anda menyetujui perbaikan izin. Keduanya adalah
dua keputusan yang berbeda. Companion tidak pernah menjalankan NVDA atau
WhatsApp sebagai administrator.

### Apa yang diubah oleh perbaikan opsional?

Perbaikan memberi akun Windows Anda izin untuk membaca dan memperbarui satu
kunci kebijakan WebView2. Kunci kebijakan adalah lokasi Registry yang digunakan
untuk pengaturan aplikasi.

Perbaikan tidak mengubah nilai Registry. Perbaikan tidak mengubah kebijakan
tingkat komputer, menghapus aturan penolakan administrator, mengambil alih
kepemilikan, atau menyentuh `HKEY_LOCAL_MACHINE`.

Windows memberi izin untuk seluruh kunci, bukan untuk satu nilai di dalamnya.
Artinya, program yang berjalan menggunakan akun Windows Anda dapat mengubah
nilai lain di dalam kunci kebijakan WebView2 tersebut. Dialog menjelaskan hal
ini sebelum Anda menyetujui perbaikan.

Izin akan tetap ada setelah NVDA atau Windows dimulai ulang dan setelah add-on
dihapus. Hanya administrator yang dapat mengubahnya nanti. Lokasi lengkapnya
adalah:

`HKEY_CURRENT_USER\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments`

Hubungi administrator jika kebijakan Windows, aturan penolakan, atau hak
administrator yang tidak memadai menghalangi perbaikan.

## Privasi dan keamanan

Anda boleh melewati bagian ini saat menggunakan Companion seperti biasa.
Bagian ini menjelaskan batasan yang membuat Companion tetap berfokus pada
WhatsApp.

- Companion hanya bekerja dengan aplikasi WhatsApp Stable dan Beta Microsoft
  Store yang didukung.
- Koneksi sementaranya tetap berada di komputer Anda dan dibatasi untuk
  aplikasi WhatsApp yang dibuka oleh Companion.
- Companion hanya terhubung ke halaman internal WhatsApp yang diharapkan.
- Companion tidak mengirim chat, kontak, atau data sesi WhatsApp ke layanan
  pembaruan.
- Companion hanya mengunduh JavaScript setelah Anda menjalankan perintah
  pembaruan dan hanya dari alamat resmi Greasy Fork yang sudah ditentukan.
- Companion memeriksa identitas userscript, versi, alamat, mode izin, sidik
  jari SHA-256, dan ukuran file sebelum memilih hasil unduhan.
- Userscript yang terdapat di dalam paket add-on tidak pernah ditimpa.
- Pengaturan Windows sementara dihapus setelah koneksi lokal siap.
- Perbaikan izin hanya berjalan setelah konfirmasi terpisah dan persetujuan
  Windows.

Sumber pembaruan menggunakan HTTPS dan satu akun Greasy Fork yang sudah
ditentukan. Saat ini sumber tersebut tidak menyediakan tanda tangan penerbit
terpisah. Menjalankan perintah pembaruan berarti Anda mempercayai akun dan
layanan tersebut untuk menyediakan kode yang dapat dijalankan. Pemeriksaan file
dan penyimpanan aman dapat mendeteksi isi yang rusak atau tidak sesuai, tetapi
tidak dapat membuktikan identitas penerbit jika akun atau layanan sumber
diambil alih.

Informasi untuk pengembang dan peninjau mengenai userscript di dalam paket
tersedia di `upstream.json`, `bundle.json`, dan `THIRD_PARTY_NOTICES.md`.

## Cara kerja Companion

Bagian ini bersifat opsional. Anda tidak perlu membacanya untuk menggunakan
add-on.

Setiap kali Anda menjalankan perintah pembuka, Companion:

1. Memastikan Windows tidak terkunci dan NVDA berjalan secara normal.
2. Memastikan aplikasi WhatsApp Microsoft Store yang dipilih sudah terpasang
   dan belum berjalan.
3. Membuat koneksi sementara yang hanya tersedia di komputer Anda.
4. Membuka WhatsApp dan memastikan koneksi menuju aplikasi yang benar.
5. Menghapus pengaturan peluncuran sementara.
6. Menunggu sampai navigasi dan daftar chat WhatsApp siap.
7. Memuat dan memeriksa salinan WhatsApp Web Plus.
8. Menyambung kembali secara otomatis jika halaman internal WhatsApp dimuat
   ulang.

Pekerjaan tersebut berjalan di latar belakang agar antarmuka NVDA tetap
responsif. NVDA tetap membaca kontrol, menu, dialog, dan fokus WhatsApp biasa.
Companion hanya meneruskan pengumuman WhatsApp Web Plus tertentu ke ucapan dan
braille. Pengumuman yang tidak lagi sesuai dengan chat, bahasa, pengaturan
privasi, atau sesi saat ini akan dibuang.

## Pemecahan masalah

### NVDA mengatakan WhatsApp sudah berjalan

Tutup WhatsApp seperti biasa. Jika masih berada di area notifikasi, gunakan
perintah **Keluar** atau **Exit** WhatsApp. Jika WhatsApp tetap tidak tertutup,
gunakan **Tutup paksa semua proses WhatsApp dari Microsoft Store** dari submenu
Companion.

### Kanal WhatsApp yang dipilih tidak ditemukan

Pasang aplikasi yang benar dari Microsoft Store. WhatsApp Stable dan WhatsApp
Beta adalah aplikasi terpisah. Memasang salah satunya tidak memasang yang lain.

### Companion tidak dapat berjalan dalam keadaan saat ini

Buka kunci Windows dan jalankan NVDA secara normal. Jangan menjalankan NVDA
sebagai administrator. Companion tidak bekerja di desktop aman, dari sesi
Windows yang terkunci, atau dalam konfigurasi NVDA hanya-baca.

### WhatsApp terbuka tetapi Companion belum siap

Tunggu sampai NVDA memastikan bahwa WhatsApp berjalan dengan Companion.
Pemuatan dapat memerlukan waktu lebih lama ketika WhatsApp mengunduh pesan.
Jika NVDA melaporkan kesalahan, jalankan **Laporkan hasil WhatsApp Companion
terakhir** dan catat pesan lengkapnya.

### WhatsApp sudah siap tetapi tidak menerima fokus

Tekan `Alt+Tab` sekali untuk berpindah ke WhatsApp.

### Perintah WhatsApp Web Plus tidak berfungsi

Pastikan Anda membuka WhatsApp dari submenu Companion, bukan dari menu Mulai.
Jalankan **Laporkan hasil WhatsApp Companion terakhir** dan pastikan
pembukaan terakhir berhasil. Setelah itu, baca
[Pintasan keyboard WhatsApp](#pintasan-keyboard-whatsapp) untuk mengetahui
perintah terbaru dan pemetaan ulang opsional.

### NVDA mengatakan koneksi terputus

Tutup WhatsApp sepenuhnya lalu buka kembali melalui Companion. Companion
seharusnya dapat memulihkan pemuatan ulang halaman internal yang sederhana
secara otomatis. Kesalahan ini berarti beberapa percobaan penyambungan kembali
tidak berhasil memulihkan sesi yang sah.

### NVDA melaporkan masalah izin WebView2

Jalankan **Diagnosa dan perbaiki izin kebijakan WebView2** lalu ikuti petunjuk
yang diucapkan. Diagnosis tidak mengubah apa pun. Jika masalah disebabkan oleh
kebijakan komputer atau aturan penolakan administrator, hubungi administrator.

### Alat bantu perbaikan hilang atau tidak tepercaya

Pasang kembali Companion dari paket tepercaya. Companion memeriksa alat bantu
perbaikan sebelum menjalankannya dan menolak file yang tidak sesuai dengan
catatan di dalam paket.

### Perbaikan tidak dapat mengembalikan pengaturan sebelumnya

Jangan membuka WhatsApp melalui Companion. Minta administrator memeriksa kunci
kebijakan WebView2 per pengguna yang disebutkan di bagian izin sebelum Anda
mencoba lagi.

### Hasil yang datang di latar belakang tidak diucapkan

Mode ucapan Sesuai Permintaan NVDA mungkin menyembunyikan ucapan latar
belakang. Jalankan **Laporkan hasil WhatsApp Companion terakhir**.
Output braille tetap tersedia sesuai pengaturan NVDA Anda.

### Pembaruan gagal

Salinan sah yang sedang dipilih tetap digunakan. Periksa koneksi internet lalu
coba jalankan perintah pembaruan lagi nanti. Pembaruan yang gagal tidak akan
mengganti sebagian salinan di dalam paket.

## Menghapus Companion

1. Tutup WhatsApp.
2. Buka Add-on Store NVDA.
3. Temukan **WhatsApp Companion** di bagian add-on terpasang.
4. Pilih **Hapus**, lalu mulai ulang NVDA ketika diminta.

Menghapus Companion tidak menghapus WhatsApp atau userscript browser yang
terpisah. Tindakan ini juga tidak menghapus izin WebView2 yang ditambahkan oleh
perbaikan opsional. Administrator harus mengubah izin tersebut.

## Kamus istilah sederhana

- **Add-on:** Program kecil yang menambahkan fitur ke NVDA.
- **Userscript:** Program JavaScript kecil yang mengubah cara kerja halaman
  web. WhatsApp Web Plus adalah userscript.
- **Pengelola userscript browser:** Ekstensi seperti Tampermonkey yang
  menjalankan userscript di browser. Companion tidak memerlukannya.
- **Kanal WhatsApp:** Aplikasi Stable atau Beta dari Microsoft Store.
- **Registry:** Tempat Windows menyimpan pengaturan.
- **Kunci kebijakan:** Lokasi Registry untuk pengaturan aplikasi atau
  administrator.
- **WebView2:** Komponen Windows yang dipakai WhatsApp Desktop untuk menampilkan
  antarmukanya.
- **Bundel atau salinan bawaan:** Salinan JavaScript WhatsApp Web Plus yang
  dipilih oleh Companion.
- **SHA-256:** Sidik jari file yang dipakai untuk mencocokkan isi file dengan
  catatan yang diharapkan.
- **Administrator atau ditingkatkan:** Program yang berjalan dengan hak Windows
  tambahan.
- **Renderer:** Halaman internal yang menggambar antarmuka WhatsApp.
- **Pengumuman:** Pesan singkat yang diucapkan NVDA atau ditampilkan di braille.

## Untuk pengembang

Bagian ini tidak diperlukan untuk memasang atau menggunakan Companion.

Repository menggunakan
[NV Access Add-on Template resmi](https://github.com/nvaccess/AddonTemplate).
File Python memakai tab, akhir baris LF, dan panjang baris maksimum 110
karakter.

Pasang lingkungan pengembangan dengan versi yang sudah ditentukan:

```powershell
uv sync
```

Sinkronkan userscript hasil build dari repository sumber di sebelahnya:

```powershell
npm run sync:userscript
```

Jalankan lint, pengujian, pembuatan dokumentasi terjemahan, dan pembuatan paket:

```powershell
npm test
```

Jalankan semua pemeriksaan template resmi:

```powershell
$env:PREK_SKIP = "no-commit-to-branch"
uv run prek run --all-files
```

Pyright bersifat opsional. Alat ini memerlukan source NVDA yang sudah disiapkan
di `../nvda/source`:

```powershell
uv sync --group typecheck
uv run pyright
```

Alat bantu perbaikan izin dikemas sebagai `registryRepair.ps1` dan
`registryRepair.bat`. Catatan SHA-256 disimpan di
`resources/registry-repair.json`. Buat ulang catatan tersebut setelah mengubah
salah satu file alat bantu.

Sebelum rilis, periksa `upstream.json`, sinkronkan userscript, jalankan semua
pengujian, buat paket `.nvda-addon`, pasang paket, lalu selesaikan pengujian
manual NVDA dan WhatsApp.

Bantuan HTML, manifest terjemahan, katalog pesan terkompilasi, keadaan SCons,
dan paket `.nvda-addon` harus dibuat melalui proses build dan tidak boleh
diedit secara manual.

## Mendapatkan bantuan atau melaporkan masalah

Laporkan masalah pembukaan, koneksi, pembaruan, perbaikan, atau integrasi NVDA
di
[pelacak masalah WhatsApp Companion](https://github.com/muhammadGagah/whatsapp-web-plus-companion/issues).

Laporkan masalah pintasan WhatsApp, label, pembacaan Status, penyaringan
privasi, atau pengaturan userscript di
[pelacak masalah WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus/issues).

Sertakan versi NVDA, kanal WhatsApp, versi Windows, perintah yang digunakan,
pesan lengkap NVDA, dan hal yang terjadi. Jangan sertakan isi chat pribadi,
nama kontak, atau nomor telepon.

## Lisensi

Add-on Companion menggunakan GPL-2.0-or-later di bawah lisensi NVDA yang
dimodifikasi dalam `COPYING.txt`. Userscript WhatsApp Web Plus yang tertanam
tetap menggunakan lisensi MIT. Asal komponen dan batas lisensi dijelaskan dalam
`THIRD_PARTY_NOTICES.md`.
