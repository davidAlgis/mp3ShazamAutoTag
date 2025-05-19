# auto_tag/audio_recognize.py
"""
Recognise audio files with Shazam, optionally rename or copy them,
and update metadata (tags, cover art).

OGG files are converted to WAV via soundfile/libsndfile (no ffmpeg),
but if conversion or recognition on WAV fails, we fall back to the
original OGG for recognition—so tests with DummyShazam still work.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import tempfile
from urllib.request import urlopen

import eyed3
import soundfile as sf
from mutagen import File
from mutagen.flac import Picture
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from shazamio import Shazam
from tqdm.asyncio import tqdm

from auto_tag.utils import find_deepest_metadata_key, sanitize


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
    copy_to: str | None = None,
) -> None:
    """
    Walk folder_path, recognise each file, then move or copy/tag it.
    copy_to, if given, is the base dir to copy files into (instead of moving).
    """
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
            copy_to=copy_to,
        )
        if "error" in res and trace:
            print(f"[{os.path.basename(path)}] {res['error']}")
        if "error" not in res:
            ok += 1

    print(f"Succeeded {ok}/{len(audio_files)}.")


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
    copy_to: str | None = None,
) -> dict:
    """
    Recognise file_path with Shazam, then move or copy & tag it.
    - If copy_to is set, the file is **copied** to that directory (with or
      without Plex subfolders) and the original remains untouched.
    - Otherwise it is **moved** (renamed) in place or under the output_dir.
    """
    ext = os.path.splitext(file_path)[1].lower()
    tmp_wav: str | None = None

    # 1) For OGG, try to convert to WAV first
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
                print(f"[{os.path.basename(file_path)}] OGG→WAV failed: {exc}")
            input_path = file_path  # fallback

    # 2) Recognise with retries
    out = None
    for attempt in range(1, nbr_retry + 1):
        try:
            candidate = await shazam.recognize(input_path)
            if candidate:
                out = candidate
                break
        except Exception as exc:
            if trace:
                print(
                    f"[{os.path.basename(file_path)}] attempt {attempt}: {exc}"
                )
        if attempt < nbr_retry:
            await asyncio.sleep(delay)

    # Fallback for OGG if WAV recognition failed
    if ext == ".ogg" and out is None and input_path != file_path:
        for attempt in range(1, nbr_retry + 1):
            try:
                candidate = await shazam.recognize(file_path)
                if candidate:
                    out = candidate
                    break
            except Exception as exc:
                if trace:
                    print(
                        f"[{os.path.basename(file_path)}] OGG fallback"
                        f" attempt {attempt}: {exc}"
                    )
            if attempt < nbr_retry:
                await asyncio.sleep(delay)

    # cleanup
    if tmp_wav and os.path.exists(tmp_wav):
        os.remove(tmp_wav)

    if not out or "track" not in out:
        if trace:
            print(f"Shazam failed: {file_path}")
        return {"file_path": file_path, "error": "Recognition failed"}

    # 3) Extract metadata
    track = out["track"]
    title = track.get("title", "Unknown Title")
    artist = track.get("subtitle", "Unknown Artist")
    album = find_deepest_metadata_key(track, "Album") or "Unknown Album"
    cover = track.get("images", {}).get("coverart", "")

    s_title = sanitize(title, trace)
    s_artist = sanitize(artist, trace)
    s_album = sanitize(album, trace)

    # 4) Build filename
    if plex_structure:
        new_name = f"{s_title}{ext}"
    else:
        new_name = f"{s_title} - {s_artist} - {s_album}{ext}"

    # 5) Determine the root folder for the new file
    root_dir = copy_to or output_dir or os.path.dirname(file_path)
    if plex_structure:
        root_dir = os.path.join(root_dir, s_artist, s_album)
    os.makedirs(root_dir, exist_ok=True)

    # 6) Ensure uniqueness
    new_path = os.path.join(root_dir, new_name)
    count = 1
    while os.path.exists(new_path) and new_path != file_path:
        stem, e2 = os.path.splitext(new_path)
        new_path = f"{stem} ({count}){e2}"
        count += 1

    # 7) Move or copy & tag
    if modify:
        try:
            if copy_to:
                shutil.copy2(file_path, new_path)
            else:
                os.rename(file_path, new_path)

            if ext == ".mp3":
                update_mp3_tags(new_path, s_title, s_artist, s_album)
                if cover:
                    update_mp3_cover_art(new_path, cover, trace)
            else:  # .ogg
                update_ogg_tags(
                    new_path, s_title, s_artist, s_album, cover, trace
                )

        except Exception as exc:
            return {"file_path": file_path, "error": f"Tag error: {exc}"}

    return {
        "file_path": file_path,
        "new_file_path": new_path,
        "title": s_title,
        "author": s_artist,
        "album": s_album,
        "cover_link": cover,
    }


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
    # Try Vorbis, then Opus, then generic
    try:
        audio = OggVorbis(file_path)
    except Exception:
        try:
            audio = OggOpus(file_path)
        except Exception:
            audio = File(file_path)
            if audio is None:
                raise RuntimeError("Unsupported OGG type for tagging")

    # Mutagen expects tag values as lists
    audio["TITLE"] = [title]
    audio["ARTIST"] = [artist]
    audio["ALBUM"] = [album]

    if cover_url:
        try:
            img = urlopen(cover_url).read()
            pic = Picture()
            pic.data = img
            pic.type = 3
            pic.mime = "image/jpeg"
            pic.width = pic.height = pic.depth = pic.colors = 0
            b64 = base64.b64encode(pic.write()).decode("ascii")
            audio["METADATA_BLOCK_PICTURE"] = [b64]
        except Exception as exc:
            if trace:
                print("Cover art error:", exc)
    elif trace:
        print("No cover art for OGG:", file_path)

    audio.save()