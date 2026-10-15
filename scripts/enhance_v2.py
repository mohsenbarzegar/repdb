"""Enhanced loop v2 — locked-off camera composite.

v1 flow-warp melted the barbell (150px travel + occlusion is beyond
Farneback). v2 instead guarantees a fixed camera by construction:
  1. Align photo B onto A (phase correlation) + colour/exposure match.
  2. Build a feathered motion mask from |A-B|: pixels that never change
     (the whole background) are taken from photo A in EVERY frame —
     background flicker is exactly zero, the camera cannot drift.
  3. Inside the mask, crossfade with smoothstep easing, 7 steps, holds
     at both ends (pro tempo recipe).
  4. 540x540, unsharp finish. Also writes an MP4 (ffmpeg) — same frames,
     a fraction of the GIF size.

Usage: .venv/bin/python scripts/enhance_v2.py <Exercise_Id>
"""
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enhance_sample import align, load, match_colour, square  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def align_bg(ref, img):
    """Shift from background bands only (top + bottom strips), best phase
    response wins, clamped to +-40px. Whole-frame correlation locks onto
    the moving lifter on big vertical moves (deadlift read +125px and
    smeared the floor); background bands stay honest."""
    h = ref.shape[0]
    bands = [(0, int(h * 0.22)), (int(h * 0.82), h)]
    g1 = cv2.cvtColor(ref.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    best = None
    for y0, y1 in bands:
        (dx, dy), resp = cv2.phaseCorrelate(g1[y0:y1], g2[y0:y1])
        if best is None or resp > best[1]:
            best = ((dx, dy), resp)
    (dx, dy), resp = best
    dx = float(np.clip(dx, -40, 40))
    dy = float(np.clip(dy, -40, 40))
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    out = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                         flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return out, (dx, dy), resp


def shift_img(img, dx, dy):
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                          flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def bg_agreement(A, B):
    """Mean |A-B| over the four corner patches (pure background)."""
    h, w = A.shape[:2]
    s = 70
    patches = [(0, 0), (0, w - s), (h - s, 0), (h - s, w - s)]
    return float(np.mean([np.abs(A[y:y + s, x:x + s] - B[y:y + s, x:x + s]).mean()
                          for y, x in patches]))


def build(eid, size=540):
    A = load(eid, 0)
    B = load(eid, 1)
    # candidate shifts: none, background-band phase, whole-frame phase
    # (small clamp). Score each by background agreement and keep the best —
    # blindly applying a subject-locked correlation is what broke deadlift.
    _, band_shift, _ = align_bg(A, B)
    gA = cv2.cvtColor(A.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    gB = cv2.cvtColor(B.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    (fx, fy), _ = cv2.phaseCorrelate(gA, gB)
    frame_shift = (float(np.clip(fx, -12, 12)), float(np.clip(fy, -12, 12)))
    cands = [(0.0, 0.0), band_shift, frame_shift]
    scored = []
    for dx, dy in cands:
        Bs = match_colour(A, shift_img(B, dx, dy))
        scored.append((bg_agreement(A, Bs), (dx, dy)))
    scored.sort()
    best_score, shift = scored[0]
    B = shift_img(B, *shift)
    print(f"  candidates {[(round(s,1), (round(dx,1), round(dy,1))) for s, (dx, dy) in scored]} -> shift {shift}, bg diff {best_score:.1f}")
    B = match_colour(A, B)
    A, B = square(A, size), square(B, size)

    diff = cv2.cvtColor(np.abs(A - B).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    mask = (diff > 18).astype(np.float32)
    mask = cv2.dilate(mask, np.ones((21, 21), np.float32))
    mask = cv2.GaussianBlur(mask, (0, 0), 6)[..., None]

    steps = 7
    frames = []
    for k in range(steps + 1):
        t = k / steps
        te = t * t * (3 - 2 * t)
        blend = (1 - te) * A + te * B
        frames.append(A * (1 - mask) + blend * mask)
    seq = [frames[0]] + frames[1:] + frames[-2::-1]
    durs = [650] + [90] * steps + [650] + [90] * steps

    out_frames = []
    for f in seq:
        f = np.clip(f, 0, 255).astype(np.uint8)
        blur = cv2.GaussianBlur(f, (0, 0), 1.0)
        f = cv2.addWeighted(f, 1.3, blur, -0.3, 0)
        out_frames.append(Image.fromarray(f))

    outdir = os.path.join(ROOT, "media", "gif-enhanced2")
    os.makedirs(outdir, exist_ok=True)
    gif = os.path.join(outdir, f"{eid}.gif")
    out_frames[0].save(gif, save_all=True, append_images=out_frames[1:],
                       duration=durs, loop=0, optimize=True)
    # MP4 from the same frames: expand GIF durations onto a 30fps timeline
    tmp = os.path.join(outdir, f"{eid}_frames")
    os.makedirs(tmp, exist_ok=True)
    timeline = []
    for img, d in zip(out_frames, durs):
        timeline += [img] * max(1, round(d / 33.3))
    for n, img in enumerate(timeline):
        cv2.imwrite(os.path.join(tmp, f"{n:03d}.png"),
                    cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR))
    mp4 = os.path.join(outdir, f"{eid}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30",
                    "-i", os.path.join(tmp, "%03d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)
    subprocess.run(["rm", "-rf", tmp])

    def bg_std(fr):
        ps = []
        for f in fr:
            a = np.asarray(f)
            ps.append([a[:50, :50].mean(), a[:50, -50:].mean(),
                       a[-50:, :50].mean(), a[-50:, -50:].mean()])
        return float(np.std(np.array(ps), axis=0).mean())
    print(f"{eid}: shift corrected {shift[0]:.2f},{shift[1]:.2f}px | "
          f"bg flicker std={bg_std(out_frames):.3f} | "
          f"GIF {os.path.getsize(gif)//1024} KB | MP4 {os.path.getsize(mp4)//1024} KB")
    return gif, mp4


if __name__ == "__main__":
    build(sys.argv[1])
