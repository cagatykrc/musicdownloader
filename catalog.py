#!/usr/bin/env python3
"""MusicBrainz üzerinden sanatçı + yıl aralığı şarkı keşfi."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

USER_AGENT = "MusicDownloader/1.1 (local; portfolio)"
API = "https://musicbrainz.org/ws/2"
MIN_INTERVAL = 1.05  # MusicBrainz: max 1 istek/sn


@dataclass(frozen=True)
class ArtistHit:
    mbid: str
    name: str
    disambiguation: str = ""
    score: int = 0

    @property
    def label(self) -> str:
        if self.disambiguation:
            return f"{self.name} ({self.disambiguation})"
        return self.name


@dataclass(frozen=True)
class TrackHit:
    title: str
    artist: str
    year: int | None = None

    @property
    def query(self) -> str:
        return f"{self.artist} - {self.title}"


_last_req = 0.0


def _throttle() -> None:
    global _last_req
    now = time.monotonic()
    wait = MIN_INTERVAL - (now - _last_req)
    if wait > 0:
        time.sleep(wait)
    _last_req = time.monotonic()


def _get_json(path: str, params: dict, retries: int = 4) -> dict:
    import json

    query = urllib.parse.urlencode(params)
    url = f"{API}/{path}?{query}"
    last_err: Exception | None = None
    for attempt in range(retries):
        _throttle()
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            last_err = RuntimeError(f"MusicBrainz HTTP {exc.code}: {body}")
            if exc.code in (503, 429, 502) and attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last_err from exc
        except urllib.error.URLError as exc:
            last_err = RuntimeError(f"Ağ hatası: {exc.reason}")
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last_err from exc
    raise last_err or RuntimeError("MusicBrainz isteği başarısız")


def _escape_lucene(text: str) -> str:
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", text.strip())


def _norm_title(title: str) -> str:
    t = title.casefold().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*[\(\[].*?[\)\]]\s*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def search_artists(name: str, limit: int = 8) -> list[ArtistHit]:
    name = name.strip()
    if not name:
        return []
    data = _get_json(
        "artist",
        {
            "query": f'artist:"{_escape_lucene(name)}"',
            "fmt": "json",
            "limit": str(limit),
        },
    )
    hits: list[ArtistHit] = []
    for row in data.get("artists") or []:
        hits.append(
            ArtistHit(
                mbid=row["id"],
                name=row.get("name") or name,
                disambiguation=(row.get("disambiguation") or "").strip(),
                score=int(row.get("score") or 0),
            )
        )
    hits.sort(key=lambda a: (-a.score, a.name.casefold()))
    return hits


def find_tracks_for_artist(
    artist: ArtistHit,
    year_from: int,
    year_to: int,
    *,
    max_tracks: int = 400,
    on_status: Callable[[str], None] | None = None,
) -> list[TrackHit]:
    if year_from > year_to:
        year_from, year_to = year_to, year_from
    if year_from < 1900 or year_to > 2100:
        raise ValueError("Yıl aralığı geçersiz.")

    def status(msg: str) -> None:
        if on_status:
            on_status(msg)

    query = (
        f"arid:{artist.mbid} AND video:false "
        f"AND firstreleasedate:[{year_from} TO {year_to}]"
    )
    limit = 100
    offset = 0
    total: int | None = None
    seen: set[str] = set()
    tracks: list[TrackHit] = []

    while True:
        status(f"Kayıtlar alınıyor… ({len(tracks)} / {total or '?'})")
        data = _get_json(
            "recording",
            {
                "query": query,
                "fmt": "json",
                "limit": str(limit),
                "offset": str(offset),
            },
        )
        if total is None:
            total = int(data.get("count") or 0)
        rows = data.get("recordings") or []
        if not rows:
            break

        for row in rows:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            key = _norm_title(title)
            if not key or key in seen:
                continue
            # remaster / live / karaoke gürültüsünü hafif ele
            low = title.casefold()
            if any(
                tag in low
                for tag in (
                    "karaoke",
                    "instrumental",
                    "remaster",
                    "live at",
                    "bonus track",
                )
            ):
                continue
            seen.add(key)
            year = _first_year(row)
            tracks.append(TrackHit(title=title, artist=artist.name, year=year))
            if len(tracks) >= max_tracks:
                status(f"{len(tracks)} şarkı bulundu (üst sınır).")
                return _sorted_tracks(tracks)

        offset += limit
        if offset >= (total or 0) or offset >= 1000:
            break

    status(f"{len(tracks)} benzersiz şarkı.")
    return _sorted_tracks(tracks)


def _first_year(row: dict) -> int | None:
    raw = row.get("first-release-date") or ""
    if len(raw) >= 4 and raw[:4].isdigit():
        return int(raw[:4])
    return None


def _sorted_tracks(tracks: list[TrackHit]) -> list[TrackHit]:
    return sorted(
        tracks,
        key=lambda t: (
            t.year if t.year is not None else 9999,
            t.title.casefold(),
        ),
    )


def discover_artist_tracks(
    artist_name: str,
    year_from: int,
    year_to: int,
    *,
    on_status: Callable[[str], None] | None = None,
) -> tuple[ArtistHit, list[TrackHit]]:
    """Sanatçı adı + yıl → en iyi eşleşme ve şarkı listesi."""
    if on_status:
        on_status("Sanatçı aranıyor…")
    artists = search_artists(artist_name)
    if not artists:
        raise LookupError(f"Sanatçı bulunamadı: {artist_name}")
    best = artists[0]
    if on_status:
        on_status(f"Seçildi: {best.label}")
    tracks = find_tracks_for_artist(
        best, year_from, year_to, on_status=on_status
    )
    return best, tracks
