from __future__ import annotations

from pathlib import Path

try:
    from mutagen import File
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    File = None


AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".aiff",
    ".alac",
}


def is_audio_file(path: Path) -> bool:
    # macOS AppleDouble sidecar files (._*) are metadata blobs, not audio.
    if path.name.startswith("._"):
        return False
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def _first(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        if not value:
            return ""
        return str(value[0]).strip()
    return str(value).strip()


def _tag_value(tags: object, *keys: str) -> str:
    if tags is None:
        return ""

    for key in keys:
        value = None
        try:
            value = tags.get(key)
        except Exception:
            value = None
        if value:
            return _first(value)

    return ""


def read_audio_info(path: Path) -> dict[str, object]:
    if File is None:
        return {
            "artist": "",
            "album": "",
            "title": path.stem,
            "track_number": "",
            "year": "",
            "genre": "",
            "duration_seconds": None,
            "bitrate_kbps": None,
            "sample_rate_hz": None,
            "metadata_source": "none-no-mutagen",
        }

    try:
        audio = File(path, easy=True)
    except Exception:
        return {
            "artist": "",
            "album": "",
            "title": path.stem,
            "track_number": "",
            "year": "",
            "genre": "",
            "duration_seconds": None,
            "bitrate_kbps": None,
            "sample_rate_hz": None,
            "metadata_source": "none-invalid",
        }
    if audio is None:
        return {
            "artist": "",
            "album": "",
            "title": path.stem,
            "track_number": "",
            "year": "",
            "genre": "",
            "duration_seconds": None,
            "bitrate_kbps": None,
            "sample_rate_hz": None,
            "metadata_source": "none",
        }

    info = getattr(audio, "info", None)
    duration_seconds = getattr(info, "length", None)
    sample_rate_hz = getattr(info, "sample_rate", None)
    bitrate = getattr(info, "bitrate", None)
    bitrate_kbps = int(bitrate / 1000) if isinstance(bitrate, (int, float)) else None

    tags = getattr(audio, "tags", None)

    artist = _tag_value(tags, "artist", "albumartist", "ARTIST", "TPE1", "\u00a9ART")
    album = _tag_value(tags, "album", "ALBUM", "TALB", "\u00a9alb")
    title = _tag_value(tags, "title", "TITLE", "TIT2", "\u00a9nam")
    track_number = _tag_value(tags, "tracknumber", "TRACKNUMBER", "TRCK", "trkn")
    year = _tag_value(tags, "date", "year", "DATE", "TDRC", "\u00a9day")
    genre = _tag_value(tags, "genre", "GENRE", "TCON", "\u00a9gen")

    return {
        "artist": artist,
        "album": album,
        "title": title or path.stem,
        "track_number": track_number,
        "year": year,
        "genre": genre,
        "duration_seconds": float(duration_seconds) if isinstance(duration_seconds, (int, float)) else None,
        "bitrate_kbps": bitrate_kbps,
        "sample_rate_hz": int(sample_rate_hz) if isinstance(sample_rate_hz, (int, float)) else None,
        "metadata_source": "tags" if tags else "audio-info",
    }


def normalized_artist(value: str) -> str:
    value = value.strip()
    return value if value else "Unknown Artist"


def normalized_album(value: str) -> str:
    value = value.strip()
    return value if value else "Miscellaneous"


def normalized_title(value: str, fallback: str) -> str:
    value = value.strip()
    return value if value else fallback


def write_audio_tags(
    path: Path,
    artist: str,
    album: str,
    title: str,
    track_number: str = "",
    year: str = "",
    genre: str = "",
) -> bool:
    if File is None:
        return False

    try:
        audio = File(path, easy=True)
    except Exception:
        return False

    if audio is None:
        return False

    tag_map = {
        "artist": artist,
        "album": album,
        "title": title,
        "tracknumber": track_number,
        "date": year,
        "genre": genre,
    }

    try:
        for key, value in tag_map.items():
            if value:
                audio[key] = [value]
        audio.save()
    except Exception:
        return False

    return True
