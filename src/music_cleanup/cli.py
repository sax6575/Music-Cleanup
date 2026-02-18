from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from .enrichment import enrich_with_musicbrainz
from .exporters import export_metrics_csv, export_sqlite, export_tracks_csv
from .metrics import human_size, summarize
from .organizer import organize_files, organize_sidecar_files
from .scanner import scan_music


def _make_progress_printer(stage: str) -> Callable[[int, int], None]:
    is_tty = sys.stdout.isatty()
    last_percent = -1

    def _report(current: int, total: int) -> None:
        nonlocal last_percent
        percent = 100 if total <= 0 else int((current / total) * 100)
        percent = max(0, min(100, percent))

        if is_tty:
            if percent == last_percent and current < total:
                return
            end = "\n" if current >= total else ""
            print(f"\r[{stage}] {percent:3d}% ({current}/{total})", end=end, flush=True)
            last_percent = percent
            return

        should_print = (
            last_percent < 0
            or current >= total
            or percent >= last_percent + 10
        )
        if should_print:
            print(f"[{stage}] {percent:3d}% ({current}/{total})")
            last_percent = percent

    return _report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="music-cleanup",
        description="Catalog and organize local music libraries.",
    )
    parser.add_argument("root", type=Path, help="Top-level music directory to scan")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./output"),
        help="Directory for generated CSV/SQLite outputs",
    )
    parser.add_argument(
        "--export",
        choices=["csv", "sqlite", "both"],
        default="both",
        help="Export format for catalog data",
    )
    parser.add_argument(
        "--organize",
        action="store_true",
        help="Organize files into Artist/Album structure",
    )
    parser.add_argument(
        "--organize-sidecars-only",
        action="store_true",
        help="Only move/copy sidecar files (artwork/metadata) into existing organized folders",
    )
    parser.add_argument(
        "--dest-root",
        type=Path,
        default=None,
        help="Destination root for organized library (defaults to root)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply file operations. Without this flag, organize runs in dry-run mode.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy files instead of moving when organizing",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-file scan and organize details",
    )
    parser.add_argument(
        "--enrich-musicbrainz",
        action="store_true",
        help="Query MusicBrainz to improve missing/weak metadata before export/organize",
    )
    parser.add_argument(
        "--enrich-all",
        action="store_true",
        help="Attempt enrichment for all tracks (default enriches only missing artist/album)",
    )
    parser.add_argument(
        "--musicbrainz-min-score",
        type=int,
        default=85,
        help="Minimum MusicBrainz match score (0-100) required to apply updates",
    )
    parser.add_argument(
        "--musicbrainz-contact",
        type=str,
        default="https://example.com/contact",
        help="Contact URL/email for MusicBrainz user-agent",
    )
    parser.add_argument(
        "--musicbrainz-sleep-seconds",
        type=float,
        default=1.1,
        help="Delay between MusicBrainz requests to stay within public rate limits",
    )
    parser.add_argument(
        "--write-tags",
        action="store_true",
        help="When enriching, write updated metadata tags back into the source files",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    root: Path = args.root.expanduser().resolve()
    output_dir: Path = args.output_dir.expanduser().resolve()

    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root directory does not exist or is not a directory: {root}")

    if args.organize_sidecars_only:
        destination_root = (args.dest_root or root).expanduser().resolve()
        print(f"[sidecar] source root: {root}")
        print(f"[sidecar] destination root: {destination_root}")
        if args.enrich_musicbrainz:
            raise SystemExit("--organize-sidecars-only cannot be used with --enrich-musicbrainz")
        if not args.apply:
            print("[sidecar] dry-run mode enabled (pass --apply to execute)")
        sidecar_result = organize_sidecar_files(
            root=root,
            destination_root=destination_root,
            dry_run=not args.apply,
            copy_instead_of_move=args.copy,
            verbose=args.verbose,
            progress_callback=_make_progress_printer("sidecar"),
        )
        print(f"[sidecar] sidecar files moved/copied: {sidecar_result.sidecar_moved}")
        if sidecar_result.warnings:
            output_dir.mkdir(parents=True, exist_ok=True)
            warnings_path = output_dir / "organize_warnings.log"
            warnings_path.write_text("\n".join(sidecar_result.warnings) + "\n", encoding="utf-8")
            print(f"[warn] organize warnings: {len(sidecar_result.warnings)}")
            print(f"[warn] details written: {warnings_path}")
        return

    print(f"[start] scanning: {root}")
    scan_result = scan_music(
        root,
        verbose=args.verbose,
        progress_callback=_make_progress_printer("scan"),
    )
    records = scan_result.records

    if args.enrich_musicbrainz:
        print("[enrich] running MusicBrainz enrichment pass")
        try:
            checked, updated, unmatched, tags_written = enrich_with_musicbrainz(
                records,
                app_name="music-cleanup",
                app_version="0.1.0",
                app_contact=args.musicbrainz_contact,
                missing_only=not args.enrich_all,
                min_score=args.musicbrainz_min_score,
                sleep_seconds=args.musicbrainz_sleep_seconds,
                write_tags=args.write_tags,
                verbose=args.verbose,
                progress_callback=_make_progress_printer("enrich"),
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc))
        print(f"[enrich] tracks checked: {checked}")
        print(f"[enrich] tracks updated: {updated}")
        print(f"[enrich] no confident match: {unmatched}")
        if args.write_tags:
            print(f"[enrich] tags written: {tags_written}")

    metrics, format_percent, format_bytes = summarize(records)

    print(f"[done] tracks found: {metrics.total_tracks}")
    print(f"[done] total size: {human_size(metrics.total_size_bytes)}")
    print(f"[done] unique artists: {metrics.unique_artists}")
    print(f"[done] unique albums: {metrics.unique_albums}")
    if format_percent:
        print("[done] format distribution (% by size):")
        for fmt in sorted(format_percent):
            print(f"  - {fmt}: {format_percent[fmt]}% ({human_size(format_bytes.get(fmt, 0))})")

    output_dir.mkdir(parents=True, exist_ok=True)

    if scan_result.warnings:
        warnings_path = output_dir / "scan_warnings.log"
        warnings_path.write_text("\n".join(scan_result.warnings) + "\n", encoding="utf-8")
        print(f"[warn] scan warnings: {len(scan_result.warnings)}")
        print(f"[warn] details written: {warnings_path}")

    if args.export in {"csv", "both"}:
        tracks_csv = output_dir / "tracks_catalog.csv"
        metrics_csv = output_dir / "library_metrics.csv"
        export_tracks_csv(tracks_csv, records)
        export_metrics_csv(metrics_csv, metrics, format_percent, format_bytes)
        print(f"[write] CSV catalog: {tracks_csv}")
        print(f"[write] CSV metrics: {metrics_csv}")

    if args.export in {"sqlite", "both"}:
        db_path = output_dir / "music_catalog.db"
        export_sqlite(db_path, records, metrics, format_percent, format_bytes)
        print(f"[write] SQLite catalog: {db_path}")

    if args.organize:
        destination_root = (args.dest_root or root).expanduser().resolve()
        print(f"[organize] destination root: {destination_root}")
        if not args.apply:
            print("[organize] dry-run mode enabled (pass --apply to execute)")
        organize_result = organize_files(
            records,
            destination_root,
            dry_run=not args.apply,
            copy_instead_of_move=args.copy,
            verbose=args.verbose,
            progress_callback=_make_progress_printer("organize"),
        )
        print(f"[organize] planned/performed file operations: {organize_result.moved}")
        print(f"[organize] skipped (already in place): {organize_result.skipped}")
        print(f"[organize] sidecar files moved/copied: {organize_result.sidecar_moved}")
        if organize_result.warnings:
            warnings_path = output_dir / "organize_warnings.log"
            warnings_path.write_text("\n".join(organize_result.warnings) + "\n", encoding="utf-8")
            print(f"[warn] organize warnings: {len(organize_result.warnings)}")
            print(f"[warn] details written: {warnings_path}")


if __name__ == "__main__":
    main()
