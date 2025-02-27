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
        self.data = []  # List of dicts with result info and an "apply" flag.

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

        # Progress bar frame: includes the bar and an info label.
        progress_frame = ttk.Frame(root, padding="10")
        progress_frame.pack(fill=tk.X)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.progress_info = ttk.Label(progress_frame,
                                       text="0/0, Remaining: 0 sec")
        self.progress_info.pack(side=tk.LEFT)

        # Middle Frame: Treeview for displaying MP3 file info.
        tree_frame = ttk.Frame(root, padding="10")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame,
                                 columns=("apply", "old", "new"),
                                 show="headings")
        self.tree.heading("apply", text="Apply")
        self.tree.heading("old",
                          text="Old Name",
                          command=lambda: self.sort_by("old"))
        self.tree.heading("new",
                          text="New Name",
                          command=lambda: self.sort_by("new"))
        self.tree.column("apply", width=80, anchor="center")
        self.tree.column("old", width=300, anchor="w")
        self.tree.column("new", width=300, anchor="w")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Allow user to adjust column widths by adding a scrollbar.
        scrollbar = ttk.Scrollbar(tree_frame,
                                  orient="vertical",
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind click event to toggle the "Apply" flag.
        self.tree.bind("<Button-1>", self.on_tree_click)

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
            self.start_recognition(directory)

    def start_recognition(self, directory):
        # Clear previous data and tree entries.
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.data.clear()
        results_list.clear()
        self.progress.config(value=0)
        self.progress_info.config(text="0/0, Remaining: 0 sec")

        # Run recognition in a separate thread.
        thread = threading.Thread(target=self.run_recognition,
                                  args=(directory, ))
        thread.start()

    def run_recognition(self, directory):
        asyncio.run(self.process_files(directory))
        self.root.after(0, self.populate_tree)

    async def process_files(self, directory):
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
                # Add an "apply" flag defaulting to True.
                result["apply"] = True
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

    def populate_tree(self):
        # Populate the Treeview with data from results_list.
        for result in results_list:
            # Store each row's data.
            self.data.append(result)
            self.tree.insert(
                "",
                "end",
                values=("Yes", os.path.basename(result.get("file_path", "")),
                        os.path.basename(result.get("new_file_path", ""))))
        if not self.data:
            messagebox.showinfo("Info", "No MP3 files were processed.")

    def on_tree_click(self, event):
        # Identify column and row clicked.
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        # If "Apply" column (first column) is clicked, toggle the flag.
        if column == "#1":
            index = self.tree.index(row_id)
            # Toggle the flag.
            self.data[index]["apply"] = not self.data[index].get("apply", True)
            new_value = "Yes" if self.data[index]["apply"] else "No"
            self.tree.set(row_id, "apply", new_value)

    def sort_by(self, key):
        # key is "old" or "new"
        if key == "old":
            self.data.sort(
                key=lambda x: os.path.basename(x.get("file_path", "")).lower())
        elif key == "new":
            self.data.sort(key=lambda x: os.path.basename(
                x.get("new_file_path", "")).lower())
        # Clear and repopulate tree.
        for item in self.tree.get_children():
            self.tree.delete(item)
        for result in self.data:
            self.tree.insert(
                "",
                "end",
                values=("Yes" if result.get("apply", True) else "No",
                        os.path.basename(result.get("file_path", "")),
                        os.path.basename(result.get("new_file_path", ""))))

    def apply_changes(self):
        errors = []
        for result in self.data:
            if result.get("apply", True):
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


if __name__ == "__main__":
    launch_gui()
