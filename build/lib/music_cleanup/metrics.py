from __future__ import annotations

from collections import Counter

from .models import LibraryMetrics, TrackRecord


def summarize(records: list[TrackRecord]) -> tuple[LibraryMetrics, dict[str, float], dict[str, int]]:
    total_tracks = len(records)
    total_size_bytes = sum(r.size_bytes for r in records)
    unique_artists = len({r.artist for r in records})
    unique_albums = len({(r.artist, r.album) for r in records})

    format_bytes = Counter()
    for r in records:
        format_bytes[r.format_ext] += r.size_bytes

    format_percent: dict[str, float] = {}
    for fmt, size in sorted(format_bytes.items()):
        pct = (size / total_size_bytes * 100.0) if total_size_bytes else 0.0
        format_percent[fmt] = round(pct, 2)

    return (
        LibraryMetrics(
            total_tracks=total_tracks,
            total_size_bytes=total_size_bytes,
            unique_artists=unique_artists,
            unique_albums=unique_albums,
        ),
        format_percent,
        dict(format_bytes),
    )


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{num_bytes} B"
