#!/usr/bin/env python3
"""Side-by-side face crops (same scale: face width -> 300 px, eye line level) for visual review.
  python3 tools/likeness/compare.py OUT.jpg IMG [IMG ...]   (label = file name)"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as MS


def crop(path, fw_px=300, size=(420, 560)):
    rgb = MS.load_rgb(path); lm = MS.landmarks(rgb)
    if lm is None:
        return np.full((size[1], size[0], 3), 80, np.uint8)
    pts = lm[0]
    a, b = pts[MS.R_OUT, :2], pts[MS.L_OUT, :2]
    fw = np.linalg.norm(pts[MS.CHEEK_L, :2] - pts[MS.CHEEK_R, :2])
    ang = np.degrees(np.arctan2(b[1] - a[1], b[0] - a[0])); sc = fw_px / fw
    c = pts[MS.GLABELLA, :2]
    M = cv2.getRotationMatrix2D((float(c[0]), float(c[1])), ang, sc)
    M[:, 2] += np.array([size[0] / 2, size[1] * 0.42]) - c
    return cv2.warpAffine(rgb, M, size, flags=cv2.INTER_AREA, borderValue=(40, 40, 40))


def main():
    out, ims = sys.argv[1], sys.argv[2:]
    tiles = []
    for p in ims:
        label = None
        if "=" in p:
            label, p = p.split("=", 1)
        t = cv2.cvtColor(crop(p), cv2.COLOR_RGB2BGR)
        cv2.putText(t, (label or os.path.basename(p))[:34], (6, 20), 0, 0.55, (0, 255, 255), 2)
        tiles.append(t)
    cols = min(len(tiles), 5)
    while len(tiles) % cols: tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 92])


if __name__ == "__main__":
    main()
