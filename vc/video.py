"""Render the analysed practice as a scrolling video with the original audio."""
import bisect
import os
import subprocess
import tempfile
import textwrap

import imageio_ffmpeg
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

from .analysis import Result, fmt_t, note_name
from .score import beats_per_bar

Image.MAX_IMAGE_PIXELS = None

W, H, FPS = 1280, 720, 30
PPS = 170                      # strip pixels per second
GUTTER = 64
LANE_Y, LANE_H = 92, 372
PLAYHEAD = 380                 # playhead x inside the lane
OUTRO = 12.0                   # seconds of summary card after the audio

BG = (17, 20, 24)
LANE = (23, 27, 33)
GRIDLINE = (35, 40, 48)
GHOST = (52, 60, 74)
TEXT = (232, 234, 237)
MUTED = (138, 147, 160)
GOOD = (62, 207, 142)
WARN = (245, 196, 81)
BAD = (255, 107, 107)
ACCENT = (106, 168, 255)


def _font(size, mono=False, bold=False):
    paths = (["/System/Library/Fonts/Menlo.ttc"] if mono else
             ["/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/Helvetica.ttc"])
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size, index=1 if bold else 0)
            except OSError:
                continue
    return ImageFont.load_default(size)


def grade(cents, status="ok"):
    if status != "ok":
        return BAD
    a = abs(cents)
    return GOOD if a <= 10 else WARN if a <= 25 else BAD


class Renderer:
    def __init__(self, res: Result, fb: dict, photo=None, beat_unit=1.0):
        self.res, self.fb, self.photo = res, fb, photo
        self.a = res.audio
        self.notes = [n for n in self.a.notes]
        self.starts = [n.start for n in self.notes]
        targets = [n.target for n in self.notes if n.target is not None]
        targets += [n.expected for n in self.notes if n.expected is not None]
        lo, hi = (min(targets), max(targets)) if targets else (67, 79)
        self.lo, self.hi = lo - 1.5, hi + 1.5
        self.ps = LANE_H / (self.hi - self.lo)        # pixels per semitone
        self.f = dict(title=_font(26, bold=True), h=_font(20), small=_font(15),
                      tiny=_font(13), mono=_font(15, mono=True),
                      big=_font(40, bold=True), cap=_font(30), cap_label=_font(14, bold=True))
        self.bpb = beats_per_bar(res.score.meter, beat_unit) if res.score else None
        self._build_strip()
        self._build_base()

    # ------------------------------------------------------------ geometry
    def y(self, midi):
        return LANE_H - (midi - self.lo) * self.ps

    def sx(self, t):
        return PLAYHEAD + t * PPS

    # ------------------------------------------------------------ static art
    def _build_strip(self):
        a = self.a
        w = int(self.sx(a.duration + OUTRO) + W)
        img = Image.new("RGB", (w, LANE_H), LANE)
        d = ImageDraw.Draw(img)
        for m in range(int(np.ceil(self.lo)), int(self.hi) + 1):
            if note_name(m)[1] != "#":
                d.line([(0, self.y(m)), (w, self.y(m))], fill=GRIDLINE, width=1)

        # beats, with bar lines anchored where pass 1 started
        bar0 = None
        if self.bpb:
            first = next((n for n in self.notes if n.index_in_score is not None), None)
            if first:
                sn = self.res.score.notes[first.index_in_score]
                bar0 = round(a.grid.beat_pos(first.start) - sn.onset)
        for k, t in enumerate(a.grid.clicks):
            x = self.sx(t)
            is_bar = bar0 is not None and (k - bar0) % round(self.bpb) == 0
            d.line([(x, 0), (x, LANE_H)], fill=(70, 80, 96) if is_bar else (44, 51, 62),
                   width=2 if is_bar else 1)

        tr = a.track
        for n in self.notes:
            x0, x1 = self.sx(n.start), self.sx(n.end)
            if n.expected is not None:
                yy = self.y(n.expected)
                d.rounded_rectangle([x0, yy - self.ps * 0.4, x1, yy + self.ps * 0.4],
                                    radius=4, fill=GHOST)
            col = grade(n.cents, n.status)
            i0 = bisect.bisect_left(tr.times, n.start)
            i1 = bisect.bisect_right(tr.times, n.end)
            pts = [(self.sx(tr.times[i]), self.y(tr.midi[i]))
                   for i in range(i0, i1) if not np.isnan(tr.midi[i])
                   and abs(tr.midi[i] - n.midi) < 1.0]
            if len(pts) > 1:
                d.line(pts, fill=col, width=4, joint="curve")
            label = (f"{note_name(n.target)} {n.cents:+.0f}" if n.status == "ok" else
                     f"{note_name(n.target)}≠{note_name(n.expected)}" if n.status == "wrong" else
                     f"+{note_name(n.target)}?")
            ly = self.y(max(n.midi, n.expected or n.midi)) - self.ps * 0.5 - 18
            d.text((x0, ly), label, font=self.f["tiny"], fill=col)

        for e in self.res.events:
            if e.kind in ("missed", "restart"):
                x = self.sx(e.t)
                d.line([(x, 0), (x, LANE_H)], fill=BAD if e.kind == "missed" else WARN, width=2)
                d.text((x + 4, 4), e.text, font=self.f["tiny"],
                       fill=BAD if e.kind == "missed" else WARN)
        for c in self.fb.get("comments", []):
            x = self.sx(c["t"])
            d.polygon([(x - 7, LANE_H - 14), (x + 7, LANE_H - 14), (x, LANE_H - 3)], fill=ACCENT)
        self.strip = img

    def _build_base(self):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        sc = self.res.score
        d.text((24, 18), sc.title if sc else "Violin practice", font=self.f["title"], fill=TEXT)
        sub = f"{self.a.grid.bpm:.0f} BPM" + (f"  ·  key {sc.key}  ·  {sc.meter}" if sc else "")
        d.text((24, 54), sub, font=self.f["small"], fill=MUTED)
        # label the pitches actually played/expected, dropping any too close to the last
        used = {n.target for n in self.notes} | {n.expected for n in self.notes}
        used.discard(None)
        last_y = -100
        for m in range(int(np.ceil(self.lo)), int(self.hi) + 1):
            yy = LANE_Y + self.y(m)
            if m in used and abs(yy - last_y) >= 15:
                d.text((12, yy - 8), note_name(m), font=self.f["mono"], fill=MUTED)
                last_y = yy
        # legend
        lx = W - 740
        for col, txt in ((GOOD, "within 10¢"), (WARN, "10–25¢"), (BAD, ">25¢ / wrong"), (GHOST, "score")):
            d.rounded_rectangle([lx, 62, lx + 14, 72], radius=3, fill=col)
            d.text((lx + 20, 58), txt, font=self.f["tiny"], fill=MUTED)
            lx += 112
        self.base = img

    # ------------------------------------------------------------ per frame
    def _current_note(self, t):
        i = bisect.bisect_right(self.starts, t) - 1
        if i >= 0 and t <= self.notes[i].end + 0.35:
            return self.notes[i]
        return None

    def _caption(self, t):
        cur = None
        for c in self.fb.get("comments", []):
            if c["t"] - 0.3 <= t < c["t"] + 5.0:
                cur = c
        return cur

    def _meter(self, d, x, y, w, value, lim, ticks, label, col):
        d.rounded_rectangle([x, y, x + w, y + 10], radius=5, fill=(40, 46, 56))
        cx = x + w / 2
        for tk in ticks:
            for s in (-1, 1):
                tx = cx + s * tk / lim * w / 2
                d.line([(tx, y - 3), (tx, y + 13)], fill=(70, 78, 92), width=1)
        d.line([(cx, y - 6), (cx, y + 16)], fill=MUTED, width=2)
        if value is not None:
            v = max(-lim, min(lim, value))
            nx = cx + v / lim * w / 2
            d.ellipse([nx - 8, y - 3, nx + 8, y + 13], fill=col)
        d.text((x, y + 20), label, font=self.f["small"], fill=col if value is not None else MUTED)

    def frame(self, t):
        if t > self.a.duration:
            return self.outro()
        img = self.base.copy()
        sx0 = int(t * PPS)
        img.paste(self.strip.crop((sx0, 0, sx0 + W - GUTTER, LANE_H)), (GUTTER, LANE_Y))
        d = ImageDraw.Draw(img)
        px = GUTTER + PLAYHEAD
        d.line([(px, LANE_Y), (px, LANE_Y + LANE_H)], fill=(255, 255, 255), width=2)

        # header: time, pass, metronome flash
        n = self._current_note(t)
        d.text((W - 200, 18), fmt_t(t), font=self.f["title"], fill=TEXT)
        if n is not None and n.rep is not None and self.res.score:
            d.text((W - 200, 54), f"pass {n.rep + 1}/{len(self.res.reps)}", font=self.f["small"], fill=MUTED)
        g = self.a.grid
        k = bisect.bisect_right(g.clicks, t) - 1
        flash = k >= 0 and t - g.clicks[k] < 0.09
        d.ellipse([W - 250, 26, W - 230, 46], fill=ACCENT if flash else (45, 52, 64))

        # caption
        c = self._caption(t)
        cy = LANE_Y + LANE_H + 16
        if c:
            d.rounded_rectangle([24, cy, W - 24, cy + 108], radius=12, fill=(28, 36, 52))
            d.text((44, cy + 12), "COACH", font=self.f["cap_label"], fill=ACCENT)
            lines = textwrap.wrap(c["text"], 64)[:2]
            for i, ln in enumerate(lines):
                d.text((44, cy + 32 + i * 36), ln, font=self.f["cap"], fill=TEXT)

        # readouts
        ry = H - 92
        if n is not None and n.status == "ok":
            word = "in tune" if abs(n.cents) <= 10 else "sharp" if n.cents > 0 else "flat"
            self._meter(d, 40, ry, 360, n.cents, 50, (10, 25),
                        f"{note_name(n.target)}  {n.cents:+.0f}¢  {word}", grade(n.cents))
        elif n is not None and n.status == "wrong":
            self._meter(d, 40, ry, 360, None, 50, (10, 25),
                        f"wrong note: {note_name(n.target)} (score: {note_name(n.expected)})", BAD)
        else:
            self._meter(d, 40, ry, 360, None, 50, (10, 25), "pitch", MUTED)
        tm = n.timing_ms if n is not None and n.status == "ok" else None
        if tm is not None:
            tcol = GOOD if abs(tm) <= 20 else WARN if abs(tm) <= 50 else BAD
            word = "on the beat" if abs(tm) <= 20 else "late" if tm > 0 else "early"
            self._meter(d, 470, ry, 360, tm, 120, (20, 50), f"{abs(tm):.0f} ms {word}", tcol)
        else:
            self._meter(d, 470, ry, 360, None, 120, (20, 50), "timing", MUTED)

        # session timeline
        d.rounded_rectangle([900, ry, W - 40, ry + 10], radius=5, fill=(40, 46, 56))
        span = W - 40 - 900
        d.rounded_rectangle([900, ry, 900 + span * t / self.a.duration, ry + 10], radius=5, fill=ACCENT)
        for cm in self.fb.get("comments", []):
            x = 900 + span * cm["t"] / self.a.duration
            d.line([(x, ry - 5), (x, ry + 15)], fill=TEXT, width=2)
        d.text((900, ry + 20), "session", font=self.f["small"], fill=MUTED)
        return img

    def outro(self):
        if hasattr(self, "_outro"):
            return self._outro
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        fb = self.fb
        y = 36
        for ln in wrap_px(fb.get("headline", ""), self.f["big"], W - 96)[:2]:
            d.text((48, y), ln, font=self.f["big"], fill=TEXT)
            y += 50
        y += 14
        top = y
        right = 700 if self.photo else W - 48
        reps = [r for r in self.res.reps if r["abs_cents"] is not None]
        bottom = H - 130 if len(reps) > 1 else H - 24
        sections = (("What the numbers say", fb.get("summary", [])[:4], ACCENT),
                    ("Tomorrow's practice", fb.get("next_steps", [])[:4], GOOD))

        # shrink the body text until both sections fit above the chart
        for size in range(20, 12, -1):
            body = _font(size)
            line_h = int(size * 1.4)
            layout, y = [], top
            for title, items, col in sections:
                layout.append(("title", title, col, y))
                y += 24
                for it in items:
                    for j, ln in enumerate(wrap_px(str(it), body, right - 48 - 20)):
                        layout.append(("line", ln, j, y))
                        y += line_h
                    y += 5
                y += 12
            if y <= bottom:
                break
        for kind, text, extra, ly in layout:
            if kind == "title":
                d.text((48, ly), text.upper(), font=self.f["cap_label"], fill=extra)
            else:
                d.text((48 if extra == 0 else 68, ly), ("• " if extra == 0 else "") + text,
                       font=body, fill=TEXT)

        # pass-by-pass bars
        if len(reps) > 1:
            by = H - 30
            d.text((48, by - 100), "PASS BY PASS  (pitch error ¢ / timing ms)", font=self.f["cap_label"], fill=MUTED)
            bw = min(40, (right - 48) // (len(reps) * 2))
            for i, r in enumerate(reps[:30]):
                x = 48 + i * bw * 2
                hc = min(70, r["abs_cents"] * 2.5)
                ht = min(70, abs(r["timing_mean"] or 0) * 1.0)
                d.rectangle([x, by - hc, x + bw * 0.45, by], fill=grade(r["abs_cents"]))
                tm = abs(r["timing_mean"] or 0)
                d.rectangle([x + bw * 0.5, by - ht, x + bw * 0.95, by],
                            fill=GOOD if tm <= 20 else WARN if tm <= 50 else BAD)
                d.text((x, by + 4), str(r["rep"]), font=self.f["tiny"], fill=MUTED)
        if self.photo:
            ph = self.photo.copy()
            ph.thumbnail((W - right - 72, H - top - 40))
            img.paste(ph, (W - 48 - ph.width, top))
        self._outro = img
        return img


def wrap_px(text, font, width):
    """Word-wrap by rendered width rather than character count."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def render(res: Result, fb: dict, audio_path, out_path, photo=None, beat_unit=1.0, log=print):
    r = Renderer(res, fb, photo, beat_unit)
    total = res.audio.duration + OUTRO
    nframes = int(total * FPS)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        sf.write(wav, res.audio.y * 0.95, res.audio.sr)  # decoded mono copy: any input format works
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
               out_path]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(nframes):
            p.stdin.write(r.frame(i / FPS).tobytes())
            if i % (FPS * 10) == 0:
                log(f"  video {i / FPS:5.0f}s / {total:.0f}s")
        p.stdin.close()
        if p.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    return r
