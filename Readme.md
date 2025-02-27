# MP3 File Recognizer and Renamer

This Python project automatically recognizes MP3 files using Shazam, renames them according to the recognized song title and artist, and updates their MP3 tags and cover art. In addition to the command‑line interface, a user‑friendly GUI is now available. You can download a zip file containing the executable from the following address: [https://github.com/davidAlgis/mp3ShazamAutoTag/releases](https://github.com/davidAlgis/mp3ShazamAutoTag/releases).

> ![Example UI](example-ui.jpeg)

## Usage

### Graphical User Interface (GUI)

A user‑friendly executable is now available as a zip file (download link above). This GUI allows you to:
- Select the input directory via a browse button.
- See a progress bar with file count and estimated remaining time.
- View a table of MP3 files with options to check/uncheck rows and directly edit the new file names.
- Apply the changes by clicking the "Apply" button.

Simply unzip the file and run the executable.


## Manual Installation

Before running the script, create a clean environment and install the required Python libraries. For example:

```bash
pip install .
```

**Note:**  
- Ensure you have Python 3.6 or newer installed on your system.  
- There might be some issues with Python 3.11 and 3.12 (see [Issue #1](https://github.com/davidAlgis/mp3ShazamAutoTag/issues/1)).  
- macOS users may need to install *shazamio* manually (see [Issue #5](https://github.com/davidAlgis/mp3ShazamAutoTag/issues/5)).


## Command‑Line Interface

Alternatively, you can run the script from the command line. First, clone this repository (or download the files), install the required libraries as mentioned above, and then run:

```bash
python main.py [options]
```

### Options

- `-di`, `--directory` `<directory>`  
  Specify the directory where MP3 files are located for processing. If not specified, the script uses its current directory.

- `-t`, `--test`  
  Execute a test function to verify the script's functionality. It looks for a file named `fileToTest.mp3` in a `test` folder and checks the renaming process.

- `-m`, `--modify` `<True/False>`  
  Indicate whether the script should apply modifications to the MP3 tags and filenames. Defaults to `True`.

- `-de`, `--delay` `<delay>`  
  Specify a delay (in seconds) to wait before retrying the Shazam API call if the initial attempt fails. Defaults to 10 seconds.

- `-n`, `--nbrRetry` `<number>`  
  Specify the number of retries for the Shazam API call if it fails. Defaults to 10 tries.

- `-tr`, `--trace`  
  Enable tracing to print messages during the recognition and renaming process. Useful for debugging or monitoring script progress.

- `-h`, `--help`  
  Display help information showing all command-line options.

## Building the Executable

This project now includes a `setup.py` to build a standalone executable using **cx_Freeze**. To build the executable:

1. Install cx_Freeze if not already installed:

   ```bash
   pip install cx_Freeze
   ```

2. Run the build command:

   ```bash
   python setup.py build
   ```

This will create a **build** folder with the executable and required files.

Enjoy using the MP3 File Recognizer and Renamer!
