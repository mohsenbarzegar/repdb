"""RepDB dataset builder.

Transforms the public-domain free-exercise-db dataset (Unlicense) into an
ExerciseDB-style schema + a static API tree that can be hosted for free
(GitHub Pages / Cloudflare Pages) with no server at all.

Upstream fields : name, force, level, mechanic, equipment, primaryMuscles,
                  secondaryMuscles, instructions, category, images, id
RepDB fields     : id, name, bodyPart, target, secondaryMuscles, equipment,
                  gifUrl, imageUrls, instructions, level, category,
                  mechanic, force
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MUSCLE_TO_BODYPART = {
    "chest": "chest",
    "lats": "back", "traps": "back", "lower back": "back", "middle back": "back",
    "shoulders": "shoulders",
    "biceps": "upper arms", "triceps": "upper arms",
    "forearms": "lower arms",
    "abdominals": "waist",
    "quadriceps": "upper legs", "hamstrings": "upper legs", "glutes": "upper legs",
    "adductors": "upper legs", "abductors": "upper legs",
    "calves": "lower legs",
    "neck": "neck",
}


def main():
    raw = json.load(open(os.path.join(ROOT, "data", "upstream-exercises.json")))
    out = []
    for e in raw:
        primary = e.get("primaryMuscles") or []
        target = primary[0] if primary else "full body"
        body_part = MUSCLE_TO_BODYPART.get(target, "full body")
        imgs = e.get("images") or []
        out.append({
            "id": e["id"],
            "name": e["name"],
            "bodyPart": body_part,
            "target": target,
            "secondaryMuscles": e.get("secondaryMuscles") or [],
            "equipment": e.get("equipment") or "none",
            "gifUrl": f"media/gif/{e['id']}.gif",
            "gifUrl360": f"media/gif360/{e['id']}.gif",
            "imageUrls": [f"media/img/{e['id']}/{i}.jpg" for i in range(len(imgs))],
            "instructions": e.get("instructions") or [],
            "level": e.get("level"),
            "category": e.get("category"),
            "mechanic": e.get("mechanic"),
            "force": e.get("force"),
        })
    out.sort(key=lambda x: x["name"])
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "exercises.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("exercises:", len(out))

    # ---- static API tree (same shapes as the live server endpoints)
    api = os.path.join(ROOT, "api-static")
    if os.path.exists(api):
        shutil.rmtree(api)
    os.makedirs(api)

    def dump(rel, payload):
        p = os.path.join(api, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump(payload, f)

    dump("v1/exercises.json", out)
    for e in out:
        dump(f"v1/exercise/{e['id']}.json", e)
    for field, listname in (("bodyPart", "bodyPartList"), ("target", "targetList"),
                            ("equipment", "equipmentList")):
        vals = sorted({e[field] for e in out})
        dump(f"v1/{listname}.json", vals)
        for v in vals:
            safe = v.replace("/", "_")
            dump(f"v1/{field}/{safe}.json",
                 [e for e in out if e[field] == v])
    # search index for the storefront demo + API clients
    dump("v1/search-index.json",
         [{"id": e["id"], "name": e["name"], "bodyPart": e["bodyPart"],
           "target": e["target"], "equipment": e["equipment"]} for e in out])
    print("static API written to api-static/v1/")


if __name__ == "__main__":
    main()
