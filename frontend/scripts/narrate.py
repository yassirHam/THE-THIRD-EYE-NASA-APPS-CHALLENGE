"""Generate the intro narration with Kokoro-82M (Apache-2.0), a local text-to-speech model.

One MP3 per subtitle line goes to public/audio/intro/, and src/story/narration.json records
each line's length so the intro timeline can wait for the voice before moving on.

Run with the private environment (not part of the site build):
  %LOCALAPPDATA%\\the-third-eye-tts\\Scripts\\python.exe scripts/narrate.py [--voice am_michael] [--speed 0.92]

The spoken text matches the on-screen subtitles word for word. Only pronunciation is
spelled out: numbers as words, and phonemes for MODIS, VIIRS and Suomi.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "audio" / "intro"
MANIFEST = ROOT / "src" / "story" / "narration.json"
RATE = 24000

MODIS = "[MODIS](/mˈOdɪs/)"
VIIRS = "[VIIRS](/vˈɪɹz/)"
SUOMI = "[Suomi](/sˈuːəmi/)"

# key -> spoken text. Keys match data-k in src/story/Intro.tsx.
LINES = {
    "p1": "Hold a finger in front of your face.",
    "p2": "Close one eye, then the other.",
    "p3": "It jumps. Nothing moved. Only the place you looked from.",
    "p4": "That shift is parallax.",
    "l1": "Close your left eye.",
    "l2": f"This is {MODIS}, on NASA's Aqua satellite. It has watched Earth since two thousand and two.",
    "l3": "It sees in squares about a kilometre wide. Small fires can slip through.",
    "r1": "Now close your right eye.",
    "r2": f"This is {VIIRS}, on {SUOMI} N P P. It watched from twenty twelve until November twenty twenty-six.",
    "r3": "Its squares are about three hundred and seventy-five metres wide. It often catches small fires the first eye missed.",
    "b1": "Open both eyes and join their records.",
    "b2": "The fire history jumps in twenty twelve.",
    "b3": "Part of that jump is not fire. It is the change of eye.",
    "t1": "Now look from a third place.",
    "t2": "From here you can tell which differences belong to the fire, and which belong to the eye.",
    "t3": "And when you cannot tell, it says so.",
    "title": "[The Third Eye](/ˈæftəɹˌɪmɪʤ/).",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="am_michael", help="Kokoro voice id, e.g. am_michael, am_fenrir, bm_george")
    ap.add_argument("--speed", type=float, default=0.92)
    ap.add_argument("--only", nargs="*", help="regenerate only these keys")
    args = ap.parse_args()

    lang = "b" if args.voice.startswith("b") else "a"
    pipe = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    OUT.mkdir(parents=True, exist_ok=True)
    old = json.loads(MANIFEST.read_text("utf-8")) if MANIFEST.exists() else {}
    lengths = dict(old.get("lines", {}))

    for key, text in LINES.items():
        if args.only and key not in args.only:
            continue
        parts = [np.asarray(a, dtype=np.float32) for _, _, a in pipe(text, voice=args.voice, speed=args.speed)]
        if not parts:
            raise SystemExit(f"no audio for {key}")
        audio = np.concatenate(parts)
        # trim near-silence at both ends, then pad 60 ms so lines do not clip
        loud = np.where(np.abs(audio) > 0.01)[0]
        if len(loud):
            audio = audio[max(0, loud[0] - 600): loud[-1] + 1200]
        audio = np.concatenate([np.zeros(int(RATE * 0.06), np.float32), audio])
        # same loudness for every line: peak at about -1 dBFS
        peak = float(np.abs(audio).max())
        if peak > 0:
            audio = audio * (0.89 / peak)
        sf.write(OUT / f"{key}.mp3", audio, RATE, format="MP3")
        lengths[key] = round(len(audio) / RATE, 3)
        print(f"{key:6s} {lengths[key]:5.2f}s  {text}")

    MANIFEST.write_text(json.dumps({
        "voice": args.voice,
        "speed": args.speed,
        "model": "Kokoro-82M (Apache-2.0), generated locally",
        "lines": lengths,
    }, indent=2) + "\n", "utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
