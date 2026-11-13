@echo off
cd /d "%~dp0"
if exist "MusicDownloaderPortable\MusicDownloader.exe" (
  start "" "MusicDownloaderPortable\MusicDownloader.exe" %*
) else (
  python download.py %*
)
