import os
import asyncio
import threading
import time
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
        self.row_widgets = []  # Each element: (checkbox_var, result_dict)

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

        # Progress bar frame to include both the bar and the info label.
        progress_frame = ttk.Frame(root, padding="10")
        progress_frame.pack(fill=tk.X)

        # Progress bar.
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # Progress info label.
        self.progress_info = ttk.Label(progress_frame,
                                       text="0/0, Remaining: 0 sec")
        self.progress_info.pack(side=tk.LEFT)

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
        header_label_apply = ttk.Label(header_frame,
                                       text="Apply",
                                       anchor="center",
                                       relief="ridge")
        header_label_old = ttk.Label(header_frame,
                                     text="Old Name",
                                     anchor="center",
                                     relief="ridge")
        header_label_new = ttk.Label(header_frame,
                                     text="New Name",
                                     anchor="center",
                                     relief="ridge")
        header_label_apply.grid(row=0, column=0, sticky="nsew")
        header_label_old.grid(row=0, column=1, sticky="nsew")
        header_label_new.grid(row=0, column=2, sticky="nsew")
        # Set uniform column widths.
        header_frame.grid_columnconfigure(0, weight=1, uniform="group")
        header_frame.grid_columnconfigure(1, weight=3, uniform="group")
        header_frame.grid_columnconfigure(2, weight=3, uniform="group")
        # Bind clicks for sorting.
        header_label_old.bind("<Button-1>", lambda e: self.sort_by_old_name())
        header_label_new.bind("<Button-1>", lambda e: self.sort_by_new_name())

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

        self.start_time = None  # To track when processing started.
        self.total_files = 0

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

        # Reset and start progress bar.
        self.progress.config(value=0)
        self.progress_info.config(text="0/0, Remaining: 0 sec")

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
        run recognition on each file (with modify=False), and update the progress bar and info.
        """
        mp3_files = []
        for root_dir, dirs, files in os.walk(directory):
            if "test" in os.path.basename(root_dir).lower():
                continue
            for file in files:
                if file.lower().endswith(".mp3"):
                    full_path = os.path.join(root_dir, file)
                    mp3_files.append((file, full_path))

        self.total_files = len(mp3_files)
        if self.total_files == 0:
            self.root.after(
                0, lambda: messagebox.showinfo(
                    "Info", f"No MP3 files found in {directory}"))
            return

        self.root.after(0,
                        lambda: self.progress.config(maximum=self.total_files))
        self.start_time = time.time()

        shazam = Shazam()
        count = 0
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
            count += 1
            elapsed = time.time() - self.start_time
            avg_time = elapsed / count if count else 0
            remaining = int(avg_time * (self.total_files - count))
            self.root.after(
                0, lambda c=count, r=remaining: self.update_progress(c, r))

    def update_progress(self, count, remaining):
        self.progress.config(value=count)
        self.progress_info.config(
            text=f"{count}/{self.total_files}, Remaining: {remaining} sec")

    def populate_results(self):
        # Populate rows from the global results_list.
        for result in results_list:
            self.add_row(result)
        if not self.row_widgets:
            messagebox.showinfo("Info", "No MP3 files were processed.")

    def add_row(self, result):
        row_frame = ttk.Frame(self.rows_container,
                              relief="groove",
                              borderwidth=1,
                              padding=2)
        row_frame.pack(fill=tk.X, padx=2, pady=2)
        # Configure grid columns uniformly for this row.
        row_frame.grid_columnconfigure(0, weight=1, uniform="group")
        row_frame.grid_columnconfigure(1, weight=3, uniform="group")
        row_frame.grid_columnconfigure(2, weight=3, uniform="group")

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

    def refresh_rows(self):
        # Clear current rows.
        for widget in self.rows_container.winfo_children():
            widget.destroy()
        # Rebuild rows in order.
        for var, result in self.row_widgets:
            self.add_row(result)

    def sort_by_old_name(self):
        # Sort rows based on the basename of file_path.
        self.row_widgets.sort(
            key=lambda x: os.path.basename(x[1].get("file_path", "")).lower())
        self.refresh_rows()

    def sort_by_new_name(self):
        # Sort rows based on the basename of new_file_path.
        self.row_widgets.sort(key=lambda x: os.path.basename(x[1].get(
            "new_file_path", "")).lower())
        self.refresh_rows()

    def apply_changes(self):
        errors = []
        for var, result in self.row_widgets:
            if var.get():
                old_path = result.get("file_path")
                new_path = result.get("new_file_path")
                try:
                    if not os.path.exists(old_path):
                        continue
                    base, ext = os.path.splitext(new_path)
                    counter = 1
                    unique_new_path = new_path
                    while os.path.exists(unique_new_path):
                        unique_new_path = f"{base} ({counter}){ext}"
                        counter += 1
                    os.rename(old_path, unique_new_path)
                    base_name = os.path.splitext(
                        os.path.basename(unique_new_path))[0]
                    parts = base_name.split(" - ")
                    album = parts[2] if len(parts) >= 3 else "Unknown Album"
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
