"""Synthesize a fake practice take (violin-ish tone + metronome) with known mistakes.

Writes test_data/practice.wav, test_data/score.abc and test_data/truth.json.
Mistakes baked in:
  - every C#5 is played ~22 cents sharp (classic high 2nd finger)
  - repetition 3, note 4: D#5 instead of D5 (wrong note)
  - repetition 4, note 6: skipped (missed note)
  - repetitions 5-6 drift progressively late (dragging)
"""
import json
import os
import sys

import numpy as np
import soundfile as sf

SR = 22050
BPM = 80
REPS = 6
ABC = """X:1
T:Test exercise (A string)
M:4/4
L:1/8
K:A
A B c d e d c B | A B c d e d c B |
"""
# A4 B4 C#5 D5 E5 D5 C#5 B4, twice per repetition, eighth notes
PATTERN = [69, 71, 73, 74, 76, 74, 73, 71] * 2


def tone(midi, dur, cents=0.0, rng=None):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 440 * 2 ** ((midi - 69 + cents / 100) / 12)
    vib_depth = np.clip((t - 0.12) / 0.15, 0, 1) * 12  # cents, vibrato fades in
    inst_f = f * 2 ** (vib_depth * np.sin(2 * np.pi * 5.5 * t) / 1200)
    phase = 2 * np.pi * np.cumsum(inst_f) / SR
    y = sum((1 / k) * np.sin(k * phase) for k in range(1, 16) if k * f < 9000)
    env = np.minimum(1, t / 0.03) * np.minimum(1, (dur - t) / 0.04)
    y = y * env
    y += 0.01 * rng.standard_normal(n) * env  # bow noise
    return y


def click(rng):
    n = int(0.02 * SR)
    t = np.arange(n) / SR
    return (0.6 * np.sin(2 * np.pi * 2500 * t) + 0.4 * rng.standard_normal(n)) * np.exp(-t / 0.003)


def main(out_dir):
    rng = np.random.default_rng(1)
    beat = 60 / BPM
    eighth = beat / 2
    lead_in = 4  # count-in clicks
    total_beats = lead_in + REPS * len(PATTERN) / 2 + 4
    y = np.zeros(int(total_beats * beat * SR) + SR)

    for k in range(int(total_beats)):
        i = int(k * beat * SR)
        c = click(rng)
        y[i:i + len(c)] += 0.8 * c

    truth = []
    for rep in range(REPS):
        for j, midi in enumerate(PATTERN):
            if rep == 3 and j == 5:
                continue  # missed note
            played = 75 if (rep == 2 and j == 3) else midi
            cents = rng.normal(0, 4) + (22 if played == 73 else 0)
            late = 0.0
            if rep >= 4:
                late = 0.015 * (rep - 3) + 0.004 * j
            t0 = (lead_in + (rep * len(PATTERN) + j) / 2) * beat + late + rng.normal(0, 0.006)
            seg = tone(played, eighth * 0.95, cents, rng) * 0.35
            i = int(t0 * SR)
            y[i:i + len(seg)] += seg
            truth.append(dict(rep=rep, idx=j, t=round(t0, 3), midi=played,
                              expected=midi, cents=round(cents, 1), late_ms=round(late * 1000)))

    y += 0.003 * rng.standard_normal(len(y))
    y /= np.max(np.abs(y))
    os.makedirs(out_dir, exist_ok=True)
    sf.write(os.path.join(out_dir, "practice.wav"), y, SR)
    with open(os.path.join(out_dir, "score.abc"), "w") as f:
        f.write(ABC)
    with open(os.path.join(out_dir, "truth.json"), "w") as f:
        json.dump(truth, f, indent=1)
    print(f"wrote {out_dir}/practice.wav ({len(y) / SR:.1f}s), score.abc, truth.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "test_data")
