"""Audio -> metronome grid + pitch track + note events.

The recording is split with harmonic/percussive separation: the percussive
part carries the metronome clicks, the harmonic part carries the violin.
"""
import os
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

import imageio_ffmpeg
import librosa
import numpy as np
from scipy.ndimage import median_filter

SR = 22050
HOP = 256  # ~11.6 ms per pitch frame
# the centred STFT sees a click's flux peak ~14 ms before the click itself
CLICK_LATENCY = 0.014


@dataclass
class Grid:
    bpm: float
    period: float          # seconds per click
    t0: float              # time of first click
    clicks: np.ndarray     # fitted click times
    detected: bool         # False when bpm was forced and no clicks were found

    def beat_pos(self, t):
        """Continuous beat index for time t (0 = first click)."""
        return (np.asarray(t) - self.t0) / self.period


@dataclass
class Note:
    start: float
    end: float
    midi: float            # median played pitch (fractional MIDI)
    stability: float       # std of pitch inside the note, cents
    loudness: float        # dB
    # filled in later by analysis
    target: Optional[int] = None
    cents: float = 0.0
    timing_ms: Optional[float] = None
    status: str = "ok"     # ok | wrong | extra
    expected: Optional[int] = None
    rep: Optional[int] = None
    index_in_score: Optional[int] = None

    @property
    def dur(self):
        return self.end - self.start


@dataclass
class PitchTrack:
    times: np.ndarray
    midi: np.ndarray       # NaN where unvoiced
    rms_db: np.ndarray


@dataclass
class AudioAnalysis:
    y: np.ndarray
    sr: int
    duration: float
    grid: Grid
    track: PitchTrack
    notes: List[Note] = field(default_factory=list)


def load(path):
    """Any format ffmpeg reads (m4a from a phone, mp4 video, ...), decoded with the
    ffmpeg bundled in imageio-ffmpeg so no system install is needed."""
    if os.path.splitext(path)[1].lower() in (".wav", ".flac", ".ogg"):
        y, sr = librosa.load(path, sr=SR, mono=True)
    else:
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", path,
               "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
        y = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout,
                          dtype=np.float32).copy()
        sr = SR
    peak = np.max(np.abs(y)) or 1.0
    return y / peak, sr


# ---------------------------------------------------------------- metronome

def _click_envelope(y, sr, n_bands=40, top=3):
    """Onset envelope of the metronome.

    Clicks are broadband, app beeps are pure tones, and both overlap the violin.
    What sets the metronome apart is that it is the one sound that repeats
    identically: so split the spectrum into bands, measure how periodic each
    band's onsets are, and keep the most periodic bands."""
    fps = sr / 128.0
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=128))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    edges = np.geomspace(300, min(10000, sr / 2 - 1), n_bands + 1)
    lo, hi = int(fps * 60 / 240), int(fps * 60 / 40)
    envs, scores = [], []
    for b in range(n_bands):
        sel = (freqs >= edges[b]) & (freqs < edges[b + 1])
        if not sel.any():
            continue
        band = np.log1p(100 * S[sel])
        f = np.maximum(0, np.diff(band, axis=1, prepend=band[:, :1])).sum(axis=0)
        f = np.maximum(0, f - median_filter(f, size=31))
        f /= f.max() or 1.0
        ac = librosa.autocorrelate(f - f.mean(), max_size=hi + 1)
        scores.append(ac[lo:hi].max() / (ac[0] or 1.0))
        envs.append(f)
    best = np.argsort(scores)[-top:]
    env = np.sum([envs[i] for i in best], axis=0)
    return env / (env.max() or 1.0), fps


def detect_metronome(y, sr, bpm_hint=None) -> Grid:
    env, fps = _click_envelope(y, sr)
    duration = len(y) / sr

    if bpm_hint:
        period = 60.0 / bpm_hint
    else:
        # autocorrelation over 40..240 BPM; prefer the shortest strong period
        ac = librosa.autocorrelate(env, max_size=int(fps * 1.6))
        ac /= ac[0] or 1.0
        lo, hi = int(fps * 60 / 240), int(fps * 60 / 40)
        seg = ac[lo:hi]
        peaks = [i for i in range(1, len(seg) - 1)
                 if seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1]]
        if not peaks:
            raise RuntimeError("Could not find a metronome. Pass --bpm.")
        best = max(seg[i] for i in peaks)
        lag = min(i for i in peaks if seg[i] >= 0.7 * best) + lo
        period = lag / fps

    # phase: pick the offset whose comb collects the most click energy
    n_lag = int(round(period * fps))
    comb = np.array([env[o::n_lag].sum() / max(1, len(env[o::n_lag]))
                     for o in range(n_lag)]) if n_lag > 0 else np.zeros(1)
    phase = int(np.argmax(comb)) / fps

    # snap each grid point to the local envelope peak, then fit a straight line
    ks, ts = [], []
    k = 0
    win = int(0.035 * fps)
    thresh = 0.25 * np.percentile(env[env > 0], 99) if np.any(env > 0) else 1
    t = phase
    while t < duration:
        c = int(t * fps)
        a, b = max(0, c - win), min(len(env), c + win + 1)
        if b > a:
            j = a + int(np.argmax(env[a:b]))
            if env[j] > thresh:
                ks.append(k)
                ts.append(j / fps)
        k += 1
        t = phase + k * period

    detected = len(ks) >= 4
    if detected:
        ks, ts = np.array(ks), np.array(ts)
        for _ in range(3):  # robust refit
            A = np.vstack([ks, np.ones_like(ks)]).T
            (p, o), *_ = np.linalg.lstsq(A, ts, rcond=None)
            res = np.abs(ts - (p * ks + o))
            keep = res < max(0.02, 3 * np.median(res))
            ks, ts = ks[keep], ts[keep]
        period, t0 = float(p), float(o)
        # extend grid over the span where clicks were heard
        k_first, k_last = ks.min(), ks.max()
        clicks = t0 + period * np.arange(k_first, k_last + 1)
        t0 = float(clicks[0])
    else:
        t0 = phase
        clicks = np.arange(t0, duration, period)

    return Grid(bpm=60.0 / period, period=period, t0=t0 + CLICK_LATENCY,
                clicks=clicks + CLICK_LATENCY, detected=detected)


# ---------------------------------------------------------------- pitch

def pitch_track(y_harm, sr) -> PitchTrack:
    f0, voiced, prob = librosa.pyin(
        y_harm, fmin=180, fmax=2800, sr=sr, frame_length=2048, hop_length=HOP)
    midi = librosa.hz_to_midi(f0)
    midi[~(voiced & (prob > 0.3))] = np.nan
    rms = librosa.feature.rms(y=y_harm, frame_length=2048, hop_length=HOP)[0]
    n = min(len(midi), len(rms))
    times = librosa.frames_to_time(np.arange(n), sr=sr, hop_length=HOP)
    rms_db = librosa.amplitude_to_db(rms[:n], ref=np.max)
    return PitchTrack(times=times, midi=midi[:n], rms_db=rms_db)


def _split_on_dips(a, b, rms_db, min_len):
    """Split frame range [a, b) at loudness dips (bow changes on repeated notes)."""
    seg = median_filter(rms_db[a:b], size=3)
    cuts = []
    i = min_len
    while i < len(seg) - min_len:
        left = seg[max(0, i - 12):i].max()
        right = seg[i + 1:i + 13].max()
        if seg[i] == seg[i - 2:i + 3].min() and min(left, right) - seg[i] > 6:
            cuts.append(a + i)
            i += min_len
        else:
            i += 1
    edges = [a] + cuts + [b]
    return list(zip(edges[:-1], edges[1:]))


def segment_notes(track: PitchTrack, min_dur=0.06) -> List[Note]:
    midi = track.midi.copy()
    fps = 1.0 / (track.times[1] - track.times[0])
    min_len = max(2, int(min_dur * fps))
    sm = midi.copy()
    v = ~np.isnan(midi)
    sm[v] = median_filter(midi[v], size=5)

    # pass 1: runs of voiced frames with a stable semitone
    runs = []
    start, ref, off = None, None, 0
    for i in range(len(sm)):
        if np.isnan(sm[i]):
            if start is not None:
                runs.append((start, i))
                start = None
            continue
        if start is None:
            start, ref, off = i, sm[i], 0
            continue
        if abs(sm[i] - ref) > 0.6:
            off += 1
            if off >= 3:            # pitch really moved: new note
                runs.append((start, i - off + 1))
                start, ref, off = i - off + 1, sm[i], 0
        else:
            off = 0
            ref = np.median(sm[start:i + 1])

    if start is not None:
        runs.append((start, len(sm)))

    notes = []
    for a, b in runs:
        if b - a < min_len:
            continue
        for s, e in _split_on_dips(a, b, track.rms_db, min_len):
            if e - s < min_len:
                continue
            # skip attack and release: use the middle 60%
            m0 = s + int(0.2 * (e - s))
            m1 = max(m0 + 1, e - int(0.2 * (e - s)))
            core = sm[m0:m1]
            core = core[~np.isnan(core)]
            if len(core) == 0:
                continue
            med = float(np.median(core))
            notes.append(Note(
                start=float(track.times[s]),
                end=float(track.times[min(e, len(track.times) - 1)]),
                midi=med,
                stability=float(np.std(core - med) * 100),
                loudness=float(np.mean(track.rms_db[s:e])),
            ))
    return _merge_octave_slips(notes)


def _merge_octave_slips(notes, max_dur=0.3, max_gap=0.05):
    """pYIN sometimes locks onto the subharmonic for the first moments of a note
    (bow change, string crossing). A short fragment exactly an octave away from
    the note it touches is that note, not a separate one."""
    out = []
    for i, n in enumerate(notes):
        nxt = notes[i + 1] if i + 1 < len(notes) else None
        if (nxt and n.dur < max_dur and nxt.start - n.end < max_gap
                and abs(round(n.midi) - round(nxt.midi)) in (12, 24)):
            nxt.start = n.start
            continue
        prv = out[-1] if out else None
        if (prv and n.dur < max_dur and n.start - prv.end < max_gap
                and abs(round(n.midi) - round(prv.midi)) in (12, 24)):
            prv.end = n.end
            continue
        out.append(n)
    return out


def refine_pitch(notes, y_harm, sr):
    """pYIN works in 10-cent bins; re-measure each note's core with YIN,
    which interpolates continuously, searching only near the coarse pitch."""
    for n in notes:
        a = int((n.start + 0.2 * n.dur) * sr)
        b = int((n.end - 0.2 * n.dur) * sr)
        if b - a < 2048:
            continue
        f = librosa.midi_to_hz(n.midi)
        f0 = librosa.yin(y_harm[a:b], fmin=f * 0.94, fmax=f * 1.06, sr=sr,
                         frame_length=2048, hop_length=HOP)
        m = librosa.hz_to_midi(f0)
        m = m[np.abs(m - n.midi) < 0.5]
        if len(m):
            med = float(np.median(m))
            n.midi = med
            n.stability = float(np.std(m - med) * 100)


def analyze(path, bpm_hint=None) -> AudioAnalysis:
    y, sr = load(path)
    y_harm = librosa.effects.harmonic(y, margin=3.0)
    grid = detect_metronome(y, sr, bpm_hint)
    track = pitch_track(y_harm, sr)
    notes = segment_notes(track)
    refine_pitch(notes, y_harm, sr)
    return AudioAnalysis(y=y, sr=sr, duration=len(y) / sr, grid=grid,
                         track=track, notes=notes)
