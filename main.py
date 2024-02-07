import os
import sys
import asyncio
from shazamio import Shazam
from tqdm.asyncio import tqdm  # Import the asyncio version of tqdm


async def recognize_song(file_path, shazam):
    try:
        out = await shazam.recognize_song(file_path)
        title = out['track']['title']
        author = out['track']['subtitle']
        cover_link = out['track']['images']['coverart']
        album = out['track'].get('album', {}).get('name', 'Unknown Album')
        return {
            'title': title,
            'author': author,
            'cover_link': cover_link,
            'album': album
        }
    except Exception as e:
        print(f"Error recognizing {file_path}: {e}")
        return None


async def find_and_recognize_mp3_files(folder_path):
    mp3_files = [os.path.join(root, file)
                 for root, dirs, files in os.walk(folder_path)
                 for file in files if file.lower().endswith('.mp3')]

    shazam = Shazam()
    tasks = [recognize_song(file_path, shazam) for file_path in mp3_files]
    results = []

    # Using tqdm to create a progress bar for the asynchronous tasks
    for result in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Recognizing Songs"):
        recognition_result = await result
        results.append(recognition_result)

    for result in results:
        if result:
            print(
                f"Title: {result['title']}, Author: {result['author']}, Album: {result['album']}, Cover Link: {result['cover_link']}")


async def main():
    folder_path = os.path.dirname(os.path.realpath(
        __file__)) if len(sys.argv) < 2 else sys.argv[1]
    await find_and_recognize_mp3_files(folder_path)

if __name__ == "__main__":
    asyncio.run(main())


# import os
# import sys
# import asyncio


# async def find_mp3_files(folder_path):
#     mp3_files = []
#     for root, dirs, files in os.walk(folder_path):
#         for file in files:
#             if file.lower().endswith('.mp3'):
#                 mp3_files.append(os.path.join(root, file))
#     return mp3_files


# async def main():
#     # Use the script's directory as the default folder_path if no argument is given
#     folder_path = os.path.dirname(os.path.realpath(
#         __file__)) if len(sys.argv) < 2 else sys.argv[1]

#     mp3_files = await find_mp3_files(folder_path)

#     if mp3_files:
#         print("Found MP3 files:")
#         for file in mp3_files:
#             print(file)
#     else:
#         print("No MP3 files found in the specified directory.")

# if __name__ == "__main__":
#     asyncio.run(main())


# def fetch_from_shazam():
#     # async def main():
#     shazam = Shazam()
#     out = await shazam.recognize_song('C:\\Users\\david\\Downloads\\autoRenameShazam\\Anime\\Fate⧸Apocrypha - Battle.mp3')
#     print(out)

# loop = asyncio.get_event_loop()
# loop.run_until_complete(main())
