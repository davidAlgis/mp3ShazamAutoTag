import os
import shutil
from pathlib import Path

import pytest

from auto_tag import audio_recognize
from auto_tag.audio_recognize import recognize_and_rename_file


# -------------------------------------------------
# Dummy Shazam stub that returns metadata based on extension
# -------------------------------------------------
class DummyShazam:
    async def recognize(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".mp3":
            return {
                "track": {
                    "title": "Drive My Car",
                    "subtitle": "The Beatles",
                    "images": {"coverart": ""},
                    "sections": [
                        {
                            "metadata": [
                                {"title": "Album", "text": "Rubber Soul"}
                            ]
                        }
                    ],
                }
            }
        elif ext == ".ogg":
            return {
                "track": {
                    "title": "Bring Me To Life",
                    "subtitle": "Evanescence",
                    "images": {"coverart": ""},
                    "sections": [
                        {"metadata": [{"title": "Album", "text": "Fallen"}]}
                    ],
                }
            }
        return {}


# Extensions to test
test_extensions = ["mp3", "ogg"]


# -------------------------------------------------
# Disable actual tag-writing so tests don’t depend on real audio
# -------------------------------------------------
@pytest.fixture(autouse=True)
def patch_tag_functions(monkeypatch):
    monkeypatch.setattr(
        audio_recognize, "update_mp3_tags", lambda *a, **k: None
    )
    monkeypatch.setattr(
        audio_recognize, "update_mp3_cover_art", lambda *a, **k: None
    )
    monkeypatch.setattr(
        audio_recognize, "update_ogg_tags", lambda *a, **k: None
    )


# -------------------------------------------------
# Flat structure test
# -------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_recognize_and_rename_file_flat(tmp_path, ext):
    """
    The file should be renamed to:
      - Drive My Car - The Beatles - Rubber Soul.mp3
      - Bring Me To Life - Evanescence - Fallen.ogg
    """
    src = Path(__file__).parent / f"fileToTest.{ext}"
    dest = tmp_path / f"fileToTest.{ext}"
    shutil.copy2(src, dest)

    expected_name = (
        "Drive My Car - The Beatles - Rubber Soul.mp3"
        if ext == "mp3"
        else "Bring Me To Life - Evanescence - Fallen.ogg"
    )
    expected = tmp_path / expected_name

    result = await recognize_and_rename_file(
        file_path=str(dest),
        shazam=DummyShazam(),
        modify=True,
        delay=0,
        nbr_retry=1,
        trace=False,
        output_dir=str(tmp_path),
        plex_structure=False,
    )

    assert result.get("new_file_path") == str(expected)
    assert expected.exists(), f"File not found at {expected}"


# -------------------------------------------------
# Plex structure test
# -------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_recognize_and_rename_file_with_plex(tmp_path, ext):
    """
    The file should be placed under:
      <artist>/<album>/Drive My Car.mp3
      <artist>/<album>/Bring Me To Life.ogg
    """
    src = Path(__file__).parent / f"fileToTest.{ext}"
    dest = tmp_path / f"fileToTest.{ext}"
    shutil.copy2(src, dest)

    if ext == "mp3":
        artist, album, name = "The Beatles", "Rubber Soul", "Drive My Car.mp3"
    else:
        artist, album, name = "Evanescence", "Fallen", "Bring Me To Life.ogg"
    expected = tmp_path / artist / album / name

    result = await recognize_and_rename_file(
        file_path=str(dest),
        shazam=DummyShazam(),
        modify=True,
        delay=0,
        nbr_retry=1,
        trace=False,
        output_dir=str(tmp_path),
        plex_structure=True,
    )

    assert result.get("new_file_path") == str(expected)
    assert expected.exists(), f"File not found at {expected}"


# -------------------------------------------------
# Copy-to directory, flat structure
# -------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_copy_to_directory_flat(tmp_path, ext):
    """
    The file should be copied (not moved) to <copy_to> with flat naming,
    and the original should still exist.
    """
    src = Path(__file__).parent / f"fileToTest.{ext}"
    dest = tmp_path / f"fileToTest.{ext}"
    shutil.copy2(src, dest)

    copy_to = tmp_path / "copies"
    expected_name = (
        "Drive My Car - The Beatles - Rubber Soul.mp3"
        if ext == "mp3"
        else "Bring Me To Life - Evanescence - Fallen.ogg"
    )
    expected = copy_to / expected_name

    result = await recognize_and_rename_file(
        file_path=str(dest),
        shazam=DummyShazam(),
        modify=True,
        delay=0,
        nbr_retry=1,
        trace=False,
        output_dir=None,
        plex_structure=False,
        copy_to=str(copy_to),
    )

    assert result.get("new_file_path") == str(expected)
    assert expected.exists(), f"Copied file not found at {expected}"
    assert dest.exists(), "Original file should still exist"


# -------------------------------------------------
# Copy-to directory, plex structure
# -------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_copy_to_directory_with_plex(tmp_path, ext):
    """
    The file should be copied to <copy_to>/<artist>/<album>/Title.ext,
    and the original should still exist.
    """
    src = Path(__file__).parent / f"fileToTest.{ext}"
    dest = tmp_path / f"fileToTest.{ext}"
    shutil.copy2(src, dest)

    copy_to = tmp_path / "plex_copies"
    if ext == "mp3":
        artist, album, name = "The Beatles", "Rubber Soul", "Drive My Car.mp3"
    else:
        artist, album, name = "Evanescence", "Fallen", "Bring Me To Life.ogg"
    expected = copy_to / artist / album / name

    result = await recognize_and_rename_file(
        file_path=str(dest),
        shazam=DummyShazam(),
        modify=True,
        delay=0,
        nbr_retry=1,
        trace=False,
        output_dir=None,
        plex_structure=True,
        copy_to=str(copy_to),
    )

    assert result.get("new_file_path") == str(expected)
    assert expected.exists(), f"Copied file not found at {expected}"
    assert dest.exists(), "Original file should still exist"