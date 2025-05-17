import os

import pytest

from auto_tag import audio_recognize
from auto_tag.audio_recognize import recognize_and_rename_file


# -------------------------------------------------
# Dummy Shazam stub that always returns fixed metadata
# matching the structure produced by shazamio so that
# find_deepest_metadata_key() can locate the album name.
# -------------------------------------------------
class DummyShazam:
    async def recognize(self, file_path):
        return {
            "track": {
                "title": "Drive My Car",
                "subtitle": "The Beatles",
                "images": {"coverart": ""},
                "sections": [
                    {"metadata": [{"title": "Album", "text": "Rubber Soul"}]}
                ],
            }
        }


# Extensions we want to test on
test_extensions = ["mp3", "ogg"]


# -------------------------------------------------
# Helper to neuter tag‑writing functions so tests don’t
# depend on valid audio binaries / mutagen behaviour.
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
    """The file should be moved/renamed to Drive My Car.<ext> in the same folder."""
    # Arrange – create dummy audio file
    test_file = tmp_path / f"fileToTest.{ext}"
    test_file.write_bytes(b"dummy audio data")

    expected = tmp_path / f"Drive My Car - The Beatles - Rubber Soul.{ext}"

    # Act
    result = await recognize_and_rename_file(
        file_path=str(test_file),
        shazam=DummyShazam(),
        modify=True,
        delay=0,
        nbr_retry=1,
        trace=False,
        output_dir=str(tmp_path),
        plex_structure=False,
    )

    # Assert
    assert result.get("new_file_path") == str(expected)
    assert expected.exists(), f"File not found at {expected}"


# -------------------------------------------------
# Plex structure test
# -------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("ext", test_extensions)
async def test_recognize_and_rename_file_with_plex(tmp_path, ext):
    """The file should be moved to <artist>/<album>/Drive My Car.<ext>."""
    # Arrange – create dummy audio file
    test_file = tmp_path / f"fileToTest.{ext}"
    test_file.write_bytes(b"dummy audio data")

    artist_dir = tmp_path / "The Beatles"
    album_dir = artist_dir / "Rubber Soul"
    expected = album_dir / f"Drive My Car.{ext}"

    # Act
    result = await recognize_and_rename_file(
        file_path=str(test_file),
        shazam=DummyShazam(),
        modify=True,
        delay=0,
        nbr_retry=1,
        trace=False,
        output_dir=str(tmp_path),
        plex_structure=True,
    )

    # Assert
    assert result.get("new_file_path") == str(expected)
    assert expected.exists(), f"File not found at {expected}"
