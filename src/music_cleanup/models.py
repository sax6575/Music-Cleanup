from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TrackRecord:
    file_path: Path
    relative_path: str
    size_bytes: int
    format_ext: str
    artist: str
    album: str
    title: str
    track_number: str
    year: str
    genre: str
    duration_seconds: Optional[float]
    bitrate_kbps: Optional[int]
    sample_rate_hz: Optional[int]
    metadata_source: str


@dataclass
class LibraryMetrics:
    total_tracks: int
    total_size_bytes: int
    unique_artists: int
    unique_albums: int


@dataclass
class ScanResult:
    records: list[TrackRecord]
    warnings: list[str]


@dataclass
class OrganizeResult:
    moved: int
    skipped: int
    sidecar_moved: int
    warnings: list[str]
