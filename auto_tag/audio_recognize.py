import asyncio
import os
from urllib.request import urlopen

import eyed3
from mutagen.flac import Picture
from mutagen.oggvorbis import OggVorbis
from shazamio import Shazam
from tqdm.asyncio import tqdm
from unidecode import unidecode

from auto_tag.utils import find_deepest_metadata_key


async def find_and_recognize_audio_files(
    folder_path: str,
    modify: bool = True,
    delay: int = 10,
    nbr_retry: int = 3,
    trace: bool = False,
    extensions: list[str] = ("mp3",),
    output_dir: str | None = None,
    plex_structure: bool = False,
):
    # Build list of all matching audio files
    exts = set(e.lower().lstrip(".") for e in extensions)
    audio_files = []
    for root, dirs, files in os.walk(folder_path):
        if "test" in os.path.basename(root).lower():
            continue
        for f in files:
            ext = os.path.splitext(f)[1].lower().lstrip(".")
            if ext in exts:
                audio_files.append(os.path.join(root, f))

    if not audio_files:
        print(f"No files with extensions {exts} found in {folder_path}.")
        return

    shazam = Shazam()
    results = []
    for path in tqdm(audio_files, desc="Recognizing and Renaming"):
        r = await recognize_and_rename_file(
            path,
            shazam,
            modify,
            delay,
            nbr_retry,
            trace,
            output_dir,
            plex_structure,
        )
        results.append(r)

    succeeded = sum(1 for r in results if not r.get("error"))
    print(f"Succeeded {succeeded}/{len(results)}.")


async def recognize_and_rename_file(
    file_path: str,
    shazam: Shazam,
    modify: bool,
    delay: int,
    nbr_retry: int,
    trace: bool,
    output_dir: str | None,
    plex_structure: bool,
) -> dict:
    # 1) Recognize via Shazam with retry
    attempt, out = 0, None
    while attempt < nbr_retry:
        try:
            out = await shazam.recognize(file_path)
            if out:
                break
        except Exception as e:
            if trace:
                print(f"  Attempt {attempt+1} failed: {e}")
        attempt += 1
        if attempt < nbr_retry:
            await asyncio.sleep(delay)

    if not out or "track" not in out:
        if trace:
            print(f"Failed to recognize {file_path}")
        return {"file_path": file_path, "error": "Recognition failed"}

    # 2) Extract & sanitize metadata
    track = out["track"]
    title = track.get("title", "Unknown Title")
    artist = track.get("subtitle", "Unknown Artist")
    album = find_deepest_metadata_key(track, "Album") or "Unknown Album"
    cover_url = track.get("images", {}).get("coverart", "")

    s_title = sanitize_string(title, trace)
    s_artist = sanitize_string(artist, trace)
    s_album = sanitize_string(album, trace)

    # 3) Build new file path
    ext = os.path.splitext(file_path)[1]
    new_name = f"{s_title}{ext}"

    base_dir = output_dir or os.path.dirname(file_path)
    if plex_structure:
        base_dir = os.path.join(base_dir, s_artist, s_album)
    os.makedirs(base_dir, exist_ok=True)

    new_path = os.path.join(base_dir, new_name)
    count, orig = 1, new_path
    while os.path.exists(new_path) and new_path != file_path:
        stem, e2 = os.path.splitext(orig)
        new_path = f"{stem} ({count}){e2}"
        count += 1

    # 4) Rename/move
    if modify:
        os.rename(file_path, new_path)

    # 5) Update tags + cover
    try:
        if ext.lower() == ".mp3":
            update_mp3_tags(new_path, s_title, s_artist, s_album)
            if cover_url:
                update_mp3_cover_art(new_path, cover_url, trace)
        elif ext.lower() == ".ogg":
            update_ogg_tags(
                new_path, s_title, s_artist, s_album, cover_url, trace
            )
    except Exception as e:
        return {"file_path": file_path, "error": f"Tag error: {e}"}

    return {"file_path": file_path, "new_file_path": new_path}


def update_mp3_cover_art(file_path, cover_url, trace):
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


def update_mp3_tags(file_path, title, artist, album):
    audio = eyed3.load(file_path)
    if not audio:
        return
    if audio.tag is None:
        audio.initTag()
    audio.tag.title = title
    audio.tag.artist = artist
    audio.tag.album = album
    audio.tag.save()


def update_ogg_tags(file_path, title, artist, album, cover_url, trace):
    audio = OggVorbis(file_path)
    audio["TITLE"] = title
    audio["ARTIST"] = artist
    audio["ALBUM"] = album
    audio.save()
    if cover_url:
        img = urlopen(cover_url).read()
        pic = Picture()
        pic.data = img
        pic.type = 3
        pic.mime = "image/jpeg"
        pics = audio.metadata_block_pictures or []
        pics.append(pic.write())
        audio.metadata_block_pictures = pics
        audio.save()
    elif trace:
        print("No cover art for OGG:", file_path)


def sanitize_string(s, trace):
    orig = s
    s = unidecode(s)
    # remove parenthetical
    out, skip = "", 0
    for c in s:
        if c == "(":
            skip += 1
        elif c == ")" and skip > 0:
            skip -= 1
        elif skip == 0:
            out += c
    s = out or orig
    for ch in '<>:"/\\|?*':
        s = s.replace(ch, "")
    s = s.replace("&", "-")
    s = " ".join(w.capitalize() for w in s.split())
    if not s.strip():
        if trace:
            print("Empty after sanitize:", orig)
        s = "Unknown"
    return s
