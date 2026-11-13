# Music Downloader

YouTube üzerinden şarkı arayıp **MP3** olarak indiren masaüstü uygulaması.

- Arayüzden şarkı listesi yönetimi (txt zorunlu değil)
- Sanatçı + yıl aralığı ile MusicBrainz’ten toplu şarkı bulma
- İndirme sırasında ASCII göz animasyonu
- Taşınabilir `.exe` paketi (Python kurulumu olmadan)

> Yalnızca kendi içeriğin / yasal olarak indirme hakkın olan içerik için kullan.

---

## Ekran görüntüsü / akış

1. Listeye şarkı ekle **veya** sağdan sanatçı + yıl ile toplu bul  
2. **İndirmeyi başlat**  
3. Göz animasyonu oynar, bitince özet log gelir  

---

## Hızlı başlangıç (geliştirici)

### Gereksinimler

- Windows 10/11
- Python 3.11+
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) → `vendor/ffmpeg.exe` olarak koy

```text
musicdownloader/
├── gui_app.py
├── download.py
├── catalog.py
├── eye_anim.py
├── win_theme.py
├── assets/
├── vendor/
│   └── ffmpeg.exe      ← sen ekliyorsun (repoda yok)
└── requirements.txt
```

### Kurulum

```bash
pip install -r requirements.txt
```

`ffmpeg.exe` dosyasını `vendor/` klasörüne kopyala.

### Çalıştırma

```bash
python gui_app.py
```

veya

```bash
python download.py
```

CLI için:

```bash
python download.py --cli -f songs.example.txt
```

---

## Taşınabilir paket (exe)

```powershell
# Önce vendor\ffmpeg.exe hazır olmalı
powershell -ExecutionPolicy Bypass -File .\build_portable.ps1
```

Çıktı: `MusicDownloaderPortable/`

| Dosya | Açıklama |
|--------|----------|
| `MusicDownloader.exe` | Uygulama |
| `ffmpeg.exe` | MP3 dönüşümü |
| `songs.txt` | Liste (otomatik güncellenir) |
| `downloads/` | İnen MP3’ler |
| `KULLANIM.txt` | Kısa kullanım |

---

## Proje yapısı

| Dosya | Rol |
|--------|-----|
| `gui_app.py` | Ana arayüz |
| `download.py` | yt-dlp ile indirme (5 paralel) |
| `catalog.py` | MusicBrainz sanatçı/yıl arama |
| `eye_anim.py` | İndirme animasyonu |
| `win_theme.py` | Koyu başlık çubuğu / DPI |
| `create_icon.py` | İkon üretimi |
| `build_portable.ps1` | PyInstaller + portable klasör |
| `songs.example.txt` | Örnek liste |

`build/`, `dist/`, `MusicDownloaderPortable/`, `downloads/` ve `vendor/ffmpeg.exe` bilerek repoya **alınmaz**.

---

## Kullanım (arayüz)

**Sol — İndirme listesi**  
Şarkı yaz → **Ekle**. Sil / temizle ile yönet.

**Sağ — Sanatçıdan bul**  
Sanatçı adı + başlangıç/bitiş yılı → **Şarkıları bul** → seçilenleri veya tümünü listeye ekle.

**Alt**  
**İndirmeyi başlat** → animasyon → özet. MP3’ler `downloads/` içine iner.

---

## Notlar

- İndirme hızı internetine ve YouTube’a bağlıdır; varsayılan **5 paralel** indirme vardır.
- Çok agresif paralellik geçici engellere yol açabilir; gerekirse `download.py` içindeki `DOWNLOAD_WORKERS` değerini düşür.
- Sanatçı araması MusicBrainz API kullanır (ücretsiz, ~1 istek/sn).

---

## Lisans

MIT — bkz. [LICENSE](LICENSE)
