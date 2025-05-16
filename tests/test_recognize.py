import os

import pytest
from shazamio import Shazam

from auto_tag.audio_recognize import (recognize_and_rename_file,
                                      recognize_and_rename_song)

# Define the extensions to test
test_extensions = ["mp3", "ogg"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_recognize_and_rename_song(ext):
    """
    Test that MP3 and OGG files are recognized and renamed correctly in flat structure.
    """
    test_folder = os.path.dirname(os.path.realpath(__file__))
    filename = f"fileToTest.{ext}"
    test_file_path = os.path.join(test_folder, filename)
    expected_new_name = f"Drive My Car - The Beatles - Rubber Soul.{ext}"
    expected_new_file_path = os.path.join(test_folder, expected_new_name)

    # Reset if the expected file already exists
    if os.path.exists(expected_new_file_path):
        os.replace(expected_new_file_path, test_file_path)

    # Ensure the original test file exists
    assert os.path.exists(
        test_file_path
    ), f"Error: The test file {filename} does not exist, so the test could not be launched."

    # Recognize and rename
    shazam = Shazam()
    result = await recognize_and_rename_song(
        test_file_path, filename, shazam, modify=True
    )

    # Verify the file was renamed correctly
    assert os.path.exists(
        expected_new_file_path
    ), f"Test Failed for .{ext.upper()}: The file was not correctly renamed."

    # Cleanup
    os.replace(expected_new_file_path, test_file_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_recognize_and_rename_song_with_plex(ext):
    """
    Test that MP3 and OGG files are recognized and placed in Plex (Artist/Album) structure.
    """
    test_folder = os.path.dirname(os.path.realpath(__file__))
    filename = f"fileToTest.{ext}"
    test_file_path = os.path.join(test_folder, filename)
    # Expected nested directory based on metadata
    artist_dir = os.path.join(test_folder, "The Beatles")
    album_dir = os.path.join(artist_dir, "Rubber Soul")
    expected_new_path = os.path.join(album_dir, f"Drive My Car.{ext}")

    # Reset if already moved by a previous run
    if os.path.exists(expected_new_path):
        os.replace(expected_new_path, test_file_path)
        # Remove empty Plex directories
        os.removedirs(album_dir)

    # Ensure the original file exists
    assert os.path.exists(
        test_file_path
    ), f"Error: The test file {filename} does not exist, so the Plex test could not be launched."

    # Recognize and rename with Plex structure
    shazam = Shazam()
    result = await recognize_and_rename_file(
        test_file_path,
        shazam,
        modify=True,
        delay=1,
        nbr_retry=1,
        trace=False,
        output_dir=None,
        plex_structure=True,
    )

    new_path = result.get("new_file_path")
    # Verify returned path and actual file location
    assert (
        new_path == expected_new_path
    ), f"Expected new path {expected_new_path}, got {new_path}"
    assert os.path.exists(
        expected_new_path
    ), f"Plex structure test failed for .{ext.upper()}: File not found at {expected_new_path}."

    # Cleanup: move back and remove Plex dirs
    os.replace(expected_new_path, test_file_path)
    os.removedirs(album_dir)
