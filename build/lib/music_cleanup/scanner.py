from __future__ import annotations

from pathlib import Path

from .metadata import is_audio_file, normalized_album, normalized_artist, normalized_title, read_audio_info
from .models import TrackRecord


def scan_music(root: Path, verbose: bool = False) -> list[TrackRecord]:
    records: list[TrackRecord] = []

    for path in root.rglob("*"):
        if not is_audio_file(path):
            continue

        rel_path = str(path.relative_to(root))
        if verbose:
            print(f"[scan] {rel_path}")

        size_bytes = path.stat().st_size
        metadata = read_audio_info(path)

        artist = normalized_artist(str(metadata["artist"]))
        album = normalized_album(str(metadata["album"]))
        title = normalized_title(str(metadata["title"]), path.stem)

        records.append(
            TrackRecord(
                file_path=path,
                relative_path=rel_path,
                size_bytes=size_bytes,
                format_ext=path.suffix.lower().lstrip("."),
                artist=artist,
                album=album,
                title=title,
                track_number=str(metadata["track_number"]),
                year=str(metadata["year"]),
                genre=str(metadata["genre"]),
                duration_seconds=metadata["duration_seconds"],
                bitrate_kbps=metadata["bitrate_kbps"],
                sample_rate_hz=metadata["sample_rate_hz"],
                metadata_source=str(metadata["metadata_source"]),
            )
        )

    return records
