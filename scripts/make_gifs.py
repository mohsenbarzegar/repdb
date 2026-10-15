"""Download upstream photos and build looping start<->end crossfade GIFs.

Zero cost: source photos are public domain (Unlicense). Two sizes mirror
the usual dataset tiers: 180x180 for every exercise, 360x360 for a core set
(pass --core360 N to control how many, ordered by name; bench/squat/curl
family always included). Usage: python3 scripts/make_gifs.py [core360]
"""
import json
import os
import subprocess
import sys
from multiprocessing import Pool

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises"
CORE_WORDS = ("bench press", "squat", "curl", "deadlift", "press", "row", "pull-up", "lunge")


def square(im, size):
    w, h = im.size
    side = min(w, h)
    im = im.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
    return im.resize((size, size), Image.LANCZOS)


def make_loop(a, b, size, path):
    A, B = square(a, size), square(b, size)
    frames, durs = [A], [650]
    for t in (0.25, 0.5, 0.75):
        frames.append(Image.blend(A, B, t))
        durs.append(70)
    frames.append(B)
    durs.append(650)
    for t in (0.75, 0.5, 0.25):
        frames.append(Image.blend(A, B, t))
        durs.append(70)
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=durs, loop=0, optimize=True)


def job(args):
    ex, do360 = args
    eid = ex["id"]
    d = os.path.join(ROOT, "media", "img", eid)
    os.makedirs(d, exist_ok=True)
    paths = []
    for i in range(2):
        p = os.path.join(d, f"{i}.jpg")
        if not os.path.exists(p):
            subprocess.run(["curl", "-sL", "-o", p, f"{RAW}/{eid}/{i}.jpg"], check=True)
        paths.append(p)
    try:
        a, b = Image.open(paths[0]).convert("RGB"), Image.open(paths[1]).convert("RGB")
    except Exception as e:
        return (eid, f"skip: {e}")
    g180 = os.path.join(ROOT, "media", "gif", f"{eid}.gif")
    make_loop(a, b, 180, g180)
    if do360:
        g360 = os.path.join(ROOT, "media", "gif360", f"{eid}.gif")
        os.makedirs(os.path.dirname(g360), exist_ok=True)
        make_loop(a, b, 360, g360)
    return (eid, "ok")


def main():
    core360 = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    raw = json.load(open(os.path.join(ROOT, "data", "upstream-exercises.json")))
    raw = [e for e in raw if len(e.get("images") or []) >= 2]
    raw.sort(key=lambda e: e["name"])
    core_ids = {e["id"] for e in raw
                if any(w in e["name"].lower() for w in CORE_WORDS)}
    extra = [e for e in raw if e["id"] not in core_ids][:max(0, core360 - len(core_ids))]
    do360_ids = core_ids | {e["id"] for e in extra}
    print(f"total {len(raw)}, with 360: {len(do360_ids)}", flush=True)
    with Pool(2) as pool:
        for i, (eid, status) in enumerate(pool.imap_unordered(
                job, [(e, e["id"] in do360_ids) for e in raw], chunksize=8)):
            if status != "ok":
                print(" ", eid, status, flush=True)
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(raw)}", flush=True)
    print("GIFs done")


if __name__ == "__main__":
    main()
