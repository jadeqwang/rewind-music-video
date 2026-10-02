"""Mouth-openness track for re-mouthing the singer: video/data/mouth.json {fps, open:[0..1]} over the whole song.

The singer's lips are redrawn from this track (positioned by the plate's face landmarks), so the drawn mouth
is in sync with the vocal by construction, whatever the generated take did.
  open(t) = vocal-stem loudness (attack 20 ms, release 90 ms), mapped −44 dB → 0 … −16 dB → 1,
            opened ~40 ms ahead of the sound (mouths move before voices),
            forced shut around bilabial onsets (b, m, p) from the word timings.
"""
import json, pathlib, subprocess
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
FPS = 48
SR = 16000


def main():
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "/tmp/work/audio/vocals.wav", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    y = np.frombuffer(raw, dtype=np.float32)
    hop = SR // FPS
    n = len(y) // hop
    rms = np.array([np.sqrt(np.mean(y[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(rms + 1e-9)
    tgt = np.clip((db + 44) / 28, 0, 1)
    # asymmetric smoothing: fast attack, slower release
    env = np.zeros_like(tgt); a_up, a_dn = 1 - np.exp(-1 / (FPS * .02)), 1 - np.exp(-1 / (FPS * .09))
    for i in range(1, n):
        a = a_up if tgt[i] > env[i - 1] else a_dn
        env[i] = env[i - 1] + a * (tgt[i] - env[i - 1])
    env = np.roll(env, -2)                       # lead the sound by ~40 ms
    env = np.power(env, .8)
    # bilabial closures
    tm = json.loads((ROOT / "video" / "data" / "timing.json").read_text())
    for l in tm["lines"]:
        for t, w in l["words"]:
            ww = w.lower().strip(",.…'()—")
            if ww[:1] in "bmp":
                for i in range(int((t - .07) * FPS), int((t + .05) * FPS) + 1):
                    if 0 <= i < n:
                        d = abs(i / FPS - (t - .01)) / .06
                        env[i] *= min(1, d ** 2)
    out = {"fps": FPS, "open": [round(float(v), 3) for v in env]}
    (ROOT / "video" / "data" / "mouth.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"mouth track: {n} samples at {FPS} fps, mean open {env.mean():.2f}")


if __name__ == "__main__":
    main()
