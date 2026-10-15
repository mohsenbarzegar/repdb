# RepDB — exercise dataset & API SaaS (working name)

An ExerciseDB-style product built at **£0**: dataset + looping demo GIFs +
API + storefront, designed to sit alongside Trainloop (its first customer).

## The zero-cost formula
| Layer | Choice | Cost |
|---|---|---|
| Data | free-exercise-db — 876 exercises, **Unlicense (public domain)**, verified from source | £0 |
| Media | Looping GIFs generated from the dataset's public-domain start/end photos (PIL crossfade) | £0 |
| API | Zero-dependency Node server **or** a pre-generated static JSON tree — no server needed | £0 |
| Hosting (planned) | Cloudflare Pages / GitHub Pages free tiers for site + static API + media | £0 |
| Tooling | Built with AI assistance; Python + Node stdlib only | £0 |

## What "replicate ExerciseDB" means here — and what it doesn't
Same **product**: ExerciseDB-shaped schema (`id, name, bodyPart, target,
secondaryMuscles, equipment, gifUrl, instructions…`), the same endpoint
shapes, dataset tiers, and a storefront. **Not** their assets: ExerciseDB's
GIFs, text and branding are their copyright (they actively correct
re-uploads), so every asset here is public-domain or original. That's what
makes £0 *legal*, not just cheap.

## Status 2026-10-15 (evening)
- Enhanced media COMPLETE for all 873 two-photo exercises: aligned,
  colour-matched, locked-background composite loops at 540×540
  (MP4 primary on the web; 540 GIFs in the local dataset copy).
- Camera-lock QA per exercise (background-agreement score, shipped in the
  data as `cameraLock`): **locked 572 · usable 133 · angle_mismatch 168**
  (source pair shot from two different angles — flagged, never hidden) ·
  3 exercises have <2 photos and ship data + photos only.
- Node API passes end-to-end tests (all route shapes, search, filters,
  media, static tree, storefront, docs).
- Hosting: GitHub Pages (public repo) — site + static API + media.

## Layout
- `data/exercises.json` — full dataset (876) in RepDB schema
- `data/upstream-exercises.json` + `UPSTREAM-LICENSE.txt` — source + licence
- `api-static/v1/` — static API tree (exercises, per-exercise, per-filter, lists)
- `media/gif/` — 180×180 loops (all 873); `media/enhanced/` — 540×540 locked-camera MP4 loops (all 873) + GIFs (local dataset)
- `media/img/` — original start/end photos, self-hosted
- `server/server.js` — zero-dependency Node API + site server (`PORT=8787 node server/server.js`)
- `site/` — storefront (`index.html` with live exercise browser) + `docs.html`
- `scripts/build_dataset.py` — upstream → RepDB schema + static API
- `scripts/make_gifs.py` — photo download + GIF generation (multiprocess)

## Run it
```bash
python3 scripts/build_dataset.py     # dataset + static API
python3 scripts/make_gifs.py 60      # media (180s for all, 360s for core ~60+)
node server/server.js                # http://localhost:8787
```

## Honest gaps vs ExerciseDB (v1)
- **Media**: photo crossfade loops ≠ their smooth 3D renders. Real-human
  photos, accurate start/end positions, but motion is a blend, not a true
  movement capture. Upgrade paths (priced in the research report): AI mocap
  pipeline, or licensing.
- **Taxonomy**: 11 fields vs their Pro 17 (no similar/substitution graph yet —
  computable from target/equipment/mechanic overlap when wanted).
- **Counts**: 876 vs their 1,394. wger (CC-BY-SA) could add more later, with
  share-alike obligations to weigh first.
- Male/female coverage and non-English names/instructions not yet included.

## Next steps (not yet done, need Mohsen's call)
1. Name/brand final + domain (free subdomain to start).
2. Deploy static stack to Cloudflare Pages/GitHub Pages (free).
3. List the API on RapidAPI (free tier listing) for distribution.
4. Trainloop consumes it as its exercise-media source.
