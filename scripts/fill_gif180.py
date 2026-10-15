"""Fill any missing 180x180 crossfade GIFs (photos already local)."""
import json
import os
import sys
from multiprocessing import Pool

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_gifs import make_loop  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def job(eid):
    g = os.path.join(ROOT, "media", "gif", f"{eid}.gif")
    if os.path.exists(g):
        return (eid, "exists")
    d = os.path.join(ROOT, "media", "img", eid)
    try:
        a = Image.open(os.path.join(d, "0.jpg")).convert("RGB")
        b = Image.open(os.path.join(d, "1.jpg")).convert("RGB")
        make_loop(a, b, 180, g)
        return (eid, "made")
    except Exception as e:
        return (eid, f"skip: {e}")


if __name__ == "__main__":
    raw = json.load(open(os.path.join(ROOT, "data", "upstream-exercises.json")))
    ids = [e["id"] for e in raw if len(e.get("images") or []) >= 2]
    with Pool(2) as pool:
        res = pool.map(job, ids)
    from collections import Counter
    print(Counter(s for _, s in res))
