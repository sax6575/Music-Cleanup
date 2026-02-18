from __future__ import annotations

import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Callable

from .models import OrganizeResult, TrackRecord


INVALID_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1F]")
SIDECAR_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".nfo",
    ".cue",
    ".txt",
    ".m3u",
    ".m3u8",
    ".pdf",
}


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


def _is_sidecar_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.startswith("._"):
        return False
    return path.suffix.lower() in SIDECAR_EXTENSIONS


def _clean_album_dir_name(value: str) -> str:
    cleaned = value.strip()
    while True:
        next_cleaned = re.sub(r"\s*(\([^)]*\)|\[[^\]]*\])\s*$", "", cleaned).strip()
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    return cleaned


def _infer_scan_root(records: list[TrackRecord]) -> Path | None:
    for record in records:
        rel_parts = Path(record.relative_path).parts
        if not rel_parts:
            continue
        idx = len(rel_parts) - 1
        if idx < len(record.file_path.parents):
            return record.file_path.parents[idx]
    return None


def _guess_destination_dir(source_dir: Path, destination_root: Path) -> Path | None:
    name = source_dir.name
    if " - " not in name:
        return None
    artist_raw, album_raw = name.split(" - ", 1)
    artist = sanitize_name(artist_raw)
    album = sanitize_name(_clean_album_dir_name(album_raw))
    candidate = destination_root / artist / album
    if candidate.exists():
        return candidate
    return None


def _collect_sidecar_files(
    root: Path,
    destination_root: Path,
    warnings: list[str],
    verbose: bool,
) -> dict[Path, list[Path]]:
    sidecar_files_by_dir: dict[Path, list[Path]] = defaultdict(list)

    def _on_walk_error(err: OSError) -> None:
        target = getattr(err, "filename", None) or str(root)
        warnings.append(f"organize sidecar walk error: {target}: {err.strerror or str(err)}")
        if verbose:
            print(f"[organize-warning] sidecar walk error: {target}: {err.strerror or str(err)}")

    for dirpath, _, filenames in os.walk(root, onerror=_on_walk_error):
        current = Path(dirpath)
        if current == destination_root or destination_root in current.parents:
            continue
        for name in filenames:
            candidate = current / name
            try:
                if _is_sidecar_file(candidate):
                    sidecar_files_by_dir[current].append(candidate)
            except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
                warnings.append(f"organize sidecar skipped: {candidate}: {exc}")
                if verbose:
                    print(f"[organize-warning] sidecar skipped: {candidate}: {exc}")

    return sidecar_files_by_dir


def _move_sidecar_candidates(
    sidecar_files_by_dir: dict[Path, list[Path]],
    source_to_dest: dict[Path, Path],
    destination_root: Path,
    dry_run: bool,
    copy_instead_of_move: bool,
    verbose: bool,
    warnings: list[str],
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    files_total = sum(len(files) for files in sidecar_files_by_dir.values())
    files_done = 0
    if progress_callback:
        progress_callback(0, files_total)

    sidecar_moved = 0
    for src_dir, files in sidecar_files_by_dir.items():
        dest_dir = source_to_dest.get(src_dir) or _guess_destination_dir(src_dir, destination_root)
        if dest_dir is None:
            warnings.append(f"organize sidecar directory unmapped: {src_dir}")
            if verbose:
                print(f"[organize-warning] sidecar directory unmapped: {src_dir}")
            files_done += len(files)
            if progress_callback:
                progress_callback(files_done, files_total)
            continue

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            for candidate in files:
                try:
                    target = _non_colliding_path(dest_dir / candidate.name)
                    if verbose or dry_run:
                        action = "copy" if copy_instead_of_move else "move"
                        print(f"[{action}-sidecar] {candidate} -> {target}")
                    if not dry_run:
                        if copy_instead_of_move:
                            shutil.copy2(candidate, target)
                        else:
                            shutil.move(str(candidate), str(target))
                    sidecar_moved += 1
                except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
                    warnings.append(f"organize sidecar skipped: {candidate}: {exc}")
                    if verbose:
                        print(f"[organize-warning] sidecar skipped: {candidate}: {exc}")
                finally:
                    files_done += 1
                    if progress_callback:
                        progress_callback(files_done, files_total)
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
            warnings.append(f"organize sidecar destination skipped: {dest_dir}: {exc}")
            if verbose:
                print(f"[organize-warning] sidecar destination skipped: {dest_dir}: {exc}")
            files_done += len(files)
            if progress_callback:
                progress_callback(files_done, files_total)

    return sidecar_moved


def organize_sidecar_files(
    root: Path,
    destination_root: Path,
    dry_run: bool = True,
    copy_instead_of_move: bool = False,
    verbose: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> OrganizeResult:
    warnings: list[str] = []
    sidecar_files_by_dir = _collect_sidecar_files(root, destination_root, warnings, verbose)
    sidecar_moved = _move_sidecar_candidates(
        sidecar_files_by_dir=sidecar_files_by_dir,
        source_to_dest={},
        destination_root=destination_root,
        dry_run=dry_run,
        copy_instead_of_move=copy_instead_of_move,
        verbose=verbose,
        warnings=warnings,
        progress_callback=progress_callback,
    )
    return OrganizeResult(moved=0, skipped=0, sidecar_moved=sidecar_moved, warnings=warnings)


def organize_files(
    records: list[TrackRecord],
    destination_root: Path,
    dry_run: bool = True,
    copy_instead_of_move: bool = False,
    verbose: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> OrganizeResult:
    moved = 0
    skipped = 0
    sidecar_moved = 0
    warnings: list[str] = []
    total = len(records)
    source_to_dest_candidates: dict[Path, dict[Path, int]] = defaultdict(lambda: defaultdict(int))
    if progress_callback:
        progress_callback(0, total)

    for idx, record in enumerate(records, start=1):
        try:
            target = target_path_for(record, destination_root)

            source_path = record.file_path
            try:
                same_path = source_path.resolve() == target.resolve()
            except OSError:
                same_path = False

            if same_path:
                skipped += 1
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            final_target = _non_colliding_path(target)

            if verbose or dry_run:
                action = "copy" if copy_instead_of_move else "move"
                print(f"[{action}] {source_path} -> {final_target}")

            if not dry_run:
                if copy_instead_of_move:
                    shutil.copy2(source_path, final_target)
                else:
                    shutil.move(str(source_path), str(final_target))

            moved += 1
            source_to_dest_candidates[source_path.parent][final_target.parent] += 1
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
            rel = record.relative_path or str(record.file_path)
            warnings.append(f"organize skipped: {rel}: {exc}")
            if verbose:
                print(f"[organize-warning] skipped: {rel}: {exc}")
        finally:
            if progress_callback:
                progress_callback(idx, total)

    source_to_dest: dict[Path, Path] = {}
    for src_dir, counts in source_to_dest_candidates.items():
        if not counts:
            continue
        source_to_dest[src_dir] = max(counts.items(), key=lambda item: item[1])[0]

    inferred_root = _infer_scan_root(records)
    if inferred_root is not None:
        sidecar_files_by_dir = _collect_sidecar_files(inferred_root, destination_root, warnings, verbose)
    else:
        sidecar_files_by_dir = defaultdict(list)
        for src_dir in source_to_dest:
            try:
                for candidate in src_dir.iterdir():
                    if _is_sidecar_file(candidate):
                        sidecar_files_by_dir[src_dir].append(candidate)
            except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
                warnings.append(f"organize sidecar directory skipped: {src_dir}: {exc}")
                if verbose:
                    print(f"[organize-warning] sidecar directory skipped: {src_dir}: {exc}")

    sidecar_moved = _move_sidecar_candidates(
        sidecar_files_by_dir=sidecar_files_by_dir,
        source_to_dest=source_to_dest,
        destination_root=destination_root,
        dry_run=dry_run,
        copy_instead_of_move=copy_instead_of_move,
        verbose=verbose,
        warnings=warnings,
    )

    return OrganizeResult(moved=moved, skipped=skipped, sidecar_moved=sidecar_moved, warnings=warnings)
