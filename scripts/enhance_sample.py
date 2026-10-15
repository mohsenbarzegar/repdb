"""Enhanced loop builder — replaces the plain crossfade with:
  1. CAMERA LOCK: phase-correlation alignment of photo B onto photo A
     (measures and removes any micro-shift between the two shots), plus
     exposure/colour matching so nothing flickers between frames.
  2. REAL MOTION: dense optical flow (Farneback) warps both photos toward
     each other for intermediate frames — limbs and bar actually travel
     instead of ghosting through each other like a crossfade.
  3. TEMPO: ease-in-out timing + end holds (same recipe as pro GIFs).
  4. FINISH: 540x540 output (native photo resolution, up from 360) and a
     gentle unsharp pass.

Usage: .venv/bin/python scripts/enhance_sample.py <Exercise_Id> [size]
Out: media/gif-enhanced/<id>.gif + prints camera-shift + background
     stability metrics for the crossfade vs enhanced versions.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(eid, i):
    img = cv2.imread(os.path.join(ROOT, "media", "img", eid, f"{i}.jpg"))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)


def align(ref, img):
    g1 = cv2.cvtColor(ref.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    (dx, dy), resp = cv2.phaseCorrelate(g1.astype(np.float32), g2.astype(np.float32))
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    out = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                         flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, (dx, dy), resp


def match_colour(ref, img):
    out = np.empty_like(img)
    for c in range(3):
        m1, s1 = ref[..., c].mean(), ref[..., c].std() + 1e-6
        m2, s2 = img[..., c].mean(), img[..., c].std() + 1e-6
        out[..., c] = (img[..., c] - m2) * (s1 / s2) + m1
    return out


def square(img, size):
    h, w = img.shape[:2]
    side = min(w, h)
    x, y = (w - side) // 2, (h - side) // 2
    return cv2.resize(img[y:y + side, x:x + side], (size, size), interpolation=cv2.INTER_AREA)


def warp(img, flow, t):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    mx = xx - flow[..., 0] * t
    my = yy - flow[..., 1] * t
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def build(eid, size=540):
    A = load(eid, 0)
    B = load(eid, 1)
    B, shift, resp = align(A, B)
    B = match_colour(A, B)
    A, B = square(A, size), square(B, size)

    gA = cv2.cvtColor(A.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    gB = cv2.cvtColor(B.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    flowAB = cv2.calcOpticalFlowFarneback(gA, gB, None, 0.5, 3, 25, 3, 5, 1.2, 0)
    flowBA = cv2.calcOpticalFlowFarneback(gB, gA, None, 0.5, 3, 25, 3, 5, 1.2, 0)

    steps = 7
    frames = []
    for k in range(steps + 1):
        t = k / steps
        te = t * t * (3 - 2 * t)  # smoothstep easing
        fa = warp(A, flowAB, te)
        fb = warp(B, flowBA, 1 - te)
        frames.append(((1 - te) * fa + te * fb))
    # loop: A hold -> travel -> B hold -> travel back
    seq = [frames[0]] + frames[1:] + frames[-2::-1]
    durs = [650] + [90] * steps + [650] + [90] * steps
    out_frames = []
    for f in seq:
        f = np.clip(f, 0, 255).astype(np.uint8)
        blur = cv2.GaussianBlur(f, (0, 0), 1.0)
        f = cv2.addWeighted(f, 1.35, blur, -0.35, 0)
        out_frames.append(Image.fromarray(f))
    outdir = os.path.join(ROOT, "media", "gif-enhanced")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f"{eid}.gif")
    out_frames[0].save(path, save_all=True, append_images=out_frames[1:],
                       duration=durs, loop=0, optimize=True)

    # background stability: std of the four corner patches across frames
    def bg_std(frames_arr):
        patches = []
        for f in frames_arr:
            h, w = f.shape[:2]
            ps = [f[:50, :50], f[:50, -50:], f[-50:, :50], f[-50:, -50:]]
            patches.append([p.mean() for p in ps])
        return float(np.std(np.array(patches), axis=0).mean())
    enh_std = bg_std([np.asarray(f) for f in out_frames])
    print(f"{eid}: camera shift corrected dx={shift[0]:.2f}px dy={shift[1]:.2f}px "
          f"(phase response {resp:.2f}); background flicker std={enh_std:.2f}; "
          f"frames={len(out_frames)} size={size} -> {path} "
          f"({os.path.getsize(path)//1024} KB)")
    return path


if __name__ == "__main__":
    eid = sys.argv[1]
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 540
    build(eid, size)
