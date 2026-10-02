"""Mouth crops every 1/8 s over a song window, with the vocal envelope and word onsets drawn under them."""
import json, sys
import cv2, numpy as np, librosa

def main(clip, t0, a, b, roi, out, lag=0.0):
    cap = cv2.VideoCapture(clip); fps = cap.get(cv2.CAP_PROP_FPS) or 24; frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    x0, y0, x1, y1 = roi
    words = [w for w in json.load(open('/tmp/work/lyrics_words_v3.json')) if a <= w['t'] < b]
    v, sr = librosa.load('/tmp/work/vocals.wav', sr=22050, mono=True, offset=a, duration=b - a)
    env = librosa.feature.rms(y=v, frame_length=1024, hop_length=256)[0]; env = env / (env.max() + 1e-9)
    step = 0.125; n = int((b - a) / step)
    tw = 90; th = int(tw * (y1 - y0) / (x1 - x0))
    tiles = []
    for i in range(n):
        t = a + i * step
        fi = int(round((t - t0 + lag) * fps)); fi = max(0, min(len(frames) - 1, fi))
        c = cv2.resize(frames[fi][y0:y1, x0:x1], (tw, th))
        cv2.putText(c, f"{t:.2f}", (2, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 255), 1)
        tiles.append(c)
    per = 20
    rows = []
    for r in range(0, n, per):
        seg = tiles[r:r + per]
        row = np.hstack(seg + [np.zeros((th, tw, 3), np.uint8)] * (per - len(seg)))
        # envelope strip
        strip = np.zeros((60, row.shape[1], 3), np.uint8)
        ta, tb = a + r * step, a + (r + per) * step
        for k in range(row.shape[1]):
            t = ta + k / row.shape[1] * (tb - ta)
            e = env[min(len(env) - 1, int((t - a) * sr / 256))] if t < b else 0
            cv2.line(strip, (k, 59), (k, 59 - int(e * 55)), (80, 200, 80), 1)
        for w in words:
            if ta <= w['t'] < tb:
                xx = int((w['t'] - ta) / (tb - ta) * row.shape[1])
                cv2.line(strip, (xx, 0), (xx, 59), (0, 0, 255), 1)
                cv2.putText(strip, w['word'][:10], (xx + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        rows.append(np.vstack([row, strip]))
    cv2.imwrite(out, np.vstack(rows))

if __name__ == '__main__':
    roi = tuple(int(v) for v in sys.argv[5].split(','))
    main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), roi, sys.argv[6], float(sys.argv[7]) if len(sys.argv) > 7 else 0.0)
