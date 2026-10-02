"""Align canonical lyrics to Whisper word timestamps and refine starts with vocal onsets."""
import difflib, json, re, sys
import numpy as np
import librosa

LINES = [
 ("V1", "Do you still care"),
 ("V1", "You're yearning to see the life out there"),
 ("V1", "Searching for me"),
 ("V1", "Are you still there"),
 ("V1", "A rare earth looking for a friend"),
 ("V2", "Lived my life on a pale blue dot"),
 ("V2", "Your signal here I think I've caught"),
 ("V2", "The beating blinking of a star"),
 ("V2", "A planet's transit is not that far from my own"),
 ("V2", "How could we be alone"),
 ("V3", "Before they launch or self-destruct"),
 ("V3", "Weapons, wars, and now we're"),
 ("V3", "Keep on looking, keep the faith"),
 ("V3", "Keep up funding, our planet waits"),
 ("V3", "for your transmission"),
 ("V3", "Our science has a vision"),
 ("V4", "Do you still care"),
 ("V4", "You're yearning to see the life out there"),
 ("V4", "Searching for me"),
 ("V4", "Are you still there"),
 ("V4", "A rare earth looking for a friend"),
 ("V5", "Lived my life on a pale blue dot"),
 ("V5", "Your signal here I think I've caught"),
 ("V5", "The beating blinking of a star"),
 ("V5", "A planet's transit is not that far from my own"),
 ("V5", "How could we be alone"),
]


def norm(w):
    return re.sub(r"[^a-z']", "", w.lower().replace("-", ""))


def main(whisper_json, vocals_wav, onsets_npy, out_json):
    d = json.load(open(whisper_json))["result"]
    ww = []
    for s in d["segments"]:
        for w in s.get("words") or []:
            if w["start"] < 115:
                for part in re.split(r"(?<=\w)-(?=\w)|\s+", w["word"].strip()):
                    if part:
                        ww.append({"w": part, "start": w["start"], "end": w["end"]})
    canon = [(li, sec, wd) for li, (sec, line) in enumerate(LINES) for wd in line.split()]
    a = [norm(x[2]) for x in canon]
    b = [norm(x["w"]) for x in ww]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    t = [None] * len(canon)
    te = [None] * len(canon)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                t[i1 + k] = ww[j1 + k]["start"]; te[i1 + k] = ww[j1 + k]["end"]
        elif tag == "replace":
            # spread the replaced whisper span across the canonical words
            s0, e0 = ww[j1]["start"], ww[j2 - 1]["end"]
            n = i2 - i1
            for k in range(n):
                t[i1 + k] = s0 + (e0 - s0) * k / n; te[i1 + k] = s0 + (e0 - s0) * (k + 1) / n
    # interpolate any still-missing
    idx = [i for i in range(len(t)) if t[i] is not None]
    for i in range(len(t)):
        if t[i] is None:
            t[i] = float(np.interp(i, idx, [t[j] for j in idx])); te[i] = t[i] + 0.2

    v, sr = librosa.load(vocals_wav, sr=22050, mono=True)
    hop = 128
    rms = librosa.feature.rms(y=v, frame_length=1024, hop_length=hop)[0]
    rn = rms / np.percentile(rms, 99)
    onsets = np.load(onsets_npy)
    out = []
    for i, (li, sec, wd) in enumerate(canon):
        s = t[i]
        initial = i == 0 or canon[i - 1][0] != li
        if initial:
            cands = onsets[(onsets >= s - 0.15) & (onsets <= s + 1.2)]
            best = None
            for c in cands:
                if rn[int(c * sr / hop):int((c + 0.12) * sr / hop)].max() > 0.22:
                    best = c; break
            s2 = best if best is not None else s
        else:
            cands = onsets[(onsets >= s - 0.12) & (onsets <= s + 0.12)]
            s2 = cands[np.argmin(np.abs(cands - s))] if len(cands) else s
        out.append({"sec": sec, "line": li, "word": wd, "t": round(float(s2), 3), "w_start": round(t[i], 3), "w_end": round(te[i], 3)})
    # enforce strictly increasing word starts within a line (>= 70 ms apart); fall back to whisper time
    for i in range(1, len(out)):
        if out[i]["line"] == out[i - 1]["line"] and out[i]["t"] < out[i - 1]["t"] + 0.07:
            out[i]["t"] = round(max(out[i]["w_start"], out[i - 1]["t"] + 0.07), 3)
    for i, o in enumerate(out):
        if i + 1 < len(out) and out[i + 1]["line"] == o["line"]:
            o["end"] = out[i + 1]["t"]
        else:
            e = o["w_end"]; k = int(e * sr / hop)
            while k < len(rn) - 1 and rn[k] > 0.12 and (k * hop / sr) < e + 3.0:
                k += 1
            o["end"] = round(k * hop / sr, 3)
            nxt = next((q["t"] for q in out[i + 1:] if q["line"] != o["line"]), None)
            if nxt is not None:
                o["end"] = round(min(o["end"], nxt - 0.02), 3)
    json.dump(out, open(out_json, "w"), indent=1)
    for li in range(len(LINES)):
        ws = [o for o in out if o["line"] == li]
        print(f"L{li:02d} {ws[0]['sec']} {ws[0]['t']:7.3f}-{ws[-1]['end']:7.3f} | " + " ".join(
            f"{o['word']}@{o['t']:.2f}" + ("*" if abs(o['t'] - o['w_start']) > 0.08 else "") for o in ws))


if __name__ == "__main__":
    main(*sys.argv[1:5])
