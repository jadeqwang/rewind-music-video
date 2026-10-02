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
    g = gray.astype(np.float32) / 255.0
    g1 = cv2.GaussianBlur(g, (0, 0), sigma)
    g2 = cv2.GaussianBlur(g, (0, 0), sigma * k)
    d = g1 - tau * g2
    e = np.where(d >= eps, 1.0, 1.0 + np.tanh(phi * (d - eps)))
    return np.clip(1.0 - e, 0, 1)

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
    for (x0, y0, x1, y1) in [(150, 450, 330, 900), (420, 430, 640, 950), (680, 420, 860, 880), (470, 300, 560, 400), (220, 330, 290, 420), (700, 290, 770, 400)]:
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
    faces = [(255, 372, 150, 46), (515, 346, 160, 48), (737, 340, 145, 44)]
    meta = dict(fps=FPS, frames=n, w=W, h=H, layers=['lines', 'matte'], src='assets/tests/flux_schnell.jpg', per_frame=[])
    for i in range(n):
        u = i / (n - 1)
        s = (H / h) * (0.98 + 0.30 * u * u * 0 + 0.30 * u)          # push-in (they approach)
        bob = 5 * abs(np.sin(i / FPS * np.pi * 2.07))               # footsteps
        M = np.array([[s, 0, W / 2 - s * w / 2], [0, s, H * 0.98 - s * h + 120 * u + bob]], np.float32)
        g = cv2.warpAffine(cl, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
        mt = cv2.warpAffine(mm, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0).astype(np.float32) / 255
        ln = clean(xdog(g, sigma=1.0, tau=0.98, eps=0.015, phi=40), 30)
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
        ln = clean(xdog(g, sigma=1.1, tau=0.975, eps=0.02, phi=35), 40)
        save(d, 'lines', i, ln)
        meta['per_frame'].append({})
    json.dump(meta, open(d + '/meta.json', 'w'))
    print('road', n)

# ---------------- procedural Jade (driver at the wheel, 3/4 front, facing screen-left) ----------------
SS = 2  # supersample

def P(pts, s=SS):
    return (np.array(pts, np.float32) * s).astype(np.int32)

def jade(n=60):
    d = OUT + '/ld_jade'
    meta = dict(fps=FPS, frames=n, w=W, h=H, layers=['lines', 'matte', 'face', 'features', 'hair'],
                note='procedural stand-in figure for look-dev; not a likeness', per_frame=[])
    for i in range(n):
        t = i / FPS
        br = np.sin(t * 2 * np.pi * 0.28) * 3.0                  # breathing
        turn = 0.5 + 0.5 * np.sin(t * 2 * np.pi * 0.12 - 1.2)     # 0 = toward camera, 1 = toward road
        tilt = np.sin(t * 2 * np.pi * 0.09) * 0.04
        cx, cy = 960 - 18 * turn, 300 + br * 0.4                  # head centre
        hw, hh = 78, 100
        Hs, Ws = H * SS, W * SS
        matte = np.zeros((Hs, Ws), np.uint8); face = np.zeros_like(matte); hair = np.zeros_like(matte)
        lines = np.zeros_like(matte); feat = np.zeros_like(matte)
        def rot(p):
            x, y = p[0] - cx, p[1] - cy
            c, s_ = np.cos(tilt), np.sin(tilt)
            return [cx + c * x - s_ * y, cy + s_ * x + c * y]
        # torso / shoulders (seated, wheel in front)
        sh_y = 470 + br
        torso = [(700, 720), (735, sh_y + 60), (800, sh_y + 8), (900, sh_y - 18), (cx - 30, 395), (cx + 34, 395),
                 (1030, sh_y - 14), (1130, sh_y + 10), (1195, sh_y + 70), (1225, 720)]
        cv2.fillPoly(matte, [P(torso)], 255, cv2.LINE_AA)
        # neck
        cv2.fillPoly(matte, [P([(cx - 30, 360), (cx + 30, 360), (cx + 36, 420), (cx - 34, 420)])], 255, cv2.LINE_AA)
        # face oval (3/4: jaw shifted left with turn)
        jaw = []
        for a in np.linspace(0, 2 * np.pi, 80, endpoint=False):
            x = np.cos(a) * hw * (1 - 0.10 * turn * (np.cos(a) > 0)); y = np.sin(a) * hh
            if np.sin(a) > 0: x *= 1 - 0.28 * np.sin(a) ** 2; y *= 1.02  # chin taper
            jaw.append(rot((cx + x - 8 * turn * np.sin(a), cy + y)))
        cv2.fillPoly(matte, [P(jaw)], 255, cv2.LINE_AA)
        cv2.fillPoly(face, [P(jaw)], 255, cv2.LINE_AA)
        # hair: long, behind shoulders, side part, frames the face
        hair_out = [rot(p) for p in [(cx - 96, cy - 40), (cx - 80, cy - 112), (cx - 20, cy - 138), (cx + 60, cy - 128), (cx + 100, cy - 70),
                                     (cx + 108, cy + 40), (cx + 116, cy + 150), (cx + 132, cy + 245), (cx + 70, cy + 235), (cx + 62, cy + 120),
                                     (cx + 70, cy + 10), (cx + 55, cy - 70), (cx - 10, cy - 92), (cx - 60, cy - 60), (cx - 72, cy + 30),
                                     (cx - 88, cy + 140), (cx - 120, cy + 230), (cx - 150, cy + 215), (cx - 110, cy + 120), (cx - 104, cy + 20)]]
        cv2.fillPoly(hair, [P(hair_out)], 255, cv2.LINE_AA)
        cv2.fillPoly(matte, [P(hair_out)], 255, cv2.LINE_AA)
        face = cv2.bitwise_and(face, cv2.bitwise_not(hair))
        # interior lines (outside the face): collar, seams, the wheel rim she holds, fingers
        L = lambda pts, wdt=2, img=lines: cv2.polylines(img, [P(pts)], False, 255, wdt * SS, cv2.LINE_AA)
        L([(cx - 34, 420), (cx - 6, 470 + br), (cx + 34, 420)])                      # collar V
        L([(cx - 6, 470 + br), (cx - 2, 720)], 1)                                     # zip line
        L([(800, sh_y + 10), (830, 640), (842, 720)], 1)                              # sleeve seam
        L([(1130, sh_y + 12), (1105, 640), (1098, 720)], 1)
        # steering wheel rim (world line, part of the drawing)
        ax = (cx - 30) * SS, 820 * SS
        cv2.ellipse(lines, (int(ax[0]), int(ax[1])), (int(330 * SS), int(150 * SS)), 0, 196, 344, 255, 3 * SS, cv2.LINE_AA)
        # hands on wheel at ten-and-two
        for hx, hy, sgn in [(745, 690, -1), (1110, 676, 1)]:
            hand = [(hx - 34, hy - 6), (hx - 8, hy - 30), (hx + 26, hy - 26), (hx + 40, hy + 4), (hx + 22, hy + 28), (hx - 24, hy + 24)]
            cv2.fillPoly(matte, [P(hand)], 255, cv2.LINE_AA)
            for k in range(3): L([(hx - 18 + k * 14, hy - 18), (hx - 14 + k * 14, hy + 16)], 1)
        # hair/jaw contours (allowed inside the face rule): hair edge strands
        L([rot(p) for p in [(cx - 10, cy - 92), (cx + 30, cy - 60), (cx + 56, cy + 10)]], 2, feat)
        L([rot(p) for p in [(cx - 60, cy - 60), (cx - 74, cy + 10)]], 2, feat)
        # features: eyes at full size (almond), brows, nose tip, (lips are drawn live from the vocal track)
        ex = 34 - 6 * turn
        blink = 1.0 if (t % 3.1) > 0.12 else 0.15
        for side in (-1, 1):
            e_c = rot((cx - 14 * turn + side * ex, cy - 6))
            ew, eh = 24 - (6 * turn if side > 0 else 0), 11 * blink
            cv2.ellipse(feat, (int(e_c[0] * SS), int(e_c[1] * SS)), (int(ew * SS), int(eh * SS)), np.degrees(tilt), 0, 360, 255, int(2.4 * SS), cv2.LINE_AA)
            if blink > 0.5:
                cv2.circle(feat, (int((e_c[0] - 4 * turn - 2) * SS), int(e_c[1] * SS)), int(7.5 * SS), 255, -1, cv2.LINE_AA)
            b0 = rot((cx - 14 * turn + side * ex - 22, cy - 32)); b1 = rot((cx - 14 * turn + side * ex + 4, cy - 38)); b2 = rot((cx - 14 * turn + side * ex + 24, cy - 33))
            L([b0, b1, b2], 3, feat)
        L([rot((cx - 26 * turn - 4, cy + 34)), rot((cx - 26 * turn + 6, cy + 38))], 2, feat)   # nose tip
        mouth = rot((cx - 22 * turn, cy + 62))
        down = lambda a: cv2.resize(a, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        save(d, 'matte', i, down(matte)); save(d, 'face', i, down(face)); save(d, 'hair', i, down(hair))
        save(d, 'lines', i, down(lines)); save(d, 'features', i, down(feat))
        meta['per_frame'].append(dict(mouth=[float(mouth[0]), float(mouth[1]), 38.0], tilt=float(tilt)))
    json.dump(meta, open(d + '/meta.json', 'w'))
    print('jade', n)

if __name__ == '__main__':
    which = sys.argv[1:] or ['suits', 'road', 'jade']
    for k in which: globals()[k]()
