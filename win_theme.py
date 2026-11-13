"""Windows DPI + koyu başlık çubuğu yardımcıları."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from tkinter import ttk


def enable_dpi_awareness() -> None:
    """Tk bulanıklığını azaltmak için process DPI awareness."""
    if sys.platform != "win32":
        return
    try:
        # Per-monitor v2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass


def apply_dark_titlebar(window: tk.Misc) -> None:
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(int(window.winfo_id()))
        if not hwnd:
            hwnd = int(window.winfo_id())
        value = ctypes.c_int(1)
        # 20: Win10 1903+, 19: eski build
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                attr,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
    except Exception:  # noqa: BLE001
        pass


def disable_maximize(window: tk.Misc) -> None:
    """Yeniden boyutlandırma + maximize / fullscreen kapalı."""
    try:
        window.resizable(False, False)
        window.attributes("-fullscreen", False)
    except Exception:  # noqa: BLE001
        pass
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(int(window.winfo_id()))
        if not hwnd:
            hwnd = int(window.winfo_id())
        gwl_style = -16
        ws_maximizebox = 0x00010000
        ws_thickframe = 0x00040000
        get_long = ctypes.windll.user32.GetWindowLongW
        set_long = ctypes.windll.user32.SetWindowLongW
        style = get_long(hwnd, gwl_style)
        style &= ~(ws_maximizebox | ws_thickframe)
        set_long(hwnd, gwl_style, style)
    except Exception:  # noqa: BLE001
        pass


def configure_dark_ttk(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:  # noqa: BLE001
        pass

    trough = "#12141a"
    thumb = "#2a2d36"
    thumb_active = "#3d4250"
    arrow = "#8a857c"
    border = "#0b0c0f"

    style.configure(
        "Dark.Vertical.TScrollbar",
        gripcount=0,
        background=thumb,
        darkcolor=thumb,
        lightcolor=thumb,
        troughcolor=trough,
        bordercolor=border,
        arrowcolor=arrow,
        relief="flat",
        width=12,
    )
    style.map(
        "Dark.Vertical.TScrollbar",
        background=[
            ("active", thumb_active),
            ("pressed", "#c4a35a"),
            ("disabled", trough),
        ],
        arrowcolor=[
            ("pressed", "#0b0c0f"),
            ("active", "#c4a35a"),
        ],
    )
    style.configure(
        "Dark.Horizontal.TScrollbar",
        gripcount=0,
        background=thumb,
        darkcolor=thumb,
        lightcolor=thumb,
        troughcolor=trough,
        bordercolor=border,
        arrowcolor=arrow,
        relief="flat",
        width=12,
    )
    style.map(
        "Dark.Horizontal.TScrollbar",
        background=[
            ("active", thumb_active),
            ("pressed", "#c4a35a"),
            ("disabled", trough),
        ],
        arrowcolor=[
            ("pressed", "#0b0c0f"),
            ("active", "#c4a35a"),
        ],
    )
    return style
