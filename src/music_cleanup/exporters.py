from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .metrics import bytes_to_mb
from .models import LibraryMetrics, TrackRecord


TRACK_COLUMNS = [
    "file_path",
    "relative_path",
    "size_mb",
    "format_ext",
    "artist",
    "album",
    "title",
    "track_number",
    "year",
    "genre",
    "duration_seconds",
    "bitrate_kbps",
    "sample_rate_hz",
    "metadata_source",
]


def export_tracks_csv(path: Path, records: list[TrackRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACK_COLUMNS)
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "file_path": str(r.file_path),
                    "relative_path": r.relative_path,
                    "size_mb": round(bytes_to_mb(r.size_bytes), 2),
                    "format_ext": r.format_ext,
                    "artist": r.artist,
                    "album": r.album,
                    "title": r.title,
                    "track_number": r.track_number,
                    "year": r.year,
                    "genre": r.genre,
                    "duration_seconds": r.duration_seconds,
                    "bitrate_kbps": r.bitrate_kbps,
                    "sample_rate_hz": r.sample_rate_hz,
                    "metadata_source": r.metadata_source,
                }
            )


def export_metrics_csv(path: Path, metrics: LibraryMetrics, format_percent: dict[str, float], format_bytes: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_tracks", metrics.total_tracks])
        writer.writerow(["total_size_mb", round(bytes_to_mb(metrics.total_size_bytes), 2)])
        writer.writerow(["unique_artists", metrics.unique_artists])
        writer.writerow(["unique_albums", metrics.unique_albums])
        writer.writerow([])
        writer.writerow(["format", "size_mb", "percent_of_library"])
        for fmt in sorted(format_percent):
            writer.writerow([fmt, round(bytes_to_mb(format_bytes.get(fmt, 0)), 2), format_percent[fmt]])


def export_sqlite(path: Path, records: list[TrackRecord], metrics: LibraryMetrics, format_percent: dict[str, float], format_bytes: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS tracks")
        cur.execute("DROP TABLE IF EXISTS library_metrics")
        cur.execute("DROP TABLE IF EXISTS format_metrics")

        cur.execute(
            """
            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                format_ext TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                title TEXT NOT NULL,
                track_number TEXT,
                year TEXT,
                genre TEXT,
                duration_seconds REAL,
                bitrate_kbps INTEGER,
                sample_rate_hz INTEGER,
                metadata_source TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE library_metrics (
                total_tracks INTEGER NOT NULL,
                total_size_bytes INTEGER NOT NULL,
                unique_artists INTEGER NOT NULL,
                unique_albums INTEGER NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE format_metrics (
                format_ext TEXT PRIMARY KEY,
                size_bytes INTEGER NOT NULL,
                percent_of_library REAL NOT NULL
            )
            """
        )

        cur.executemany(
            """
            INSERT INTO tracks (
                file_path, relative_path, size_bytes, format_ext, artist, album, title,
                track_number, year, genre, duration_seconds, bitrate_kbps, sample_rate_hz, metadata_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(r.file_path),
                    r.relative_path,
                    r.size_bytes,
                    r.format_ext,
                    r.artist,
                    r.album,
                    r.title,
                    r.track_number,
                    r.year,
                    r.genre,
                    r.duration_seconds,
                    r.bitrate_kbps,
                    r.sample_rate_hz,
                    r.metadata_source,
                )
                for r in records
            ],
        )

        cur.execute(
            "INSERT INTO library_metrics VALUES (?, ?, ?, ?)",
            (metrics.total_tracks, metrics.total_size_bytes, metrics.unique_artists, metrics.unique_albums),
        )

        cur.executemany(
            "INSERT INTO format_metrics VALUES (?, ?, ?)",
            [(fmt, format_bytes.get(fmt, 0), format_percent[fmt]) for fmt in sorted(format_percent)],
        )

        conn.commit()
    finally:
        conn.close()
