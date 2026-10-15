"""Finalize after the batch: fold media QA into the dataset + static API.

Adds per exercise: videoUrl (enhanced 540 MP4), gifUrl540 (local dataset
file, not web-hosted due to size), cameraLock bucket from the manifest.
Removes gifUrl360 (superseded by the enhanced video).
Run: python3 scripts/finalize.py && python3 scripts/build_dataset.py is NOT
needed — this script regenerates the static API itself via build_dataset
functions on the updated records.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def main():
    manifest = json.load(open(os.path.join(ROOT, "data", "media-manifest.json")))
    data = json.load(open(os.path.join(ROOT, "data", "exercises.json")))
    for e in data:
        m = manifest.get(e["id"], {})
        e.pop("gifUrl360", None)
        e["videoUrl"] = f"media/enhanced/{e['id']}.mp4"
        e["gifUrl540"] = f"media/enhanced/{e['id']}.gif"
        e["cameraLock"] = m.get("bucket", "unknown")
        e["bgDiff"] = m.get("bgDiff")
    json.dump(data, open(os.path.join(ROOT, "data", "exercises.json"), "w"), indent=1)
    from collections import Counter
    print("cameraLock:", Counter(e["cameraLock"] for e in data))

    # regenerate static API from updated records (mirror of build_dataset)
    import shutil
    api = os.path.join(ROOT, "api-static")
    if os.path.exists(api):
        shutil.rmtree(api)
    os.makedirs(api)

    def dump(rel, payload):
        p = os.path.join(api, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(payload, open(p, "w"))

    dump("v1/exercises.json", data)
    for e in data:
        dump(f"v1/exercise/{e['id']}.json", e)
    for field, listname in (("bodyPart", "bodyPartList"), ("target", "targetList"),
                            ("equipment", "equipmentList")):
        vals = sorted({e[field] for e in data})
        dump(f"v1/{listname}.json", vals)
        for v in vals:
            dump(f"v1/{field}/{v.replace('/', '_')}.json",
                 [e for e in data if e[field] == v])
    dump("v1/search-index.json",
         [{"id": e["id"], "name": e["name"], "bodyPart": e["bodyPart"],
           "target": e["target"], "equipment": e["equipment"]} for e in data])
    print("static API regenerated")


if __name__ == "__main__":
    main()
