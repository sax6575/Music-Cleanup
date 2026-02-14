# Music Cleanup

Python CLI to catalog and organize an offline music collection.

## What it does (MVP)
- Scans a provided root directory recursively for audio files
- Reads metadata (artist, album, title, track, year, genre) using Mutagen
- Optionally enriches missing metadata from MusicBrainz before export/organize
- Builds a catalog of tracks
- Computes metrics:
  - total tracks
  - total storage used
  - unique artists
  - unique albums
  - format distribution by storage percentage (`mp3`, `flac`, `wav`, etc.)
- Exports catalog to:
  - CSV (`tracks_catalog.csv`, `library_metrics.csv`)
  - SQLite (`music_catalog.db`)
- Optionally organizes files into:
  - `Artist/Album/<filename>`
  - falls back to `Artist/Miscellaneous/<filename>` when album is missing
- Supports safe dry-run mode for organization by default

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage
### Scan and export catalog + metrics
```bash
music-cleanup "/path/to/music" --export both --output-dir ./output
```

### Organize preview (dry-run)
```bash
music-cleanup "/path/to/music" --organize --dest-root "/path/to/organized/library"
```

### Enrich metadata with MusicBrainz (missing artist/album only)
```bash
music-cleanup "/path/to/music" --enrich-musicbrainz --export both --output-dir ./output
```

### Enrich metadata for all tracks, then organize
```bash
music-cleanup "/path/to/music" \
  --enrich-musicbrainz \
  --enrich-all \
  --organize \
  --dest-root "/path/to/organized/library"
```

### Enrich and write updated tags to files
```bash
music-cleanup "/path/to/music" \
  --enrich-musicbrainz \
  --write-tags \
  --export both
```

### Apply organization changes (move files)
```bash
music-cleanup "/path/to/music" --organize --apply --dest-root "/path/to/organized/library"
```

### Copy instead of move
```bash
music-cleanup "/path/to/music" --organize --apply --copy --dest-root "/path/to/organized/library"
```

## CLI flags
- `root`: top-level directory to scan
- `--output-dir`: output folder for catalog files (default: `./output`)
- `--export {csv,sqlite,both}`
- `--organize`: enable organization pass
- `--dest-root`: destination root for organized structure (default: input root)
- `--apply`: execute file operations (otherwise dry-run)
- `--copy`: copy files instead of moving
- `--enrich-musicbrainz`: query MusicBrainz for metadata updates
- `--enrich-all`: enrich all tracks instead of only missing artist/album
- `--musicbrainz-min-score`: match threshold for applying updates (default: `85`)
- `--musicbrainz-contact`: contact URL/email for MusicBrainz user-agent
- `--musicbrainz-sleep-seconds`: delay between MusicBrainz requests (default: `1.1`)
- `--write-tags`: write enriched artist/album/title/year tags back to files
- `--verbose`: print per-file progress

## Project structure
- `/Users/joshsachs/Desktop/Music Cleanup/src/music_cleanup/cli.py`
- `/Users/joshsachs/Desktop/Music Cleanup/src/music_cleanup/scanner.py`
- `/Users/joshsachs/Desktop/Music Cleanup/src/music_cleanup/metadata.py`
- `/Users/joshsachs/Desktop/Music Cleanup/src/music_cleanup/enrichment.py`
- `/Users/joshsachs/Desktop/Music Cleanup/src/music_cleanup/metrics.py`
- `/Users/joshsachs/Desktop/Music Cleanup/src/music_cleanup/exporters.py`
- `/Users/joshsachs/Desktop/Music Cleanup/src/music_cleanup/organizer.py`

## Roadmap (next iterations)
1. Metadata correctness engine
- detect likely bad/missing tags
- optional auto-fix from filename/folder heuristics
- confidence scoring and change report

2. Duplicate and conflict handling
- hash-based duplicate detection
- smarter collision strategy for same filename/track

3. Quality and integrity checks
- invalid/unreadable audio report
- bitrate/sample-rate outlier reporting

4. Better library analytics
- artist/album summaries
- top storage consumers
- timeline breakdown by year/decade

5. Packaging for broader use
- pipx-ready packaging
- sample config file
- optional progress bar

## Notes
- Keep `--organize` in dry-run first, validate output, then run with `--apply`.
- For large libraries, run export first and inspect `music_catalog.db` before moving files.
- If using `--write-tags`, run on a backup or a small subset first.
