from __future__ import annotations

import time
from typing import Callable, Optional

from .metadata import normalized_album, normalized_artist, normalized_title, write_audio_tags
from .models import TrackRecord

try:
    import musicbrainzngs
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    musicbrainzngs = None


def _strip_year(date_value: str) -> str:
    if not date_value:
        return ""
    if len(date_value) >= 4 and date_value[:4].isdigit():
        return date_value[:4]
    return date_value


def _result_score(item: dict) -> int:
    score = item.get("ext:score", "0")
    try:
        return int(score)
    except (TypeError, ValueError):
        return 0


def _extract_best_candidate(recordings: list[dict]) -> Optional[dict]:
    if not recordings:
        return None
    ranked = sorted(recordings, key=_result_score, reverse=True)
    return ranked[0]


def _release_title(candidate: dict) -> str:
    releases = candidate.get("release-list", [])
    if not releases:
        return ""
    title = releases[0].get("title", "")
    return str(title).strip()


def _artist_name(candidate: dict) -> str:
    value = candidate.get("artist-credit-phrase", "")
    return str(value).strip()


def _recording_title(candidate: dict) -> str:
    value = candidate.get("title", "")
    return str(value).strip()


def _recording_year(candidate: dict) -> str:
    value = candidate.get("first-release-date", "")
    return _strip_year(str(value).strip())


def _needs_enrichment(record: TrackRecord, missing_only: bool) -> bool:
    if not missing_only:
        return True

    missing_artist = not record.artist.strip() or record.artist.strip().lower() == "unknown artist"
    missing_album = not record.album.strip() or record.album.strip().lower() == "miscellaneous"
    return missing_artist or missing_album


def enrich_with_musicbrainz(
    records: list[TrackRecord],
    app_name: str,
    app_version: str,
    app_contact: str,
    missing_only: bool = True,
    min_score: int = 85,
    sleep_seconds: float = 1.1,
    write_tags: bool = False,
    verbose: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[int, int, int, int]:
    if musicbrainzngs is None:
        raise RuntimeError("musicbrainzngs is not installed. Run: pip install musicbrainzngs")

    musicbrainzngs.set_useragent(app_name, app_version, app_contact)

    updated = 0
    unmatched = 0
    checked = 0
    tags_written = 0

    candidates = [record for record in records if _needs_enrichment(record, missing_only=missing_only)]
    total_candidates = len(candidates)
    if progress_callback:
        progress_callback(0, total_candidates)

    for idx, record in enumerate(candidates, start=1):

        checked += 1

        query_artist = "" if record.artist == "Unknown Artist" else record.artist
        query_title = normalized_title(record.title, record.file_path.stem)

        if not query_title:
            unmatched += 1
            if progress_callback:
                progress_callback(idx, total_candidates)
            continue

        try:
            response = musicbrainzngs.search_recordings(
                recording=query_title,
                artist=query_artist if query_artist else None,
                limit=5,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            if verbose:
                print(f"[enrich] query failed for {record.relative_path}: {exc}")
            unmatched += 1
            time.sleep(sleep_seconds)
            if progress_callback:
                progress_callback(idx, total_candidates)
            continue

        recordings = response.get("recording-list", [])
        candidate = _extract_best_candidate(recordings)
        if not candidate:
            unmatched += 1
            time.sleep(sleep_seconds)
            if progress_callback:
                progress_callback(idx, total_candidates)
            continue

        score = _result_score(candidate)
        if score < min_score:
            unmatched += 1
            if verbose:
                print(f"[enrich] low score {score} for {record.relative_path}")
            time.sleep(sleep_seconds)
            if progress_callback:
                progress_callback(idx, total_candidates)
            continue

        new_artist = normalized_artist(_artist_name(candidate) or record.artist)
        new_album = normalized_album(_release_title(candidate) or record.album)
        new_title = normalized_title(_recording_title(candidate) or record.title, record.file_path.stem)
        new_year = _recording_year(candidate) or record.year

        changed = (
            new_artist != record.artist
            or new_album != record.album
            or new_title != record.title
            or new_year != record.year
        )

        if changed:
            if verbose:
                print(
                    f"[enrich] {record.relative_path}: "
                    f"artist='{record.artist}' -> '{new_artist}', "
                    f"album='{record.album}' -> '{new_album}'"
                )
            record.artist = new_artist
            record.album = new_album
            record.title = new_title
            record.year = new_year
            record.metadata_source = "musicbrainz"
            updated += 1
            if write_tags:
                saved = write_audio_tags(
                    record.file_path,
                    artist=record.artist,
                    album=record.album,
                    title=record.title,
                    track_number=record.track_number,
                    year=record.year,
                    genre=record.genre,
                )
                if saved:
                    tags_written += 1

        time.sleep(sleep_seconds)
        if progress_callback:
            progress_callback(idx, total_candidates)

    return checked, updated, unmatched, tags_written
