import os
import sys
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


def get_base_directory():
    """
    Determines the base directory for the application.
    - When frozen by PyInstaller, sys._MEIPASS is used.
    - Otherwise, the directory of the current file is used.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller sets sys._MEIPASS to the temp folder containing bundled files.
        return sys._MEIPASS
    else:
        current_directory = os.path.abspath(os.path.dirname(__file__))
        return os.path.abspath(os.path.join(current_directory, os.pardir))


class MP3RenamerGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("MP3 Shazam Auto Tag")
        self.data = []  # List of dicts with result info and an "apply" flag.
        self.editing_entry = None  # Reference to the current editing Entry widget.

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

        # Set up a custom style for the Treeview to add padding and increase row height.
        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=30, padding=5)
        style.configure("Custom.Treeview.Heading", padding=5)

        # Middle Frame: Treeview for displaying MP3 file info.
        tree_frame = ttk.Frame(root, padding="10")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame,
                                 columns=("apply", "old", "new"),
                                 show="headings",
                                 style="Custom.Treeview")
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

        # Bind events:
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Return>", self.on_enter)
        # Bind double-click for editing new name cells.
        self.tree.bind("<Double-1>", self.on_double_click)

        # Bottom Frame: Apply and Check/Uncheck buttons.
        bottom_frame = ttk.Frame(root, padding="10")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        apply_btn = ttk.Button(bottom_frame,
                               text="Apply",
                               command=self.apply_changes)
        apply_btn.pack(side=tk.RIGHT, padx=(5, 0))
        uncheck_all_btn = ttk.Button(bottom_frame,
                                     text="Uncheck All",
                                     command=self.uncheck_all)
        uncheck_all_btn.pack(side=tk.RIGHT, padx=5)
        check_all_btn = ttk.Button(bottom_frame,
                                   text="Check All",
                                   command=self.check_all)
        check_all_btn.pack(side=tk.RIGHT, padx=5)

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
        for result in results_list:
            self.data.append(result)
            self.tree.insert(
                "",
                "end",
                values=("Yes", os.path.basename(result.get("file_path", "")),
                        os.path.basename(result.get("new_file_path", ""))))
        if not self.data:
            messagebox.showinfo("Info", "No MP3 files were processed.")

    def on_tree_click(self, event):
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
            self.data[index]["apply"] = not self.data[index].get("apply", True)
            new_value = "Yes" if self.data[index]["apply"] else "No"
            self.tree.set(row_id, "apply", new_value)

    def on_enter(self, event):
        # Toggle the "Apply" flag for the focused row when Enter is pressed.
        row_id = self.tree.focus()
        if not row_id:
            return
        index = self.tree.index(row_id)
        self.data[index]["apply"] = not self.data[index].get("apply", True)
        new_value = "Yes" if self.data[index]["apply"] else "No"
        self.tree.set(row_id, "apply", new_value)

    def on_double_click(self, event):
        # Determine which cell was double-clicked.
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        # We only allow editing on the "New Name" column (third column, i.e. "#3").
        if column != "#3":
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        x, y, width, height = self.tree.bbox(row_id, column)
        # Get the current text.
        current_text = self.tree.set(row_id, "new")
        # Create an Entry widget over the cell.
        self.editing_entry = tk.Entry(self.tree)
        self.editing_entry.place(x=x, y=y, width=width, height=height)
        self.editing_entry.insert(0, current_text)
        self.editing_entry.focus()
        # Bind Return key and focus out to finish editing.
        self.editing_entry.bind("<Return>",
                                lambda e: self.finish_editing(row_id))
        self.editing_entry.bind("<FocusOut>",
                                lambda e: self.finish_editing(row_id))

    def finish_editing(self, row_id):
        if self.editing_entry:
            new_value = self.editing_entry.get()
            self.tree.set(row_id, "new", new_value)
            # Update the underlying data. Use the row index.
            index = self.tree.index(row_id)
            # Here we also update the "new_file_path" based on the new value.
            # For example, we assume the new value should become the basename of the new file path.
            old_new_path = self.data[index].get("new_file_path", "")
            dir_path = os.path.dirname(old_new_path) if old_new_path else ""
            if dir_path:
                self.data[index]["new_file_path"] = os.path.join(
                    dir_path, new_value)
            else:
                self.data[index]["new_file_path"] = new_value
            self.editing_entry.destroy()
            self.editing_entry = None

    def sort_by(self, key):
        if key == "old":
            self.data.sort(
                key=lambda x: os.path.basename(x.get("file_path", "")).lower())
        elif key == "new":
            self.data.sort(key=lambda x: os.path.basename(
                x.get("new_file_path", "")).lower())
        for item in self.tree.get_children():
            self.tree.delete(item)
        for result in self.data:
            self.tree.insert(
                "",
                "end",
                values=("Yes" if result.get("apply", True) else "No",
                        os.path.basename(result.get("file_path", "")),
                        os.path.basename(result.get("new_file_path", ""))))

    def check_all(self):
        for idx, result in enumerate(self.data):
            result["apply"] = True
            item_id = self.tree.get_children()[idx]
            self.tree.set(item_id, "apply", "Yes")

    def uncheck_all(self):
        for idx, result in enumerate(self.data):
            result["apply"] = False
            item_id = self.tree.get_children()[idx]
            self.tree.set(item_id, "apply", "No")

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
    # Use get_base_directory to determine the path for the icon
    base_dir = get_base_directory()
    icon_path = os.path.join(base_dir, "assets", "auto_tag.ico")
    try:
        root.iconbitmap(icon_path)
    except Exception as e:
        print("Warning: Unable to load icon.", e)
    app = MP3RenamerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
