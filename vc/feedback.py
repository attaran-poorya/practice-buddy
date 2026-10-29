"""Turn the measurement report into teacher-style feedback (LLM or rules)."""
from collections import defaultdict

import numpy as np

from .analysis import OPEN_STRINGS, Result, consistent_error, note_name
from .llm import extract_json

SYSTEM = """You are a warm, precise violin teacher reviewing a student's practice recording.
You do not hear the audio. You get measurements from software that tracked every note against the score and the metronome. Trust the numbers; do not invent problems that are not in them.

How to read the data:
- Intonation in cents (100c = 1 semitone). Within 10c is good; 10-25c is noticeable; over 25c is clearly out of tune.
- A pitch that is "consistently SHARP/FLAT" means a finger placement habit. Name the note and, when you can tell from the key and range, the likely finger/string (e.g. C#5 in first position on the A string is the 2nd finger).
- Timing in ms vs the metronome: under 20ms is fine. A steady positive average means dragging, negative means rushing. A large spread means unsteady rhythm.
- Compare passes: say whether things improved or got worse during the session (fatigue, focus).
- Note errors (wrong/missed/extra) and restarts show where the passage breaks down.

Reply with JSON only, in this shape:
{"headline": "<one encouraging sentence summarising the session>",
 "summary": ["<2-4 short observations, most important first>"],
 "comments": [{"t": <seconds, copied from a t= value in the data>, "text": "<max 18 words, shown on screen at that moment>"}],
 "next_steps": ["<2-3 concrete practice instructions for tomorrow>"]}
Give 4 to 8 comments, spread across the session, each tied to a specific moment listed in the data."""


def llm_feedback(llm, res: Result):
    text = llm.chat([{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": res.report}], json_mode=True)
    fb = extract_json(text)
    return _clean(fb, res)


def _clean(fb, res):
    dur = res.audio.duration
    times = sorted({n.start for n in res.audio.notes} | {e.t for e in res.events})
    out = []
    for c in fb.get("comments", []):
        try:
            t = float(c["t"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= t <= dur:
            continue
        if times:  # snap to a real note/event so the caption lands on the moment
            t = min(times, key=lambda x: abs(x - t))
        out.append({"t": t, "text": str(c.get("text", "")).strip()})
    fb["comments"] = sorted(out, key=lambda c: c["t"])
    fb.setdefault("headline", "Practice reviewed")
    fb.setdefault("summary", [])
    fb.setdefault("next_steps", [])
    return fb


def rule_feedback(res: Result):
    """No-LLM fallback: the same facts the LLM gets, phrased by simple rules."""
    comments, summary, steps = [], [], []
    ok = [n for n in res.audio.notes if n.status == "ok"]
    by = defaultdict(list)
    for n in ok:
        by[n.target].append(n)

    # instrument tuning first: no point fixing fingers against a flat open string
    for m, s in OPEN_STRINGS.items():
        if m in by:
            avg = np.mean([n.cents for n in by[m]])
            if abs(avg) >= 12:
                d = "flat" if avg < 0 else "sharp"
                summary.append(f"Open {s} string reads {avg:+.0f}c: the instrument is {d}, not your fingers.")
                steps.append(f"Tune the {s} string before practising (it was {abs(avg):.0f}c {d}).")
                comments.append({"t": by[m][0].start, "text": f"Open {s} string is {abs(avg):.0f}c {d}: retune it"})

    for m in sorted(by):
        if m in OPEN_STRINGS:
            continue
        cs = [n.cents for n in by[m]]
        if consistent_error(cs):
            name, avg = note_name(m), np.mean(cs)
            d = "sharp" if avg > 0 else "flat"
            summary.append(f"{name} is {d} every time ({avg:+.0f}c on average).")
            steps.append(f"Place {name} slowly against a drone or the open string, "
                         f"aiming {'lower' if d == 'sharp' else 'higher'}, 10 times.")
            worst = max(by[m], key=lambda n: abs(n.cents))
            comments.append({"t": worst.start, "text": f"{name} {worst.cents:+.0f}c: {d} again"})

    for e in res.events[:6]:
        comments.append({"t": e.t, "text": e.text})

    tm = [n for n in ok if n.timing_ms is not None]
    if tm:
        avg = np.mean([n.timing_ms for n in tm])
        if abs(avg) > 35:
            late = avg > 0
            summary.append(f"Notes land {abs(avg):.0f}ms {'after' if late else 'before'} the click on average"
                           f" ({'reacting to it rather than playing with it' if late else 'rushing'}).")
            steps.append("Breathe in on the beat before and start the bow change together with the click."
                         if late else "Let the click come to you; wait for it before each note.")
        worst = max(tm, key=lambda n: abs(n.timing_ms))
        if abs(worst.timing_ms) > 80:
            comments.append({"t": worst.start, "text":
                f"{note_name(worst.target)} {abs(worst.timing_ms):.0f}ms "
                f"{'late' if worst.timing_ms > 0 else 'early'}"})

    for r in res.reps:
        if len(res.reps) > 1 and r["timing_mean"] is not None and abs(r["timing_mean"]) > 35:
            late = r["timing_mean"] > 0
            comments.append({"t": r["start"], "text":
                f"Pass {r['rep']}: {'dragging' if late else 'rushing'}, "
                f"{abs(r['timing_mean']):.0f}ms {'behind' if late else 'ahead of'} the click"})
            break

    good = np.mean([abs(n.cents) <= 10 for n in ok]) if ok else 0
    if not summary:
        summary.append("No consistent intonation problems.")
    headline = (f"{good:.0%} of notes within 10 cents"
                + (f", {len(res.events)} note errors" if res.events else ", no wrong notes"))
    return _clean({"headline": headline, "summary": summary, "comments": comments,
                   "next_steps": steps or ["Repeat the exercise at the same tempo."]}, res)
