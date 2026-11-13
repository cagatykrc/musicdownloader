$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$ffmpeg = Join-Path $PSScriptRoot "vendor\ffmpeg.exe"
if (-not (Test-Path $ffmpeg)) {
    Write-Error "vendor\ffmpeg.exe yok. Once vendor\README.md adimlarini uygula."
}

Write-Host "==> Ikon yenile..."
python create_icon.py

$iconPath = (Resolve-Path "assets\icon.ico").Path
Write-Host "==> PyInstaller derlemesi (GUI)..."
python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name MusicDownloader `
  --icon $iconPath `
  --add-data "assets\icon.ico;assets" `
  --hidden-import yt_dlp.compat._legacy `
  --hidden-import numpy `
  --collect-submodules numpy `
  gui_app.py

$portable = Join-Path $PSScriptRoot "MusicDownloaderPortable"
if (Test-Path $portable) { Remove-Item $portable -Recurse -Force }
New-Item -ItemType Directory -Force -Path $portable | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $portable "downloads") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $portable "assets") | Out-Null

Copy-Item "dist\MusicDownloader.exe" $portable -Force
Copy-Item "vendor\ffmpeg.exe" $portable -Force
Copy-Item "songs.txt" $portable -Force
Copy-Item "assets\icon.ico" (Join-Path $portable "assets") -Force
Copy-Item "assets\icon.png" (Join-Path $portable "assets") -Force -ErrorAction SilentlyContinue

@"
Music Downloader (tasinabilir)

1) MusicDownloader.exe dosyasina cift tikla
2) Soldaki listeden sarki ekle / sil
3) Sagda sanatci + yil araligi yazip "Sarkilari bul" ile toplu ekle
4) "Indirmeyi baslat" — goz animasyonu oynar, bitince ozet gelir

Liste songs.txt olarak otomatik kaydedilir.
MP3 dosyalari downloads klasorune iner.
Python / ffmpeg kurulumu gerekmez. Internet gerekir.
"@ | Set-Content -Path (Join-Path $portable "KULLANIM.txt") -Encoding UTF8

Write-Host "==> Hazir: $portable"
Get-ChildItem $portable -Recurse | Select-Object FullName, Length | Format-Table -AutoSize
