"""Align played notes to the score, measure them, and condense everything into a
short text report: the 'right level of abstraction' for a small LLM.

The LLM never sees audio or pixels, only facts like
"C#5: 12 times, avg +21c, consistent" and "rep 5: 38 ms late on average".
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional

import librosa
import numpy as np

from .audio import AudioAnalysis
from .score import Score, beats_per_bar

DEL, INS, START, RESTART = 1.0, 1.0, 1.0, 2.0


def note_name(midi):
    return librosa.midi_to_note(int(midi), unicode=False)


def fmt_t(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


OPEN_STRINGS = {55: "G", 62: "D", 69: "A", 76: "E"}


def consistent_error(cents):
    """Same-direction error on every instance of a pitch: a placement habit.
    With few instances (a scale plays each note twice) demand a bigger, tighter error."""
    cs = np.asarray(cents)
    mean, sd = cs.mean(), cs.std()
    return ((len(cs) >= 3 and abs(mean) >= 10 and sd < abs(mean))
            or (len(cs) == 2 and abs(mean) >= 15 and sd < abs(mean) / 2))


def _sub_cost(played, expected):
    d = abs(round(played) - expected)
    if d == 0:
        return 0.0
    if d % 12 == 0:
        return 0.4      # octave error is usually the pitch tracker, not the player
    return 1.0 if d <= 2 else 1.5


@dataclass
class Event:
    t: float
    kind: str           # wrong | missed | extra | restart
    text: str
    rep: Optional[int] = None


@dataclass
class Result:
    audio: AudioAnalysis
    score: Optional[Score]
    events: List[Event] = field(default_factory=list)
    reps: List[dict] = field(default_factory=list)
    report: str = ""


def align(notes, score: Score):
    """Looping alignment. State j = index of the last consumed score note.
    Transitions: play next score note (wrapping m-1 -> 0 = next repetition),
    extra played note, missed score note, or restart from note 0."""
    P = [n.midi for n in notes]
    E = [s.midi for s in score.notes]
    n, m = len(P), len(E)
    INF = 1e18
    prev = np.full(m, START)
    prev[m - 1] = 0.0                  # first played note may start the exercise for free
    back = []                          # back[i][j] = (kind, prev_j)
    for i in range(n):
        cur = np.full(m, INF)
        ptr = [None] * m
        best_prev = int(np.argmin(prev))
        for j in range(m):
            pj = (j - 1) % m
            c = prev[pj] + _sub_cost(P[i], E[j])
            cur[j], ptr[j] = c, ("play", pj)
            if j == 0:
                c = prev[best_prev] + RESTART + _sub_cost(P[i], E[0])
                if c < cur[j] and best_prev != m - 1:
                    cur[j], ptr[j] = c, ("restart", best_prev)
            c = prev[j] + INS
            if c < cur[j]:
                cur[j], ptr[j] = c, ("extra", j)
        for _ in range(2):             # missed notes, circular
            for j in range(m):
                pj = (j - 1) % m
                if cur[pj] + DEL < cur[j]:
                    cur[j], ptr[j] = cur[pj] + DEL, ("missed", pj)
        back.append(ptr)
        prev = cur

    # backtrace
    j = int(np.argmin(prev))
    steps = []
    i = n - 1
    while i >= 0:
        kind, pj = back[i][j]
        steps.append((i, j, kind, pj))
        if kind != "missed":
            i -= 1
        j = pj
    steps.reverse()
    return steps


def _timing(audio, beat_pos_expected_frac, t):
    g = audio.grid
    if t < g.clicks[0] - g.period or t > g.clicks[-1] + g.period:
        return None             # outside the metronome
    b = g.beat_pos(t)
    k = round(b - beat_pos_expected_frac)
    return (b - (k + beat_pos_expected_frac)) * g.period * 1000


def analyze(audio: AudioAnalysis, score: Optional[Score], a4=440.0) -> Result:
    res = Result(audio=audio, score=score)
    notes = audio.notes
    tune = 12 * math.log2(a4 / 440.0)
    for nt in notes:
        nt.midi -= tune

    if score and score.notes and notes:
        steps = align(notes, score)
        m = len(score.notes)
        rep, last_j = 0, None
        started = False
        for i, j, kind, pj in steps:
            if kind == "restart" or (started and kind == "play" and j == 0 and pj == m - 1):
                rep += 1
                if kind == "restart":
                    res.events.append(Event(notes[i].start, "restart",
                        f"restarted after note {pj + 1} ({score.notes[pj].name})", rep))
            if kind == "missed":
                t = notes[i].end if i >= 0 else notes[0].start
                if started:
                    res.events.append(Event(t, "missed",
                        f"missed note {j + 1} ({score.notes[j].name})", rep))
                continue
            nt = notes[i]
            nt.rep = rep
            if kind == "extra":
                nt.status = "extra"
                nt.target = int(round(nt.midi))
                res.events.append(Event(nt.start, "extra",
                    f"extra note {note_name(nt.target)}", rep))
            else:
                started = True
                sn = score.notes[j]
                nt.index_in_score = j
                nt.expected = sn.midi
                played = int(round(nt.midi))
                if played == sn.midi or abs(played - sn.midi) % 12 == 0:
                    nt.status, nt.target = "ok", played
                else:
                    nt.status, nt.target = "wrong", played
                    res.events.append(Event(nt.start, "wrong",
                        f"played {note_name(played)} instead of {sn.name} (note {j + 1})", rep))
                nt.timing_ms = _timing(audio, sn.onset % 1.0, nt.start)
            nt.cents = (nt.midi - nt.target) * 100
    else:
        # no score: nearest semitone, nearest subdivision of the beat
        iois = np.diff([n.start for n in notes]) if len(notes) > 1 else [audio.grid.period]
        sub = 2 ** round(math.log2(audio.grid.period / max(0.05, np.median(iois))))
        sub = int(min(4, max(1, sub)))
        for nt in notes:
            nt.target = int(round(nt.midi))
            nt.cents = (nt.midi - nt.target) * 100
            b = audio.grid.beat_pos(nt.start) * sub
            frac = (b - round(b)) / sub
            inside = audio.grid.clicks[0] - 1 < nt.start < audio.grid.clicks[-1] + 1
            nt.timing_ms = frac * audio.grid.period * 1000 if inside else None
            nt.rep = 0

    res.reps = _rep_stats(notes, res.events)
    res.report = build_report(res, a4)
    return res


def _rep_stats(notes, events):
    by = defaultdict(list)
    for n in notes:
        by[n.rep or 0].append(n)
    out = []
    for r in sorted(by):
        ns = by[r]
        ok = [n for n in ns if n.status == "ok"]
        tm = [n.timing_ms for n in ok if n.timing_ms is not None]
        out.append(dict(
            rep=r + 1, start=ns[0].start, end=ns[-1].end, n=len(ns),
            abs_cents=float(np.mean([abs(n.cents) for n in ok])) if ok else None,
            timing_mean=float(np.mean(tm)) if tm else None,
            timing_sd=float(np.std(tm)) if tm else None,
            errors=sum(1 for e in events if e.rep == r and e.kind in ("wrong", "missed", "extra")),
        ))
    return out


def build_report(res: Result, a4) -> str:
    a, sc, notes = res.audio, res.score, res.audio.notes
    ok = [n for n in notes if n.status == "ok"]
    L = []
    L.append(f"SESSION: {fmt_t(a.duration)} long, metronome {a.grid.bpm:.0f} BPM "
             f"({'detected' if a.grid.detected else 'given, clicks not found'}), A4={a4:g} Hz")
    if sc:
        L.append(f"EXERCISE: \"{sc.title}\", key {sc.key}, meter {sc.meter}, "
                 f"{len(sc.notes)} notes per pass: "
                 + " ".join(n.name for n in sc.notes[:48])
                 + (" ..." if len(sc.notes) > 48 else ""))
        L.append(f"PASSES through the exercise: {len(res.reps)}")
    else:
        L.append("EXERCISE: no score given; targets are the nearest semitone")

    if not ok:
        L.append("No stable notes detected.")
        return "\n".join(L)

    c = np.array([n.cents for n in ok])
    L.append("")
    L.append(f"INTONATION ({len(ok)} correct notes; + = sharp, - = flat, 100 cents = 1 semitone):")
    L.append(f"  median |error| {np.median(np.abs(c)):.0f}c; within 10c: {np.mean(np.abs(c) <= 10):.0%}; "
             f"off by >25c: {np.mean(np.abs(c) > 25):.0%}")
    by = defaultdict(list)
    for n in ok:
        by[n.target].append(n)
    L.append("  per pitch (n, average, spread):")
    for t in sorted(by):
        cs = np.array([n.cents for n in by[t]])
        mean, sd = cs.mean(), cs.std()
        tag = ""
        if consistent_error(cs):
            tag = "  <- consistently " + ("SHARP" if mean > 0 else "FLAT")
        elif sd >= 15:
            tag = "  <- inconsistent"
        L.append(f"    {note_name(t):4s} n={len(cs):3d} avg {mean:+4.0f}c spread {sd:3.0f}c{tag}")
    opens = [(s, by[m]) for m, s in OPEN_STRINGS.items() if m in by]
    if opens:
        L.append("  open-string pitches (if played open, this is the instrument's tuning, not the fingers):")
        L.append("    " + ", ".join(f"{s} string {np.mean([n.cents for n in ns]):+.0f}c" for s, ns in opens))
    wob = np.median([n.stability for n in ok])
    L.append(f"  pitch steadiness inside notes: median wobble {wob:.0f}c "
             f"({'steady' if wob < 8 else 'some wobble/vibrato' if wob < 20 else 'unsteady'})")

    tm = [(n, n.timing_ms) for n in ok if n.timing_ms is not None]
    if tm:
        arr = np.array([x for _, x in tm])
        L.append("")
        L.append("TIMING vs metronome (+ = late, - = early; +-20ms is hard to hear):")
        L.append(f"  average {arr.mean():+.0f}ms, spread {arr.std():.0f}ms, "
                 f"notes more than 50ms off: {np.mean(np.abs(arr) > 50):.0%}")
        on = [x for n, x in tm if sc and n.index_in_score is not None
              and sc.notes[n.index_in_score].onset % 1.0 == 0]
        off = [x for n, x in tm if sc and n.index_in_score is not None
               and sc.notes[n.index_in_score].onset % 1.0 != 0]
        if on and off:
            L.append(f"  on the click: {np.mean(on):+.0f}ms; between clicks: {np.mean(off):+.0f}ms")

    if sc:
        L.append("")
        L.append("PASS BY PASS:")
        for r in res.reps:
            ac = f"{r['abs_cents']:.0f}c" if r["abs_cents"] is not None else "-"
            tmean = f"{r['timing_mean']:+.0f}ms" if r["timing_mean"] is not None else "-"
            tsd = f"{r['timing_sd']:.0f}ms" if r["timing_sd"] is not None else "-"
            L.append(f"  pass {r['rep']:2d} [{fmt_t(r['start'])}-{fmt_t(r['end'])}]: "
                     f"|pitch err| {ac}, timing {tmean} (spread {tsd}), note errors {r['errors']}")

    if res.events:
        L.append("")
        L.append("NOTE ERRORS AND RESTARTS:")
        for e in res.events[:30]:
            L.append(f"  t={e.t:.1f}s ({fmt_t(e.t)}) pass {(e.rep or 0) + 1}: {e.text}")
        if len(res.events) > 30:
            L.append(f"  ... {len(res.events) - 30} more")

    worst = sorted(ok, key=lambda n: -abs(n.cents))[:6]
    worst = [n for n in worst if abs(n.cents) >= 15]
    if worst:
        L.append("")
        L.append("WORST INTONATION MOMENTS:")
        for n in worst:
            L.append(f"  t={n.start:.1f}s ({fmt_t(n.start)}) pass {(n.rep or 0) + 1}: "
                     f"{note_name(n.target)} {n.cents:+.0f}c")
    late = sorted([x for x in tm if abs(x[1]) >= 40], key=lambda x: -abs(x[1]))[:5] if tm else []
    if late:
        L.append("WORST TIMING MOMENTS:")
        for n, x in late:
            L.append(f"  t={n.start:.1f}s ({fmt_t(n.start)}) pass {(n.rep or 0) + 1}: "
                     f"{note_name(n.target)} {x:+.0f}ms")
    return "\n".join(L)
