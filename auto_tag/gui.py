import os
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from auto_tag.mp3_recognize import (recognize_and_rename_song, update_mp3_tags,
                                    update_mp3_cover_art)
from shazamio import Shazam

# Global list to store recognition results.
# Each item is a dict with keys: file_path, new_file_path, title, author, cover_link.
results_list = []


class MP3RenamerGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("MP3 Auto-Title & Tagger")

        # Top Frame: Directory input and browse button.
        top_frame = ttk.Frame(root, padding="10")
        top_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top_frame, text="Input Directory:").pack(side=tk.LEFT)
        self.dir_var = tk.StringVar()
        self.dir_entry = ttk.Entry(top_frame,
                                   textvariable=self.dir_var,
                                   width=50)
        self.dir_entry.pack(side=tk.LEFT, padx=(5, 0))
        browse_btn = ttk.Button(top_frame,
                                text="Browse",
                                command=self.browse_directory)
        browse_btn.pack(side=tk.LEFT, padx=5)

        # Progress bar.
        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=10, pady=5)

        # Middle Frame: Scrollable area for MP3 files.
        mid_frame = ttk.Frame(root, padding="10")
        mid_frame.pack(fill=tk.BOTH, expand=True)

        # Create a canvas and a vertical scrollbar for the frame.
        self.canvas = tk.Canvas(mid_frame)
        self.scrollbar = ttk.Scrollbar(mid_frame,
                                       orient="vertical",
                                       command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.
                                                           canvas.bbox("all")))

        self.canvas.create_window((0, 0),
                                  window=self.scrollable_frame,
                                  anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Header row for the table.
        header_frame = ttk.Frame(self.scrollable_frame)
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame,
                  text="Apply",
                  width=6,
                  anchor="center",
                  relief="ridge").grid(row=0, column=0, sticky="nsew")
        ttk.Label(header_frame,
                  text="Old Name",
                  width=30,
                  anchor="center",
                  relief="ridge").grid(row=0, column=1, sticky="nsew")
        ttk.Label(header_frame,
                  text="New Name",
                  width=30,
                  anchor="center",
                  relief="ridge").grid(row=0, column=2, sticky="nsew")

        # Container for file rows.
        self.rows_container = ttk.Frame(self.scrollable_frame)
        self.rows_container.pack(fill=tk.BOTH, expand=True)

        # Bottom Frame: Apply button.
        bottom_frame = ttk.Frame(root, padding="10")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        apply_btn = ttk.Button(bottom_frame,
                               text="Apply",
                               command=self.apply_changes)
        apply_btn.pack()

        # List to store per-row widgets.
        self.row_widgets = [
        ]  # Each element: (checkbox_var, old_name, new_name, result_dict)

    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)
            # Start the recognition process.
            self.start_recognition(directory)

    def start_recognition(self, directory):
        # Clear any previous rows.
        for widget in self.rows_container.winfo_children():
            widget.destroy()
        self.row_widgets.clear()
        results_list.clear()

        # Start progress bar.
        self.progress.start(10)

        # Run the async processing in a separate thread.
        thread = threading.Thread(target=self.run_recognition,
                                  args=(directory, ))
        thread.start()

    def run_recognition(self, directory):
        asyncio.run(self.process_files(directory))
        # When done, update the UI from the main thread.
        self.root.after(0, self.populate_results)

    async def process_files(self, directory):
        """
        Traverse the directory for mp3 files (excluding any folder named 'test'),
        and run recognition on each file (with modify=False).
        """
        mp3_files = []
        # Walk the directory tree.
        for root_dir, dirs, files in os.walk(directory):
            # Skip directories named 'test' (case-insensitive).
            if "test" in os.path.basename(root_dir).lower():
                continue
            for file in files:
                if file.lower().endswith(".mp3"):
                    full_path = os.path.join(root_dir, file)
                    mp3_files.append((file, full_path))

        if not mp3_files:
            self.root.after(
                0, lambda: messagebox.showinfo(
                    "Info", f"No MP3 files found in {directory}"))
            return

        shazam = Shazam()
        # Process files sequentially so we can update the UI after each.
        for file_name, file_path in mp3_files:
            try:
                result = await recognize_and_rename_song(file_path,
                                                         file_name,
                                                         shazam,
                                                         modify=False,
                                                         delay=10,
                                                         nbrRetry=3,
                                                         trace=False)
                results_list.append(result)
            except Exception as e:
                print(f"Error processing {file_name}: {e}")

    def populate_results(self):
        # Stop the progress bar.
        self.progress.stop()

        # For each result, add a row with a checkbox, old name and new name.
        for result in results_list:
            row_frame = ttk.Frame(self.rows_container,
                                  relief="groove",
                                  borderwidth=1,
                                  padding=2)
            row_frame.pack(fill=tk.X, padx=2, pady=2)

            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(row_frame, variable=var)
            chk.grid(row=0, column=0, padx=5, sticky="w")

            old_name = os.path.basename(result.get("file_path", ""))
            new_name = os.path.basename(result.get("new_file_path", ""))
            lbl_old = ttk.Label(row_frame, text=old_name, width=30)
            lbl_old.grid(row=0, column=1, padx=5, sticky="w")
            lbl_new = ttk.Label(row_frame, text=new_name, width=30)
            lbl_new.grid(row=0, column=2, padx=5, sticky="w")

            self.row_widgets.append((var, result))
        if not self.row_widgets:
            messagebox.showinfo("Info", "No MP3 files were processed.")

    def apply_changes(self):
        # For each row that is checked, apply the renaming and update tags and cover art.
        errors = []
        for var, result in self.row_widgets:
            if var.get():
                old_path = result.get("file_path")
                new_path = result.get("new_file_path")
                try:
                    # Skip if the original file doesn't exist.
                    if not os.path.exists(old_path):
                        continue

                    # If a file with new_path already exists, append a counter to make it unique.
                    base, ext = os.path.splitext(new_path)
                    counter = 1
                    unique_new_path = new_path
                    while os.path.exists(unique_new_path):
                        unique_new_path = f"{base} ({counter}){ext}"
                        counter += 1

                    # Rename file using the unique new path.
                    os.rename(old_path, unique_new_path)

                    # Parse new file name to extract album:
                    # Expected format: "Title - Artist - Album.mp3"
                    base_name = os.path.splitext(
                        os.path.basename(unique_new_path))[0]
                    parts = base_name.split(" - ")
                    if len(parts) >= 3:
                        album = parts[2]
                    else:
                        album = "Unknown Album"

                    # Update tags and cover art.
                    update_mp3_tags(unique_new_path,
                                    result.get("title", "Unknown Title"),
                                    result.get("author", "Unknown Artist"),
                                    album)
                    update_mp3_cover_art(unique_new_path,
                                         result.get("cover_link", ""),
                                         trace=False)
                except Exception as e:
                    errors.append(f"Error processing {old_path}: {e}")

        if errors:
            messagebox.showerror("Errors Occurred", "\n".join(errors))
        else:
            messagebox.showinfo("Success", "Changes applied successfully.")


def launch_gui():
    root = tk.Tk()
    app = MP3RenamerGUI(root)
    root.mainloop()
