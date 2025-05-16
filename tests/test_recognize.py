import os

import pytest
from shazamio import Shazam

from auto_tag.audio_recognize import recognize_and_rename_song

test_extensions = ["mp3", "ogg"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_recognize_and_rename_song(ext):
    # Define the test folder and file paths relative to the location of this test script
    test_folder = os.path.dirname(os.path.realpath(__file__))
    filename = f"fileToTest.{ext}"
    test_file_path = os.path.join(test_folder, filename)
    expected_new_name = f"Drive My Car - The Beatles - Rubber Soul.{ext}"
    expected_new_file_path = os.path.join(test_folder, expected_new_name)

    # If the expected new file exists, rename it back to the test file to reset state
    if os.path.exists(expected_new_file_path):
        os.rename(expected_new_file_path, test_file_path)

    # Ensure the test file exists before running
    assert os.path.exists(
        test_file_path
    ), f"Error: The test file {filename} does not exist, so the test could not be launched."

    # Initialize Shazam and call the function to recognize and rename the song
    shazam = Shazam()
    modify = True  # Apply modifications in the test

    result = await recognize_and_rename_song(
        test_file_path, filename, shazam, modify
    )

    # Verify that the file was correctly renamed to the expected name
    assert os.path.exists(
        expected_new_file_path
    ), f"Test Failed for .{ext.upper()}: The file was not correctly renamed."

    # Cleanup: rename the file back to its original name for subsequent tests
    os.rename(expected_new_file_path, test_file_path)
