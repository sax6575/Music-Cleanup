from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .metadata import is_audio_file, normalized_album, normalized_artist, normalized_title, read_audio_info
from .models import ScanResult, TrackRecord


def scan_music(
    root: Path,
    verbose: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ScanResult:
    records: list[TrackRecord] = []
    warnings: list[str] = []
    candidates: list[Path] = []

    def _on_walk_error(err: OSError) -> None:
        target = getattr(err, "filename", None) or str(root)
        warnings.append(f"walk error: {target}: {err.strerror or str(err)}")
        if verbose:
            print(f"[scan-warning] walk error: {target}: {err.strerror or str(err)}")

    for dirpath, _, filenames in os.walk(root, onerror=_on_walk_error):
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            try:
                if is_audio_file(path):
                    candidates.append(path)
            except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
                warnings.append(f"file skipped: {path}: {exc}")
                if verbose:
                    print(f"[scan-warning] file skipped: {path}: {exc}")

    total = len(candidates)
    if progress_callback:
        progress_callback(0, total)

    for idx, path in enumerate(candidates, start=1):
        try:
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
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
            rel = str(path)
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                pass
            warnings.append(f"file skipped: {rel}: {exc}")
            if verbose:
                print(f"[scan-warning] file skipped: {rel}: {exc}")
        finally:
            if progress_callback:
                progress_callback(idx, total)

    return ScanResult(records=records, warnings=warnings)
