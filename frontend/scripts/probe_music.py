"""Debug helper: decode the music file and print loudness, spectrum and seam figures."""
import numpy as np
import soundfile as sf

x, sr = sf.read("public/audio/music/intro-bed.mp3")
print("shape", x.shape, "sr", sr, "secs", round(len(x) / sr, 3))
nz = np.where(np.abs(x).max(1) > 1e-4)[0]
print("first nonsilent sample", nz[0], "last", nz[-1], "of", len(x))
m = x.mean(1)
for a, b in [(0, 8), (8, 16), (24, 32), (56, 64)]:
    seg = m[int(a * sr):int(b * sr)]
    print(f"{a:2d}-{b:2d}s rms {20 * np.log10(np.sqrt((seg ** 2).mean())):.1f} dB peak {np.abs(seg).max():.2f}")
spec = np.abs(np.fft.rfft(m[:sr * 16])) ** 2
f = np.fft.rfftfreq(sr * 16, 1 / sr)
for lo, hi in [(20, 120), (120, 500), (500, 2000), (2000, 6000), (6000, 16000)]:
    print(f"band {lo}-{hi} Hz share {spec[(f >= lo) & (f < hi)].sum() / spec.sum() * 100:.1f}%")
# seam: compare the step across the loop point with typical sample-to-sample steps
o = nz[0]
L = int(64 * sr)
if o + L <= len(x):
    step = np.abs(x[o + L - 1] - x[o]).max()
    typical = np.percentile(np.abs(np.diff(x[o:o + L], axis=0)).max(1), 99)
    print(f"seam step {step:.4f} vs 99th percentile step {typical:.4f}")
