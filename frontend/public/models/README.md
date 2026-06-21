# 3D asteroid models

Drop `.glb` model files here and the specimen viewer (object detail panel) will
load them. Any `.glb` works, pick whatever looks good to you.

## Filenames the app looks for

- `asteroid.glb` — generic model used for every object without a specific one (add this first)
- `eros.glb`, `itokawa.glb`, `bennu.glb`, `ryugu.glb`, `vesta.glb`, `ida.glb`, `gaspra.glb` — real shape models used for those named asteroids

Only `asteroid.glb` is needed to light up the whole catalog; the named ones are
optional upgrades for the famous bodies.

## Where to get free, public-domain models

- NASA Science 3D resources: https://science.nasa.gov/3d-resources/ (Eros, Itokawa, Bennu, Vesta, Ida, Gaspra)
- NASA Bennu (OBJ + glTF): https://solarsystem.nasa.gov/resources/2403/bennu-3d-model/
- NASA Itokawa: https://science.nasa.gov/resource/asteroid-itokawa-3d-model/
- 3D Asteroid Catalogue: https://3d-asteroids.space/
- A generic CC0 asteroid rock: search Sketchfab / Poly Pizza for "asteroid" filtered to CC0/Downloadable, export as `.glb`

If a model downloads as `.obj`/`.gltf`, convert to `.glb` (e.g. drag into
https://gltf.report or use `gltf-pipeline`), then rename per the list above.

The viewer auto-centers, scales, lights, and slowly rotates whatever you drop in.
