"""Compose the intro's background music: a slow ambient loop, synthesized from scratch.

Every sound is made here with numpy (no samples, no recordings, no model), so the music has
no licence questions. Mood: the old observatory at night. A low D pedal like the hum of a
large instrument, a warm pad moving slowly through D Dorian, and sparse glass-bell notes like
a brass astrolabe being turned. Everything is rendered on a circle, so the file loops with
no seam.

Output: public/audio/music/intro-bed.mp3 and src/story/music.json (the exact loop length).
Run with the private environment (not part of the site build):
  %LOCALAPPDATA%\\the-third-eye-tts\\Scripts\\python.exe scripts/compose.py
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "audio" / "music" / "intro-bed.mp3"
MANIFEST = ROOT / "src" / "story" / "music.json"

SR = 44100
BAR = 8.0  # seconds per chord
# D Dorian: Dm9, Bbmaj7, Fadd9, Csus2, Dm7/A, Gm9, Bbmaj9, Asus4 (which leans back to Dm)
CHORDS = [
    ["D3", "A3", "C4", "E4", "F4"],
    ["Bb2", "F3", "A3", "D4"],
    ["F2", "C3", "G3", "A3"],
    ["C3", "G3", "D4", "E4"],
    ["A2", "D3", "F3", "C4"],
    ["G2", "D3", "F3", "A3", "Bb3"],
    ["Bb2", "F3", "A3", "C4", "D4"],
    ["A2", "E3", "A3", "D4"],
]
LOOP = BAR * len(CHORDS)
N = int(SR * LOOP)
rng = np.random.default_rng(7)

PC = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "Gb": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}


def hz(note: str) -> float:
    name, octave = note[:-1], int(note[-1])
    midi = 12 * (octave + 1) + PC[name]
    return 440.0 * 2 ** ((midi - 69) / 12)


def pan2(sig: np.ndarray, p: float) -> np.ndarray:
    """Equal-power pan, p from -1 (left) to 1 (right)."""
    a = (p + 1) * np.pi / 4
    return np.stack([sig * np.cos(a), sig * np.sin(a)])


def add(buf: np.ndarray, start: float, sig: np.ndarray) -> None:
    """Add a stereo event to the loop, wrapping past the end back to the start."""
    pos, off = int(start * SR) % N, 0
    while off < sig.shape[1]:
        take = min(N - pos, sig.shape[1] - off)
        buf[:, pos:pos + take] += sig[:, off:off + take]
        off += take
        pos = 0


def ease(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0, 1)
    return 0.5 - 0.5 * np.cos(np.pi * x)


def pad(buf: np.ndarray) -> None:
    """Each chord swells in over 3.5 s and fades out over 6 s, overlapping the next."""
    attack, release = 3.5, 6.0
    n = int(SR * (BAR + release))
    t = np.arange(n) / SR
    env = ease(t / attack) * (1 - ease((t - BAR) / release))
    for i, chord in enumerate(CHORDS):
        for j, note in enumerate(chord):
            f0 = hz(note)
            out = np.zeros((2, n))
            # three slightly detuned voices spread across the stereo field: slow, soft beating
            for cents, p in ((-6, -0.55), (0, 0.0), (6, 0.55)):
                f = f0 * 2 ** (cents / 1200)
                tone = np.zeros(n)
                for k in range(1, 7):
                    if f * k > 4200:
                        break
                    tone += np.sin(2 * np.pi * f * k * t + rng.uniform(0, 2 * np.pi)) / k ** 1.8
                out += pan2(tone, p)
            # lower notes carry more of the weight, upper ones stay quiet
            weight = 1.0 if j == 0 else 0.62 / (1 + 0.12 * j)
            add(buf, i * BAR, out * env * weight)


def drone(buf: np.ndarray) -> None:
    """D pedal under everything. Frequencies are rounded so each wave fits the loop exactly."""
    t = np.arange(N) / SR

    def fit(f: float) -> float:
        return round(f * LOOP) / LOOP

    sig = (np.sin(2 * np.pi * fit(hz("D2")) * t)
           + 0.32 * np.sin(2 * np.pi * fit(hz("D3")) * t + 0.7)
           + 0.10 * np.sin(2 * np.pi * fit(hz("A3")) * t + 1.9))
    breath = 0.82 + 0.18 * np.sin(2 * np.pi * t / 16.0)  # 16 s divides the 64 s loop
    buf += np.stack([sig * breath, sig * breath * 0.97])


def bell(f: float, vel: float) -> np.ndarray:
    """A glass bell: three inharmonic partials, the upper ones dying first."""
    n = int(SR * 6.0)
    t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * f * t) * np.exp(-t / 2.4)
           + 0.30 * np.sin(2 * np.pi * f * 2.756 * t) * np.exp(-t / 0.8)
           + 0.10 * np.sin(2 * np.pi * f * 5.404 * t) * np.exp(-t / 0.3))
    sig *= np.minimum(1, t / 0.006) * vel
    return sig


def bells(buf: np.ndarray) -> None:
    for i, chord in enumerate(CHORDS):
        tones = [hz(n) * 4 for n in chord[1:]]  # chord tones, two octaves up
        times = sorted(rng.uniform(0.6, BAR - 1.2, size=rng.integers(1, 3)))
        for s in times:
            f = float(rng.choice(tones))
            add(buf, i * BAR + s, pan2(bell(f, rng.uniform(0.45, 1.0)), rng.uniform(-0.7, 0.7)))
            # a quiet answer a fifth above or an octave below, sometimes
            if rng.random() < 0.35:
                g = f * (1.5 if rng.random() < 0.5 else 0.5)
                add(buf, i * BAR + s + rng.uniform(0.9, 1.6), pan2(bell(g, 0.35), rng.uniform(-0.7, 0.7)))


def air(buf: np.ndarray) -> None:
    """Very quiet band-limited noise: night air. Shaped in the frequency domain, so it loops."""
    freqs = np.fft.rfftfreq(N, 1 / SR)
    shape = 1 / (1 + ((freqs - 900) / 700) ** 2)
    out = []
    for _ in range(2):
        spec = np.fft.rfft(rng.standard_normal(N)) * shape
        out.append(np.fft.irfft(spec, N))
    sig = np.stack(out)
    t = np.arange(N) / SR
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / 32.0)
    buf += sig / np.abs(sig).max() * swell * 0.05


def reverb(x: np.ndarray, seconds: float = 4.5, decay: float = 0.7) -> np.ndarray:
    """Circular convolution with a dark, decaying noise tail, so the loop wraps cleanly."""
    n = int(SR * seconds)
    t = np.arange(n) / SR
    freqs = np.fft.rfftfreq(N, 1 / SR)
    dark = 1 / (1 + (freqs / 2600) ** 2)
    wet = []
    for ch in range(2):
        ir = np.zeros(N)
        ir[int(SR * 0.025):int(SR * 0.025) + n] = rng.standard_normal(n) * np.exp(-t / decay)
        y = np.fft.irfft(np.fft.rfft(x[ch]) * np.fft.rfft(ir) * dark, N)
        wet.append(y)
    wet = np.stack(wet)
    return wet / np.abs(wet).max()


def main() -> None:
    stems = {}
    for name, fn in (("pad", pad), ("drone", drone), ("bells", bells), ("air", air)):
        b = np.zeros((2, N))
        fn(b)
        stems[name] = b / max(np.abs(b).max(), 1e-9)
    dry = 0.55 * stems["pad"] + 0.30 * stems["drone"] + 0.26 * stems["bells"] + 0.05 * stems["air"]
    mix = 0.62 * dry + 0.48 * reverb(dry)
    mix *= 0.7 / np.abs(mix).max()  # peak about -3 dBFS; the site plays it well under the voice

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sf.write(OUT, mix.T.astype(np.float32), SR, format="MP3")
    rms = float(np.sqrt(np.mean(mix ** 2)))
    MANIFEST.write_text(json.dumps({
        "file": "/audio/music/intro-bed.mp3",
        "loopSeconds": LOOP,
        "sampleRate": SR,
        "made": "synthesized by scripts/compose.py (numpy, no samples)",
    }, indent=2) + "\n", "utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  {LOOP:.0f}s loop  rms {20 * np.log10(rms):.1f} dBFS  "
          f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
