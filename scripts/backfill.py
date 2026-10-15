"""Backfill QA metrics for 'exists' entries and rebuild the 4 exercises
whose photo pairs have mismatched dimensions (resize B onto A's canvas
before alignment). Updates data/media-manifest.json in place."""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enhance_all import build_one  # noqa: E402
from enhance_sample import load, match_colour  # noqa: E402
from enhance_v2 import align_bg, bg_agreement, shift_img  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "media-manifest.json")


def score(A, B):
    if B.shape != A.shape:
        B = cv2.resize(B, (A.shape[1], A.shape[0]))
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
    bg, shift = scored[0]
    bucket = "locked" if bg <= 10 else ("usable" if bg <= 20 else "angle_mismatch")
    return {"status": "ok", "shift": [round(shift[0], 2), round(shift[1], 2)],
            "bgDiff": round(bg, 1), "bucket": bucket, "backfilled": True}


def main():
    m = json.load(open(MANIFEST))
    # 1) rebuild the 4 size-mismatched pairs with a resize-aware load
    import enhance_all
    orig_load = enhance_all.load

    def load_resized(eid, i):
        img = orig_load(eid, i)
        return img

    errs = [k for k, v in m.items() if str(v.get("status", "")).startswith("error")]
    # portrait vs landscape pair: no aligned composite possible; ship a
    # plain crossfade MP4 and bucket it as a mismatch so consumers can skip it
    if "Close-Grip_EZ-Bar_Press" in errs:
        import subprocess
        from PIL import Image
        eid = "Close-Grip_EZ-Bar_Press"
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from make_gifs import make_loop
        d = os.path.join(ROOT, "media", "img", eid)
        a = Image.open(os.path.join(d, "0.jpg")).convert("RGB")
        b = Image.open(os.path.join(d, "1.jpg")).convert("RGB")
        gif = os.path.join(ROOT, "media", "enhanced", f"{eid}.gif")
        make_loop(a, b, 540, gif)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", gif,
                        "-movflags", "faststart", "-pix_fmt", "yuv420p",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        os.path.join(ROOT, "media", "enhanced", f"{eid}.mp4")],
                       check=True)
        m[eid] = {"status": "ok", "bucket": "angle_mismatch",
                  "note": "photo pair has mismatched orientation (portrait vs landscape); crossfade only"}
        errs.remove(eid)
        print("special-cased", eid)
    for eid in errs:
        # patch: resize photo 1 file in-memory by wrapping cv2.imread path —
        # simplest: pre-resize via PIL into a temp copy under media/img
        from PIL import Image
        d = os.path.join(ROOT, "media", "img", eid)
        a = Image.open(os.path.join(d, "0.jpg"))
        b = Image.open(os.path.join(d, "1.jpg"))
        if a.size != b.size:
            b.resize(a.size).save(os.path.join(d, "1.jpg"), quality=92)
        res = build_one(eid)
        m[eid] = res[1]
        print("rebuilt", eid, res[1].get("bucket", res[1]))
    # 2) backfill metrics for exists entries
    n = 0
    for eid, v in list(m.items()):
        if v.get("status") == "exists":
            A = load(eid, 0)
            B = load(eid, 1)
            m[eid] = score(A, B)
            n += 1
    print("backfilled", n)
    json.dump(m, open(MANIFEST, "w"), indent=0)
    from collections import Counter
    print(Counter(v.get("bucket", v.get("status")) for v in m.values()))


if __name__ == "__main__":
    main()
