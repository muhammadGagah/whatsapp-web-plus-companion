# Panduan lengkap WhatsApp Companion

[Kembali ke panduan pemasangan](../addon/doc/id/readme.md). Panduan ini berisi perintah tambahan, pemecahan masalah, keamanan, dan informasi untuk pengembang.

## Penggunaan sehari-hari

### Membuka WhatsApp

Selalu buka aplikasi WhatsApp yang didukung dari submenu Companion. Jika Anda
hanya menggunakan satu kanal WhatsApp, Anda dapat menetapkan gestur keyboard
untuk perintah membuka WhatsApp nanti.

### Menutup WhatsApp

Tutup WhatsApp seperti biasa. Jangan menjalankan lagi perintah untuk membuka
WhatsApp saat ingin menutupnya.

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
  jika WhatsApp tidak dapat ditutup seperti biasa.
- **Diagnosa dan perbaiki izin kebijakan WebView2** memeriksa izin Windows yang
  diperlukan Companion. Jalankan setelah pemasangan pertama di komputer ini,
  sebelum membuka WhatsApp. Jalankan kembali jika izin dihapus, Windows
  dipasang ulang, atau Companion melaporkan masalah izin.

### Perintah hasil dan pembaruan

- **Laporkan hasil WhatsApp Companion terakhir** mengulangi hasil
  terbaru.
- **Periksa pembaruan userscript WhatsApp Web Plus** memeriksa sumber resmi
  yang sudah ditentukan. Jika salinan resmi yang lebih baru atau berbeda lolos
  pemeriksaan, Companion akan memasangnya untuk digunakan saat WhatsApp dibuka
  kembali. Perintah ini tidak membuka browser.

## Menetapkan gestur keyboard opsional

Perintah global Companion, seperti membuka WhatsApp dan melaporkan hasil
terakhir, tidak memiliki gestur keyboard bawaan. Anda dapat menetapkan gestur
yang sesuai dengan kebutuhan. Perintah panggilan memiliki pintasan bawaan
yang tercantum di bawah.

Untuk menambahkan gestur sendiri:

1. Buka menu NVDA.
2. Pilih **Preferensi**, lalu **Gestur Input**.
3. Ketik `WhatsApp Companion` di kotak penyaring.
4. Buka kategori **WhatsApp Companion**.
5. Pilih sebuah perintah.
6. Pilih **Tambah**, tekan gestur yang Anda inginkan, lalu setujui dialog.

Anda bisa mulai dengan satu gestur untuk membuka WhatsApp seperti biasa
dan satu gestur untuk **Laporkan hasil WhatsApp Companion terakhir**.

Untuk menetapkan gestur panggilan, fokuskan WhatsApp sebelum membuka **Gestur
Input**. Perintah panggilan hanya muncul dalam kategori **WhatsApp Companion**
jika dialog dibuka dari WhatsApp. Tetapkan ulang gestur panggilan kustom dari
versi sebelumnya karena perintah ini telah dipindahkan ke app module WhatsApp.

## Pintasan keyboard WhatsApp

Companion membuka dan menghubungkan WhatsApp, menyediakan pintasan panggilan,
serta membuka pesan di jendela baca NVDA. Navigasi dan fitur opsional di dalam
WhatsApp berasal dari userscript WhatsApp Web Plus.

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
| `Alt + T` | Baca judul chat saat ini. Tekan dua kali dengan cepat untuk mengaktifkan atau menonaktifkan pemantau aktivitas chat |
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

Untuk panggilan masuk di aplikasi desktop, fokuskan jendela panggilan dengan
Alt+Tab sebelum menggunakan pintasan ini. Companion memerlukan satu pasangan
tombol Terima dan Tolak yang terlihat dan aktif di jendela tersebut.

### Kontrol panggilan aktif

Selama panggilan terhubung, gunakan pintasan berikut di jendela panggilan:

| Pintasan | Tindakan |
| --- | --- |
| Ctrl+Alt+V | Aktifkan atau nonaktifkan kamera |
| Ctrl+Alt+M | Bisukan atau aktifkan mikrofon |
| Ctrl+Alt+R | Buka reaksi |
| Ctrl+Alt+H | Angkat atau turunkan tangan |
| Ctrl+Alt+S | Mulai atau hentikan berbagi layar |
| Ctrl+Alt+W | Akhiri panggilan |

Pintasan reaksi dan berbagi layar membuka kontrol WhatsApp. Anda tetap memilih
reaksi atau layar yang ingin dibagikan. Jika pintasan mengembalikan tampilan
panggilan penuh dari tampilan kecil, lepaskan tombol, periksa tampilan, lalu
tekan pintasan lagi untuk menjalankan tindakan.

Gunakan **Menu NVDA > Peralatan > WhatsApp Companion > Label kontrol panggilan**
untuk menambahkan label sesuai bahasa WhatsApp. Masukkan satu nama kontrol
persis per baris sesuai ucapan NVDA, tanpa jenis atau status kontrolnya.
Label bawaan tetap aktif.

### Fitur opsional

| Pintasan | Tindakan |
| --- | --- |
| `Alt + Shift + N` | Aktifkan atau nonaktifkan Mode Privasi |
| `Alt + Shift + L` | Aktifkan atau nonaktifkan pembacaan pesan otomatis |
| `Shift + F8` | Buka atau tutup pengaturan WhatsApp Web Plus |
| `Alt + Shift + 8` | Aktifkan atau nonaktifkan Bersihkan Antarmuka |
| `Alt + Shift + 9` | Aktifkan atau nonaktifkan Mode Gelap Asli |

Pilihan fitur opsional Anda tetap tersimpan setelah WhatsApp dimuat ulang.

### Bantuan WhatsApp Web Plus lainnya

- [Penggunaan pertama WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#first-use)
  memandu Anda saat pertama kali menggunakan WhatsApp Web Plus.
- [Menu pengaturan WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#settings-menu)
  menjelaskan menu `Shift+F8`.
- [Mode Privasi](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#what-each-setting-does)
  menjelaskan data yang disembunyikan ketika penyaringan privasi aktif.
- [Membuka menu konteks pesan dengan NVDA](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/detailed-guide.md#open-a-message-context-menu-with-nvda)
  menjelaskan metode keyboard dan mouse NVDA.

## Memperbarui salinan WhatsApp Web Plus bawaan

Jalankan **Periksa pembaruan userscript WhatsApp Web Plus** ketika Anda ingin
Companion mencari salinan WhatsApp Web Plus yang lebih baru.

Perintah ini bekerja di latar belakang:

1. Companion menghubungi alamat resmi Greasy Fork yang sudah ditentukan.
2. Companion memeriksa versi dan rincian file.
3. Jika ada versi lebih baru, Companion mengunduh dan memeriksanya, termasuk
   memverifikasi tanda tangan dengan kunci Ed25519 tepercaya.
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

Companion menyimpan salinan di dalam paket sebagai cadangan yang aman. Jika
salinan hasil unduhan rusak, tidak lengkap, lebih lama, atau gagal dalam
pemeriksaan awal, Companion memakai salinan dari paket saat WhatsApp dibuka
kembali.

## Mendiagnosis dan memperbaiki izin WebView2

Jalankan **Diagnosa dan perbaiki izin kebijakan WebView2** setelah pemasangan
pertama di komputer ini, sebelum membuka WhatsApp. Jika izin sudah tersedia,
perbaikan tidak diperlukan. Izin tetap berlaku sampai dihapus dari Registry
atau Windows dipasang ulang. Pembaruan NVDA, Companion, dan WhatsApp biasanya
tidak memerlukan perbaikan ulang.

Bagian berikut menjelaskan pemeriksaan dan perubahan yang dilakukan.

### Apa yang diperiksa?

Sebelum membuka WhatsApp, Companion menulis satu pengaturan sementara di
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
keputusan yang berbeda. Companion tidak pernah menjalankan NVDA atau
WhatsApp sebagai administrator.

### Apa yang diubah oleh perbaikan izin?

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

Pembaruan menggunakan HTTPS dan verifikasi tanda tangan userscript dengan
kunci Ed25519 tepercaya. Jika verifikasi gagal atau tidak tersedia, Companion
tetap memakai bundel yang ada tanpa mengubahnya.

Informasi untuk pengembang dan peninjau mengenai userscript di dalam paket
tersedia di `upstream.json`, `bundle.json`, dan `THIRD_PARTY_NOTICES.md`.

## Cara kerja Companion

Bagian ini bersifat opsional. Anda tidak perlu membacanya untuk menggunakan
add-on.

Setiap kali Anda menjalankan perintah untuk membuka WhatsApp, Companion:

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
biasanya dapat terhubung kembali secara otomatis setelah halaman internal
dimuat ulang. Kesalahan ini berarti Companion sudah mencoba terhubung kembali
beberapa kali, tetapi belum berhasil memulihkan sesi yang valid.

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

Dalam mode ucapan Sesuai Permintaan, NVDA mungkin tidak membacakan pesan
dari proses yang berjalan di latar belakang. Jalankan **Laporkan hasil WhatsApp Companion terakhir**.
Output braille tetap tersedia sesuai pengaturan NVDA Anda.

### Pembaruan gagal

Companion tetap memakai salinan terpilih yang sudah lolos pemeriksaan. Periksa
koneksi internet lalu coba jalankan perintah pembaruan lagi nanti. Jika
pembaruan gagal, salinan di dalam paket tetap utuh.

## Menghapus Companion

1. Tutup WhatsApp.
2. Buka Add-on Store NVDA.
3. Temukan **WhatsApp Companion** di bagian add-on terpasang.
4. Pilih **Hapus**, lalu mulai ulang NVDA ketika diminta.

Menghapus Companion tidak menghapus WhatsApp atau userscript browser yang
terpisah. Tindakan ini juga tidak menghapus izin WebView2 yang ditambahkan oleh
perbaikan izin. Administrator harus mengubah izin tersebut.

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

Pyright bersifat opsional. Alat ini memerlukan kode sumber NVDA yang sudah disiapkan
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
pesan lengkap NVDA, dan apa yang terjadi. Jangan sertakan isi chat pribadi,
nama kontak, atau nomor telepon.

## Membaca pesan melalui jendela NVDA

Jika WhatsApp dijalankan melalui Companion, fokuskan pesan lalu tekan
**Alt+Shift+C**. Pesan lengkap ditampilkan dalam jendela teks NVDA, termasuk
tautan, daftar, dan waktu pengiriman. Pesan yang disingkat akan ditampilkan
secara lengkap terlebih dahulu. Cara ini tidak membuka pop-up browser pada
aplikasi desktop.

Tekan **Escape** untuk menutup pembaca. Tombol Tutup dan Salin disediakan jika
versi NVDA mendukungnya. Isi pesan tidak sekaligus dimasukkan ke antrean
pengumuman suara atau braille. Di browser biasa, pintasan tetap membuka tab
pembaca yang sudah tersedia.

Tetap di WhatsApp selama pesan dimuat. Berpindah aplikasi, mengganti chat, atau
mengunci Windows membatalkan permintaan yang sudah tidak berlaku. Jika pesan
melebihi batas ukuran pembaca, Anda akan mendapat pesan kesalahan. Teks tidak
akan dipotong tanpa pemberitahuan. Perbarui Companion lalu jalankan ulang
WhatsApp melalui Companion agar bundel pembaca terbaru digunakan.

## Lisensi

Add-on Companion menggunakan GPL-2.0-or-later di bawah lisensi NVDA yang
dimodifikasi dalam `COPYING.txt`. Userscript WhatsApp Web Plus yang tertanam
tetap menggunakan lisensi MIT. Asal komponen dan batas lisensi dijelaskan dalam
`THIRD_PARTY_NOTICES.md`.
