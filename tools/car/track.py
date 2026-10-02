#!/usr/bin/env python3
"""Per-frame bounding-box track of the hero car in assets/clips/{E1,Epull}.mp4 -> assets/car/tracks/<clip>.json
Light-blob tracking (the Seedance car bodies are dark and unreliable):
  E1    : red tail-light pair (chase / aerial from behind). bbox from the pair via ratios measured on frame 200.
  Epull : the lead car's leading-end light cluster (white headlights early, red lights after the Seedance flip),
          static streetlights removed with a median background; bbox from a road-perspective length model.
Coordinates in source pixels (1280x720, 24 fps); also normalized [0,1]. Gaps are linearly interpolated (flag interp)."""
import json, sys, os
import numpy as np, cv2

ROOT = "/home/user/rewind-music-video"


def frames(path):
    cap = cv2.VideoCapture(path); F = []
    while True:
        ok, f = cap.read()
        if not ok: break
        F.append(f)
    return np.array(F), cap.get(cv2.CAP_PROP_FPS)


def comps(mask, min_area):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    return [(st[i], cen[i]) for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= min_area]


def red_mask(f):
    h = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    return ((h[..., 0] < 8) | (h[..., 0] > 172)) & (h[..., 1] > 120) & (h[..., 2] > 150)


def track_E1(F):
    """Tracked BACKWARDS from the last frame (car large and unambiguous), gated by the previous position,
    so early sodium-lamp / skyline red pixels can't capture the track. Stops after 6 misses."""
    out = [None] * len(F); prev = None; miss = 0
    for i in range(len(F) - 1, -1, -1):
        f = F[i]
        r = red_mask(f); r[:int(0.2 * r.shape[0])] = False   # skyline red dots
        cs = comps(cv2.dilate(r.astype(np.uint8), np.ones((3, 3), np.uint8)), 3)
        if prev is not None:
            gx, gy = max(25, 0.6 * prev[2]), max(20, 0.4 * prev[2])
            cs = [c for c in cs if abs(c[1][0] - prev[0]) < gx + prev[2] / 2 and abs(c[1][1] - prev[1]) < gy]
        if not cs:
            miss += 1
            if miss > 6 and prev is not None: break
            continue
        miss = 0
        a = max(cs, key=lambda c: c[0][4])
        grp = [c for c in cs if abs(c[1][1] - a[1][1]) < max(8, a[0][3] * 1.5)
               and abs(c[1][0] - a[1][0]) < max(30, (prev[2] * 1.3 if prev else 300))]
        x0 = min(c[0][0] for c in grp); x1 = max(c[0][0] + c[0][2] for c in grp)
        ly = float(np.average([c[1][1] for c in grp], weights=[c[0][4] for c in grp]))
        span = max(x1 - x0, 6); cx = (x0 + x1) / 2
        w = 1.12 * span
        out[i] = {"lights_x": [float(x0), float(x1)], "lights_y": ly,
                  "bbox": [cx - w / 2, ly - 0.53 * span, cx + w / 2, ly + 0.42 * span], "n_blobs": len(grp)}
        prev = (cx, ly, span)
    return out


def track_Epull(F):
    bg = np.median(F[::2], 0).astype(np.uint8)
    static = cv2.dilate((cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY) > 170).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    out = []; prev = None
    L = lambda y: 85 + 0.37 * (y - 220)      # lead-car length in px vs image y (measured f0, f50, f96)
    for i, f in enumerate(F):
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        white = (hsv[..., 2] > 235) & (hsv[..., 1] < 70)
        m = (white | red_mask(f)) & ~static
        cs = comps(cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)), 6)
        # the lead car is the leftmost moving light cluster near the previous position
        if prev is not None:
            near = [c for c in cs if abs(c[1][0] - prev[0]) < 90 and abs(c[1][1] - prev[1]) < 60]
            cs = near
        if not cs: out.append(None); prev = prev; continue
        lead = min(cs, key=lambda c: c[1][0])
        grp = [c for c in cs if abs(c[1][0] - lead[1][0]) < 45 and abs(c[1][1] - lead[1][1]) < 30 and c[0][4] >= 0.15 * lead[0][4]]
        x0 = min(c[0][0] for c in grp); y = float(min(c[1][1] for c in grp))   # topmost = lamp, not its wet-road reflection
        is_red = bool(red_mask(f)[int(y), int(np.clip(lead[1][0], 0, f.shape[1] - 1))])
        Lp = L(y)
        # the car extends up-right from its leading (left) end along the road (slope ~ -0.36)
        bb = [x0 - 0.05 * Lp, y - 0.22 * Lp, x0 + 1.05 * Lp, y + 0.2 * Lp]
        out.append({"lead_light": [float(x0), y], "light_color": "red" if is_red else "white", "bbox": bb})
        prev = (lead[1][0], y)
    return out


def finish(clip, raw, fps, size, notes):
    n = len(raw); W, H = size
    idx = [i for i, r in enumerate(raw) if r]
    B = np.array([raw[i]["bbox"] for i in idx], float)
    full = np.full((n, 4), np.nan)
    if len(idx):
        for k in range(4):
            full[idx[0]:idx[-1] + 1, k] = np.interp(np.arange(idx[0], idx[-1] + 1), idx, B[:, k])
        # light temporal smoothing (5-frame centred median then 3-tap mean) on the valid span
        s = full.copy()
        for i in range(idx[0], idx[-1] + 1):
            lo, hi = max(idx[0], i - 2), min(idx[-1], i + 2)
            s[i] = np.median(full[lo:hi + 1], 0)
        full = s
    frames_out = []
    for i in range(n):
        if np.isnan(full[i, 0]):
            frames_out.append({"f": i, "t": round(i / fps, 4), "visible": False}); continue
        x0, y0, x1, y1 = full[i]
        d = {"f": i, "t": round(i / fps, 4), "visible": True, "interp": raw[i] is None,
             "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
             "bbox_norm": [round(x0 / W, 4), round(y0 / H, 4), round(x1 / W, 4), round(y1 / H, 4)],
             "center": [round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1)], "width": round(x1 - x0, 1)}
        if raw[i]:
            d.update({k: v for k, v in raw[i].items() if k != "bbox"})
        frames_out.append(d)
    os.makedirs(f"{ROOT}/assets/car/tracks", exist_ok=True)
    J = {"clip": f"assets/clips/{clip}.mp4", "fps": fps, "size": [W, H], "n_frames": n, "notes": notes, "frames": frames_out}
    json.dump(J, open(f"{ROOT}/assets/car/tracks/{clip}.json", "w"), indent=0)
    vis = [fr for fr in frames_out if fr["visible"]]
    print(clip, "visible", len(vis), "/", n, "detected", sum(1 for r in raw if r),
          "first", vis[0]["f"] if vis else None, "last", vis[-1]["f"] if vis else None)
    return J


def overlay(clip, F, J, out):
    T = []
    for i in np.linspace(0, len(F) - 1, 8).astype(int):
        f = np.clip(F[i].astype(int) * 2, 0, 255).astype(np.uint8)
        fr = J["frames"][i]
        if fr["visible"]:
            x0, y0, x1, y1 = map(int, fr["bbox"])
            cv2.rectangle(f, (x0, y0), (x1, y1), (0, 255, 0) if not fr["interp"] else (0, 200, 255), 2)
        cv2.putText(f, str(i), (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        T.append(cv2.resize(f, (640, 360)))
    cv2.imwrite(out, np.vstack([np.hstack(T[:4]), np.hstack(T[4:])]))


if __name__ == "__main__":
    for clip in sys.argv[1:] or ["E1", "Epull"]:
        F, fps = frames(f"{ROOT}/assets/clips/{clip}.mp4")
        if clip == "E1":
            raw = track_E1(F)
            notes = ("Hero car seen from behind/above (chase). bbox from the red tail-light pair: width=1.12*light span, "
                     "top=lights_y-0.53*span, bottom=lights_y+0.42*span. Frames before the first visible frame show an oncoming car "
                     "(headlights) leaving the bottom edge: not tracked. Use view 'chase'/'rear34' line art.")
        else:
            raw = track_Epull(F)
            notes = ("Lead car = leftmost moving light cluster (its leading/left end). Seedance flips the car mid-clip: white "
                     "headlights at the leading end until ~f45, red lights at the same end afterwards. Draw our TL in 'side' view "
                     "facing LEFT (direction of travel), rotated ~-20 deg to the road (slope -0.36). bbox from a perspective length "
                     "model L(y)=85+0.37*(y-220) px. The follower (black sedan headlights) is not tracked here.")
        J = finish(clip, raw, fps, (F.shape[2], F.shape[1]), notes)
        overlay(clip, F, J, f"{ROOT}/analysis/car/track_{clip}.jpg")
