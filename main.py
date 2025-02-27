import os
import argparse
import asyncio
from auto_tag.mp3_recognize import find_and_recognize_mp3_files


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


async def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(
        description=
        "Process MP3 files with Shazam recognition and optional renaming and tagging."
    )
    parser.add_argument(
        "-di",
        "--directory",
        help=
        "Specify the directory to process MP3 files. (default is current folder)",
        default=os.path.dirname(os.path.realpath(__file__)),
    )
    parser.add_argument(
        "-m",
        "--modify",
        type=str2bool,
        nargs="?",
        const=True,
        default=True,
        help=
        "Indicate if modifications to tag and file name should be applied. (default is true)",
    )
    parser.add_argument(
        "-de",
        "--delay",
        type=int,
        default=10,
        help=
        "Specify a delay in seconds between retries if the Shazam API call fails. (default 10 seconds, reduce it to improve performances)",
    )
    parser.add_argument(
        "-n",
        "--nbrRetry",
        type=int,
        default=10,
        help=
        "Specify the number of retries for Shazam API call if it fails. (default 10 try, reduce it to improve performances)",
    )
    parser.add_argument(
        "-tr",
        "--trace",
        type=str2bool,
        nargs="?",
        const=True,
        default=False,
        help=
        "Enable tracing to print messages during the recognition and renaming process.",
    )

    args = parser.parse_args()

    # Handle the directory argument
    folder_path = (args.directory if args.directory else os.path.dirname(
        os.path.realpath(__file__)))

    await find_and_recognize_mp3_files(args.directory, args.modify, args.delay,
                                       args.nbrRetry, args.trace)


if __name__ == "__main__":
    asyncio.run(main())
