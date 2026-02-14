from __future__ import annotations

import argparse
from pathlib import Path

from .enrichment import enrich_with_musicbrainz
from .exporters import export_metrics_csv, export_sqlite, export_tracks_csv
from .metrics import human_size, summarize
from .organizer import organize_files
from .scanner import scan_music


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

    print(f"[start] scanning: {root}")
    records = scan_music(root, verbose=args.verbose)

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
        moved, skipped = organize_files(
            records,
            destination_root,
            dry_run=not args.apply,
            copy_instead_of_move=args.copy,
            verbose=args.verbose,
        )
        print(f"[organize] planned/performed file operations: {moved}")
        print(f"[organize] skipped (already in place): {skipped}")


if __name__ == "__main__":
    main()
