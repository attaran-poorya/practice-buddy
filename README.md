# Violin practice coach

Practice recording (with metronome) + photo of the page → a video of your take with
every note's intonation and timing drawn on it, and a teacher-style coach commenting
at the important moments.

```
recording ─► metronome grid ─┐
          └► pitch track ─► notes ─┐
photo ─► vision LLM ─► ABC score ──┴► align ─► report.txt ─► small LLM ─► feedback.json
                                                       └──────────────────────┴─► video.mp4
```

The LLM never hears audio. It reads `report.txt`: per-pitch averages ("C#5: 24×,
+23¢, consistently sharp"), timing vs. the click, pass-by-pass trends, wrong/missed
notes and restarts. That's why a small free model is enough.

## Setup (once)

```bash
cd violin_coach
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env    # then paste a free key in .env
```

Free LLM options (pick one, `--llm`):

| provider | key | reads the photo? | notes |
|---|---|---|---|
| `gemini` (default) | free at aistudio.google.com/apikey | yes, best at notation | free tier has rate limits, plenty for this |
| `groq` | free at console.groq.com/keys | yes (Llama 4 Scout) | very fast |
| `custom` | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` in `.env` | if the model can | any OpenAI-compatible service |
| `ollama` | none, runs on this Mac | weakly (`qwen2.5vl:7b`) | install from ollama.com, `ollama pull qwen2.5:7b` |

## Use

```bash
# first time with a new exercise: read the photo
.venv/bin/python coach.py practice.m4a --photo sevcik.jpg --crop 0,0.18,1,0.32 --which "No. 4"
# the transcription is saved to out/practice/score.abc - check it, fix it, then reuse it:
.venv/bin/python coach.py practice2.m4a --score out/practice/score.abc
```

Output in `out/<name>/`: `<name>_coached.mp4`, `report.txt`, `feedback.json`, `score.abc`.

Flags: `--beat 0.5` if the metronome clicks eighths (1.5 for dotted quarters in 6/8),
`--bpm 72` if tempo detection is off, `--a4 442` for your tuning, `--no-llm` for
rule-based feedback only.

## Tips for the recording / photo

- Phone recording is fine (m4a, mp4, wav…). The metronome must be audible in the recording
  (a speaker, not earbuds). Clicks or beeps both work.
- **Crop the photo to the exercise you played.** A whole Ševčík page is too dense for
  any reader; one or two lines is reliable. `--crop` takes fractions of the image.
- Always glance at `score.abc` the first time; one wrong accidental makes every
  instance of that note look "wrong". You only fix it once per exercise.

## Known limits

- Single line only: double stops follow the top note.
- Timing is measured where the pitch becomes stable, so a slow, soft attack may read
  a little late. Compare passes with each other rather than trusting one absolute ms value.
- "In tune" is equal temperament at A4. Expressive intonation (high leading tones)
  will show as a few cents sharp, which is expected.

## Test without a violin

```bash
.venv/bin/python tools/make_test_practice.py      # synthetic take with planted mistakes
.venv/bin/python coach.py test_data/practice.wav --score test_data/score.abc --no-llm
```
