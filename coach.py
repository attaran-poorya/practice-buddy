#!/usr/bin/env python3
"""Violin practice coach: recording + sheet music photo -> annotated video.

  python coach.py practice.m4a --photo page.jpg
  python coach.py practice.m4a --score out/practice/score.abc   # after fixing the ABC
"""
import argparse
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vc import analysis, audio, feedback, score, video  # noqa: E402
from vc.llm import LLM, load_dotenv  # noqa: E402


def main():
    load_dotenv()  # before argparse, so LLM_PROVIDER in .env picks the default --llm
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording", help="audio (or video) of the practice, with the metronome audible")
    ap.add_argument("--photo", help="photo of the sheet music")
    ap.add_argument("--crop", help="crop the photo to the exercise: x0,y0,x1,y1 as fractions, e.g. 0,0.2,1,0.35")
    ap.add_argument("--which", help='which exercise on the page, e.g. "No. 3, first line"')
    ap.add_argument("--score", help="ABC file to use instead of reading the photo")
    ap.add_argument("--beat", type=float, default=1.0,
                    help="what one metronome click is, in quarter notes (0.5 = eighths, 1.5 = dotted quarter)")
    ap.add_argument("--bpm", type=float, help="metronome tempo, if auto-detection gets it wrong")
    ap.add_argument("--a4", type=float, default=440.0, help="tuning reference (default 440)")
    ap.add_argument("--llm", default=os.environ.get("LLM_PROVIDER", "gemini"),
                    choices=["gemini", "groq", "custom", "ollama"])
    ap.add_argument("--no-llm", action="store_true", help="rule-based feedback only")
    ap.add_argument("-o", "--out", help="output folder (default out/<recording name>)")
    args = ap.parse_args()

    name = os.path.splitext(os.path.basename(args.recording))[0]
    out = args.out or os.path.join("out", name)
    os.makedirs(out, exist_ok=True)
    t_start = time.time()
    llm = None if args.no_llm else LLM(args.llm)

    # 1. sheet music -> ABC
    sc = None
    abc_path = os.path.join(out, "score.abc")
    if args.score:
        sc = score.parse_abc(open(args.score).read(), args.beat)
    elif args.photo:
        if llm is None:
            sys.exit("Reading a photo needs a vision LLM; drop --no-llm or pass --score.")
        print(f"Reading sheet music with {llm.provider} ({llm.vision_model})...")
        crop = tuple(float(x) for x in args.crop.split(",")) if args.crop else None
        try:
            abc = score.transcribe_photo(llm, args.photo, crop, args.which)
            open(abc_path, "w").write(abc)
            sc = score.parse_abc(abc, args.beat)
        except Exception as e:
            print(f"  could not read the score ({str(e)[:200]})\n"
                  f"  continuing without a score: notes are judged against the nearest semitone.")
        else:
            print(f"  {len(sc.notes)} notes: {' '.join(n.name for n in sc.notes[:24])}"
                  f"{' ...' if len(sc.notes) > 24 else ''}")
            print(f"  saved to {abc_path} - if notes are wrong, fix it and re-run with --score {abc_path}")

    # 2. audio -> notes, metronome grid
    print("Analysing audio...")
    a = audio.analyze(args.recording, args.bpm)
    print(f"  {a.duration:.0f}s, metronome {a.grid.bpm:.1f} BPM"
          f"{'' if a.grid.detected else ' (clicks NOT found - pass --bpm)'}, {len(a.notes)} notes")

    # 3. align + condense
    res = analysis.analyze(a, sc, args.a4)
    open(os.path.join(out, "report.txt"), "w").write(res.report)

    # 4. feedback
    fb = None
    if llm:
        print(f"Asking {llm.provider} ({llm.model}) for feedback...")
        try:
            fb = feedback.llm_feedback(llm, res)
        except Exception as e:
            print(f"  LLM failed ({e}); using rule-based feedback.")
    if fb is None:
        fb = feedback.rule_feedback(res)
    json.dump(fb, open(os.path.join(out, "feedback.json"), "w"), indent=2)
    print(f"\n{fb['headline']}")
    for s in fb["summary"]:
        print(f"  - {s}")

    # 5. video
    print("\nRendering video...")
    photo = score.prepare_photo(args.photo, None, 900) if args.photo else None
    mp4 = os.path.join(out, f"{name}_coached.mp4")
    video.render(res, fb, args.recording, mp4, photo, args.beat)
    print(f"\nDone in {time.time() - t_start:.0f}s -> {mp4}")


if __name__ == "__main__":
    main()
