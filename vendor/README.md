# vendor/

Bu klasöre **ffmpeg.exe** koy.

1. https://www.gyan.dev/ffmpeg/builds/ adresinden `ffmpeg-release-essentials.zip` indir  
2. Zip içinden `bin/ffmpeg.exe` dosyasını buraya kopyala  
3. Yol: `vendor/ffmpeg.exe`

Portable derleme (`build_portable.ps1`) bu dosyayı pakete kopyalar.
Uygulama çalışırken de önce yanındaki, yoksa `vendor/` altındaki ffmpeg’i arar.
