"""Draw a simple single-staff score (treble clef, sharps-only key, quarter/half/whole
notes) from an ABC file, as a test image for the photo reader.

  python tools/render_score.py takes/g_major_scale.abc takes/g_major_scale.png
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vc.score import parse_abc  # noqa: E402

SP = 18                       # staff line spacing (px)
STEP = SP / 2
LETTERS = "CDEFGAB"
SHARP_ORDER = [("F", 5), ("C", 5), ("G", 5), ("D", 5), ("A", 4), ("E", 5), ("B", 4)]
KEY_SHARPS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5}
SYM = "/System/Library/Fonts/Apple Symbols.ttf"


def diatonic(name):
    """'F#5' -> staff step number (C0 = 0)."""
    return int(name[-1]) * 7 + LETTERS.index(name[0])


def main(abc_path, out_path, per_line=17):
    sc = parse_abc(open(abc_path).read())
    notes = sc.notes
    lines = [notes[i:i + per_line] for i in range(0, len(notes), per_line)]
    W, line_h, top = 1700, 260, 140
    img = Image.new("RGB", (W, top + line_h * len(lines) + 40), "white")
    d = ImageDraw.Draw(img)
    clef = ImageFont.truetype(SYM, int(SP * 7.4))
    acc = ImageFont.truetype(SYM, int(SP * 2.4))
    big = ImageFont.truetype("/System/Library/Fonts/Times.ttc", int(SP * 2.3), index=1)
    title = ImageFont.truetype("/System/Library/Fonts/Times.ttc", 40)
    tw = d.textlength(sc.title, font=title)
    d.text(((W - tw) / 2, 40), sc.title, font=title, fill="black")
    n_sharps = KEY_SHARPS.get(sc.key.split()[0], 0)

    beat_in_bar = 0.0
    bar_len = 4.0
    for li, group in enumerate(lines):
        y_bot = top + li * line_h + 120          # bottom staff line (E4)
        x0, x1 = 60, W - 60

        def y(step):
            return y_bot - (step - diatonic("E4")) * STEP

        for k in range(5):
            d.line([(x0, y_bot - k * SP), (x1, y_bot - k * SP)], fill="black", width=2)
        d.text((x0 + 4, y_bot - SP * 6.1), "\U0001D11E", font=clef, fill="black")
        x = x0 + SP * 4.2
        for letter, octv in SHARP_ORDER[:n_sharps]:
            d.text((x, y(diatonic(f"{letter}{octv}")) - SP * 1.05), "♯", font=acc, fill="black")
            x += SP * 1.1
        if li == 0:
            for k, digit in enumerate(sc.meter.split("/")):
                d.text((x + 6, y_bot - SP * (4 - 2 * k) - SP * 0.2), digit, font=big, fill="black")
            x += SP * 2.4
        x += SP * 1.5
        dx = (x1 - x - SP * 2) / len(group)
        for n in group:
            cx = x + dx / 2
            st = diatonic(n.name.replace("#", "").replace("-", ""))
            cy = y(st)
            # ledger lines
            for ls in range(diatonic("C4"), st - 1, -2):
                d.line([(cx - SP * 1.0, y(ls)), (cx + SP * 1.0, y(ls))], fill="black", width=2)
            for ls in range(diatonic("A5"), st + 1, 2):
                d.line([(cx - SP * 1.0, y(ls)), (cx + SP * 1.0, y(ls))], fill="black", width=2)
            box = [cx - SP * 0.68, cy - SP * 0.5, cx + SP * 0.68, cy + SP * 0.5]
            if n.beats >= 2:
                d.ellipse(box, outline="black", width=3)
            else:
                d.ellipse(box, fill="black")
            if n.beats < 4:
                if st < diatonic("B4"):
                    d.line([(box[2] - 1, cy), (box[2] - 1, cy - SP * 3.5)], fill="black", width=2)
                else:
                    d.line([(box[0] + 1, cy), (box[0] + 1, cy + SP * 3.5)], fill="black", width=2)
            x += dx
            beat_in_bar += n.beats
            if beat_in_bar >= bar_len - 1e-6:
                beat_in_bar = 0
                bx = x - SP * 0.2 if n is not group[-1] else x1
                d.line([(bx, y_bot), (bx, y_bot - 4 * SP)], fill="black", width=2)
        if li == len(lines) - 1:
            d.line([(x1 - 8, y_bot), (x1 - 8, y_bot - 4 * SP)], fill="black", width=2)
            d.rectangle([x1 - 4, y_bot - 4 * SP, x1, y_bot], fill="black")
    img.save(out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main(*sys.argv[1:3])
