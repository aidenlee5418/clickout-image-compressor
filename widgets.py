"""Canvas-based rounded widgets — pill buttons, segmented controls, toggles, slider."""

import tkinter as tk
import tkinter.font as tkfont

FONT = "Helvetica Neue"

# Shared palette (kept in sync with app.py)
BG = "#101216"
CARD = "#181B21"
CARD_HI = "#22262E"
TRACK = "#20242B"
TEXT = "#E8EAEE"
MUTED = "#8A91A0"
BORDER = "#2A2E37"
ACCENT = "#7C83FF"
ACCENT_HI = "#959BFF"
ACCENT_DIM = "#3E4270"
ON_ACCENT = "#0E1013"


def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle as a smoothed polygon."""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class PillButton(tk.Canvas):
    """Rounded pill button. kind: 'accent' (filled) or 'ghost' (outlined)."""

    def __init__(self, parent, text, command=None, kind="ghost",
                 font_size=11, bold=False, padx=16, pady=7):
        self.font = tkfont.Font(family=FONT, size=font_size,
                                weight="bold" if bold or kind == "accent" else "normal")
        tw = self.font.measure(text)
        th = self.font.metrics("linespace")
        w, h = tw + padx * 2, th + pady * 2
        parent_bg = parent.cget("bg") if isinstance(parent, (tk.Frame, tk.Canvas)) else BG
        super().__init__(parent, width=w, height=h, bg=parent_bg,
                         bd=0, highlightthickness=0)
        self.command = command
        self.kind = kind
        self.state = "normal"
        r = h / 2 - 1
        if kind == "accent":
            self.shape = _round_rect(self, 1, 1, w - 1, h - 1, r, fill=ACCENT, outline="")
            self.label = self.create_text(w / 2, h / 2, text=text, font=self.font, fill=ON_ACCENT)
        else:
            self.shape = _round_rect(self, 1, 1, w - 1, h - 1, r,
                                     fill=CARD, outline=BORDER)
            self.label = self.create_text(w / 2, h / 2, text=text, font=self.font, fill=TEXT)
        self.bind("<Enter>", self._hover)
        self.bind("<Leave>", self._unhover)
        self.bind("<Button-1>", self._click)

    def _hover(self, _):
        if self.state != "normal":
            return
        self.config(cursor="pointinghand")
        self.itemconfig(self.shape, fill=ACCENT_HI if self.kind == "accent" else CARD_HI)

    def _unhover(self, _):
        if self.state != "normal":
            return
        self.config(cursor="")
        self.itemconfig(self.shape, fill=ACCENT if self.kind == "accent" else CARD)

    def _click(self, _):
        if self.state == "normal" and self.command:
            self.command()

    def set_state(self, state):
        self.state = state
        if state == "disabled":
            if self.kind == "accent":
                self.itemconfig(self.shape, fill=ACCENT_DIM)
                self.itemconfig(self.label, fill="#6E7280")
            else:
                self.itemconfig(self.shape, fill=CARD, outline=BORDER)
                self.itemconfig(self.label, fill="#565B66")
            self.config(cursor="")
        else:
            if self.kind == "accent":
                self.itemconfig(self.shape, fill=ACCENT)
                self.itemconfig(self.label, fill=ON_ACCENT)
            else:
                self.itemconfig(self.shape, fill=CARD, outline=BORDER)
                self.itemconfig(self.label, fill=TEXT)


class Segmented(tk.Canvas):
    """iOS-style segmented control: one rounded track, a filled pill on the selection."""

    HEIGHT = 32
    PAD = 3          # inset of the selected pill inside the track
    SEG_PADX = 14    # horizontal padding inside each segment

    def __init__(self, parent, options, value=None, command=None):
        self.font = tkfont.Font(family=FONT, size=11)
        self.options = options            # [(label, value), ...]
        self.value = value if value is not None else options[0][1]
        self.command = command
        self.widths = [self.font.measure(lbl) + self.SEG_PADX * 2 for lbl, _ in options]
        w = sum(self.widths) + self.PAD * 2
        h = self.HEIGHT
        parent_bg = parent.cget("bg") if isinstance(parent, (tk.Frame, tk.Canvas)) else CARD
        super().__init__(parent, width=w, height=h, bg=parent_bg,
                         bd=0, highlightthickness=0)
        self._draw()
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self.config(cursor="pointinghand"))
        self.bind("<Leave>", lambda e: self.config(cursor=""))

    def _draw(self):
        self.delete("all")
        w = sum(self.widths) + self.PAD * 2
        h = self.HEIGHT
        _round_rect(self, 0, 0, w, h, h / 2, fill=TRACK, outline="")
        x = self.PAD
        for (lbl, val), sw in zip(self.options, self.widths):
            if val == self.value:
                r = (h - self.PAD * 2) / 2
                _round_rect(self, x, self.PAD, x + sw, h - self.PAD, r,
                            fill=ACCENT, outline="")
                self.create_text(x + sw / 2, h / 2, text=lbl, font=self.font, fill=ON_ACCENT)
            else:
                self.create_text(x + sw / 2, h / 2, text=lbl, font=self.font, fill=MUTED)
            x += sw

    def _click(self, event):
        x = self.PAD
        for (lbl, val), sw in zip(self.options, self.widths):
            if x <= event.x <= x + sw:
                if val != self.value:
                    self.value = val
                    self._draw()
                    if self.command:
                        self.command(val)
                return
            x += sw

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self._draw()


class Toggle(tk.Frame):
    """Switch with a text label; click either to flip."""

    W, H = 42, 25

    def __init__(self, parent, text, value=True, command=None):
        parent_bg = parent.cget("bg") if isinstance(parent, (tk.Frame, tk.Canvas)) else CARD
        super().__init__(parent, bg=parent_bg)
        self.value = value
        self.command = command
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg=parent_bg,
                                bd=0, highlightthickness=0)
        self.canvas.pack(side="left")
        self.label = tk.Label(self, text=text, font=(FONT, 11), bg=parent_bg, fg=TEXT)
        self.label.pack(side="left", padx=(8, 0))
        self._draw()
        for widget in (self.canvas, self.label):
            widget.bind("<Button-1>", self._flip)
            widget.bind("<Enter>", lambda e: self.canvas.config(cursor="pointinghand"))
            widget.bind("<Leave>", lambda e: self.canvas.config(cursor=""))

    def _draw(self):
        c = self.canvas
        c.delete("all")
        w, h = self.W, self.H
        r = h / 2 - 1
        track = ACCENT if self.value else BORDER
        _round_rect(c, 1, 1, w - 1, h - 1, r, fill=track, outline="")
        kr = r - 3
        kx = (w - 1 - kr - 4) if self.value else (1 + kr + 4)
        knob = "#FFFFFF" if self.value else "#B8BDC8"
        c.create_oval(kx - kr, h / 2 - kr, kx + kr, h / 2 + kr, fill=knob, outline="")

    def _flip(self, _):
        self.value = not self.value
        self._draw()
        if self.command:
            self.command(self.value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)
        self._draw()


class Slider(tk.Canvas):
    """Horizontal slider with a round thumb. Values are ints in [lo, hi]."""

    H = 26
    THUMB_R = 8

    def __init__(self, parent, lo=1, hi=100, value=80, command=None):
        parent_bg = parent.cget("bg") if isinstance(parent, (tk.Frame, tk.Canvas)) else CARD
        super().__init__(parent, height=self.H, bg=parent_bg, bd=0, highlightthickness=0)
        self.lo, self.hi = lo, hi
        self.value = value
        self.command = command
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Enter>", lambda e: self.config(cursor="pointinghand"))
        self.bind("<Leave>", lambda e: self.config(cursor=""))

    def _geometry(self):
        w = self.winfo_width()
        pad = self.THUMB_R + 2
        return pad, max(w - pad, pad + 1)

    def _draw(self):
        self.delete("all")
        x0, x1 = self._geometry()
        cy = self.H / 2
        frac = (self.value - self.lo) / (self.hi - self.lo)
        tx = x0 + frac * (x1 - x0)
        self.create_line(x0, cy, x1, cy, fill=BORDER, width=4, capstyle="round")
        self.create_line(x0, cy, tx, cy, fill=ACCENT, width=4, capstyle="round")
        r = self.THUMB_R
        self.create_oval(tx - r, cy - r, tx + r, cy + r, fill="#FFFFFF", outline="")

    def _drag(self, event):
        x0, x1 = self._geometry()
        frac = min(1.0, max(0.0, (event.x - x0) / (x1 - x0)))
        new = round(self.lo + frac * (self.hi - self.lo))
        if new != self.value:
            self.value = new
            self._draw()
            if self.command:
                self.command(new)

    def get(self):
        return self.value

    def set(self, value):
        self.value = max(self.lo, min(self.hi, int(value)))
        self._draw()
        if self.command:
            self.command(self.value)
