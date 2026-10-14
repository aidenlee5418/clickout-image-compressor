"""Clickout Media Image Compressor — Tkinter GUI."""

import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from compressor import Options, collect_images, compress_all, format_size
from widgets import (ACCENT, BORDER, CARD, CARD_HI, FONT, MUTED, TEXT,
                     PillButton, Segmented, Slider, Toggle)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

BG = "#101216"
LOG_BG = "#14161B"
OK_GREEN = "#5DD39E"
ERR_RED = "#F27D72"

FORMATS = [("Original", "keep"), ("WebP", "webp"), ("AVIF", "avif"),
           ("JPG", "jpeg"), ("PNG", "png")]
TARGETS = [("Off", 0), ("50 KB", 50), ("100 KB", 100), ("200 KB", 200), ("300 KB", 300)]
WIDTHS = [("Off", 0), ("800", 800), ("1200", 1200), ("1920", 1920), ("2560", 2560)]


class App:
    def __init__(self, root):
        self.root = root
        root.title("Clickout Media Image Compressor")
        root.geometry("700x790")
        root.minsize(660, 710)
        root.configure(bg=BG)

        self.files = []
        self.running = False
        self.last_output_dirs = set()
        self.current_target = 0

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TProgressbar", background=ACCENT, troughcolor=CARD,
                        borderwidth=0, thickness=5)

        main = tk.Frame(root, bg=BG, padx=22, pady=18)
        main.pack(fill="both", expand=True)

        # ── Header ────────────────────────────────────────────
        header = tk.Frame(main, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text="Clickout Media", font=(FONT, 12, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(header, text="Image Compressor", font=(FONT, 12),
                 bg=BG, fg=MUTED).pack(side="left", padx=(6, 0))
        PillButton(header, "✦ SEO Preset",
                   command=self.apply_seo_preset).pack(side="right")

        # ── Drop zone ─────────────────────────────────────────
        drop_wrap = tk.Frame(main, bg=BORDER, padx=1, pady=1)
        drop_wrap.pack(fill="x", pady=(14, 0))
        drop_text = "Drop images or folders here" if DND_AVAILABLE \
            else "Use the buttons below to add files or folders"
        self.drop_label = tk.Label(
            drop_wrap, text=drop_text, font=(FONT, 13),
            bg=CARD, fg=MUTED, height=4,
        )
        self.drop_label.pack(fill="x")
        if DND_AVAILABLE:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self.on_drop)
            self.drop_label.bind("<Enter>", lambda e: self.drop_label.config(bg=CARD_HI))
            self.drop_label.bind("<Leave>", lambda e: self.drop_label.config(bg=CARD))

        # ── File list ─────────────────────────────────────────
        btn_row = tk.Frame(main, bg=BG)
        btn_row.pack(fill="x", pady=(10, 6))
        PillButton(btn_row, "Add Files", command=self.add_files).pack(side="left")
        PillButton(btn_row, "Add Folder", command=self.add_folder).pack(side="left", padx=6)
        PillButton(btn_row, "Clear", command=self.clear_files).pack(side="left")
        self.count_label = tk.Label(btn_row, text="0 files", font=(FONT, 11),
                                    bg=BG, fg=MUTED)
        self.count_label.pack(side="right")

        list_wrap = tk.Frame(main, bg=BORDER, padx=1, pady=1)
        list_wrap.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(
            list_wrap, height=5, font=(FONT, 11), bg=CARD, fg=TEXT,
            bd=0, highlightthickness=0, selectbackground=ACCENT,
            selectforeground="#0E1013", activestyle="none",
        )
        self.listbox.pack(fill="both", expand=True, padx=8, pady=6)

        # ── Settings ──────────────────────────────────────────
        settings_wrap = tk.Frame(main, bg=BORDER, padx=1, pady=1)
        settings_wrap.pack(fill="x", pady=(12, 0))
        settings = tk.Frame(settings_wrap, bg=CARD, padx=16, pady=14)
        settings.pack(fill="both")

        self._section(settings, "FORMAT",
                      "WebP and AVIF load fastest — best for page speed and Core Web Vitals")
        self.out_format = Segmented(settings, FORMATS, value="webp")
        self.out_format.pack(anchor="w", pady=(6, 12))

        self._section(settings, "TARGET SIZE",
                      "Guide: thumbnails ≤ 50 KB · content images ≤ 100 KB · hero images ≤ 200 KB")
        self.target_kb = Segmented(settings, TARGETS, value=100)
        self.target_kb.pack(anchor="w", pady=(6, 12))

        self._section(settings, "MAX WIDTH",
                      "Web pages rarely need images wider than 1920 px")
        self.max_width = Segmented(settings, WIDTHS, value=1920)
        self.max_width.pack(anchor="w", pady=(6, 12))

        self._section(settings, "QUALITY",
                      "Upper bound — lowered automatically when a target size is set")
        q_row = tk.Frame(settings, bg=CARD)
        q_row.pack(fill="x", pady=(6, 12))
        self.quality_label = tk.Label(q_row, text="80", width=3,
                                      font=(FONT, 11, "bold"), bg=CARD, fg=ACCENT)
        self.quality = Slider(q_row, lo=1, hi=100, value=80,
                              command=lambda v: self.quality_label.config(text=str(v)))
        self.quality.pack(side="left", fill="x", expand=True)
        self.quality_label.pack(side="left", padx=(10, 0))

        t_row = tk.Frame(settings, bg=CARD)
        t_row.pack(fill="x")
        self.strip_meta = Toggle(t_row, "Strip metadata", value=True)
        self.strip_meta.pack(side="left")
        self.seo_rename = Toggle(t_row, "SEO filenames  (my-photo-1.webp)", value=True)
        self.seo_rename.pack(side="left", padx=(20, 0))

        # ── Run row ───────────────────────────────────────────
        run_row = tk.Frame(main, bg=BG)
        run_row.pack(fill="x", pady=(14, 0))
        self.start_btn = PillButton(run_row, "Compress", kind="accent",
                                    font_size=12, padx=22, pady=8, command=self.start)
        self.start_btn.pack(side="left")
        self.open_btn = PillButton(run_row, "Open Output Folder", command=self.open_output)
        self.open_btn.pack(side="left", padx=8)
        self.open_btn.set_state("disabled")

        self.progress = ttk.Progressbar(main, style="TProgressbar")
        self.progress.pack(fill="x", pady=(12, 6))

        # ── Log ───────────────────────────────────────────────
        log_wrap = tk.Frame(main, bg=BORDER, padx=1, pady=1)
        log_wrap.pack(fill="both", expand=True)
        self.log = tk.Text(
            log_wrap, height=7, state="disabled", font=("Menlo", 11),
            bg=LOG_BG, fg=TEXT, bd=0, highlightthickness=0, padx=10, pady=8,
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("ok", foreground=OK_GREEN)
        self.log.tag_configure("err", foreground=ERR_RED)
        self.log.tag_configure("muted", foreground=MUTED)

    # ── UI helpers ────────────────────────────────────────────
    def _section(self, parent, title, caption):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x")
        tk.Label(row, text=title, font=(FONT, 9, "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        tk.Label(row, text="   " + caption, font=(FONT, 9),
                 bg=CARD, fg=MUTED).pack(side="left")

    # ── SEO preset ────────────────────────────────────────────
    def apply_seo_preset(self):
        self.out_format.set("webp")
        self.target_kb.set(100)
        self.max_width.set(1920)
        self.quality.set(80)
        self.strip_meta.set(True)
        self.seo_rename.set(True)
        self.log_write("SEO preset applied: WebP · ≤100 KB · max 1920 px · "
                       "strip metadata · SEO filenames\n", "muted")

    # ── File list ─────────────────────────────────────────────
    def on_drop(self, event):
        self._add_paths(self.root.tk.splitlist(event.data))

    def add_files(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.avif *.svg"),
                       ("All files", "*.*")]
        )
        if paths:
            self._add_paths(paths)

    def add_folder(self):
        path = filedialog.askdirectory()
        if path:
            self._add_paths([path])

    def _add_paths(self, paths):
        images, skipped = collect_images(list(paths))
        added = 0
        for f in images:
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", f"  {f}")
                added += 1
        self.count_label.config(text=f"{len(self.files)} files")
        if skipped:
            names = ", ".join(f.name for f in skipped[:10])
            if len(skipped) > 10:
                names += f", and {len(skipped) - 10} more"
            self.log_write(f"Skipped {len(skipped)} unsupported file(s): {names}\n", "muted")
        if added:
            self.log_write(f"Added {added} file(s)\n", "muted")

    def clear_files(self):
        self.files.clear()
        self.listbox.delete(0, "end")
        self.count_label.config(text="0 files")

    # ── Run ───────────────────────────────────────────────────
    def start(self):
        if self.running or not self.files:
            if not self.files:
                self.log_write("Add some files first.\n", "muted")
            return

        opts = Options(
            quality=self.quality.get(),
            out_format=self.out_format.get(),
            target_kb=self.target_kb.get(),
            max_width=self.max_width.get(),
            strip_metadata=self.strip_meta.get(),
            seo_rename=self.seo_rename.get(),
        )
        self.running = True
        self.start_btn.set_state("disabled")
        self.open_btn.set_state("disabled")
        self.progress.config(maximum=len(self.files), value=0)
        self.log_clear()
        self.log_write(f"Compressing {len(self.files)} file(s)...\n", "muted")

        files = list(self.files)
        self.current_target = opts.target_kb * 1024
        threading.Thread(target=self._worker, args=(files, opts), daemon=True).start()

    def _worker(self, files, opts):
        def progress(i, total, r):
            self.root.after(0, self._on_progress, i, r)

        results = compress_all(files, opts, progress)
        self.root.after(0, self._on_done, results)

    def _on_progress(self, i, r):
        self.progress.config(value=i)
        if r.error:
            self.log_write(f"✗ {r.path.name}: {r.error}\n", "err")
        else:
            pct = (r.saved / r.original_size * 100) if r.original_size else 0
            note = ""
            if self.current_target and r.compressed_size > self.current_target \
                    and r.output and r.output.suffix != ".svg":
                note = "  (couldn't reach target at lowest quality)"
            self.log_write(
                f"✓ {r.path.name} → {r.output.name}: "
                f"{format_size(r.original_size)} → "
                f"{format_size(r.compressed_size)} (-{pct:.0f}%){note}\n", "ok"
            )

    def _on_done(self, results):
        self.running = False
        self.start_btn.set_state("normal")
        ok = [r for r in results if not r.error]
        failed = [r for r in results if r.error]
        total_saved = sum(r.saved for r in ok)
        self.log_write(
            f"\nDone: {len(ok)} succeeded"
            + (f", {len(failed)} failed" if failed else "")
            + f" — saved {format_size(total_saved)} total\n"
        )
        self.last_output_dirs = {r.output.parent for r in ok if r.output}
        if self.last_output_dirs:
            self.open_btn.set_state("normal")

    def open_output(self):
        for d in sorted(self.last_output_dirs):
            subprocess.run(["open", str(d)])

    # ── Log ───────────────────────────────────────────────────
    def log_write(self, text, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", text, tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def log_clear(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


def main():
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
