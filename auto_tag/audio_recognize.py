# auto_tag/audio_recognize.py
"""
Recognise audio files with Shazam, optionally rename them,
and (optionally) write tags & cover art.

OGG files are decoded to a temporary WAV via soundfile/libsndfile – no external
ffmpeg binary required.
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from urllib.request import urlopen

import eyed3
import soundfile as sf
from mutagen.flac import Picture
from mutagen.oggvorbis import OggVorbis
from shazamio import Shazam
from tqdm.asyncio import tqdm

from auto_tag.utils import find_deepest_metadata_key, sanitize


# ─────────────────────────────────────────────────────────────────────────────
# bulk scan helper
# ─────────────────────────────────────────────────────────────────────────────
async def find_and_recognize_audio_files(
    folder_path: str,
    *,
    modify: bool = True,
    delay: int = 10,
    nbr_retry: int = 3,
    trace: bool = False,
    extensions: list[str] | tuple[str, ...] = ("mp3", "ogg"),
    output_dir: str | None = None,
    plex_structure: bool = False,
) -> None:
    exts = {e.lower().lstrip(".") for e in extensions}
    audio_files: list[str] = []

    for root, _, files in os.walk(folder_path):
        if "test" in os.path.basename(root).lower():
            continue
        for fn in files:
            if os.path.splitext(fn)[1].lower().lstrip(".") in exts:
                audio_files.append(os.path.join(root, fn))

    if not audio_files:
        print(f"No files with extensions {exts} found in {folder_path}.")
        return

    shazam = Shazam()
    ok = 0
    for path in tqdm(audio_files, desc="Recognising and renaming"):
        res = await recognize_and_rename_file(
            file_path=path,
            shazam=shazam,
            modify=modify,
            delay=delay,
            nbr_retry=nbr_retry,
            trace=trace,
            output_dir=output_dir,
            plex_structure=plex_structure,
        )
        if "error" not in res:
            ok += 1

    print(f"Succeeded {ok}/{len(audio_files)}.")


# ─────────────────────────────────────────────────────────────────────────────
# single-file pipeline
# ─────────────────────────────────────────────────────────────────────────────
async def recognize_and_rename_file(
    *,
    file_path: str,
    shazam: Shazam,
    modify: bool,
    delay: int,
    nbr_retry: int,
    trace: bool,
    output_dir: str | None,
    plex_structure: bool,
) -> dict:
    """Recognise *file_path* with Shazam, optionally rename & tag it."""

    ext = os.path.splitext(file_path)[1].lower()
    tmp_wav: str | None = None

    # 1 ── Shazam with retry (OGG → temp WAV if needed)
    try:
        input_path = file_path
        if ext == ".ogg":
            fd, tmp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                data, sr = sf.read(file_path, dtype="int16")
                sf.write(tmp_wav, data, sr, subtype="PCM_16")
                input_path = tmp_wav
            except Exception as exc:
                if trace:
                    print(f"OGG→WAV conversion failed for {file_path}: {exc}")
                return {"file_path": file_path, "error": "Conversion failed"}

        attempt, out = 0, None
        while attempt < nbr_retry:
            try:
                out = await shazam.recognize(input_path)
                if out:
                    break
            except Exception as exc:
                if trace:
                    print(
                        f"[{os.path.basename(file_path)}] attempt {attempt+1}:"
                        f"{exc}"
                    )
            attempt += 1
            if attempt < nbr_retry:
                await asyncio.sleep(delay)

    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    if not out or "track" not in out:
        if trace:
            print("Shazam failed:", file_path)
        return {"file_path": file_path, "error": "Recognition failed"}

    # 2 ── metadata
    track = out["track"]
    title = track.get("title", "Unknown Title")
    artist = track.get("subtitle", "Unknown Artist")
    album = find_deepest_metadata_key(track, "Album") or "Unknown Album"
    cover = track.get("images", {}).get("coverart", "")

    s_title = sanitize(title, trace)
    s_artist = sanitize(artist, trace)
    s_album = sanitize(album, trace)

    # 3 ── destination path
    if plex_structure:
        new_name = f"{s_title}{ext}"
    else:
        new_name = f"{s_title} - {s_artist} - {s_album}{ext}"

    base_dir = output_dir or os.path.dirname(file_path)
    if plex_structure:
        base_dir = os.path.join(base_dir, s_artist, s_album)
    os.makedirs(base_dir, exist_ok=True)

    new_path = os.path.join(base_dir, new_name)
    counter = 1
    while os.path.exists(new_path) and new_path != file_path:
        stem, ext2 = os.path.splitext(new_path)
        new_path = f"{stem} ({counter}){ext2}"
        counter += 1

    # 4 ── move & tag
    if modify:
        os.rename(file_path, new_path)
        try:
            if ext == ".mp3":
                update_mp3_tags(new_path, s_title, s_artist, s_album)
                if cover:
                    update_mp3_cover_art(new_path, cover, trace)
            elif ext == ".ogg":
                update_ogg_tags(
                    new_path, s_title, s_artist, s_album, cover, trace
                )
        except Exception as exc:
            return {"file_path": file_path, "error": f"Tag error: {exc}"}

    # 5 ── success payload
    return {
        "file_path": file_path,
        "new_file_path": new_path,
        "title": s_title,
        "author": s_artist,
        "album": s_album,
        "cover_link": cover,
    }


# ─────────────────────────────────────────────────────────────────────────────
# tag helpers (unchanged)
# ─────────────────────────────────────────────────────────────────────────────
def update_mp3_cover_art(file_path: str, cover_url: str, trace: bool) -> None:
    if not cover_url:
        if trace:
            print("No cover art:", file_path)
        return
    audio = eyed3.load(file_path)
    if audio.tag is None:
        audio.initTag()
    img = urlopen(cover_url).read()
    audio.tag.images.set(3, img, "image/jpeg", "cover")
    audio.tag.save()


def update_mp3_tags(
    file_path: str, title: str, artist: str, album: str
) -> None:
    audio = eyed3.load(file_path)
    if not audio:
        return
    if audio.tag is None:
        audio.initTag()
    audio.tag.title = title
    audio.tag.artist = artist
    audio.tag.album = album
    audio.tag.save()


def update_ogg_tags(
    file_path: str,
    title: str,
    artist: str,
    album: str,
    cover_url: str,
    trace: bool,
) -> None:
    audio = OggVorbis(file_path)
    audio["TITLE"] = title
    audio["ARTIST"] = artist
    audio["ALBUM"] = album

    if cover_url:
        img = urlopen(cover_url).read()
        pic = Picture()
        pic.data = img
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.width = pic.height = pic.depth = pic.colors = 0
        b64 = base64.b64encode(pic.write()).decode("ascii")
        audio["METADATA_BLOCK_PICTURE"] = [b64]
    elif trace:
        print("No cover art for OGG:", file_path)

    audio.save()