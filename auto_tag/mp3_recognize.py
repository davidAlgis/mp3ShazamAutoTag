import os
import asyncio
from shazamio import Shazam
from tqdm.asyncio import tqdm
from unidecode import unidecode
import eyed3
from urllib.request import urlopen
from auto_tag.utils import find_deepest_metadata_key


def update_mp3_cover_art(file_path, cover_url, trace):
    """
    Update the cover art of the MP3 file using the image from the given URL.
    If no URL is provided, prints a warning message.

    Parameters:
    - file_path: The path to the MP3 file whose cover art is to be updated.
    - cover_url: The URL of the new cover image.
    """
    if cover_url == "":
        if trace:
            print("\nNo cover found for ", file_path)
        return

    audiofile = eyed3.load(file_path)
    if audiofile.tag is None:
        audiofile.initTag()

    audiofile.tag.images.set(
        3,
        img_data=urlopen(cover_url).read(),
        mime_type="image/jpg",
        description="cover",
    )
    audiofile.tag.save()


def update_mp3_tags(file_path: str, title: str, artist: str, album: str):
    """
    Update the MP3 tags of the given file with the specified title and artist.

    Parameters:
    - file_path: The path to the MP3 file to be tagged.
    - title: The title tag to be set for the MP3 file.
    - artist: The artist tag to be set for the MP3 file.
    """
    audiofile = eyed3.load(file_path)
    if not audiofile:
        return
    if audiofile.tag is None:
        audiofile.initTag()
    audiofile.tag.title = title
    audiofile.tag.artist = artist
    audiofile.tag.album = album
    audiofile.tag.save()


def sanitize_string(filename, trace):
    """
    Sanitize the filename to remove invalid characters, adjust casing, and transliterate to Latin characters.
    Ensures the filename is not empty after transformations. If transliteration results in an empty string,
    uses the original filename with non-Unicode characters.

    Parameters:
    - filename: The original filename to be sanitized.

    Returns:
    - A sanitized, safe filename with adjustments made for file system compatibility.
    """
    original_filename = filename  # Store the original filename
    filename = unidecode(filename)  # Attempt to transliterate to ASCII

    # Manually remove content within parentheses
    new_filename = ""
    skip = 0
    for char in filename:
        if char == "(":
            skip += 1
        elif char == ")" and skip > 0:
            skip -= 1
        elif skip == 0:
            new_filename += char
    filename = new_filename

    # Revert to the original filename if transliteration results in an empty string
    if not filename.strip():
        filename = original_filename

    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        # Remove invalid file name characters
        filename = filename.replace(char, "")
    filename = filename.replace("&", "-")  # Replace '&' with '-'
    # Change uppercase words to capitalize (first letter uppercase, rest lowercase)
    filename = " ".join(word.capitalize() for word in filename.split())

    if not filename.strip():
        if trace:
            print("\nWarning: Filename became empty after sanitization.")
        filename = "Unknown song"  # Default filename if all else fails

    return filename


async def recognize_and_rename_song(
    file_path: str,
    file_name: str,
    shazam: Shazam,
    modify=True,
    delay=10,
    nbrRetry=3,
    trace=False,
):
    """
    Recognize a song using Shazam, rename the MP3 file based on the song title and artist,
    and update its tags and cover art accordingly.

    Parameters:
    - file_path: The path to the MP3 file to be recognized and renamed.
    - shazam: An instance of the Shazam client.
    """
    attempt = 0
    out = None
    errorStr = ""
    while attempt < nbrRetry:
        try:
            out = await shazam.recognize(file_path)
            if out:  # Assuming 'out' being non-empty means success
                break
        except Exception as e:
            errorStr = f"Exception : {e}"
            print(errorStr)
            attempt += 1
        if attempt < nbrRetry:
            await asyncio.sleep(delay)

    if out is None:
        if trace:
            print(
                f"\nFailed to recognize {file_name} after {nbrRetry} attempts. Error {errorStr}"
            )
        return {"file_path": file_name, "error": "Could not recognize file"}

    # Extract necessary information from recognition result
    track_info = out.get("track", {})
    title = track_info.get("title", "Unknown Title")
    author = track_info.get("subtitle", "Unknown Artist")
    album = find_deepest_metadata_key(track_info, "Album") or "Unknown Album"
    images = track_info.get("images", {})
    cover_link = images.get("coverart", "")  # Default to empty if no cover art
    if title == "Unknown Title" and trace:
        print(f"\nCould not recognize {file_name}, will not modify it.")
        return {"file_path": file_name, "error": "Could not recognize file"}

    # Sanitize, rename, and update MP3 file
    sanitized_title = sanitize_string(title, trace)
    sanitized_author = sanitize_string(author, trace)
    sanitized_album = sanitize_string(album, trace)
    new_filename_components = [
        sanitized_title, sanitized_author, sanitized_album
    ]
    new_filename = " - ".join(filter(None, new_filename_components)) + ".mp3"
    directory = os.path.dirname(file_path)
    new_file_path = os.path.join(directory, new_filename)

    # Check if a file with the new name already exists and append a number to make it unique
    counter = 1
    base_new_filename = new_filename
    while os.path.exists(new_file_path):
        if new_filename == file_name:
            break
        if trace:
            print(
                f"\nWarning: File {new_file_path} already exists. Trying a new name."
            )
        new_filename = (os.path.splitext(base_new_filename)[0] +
                        f" ({counter})" +
                        os.path.splitext(base_new_filename)[1])
        new_file_path = os.path.join(directory, new_filename)
        counter += 1

    if modify:
        os.rename(file_path, new_file_path)
        # Update tags and cover art
        try:
            update_mp3_tags(new_file_path, sanitized_title, sanitized_author,
                            sanitized_album)
        except Exception as e:
            if trace:
                print(f"\nError updating mp3 tag {file_path}: {e}")
            return {"file_path": file_path, "error": str(e)}
        try:
            update_mp3_cover_art(new_file_path, cover_link, trace)
        except Exception as e:
            if trace:
                print(f"\nError updating cover {file_path}: {e}")

    return {
        "file_path": file_path,
        "new_file_path": new_file_path,
        "title": title,
        "author": author,
        "cover_link": cover_link,
    }


async def find_and_recognize_mp3_files(folder_path,
                                       modify=True,
                                       delay=10,
                                       nbrRetry=3,
                                       trace=False):
    mp3_files_path = []
    test_folder_name = "test"  # Name of the test folder to exclude
    if (test_folder_name in folder_path):
        print(
            "Cannot recognize mp3 files from a folder name \"test\". Please use another name."
        )
        return
    trace = True
    for root, dirs, files in os.walk(folder_path):
        # Skip files in the test folder by checking if 'test' is part of the current root path
        if test_folder_name in os.path.split(root)[1].lower():
            continue  # Skip this iteration, effectively excluding files in the 'test' folder
        for file in files:
            if file.lower().endswith(".mp3"):
                mp3_files_path.append([file, os.path.join(root, file)])

    if len(mp3_files_path) == 0:
        print(f"No mp3 founds in {folder_path} exit !")
        return
    shazam = Shazam()
    results = []

    # Process each MP3 file not in the 'test' folder
    async for file_path in tqdm(mp3_files_path,
                                desc="Recognizing and Renaming Songs"):
        result = await recognize_and_rename_song(file_path[1], file_path[0],
                                                 shazam, modify, delay,
                                                 nbrRetry, trace)
        results.append(result)

    action = ""
    if modify:
        action = "Renamed"
    else:
        action = "Will be renamed in:"
    if trace:
        print(
            "\n\n------------------------------- End Recognize and Rename Process -------------------------------\n\n"
        )
    # Print results after all files have been processed
    succeed = 0
    for result in results:
        if "error" not in result:
            succeed += 1
            if trace:
                print(
                    f"{action}: {result['file_path']} -> {result['new_file_path']}"
                )
        else:
            if trace:
                print(
                    f"File: {result['file_path']} - Error: {result['error']}")
    print(f"Succeed {succeed}/{len(results)}.")
