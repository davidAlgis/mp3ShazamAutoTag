import os
import sys
import asyncio
from shazamio import Shazam
from tqdm.asyncio import tqdm
from unidecode import unidecode  # Import unidecode


def sanitize_filename(filename):
    """Sanitize the filename to avoid invalid characters, adjust casing, transliterate to Latin, and ensure non-emptiness."""
    filename = unidecode(filename)  # Transliterate to Latin characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    # Replace '&' with '-'
    filename = filename.replace('&', '-')
    # Change uppercase words to capitalize
    filename = ' '.join(word.capitalize() for word in filename.split())
    if not filename.strip():
        print("The filename became empty after sanitization.")
        filename = "Unnamed_File"
    return filename


async def recognize_and_rename_song(file_path, shazam):
    try:
        out = await shazam.recognize_song(file_path)
        title = out['track']['title']
        author = out['track']['subtitle']
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
