#!/usr/bin/env python3
"""Liste yönetimi + sanatçı keşfi, indirme sırasında göz animasyonu."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkf
from pathlib import Path
from tkinter import ttk

from catalog import discover_artist_tracks
from download import (
    app_dir,
    default_songs_path,
    download_songs,
    read_songs_from_file,
    save_songs_to_file,
)
from eye_anim import EyePanel
from win_theme import (
    apply_dark_titlebar,
    configure_dark_ttk,
    disable_maximize,
    enable_dpi_awareness,
)

BG = "#0e1014"
FG = "#ebe7e0"
MUTED = "#8b8680"
ACCENT = "#c4a35a"
OK = "#7dba7d"
BAD = "#d27a7a"
SURFACE = "#171a21"
FIELD = "#1c2028"
LINE = "#2a2e38"

WIN_W, WIN_H = 860, 600
RESULT_W, RESULT_H = 660, 440


def _bundled_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return Path(__file__).resolve().parent


class App:
    @staticmethod
    def _resolve_icon() -> Path | None:
        candidates = [
            app_dir() / "assets" / "icon.ico",
            _bundled_dir() / "assets" / "icon.ico",
            Path(__file__).resolve().parent / "assets" / "icon.ico",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Music Downloader")
        self.root.configure(bg=BG)

        try:
            self.root.tk.call("tk", "scaling", 1.0)
        except Exception:  # noqa: BLE001
            pass

        configure_dark_ttk(self.root)
        apply_dark_titlebar(self.root)
        disable_maximize(self.root)
        self.root.after(50, lambda: apply_dark_titlebar(self.root))
        self.root.after(80, lambda: disable_maximize(self.root))

        icon = self._resolve_icon()
        if icon is not None:
            try:
                self.root.iconbitmap(default=str(icon))
            except Exception:  # noqa: BLE001
                pass

        self.queue: queue.Queue = queue.Queue()
        self._closing = False
        self._busy = False
        self.songs: list[str] = []
        self._songs_path = default_songs_path()
        self._found_queries: list[str] = []

        fams = set(tkf.families())
        ui = next(
            (f for f in ("Segoe UI", "Candara", "Calibri", "Arial") if f in fams),
            "Arial",
        )
        mono = next(
            (f for f in ("Cascadia Mono", "Consolas", "Courier New") if f in fams),
            "Courier",
        )
        self.font_title = tkf.Font(family=ui, size=18, weight="bold")
        self.font_section = tkf.Font(family=ui, size=11, weight="bold")
        self.font_ui = tkf.Font(family=ui, size=11)
        self.font_small = tkf.Font(family=ui, size=10)
        self.font_btn = tkf.Font(family=ui, size=10)
        self.font_mono = tkf.Font(family=mono, size=10)
        self._style_ttk()

        self.status = tk.StringVar(value="")
        self.setup_hint = tk.StringVar(value="Şarkı ekle veya sağdan sanatçı ara")
        self.list_count = tk.StringVar(value="0 şarkı")
        self.found_count = tk.StringVar(value="")
        self.artist_var = tk.StringVar()
        self.year_from_var = tk.StringVar(value="2000")
        self.year_to_var = tk.StringVar(value="2024")
        self.song_entry_var = tk.StringVar()

        self._build_setup()
        self._build_loading()
        self._build_results()

        self.root.protocol("WM_DELETE_WINDOW", self._force_close)
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<F11>", lambda e: "break")

        self._load_initial_songs()
        self._show_setup()
        self.root.after(80, self._poll_queue)
        self._center(WIN_W, WIN_H)

    def _style_ttk(self) -> None:
        style = ttk.Style(self.root)
        style.configure(
            "Ghost.TButton",
            background=FIELD,
            foreground=FG,
            borderwidth=0,
            focuscolor=ACCENT,
            padding=(12, 7),
            font=self.font_btn,
        )
        style.map(
            "Ghost.TButton",
            background=[("active", LINE), ("disabled", SURFACE)],
            foreground=[("disabled", MUTED)],
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#0e1014",
            borderwidth=0,
            padding=(16, 8),
            font=self.font_btn,
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#d4b56a"), ("disabled", "#5a5240")],
            foreground=[("disabled", "#2a2618")],
        )

    def _center(self, w: int, h: int) -> None:
        x = (self.root.winfo_screenwidth() - w) // 2
        y = max(0, (self.root.winfo_screenheight() - h) // 2 - 24)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        apply_dark_titlebar(self.root)
        disable_maximize(self.root)

    def _field(self, parent, textvariable, **kw) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=textvariable,
            bg=FIELD,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=self.font_ui,
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=ACCENT,
            **kw,
        )

    def _btn(self, parent, text, command, accent: bool = False) -> ttk.Button:
        style = "Accent.TButton" if accent else "Ghost.TButton"
        return ttk.Button(parent, text=text, command=command, style=style)

    def _listbox(self, parent, **kw) -> tuple[tk.Frame, tk.Listbox]:
        shell = tk.Frame(parent, bg=SURFACE, highlightthickness=0)
        lb = tk.Listbox(
            shell,
            bg=SURFACE,
            fg=FG,
            selectbackground=ACCENT,
            selectforeground="#0e1014",
            activestyle="none",
            highlightthickness=0,
            borderwidth=0,
            font=self.font_mono,
            exportselection=False,
            relief="flat",
            **kw,
        )
        sb = ttk.Scrollbar(
            shell,
            orient="vertical",
            style="Dark.Vertical.TScrollbar",
            command=lb.yview,
        )
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=8)
        return shell, lb

    # ── setup ────────────────────────────────────────────────

    def _build_setup(self) -> None:
        self.setup = tk.Frame(self.root, bg=BG)
        root_pad = tk.Frame(self.setup, bg=BG)
        root_pad.pack(fill="both", expand=True, padx=28, pady=22)

        # Header
        head = tk.Frame(root_pad, bg=BG)
        head.pack(fill="x", pady=(0, 18))
        tk.Label(
            head, text="Music Downloader", font=self.font_title, fg=FG, bg=BG
        ).pack(anchor="w")
        tk.Label(
            head,
            text="İndirmek istediğin şarkıları listele, sonra indir.",
            font=self.font_small,
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(4, 0))

        # Two columns
        body = tk.Frame(root_pad, bg=BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3, minsize=360)
        body.columnconfigure(1, weight=2, minsize=280)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(4, weight=1)
        right.columnconfigure(0, weight=1)

        # LEFT — queue
        left_head = tk.Frame(left, bg=BG)
        left_head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(
            left_head,
            text="İndirme listesi",
            font=self.font_section,
            fg=FG,
            bg=BG,
        ).pack(side="left")
        tk.Label(
            left_head,
            textvariable=self.list_count,
            font=self.font_small,
            fg=MUTED,
            bg=BG,
        ).pack(side="right")

        add_row = tk.Frame(left, bg=BG)
        add_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        add_row.columnconfigure(0, weight=1)
        self.song_entry = self._field(add_row, self.song_entry_var)
        self.song_entry.grid(row=0, column=0, sticky="ew", ipady=8, padx=(0, 8))
        self.song_entry.bind("<Return>", lambda e: self._add_song())
        self._btn(add_row, "Ekle", self._add_song).grid(row=0, column=1)

        list_shell, self.song_list = self._listbox(left)
        list_shell.grid(row=2, column=0, sticky="nsew")
        self.song_list.bind("<Delete>", lambda e: self._remove_selected())

        left_tools = tk.Frame(left, bg=BG)
        left_tools.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self._btn(left_tools, "Seçileni sil", self._remove_selected).pack(
            side="left", padx=(0, 6)
        )
        self._btn(left_tools, "Listeyi temizle", self._clear_songs).pack(side="left")

        # RIGHT — artist search
        tk.Label(
            right,
            text="Sanatçıdan bul",
            font=self.font_section,
            fg=FG,
            bg=BG,
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        tk.Label(
            right,
            text="İsim + yıl aralığı yaz, çıkanları listeye ekle.",
            font=self.font_small,
            fg=MUTED,
            bg=BG,
            wraplength=280,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 10))

        form = tk.Frame(right, bg=BG)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(0, weight=1)

        tk.Label(form, text="Sanatçı", font=self.font_small, fg=MUTED, bg=BG).grid(
            row=0, column=0, sticky="w"
        )
        self.artist_entry = self._field(form, self.artist_var)
        self.artist_entry.grid(row=1, column=0, sticky="ew", ipady=7, pady=(2, 10))
        self.artist_entry.bind("<Return>", lambda e: self._find_artist_tracks())

        years = tk.Frame(form, bg=BG)
        years.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        years.columnconfigure(0, weight=1)
        years.columnconfigure(2, weight=1)
        tk.Label(years, text="Başlangıç yılı", font=self.font_small, fg=MUTED, bg=BG).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(years, text="Bitiş yılı", font=self.font_small, fg=MUTED, bg=BG).grid(
            row=0, column=2, sticky="w"
        )
        self.year_from = self._field(years, self.year_from_var, justify="center")
        self.year_from.grid(row=1, column=0, sticky="ew", ipady=7, padx=(0, 6))
        tk.Label(years, text="→", fg=MUTED, bg=BG).grid(row=1, column=1)
        self.year_to = self._field(years, self.year_to_var, justify="center")
        self.year_to.grid(row=1, column=2, sticky="ew", ipady=7, padx=(6, 0))

        self.find_btn = self._btn(form, "Şarkıları bul", self._find_artist_tracks)
        self.find_btn.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        found_head = tk.Frame(right, bg=BG)
        found_head.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        tk.Label(
            found_head, text="Bulunan şarkılar", font=self.font_small, fg=MUTED, bg=BG
        ).pack(side="left")
        tk.Label(
            found_head,
            textvariable=self.found_count,
            font=self.font_small,
            fg=MUTED,
            bg=BG,
        ).pack(side="right")

        found_shell, self.found_list = self._listbox(right, selectmode=tk.EXTENDED)
        found_shell.grid(row=4, column=0, sticky="nsew")
        self.found_list.configure(selectbackground="#3a455c", selectforeground=FG)

        found_tools = tk.Frame(right, bg=BG)
        found_tools.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        self._btn(found_tools, "Seçilenleri ekle", self._add_found_selected).pack(
            side="left", padx=(0, 6)
        )
        self._btn(found_tools, "Tümünü ekle", self._add_found_all).pack(side="left")

        # Footer
        foot = tk.Frame(root_pad, bg=BG)
        foot.pack(fill="x", pady=(16, 0))
        tk.Label(
            foot,
            textvariable=self.setup_hint,
            font=self.font_small,
            fg=MUTED,
            bg=BG,
        ).pack(side="left")
        self.start_btn = self._btn(
            foot, "İndirmeyi başlat", self._start_download, accent=True
        )
        self.start_btn.pack(side="right")

    def _build_loading(self) -> None:
        self.loading = tk.Frame(self.root, bg="#010203", highlightthickness=0, bd=0)
        self.eye = EyePanel(self.loading, max_rows=52, fill_ratio=0.68)
        self.eye.pack()
        eye_bg = "#010203"
        self.header = tk.Label(
            self.eye.frame,
            text="Music Downloader",
            font=self.font_ui,
            fg=ACCENT,
            bg=eye_bg,
        )
        self.status_lbl = tk.Label(
            self.eye.frame,
            textvariable=self.status,
            font=self.font_small,
            fg=MUTED,
            bg=eye_bg,
        )

    def _build_results(self) -> None:
        self.result_frame = tk.Frame(self.root, bg=BG)
        pad = tk.Frame(self.result_frame, bg=BG)
        pad.pack(fill="both", expand=True, padx=28, pady=22)

        self.summary = tk.Label(
            pad, text="", font=self.font_section, fg=FG, bg=BG, justify="left"
        )
        self.summary.pack(anchor="w", pady=(0, 12))

        log_shell = tk.Frame(pad, bg=SURFACE)
        log_shell.pack(fill="both", expand=True)
        self.log = tk.Text(
            log_shell,
            font=self.font_mono,
            bg=SURFACE,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=12,
            pady=12,
            wrap="word",
        )
        scrollbar = ttk.Scrollbar(
            log_shell,
            orient="vertical",
            style="Dark.Vertical.TScrollbar",
            command=self.log.yview,
        )
        self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.configure(state="disabled")

        actions = tk.Frame(pad, bg=BG)
        actions.pack(fill="x", pady=(14, 0))
        self._btn(actions, "Listeye dön", self._back_to_setup).pack(side="left")
        self._btn(actions, "Kapat", self._force_close, accent=True).pack(side="right")

    # ── liste ────────────────────────────────────────────────

    def _load_initial_songs(self) -> None:
        if self._songs_path.exists():
            try:
                self.songs = read_songs_from_file(self._songs_path)
            except Exception:  # noqa: BLE001
                self.songs = []
        self._refresh_song_list()
        if self.songs:
            self.setup_hint.set("Kayıtlı liste yüklendi")
        else:
            self.setup_hint.set("Şarkı ekle veya sağdan sanatçı ara")

    def _persist(self) -> None:
        try:
            save_songs_to_file(self._songs_path, self.songs)
        except Exception:  # noqa: BLE001
            pass

    def _refresh_song_list(self) -> None:
        self.song_list.delete(0, "end")
        for s in self.songs:
            self.song_list.insert("end", s)
        n = len(self.songs)
        self.list_count.set(f"{n} şarkı")

    def _add_song(self) -> None:
        raw = self.song_entry_var.get().strip()
        if not raw:
            self.setup_hint.set("Önce şarkı adı yaz")
            return
        if raw in self.songs:
            self.setup_hint.set("Bu şarkı zaten listede")
            return
        self.songs.append(raw)
        self.song_entry_var.set("")
        self._refresh_song_list()
        self._persist()
        self.song_list.see("end")
        self.setup_hint.set("Şarkı listeye eklendi")

    def _remove_selected(self) -> None:
        sel = list(self.song_list.curselection())
        if not sel:
            self.setup_hint.set("Silmek için listeden bir şarkı seç")
            return
        for i in reversed(sel):
            del self.songs[i]
        self._refresh_song_list()
        self._persist()
        self.setup_hint.set(f"{len(sel)} şarkı silindi")

    def _clear_songs(self) -> None:
        if not self.songs:
            return
        self.songs.clear()
        self._refresh_song_list()
        self._persist()
        self.setup_hint.set("Liste temizlendi")

    def _add_queries(self, queries: list[str]) -> int:
        added = 0
        existing = set(self.songs)
        for q in queries:
            q = q.strip()
            if not q or q in existing:
                continue
            self.songs.append(q)
            existing.add(q)
            added += 1
        if added:
            self._refresh_song_list()
            self._persist()
            self.song_list.see("end")
        return added

    # ── sanatçı ──────────────────────────────────────────────

    def _find_artist_tracks(self) -> None:
        if self._busy:
            return
        name = self.artist_var.get().strip()
        if not name:
            self.setup_hint.set("Sanatçı adını yaz")
            return
        try:
            y0 = int(self.year_from_var.get().strip())
            y1 = int(self.year_to_var.get().strip())
        except ValueError:
            self.setup_hint.set("Yıllar sayı olmalı (ör. 2000)")
            return
        if y0 > y1:
            y0, y1 = y1, y0
            self.year_from_var.set(str(y0))
            self.year_to_var.set(str(y1))

        self._busy = True
        self.find_btn.configure(state="disabled")
        self.setup_hint.set("Şarkılar aranıyor…")
        self.found_count.set("")
        self.found_list.delete(0, "end")
        self._found_queries = []

        def work() -> None:
            try:
                artist, tracks = discover_artist_tracks(
                    name,
                    y0,
                    y1,
                    on_status=lambda m: self.queue.put(("hint", m)),
                )
                rows = [
                    (t.query, f"{t.year or '????'}  ·  {t.title}") for t in tracks
                ]
                self.queue.put(("found", artist.label, rows))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("hint_error", str(exc)))
            finally:
                self.queue.put(("find_done",))

        threading.Thread(target=work, daemon=True).start()

    def _add_found_selected(self) -> None:
        sel = self.found_list.curselection()
        if not sel:
            self.setup_hint.set("Sağdaki listeden şarkı seç")
            return
        n = self._add_queries([self._found_queries[i] for i in sel])
        self.setup_hint.set(f"{n} şarkı indirme listesine eklendi")

    def _add_found_all(self) -> None:
        if not self._found_queries:
            self.setup_hint.set("Önce ‘Şarkıları bul’a bas")
            return
        n = self._add_queries(self._found_queries)
        self.setup_hint.set(f"{n} şarkı indirme listesine eklendi")

    # ── sahneler ─────────────────────────────────────────────

    def _hide_all(self) -> None:
        self.setup.pack_forget()
        self.loading.pack_forget()
        self.result_frame.pack_forget()
        self.header.place_forget()
        self.status_lbl.place_forget()

    def _show_setup(self) -> None:
        self._hide_all()
        try:
            self.eye.stop()
        except Exception:  # noqa: BLE001
            pass
        self.setup.pack(fill="both", expand=True)
        self._center(WIN_W, WIN_H)

    def _show_loading(self) -> None:
        self._hide_all()
        self.loading.pack()
        self.header.place(relx=0.5, y=16, anchor="n")
        self.status_lbl.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self._center(self.eye.width, self.eye.height)

    def _show_results_frame(self) -> None:
        self._hide_all()
        try:
            self.eye.stop()
        except Exception:  # noqa: BLE001
            pass
        self.result_frame.pack(fill="both", expand=True)
        self._center(RESULT_W, RESULT_H)

    def _back_to_setup(self) -> None:
        self._show_setup()

    # ── indirme ──────────────────────────────────────────────

    def _start_download(self) -> None:
        if self._busy:
            return
        if not self.songs:
            self.setup_hint.set("Liste boş — önce şarkı ekle")
            return
        self._persist()
        songs = list(self.songs)
        output_dir = app_dir() / "downloads"
        self.status.set(f"0/{len(songs)} — indirme başlıyor…")
        self._show_loading()
        self.eye.start()
        threading.Thread(
            target=self._worker, args=(songs, output_dir), daemon=True
        ).start()

    def _worker(self, songs: list[str], output_dir: Path) -> None:
        def log(msg: str) -> None:
            self.queue.put(("log", msg))

        def progress(i: int, total: int, song: str) -> None:
            self.queue.put(("progress", i, total, song))

        try:
            ok, fail, lines = download_songs(
                songs, output_dir, log=log, on_progress=progress
            )
            self.queue.put(("done", ok, fail, len(songs), lines))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "hint":
                    self.setup_hint.set(item[1])
                elif kind == "hint_error":
                    self.setup_hint.set(item[1])
                    self._busy = False
                    self.find_btn.configure(state="normal")
                elif kind == "find_done":
                    self._busy = False
                    self.find_btn.configure(state="normal")
                elif kind == "found":
                    _, label, rows = item
                    self.found_list.delete(0, "end")
                    self._found_queries = [q for q, _ in rows]
                    for _, line in rows:
                        self.found_list.insert("end", line)
                    self.found_count.set(f"{len(rows)}")
                    self.setup_hint.set(
                        f"{label} bulundu — seçip ‘Seçilenleri ekle’ veya ‘Tümünü ekle’"
                    )
                elif kind == "progress":
                    _, i, total, song = item
                    short = song if len(song) < 42 else song[:39] + "…"
                    self.status.set(f"{i}/{total}  ·  {short}")
                elif kind == "done":
                    _, ok, fail, total, lines = item
                    self._show_results(ok, fail, total, lines)
                elif kind == "error":
                    self._finish_error(item[1])
        except queue.Empty:
            pass
        if not self._closing:
            self.root.after(100, self._poll_queue)

    def _show_results(
        self, ok: int, fail: int, total: int, lines: list[str]
    ) -> None:
        rate = (100.0 * ok / total) if total else 0.0
        color = OK if fail == 0 else (BAD if ok == 0 else ACCENT)
        self.summary.configure(
            text=f"Başarılı: {ok}   ·   Başarısız: {fail}   ·   Oran: %{rate:.0f}",
            fg=color,
        )
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(lines))
        self.log.configure(state="disabled")
        self.log.see("end")
        self._show_results_frame()

    def _finish_error(self, msg: str) -> None:
        self.summary.configure(text="Bir sorun oluştu", fg=BAD)
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", msg)
        self.log.configure(state="disabled")
        self._show_results_frame()

    def _on_escape(self, _event=None) -> None:
        if self.loading.winfo_ismapped():
            return
        self._force_close()

    def _force_close(self) -> None:
        self._closing = True
        try:
            self.eye.stop()
        except Exception:  # noqa: BLE001
            pass
        self._persist()
        self.root.destroy()

    def run(self) -> int:
        self.root.mainloop()
        return 0


def run_gui() -> int:
    enable_dpi_awareness()
    return App().run()


if __name__ == "__main__":
    raise SystemExit(run_gui())
