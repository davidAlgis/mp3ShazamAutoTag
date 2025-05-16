# auto_tag/main.py

import argparse
import asyncio
import os

from auto_tag.audio_recognize import find_and_recognize_audio_files
from auto_tag.gui import launch_gui


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    if v.lower() in ("no", "false", "f", "n", "0"):
        return False
    raise argparse.ArgumentTypeError("Boolean value expected.")


async def main():
    parser = argparse.ArgumentParser(
        description="Process audio files with Shazam recognition and optional renaming and tagging."
    )
    parser.add_argument(
        "-di",
        "--directory",
        help="Directory to process (default: current folder)",
        default=os.getcwd(),
    )
    parser.add_argument(
        "-m",
        "--modify",
        type=str2bool,
        nargs="?",
        const=True,
        default=True,
        help="Apply modifications to tags and filenames (default: true)",
    )
    parser.add_argument(
        "-de",
        "--delay",
        type=int,
        default=10,
        help="Delay in seconds between retries if Shazam API call fails (default: 10)",
    )
    parser.add_argument(
        "-n",
        "--nbrRetry",
        type=int,
        default=3,
        help="Number of retries for Shazam API call if it fails (default: 3)",
    )
    parser.add_argument(
        "-tr",
        "--trace",
        type=str2bool,
        nargs="?",
        const=True,
        default=False,
        help="Enable tracing output (default: false)",
    )
    parser.add_argument(
        "-g",
        "--gui",
        type=str2bool,
        nargs="?",
        const=True,
        default=False,
        help="Launch the GUI (default: false)",
    )
    parser.add_argument(
        "-e",
        "--extensions",
        type=str,
        default="mp3,ogg",
        help="Comma-separated list of extensions to process (default: mp3,ogg)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Base output directory for moved files (default: same folder)",
    )
    parser.add_argument(
        "--plex",
        action="store_true",
        help="Organize output into Plex structure: Artist/Album/Title.ext",
    )

    args = parser.parse_args()

    if args.gui:
        launch_gui()
    else:
        exts = [ext.strip().lower() for ext in args.extensions.split(",")]
        await find_and_recognize_audio_files(
            folder_path=args.directory,
            modify=args.modify,
            delay=args.delay,
            nbr_retry=args.nbrRetry,
            trace=args.trace,
            extensions=exts,
            output_dir=args.output,
            plex_structure=args.plex,
        )


if __name__ == "__main__":
    asyncio.run(main())
