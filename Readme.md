# MP3 File Recognizer and Renamer

This Python script automatically recognizes MP3 files using Shazam, renames them according to the recognized song title and artist, and updates their MP3 tags and cover art.

## Installation

Before running the script, you need to install the required Python libraries. You can install them using the provided `requirements.txt` file.

```
pip install -r requirements.txt
```

## Usage

Ensure you have Python 3.6 or newer installed on your system (there might be some problem with 3.11 and 3.12 (cf. issue https://github.com/davidAlgis/mp3ShazamAutoTag/issues/1).
Clone this repository or download the script and requirements.txt file.
Install the required libraries as mentioned above.
To use the script, run it from the command line with the desired options:

```
python main.py  [options]
```

## Options

- `-d`, `--directory` <directory>: Specify the directory where MP3 files are located for processing. If not specified, the script uses its current directory.
- `-t`, `--test`: Execute a test function to verify the script's functionality. It looks for a file named "fileToTest.mp3" in a test folder and checks the renaming process.
- `-m`, `--modify` <True/False>: Indicate whether the script should apply modifications to the MP3 tags and filenames. Defaults to True.
- `-de`, `--delay` <delay>: Specify a delay (in seconds) to wait before retrying the Shazam API call if the initial attempt fails. Defaults to 10 seconds.
- `-h`, `--help`: Display help information showing all command-line options.
