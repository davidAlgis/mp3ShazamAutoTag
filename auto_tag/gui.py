# auto_tag/gui.py
from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from shazamio import Shazam

from auto_tag.audio_recognize import (recognize_and_rename_file,
                                      update_mp3_cover_art, update_mp3_tags,
                                      update_ogg_tags)

# project helpers ────────────────────────────────────────────────────────────


# shared results list between worker thread and main thread
RESULTS: list[dict] = []


def _base_dir() -> str:
    """Return project root or PyInstaller temp dir."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, os.pardir))


# ─────────────────────────────────────────────────────────────────────────────
# Main GUI class
# ─────────────────────────────────────────────────────────────────────────────
class MP3RenamerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MP3 Shazam Auto Tag")

        self.data: list[dict] = []
        self.editing_entry: tk.Entry | None = None
        self.total_files = 0
        self.start_time: float | None = None

        self._build_layout()

    # ─────────────────────────────── layout ────────────────────────────────
    def _build_layout(self) -> None:
        # top bar: directory picker
        top = ttk.Frame(self.root, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Input Directory:").pack(side=tk.LEFT)
        self.dir_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.dir_var, width=50).pack(
            side=tk.LEFT, padx=(5, 0)
        )
        ttk.Button(top, text="Browse", command=self._browse).pack(
            side=tk.LEFT, padx=5
        )

        # progress bar
        pf = ttk.Frame(self.root, padding=10)
        pf.pack(fill=tk.X)
        self.progress = ttk.Progressbar(pf, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.progress_info = ttk.Label(pf, text="0/0, Remaining 0 s")
        self.progress_info.pack(side=tk.LEFT)

        # results tree
        style = ttk.Style()
        style.configure("Custom.Treeview", rowheight=30, padding=5)
        style.configure("Custom.Treeview.Heading", padding=5)

        tree_wrap = ttk.Frame(self.root, padding=10)
        tree_wrap.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("apply", "old", "new"),
            show="headings",
            style="Custom.Treeview",
        )
        self.tree.heading("apply", text="Apply")
        self.tree.heading(
            "old", text="Old Name", command=lambda: self._sort("old")
        )
        self.tree.heading(
            "new", text="New Name", command=lambda: self._sort("new")
        )
        self.tree.column("apply", width=80, anchor="center")
        self.tree.column("old", width=300, anchor="w")
        self.tree.column("new", width=300, anchor="w")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # vertical scrollbar wired correctly
        vscroll = ttk.Scrollbar(
            tree_wrap, orient="vertical", command=self.tree.yview
        )
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vscroll.set)

        self.tree.tag_configure("Yes", foreground="#5a7849")
        self.tree.tag_configure("No", foreground="#DB504A")

        # events
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Return>", self._on_enter)
        self.tree.bind("<Double-1>", self._on_double_click)

        # bottom buttons
        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Button(
            bottom, text="Apply", command=lambda: self._apply(False)
        ).pack(side=tk.RIGHT, padx=5)
        ttk.Button(
            bottom,
            text="Apply with Plex Convention",
            command=lambda: self._apply(True),
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(bottom, text="Uncheck All", command=self._uncheck_all).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(bottom, text="Check All", command=self._check_all).pack(
            side=tk.RIGHT, padx=5
        )

    # ────────────────────────── directory picker ───────────────────────────
    def _browse(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)
            self._start_recognition(directory)

    # ───────────────────── background recognise worker ─────────────────────
    def _start_recognition(self, directory: str) -> None:
        # reset GUI
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.data.clear()
        RESULTS.clear()
        self.progress.config(value=0)
        self.progress_info.config(text="0/0, Remaining 0 s")

        threading.Thread(
            target=self._recognise_thread,
            args=(directory,),
            daemon=True,
        ).start()

    def _recognise_thread(self, directory: str) -> None:
        asyncio.run(self._process_files(directory))
        self.root.after(0, self._populate_tree)

    async def _process_files(self, directory: str) -> None:
        audio_files: list[str] = []
        for rootdir, _, names in os.walk(directory):
            if "test" in os.path.basename(rootdir).lower():
                continue
            for n in names:
                if n.lower().endswith((".mp3", ".ogg")):
                    audio_files.append(os.path.join(rootdir, n))

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

        for idx, path in enumerate(audio_files, 1):
            try:
                res = await recognize_and_rename_file(
                    file_path=path,
                    shazam=shazam,
                    modify=False,  # preview only
                    delay=10,
                    nbr_retry=3,
                    trace=False,
                    output_dir=None,
                    plex_structure=False,
                )
                res["apply"] = "error" not in res
            except Exception as exc:
                res = {
                    "file_path": path,
                    "new_file_path": str(exc),
                    "apply": False,
                }
            RESULTS.append(res)

            elapsed = time.time() - self.start_time
            remaining = int(elapsed / idx * (self.total_files - idx))
            self.root.after(
                0, lambda d=idx, r=remaining: self._update_progress(d, r)
            )

    # ─────────────────────────── tree helpers ──────────────────────────────
    def _update_progress(self, done: int, remaining: int) -> None:
        self.progress.config(value=done)
        self.progress_info.config(
            text=f"{done}/{self.total_files}, Remaining {remaining} s"
        )

    def _populate_tree(self) -> None:
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

    # ───────────────────────── click / key events ──────────────────────────
    def _toggle(self, idx: int, iid) -> None:
        self.data[idx]["apply"] = not self.data[idx].get("apply", True)
        tag = "Yes" if self.data[idx]["apply"] else "No"
        self.tree.set(iid, "apply", tag)
        self.tree.item(iid, tags=(tag,))

    def _on_click(self, event) -> None:
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        col, iid = self.tree.identify_column(event.x), self.tree.identify_row(
            event.y
        )
        if iid and col == "#1":
            self._toggle(self.tree.index(iid), iid)

    def _on_enter(self, _) -> None:
        iid = self.tree.focus()
        if iid:
            self._toggle(self.tree.index(iid), iid)

    def _on_double_click(self, event) -> None:
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        col, iid = self.tree.identify_column(event.x), self.tree.identify_row(
            event.y
        )
        if not iid:
            return
        idx = self.tree.index(iid)

        if col in ("#1", "#2"):
            self._toggle(idx, iid)
        elif col == "#3":  # edit new name
            x, y, w, h = self.tree.bbox(iid, col)
            current = self.tree.set(iid, "new")
            self.editing_entry = tk.Entry(self.tree)
            self.editing_entry.place(x=x, y=y, width=w, height=h)
            self.editing_entry.insert(0, current)
            self.editing_entry.focus()
            self.editing_entry.bind(
                "<Return>", lambda _: self._finish_edit(iid)
            )
            self.editing_entry.bind(
                "<FocusOut>", lambda _: self._finish_edit(iid)
            )

    def _finish_edit(self, iid) -> None:
        if not self.editing_entry:
            return
        new_val = self.editing_entry.get()
        self.tree.set(iid, "new", new_val)

        idx = self.tree.index(iid)
        old_new = self.data[idx].get("new_file_path", "")
        dirpath = os.path.dirname(old_new) if old_new else ""
        self.data[idx]["new_file_path"] = (
            os.path.join(dirpath, new_val) if dirpath else new_val
        )

        self.editing_entry.destroy()
        self.editing_entry = None

    # ───────────────────────────── sorting ────────────────────────────────
    def _sort(self, key: str) -> None:
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

        for iid in self.tree.get_children():
            self.tree.delete(iid)
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

    # ───────────────────────────── bulk toggle ────────────────────────────
    def _check_all(self) -> None:
        for idx, res in enumerate(self.data):
            res["apply"] = True
            iid = self.tree.get_children()[idx]
            self.tree.set(iid, "apply", "Yes")
            self.tree.item(iid, tags=("Yes",))

    def _uncheck_all(self) -> None:
        for idx, res in enumerate(self.data):
            res["apply"] = False
            iid = self.tree.get_children()[idx]
            self.tree.set(iid, "apply", "No")
            self.tree.item(iid, tags=("No",))

    # ───────────────────────────────── APPLY ──────────────────────────────
    def _apply(self, plex: bool) -> None:
        errors: list[str] = []

        for res in self.data:
            if not res.get("apply"):
                continue

            src = res.get("file_path")
            if not src or not os.path.exists(src):
                continue

            # metadata from Shazam (already sanitised)
            title: str = res.get("title", "Unknown Title")
            artist: str = res.get("author", "Unknown Artist")
            album: str = res.get("album", "Unknown Album")
            ext = os.path.splitext(src)[1].lower()

            if plex:
                base_dir = os.path.join(os.path.dirname(src), artist, album)
                os.makedirs(base_dir, exist_ok=True)
                dest = os.path.join(base_dir, f"{title}{ext}")
            else:
                dest = res.get("new_file_path") or os.path.join(
                    os.path.dirname(src), f"{title}{ext}"
                )

            # ensure unique
            counter, unique = 1, dest
            while os.path.exists(unique):
                root, ext2 = os.path.splitext(dest)
                unique = f"{root} ({counter}){ext2}"
                counter += 1

            try:
                os.rename(src, unique)

                # write tags/cover based on extension
                if ext == ".mp3":
                    update_mp3_tags(unique, title, artist, album)
                    update_mp3_cover_art(
                        unique, res.get("cover_link", ""), trace=False
                    )
                elif ext == ".ogg":
                    update_ogg_tags(
                        unique,
                        title,
                        artist,
                        album,
                        res.get("cover_link", ""),
                        trace=False,
                    )
            except Exception as exc:
                errors.append(f"{src}: {exc}")

        if errors:
            messagebox.showerror("Errors Occurred", "\n".join(errors))
        else:
            messagebox.showinfo("Success", "Changes applied successfully.")


# ─────────────────────────────── entry point ───────────────────────────────
def launch_gui() -> None:
    root = tk.Tk()
    try:
        root.iconbitmap(os.path.join(_base_dir(), "assets", "auto_tag.ico"))
    except Exception:
        pass  # icon is optional

    MP3RenamerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
