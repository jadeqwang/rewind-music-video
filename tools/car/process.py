#!/usr/bin/env python3
"""Car asset kit: ref.jpg -> matte.png, lines.png, contours.json, and CAR_SHEET.jpg.
Usage: process.py [view ...]   (default: all views in assets/car/)
Matte: rembg isnet-general-use (cached in analysis/car/<view>_rawmask.png) -> cleaned.
Lines: bilateral smooth -> XDoG + Canny inside the matte, plus the matte silhouette, specks removed.
Contours: normalized polylines (body, windows, wheels, tail/head lights, detail strokes)."""
import sys, os, json
import numpy as np, cv2
from skimage.morphology import skeletonize

ROOT = "/home/user/rewind-music-video"; CAR = ROOT + "/assets/car"
VIEWS = ["chase", "rear34", "rear", "side", "front34", "top"]


def raw_mask(v, img):
    p = f"{ROOT}/analysis/car/{v}_rawmask.png"
    if not os.path.exists(p):
        from rembg import new_session, remove
        from PIL import Image
        m = remove(Image.open(f"{CAR}/{v}/ref.jpg"), session=new_session("isnet-general-use"), only_mask=True)
        m.save(p)
    return cv2.imread(p, 0)


def clean_matte(m):
    b = (m > 127).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(b, 8)
    if n > 1:
        k = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]); b = (lab == k).astype(np.uint8)
    # fill holes
    ff = b.copy(); h, w = b.shape; msk = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, msk, (0, 0), 1); b = b | (1 - ff)
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    soft = cv2.GaussianBlur(b.astype(np.float32), (0, 0), 1.2)
    return b, (np.clip(soft, 0, 1) * 255).astype(np.uint8)


def xdog(g, s=1.0, k=1.6, p=20, eps=0.0, phi=10):
    g = g.astype(np.float32) / 255
    a = cv2.GaussianBlur(g, (0, 0), s); b = cv2.GaussianBlur(g, (0, 0), s * k)
    d = (1 + p) * a - p * b
    e = np.where(d >= eps, 1.0, 1 + np.tanh(phi * (d - eps)))
    return (e < 0.5)


def despeck(b, min_area):
    n, lab, st, _ = cv2.connectedComponentsWithStats(b.astype(np.uint8), 8)
    keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_area
    return keep[lab]


def line_art(img, body):
    h, w = body.shape
    sm = img.copy()
    for _ in range(3): sm = cv2.bilateralFilter(sm, 9, 40, 7)
    g = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY)
    g = cv2.createCLAHE(2.0, (8, 8)).apply(g)
    scale = max(w, h) / 1536
    inner = cv2.erode(body, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    xd = xdog(g, s=1.3 * scale) & (inner > 0)
    ca = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.5), 50, 120) > 0
    ca &= inner > 0
    lines = xd | ca
    lines = skeletonize(lines)
    lines = cv2.dilate(lines.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    lines = despeck(lines, int(60 * scale))
    sil = cv2.morphologyEx(body, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    allc = lines | sil
    allc = cv2.dilate(allc.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    a = cv2.GaussianBlur(allc.astype(np.float32), (0, 0), 0.8)
    a = (np.clip(a * 1.6, 0, 1) * 255).astype(np.uint8)
    rgba = np.dstack([np.full_like(a, 255)] * 3 + [a])
    return rgba, lines


def trace_skeleton(sk, min_len):
    """Skeleton -> list of open polylines (pixel coords)."""
    sk = sk.astype(np.uint8).copy(); h, w = sk.shape
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    ys, xs = np.nonzero(sk)
    deg = cv2.filter2D(sk, -1, np.ones((3, 3), np.float32)) - 1
    pts = sorted(zip(ys, xs), key=lambda p: deg[p] != 1)  # endpoints first
    out = []
    for y0, x0 in pts:
        if not sk[y0, x0]: continue
        path = [(x0, y0)]; sk[y0, x0] = 0; y, x = y0, x0
        while True:
            nxt = None
            for dy, dx in nb:
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and sk[yy, xx]: nxt = (yy, xx); break
            if nxt is None: break
            y, x = nxt; sk[y, x] = 0; path.append((x, y))
        if len(path) >= min_len: out.append(path)
    return out


def poly(c, eps):
    return cv2.approxPolyDP(np.asarray(c, np.int32).reshape(-1, 1, 2), eps, False).reshape(-1, 2)


def contours(v, img, body, lines):
    h, w = body.shape
    x0, y0, bw, bh = cv2.boundingRect(body)
    S = max(bw, bh); A = body.sum()
    eps = S * 0.004
    norm = lambda P: [[round((px - x0) / S, 4), round((py - y0) / S, 4)] for px, py in P]
    feats = []
    cs, _ = cv2.findContours(body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    feats.append({"type": "body", "closed": True, "pts": norm(cv2.approxPolyDP(c, eps, True).reshape(-1, 2))})
    hsv = cv2.cvtColor(cv2.bilateralFilter(img, 9, 40, 7), cv2.COLOR_BGR2HSV)
    H, Sa, V = [hsv[..., i].astype(int) for i in range(3)]
    inner = cv2.erode(body, np.ones((7, 7), np.uint8))
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

    def blobs(mask, typ, min_frac, maxn=8):
        mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, k5)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k5)
        cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cs = sorted([c for c in cs if cv2.contourArea(c) > min_frac * A], key=cv2.contourArea, reverse=True)[:maxn]
        res = []
        for c in cs:
            bx, by, cw, ch = cv2.boundingRect(c)
            t = typ(bx, by, cw, ch) if callable(typ) else typ
            if t is None: continue
            res.append({"type": t, "closed": True, "pts": norm(cv2.approxPolyDP(c, eps * 0.7, True).reshape(-1, 2))})
        return res

    red = ((H < 12) | (H > 168)) & (Sa > 110) & (V > 110) & (inner > 0)
    feats += blobs(red, "taillight", 0.002, 4)
    head = (V > 235) & (Sa < 60) & (inner > 0)
    if v in ("front34", "side", "top"):
        def ht(bx, by, cw, ch):
            cx = (bx + cw / 2 - x0) / bw; cy = (by + ch / 2 - y0) / bh
            if v == "top": return "headlight" if cy < 0.15 else None
            if v == "side": return "headlight" if cx < 0.15 else None
            return "headlight" if cy > 0.35 and cy < 0.75 and cx < 0.6 else None
        feats += blobs(head, ht, 0.0008, 3)
    dark = (V < 55) & (inner > 0)

    def dt(bx, by, cw, ch):
        cy = (by + ch / 2 - y0) / bh
        if v == "top": return "window"
        if cy > 0.62:
            if v in ("rear", "chase"): return "tyre"
            return "wheel" if (ch > 0.18 * bh and 0.4 < cw / max(ch, 1) < 1.6) else "lower_dark"
        return "window"
    feats += blobs(dark, dt, 0.006, 8)
    # wheel rims: ellipse fitted to each dark tyre blob, scaled to the rim radius
    if v in ("side", "front34", "rear34"):
        for f in [f for f in feats if f["type"] == "wheel"]:
            P = np.array(f["pts"], np.float32)
            if len(P) < 5: continue
            (cx, cy), (ea, eb), ang = cv2.fitEllipse(P)
            if min(ea, eb) < 0.04: continue
            E = cv2.ellipse2Poly((int(cx * 1e4), int(cy * 1e4)), (int(ea * 0.33e4), int(eb * 0.33e4)), int(ang), 0, 360, 12)
            feats.append({"type": "rim", "closed": True, "pts": [[round(x / 1e4, 4), round(y / 1e4, 4)] for x, y in E]})
    if v == "side":   # flat profile: Hough circles are exact; replace blob-based wheels
        feats = [f for f in feats if f["type"] not in ("wheel", "rim", "lower_dark")]
        g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), 2)
        circ = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, 1.5, bw * 0.25, param1=90, param2=60,
                                minRadius=int(bh * 0.12), maxRadius=int(bh * 0.32))
        ang = np.linspace(0, 2 * np.pi, 33)
        for cx, cy, r in (circ[0][:4] if circ is not None else []):
            if (cy - y0) / bh < 0.55: continue
            for t, rr in (("wheel", r * 1.0), ("rim", r * 0.68)):
                feats.append({"type": t, "closed": True, "pts": norm(np.c_[cx + rr * np.cos(ang), cy + rr * np.sin(ang)])})
    # detail strokes from the line art
    for p in sorted(trace_skeleton(skeletonize(lines), int(S * 0.04)), key=len, reverse=True)[:40]:
        feats.append({"type": "detail", "closed": False, "pts": norm(poly(p, eps))})
    return {"view": v, "units": "unit box: x,y in [0,1] scaled by max(bbox w,h) of the car, origin = bbox top-left, y down",
            "bbox_aspect_w_over_h": round(bw / bh, 4), "extent": [round(bw / S, 4), round(bh / S, 4)],
            "src_bbox_px": [int(x0), int(y0), int(bw), int(bh)], "src_size": [w, h],
            "anchor_ground_center": [round(bw / S / 2, 4), round(bh / S, 4)],
            "counts": {t: sum(f["type"] == t for f in feats) for t in sorted({f["type"] for f in feats})},
            "features": feats}


def render_contours(J, size=480, pad=20):
    W = size; ex = J["extent"]; s = (W - 2 * pad)
    Hh = int(ex[1] * s + 2 * pad)
    im = np.zeros((max(Hh, 50), W, 3), np.uint8)
    col = {"body": (255, 255, 255), "window": (200, 200, 140), "wheel": (160, 160, 160), "tyre": (160, 160, 160),
           "rim": (220, 220, 220), "lower_dark": (90, 90, 90), "taillight": (60, 60, 255), "headlight": (200, 255, 255), "detail": (150, 150, 150)}
    for f in J["features"]:
        P = (np.array(f["pts"]) * s + pad).astype(np.int32)
        cv2.polylines(im, [P], f["closed"], col[f["type"]], 2 if f["type"] != "detail" else 1, cv2.LINE_AA)
    return im


def main(views):
    for v in views:
        d = f"{CAR}/{v}"; img = cv2.imread(f"{d}/ref.jpg")
        body, soft = clean_matte(raw_mask(v, img))
        cv2.imwrite(f"{d}/matte.png", soft)
        rgba, lines = line_art(img, body)
        cv2.imwrite(f"{d}/lines.png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
        J = contours(v, img, body, lines)
        json.dump(J, open(f"{d}/contours.json", "w"), separators=(",", ":"))
        print(v, J["counts"], flush=True)
    sheet()


def sheet():
    rows = []; TW = 480
    for v in VIEWS:
        d = f"{CAR}/{v}"
        if not os.path.exists(f"{d}/contours.json"): continue
        img = cv2.imread(f"{d}/ref.jpg"); m = cv2.imread(f"{d}/matte.png", 0)
        L = cv2.imread(f"{d}/lines.png", cv2.IMREAD_UNCHANGED)
        J = json.load(open(f"{d}/contours.json"))
        x0, y0, bw, bh = J["src_bbox_px"]; p = int(0.06 * max(bw, bh))
        crop = lambda a: a[max(0, y0 - p):y0 + bh + p, max(0, x0 - p):x0 + bw + p]
        ink = np.full_like(img, (10, 8, 7))
        la = L[..., 3:4].astype(np.float32) / 255
        lines_on_ink = (ink * (1 - la) + 255 * la).astype(np.uint8)
        tiles = [crop(img), cv2.cvtColor(crop(m), cv2.COLOR_GRAY2BGR), crop(lines_on_ink)]
        tiles = [cv2.resize(t, (TW, int(t.shape[0] * TW / t.shape[1]))) for t in tiles]
        ct = render_contours(J, TW)
        th = max(t.shape[0] for t in tiles + [ct])
        th = min(th, 520)
        def fit(t):
            if t.shape[0] > th: t = cv2.resize(t, (int(t.shape[1] * th / t.shape[0]), th))
            o = np.zeros((th, TW, 3), np.uint8); o[:t.shape[0], :t.shape[1]] = t; return o
        row = np.hstack([fit(t) for t in tiles + [ct]])
        cv2.putText(row, v, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
        rows.append(row)
    cv2.imwrite(f"{CAR}/CAR_SHEET.jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])


if __name__ == "__main__":
    main(sys.argv[1:] or VIEWS)
