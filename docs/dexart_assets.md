# DexArt simulation assets: provenance

The official DexArt asset archive was downloaded successfully on 2026-09-28. No mirror was needed. The [official DexArt README](https://github.com/Kami-code/dexart-release/blob/main/README.md) links this archive, and the [official DP3 README](https://github.com/YanjieZe/3D-Diffusion-Policy/blob/master/README.md) independently links the same Google Drive file ID.

- Official published URL: <https://drive.usercontent.google.com/download?id=1DxRfB4087PeM3Aejd6cR-RQVgOKdNrL4&export=download&authuser=0>
- Download entry URL used by gdown: <https://drive.google.com/uc?id=1DxRfB4087PeM3Aejd6cR-RQVgOKdNrL4>
- Google Drive file ID: `1DxRfB4087PeM3Aejd6cR-RQVgOKdNrL4`
- Local archive: `data/dexart/assets_official.zip`
- SHA-256: `82632391d0a62b696302677796b716a0ad88d8aad5942e60a79c8142fc8fdf33`
- Official source repository: <https://github.com/Kami-code/dexart-release>
- Local source checkout commit: `d6ab75e1a0b81384d1ac918cbfd4d97b1f230149`
- Extracted simulation assets: `data/dexart/source/assets/`

The checksum was computed locally from the downloaded archive; it is a reproducibility identifier, not an independent publisher-signed integrity guarantee. The official archive contains 22,924 entries and 500,844,647 uncompressed bytes. Only the simulation-related subtrees were extracted:

| Subtree | Uncompressed bytes | Purpose |
|---|---:|---|
| `assets/sapien` | 249,540,009 | Articulated object models, meshes and metadata |
| `assets/misc` | 134,128,842 | Rendering textures, lighting and miscellaneous geometry |
| `assets/robot` | 4,683,667 | Allegro hand and xArm6 robot assets |
| `assets/annotation` | 40,761 | Task, joint and robot-placement annotations |

The selected subtrees contain 22,819 archive entries and 388,393,279 uncompressed bytes. `assets/rl_checkpoints` (105,210,984 bytes) and `assets/vision_pretrain` (7,240,384 bytes) were deliberately not extracted. The Astra evaluation does not need trained RL or vision policies. The archive is retained locally for reproducibility, but no checkpoint has been loaded or executed by this asset-preparation step.

Before extraction every entry was checked for absolute paths, `..` components, backslashes and symbolic links; none were present. Every path started with `assets`. The extraction destination was checked to have no existing `assets` subtree so source files or previous assets were not overwritten. A local reproducible validation/extraction helper is at `data/dexart/prepare_assets.py`; it checks the archive checksum and permits only the four named subtrees. The helper refuses to overwrite existing extracted assets.

## Licensing and redistribution

DexArt source code includes an Apache-2.0 `LICENSE` in its official repository. The downloaded asset archive does not contain a separate file named LICENSE or COPYING. Code licensing alone does not establish that every third-party object mesh, robot model, texture or checkpoint is covered by the same license. No independent asset-wide redistribution license was verified during this download. The assets and archive remain under ignored local `data/` and are not committed or republished in this framework's repository. Users obtain them from the official release link and should retain applicable upstream asset terms.

Successful asset preparation establishes that the required simulation files are available; simulator loading, visual rendering, action semantics, sensor isolation and task evaluation are separate checks performed by the adapter implementation.
