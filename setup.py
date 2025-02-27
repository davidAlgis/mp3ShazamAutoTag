import sys
from cx_Freeze import setup, Executable

# Options for cx_Freeze.
build_exe_options = {
    "packages": [
        "asyncio",
        "auto_tag",  # your package
        "shazamio",  # force inclusion of shazamio
        "eyed3",
        "unidecode",
    ],
    "includes": [
        "shazamio", "shazamio.core", "shazamio.recognize", "shazamio.models",
        "shazamio.utils"
    ],
    "include_files": ["README.md", "LICENSE"],
}

# On Windows, use "Console" for a console application (or "Win32GUI" for a GUI-only app).
base = "Console" if sys.platform == "win32" else None

executables = [Executable("main.py", base=base)]

setup(
    name="mp3ShazamAutoTag",
    version="0.1.0",
    description="Use shazam to rename and fill the tag of a list of mp3 files.",
    options={"build_exe": build_exe_options},
    executables=executables,
)
