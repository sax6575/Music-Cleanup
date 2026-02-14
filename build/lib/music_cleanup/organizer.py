from __future__ import annotations

import re
import shutil
from pathlib import Path

from .models import TrackRecord


INVALID_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1F]")


def sanitize_name(value: str) -> str:
    value = value.strip().rstrip(".")
    value = INVALID_CHARS.sub("_", value)
    return value if value else "Unknown"


def target_path_for(record: TrackRecord, destination_root: Path) -> Path:
    artist = sanitize_name(record.artist)
    album = sanitize_name(record.album if record.album else "Miscellaneous")
    return destination_root / artist / album / record.file_path.name


def _non_colliding_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def organize_files(
    records: list[TrackRecord],
    destination_root: Path,
    dry_run: bool = True,
    copy_instead_of_move: bool = False,
    verbose: bool = False,
) -> tuple[int, int]:
    moved = 0
    skipped = 0

    for record in records:
        target = target_path_for(record, destination_root)

        if record.file_path.resolve() == target.resolve():
            skipped += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        final_target = _non_colliding_path(target)

        if verbose or dry_run:
            action = "copy" if copy_instead_of_move else "move"
            print(f"[{action}] {record.file_path} -> {final_target}")

        if not dry_run:
            if copy_instead_of_move:
                shutil.copy2(record.file_path, final_target)
            else:
                shutil.move(str(record.file_path), str(final_target))

        moved += 1

    return moved, skipped
