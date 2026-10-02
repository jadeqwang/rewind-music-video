"""Extract rotoscope guide maps from a Seedance base clip.

For every frame (24 fps) writes, under OUT/<name>/:
  g_%04d.png  RGB guide: R = ink line strength (XDoG), G = smoothed tone (luminance), B = matte (1 = subject)
  c_%04d.jpg  bilateral-smoothed color, used only to classify inks (never shown)
and meta.json (frame count, size, fps, key: green|none).

The JS renderer redraws the frame from these guides; the clip itself is never composited.
"""
import json
import os
import sys

import cv2
import numpy as np


def xdog(gray, sigma=0.9, k=1.6, tau=0.985, eps=-0.012, phi=60.0):
    g = gray.astype(np.float32) / 255.0
    a = cv2.GaussianBlur(g, (0, 0), sigma)
    b = cv2.GaussianBlur(g, (0, 0), sigma * k)
    d = a - tau * b
    e = np.where(d >= eps, 1.0, 1.0 + np.tanh(phi * (d - eps)))
    return 1.0 - np.clip(e, 0, 1)  # 1 = ink


def green_matte(bgr):
    f = bgr.astype(np.float32) / 255.0
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    # key strength: how much green dominates
    k = g - np.maximum(r, b)
    alpha = 1.0 - np.clip((k - 0.12) / 0.22, 0, 1)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8)
    # remove specks
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return np.clip(alpha, 0, 1)


def despill(bgr, alpha):
    f = bgr.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    lim = np.maximum(r, b)
    g2 = np.where(g > lim, lim + (g - lim) * 0.15, g)
    out = np.stack([b, g2, r], -1)
    return np.clip(out, 0, 255).astype(np.uint8)


def process(clip, out_dir, key="auto", size=(1280, 720)):
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(clip)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    i = 0
    first = None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if (fr.shape[1], fr.shape[0]) != size:
            fr = cv2.resize(fr, size, interpolation=cv2.INTER_AREA)
        if first is None:
            first = fr
            if key == "auto":
                hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
                border = np.concatenate([hsv[:20].reshape(-1, 3), hsv[:, :20].reshape(-1, 3), hsv[:, -20:].reshape(-1, 3)])
                green = ((border[:, 0] > 35) & (border[:, 0] < 85) & (border[:, 1] > 120)).mean()
                key = "green" if green > 0.6 else "none"
        if key == "green":
            alpha = green_matte(fr)
            fr = despill(fr, alpha)
        else:
            alpha = np.ones(fr.shape[:2], np.float32)
        smooth = cv2.bilateralFilter(fr, 7, 40, 5)
        gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
        line = xdog(gray)
        # suppress lines outside the subject (keyed clips) and very faint strokes
        line = np.where(line < 0.12, 0, line) * np.clip(alpha * 1.4, 0, 1)
        if key == "green":
            # matte silhouette edge becomes an outline too (anime outer line)
            edge = cv2.morphologyEx((alpha > 0.5).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(np.float32)
            line = np.maximum(line, cv2.GaussianBlur(edge, (0, 0), 0.6))
        tone = cv2.GaussianBlur(gray, (0, 0), 1.2)
        guide = np.dstack([(alpha * 255).astype(np.uint8), tone, (line * 255).astype(np.uint8)])  # BGR order -> R=line
        cv2.imwrite(f"{out_dir}/g_{i:04d}.png", guide, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        cv2.imwrite(f"{out_dir}/c_{i:04d}.jpg", smooth, [cv2.IMWRITE_JPEG_QUALITY, 88])
        i += 1
    json.dump({"frames": i, "w": size[0], "h": size[1], "fps": fps, "key": key}, open(f"{out_dir}/meta.json", "w"))
    return i, key


if __name__ == "__main__":
    n, key = process(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "auto")
    print(json.dumps({"frames": n, "key": key}))
