import os
import sys
import asyncio
from shazamio import Shazam
from tqdm.asyncio import tqdm
from unidecode import unidecode  # Import unidecode
import requests
import eyed3
from eyed3.id3.frames import ImageFrame


def update_mp3_cover_art(file_path, cover_url):
    """Update the cover art of the MP3 file using the image from the given URL."""
    audiofile = eyed3.load(file_path)
    if audiofile.tag is None:
        audiofile.initTag()

    # Download the image from the cover URL
    response = requests.get(cover_url)
    if response.status_code == 200:
        # Remove existing images
        audiofile.tag.images.remove(ImageFrame.FRONT_COVER)
        # Add new image
        audiofile.tag.images.set(
            ImageFrame.FRONT_COVER, response.content, "image/jpeg")
        audiofile.tag.save()
    else:
        print(f"Failed to download cover art from {cover_url}")


def update_mp3_tags(file_path, title, artist):
    """Update the MP3 tags of the given file with the specified title and artist."""
    audiofile = eyed3.load(file_path)
    if audiofile.tag is None:  # If the file has no tags, create a new tag file
        audiofile.initTag()
    audiofile.tag.title = title
    audiofile.tag.artist = artist
    audiofile.tag.save()


def sanitize_filename(filename):
    """Sanitize the filename to avoid invalid characters, adjust casing, transliterate to Latin, and ensure non-emptiness.
    If transliteration results in an empty string, use the original non-Unicode characters."""
    original_filename = filename  # Store the original filename
    filename = unidecode(filename)  # Transliterate to Latin characters

    # If transliteration results in an empty string, revert to the original filename
    if not filename.strip():
        filename = original_filename

    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    # Replace '&' with '-'
    filename = filename.replace('&', '-')
    # Change uppercase words to capitalize
    filename = ' '.join(word.capitalize() for word in filename.split())

    # Final check to ensure filename is not empty after all transformations
    if not filename.strip():
        print("\nWarning: Filename became empty after sanitization.")
        filename = "Unnamed_File"

    return filename


async def recognize_and_rename_song(file_path, shazam):
    try:
        out = await shazam.recognize_song(file_path)
        title = out['track']['title']
        author = out['track']['subtitle']
        # Get the cover art link
        cover_link = out['track']['images']['coverart']

        # Apply transformations to the title and author
        sanitized_title = sanitize_filename(title)
        sanitized_author = sanitize_filename(author)

        # Construct the new filename while avoiding a useless '-' when either part is missing
        new_filename_components = [sanitized_title, sanitized_author]
        new_filename = " - ".join(filter(None,
                                  new_filename_components)) + ".mp3"

        # Get the directory of the original file
        directory = os.path.dirname(file_path)
        new_file_path = os.path.join(directory, new_filename)

        # Rename the file
        os.rename(file_path, new_file_path)

        # Update MP3 tags
        update_mp3_tags(new_file_path, title, author)
        # update_mp3_cover_art(new_file_path, cover_link)

        return {
            'file_path': file_path,
            'new_file_path': new_file_path,
            'title': title,
            'author': author
        }
    except Exception as e:
        print(f"Error recognizing or renaming {file_path}: {e}")
        return {'file_path': file_path, 'error': str(e)}


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
