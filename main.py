import os
import sys
import asyncio
from shazamio import Shazam
from tqdm.asyncio import tqdm
from unidecode import unidecode
import eyed3
from eyed3.id3.frames import ImageFrame


def update_mp3_cover_art(file_path, cover_url):
    """
    Update the cover art of the MP3 file using the image from the given URL.
    If no URL is provided, prints a warning message.

    Parameters:
    - file_path: The path to the MP3 file whose cover art is to be updated.
    - cover_url: The URL of the new cover image.
    """
    if cover_url == '':
        print("\nNo cover found for ", file_path)
        return

    audiofile = eyed3.load(file_path)
    if audiofile.tag is None:
        audiofile.initTag()

    # eyed3's current version does not support directly setting an image from a URL,
    # so this placeholder function demonstrates intent. You'll need to download the image and then use it.
    audiofile.tag.images.set(type_=3, img_data=None, mime_type=None,
                             description="",
                             img_url=cover_url)


def update_mp3_tags(file_path, title, artist):
    """
    Update the MP3 tags of the given file with the specified title and artist.

    Parameters:
    - file_path: The path to the MP3 file to be tagged.
    - title: The title tag to be set for the MP3 file.
    - artist: The artist tag to be set for the MP3 file.
    """
    audiofile = eyed3.load(file_path)
    if audiofile.tag is None:
        audiofile.initTag()
    audiofile.tag.title = title
    audiofile.tag.artist = artist
    audiofile.tag.save()


def sanitize_filename(filename):
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

    # Revert to the original filename if transliteration results in an empty string
    if not filename.strip():
        filename = original_filename

    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        # Remove invalid file name characters
        filename = filename.replace(char, '')
    filename = filename.replace('&', '-')  # Replace '&' with '-'
    # Change uppercase words to capitalize (first letter uppercase, rest lowercase)
    filename = ' '.join(word.capitalize() for word in filename.split())

    if not filename.strip():
        print("\nWarning: Filename became empty after sanitization.")
        filename = "Unnamed_File"  # Default filename if all else fails

    return filename


async def recognize_and_rename_song(file_path, shazam):
    """
    Recognize a song using Shazam, rename the MP3 file based on the song title and artist,
    and update its tags and cover art accordingly.

    Parameters:
    - file_path: The path to the MP3 file to be recognized and renamed.
    - shazam: An instance of the Shazam client.
    """
    try:
        out = await shazam.recognize_song(file_path)
    except Exception as e:
        print(f"\nError recognizing {file_path}: {e}")
        return {'file_path': file_path, 'error': str(e)}

    # Extract necessary information from recognition result
    track_info = out.get('track', {})
    title = track_info.get('title', 'Unknown Title')
    author = track_info.get('subtitle', 'Unknown Artist')
    images = track_info.get('images', {})
    cover_link = images.get('coverart', '')  # Default to empty if no cover art

    # Sanitize, rename, and update MP3 file
    sanitized_title = sanitize_filename(title)
    sanitized_author = sanitize_filename(author)
    new_filename_components = [sanitized_title, sanitized_author]
    new_filename = " - ".join(filter(None, new_filename_components)) + ".mp3"
    directory = os.path.dirname(file_path)
    new_file_path = os.path.join(directory, new_filename)
    os.rename(file_path, new_file_path)

    # Update tags and cover art
    try:
        update_mp3_tags(new_file_path, title, author)
    except Exception as e:
        print(f"\nError updating mp3 tag {file_path}: {e}")
        return {'file_path': file_path, 'error': str(e)}
    try:
        update_mp3_cover_art(new_file_path, cover_link)
    except Exception as e:
        print(f"\nError updating cover {file_path}: {e}")

    return {
        'file_path': file_path,
        'new_file_path': new_file_path,
        'title': title,
        'author': author,
        'cover_link': cover_link
    }


async def find_and_recognize_mp3_files(folder_path):
    mp3_files = [os.path.join(root, file)
                 for root, dirs, files in os.walk(folder_path)
                 for file in files if file.lower().endswith('.mp3')]

    shazam = Shazam()
    results = []

    # Process each file sequentially with a progress bar
    async for file_path in tqdm(mp3_files, desc="Recognizing and Renaming Songs"):
        result = await recognize_and_rename_song(file_path, shazam)
        results.append(result)

    # Print results after all files have been processed
    for result in results:
        if 'error' not in result:
            print(
                f"Renamed: {result['file_path']} -> {result['new_file_path']}")
        else:
            print(f"File: {result['file_path']} - Error: {result['error']}")


async def main():
    folder_path = os.path.dirname(os.path.realpath(
        __file__)) if len(sys.argv) < 2 else sys.argv[1]
    await find_and_recognize_mp3_files(folder_path)

if __name__ == "__main__":
    asyncio.run(main())
