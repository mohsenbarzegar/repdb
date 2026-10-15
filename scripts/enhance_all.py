"""Batch enhanced pipeline over the full library (resumable).

For every exercise with 2 photos: candidate-shift scoring by background
agreement, colour match, locked-background composite loop at 540x540 ->
media/enhanced/<id>.mp4 + <id>.gif, with per-exercise QA metrics written
to data/media-manifest.json. Buckets by background agreement score:
  locked <= 10 | usable <= 20 | angle_mismatch > 20 (source pair was shot
  from two different camera angles; no processing can lock those).

Run: .venv/bin/python scripts/enhance_all.py
"""
import json
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enhance_sample import load, match_colour, square  # noqa: E402
from enhance_v2 import align_bg, bg_agreement, shift_img  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "media", "enhanced")
os.makedirs(OUT, exist_ok=True)
MANIFEST = os.path.join(ROOT, "data", "media-manifest.json")


def build_one(eid):
    mp4 = os.path.join(OUT, f"{eid}.mp4")
    gif = os.path.join(OUT, f"{eid}.gif")
    if os.path.exists(mp4) and os.path.exists(gif):
        return (eid, {"status": "exists"})
    try:
        A = load(eid, 0)
        B = load(eid, 1)
        _, band_shift, _ = align_bg(A, B)
        gA = cv2.cvtColor(A.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        gB = cv2.cvtColor(B.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        (fx, fy), _ = cv2.phaseCorrelate(gA, gB)
        frame_shift = (float(np.clip(fx, -12, 12)), float(np.clip(fy, -12, 12)))
        scored = []
        for dx, dy in [(0.0, 0.0), band_shift, frame_shift]:
            Bs = match_colour(A, shift_img(B, dx, dy))
            scored.append((bg_agreement(A, Bs), (dx, dy)))
        scored.sort()
        bg_diff, shift = scored[0]
        B = match_colour(A, shift_img(B, *shift))
        size = 540
        A2, B2 = square(A, size), square(B, size)
        diff = cv2.cvtColor(np.abs(A2 - B2).astype(np.uint8), cv2.COLOR_RGB2GRAY)
        mask = (diff > 18).astype(np.float32)
        mask = cv2.dilate(mask, np.ones((21, 21), np.float32))
        mask = cv2.GaussianBlur(mask, (0, 0), 6)[..., None]
        steps = 7
        frames = []
        for k in range(steps + 1):
            t = k / steps
            te = t * t * (3 - 2 * t)
            blend = (1 - te) * A2 + te * B2
            frames.append(A2 * (1 - mask) + blend * mask)
        seq = [frames[0]] + frames[1:] + frames[-2::-1]
        durs = [650] + [90] * steps + [650] + [90] * steps
        out_frames = []
        for f in seq:
            f = np.clip(f, 0, 255).astype(np.uint8)
            blur = cv2.GaussianBlur(f, (0, 0), 1.0)
            f = cv2.addWeighted(f, 1.3, blur, -0.3, 0)
            out_frames.append(Image.fromarray(f))
        out_frames[0].save(gif, save_all=True, append_images=out_frames[1:],
                           duration=durs, loop=0, optimize=True)
        tmp = os.path.join(OUT, f".tmp_{eid}")
        os.makedirs(tmp, exist_ok=True)
        timeline = []
        for img, d in zip(out_frames, durs):
            timeline += [img] * max(1, round(d / 33.3))
        for n, img in enumerate(timeline):
            cv2.imwrite(os.path.join(tmp, f"{n:03d}.png"),
                        cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30",
                        "-i", os.path.join(tmp, "%03d.png"), "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "20", mp4],
                       check=True)
        subprocess.run(["rm", "-rf", tmp])
        # flicker on corners
        ps = []
        for img in out_frames:
            a = np.asarray(img)
            ps.append([a[:50, :50].mean(), a[:50, -50:].mean(),
                       a[-50:, :50].mean(), a[-50:, -50:].mean()])
        flicker = float(np.std(np.array(ps), axis=0).mean())
        bucket = "locked" if bg_diff <= 10 else ("usable" if bg_diff <= 20 else "angle_mismatch")
        return (eid, {"status": "ok", "shift": [round(shift[0], 2), round(shift[1], 2)],
                      "bgDiff": round(bg_diff, 1), "flicker": round(flicker, 3),
                      "bucket": bucket,
                      "mp4KB": os.path.getsize(mp4) // 1024,
                      "gifKB": os.path.getsize(gif) // 1024})
    except Exception as e:
        return (eid, {"status": f"error: {e}"})


def main():
    raw = json.load(open(os.path.join(ROOT, "data", "upstream-exercises.json")))
    ids = [e["id"] for e in raw if len(e.get("images") or []) >= 2]
    manifest = {}
    if os.path.exists(MANIFEST):
        manifest = json.load(open(MANIFEST))
    todo = [i for i in ids if manifest.get(i, {}).get("status") not in ("ok", "exists")]
    print(f"total {len(ids)}, already done {len(ids) - len(todo)}, to run {len(todo)}", flush=True)
    with Pool(2) as pool:
        for n, (eid, res) in enumerate(pool.imap_unordered(build_one, todo, chunksize=2)):
            manifest[eid] = res
            if (n + 1) % 25 == 0:
                json.dump(manifest, open(MANIFEST, "w"), indent=0)
                print(f"  {n+1}/{len(todo)}", flush=True)
    json.dump(manifest, open(MANIFEST, "w"), indent=0)
    from collections import Counter
    print("buckets:", Counter(v.get("bucket", v.get("status")) for v in manifest.values()))


if __name__ == "__main__":
    main()
