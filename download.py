#!/usr/bin/env python3
"""YouTube'dan şarkı arayıp MP3 olarak indirir (taşınabilir)."""

from __future__ import annotations

import argparse
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from yt_dlp import YoutubeDL


LogFn = Callable[[str], None]

# Aynı anda kaç şarkı (çok yüksek = YouTube geçici engel riski)
DOWNLOAD_WORKERS = 5


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_ffmpeg() -> str | None:
    local = app_dir() / "ffmpeg.exe"
    if local.is_file():
        return str(local)
    return None


def read_songs_from_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    songs: list[str] = []
    for line in text.splitlines():
        song = line.strip()
        if song and not song.startswith("#"):
            songs.append(song)
    return songs


def save_songs_to_file(path: Path, songs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(s.strip() for s in songs if s.strip())
    if body:
        body += "\n"
    path.write_text(body, encoding="utf-8")


def default_songs_path() -> Path:
    return app_dir() / "songs.txt"


def read_songs_from_input() -> list[str]:
    print("Şarkı isimlerini gir (her satıra bir tane).")
    print("Bitirmek için boş satır bırak veya Ctrl+Z sonra Enter:\n")
    songs: list[str] = []
    while True:
        try:
            line = input().strip()
        except EOFError:
            break
        if not line:
            break
        songs.append(line)
    return songs


def resolve_songs(args: argparse.Namespace | None = None) -> tuple[list[str], Path]:
    """Şarkı listesi ve çıktı klasörünü çözümle."""
    base = app_dir()
    output_dir = base / "downloads"
    songs: list[str] = []

    if args is None:
        default_list = base / "songs.txt"
        if default_list.exists():
            songs = read_songs_from_file(default_list)
        return songs, output_dir

    output_dir = args.output if args.output else output_dir

    if args.file:
        song_file = args.file
        if not song_file.is_absolute():
            song_file = (Path.cwd() / song_file).resolve()
            if not song_file.exists():
                song_file = (base / args.file).resolve()
        if not song_file.exists():
            raise FileNotFoundError(f"Dosya bulunamadı: {args.file}")
        songs = read_songs_from_file(song_file)
    elif args.songs:
        songs = [s.strip() for s in args.songs if s.strip()]
    else:
        default_list = base / "songs.txt"
        if default_list.exists():
            songs = read_songs_from_file(default_list)
        else:
            songs = read_songs_from_input()

    return songs, output_dir


def build_ydl_opts(output_dir: Path, quiet: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    opts: dict = {
        # m4a genelde daha hızlı iner + dönüşür
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "noplaylist": True,
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": True,
        "default_search": "ytsearch1",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "concurrent_fragment_downloads": 8,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 20,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "restrictfilenames": False,
        "windowsfilenames": True,
    }
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    return opts


def _download_one(song: str, output_dir: Path, quiet: bool) -> None:
    """Tek şarkı; her çağrı kendi YoutubeDL örneğini kullanır (thread-safe)."""
    opts = build_ydl_opts(output_dir, quiet=quiet)
    with YoutubeDL(opts) as ydl:
        ydl.download([f"ytsearch1:{song}"])


def download_songs(
    songs: list[str],
    output_dir: Path,
    log: LogFn | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    workers: int = DOWNLOAD_WORKERS,
) -> tuple[int, int, list[str]]:
    """Şarkıları indir. Dönüş: (ok, fail, log_lines)."""
    lines: list[str] = []
    lock = threading.Lock()

    def emit(msg: str) -> None:
        with lock:
            lines.append(msg)
            if log:
                log(msg)
            else:
                print(msg)

    if not songs:
        emit("İndirilecek şarkı bulunamadı.")
        return 0, 0, lines

    if not find_ffmpeg():
        emit("Uyarı: Yanında ffmpeg.exe bulunamadı. MP3 dönüşümü başarısız olabilir.")

    total = len(songs)
    workers = max(1, min(workers, total))
    quiet = log is not None
    ok = 0
    fail = 0
    done = 0

    emit(f"{total} şarkı indirilecek ({workers} paralel) → {output_dir.resolve()}")
    emit("")

    def job(song: str) -> tuple[str, Exception | None]:
        try:
            _download_one(song, output_dir, quiet=quiet)
            return song, None
        except Exception as exc:  # noqa: BLE001
            return song, exc

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(job, song): song for song in songs}
        for fut in as_completed(futures):
            song, err = fut.result()
            done += 1
            if on_progress:
                on_progress(done, total, song)
            if err is None:
                ok += 1
                emit(f"[{done}/{total}] ✓ {song}")
            else:
                fail += 1
                emit(f"[{done}/{total}] ✗ {song}")
                emit(f"    {err}")

    emit("")
    emit(f"Bitti. Başarılı: {ok} | Başarısız: {fail}")
    if total:
        rate = 100.0 * ok / total
        emit(f"Başarı oranı: %{rate:.0f}")
    return ok, fail, lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Şarkı isimlerini YouTube'dan bulup MP3 olarak indirir.",
    )
    parser.add_argument("-f", "--file", type=Path, help="Şarkı listesi .txt")
    parser.add_argument("-o", "--output", type=Path, help="İndirme klasörü")
    parser.add_argument("songs", nargs="*", help="Doğrudan şarkı isimleri")
    parser.add_argument("--cli", action="store_true", help="Konsol modu (GUI yok)")
    return parser.parse_args()


def pause_if_frozen() -> None:
    if getattr(sys, "frozen", False):
        try:
            input("\nÇıkmak için Enter'a bas...")
        except EOFError:
            pass


def main() -> int:
    args = parse_args()

    # Varsayılan: GUI. --cli ile konsol.
    if not args.cli and not args.file and not args.songs:
        from gui_app import run_gui

        return run_gui()

    try:
        songs, output_dir = resolve_songs(args)
    except FileNotFoundError as exc:
        print(exc)
        pause_if_frozen()
        return 1

    if not songs:
        print("Hiç şarkı girilmedi.")
        pause_if_frozen()
        return 1

    ok, fail, _ = download_songs(songs, output_dir)
    pause_if_frozen()
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
