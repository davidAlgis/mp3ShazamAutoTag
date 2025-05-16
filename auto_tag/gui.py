# auto_tag/gui.py
import asyncio
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from shazamio import Shazam

from auto_tag.audio_recognize import (recognize_and_rename_file,
                                      update_mp3_cover_art, update_mp3_tags)

# ──────────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────────
RESULTS: list[dict] = []  # each item gets: file_path • new_file_path • apply


def get_base_directory() -> str:
    """
    When frozen by PyInstaller, use the bundled temp dir.
    Otherwise, use the project root.
    """
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, os.pardir))


# ──────────────────────────────────────────────────────────────────────────────
# GUI class
# ──────────────────────────────────────────────────────────────────────────────
class MP3RenamerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MP3 Shazam Auto Tag")

        self.data: list[dict] = []  # rows backing the Treeview
        self.editing_entry: tk.Entry | None = None
        self.start_time: float | None = None
        self.total_files: int = 0

        # ────────── top-bar: directory picker + Plex toggle ──────────
        top = ttk.Frame(root, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Input Directory:").pack(side=tk.LEFT)
        self.dir_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.dir_var, width=50).pack(
            side=tk.LEFT, padx=(5, 0)
        )
        ttk.Button(top, text="Browse", command=self.browse_directory).pack(
            side=tk.LEFT, padx=5
        )

        self.plex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top, text="Plex Structure", variable=self.plex_var
        ).pack(side=tk.LEFT, padx=5)

        # ────────── progress bar ──────────
        pframe = ttk.Frame(root, padding=10)
        pframe.pack(fill=tk.X)
        self.progress = ttk.Progressbar(pframe, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.progress_info = ttk.Label(pframe, text="0/0, Remaining: 0 sec")
        self.progress_info.pack(side=tk.LEFT)

        # ────────── Treeview for results ──────────
        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=30, padding=5)
        style.configure("Custom.Treeview.Heading", padding=5)

        tree_frame = ttk.Frame(root, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("apply", "old", "new"),
            show="headings",
            style="Custom.Treeview",
        )
        self.tree.heading("apply", text="Apply")
        self.tree.heading(
            "old", text="Old Name", command=lambda: self.sort_by("old")
        )
        self.tree.heading(
            "new", text="New Name", command=lambda: self.sort_by("new")
        )
        self.tree.column("apply", width=80, anchor="center")
        self.tree.column("old", width=300, anchor="w")
        self.tree.column("new", width=300, anchor="w")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.tag_configure("Yes", foreground="#5a7849")
        self.tree.tag_configure("No", foreground="#DB504A")

        vscroll = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,  # scrollbar drives the Treeview
        )
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(
            yscrollcommand=vscroll.set
        )  # Treeview updates the thumb

        # events
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Return>", self.on_enter)
        self.tree.bind("<Double-1>", self.on_double_click)

        # ────────── bottom buttons ──────────
        bottom = ttk.Frame(root, padding=10)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(bottom, text="Apply", command=self.apply_changes).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(bottom, text="Uncheck All", command=self.uncheck_all).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(bottom, text="Check All", command=self.check_all).pack(
            side=tk.RIGHT, padx=5
        )

    # ─────────────────────────── directory picker ────────────────────────────
    def browse_directory(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)
            self.start_recognition(directory)

    # ─────────────────────────── workers & threads ───────────────────────────
    def start_recognition(self, directory: str) -> None:
        # reset state
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.data.clear()
        RESULTS.clear()
        self.progress.config(value=0)
        self.progress_info.config(text="0/0, Remaining: 0 sec")

        threading.Thread(
            target=self.run_recognition,
            args=(directory, self.plex_var.get()),
            daemon=True,
        ).start()

    def run_recognition(self, directory: str, plex: bool) -> None:
        asyncio.run(self.process_files(directory, plex))
        self.root.after(0, self.populate_tree)

    async def process_files(self, directory: str, plex: bool) -> None:
        # gather .mp3 + .ogg
        audio_files: list[tuple[str, str]] = []
        for root_dir, _, files in os.walk(directory):
            if "test" in os.path.basename(root_dir).lower():
                continue
            for file in files:
                if file.lower().endswith((".mp3", ".ogg")):
                    audio_files.append((file, os.path.join(root_dir, file)))

        self.total_files = len(audio_files)
        if not audio_files:
            self.root.after(
                0, lambda: messagebox.showinfo("Info", "No audio files found.")
            )
            return

        self.root.after(
            0, lambda: self.progress.config(maximum=self.total_files)
        )
        self.start_time = time.time()
        shazam = Shazam()

        count = 0
        for _, path in audio_files:
            try:
                result = await recognize_and_rename_file(
                    file_path=path,
                    shazam=shazam,
                    modify=False,
                    delay=10,
                    nbr_retry=3,
                    trace=False,
                    output_dir=None,
                    plex_structure=plex,
                )
                # if Shazam failed, give the user a hint in the table
                if "error" in result:
                    result["new_file_path"] = result[
                        "error"
                    ]  # show the message
                    result["apply"] = False
                else:
                    result["apply"] = True
            except Exception as exc:
                result = {
                    "file_path": path,
                    "new_file_path": f"Error: {exc}",
                    "apply": False,
                }
            RESULTS.append(result)

            count += 1
            elapsed = time.time() - self.start_time
            remaining = int(elapsed / count * (self.total_files - count))
            self.root.after(
                0, lambda c=count, r=remaining: self.update_progress(c, r)
            )

    # ───────────────────────── Treeview helpers ────────────────────────────
    def update_progress(self, done: int, remaining: int) -> None:
        self.progress.config(value=done)
        self.progress_info.config(
            text=f"{done}/{self.total_files}, Remaining: {remaining} sec"
        )

    def populate_tree(self) -> None:
        for res in RESULTS:
            self.data.append(res)
            tag = "Yes" if res.get("apply") else "No"
            self.tree.insert(
                "",
                "end",
                values=(
                    tag,
                    os.path.basename(res.get("file_path", "")),
                    os.path.basename(res.get("new_file_path", "")),
                ),
                tags=(tag,),
            )
        if not self.data:
            messagebox.showinfo("Info", "No files were processed.")

    # clicks / key events ----------------------------------------------------
    def on_tree_click(self, event) -> None:
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        col, row_id = self.tree.identify_column(
            event.x
        ), self.tree.identify_row(event.y)
        if not row_id or col != "#1":
            return
        idx = self.tree.index(row_id)
        self.toggle_apply(idx, row_id)

    def on_enter(self, event) -> None:
        row_id = self.tree.focus()
        if not row_id:
            return
        idx = self.tree.index(row_id)
        self.toggle_apply(idx, row_id)

    def toggle_apply(self, idx: int, row_id) -> None:
        self.data[idx]["apply"] = not self.data[idx].get("apply", True)
        tag = "Yes" if self.data[idx]["apply"] else "No"
        self.tree.set(row_id, "apply", tag)
        self.tree.item(row_id, tags=(tag,))

    def on_double_click(self, event) -> None:
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        col, row_id = self.tree.identify_column(
            event.x
        ), self.tree.identify_row(event.y)
        if not row_id:
            return

        idx = self.tree.index(row_id)
        if col in ("#1", "#2"):
            self.toggle_apply(idx, row_id)
        elif col == "#3":  # edit new name
            x, y, w, h = self.tree.bbox(row_id, col)
            current = self.tree.set(row_id, "new")
            self.editing_entry = tk.Entry(self.tree)
            self.editing_entry.place(x=x, y=y, width=w, height=h)
            self.editing_entry.insert(0, current)
            self.editing_entry.focus()
            self.editing_entry.bind(
                "<Return>", lambda _: self.finish_editing(row_id)
            )
            self.editing_entry.bind(
                "<FocusOut>", lambda _: self.finish_editing(row_id)
            )

    def finish_editing(self, row_id) -> None:
        if not self.editing_entry:
            return
        new_val = self.editing_entry.get()
        self.tree.set(row_id, "new", new_val)
        idx = self.tree.index(row_id)
        old_new = self.data[idx].get("new_file_path", "")
        dirpath = os.path.dirname(old_new) if old_new else ""
        self.data[idx]["new_file_path"] = (
            os.path.join(dirpath, new_val) if dirpath else new_val
        )
        self.editing_entry.destroy()
        self.editing_entry = None

    # sorting ----------------------------------------------------------------
    def sort_by(self, key: str) -> None:
        if key == "old":
            self.data.sort(
                key=lambda d: os.path.basename(d.get("file_path", "")).lower()
            )
        else:
            self.data.sort(
                key=lambda d: os.path.basename(
                    d.get("new_file_path", "")
                ).lower()
            )
        for item in self.tree.get_children():
            self.tree.delete(item)
        for res in self.data:
            tag = "Yes" if res.get("apply") else "No"
            self.tree.insert(
                "",
                "end",
                values=(
                    tag,
                    os.path.basename(res.get("file_path", "")),
                    os.path.basename(res.get("new_file_path", "")),
                ),
                tags=(tag,),
            )

    # bulk check/uncheck -----------------------------------------------------
    def check_all(self) -> None:
        for idx, res in enumerate(self.data):
            res["apply"] = True
            iid = self.tree.get_children()[idx]
            self.tree.set(iid, "apply", "Yes")
            self.tree.item(iid, tags=("Yes",))

    def uncheck_all(self) -> None:
        for idx, res in enumerate(self.data):
            res["apply"] = False
            iid = self.tree.get_children()[idx]
            self.tree.set(iid, "apply", "No")
            self.tree.item(iid, tags=("No",))

    # ------------------------------------------------------------------------
    # apply file operations
    # ------------------------------------------------------------------------
    def apply_changes(self):
        errors: list[str] = []

        for res in self.data:
            # Skip rows that are unchecked OR have no valid destination
            new_path = res.get("new_file_path")
            if (
                not res.get("apply")
                or not new_path
                or new_path.startswith("Tag error")
            ):
                continue

            old_path = res.get("file_path")
            if not old_path or not os.path.exists(old_path):
                continue

            try:
                # be sure the target folder exists (important in Plex mode)
                os.makedirs(os.path.dirname(new_path), exist_ok=True)

                # avoid clobbering a file that already exists
                base, ext = os.path.splitext(new_path)
                unique = new_path
                counter = 1
                while os.path.exists(unique):
                    unique = f"{base} ({counter}){ext}"
                    counter += 1

                os.rename(old_path, unique)

                # write tags + cover **only if it is an MP3/OGG we just moved**
                title = os.path.splitext(os.path.basename(unique))[0]
                if ext.lower() == ".mp3":
                    update_mp3_tags(
                        unique, title, "Unknown Artist", "Unknown Album"
                    )
                    update_mp3_cover_art(
                        unique, res.get("cover_link", ""), trace=False
                    )
                elif ext.lower() == ".ogg":
                    from auto_tag.audio_recognize import update_ogg_tags

                    update_ogg_tags(
                        unique,
                        title,
                        "Unknown Artist",
                        "Unknown Album",
                        res.get("cover_link", ""),
                        trace=False,
                    )

            except Exception as exc:
                errors.append(f"{old_path}: {exc}")

        if errors:
            messagebox.showerror("Errors Occurred", "\n".join(errors))
        else:
            messagebox.showinfo("Success", "Changes applied successfully.")


# ──────────────────────────────────────────────────────────────────────────────
# module-level helper
# ──────────────────────────────────────────────────────────────────────────────
def launch_gui() -> None:
    root = tk.Tk()

    # icon (best-effort, non-fatal)
    icon_path = os.path.join(get_base_directory(), "assets", "auto_tag.ico")
    try:
        root.iconbitmap(icon_path)
    except Exception:
        pass

    MP3RenamerGUI(root)
    root.mainloop()


# allow manual launch
if __name__ == "__main__":
    launch_gui()
