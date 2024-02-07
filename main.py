import os
import sys
import asyncio
from shazamio import Shazam
# Ensure you're using the asyncio version of tqdm for compatibility
from tqdm.asyncio import tqdm


async def recognize_song(file_path, shazam):
    try:
        out = await shazam.recognize_song(file_path)
        title = out['track']['title']
        author = out['track']['subtitle']
        cover_link = out['track']['images']['coverart']
        return {
            'file_path': file_path,  # Include file path for reference
            'title': title,
            'author': author,
            'cover_link': cover_link
        }
    except Exception as e:
        print(f"Error recognizing {file_path}: {e}")
        return {'file_path': file_path, 'error': str(e)}


async def find_and_recognize_mp3_files(folder_path):
    mp3_files = [os.path.join(root, file)
                 for root, dirs, files in os.walk(folder_path)
                 for file in files if file.lower().endswith('.mp3')]

    shazam = Shazam()
    results = []

    # Process each file sequentially with a progress bar
    async for file_path in tqdm(mp3_files, desc="Recognizing Songs"):
        result = await recognize_song(file_path, shazam)
        results.append(result)

    # Print results after all files have been processed
    for result in results:
        if 'error' not in result:
            print(
                f"File: {result['file_path']} - Title: {result['title']}, Author: {result['author']}, Cover Link: {result['cover_link']}")
        else:
            print(f"File: {result['file_path']} - Error: {result['error']}")


async def main():
    folder_path = os.path.dirname(os.path.realpath(
        __file__)) if len(sys.argv) < 2 else sys.argv[1]
    await find_and_recognize_mp3_files(folder_path)

if __name__ == "__main__":
    asyncio.run(main())
