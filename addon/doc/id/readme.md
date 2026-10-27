# WhatsApp Companion

WhatsApp Companion menghadirkan fitur aksesibilitas WhatsApp Web Plus ke aplikasi WhatsApp dari Microsoft Store. Add-on NVDA ini mendukung WhatsApp Stable dan WhatsApp Beta di Windows.

Anda tidak memerlukan Tampermonkey.

## Mana yang perlu saya gunakan?

**Aplikasi Microsoft Store:** gunakan WhatsApp Companion bersama NVDA.

**Browser:** gunakan [WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus) bersama Tampermonkey.

Anda boleh menggunakan keduanya jika memakai WhatsApp di kedua tempat. Masing-masing diperbarui secara terpisah.

## Yang Anda perlukan

Windows 10 atau Windows 11

NVDA 2025.1 sampai NVDA 2026.2

WhatsApp Stable atau WhatsApp Beta dari Microsoft Store

Paket terbaru `whatsappWebPlusCompanion-<versi>.nvda-addon`

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
2. Pilih **Tools**, lalu **WhatsApp Companion**.
3. Pilih **Diagnosa dan perbaiki izin kebijakan WebView2**.
4. Ikuti petunjuk yang diucapkan NVDA dan setujui perbaikan jika diperlukan.
5. Izinkan perbaikan ketika Windows meminta persetujuan administrator.

Jika NVDA mengatakan bahwa perbaikan tidak diperlukan, lanjutkan ke bagian berikutnya. Jika perbaikan diperlukan, tunggu sampai NVDA mengonfirmasi bahwa perbaikan berhasil.

Biasanya langkah ini cukup dilakukan sekali. Izin tetap berlaku setelah Windows dimulai ulang atau NVDA, Companion, dan WhatsApp diperbarui. Jalankan perbaikan lagi jika izin dihapus dari Registry Windows atau Windows dipasang ulang.

Jika Companion sudah pernah berfungsi di komputer ini, pembaruan biasa tidak memerlukan perbaikan izin ulang.

## Membuka WhatsApp dengan Companion

1. Pastikan WhatsApp sudah tertutup.
2. Tekan `NVDA + N`.
3. Pilih **Tools**, lalu **WhatsApp Companion**.
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

Buka **Menu NVDA > Tools > WhatsApp Companion** untuk membuka WhatsApp atau mengelola Companion.

**Mengulang pesan:** pilih **Laporkan hasil WhatsApp Companion terakhir** jika Anda melewatkan hasil atau menggunakan mode ucapan On-demand di NVDA.

**Menutup WhatsApp:** tutup seperti biasa. Jika masih berjalan, gunakan **Tutup paksa semua proses WhatsApp dari Microsoft Store**. Tindakan ini dapat memutus panggilan atau transfer dan menghilangkan teks yang belum dikirim.

**Membaca pesan lengkap:** fokuskan sebuah pesan dan tekan `Alt + Shift + C` untuk membukanya di jendela baca NVDA. Tekan `Escape` untuk menutupnya.

**Mengubah pengaturan:** tekan `Shift + F8` di WhatsApp.

### Membaca pesan

**Bacakan pesan baru secara otomatis** mengumumkan pesan baru. **Monitor aktivitas chat** mengumumkan perubahan status seperti Terkirim, Disampaikan, dan Dibaca, serta aktivitas chat. Kedua pengaturan ini dapat diaktifkan atau dimatikan secara terpisah.

Alt+Shift+C membuka teks pesan hanya-baca tanpa pembungkusan baris. Panah Atas dan Bawah mengikuti baris asli pesan. Baris panjang bergulir secara horizontal. Gunakan **Salin pesan** untuk menyalin isi pesan sebagai teks biasa tanpa judul atau waktu. Gunakan **Tampilan berformat** untuk tampilan yang membungkus baris dan tautan yang dapat dibuka. Escape menutup jendela baca.

### Meninjau pesan dengan NVDA

Gunakan perintah review NVDA untuk membaca karakter, kata, atau baris pada pesan dan kontrol WhatsApp yang didukung, termasuk saat berada di Focus Mode. Ini membantu ketika NVDA sebelumnya hanya menyebut **blank** meskipun pesan atau tombol memiliki nama yang bisa dibaca. Gunakan perintah sesuai tata letak keyboard NVDA Anda.

Companion memakai nama pesan atau kontrol yang tersedia bila diperlukan. Tombol dan tab filter yang didukung dapat ditinjau, termasuk jumlah pesan belum dibaca yang berubah. Mode Privasi tetap dihormati dan kolom pengetikan tetap bekerja seperti biasa. Dukungan ini belum mencakup setiap jenis menu atau kontrol.

Untuk pesan dengan **Baca selengkapnya**, tekan `Shift+Enter`. Teks yang diperluas tetap menyertakan pengirim dan waktu. Caption album foto juga dibaca bersama rincian pesan, dengan awalan **Keterangan:** atau **Caption:**.

### Menavigasi chat dan menu

Tekan `Alt+1` untuk kembali ke chat yang diingat dalam daftar chat, lalu gunakan panah untuk melanjutkan navigasi. Ketika Escape menutup chat pribadi, grup, channel, atau pengumuman komunitas, NVDA mengumumkan bahwa chat sudah ditutup. Menutup menu saja tidak memicu pengumuman ini.

**Jaga menu pesan tetap di dalam jendela** membantu menu tetap terbuka pada jendela kecil. Pengaturan ini aktif secara bawaan dan dapat diubah melalui **Shift+F8 > Aksesibilitas**.

### Mengikuti unduhan

Saat WhatsApp menampilkan progres unduhan dokumen, NVDA mengumumkan persentasenya secara berkala. Unduhan memakai label bernomor agar nama file tidak dibaca keras. Fokus tidak berpindah. Pengumuman 100 persen mengikuti indikator transfer WhatsApp, bukan konfirmasi bahwa file sudah tersimpan.

### Membaca stiker dengan AI

Baca Stiker meminta penyedia AI mendeskripsikan stiker yang Anda pilih. Fitur ini mati secara bawaan dan belum memiliki pintasan. Urutan penyedia adalah Gemini, Groq, Cloudflare Workers AI, lalu Custom, OpenAI-compatible.

1. Buka **Shift+F8 > Aksesibilitas > Baca Stiker**, lalu aktifkan fiturnya.
2. Pilih **Atur penyedia AI dan API key**, tentukan penyedia, dan masukkan kredensialnya. Custom juga memerlukan alamat HTTPS dan model yang dapat membaca gambar.
3. Simpan pengaturan, lalu tetapkan pintasan **Baca Stiker** melalui **Pemetaan ulang pintasan**.
4. Fokuskan pesan stiker atau tombol stikernya, tekan pintasan, lalu tunggu deskripsinya.

Saat pintasan digunakan, hanya stiker pada pesan yang difokuskan yang dikirim, maksimal enam stiker berbeda. Stiker yang sama dideskripsikan sekali beserta jumlahnya, dan stiker berbeda diberi nomor Stiker 1, Stiker 2, dan seterusnya. Fokus boleh berpindah dalam chat yang sama. Pergantian chat, bahasa, atau pengaturan membatalkan permintaan sebelumnya. Hasil dibaca sekali dan tidak mengganti label pesan. Deskripsi AI bisa keliru.

Companion terhubung langsung ke penyedia di latar belakang. Tidak diperlukan ekstensi browser atau server tambahan. Key dienkripsi di profil WhatsApp yang terpisah dari profil browser. Kosongkan kolom key untuk mempertahankan key tersimpan. Menghapus data situs dapat menghilangkannya. Enkripsi tidak melindungi key dari script halaman atau malware. Menyimpan pengaturan tidak menguji penyedia.

Animasi dibaca dari beberapa cuplikan dan bergantung pada dukungan WebView2. Perubahan singkat bisa terlewat. Jika hanya gambar diam yang dapat dibaca, hasilnya akan menjelaskan hal itu. Gambar yang tidak didukung atau permintaan yang melewati batas waktu akan dilaporkan. Rincian tersedia dalam [panduan batas teknis dan validasi Read Sticker](https://github.com/muhammadGagah/whatsapp-web-plus/blob/main/docs/read-sticker-validation.md).

### Menggunakan Gemini

Buka [Google AI Studio](https://aistudio.google.com/api-keys), masuk dengan akun Google Anda, lalu selesaikan penyiapan untuk mendapatkan API key. Salin key tersebut, lalu buka **Atur penyedia AI dan API key** pada pengaturan Baca Stiker. Pilih **Gemini**, tempel key ke kolom API key, lalu pilih **Simpan**.

### Menggunakan Cloudflare

Buka **Workers AI > Use REST API** di Cloudflare. Masukkan **Account ID** dan **API Token Workers AI** pada pengaturan Baca Stiker. Kredensial R2 tidak digunakan untuk fitur ini.

Model bawaan adalah **Llama 3.2 11B Vision**. Anda dapat mengubah **Model ID** menggunakan nama lengkap, misalnya `@cf/meta/llama-4-scout-17b-16e-instruct`. Pilih model vision yang menerima pesan berisi data URL gambar. Llama 3.2 memakai format gambarnya sendiri. Mengganti model saja mempertahankan token. Mengganti akun memerlukan token untuk akun baru.

Jika model Llama bawaan meminta persetujuan, baca ketentuan yang ditautkan dan centang kedua pernyataan hanya jika berlaku bagi Anda. Pilih **Setujui dan aktifkan model**. Setelah sukses dikonfirmasi, dialog ditutup dan hasil diumumkan. Gunakan Baca Stiker lagi untuk membaca stikernya. Jika konfirmasi tidak tiba dalam 45 detik, dialog menjelaskan bahwa hasilnya belum pasti. Menutup dialog tidak membatalkan persetujuan yang sudah diterima Cloudflare. Persetujuan untuk model lain ditangani melalui Cloudflare.

**Pratinjau persetujuan Cloudflare** dapat dipakai berulang kali untuk tutorial tanpa mengirim persetujuan. Tutup atau tekan Escape untuk kembali ke pengaturan dengan isian yang belum disimpan tetap utuh. Biaya dan batas pemakaian penyedia tetap berlaku untuk permintaan stiker yang sebenarnya.

### Pemulihan koneksi otomatis

Jika koneksi Companion terputus, Companion mencoba menyambungkannya kembali. NVDA mengumumkan saat pemulihan dimulai dan apakah pemulihan berhasil. Jika gagal, Anda akan mendengar langkah berikutnya. Jika WhatsApp ditutup selama pemulihan, Companion melaporkan bahwa prosesnya berhenti. Menutup WhatsApp seperti biasa tidak memicu pengumuman ini.

Pesan tersebut menjelaskan koneksi Companion. Pesan itu tidak memastikan koneksi internet WhatsApp atau keberhasilan pengiriman pesan. Gunakan **Laporkan hasil WhatsApp Companion terakhir** bila ada pengumuman yang terlewat.

### Pengaturan bawaan

Untuk pemasangan baru, Mode Privasi, pembacaan pesan baru otomatis, pemutaran suara dengan Enter/Space, Clean Status, penyesuaian menu pesan, dan Antarmuka ringkas aktif. Pengumuman total chat belum dibaca dan Baca Stiker mati. Pembaruan mempertahankan pilihan yang sudah disimpan.

### Label kontrol panggilan

Pilih **Menu NVDA > Tools > WhatsApp Companion > Label kontrol panggilan** untuk menambahkan label sesuai bahasa WhatsApp. Anda dapat menyesuaikan label jawab, tolak, kamera, mikrofon, reaksi, angkat/turunkan tangan, berbagi layar, dan akhiri panggilan.

1. Pilih **Tindakan panggilan**. Kolom **Label bawaan** yang hanya bisa dibaca menampilkan label yang sudah dikenali.
2. Masukkan **Label tambahan**, satu nama kontrol persis per baris sesuai ucapan NVDA. Jangan sertakan ucapan jenis atau status kontrol, seperti "tombol" atau "tidak dicentang". Untuk kontrol dengan dua status, masukkan keduanya, misalnya label untuk membisukan dan mengaktifkan mikrofon.
3. Pilih tindakan lain untuk mengedit labelnya, lalu pilih **Simpan** untuk langsung menerapkan semua perubahan. Tidak perlu memulai ulang NVDA. Pilih **Batal** untuk membuang perubahan yang belum disimpan.

Beberapa bahasa dapat dimasukkan sekaligus tanpa memilih bahasa secara manual. Label bawaan tetap aktif. Setiap tindakan menerima maksimal 20 label tambahan, masing-masing maksimal 128 karakter. Label yang sama tidak boleh digunakan untuk tindakan berbeda. Label mikrofon juga berlaku pada tampilan panggilan kecil. Masukkan juga label **Akhiri panggilan** sesuai bahasa WhatsApp, karena pintasan panggilan aktif lainnya memakai kontrol tersebut untuk mengenali panggilan.

Kolom kosong hanya memakai label bawaan. **Hapus semua label tambahan** mengosongkan isian di dialog. Pilih **Simpan** untuk menerapkannya, atau **Batal** untuk mempertahankan label tersimpan.

Label disimpan secara global di `nvda.ini` milik NVDA, pada bagian `[whatsappCompanionCallLabels]`. Pengaturan berlaku untuk WhatsApp Stable dan Beta di semua profil NVDA, serta tetap tersimpan setelah add-on diperbarui atau dipasang ulang selama konfigurasi NVDA yang sama dipertahankan. Mengembalikan NVDA ke pengaturan bawaan pabrik atau menghapus konfigurasi tersebut menghapus label tersimpan.

### Merekam panggilan

Saat panggilan berlangsung, buka menu NVDA, pilih Tools, lalu WhatsApp Companion, kemudian Mulai rekam panggilan. Pilih Stable atau Beta, pilih mikrofon yang digunakan WhatsApp, lalu tentukan folder rekaman. Mulai setelah memberi tahu peserta panggilan. Gunakan Hentikan rekaman pada menu yang sama untuk berhenti kapan saja. Kedua perintah dapat diberi shortcut melalui Input gestures NVDA pada kategori WhatsApp Companion.

Berkas WAV berisi audio WhatsApp di kanal kiri dan mikrofon di kanal kanan. Rekaman disimpan secara lokal di folder yang dipilih, dengan lokasi awal Documents/WhatsApp Recordings. Perekam hanya menangkap audio proses WhatsApp yang dipilih beserta proses anaknya. Suara lain dari WhatsApp masih dapat ikut terekam. Suara NVDA tidak termasuk dalam tangkapan tersebut, tetapi dapat masuk melalui mikrofon bila menggunakan speaker. Gunakan headset untuk menghindarinya.

Mulai rekam panggilan tidak tersedia saat rekaman sedang berjalan atau dipersiapkan, dan bila pemeriksaan terakhir tidak menemukan panggilan. Bila status panggilan belum diketahui, perintah tetap tersedia dan memeriksa ulang saat dipilih. Setelah memilih Mulai, dialog pengaturan ditutup dan Companion membuka jendela panggilan untuk memastikan sambungannya. Jika diperlukan, tampilan penuh dipulihkan dengan satu klik pada area peserta. Rekaman hanya dimulai setelah panggilan dipastikan tersambung. Biarkan jendela panggilan aktif selama pemeriksaan. Hentikan rekaman juga membatalkan persiapan yang sedang berlangsung.

Mikrofon direkam secara terpisah, termasuk saat dibisukan di WhatsApp. Bila jendela panggilan sudah hilang sekitar 15 detik, rekaman berhenti sendiri dan NVDA mengumumkan bahwa panggilan berakhir serta lokasi berkas tersimpan. Jendela panggilan yang diminimalkan atau pemeriksaan yang tidak pasti tidak pernah menghentikan rekaman. Rekaman juga berhenti saat proses WhatsApp yang dipilih keluar, NVDA keluar, sesi dikunci, desktop aman terbuka, atau batas empat jam tercapai. Jika terjadi kesalahan, sebagian rekaman mungkin tersimpan. Lokasinya akan diumumkan jika tersedia.

Perekaman memerlukan Windows build 20348 atau yang lebih baru, izin akses mikrofon untuk aplikasi desktop, serta Windows PowerShell yang dapat menjalankan Add-Type. Helper berjalan dengan execution policy Bypass hanya untuk prosesnya sendiri, sehingga kebijakan bawaan PowerShell Restricted tidak memblokirnya dan tidak ada pengaturan sistem yang diubah. Tidak perlu memasang ekstensi browser, encoder, atau aplikasi perekam tambahan. Jika penangkapan khusus proses gagal, perekam melaporkan kesalahan tanpa beralih ke audio seluruh sistem. Merekam panggilan di aplikasi desktop hanya tersedia melalui Companion. Di browser, WhatsApp Web Plus memiliki menu Rekam panggilan sendiri.

### Pintasan panggilan

Lihat [daftar pintasan lengkap](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#pintasan-keyboard-whatsapp) untuk navigasi, panggilan masuk, dan fitur tambahan.

Gunakan shortcut ini saat jendela panggilan WhatsApp aktif. Tekan `Alt + Tab` untuk berpindah ke jendela tersebut bila perlu.

Perintah panggilan hanya muncul dalam **NVDA > Pilihan > Input gestures > WhatsApp Companion** bila dialog dibuka dari WhatsApp. Fokuskan WhatsApp dahulu. Perintah global seperti Luncurkan WhatsApp tetap tersedia di aplikasi lain. Gestur kustom panggilan dari versi sebelumnya perlu ditetapkan ulang karena perintah berpindah ke app module.

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

Jika shortcut panggilan tidak menemukan kontrol pada tampilan kecil, Companion dapat memulihkan tampilan penuh dengan satu klik pada area peserta. Lepaskan tombol dan tunggu hasilnya, lalu tekan shortcut lagi untuk menjalankan perintah. Klik mengikuti posisi jendela panggilan yang telah diperiksa. Berpindah jendela membatalkan pemulihan. Jika pemulihan gagal, buka tampilan penuh secara manual.

Shortcut reaksi membuka kontrol reaksi WhatsApp. Pilih reaksi yang ingin dikirim. Saat memulai berbagi layar, pilih apa yang akan dibagikan di WhatsApp. Tekan `Ctrl + Alt + S` lagi untuk berhenti berbagi.

## Menetapkan shortcut

Pilih **Shift+F8 > Pemetaan ulang pintasan**, lalu pilih **Baca Stiker**, **Rekam pesan suara**, **Chat sebelumnya**, **Chat berikutnya**, **Mulai panggilan suara**, atau **Mulai panggilan video**. Ketik kombinasi seperti `Alt+C` atau `Alt+V`, lalu pilih **Simpan**. Gunakan Ctrl atau Alt, boleh ditambah Shift, diikuti huruf, angka, tombol tanda baca seperti koma atau titik, F1–F12, atau ArrowUp/Down/Left/Right. Huruf merujuk ke posisi fisik tombol keyboard. Kosongkan kolom untuk menonaktifkan tindakan. **Kembalikan bawaan** hanya mengubah kolom. Pilih Simpan untuk menerapkan atau Batal/Escape untuk membuang perubahan. Pengaturan lama tetap dipertahankan. Shortcut panggilan baru belum ditetapkan. Bawaan rekaman adalah Alt+M. Chat sebelumnya/berikutnya Alt+ArrowUp/Alt+ArrowDown, awalnya nonaktif.

Kombinasi ganda, perintah tetap script/Companion, dan shortcut bawaan WhatsApp ditolak. Shortcut browser, sistem, NVDA, atau ekstensi masih dapat lebih diutamakan. AltGr tidak didukung. Panggilan suara/video memakai tombol yang tersedia di header percakapan aktif, dikenali dari ikon tanpa bergantung bahasa. Tidak perlu mengisi Custom language strings. Jika tombol tidak tersedia atau ambigu, pesan pemberitahuan dibacakan tanpa memulai panggilan.

### Merekam shortcut

Dalam Pemetaan ulang pintasan, pilih aksi lalu **Rekam shortcut**. NVDA harus berada dalam **focus mode** agar script menerima tombolnya. Jika masih dalam browse mode, tekan **NVDA+Spasi** sebelum merekam. Tekan kombinasi seperti **Alt+koma**, lalu pilih **Simpan**. Escape membatalkan perekaman. Tab menghentikan perekaman dan berpindah ke kontrol berikutnya. Kombinasi masih dapat diketik secara manual. Tombol yang ditangani lebih dahulu oleh browser, sistem, atau NVDA tidak dapat direkam oleh script.

## Daftar shortcut dalam pengaturan

Pilih **Shift+F8 > Daftar shortcut** untuk membaca shortcut bawaan script yang dikelompokkan menurut fungsi. Daftar ini menampilkan bawaan. Penetapan Anda tetap terlihat dalam **Pemetaan ulang pintasan**. Companion membuka jendela baca native NVDA dengan heading yang dapat dinavigasi. Tekan Escape untuk menutupnya.

## Shortcut bawaan script

Ini adalah bawaan, bukan penetapan shortcut yang Anda simpan.

### Navigasi

| Shortcut | Fungsi |
| --- | --- |
| `Alt+Shift+1` | Buka Chat |
| `Alt+Shift+2` | Buka Status atau Pembaruan |
| `Alt+Shift+3` | Buka Komunitas |
| `Alt+Shift+4` | Buka Saluran |
| `Alt+Shift+5` | Buka Meta AI |
| `Alt+1` | Pindah ke daftar chat |
| `Alt+2` | Pindah ke pesan terakhir |
| `Alt+3` | Pindah ke pesan pertama yang belum dibaca |
| `Alt+Shift+D` | Berpindah antara pesan dan kolom penulisan |
| `Alt+T` | Baca judul chat. Tekan dua kali dengan cepat untuk mengaktifkan atau menonaktifkan pemantauan aktivitas chat |
| `Alt+0` | Tutup pemutar media atau promosi aplikasi desktop |

### Pesan dan pemformatan

| Shortcut | Fungsi |
| --- | --- |
| `Alt+Shift+C` | Buka pesan yang difokuskan di jendela baca |
| `Shift+Enter` | Perluas Baca selengkapnya pada pesan yang difokuskan |
| `Alt+F10` | Buka pilihan format untuk teks yang dipilih di kolom penulisan |
| `Enter / Space` | Putar atau jeda pesan suara yang difokuskan jika pengaturan pemutaran dengan keyboard diaktifkan (aktif secara bawaan) |

### Pengaturan dan tampilan

| Shortcut | Fungsi |
| --- | --- |
| `Shift+F8` | Buka atau tutup pengaturan |
| `Alt+Shift+N` | Aktifkan atau nonaktifkan Mode Privasi |
| `Alt+Shift+L` | Aktifkan atau nonaktifkan pembacaan pesan otomatis |
| `Alt+Shift+8` | Aktifkan atau nonaktifkan Tampilan Bersih |
| `Alt+Shift+9` | Aktifkan atau nonaktifkan Mode Gelap Asli |

### Panggilan masuk

| Shortcut | Fungsi |
| --- | --- |
| `Ctrl+Alt+A` | Terima panggilan masuk ketika tombolnya tersedia |
| `Ctrl+Alt+D` | Tolak panggilan masuk ketika tombolnya tersedia |

### Bawaan yang dapat dipetakan ulang

| Shortcut | Fungsi |
| --- | --- |
| `Alt+M` | Rekam pesan suara. Aktif secara bawaan |
| `Alt+ArrowUp` | Chat sebelumnya. Nonaktif hingga diatur dalam Pemetaan ulang pintasan |
| `Alt+ArrowDown` | Chat berikutnya. Nonaktif hingga diatur dalam Pemetaan ulang pintasan |
| Belum ditetapkan | Mulai panggilan suara: belum memiliki shortcut bawaan. Atur dalam Pemetaan ulang pintasan |
| Belum ditetapkan | Mulai panggilan video: belum memiliki shortcut bawaan. Atur dalam Pemetaan ulang pintasan |
| Belum ditetapkan | Baca Stiker: belum memiliki shortcut bawaan. Atur dalam Pemetaan ulang pintasan |

## Shortcut bawaan WhatsApp

Ini adalah shortcut WhatsApp di WebView2. Sebagian perintah bergantung pada pesan yang dipilih atau panel yang aktif.

| Shortcut | Fungsi |
| --- | --- |
| `Ctrl+Shift+U` | Tandai belum dibaca |
| `Ctrl+Shift+M` | Bisukan chat |
| `Ctrl+Shift+A` | Arsipkan chat |
| `Ctrl+Alt+Shift+P` | Sematkan chat |
| `Ctrl+Alt+/` | Cari |
| `Ctrl+Shift+F` | Cari dalam chat |
| `Ctrl+Alt+N` | Chat baru |
| `Ctrl+]` | Chat berikutnya |
| `Ctrl+[` | Chat sebelumnya |
| `Ctrl+Cmd+Shift+L` | Tambahkan chat ke daftar |
| `Escape` | Tutup chat |
| `Ctrl+Shift+N` | Grup baru |
| `Ctrl+Alt+P` | Profil dan Info |
| `Shift+.` | Tingkatkan kecepatan pesan suara yang dipilih |
| `Shift+,` | Kurangi kecepatan pesan suara yang dipilih |
| `Alt+S` | Pengaturan |
| `Ctrl+Alt+E` | Panel emoji |
| `Ctrl+Alt+G` | Panel GIF |
| `Ctrl+Alt+S` | Panel stiker |
| `Alt+K` | Pencarian lanjutan |
| `Alt+L` | Kunci aplikasi |
| `Alt+I` | Buka info chat |
| `Ctrl+Shift+B` | Blokir chat |
| `Alt+R` | Balas |
| `Ctrl+Alt+R` | Balas secara pribadi |
| `Ctrl+Alt+D` | Teruskan |
| `Alt+8` | Beri bintang pada pesan |
| `Alt+A` | Buka pilihan lampiran |
| `Ctrl+Alt+Shift+R` | Mulai merekam pesan suara |
| `Alt+P` | Jeda perekaman pesan suara |
| `Ctrl+Enter` | Kirim pesan suara |
| `Ctrl+ArrowUp` | Edit pesan terakhir |
| `Ctrl++` | Perbesar tampilan |
| `Ctrl+-` | Perkecil tampilan |
| `Ctrl+0` | Atur ulang zoom |
| `Ctrl+1..9` | Buka chat |

### Panggilan

Gunakan shortcut ini ketika kontrol panggilan tersedia. Tombol yang sama dapat memiliki fungsi berbeda di chat.

| Shortcut | Fungsi |
| --- | --- |
| `Ctrl+Alt+V` | Aktifkan atau nonaktifkan kamera |
| `Ctrl+Alt+M` | Bisukan atau aktifkan mikrofon |
| `Ctrl+Alt+R` | Reaksi |
| `Ctrl+Alt+H` | Angkat tangan |
| `Ctrl+Alt+S` | Berbagi layar |
| `Ctrl+Alt+W` | Akhiri panggilan |

## Memperbarui WhatsApp Web Plus di dalam Companion

1. Buka **Menu NVDA > Tools > WhatsApp Companion**.
2. Pilih **Periksa pembaruan userscript WhatsApp Web Plus**.
3. Tunggu sampai NVDA melaporkan hasilnya.
4. Tutup WhatsApp sepenuhnya, lalu buka kembali melalui Companion.

Langkah ini memperbarui salinan WhatsApp Web Plus yang digunakan Companion. Untuk memperbarui add-on Companion, pasang paket `.nvda-addon` yang lebih baru. Jika Anda juga memakai WhatsApp Web Plus di browser, perbarui pemasangan tersebut secara terpisah.

Versi sumber saat ini adalah **2026.10.26**, dengan WhatsApp Web Plus **2026.10.26**. Lihat [riwayat perubahan Companion](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/changelog.md) untuk rinciannya.

## Pemecahan masalah

**WhatsApp sudah berjalan:** tutup sepenuhnya, lalu buka melalui Companion.

**WhatsApp tidak ditemukan:** pastikan aplikasi Stable atau Beta yang dipilih sudah terpasang dari Microsoft Store.

**WhatsApp terbuka tetapi belum siap:** tunggu sampai pesan selesai dimuat. Jika NVDA melaporkan kesalahan, gunakan **Laporkan hasil WhatsApp Companion terakhir** dan catat pesan lengkapnya.

**Pintasan tidak berfungsi atau koneksi terputus:** tutup WhatsApp, lalu buka kembali dari menu Companion.

**Masalah izin WebView2:** jalankan kembali **Diagnosa dan perbaiki izin kebijakan WebView2**. Jika kebijakan Windows atau pembatasan administrator menghalangi perbaikan, hubungi administrator Anda.

Baca [panduan pemecahan masalah lengkap](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#pemecahan-masalah) untuk pesan dan langkah pemulihan lainnya.

## Bantuan lainnya

Untuk panggilan native masuk, fokuskan jendela panggilan melalui Alt+Tab, lalu tekan **Ctrl+Alt+A** untuk menjawab atau **Ctrl+Alt+D** untuk menolak. Companion mensyaratkan satu pasangan tombol Accept/Decline yang terlihat dan aktif di jendela itu. Akhiri panggilan tidak dianggap Tolak. Pada aplikasi lain, editor, atau AltGr, tombol diteruskan seperti biasa. Sesi secure, terkunci, dan no-write juga meneruskan tombol. Penahanan/pengulangan tombol dibatasi agar tidak segera mengaktifkan lagi. WhatsApp memberikan umpan balik hasil panggilan.

Untuk diagnostik, buka Input gestures dari WhatsApp dan tetapkan ulang gestur **Ambil diagnostik panggilan WhatsApp native** (tanpa shortcut bawaan). Saat panggilan terhubung, ambil satu snapshot. Bagian `controls` pada `WWP-CALL-SNAPSHOT` memuat semua tombol yang dikenali tanpa mengaktifkannya. Ambil snapshot lagi setelah mikrofon/kamera berubah status atau tangan diangkat, bila diperlukan. Jika tombol tidak tercatat, fokuskan tombol itu dengan Tab, pastikan navigator NVDA berada pada tombol tersebut, lalu tekan NVDA+F1, lalu salin informasi objeknya setelah menghapus identitas pribadi. Tidak perlu mengambil NVDA+F1 untuk semua tombol sejak awal.

Diagnostik juga mencatat tombol yang belum terpetakan pada `controls.unmapped`, termasuk ID teknis, enabled/offscreen, serta ketersediaan pola Invoke/Toggle. Nama tombol yang tidak dikenal tetap dihilangkan. Status `complete` berarti penelusuran selesai, bukan semua tombol sudah dikenali. Ketersediaan Toggle bukan status nyala/mati. Periksa identifier sebelum membagikan log karena provider dapat menyisipkan data pribadi. Jika kamera/reaksi/tangan/berbagi layar masih belum dikenali, kirim satu snapshot baru dahulu. Pemetaan aksi tidak ditambahkan hanya berdasarkan nama ID.

Ctrl+Alt+S mengaktifkan Start screen sharing atau Stop screen sharing sesuai kontrol yang tersedia. Pilihan layar/jendela dan konfirmasi tetap dilakukan pengguna. Tidak ada layar yang dipilih otomatis. Penelusuran tetap mencakup seluruh jendela dengan batas node/waktu, memakai cache properti UIA per objek untuk mengurangi permintaan antarproses. Identitas dan keadaan kontrol diperiksa langsung lagi sebelum aktivasi. Log propertyCache menunjukkan apakah optimasi ini tersedia. Hasil partial tetap ditolak dan bukan izin mengaktifkan tombol.

Enam shortcut panggilan aktif mensyaratkan tombol End call dan target unik dalam host yang sama. Label bawaan berbahasa Inggris; tambahkan label sesuai bahasa WhatsApp melalui **Label kontrol panggilan**. Checkbox React (NewReactionButton) dan Start/Stop screen sharing (NewScreenShareButton) menggunakan satu aktivasi TogglePattern. Kontrol Toggle-only lainnya belum didukung. Reaksi dan berbagi layar membuka kontrol WhatsApp. Pilihan lanjut tetap dilakukan pengguna. Cobalah shortcut tersebut pada panggilan percobaan terlebih dahulu. Bila memakai WhatsAppNG, nonaktifkan sementara lalu restart NVDA agar app module tidak bertabrakan.

Panduan online berikut bersifat opsional. Anda tidak perlu membacanya untuk menyelesaikan pemasangan.

[Perintah menu Companion](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#perintah-pada-menu-whatsapp-companion)

[Rincian perbaikan izin WebView2](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#mendiagnosis-dan-memperbaiki-izin-webview2)

[Privasi dan keamanan](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#privasi-dan-keamanan)

[Panduan pengembang](https://github.com/muhammadGagah/whatsapp-web-plus-companion/blob/main/docs/detailed-guide.id.md#untuk-pengembang)

## Menghapus WhatsApp Companion

Tutup WhatsApp, buka Add-on Store NVDA, cari **WhatsApp Companion** pada daftar add-on terpasang, lalu pilih **Hapus**. Mulai ulang NVDA ketika diminta.

WhatsApp dan pemasangan WhatsApp Web Plus di browser tetap terpasang. Izin WebView2 yang sudah diperbaiki juga tetap berlaku.

## Melaporkan masalah

Gunakan [pelacak masalah Companion](https://github.com/muhammadGagah/whatsapp-web-plus-companion/issues) untuk masalah pembukaan aplikasi, koneksi, integrasi NVDA, pembaruan, atau perbaikan izin. Sertakan versi NVDA dan Windows, pilihan Stable atau Beta, perintah yang digunakan, pesan lengkap NVDA, dan hal yang terjadi.

Gunakan [pelacak masalah WhatsApp Web Plus](https://github.com/muhammadGagah/whatsapp-web-plus/issues) untuk masalah pintasan, label pesan, pembacaan Status, Mode Privasi, atau pengaturan.

Jangan sertakan isi pesan pribadi, nama kontak, atau nomor telepon.

## Terima kasih khusus

Saya sangat berterima kasih kepada para pengembang yang karyanya membantu saya membangun WhatsApp Companion. Saya belajar banyak dari proyek mereka, dan masing-masing ikut membentuk add-on ini.

[Messenger Accessibility for NVDA](https://github.com/NVDATH/messengerAccess-for-nvda/), karya para pengembang NVDATH, memperkenalkan saya pada gagasan menghubungkan add-on NVDA dengan userscript melalui sebuah jembatan. Itu add-on pertama yang saya ketahui memakai pendekatan ini alih-alih menangani semuanya dengan Python. Melihat kedua bagian itu bekerja sama membantu saya membayangkan apa yang dapat dicapai Companion.

[WhatsApp Desktop accessibility enhancements (WhatsAppNG)](https://github.com/nunotfc/WhatsAppNG), karya Nuno Costa, menjadi rujukan penting saat saya mengerjakan pintasan panggilan. Pada WhatsApp versi Microsoft Store, panggilan terbuka di jendela native terpisah yang tidak dapat dijangkau userscript. Dalam pengujian saya, pintasan untuk mengakhiri panggilan, membisukan mikrofon, dan mengganti kamera tidak berfungsi di sana. Karena itu saya membuat kontrol tersebut langsung di Companion, dan mempelajari WhatsAppNG membantu saya menemukan jalannya.

[WhatsAppPlus](https://github.com/Kostya-Gladkiy/WhatsAppPlus), karya Kostya Gladkiy, mungkin merupakan inspirasi terbesar saya. Banyak pintasan dan fitur dalam proyek ini mencerminkan pengalaman yang saya hargai dari add-on miliknya. Awalnya saya berencana menamai add-on ini WhatsApp Web Plus Companion dan sudah mendapat izin Kostya untuk memakai nama itu. Kemudian seorang teman menyarankan nama WhatsApp Companion agar tidak membingungkan pengguna, sehingga nama itulah yang dipakai. Saya sangat berterima kasih kepada Kostya atas pengertian dan dukungannya.

Terakhir, saya ingin berterima kasih kepada para pengembang dan kontributor [Instant Translate](https://github.com/addonFactory/instantTranslate). Meskipun tujuannya berbeda dari proyek ini, mempelajarinya mengajarkan banyak hal kepada saya tentang pengembangan add-on NVDA. Pelajaran itu terus saya bawa saat mengerjakan Companion.

Terima kasih kepada kalian semua karena telah membagikan karya kalian dan memberi pengembang lain, termasuk saya, kesempatan untuk belajar.

## Lisensi

Companion menggunakan GPL-2.0-or-later di bawah lisensi NVDA yang dimodifikasi dalam `COPYING.txt`. Userscript WhatsApp Web Plus yang disertakan tetap menggunakan lisensi MIT. Rincian komponen tersedia di `THIRD_PARTY_NOTICES.md`.
