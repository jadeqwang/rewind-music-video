"""Lip-sync verification for singer plates.

For a plate generated with a song segment as reference audio (segment start `s0` in song time):
  1. mouth curve  : inner-lip opening per frame from the plate's face landmarks (video/plates/<id>/meta.json),
                    normalised by face height, blended with MediaPipe's jawOpen.
  2. vocal curve  : RMS envelope of the isolated vocal stem over the same window (song time s0 .. s0+dur).
  3. lag          : the shift (plate time = song time - s0 + lag) that maximises the normalised
                    cross-correlation of the two curves' derivatives-smoothed versions.
  4. audio check  : if the plate mp4 has an audio track (generate_audio), cross-correlate its envelope with
                    the reference segment's envelope → how Seedance placed the song inside the clip.
Writes media/plates/<id>/sync.json and a plot sync.png.

    python3 tools/lipsync.py jade_hook1:30.9 jade_brk:110.4 ...
"""
import sys, json, pathlib, subprocess
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOCALS = "/tmp/work/audio/vocals.wav"
SONG = str(ROOT / "Orbital_Sunrise.mp3")
FPS = 24


def load_audio(path, sr=16000, ss=None, dur=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def envelope(y, sr=16000, fps=FPS):
    hop = sr // fps
    n = len(y) // hop
    e = np.array([np.sqrt(np.mean(y[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    e = 20 * np.log10(e + 1e-6)
    e = np.clip((e - np.percentile(e, 20)) / (np.percentile(e, 98) - np.percentile(e, 20) + 1e-6), 0, 1)
    return e


def mouth_curve(pid):
    meta = json.loads((ROOT / "video" / "plates" / pid / "meta.json").read_text())
    out = []
    for m in meta:
        f = m.get("face")
        if not f or len(f) < 12:
            out.append(np.nan)
            continue
        L = f[11]
        up, lo = np.array(L["lipI_up"]).reshape(-1, 2), np.array(L["lipI_lo"]).reshape(-1, 2)
        h = f[3] - f[1]
        gap = np.mean(lo[3:8, 1] - up[3:8, 1]) / max(h, 1e-3)   # middle of the inner lips
        out.append(.6 * np.clip(gap * 6, 0, 1) + .4 * f[4])
    c = np.array(out)
    if np.isnan(c).all():
        return None
    idx = np.arange(len(c)); ok = ~np.isnan(c)
    return np.interp(idx, idx[ok], c[ok])


def best_lag(a, b, max_lag):
    """lag L (frames) maximising corr(a[t], b[t + L]); a = vocal (song-aligned), b = mouth (plate)."""
    def z(x):
        x = np.convolve(x, np.ones(3) / 3, mode="same")
        return (x - x.mean()) / (x.std() + 1e-9)
    a, b = z(a), z(b)
    best, bl = -9, 0
    for L in range(-max_lag, max_lag + 1):
        if L >= 0:
            x, y = a[:len(a) - L], b[L:L + len(a) - L]
        else:
            x, y = a[-L:], b[:len(a) + L]
        n = min(len(x), len(y))
        if n < 12:
            continue
        r = float(np.mean(x[:n] * y[:n]))
        if r > best:
            best, bl = r, L
    return bl, best


def lip_gap(pid):
    """Inner-lip gap per frame, normalised by face height (NaN where no face)."""
    meta = json.loads((ROOT / "video" / "plates" / pid / "meta.json").read_text())
    g = []
    for m in meta:
        f = m.get("face")
        if not f or len(f) < 12:
            g.append(np.nan); continue
        L = f[11]; up, lo = np.array(L["lipI_up"]).reshape(-1, 2), np.array(L["lipI_lo"]).reshape(-1, 2)
        g.append(float(np.mean(lo[3:8, 1] - up[3:8, 1]) / max(f[3] - f[1], 1e-3)))
    return np.array(g)


def event_lag(pid, s0, win, max_lag=.8):
    """Phoneme-event sync: lips must be closed on bilabials (b/m/p onsets, word-final m) and open mid-vowel.
    Returns (lag_s, score, n_events). plate time = song time - s0 + lag."""
    tm = json.loads((ROOT / "video" / "data" / "timing.json").read_text())
    words = [(t, w) for l in tm["lines"] for (t, w) in l["words"] if win[0] - .05 <= t <= win[1]]
    ends = {}
    allw = [(t, w) for l in tm["lines"] for (t, w) in l["words"]]
    for i, (t, w) in enumerate(allw):
        nxt = allw[i + 1][0] if i + 1 < len(allw) else t + .6
        ends[(t, w)] = min(nxt, t + .9)
    closed, opened = [], []
    for t, w in words:
        ww = w.lower().strip(",.…'()—")
        if ww[:1] in "bmp":
            closed.append(t + .02)
        if ww.endswith("m") or ww.endswith("me") and ww != "me":
            closed.append(ends[(t, w)] - .05)
        opened.append(t + .45 * (ends[(t, w)] - t))
    gap = lip_gap(pid)
    ok = ~np.isnan(gap)
    if ok.sum() < 10 or not closed:
        return None
    idx = np.arange(len(gap)); gi = np.interp(idx, idx[ok], gap[ok])
    gi = (gi - np.percentile(gi, 5)) / (np.percentile(gi, 95) - np.percentile(gi, 5) + 1e-9)
    samp = lambda tt: np.interp(tt * FPS, idx, gi)
    best = (-9, 0)
    for L in np.arange(-max_lag, max_lag + 1e-9, 1 / FPS):
        c = np.mean([samp(t - s0 + L) for t in closed]); o = np.mean([samp(t - s0 + L) for t in opened])
        best = max(best, (o - c, round(float(L), 3)))
    return best[1], round(float(best[0]), 3), len(closed) + len(opened)


def word_strip(pid, s0, win, lag, out):
    """Mouth crops at every word onset (and mid-word) under `lag`, labelled — for eyeballing the sync."""
    from PIL import Image, ImageDraw
    tm = json.loads((ROOT / "video" / "data" / "timing.json").read_text())
    meta = json.loads((ROOT / "video" / "plates" / pid / "meta.json").read_text())
    words = [(t, w) for l in tm["lines"] for (t, w) in l["words"] if win[0] - .05 <= t <= win[1]]
    tiles = []
    for t, w in words:
        for dt, tag in ((0.02, ""), (0.18, "+")):
            f = int(round((t + dt - s0 + lag) * FPS)) + 1
            f = max(1, min(len(meta), f))
            im = Image.open(ROOT / "video" / "plates" / pid / f"f{f:04d}.jpg")
            fc = meta[f - 1].get("face")
            if fc:
                mx, my = fc[9] * im.width, fc[10] * im.height; s = (fc[3] - fc[1]) * im.height * .42
                crop = im.crop((int(mx - s), int(my - s * .7), int(mx + s), int(my + s * .7))).resize((150, 105))
            else:
                crop = im.resize((150, 105))
            d = ImageDraw.Draw(crop); d.rectangle((0, 0, 150, 16), fill=(0, 0, 0)); d.text((3, 2), f"{w}{tag}", fill=(255, 255, 0))
            tiles.append(crop)
    if not tiles:
        return
    cols = 12; rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 150, rows * 105))
    for i, tl in enumerate(tiles):
        sheet.paste(tl, ((i % cols) * 150, (i // cols) * 105))
    sheet.save(out, quality=88)


def run(pid, s0, win=None):
    mp4 = sorted((ROOT / "media" / "plates" / pid).glob("take*.mp4"), key=lambda p: int(p.stem[4:]))[-1]
    mouth = mouth_curve(pid)
    n = len(mouth) if mouth is not None else 0
    dur = n / FPS if n else float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout)
    voc = envelope(load_audio(VOCALS, ss=s0, dur=dur))
    rep = {"plate": pid, "take": mp4.name, "seg_start": s0, "frames": n}
    if mouth is not None:
        m = min(len(voc), len(mouth))
        a, b = 0, m
        if win:  # only the part of the take the edit uses (song times)
            a, b = max(0, int((win[0] - s0) * FPS)), min(m, int((win[1] - s0) * FPS))
            rep["window"] = win
        L, r = best_lag(voc[a:b], mouth[a:b], int(.6 * FPS))
        rep.update({"mouth_lag_s": round(L / FPS, 3), "mouth_corr": round(r, 3)})
        ev = event_lag(pid, s0, win or (s0, s0 + dur))
        if ev:
            rep.update({"event_lag_s": ev[0], "event_score": ev[1], "events": ev[2]})
    # the clip's own audio track vs the reference segment
    clip_audio = load_audio(mp4)
    if len(clip_audio) > 1000:
        ref = envelope(load_audio(SONG, ss=s0, dur=dur))
        ca = envelope(clip_audio)
        m = min(len(ref), len(ca))
        La, ra = best_lag(ref[:m], ca[:m], int(.8 * FPS))
        rep.update({"audio_lag_s": round(La / FPS, 3), "audio_corr": round(ra, 3)})
    (mp4.parent / "sync.json").write_text(json.dumps(rep, indent=1))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(12, 3))
        tt = np.arange(len(voc)) / FPS
        ax.plot(tt, voc, label="vocal envelope (song)", color="#e0572a")
        if mouth is not None:
            lag = rep.get("mouth_lag_s", 0)
            ax.plot(np.arange(len(mouth)) / FPS - lag, (mouth - mouth.min()) / (np.ptp(mouth) + 1e-9), label=f"mouth (shifted by lag {lag:+.2f}s)", color="#2a64e0")
        ax.set_title(f"{pid}: {json.dumps({k: v for k, v in rep.items() if k.endswith(('lag_s', 'corr'))})}", fontsize=9)
        ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(mp4.parent / "sync.png", dpi=90); plt.close(fig)
    except Exception as e:
        print("plot failed", e)
    print(json.dumps(rep))
    return rep


if __name__ == "__main__":
    agg_path = ROOT / "video" / "data" / "sync.json"
    agg = json.loads(agg_path.read_text()) if agg_path.exists() else {}
    for a in sys.argv[1:]:
        parts = a.split(":")
        pid, s0 = parts[0], float(parts[1])
        win = (float(parts[2]), float(parts[3])) if len(parts) >= 4 else None
        rep = run(pid, s0, win)
        # lag used for playback: the mouth measurement when it is trustworthy, else the clip's audio placement
        if rep.get("event_score", 0) >= .25:
            lag, src = rep["event_lag_s"], "phoneme-events"
        elif rep.get("mouth_corr", 0) >= .25:
            lag, src = rep["mouth_lag_s"], "mouth"
        elif rep.get("audio_corr", 0) >= .4:
            lag, src = rep["audio_lag_s"], "audio"
        else:
            lag, src = 0.0, "none"
        agg[pid] = {"lag": lag, "source": src, "mouth_corr": rep.get("mouth_corr"), "event_score": rep.get("event_score"), "audio_corr": rep.get("audio_corr"), "take": rep["take"]}
        try:
            word_strip(pid, float(s0), win or (float(s0), float(s0) + 12), lag, ROOT / "media" / "plates" / pid / "words.jpg")
        except Exception as e:
            print("strip failed", e)
    agg_path.write_text(json.dumps(agg, indent=1))
    print("wrote", agg_path)
