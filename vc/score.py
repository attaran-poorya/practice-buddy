"""Sheet music -> a flat list of expected notes.

The abstraction we want from the photo is small: the pitch sequence, each note's
length in beats, the meter and the key. ABC notation carries exactly that and is
something LLMs have seen a lot of, so a vision model transcribes the photo to ABC,
the ABC is saved next to the output, and you can correct it by hand and re-run.
Dense Sevcik pages are hard for any OMR, so: crop to the one exercise you played.
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from PIL import Image, ImageOps

TRANSCRIBE_PROMPT = """You are an expert music engraver. Transcribe the violin exercise in this image into ABC notation.

Rules:
- {which}
- Output a complete ABC tune: X:, T:, M: (meter), L: (default length), K: (key signature), then the notes.
- Get the key signature and every accidental right; pitch matters most, then rhythm.
- Write repeat signs as written (|: :|). Ignore fingerings, bowings, slurs and dynamics.
- If a passage is written as "simile" or with abbreviations, write the notes out.
- Reply with ONLY the ABC inside one ```abc code block."""


@dataclass
class ScoreNote:
    midi: int
    beats: float       # length in metronome beats (see parse_abc beat_unit)
    onset: float       # position from score start, in metronome beats
    name: str


@dataclass
class Score:
    title: str
    meter: str
    key: str
    notes: List[ScoreNote]
    abc: str

    @property
    def length_beats(self):
        return self.notes[-1].onset + self.notes[-1].beats if self.notes else 0


def prepare_photo(path, crop=None, max_side=2000):
    """crop: (x0, y0, x1, y1) as fractions 0..1 of the image."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("L")
    if crop:
        w, h = img.size
        img = img.crop((int(crop[0] * w), int(crop[1] * h),
                        int(crop[2] * w), int(crop[3] * h)))
    img = ImageOps.autocontrast(img, cutoff=1)
    img.thumbnail((max_side, max_side))
    return img.convert("RGB")


def transcribe_photo(llm, path, crop=None, which=None):
    img = prepare_photo(path, crop)
    which = (f"Transcribe only this exercise/line: {which}." if which else
             "If the image holds several exercises, transcribe only the first complete one.")
    text = llm.vision(TRANSCRIBE_PROMPT.format(which=which), img)
    m = re.search(r"```(?:abc)?\s*(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def parse_abc(abc: str, beat_unit: float = 1.0) -> Score:
    """beat_unit: what one metronome click is, in quarter notes
    (1 = clicks on quarters, 0.5 = clicks on eighths, 1.5 = dotted quarters in 6/8)."""
    import music21  # slow import, keep it local
    s = music21.converter.parse(abc, format="abc")
    try:
        s = s.expandRepeats()
    except Exception:
        pass  # no measures / odd repeats: alignment loops the score anyway
    notes = []
    for n in s.flatten().notes:
        if n.isChord:
            n = n.notes[-1]  # double stops: track the top voice
        if n.duration.quarterLength == 0:
            continue  # grace notes
        notes.append(ScoreNote(
            midi=int(n.pitch.midi),
            beats=float(n.duration.quarterLength) / beat_unit,
            onset=float(n.getOffsetInHierarchy(s)) / beat_unit,
            name=n.pitch.nameWithOctave,
        ))
    notes.sort(key=lambda x: x.onset)
    title = re.search(r"^T:(.*)$", abc, re.M)
    meter = re.search(r"^M:(.*)$", abc, re.M)
    key = re.search(r"^K:(.*)$", abc, re.M)
    return Score(title=title.group(1).strip() if title else "Exercise",
                 meter=meter.group(1).strip() if meter else "4/4",
                 key=key.group(1).strip() if key else "C",
                 notes=notes, abc=abc)


def beats_per_bar(meter: str, beat_unit: float = 1.0) -> Optional[float]:
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", meter or "")
    if not m:
        return None
    return int(m.group(1)) * 4 / int(m.group(2)) / beat_unit
