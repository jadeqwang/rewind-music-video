"""Face crop + SFace identity similarity + side-by-side comparison montage."""
import cv2, numpy as np, sys, os, glob, json
S = "/tmp/claude-0/-home-user-rewind-music-video/6b28fe5a-ebc4-5b63-aa64-c3b0ecf3f843/scratchpad/"
D = "/home/user/rewind-music-video/assets/character/"
DET = cv2.FaceDetectorYN.create(S + "yunet.onnx", "", (320, 320), 0.6)
REC = cv2.FaceRecognizerSF.create(S + "sface.onnx", "")
REFS = ["PXL_20250908_195405539.MP.jpg", "PXL_20260528_215628802.jpg", "PXL_20250908_195352130.jpg",
        "PXL_20241109_223659531.jpg", "PXL_20260929_003030232.jpg"]

def faces(im):
    DET.setInputSize((im.shape[1], im.shape[0])); _, f = DET.detect(im)
    if f is None: return []
    f = sorted(f.tolist(), key=lambda r: (round((r[1] + r[3] / 2) / (im.shape[0] / 3)), r[0]))
    return [np.array(r, np.float32) for r in f]

def crop(im, f, size=320, k=1.9):
    x, y, w, h = f[:4]; cx, cy = x + w / 2, y + h / 2; s = max(w, h) * k
    M = np.float32([[size / s, 0, size / 2 - cx * size / s], [0, size / s, size / 2 - cy * size / s]])
    return cv2.warpAffine(im, M, (size, size), borderValue=(200, 200, 200))

def emb(im, f): return REC.feature(REC.alignCrop(im, f))

_ref = None
def ref_embs():
    global _ref
    if _ref is None:
        _ref = []
        for r in REFS[:4]:
            im = cv2.imread(D + "refs_small/" + r); f = faces(im)
            f = max(f, key=lambda a: a[2] * a[3]); _ref.append(emb(im, f))
    return _ref

def sim(im, f):
    e = emb(im, f)
    return float(np.mean([REC.match(e, r, cv2.FaceRecognizerSF_FR_COSINE) for r in ref_embs()]))

def label(t, s, col=(0, 0, 0)):
    t = t.copy(); cv2.rectangle(t, (0, 0), (t.shape[1], 26), (255, 255, 255), -1)
    cv2.putText(t, s, (5, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1, cv2.LINE_AA); return t

def compare(cand, out=None):
    im = cv2.imread(cand); fs = faces(im)
    top = []
    for r in REFS:
        ri = cv2.imread(D + "refs_small/" + r); rf = max(faces(ri), key=lambda a: a[2] * a[3])
        top.append(label(crop(ri, rf), "REF " + r[4:19]))
    bot, sims = [], []
    for i, f in enumerate(fs[:8]):
        s = sim(im, f); sims.append(round(s, 3))
        bot.append(label(crop(im, f), f"#{i} id={s:.2f}", (0, 120, 0) if s > 0.45 else (0, 0, 200)))
    n = max(len(top), len(bot))
    pad = lambda row: row + [np.full((320, 320, 3), 255, np.uint8)] * (n - len(row))
    mont = np.vstack([np.hstack(pad(top)), np.hstack(pad(bot) if bot else pad([]))])
    out = out or S + "cmp_" + os.path.basename(cand)
    cv2.imwrite(out, mont, [cv2.IMWRITE_JPEG_QUALITY, 88]); return out, sims

if __name__ == "__main__":
    for c in sys.argv[1:]:
        o, s = compare(c); print(os.path.basename(c), "faces", len(s), "id", s, "mean", round(np.mean(s), 3) if s else None, o)
