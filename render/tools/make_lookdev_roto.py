# Look-dev roto sequences (no gen APIs): writes assets/roto/<shot_id>/ in the renderer's roto format.
#   lines/0000.png   white-on-transparent line art (RGBA, alpha = line)
#   matte/0000.png   subject mask (alpha)            [optional]
#   face/0000.png    face region mask (alpha)        [optional; inside it only `features` lines are drawn]
#   features/0000.png sparse major facial features   [optional; eyes, brows, nose tip, lips, jaw/hair contours]
#   hair/0000.png    hair region (alpha)             [optional; drawn as ink inside the bone figure]
#   meta.json {fps, frames, w, h, layers:[...], per_frame:[{glints:[[x,y]], faces:[[x,y,w,h]], mouth:[x,y,w]}]}
#
# ld_suits : XDoG + GrabCut on assets/tests/flux_schnell.jpg with a slow approach (push-in + footstep bob)
# ld_jade  : a procedural driver figure (vector-drawn, NOT a likeness) to exercise the Jade component + face rules
# ld_road  : XDoG world lines from assets/tests/grok_imagine_image.jpg with a forward drift
import cv2, numpy as np, json, os, sys
R = os.path.dirname(os.path.abspath(__file__)) + '/../..'
OUT = R + '/assets/roto'
FPS = 15
W, H = 1280, 720

def xdog(gray, sigma=0.9, k=1.6, tau=0.985, eps=0.02, phi=60.0):
    """DoG line extraction (dark side of edges): ~0 on flat areas, ~1 on lines. eps is in units of
    local contrast (the image is normalised by its 98th-percentile DoG response)."""
    g = gray.astype(np.float32) / 255.0
    g1 = cv2.GaussianBlur(g, (0, 0), sigma)
    g2 = cv2.GaussianBlur(g, (0, 0), sigma * k)
    d = g2 * tau - g1
    d = d / max(1e-4, np.percentile(np.abs(d), 98))
    return np.clip((d - eps) * phi, 0, 1)

def clean(lines, min_area=24, thr=0.35):
    b = (lines > thr).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(b, connectivity=8)
    keep = np.zeros(n, bool); keep[1:] = st[1:, 4] >= min_area
    return lines * keep[lab]

def rgba(alpha):
    a = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    out = np.zeros(a.shape + (4,), np.uint8); out[..., :3] = 255; out[..., 3] = a
    return out

def save(dirn, name, i, alpha):
    os.makedirs(f'{dirn}/{name}', exist_ok=True)
    cv2.imwrite(f'{dirn}/{name}/{i:04d}.png', rgba(alpha), [cv2.IMWRITE_PNG_COMPRESSION, 3])

def suits(n=50):
    d = OUT + '/ld_suits'
    im = cv2.imread(R + '/assets/tests/flux_schnell.jpg')
    h, w = im.shape[:2]
    mask = np.full((h, w), cv2.GC_BGD, np.uint8)
    mask[250:1024, 70:920] = cv2.GC_PR_FGD
    for (x0, y0, x1, y1) in [(170, 520, 310, 900), (440, 500, 620, 950), (700, 500, 840, 880), (485, 310, 545, 390), (230, 340, 280, 410), (712, 300, 762, 390)]:
        mask[y0:y1, x0:x1] = cv2.GC_FGD
    for (x0, y0, x1, y1) in [(300, 250, 430, 460), (340, 780, 410, 1024), (630, 820, 670, 1024), (0, 0, 1024, 250)]:
        mask[y0:y1, x0:x1] = cv2.GC_BGD
    bg = np.zeros((1, 65)); fg = np.zeros((1, 65))
    cv2.grabCut(im, mask, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
    m = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    nn, lab, st, _ = cv2.connectedComponentsWithStats(m)
    mm = np.zeros_like(m)
    for i in range(1, nn):
        if st[i, 4] > 5000: mm[lab == i] = 255
    mm = cv2.GaussianBlur(mm, (0, 0), 1.2)
    # boost local contrast so the dark suits still give folds/lapels
    lab_ = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
    cl = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(lab_[..., 0])
    glasses = [(255, 375), (515, 348), (737, 342)]   # sunglasses centres (source px)
    faces = [(255, 374, 104, 34), (515, 348, 112, 36), (737, 342, 100, 34)]
    meta = dict(fps=FPS, frames=n, w=W, h=H, layers=['lines', 'matte'], src='assets/tests/flux_schnell.jpg', per_frame=[])
    for i in range(n):
        u = i / (n - 1)
        s = (W / w) * (1.0 + 0.22 * u)                               # cover the width, push in (they approach)
        bob = 4 * abs(np.sin(i / FPS * np.pi * 2.07))               # footsteps
        hy = 355 * s                                                 # head line (source y 355) lands at y=300
        M = np.array([[s, 0, W / 2 - s * 512], [0, s, 300 - hy + bob]], np.float32)
        g = cv2.warpAffine(cl, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mt = cv2.warpAffine(mm, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0).astype(np.float32) / 255
        ln = clean(xdog(g, sigma=1.0, tau=1.0, eps=0.3, phi=2.2), 40)
        save(d, 'lines', i, ln)
        save(d, 'matte', i, mt)
        tr = lambda p: [float(M[0, 0] * p[0] + M[0, 2]), float(M[1, 1] * p[1] + M[1, 2])]
        meta['per_frame'].append(dict(
            glints=[tr(p) for p in glasses],
            faces=[tr((x, y)) + [fw * s, fh * s] for (x, y, fw, fh) in faces]))
    json.dump(meta, open(d + '/meta.json', 'w'))
    print('suits', n)

def road(n=60):
    d = OUT + '/ld_road'
    im = cv2.imread(R + '/assets/tests/grok_imagine_image.jpg')
    h, w = im.shape[:2]
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    meta = dict(fps=FPS, frames=n, w=W, h=H, layers=['lines'], src='assets/tests/grok_imagine_image.jpg', per_frame=[])
    for i in range(n):
        u = i / (n - 1)
        s = (W / w) * (1.0 + 0.10 * u)
        b = W / w; cx, cy = 760 * b, 380 * b   # zoom toward the vanishing area
        z = s / b
        M = np.array([[s, 0, (1 - z) * cx], [0, s, (1 - z) * cy]], np.float32)
        g = cv2.warpAffine(gray, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        ln = clean(xdog(g, sigma=1.1, tau=1.0, eps=0.35, phi=2.2), 60)
        save(d, 'lines', i, ln)
        meta['per_frame'].append({})
    json.dump(meta, open(d + '/meta.json', 'w'))
    print('road', n)

# ---------------- procedural Jade (driver at the wheel, 3/4 front, facing screen-left) ----------------
SS = 2  # supersample

def P(pts, s=SS):
    return (np.array(pts, np.float32) * s).astype(np.int32)

def chaikin(pts, it=3, closed=True):
    pts = np.array(pts, np.float32)
    for _ in range(it):
        q = np.roll(pts, -1, 0) if closed else pts[1:]
        p0 = pts if closed else pts[:-1]
        a = 0.75 * p0 + 0.25 * q; b = 0.25 * p0 + 0.75 * q
        pts = np.stack([a, b], 1).reshape(-1, 2)
    return pts.tolist()

def jade(n=72):
    d = OUT + '/ld_jade'
    meta = dict(fps=FPS, frames=n, w=W, h=H, layers=['lines', 'matte', 'face', 'features', 'hair'],
                note='procedural stand-in figure for look-dev; not a likeness', per_frame=[])
    for i in range(n):
        t = i / FPS
        br = np.sin(t * 2 * np.pi * 0.25) * 2.0                   # breathing
        look = np.sin(t * 2 * np.pi * 0.11 - 0.6)                 # head yaw −1..1 (toward the text ↔ toward the road)
        tilt = np.sin(t * 2 * np.pi * 0.07) * 0.03
        cx, cy = 978 + 6 * look, 292 + br * 0.3
        hw, hh = 60, 78
        Hs, Ws = H * SS, W * SS
        matte = np.zeros((Hs, Ws), np.uint8); face = np.zeros_like(matte); hair = np.zeros_like(matte)
        lines = np.zeros_like(matte); feat = np.zeros_like(matte)
        def rot(p):
            x, y = p[0] - cx, p[1] - cy; c, s_ = np.cos(tilt), np.sin(tilt)
            return [cx + c * x - s_ * y, cy + s_ * x + c * y]
        L = lambda pts, wdt=2, img=lines: cv2.polylines(img, [P(pts)], False, 255, max(1, int(wdt * SS)), cv2.LINE_AA)
        # torso: seated, shoulders slightly hunched toward the wheel
        sy = 452 + br
        torso = [(770, 720), (790, sy + 70), (835, sy + 18), (905, sy - 4), (cx - 26, 392), (cx + 26, 392),
                 (1052, sy - 4), (1120, sy + 18), (1165, sy + 70), (1185, 720)]
        cv2.fillPoly(matte, [P(chaikin(torso[1:-1], 2, False) and [torso[0]] + chaikin(torso[1:-1], 2, False) + [torso[-1]])], 255, cv2.LINE_AA)
        cv2.fillPoly(matte, [P([(cx - 25, 340), (cx + 25, 340), (cx + 28, 405), (cx - 28, 405)])], 255, cv2.LINE_AA)  # neck
        # face: soft oval with a gentle chin, yaw squeezes the far side
        jaw = []
        for a_ in np.linspace(0, 2 * np.pi, 96, endpoint=False):
            ca, sa = np.cos(a_), np.sin(a_)
            x = ca * hw * (1 - 0.08 * look * np.sign(ca)); y = sa * hh
            if sa > 0: x *= 1 - 0.22 * sa ** 3
            jaw.append(rot((cx + x, cy + y)))
        cv2.fillPoly(matte, [P(jaw)], 255, cv2.LINE_AA); cv2.fillPoly(face, [P(jaw)], 255, cv2.LINE_AA)
        # hair: long, straight, centre part; falls in front of the shoulders
        part = cx + 4 + 4 * look
        outer = [(cx - 70, cy + 10), (cx - 76, cy - 40), (cx - 50, cy - 88), (part, cy - 100), (cx + 52, cy - 88), (cx + 78, cy - 40),
                 (cx + 74, cy + 30), (cx + 80, cy + 120), (cx + 92, sy + 40), (cx + 96, sy + 120), (cx + 58, sy + 128),
                 (cx + 52, sy + 30), (cx + 50, cy + 100), (cx + 56, cy + 10), (cx + 48, cy - 50), (part + 6, cy - 78),
                 (part - 6, cy - 78), (cx - 48, cy - 50), (cx - 56, cy + 10), (cx - 50, cy + 100), (cx - 52, sy + 30),
                 (cx - 58, sy + 128), (cx - 96, sy + 120), (cx - 92, sy + 40), (cx - 80, cy + 120), (cx - 74, cy + 30)]
        outer = chaikin([rot(p) for p in outer], 3)
        cv2.fillPoly(hair, [P(outer)], 255, cv2.LINE_AA); cv2.fillPoly(matte, [P(outer)], 255, cv2.LINE_AA)
        face = cv2.bitwise_and(face, cv2.bitwise_not(hair))
        # interior lines outside the face: collar, zip, sleeve seams, the wheel she holds, knuckles
        L([(cx - 28, 405), (cx - 2, 448 + br), (cx + 28, 405)])
        L([(cx - 2, 448 + br), (cx, 720)], 1.2)
        L([(842, sy + 24), (868, 610), (876, 720)], 1.2); L([(1113, sy + 24), (1088, 610), (1080, 720)], 1.2)
        cv2.ellipse(lines, (int(cx * SS), int(812 * SS)), (int(300 * SS), int(150 * SS)), 0, 200, 340, 255, int(3 * SS), cv2.LINE_AA)
        for hx, hy in [(752 + 0, 676), (1204, 676)]:
            hx = cx + (hx - 978)
            hand = [(hx - 30, hy - 4), (hx - 8, hy - 26), (hx + 24, hy - 22), (hx + 34, hy + 4), (hx + 18, hy + 24), (hx - 22, hy + 20)]
            cv2.fillPoly(matte, [P(hand)], 255, cv2.LINE_AA)
            for k in range(3): L([(hx - 14 + k * 12, hy - 14), (hx - 11 + k * 12, hy + 12)], 1)
        # features (the only lines allowed inside the face): eyes at full size, brows, nose tip; hair-edge strands
        L([rot((part, cy - 78)), rot((cx - 30, cy - 62)), rot((cx - 52, cy - 30))], 1.6, feat)
        L([rot((part, cy - 78)), rot((cx + 32, cy - 62)), rot((cx + 52, cy - 30))], 1.6, feat)
        blink = 1.0 if (t % 3.4) > 0.13 else 0.12
        ex = 27
        for side in (-1, 1):
            sq = 1 - 0.10 * look * side
            ecx, ecy = cx + side * ex * sq - 3 * look, cy - 4
            ew, eh = 17 * sq, 8.5 * blink
            # upper lid (heavier), lower lid (light) — almond, never thinned
            up = [rot((ecx + ew * np.cos(a_), ecy - eh * np.sin(a_))) for a_ in np.linspace(0, np.pi, 18)]
            lo = [rot((ecx + ew * np.cos(a_), ecy + eh * 0.8 * np.sin(a_))) for a_ in np.linspace(0.15, np.pi - 0.15, 14)]
            L(up, 2.6, feat); L(lo, 1.2, feat)
            if blink > 0.5:
                ic = rot((ecx - 3.5 * look, ecy + 0.5))
                cv2.circle(feat, (int(ic[0] * SS), int(ic[1] * SS)), int(6.8 * SS), 255, -1, cv2.LINE_AA)
            L([rot((ecx - 18 * side * -1 if False else ecx - 17, ecy - 19)), rot((ecx, ecy - 23)), rot((ecx + 17, ecy - 20))], 2.4, feat)
        nx = cx - 6 * look
        L([rot((nx - 5, cy + 28)), rot((nx + 1, cy + 31)), rot((nx + 6, cy + 28))], 1.8, feat)
        mouth = rot((cx - 4 * look, cy + 50))
        down = lambda a_: cv2.resize(a_, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        save(d, 'matte', i, down(matte)); save(d, 'face', i, down(face)); save(d, 'hair', i, down(hair))
        save(d, 'lines', i, down(lines)); save(d, 'features', i, down(feat))
        meta['per_frame'].append(dict(mouth=[float(mouth[0]), float(mouth[1]), 30.0], tilt=float(tilt)))
    json.dump(meta, open(d + '/meta.json', 'w'))
    print('jade', n)

if __name__ == '__main__':
    which = sys.argv[1:] or ['suits', 'road', 'jade']
    for k in which: globals()[k]()
