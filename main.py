import os
import sys
import asyncio
from shazamio import Shazam
from tqdm.asyncio import tqdm
from unidecode import unidecode
import eyed3
from eyed3.id3.frames import ImageFrame
import argparse
import time

delay = 10


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


async def recognize_and_rename_song(file_path, shazam, modify=True):
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
        print(
            f"\nError recognizing {file_path}: {e}.\nRetry once with delay of {delay} seconds")
        # return {'file_path': file_path, 'error': str(e)}
        time.sleep(delay)
        try:
            out = await shazam.recognize_song(file_path)
        except Exception as e:
            print(f"Error recognizing {file_path}: {e}")
            return {'file_path': file_path, 'error': str(e)}

    # Extract necessary information from recognition result
    track_info = out.get('track', {})
    title = track_info.get('title', 'Unknown Title')
    author = track_info.get('subtitle', 'Unknown Artist')
    images = track_info.get('images', {})
    cover_link = images.get('coverart', '')  # Default to empty if no cover art
    if (title == 'Unknown Title'):
        print(f"\nCould not recognize {file_path}, will not modify it.")
        new_file_path = file_path
    else:
        # Sanitize, rename, and update MP3 file
        sanitized_title = sanitize_filename(title)
        sanitized_author = sanitize_filename(author)
        new_filename_components = [sanitized_title, sanitized_author]
        new_filename = " - ".join(filter(None,
                                  new_filename_components)) + ".mp3"
        directory = os.path.dirname(file_path)
        new_file_path = os.path.join(directory, new_filename)

        # Check if a file with the new name already exists and append a number to make it unique
        counter = 1
        base_new_filename = new_filename
        while os.path.exists(new_file_path):
            print(
                f"Warning: File {new_file_path} already exists. Trying a new name.")
            new_filename = os.path.splitext(base_new_filename)[
                0] + f" ({counter})" + os.path.splitext(base_new_filename)[1]
            new_file_path = os.path.join(directory, new_filename)
            counter += 1

        if (modify):
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


async def find_and_recognize_mp3_files(folder_path, modify=True):
    mp3_files = []
    test_folder_name = "test"  # Name of the test folder to exclude

    for root, dirs, files in os.walk(folder_path):
        # Skip files in the test folder by checking if 'test' is part of the current root path
        if test_folder_name in os.path.split(root)[1].lower():
            continue  # Skip this iteration, effectively excluding files in the 'test' folder
        for file in files:
            if file.lower().endswith('.mp3'):
                mp3_files.append(os.path.join(root, file))

    if (len(mp3_files) == 0):
        print(f"No mp3 founds in {folder_path} exit !")
        return
    shazam = Shazam()
    results = []

    # Process each MP3 file not in the 'test' folder
    async for file_path in tqdm(mp3_files, desc="Recognizing and Renaming Songs"):
        result = await recognize_and_rename_song(file_path, shazam, modify)
        results.append(result)

    action = ""
    if (modify):
        action = "Renamed"
    else:
        action = "Will be renamed in:"
    # Print results after all files have been processed
    for result in results:
        if 'error' not in result:
            print(
                f"{action}: {result['file_path']} -> {result['new_file_path']}")
        else:
            print(f"File: {result['file_path']} - Error: {result['error']}")


async def test():
    test_folder = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), "test")
    test_file_path = os.path.join(test_folder, "fileToTest.mp3")
    expected_new_file_path = os.path.join(
        test_folder, "Gerudo Valley (live) - The Legend Of Zelda.mp3")

    # if the file Gerudo Valley (live) - The Legend Of Zelda.mp3 exists we rename it to fileToTest.mp3
    if os.path.exists(expected_new_file_path):
        os.rename(expected_new_file_path, test_file_path)

    # Check if the test file exists
    if not os.path.exists(test_file_path):
        print("Error: The test file does not exist, so the test could not be launched.")
        return

    # Apply the recognize_and_rename_song function on this file
    # Assuming shazam is an initialized instance of the Shazam client you would use in your actual script
    shazam = Shazam()  # You may need to adjust based on your actual initialization
    modify = True  # Assuming you want to apply modifications in the test

    # Call the function synchronously for simplicity in demonstration, adjust as needed
    await recognize_and_rename_song(test_file_path, shazam, modify)

    # Check if the file was correctly renamed
    if os.path.exists(expected_new_file_path):
        print("Test Success: The file was correctly renamed to 'Gerudo Valley (live) - The Legend Of Zelda.mp3'.")
        # Rename the file back to its original name for other tests
        os.rename(expected_new_file_path, test_file_path)
    else:
        print("Test Failed: The file was not correctly renamed.")


async def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description="Process MP3 files with Shazam recognition and optional renaming and tagging.")
    parser.add_argument("-d", "--directory",
                        help="Specify the directory to process MP3 files.")
    parser.add_argument("-t", "--test", action="store_true",
                        help="Call the test function.")
    parser.add_argument("-m", "--modify", type=bool, default=True,
                        help="Indicate if modifications to tag and file name should be applied (default is True).")
    parser.add_argument("-de", "--delay", type=int, default=10,
                        help="Sometimes shazam api failed due delay, therefore you can retry once after the delay given by this argument.")
    args = parser.parse_args()

    # Handle the test argument
    if args.test:
        await test()
        return  # Exit after test function if test argument is provided
    delay = args.delay

    # Handle the directory argument
    folder_path = args.directory if args.directory else os.path.dirname(
        os.path.realpath(__file__))

    await find_and_recognize_mp3_files(folder_path, args.modify)

if __name__ == "__main__":
    asyncio.run(main())
