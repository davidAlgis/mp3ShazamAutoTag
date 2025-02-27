import os
import pytest
from auto_tag.mp3_recognize import recognize_and_rename_song
from shazamio import Shazam


@pytest.mark.asyncio
async def test_recognize_and_rename_song():
    # Define the test folder and file paths relative to the location of this test script
    test_folder = os.path.dirname(os.path.realpath(__file__))
    test_file_path = os.path.join(test_folder, "fileToTest.mp3")
    expected_new_name = "Drive My Car - The Beatles - Rubber Soul.mp3"
    expected_new_file_path = os.path.join(test_folder, expected_new_name)

    # If the expected new file exists, rename it to the test file name
    if os.path.exists(expected_new_file_path):
        os.rename(expected_new_file_path, test_file_path)

    # Check if the test file exists
    assert os.path.exists(
        test_file_path
    ), "Error: The test file does not exist, so the test could not be launched."

    # Apply the recognize_and_rename_song function on this file
    shazam = Shazam()
    modify = True  # Assuming you want to apply modifications in the test

    # Call the function to recognize and rename the song
    result = await recognize_and_rename_song(test_file_path, "fileToTest.mp3",
                                             shazam, modify)

    # Check if the file was correctly renamed
    assert os.path.exists(expected_new_file_path
                          ), "Test Failed: The file was not correctly renamed."

    # Rename the file back to its original name for other tests
    os.rename(expected_new_file_path, test_file_path)
