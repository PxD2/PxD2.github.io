# PXD Mesh (.pxdm): PXD2's compact 3D format

For store models, scans (Revopoint), CAD parts and game assets.

```
python tools/pxdmesh/pxdmesh.py pack scan.glb                       # scan.pxdm + scan.pxdm.glb + scan.pxdm.json
python tools/pxdmesh/pxdmesh.py pack bracket.stl --cad bracket.step # the editable CAD file travels with the mesh
python tools/pxdmesh/pxdmesh.py pack-dir scans/ -o stores/shop/assets   # a whole store, plus assets.json
```

What it does:
- **Geometry:** meshopt compression with quantization: 14-bit positions, 10-bit normals, 12-bit UVs. That's finer than a screen or a 3D printer can show.
- **Textures:** WebP at quality 92. They're never resized.
- **Shape:** never simplified. Every triangle of the scan or CAD design is kept.
- **The PXD layer:** the whole GLB is deflated once more. Browsers undo that natively, so there's nothing extra to download.
- **Sidecar `.pxdm.json`:** the SHA-256 (so Lit and PXDZ share it by hash), the sizes and the triangle count. The CAD source is kept alongside, xz-compressed.
- **`.pxdm.glb`:** the same model as a plain GLB for Blender, Unreal and slicers.

In a page: `<script src="/pxd/pxdmesh.js"></script>`, and then `<model-viewer src="chair.pxdm">` just works. The 3D store engine (`clients/engine/vrstore.js`) loads `.pxdm` models on its own. In three.js: `PXDMesh.three(loader)`, then `loader.load(await PXDMesh.url("x.pxdm"))`.

Measured 2026-11-13 (all triangles kept):

| model | source | .pxdm | smaller by |
|---|---:|---:|---:|
| STL part, 327,680 triangles | 16.4 MB | 0.60 MB | 27.5x |
| scan-sized textured model, 327,680 triangles, 2048 texture | 14.6 MB | 3.57 MB | 4.1x |

Needs Node.js (gltf-transform runs through npx) and, for OBJ/STL/PLY, `pip install trimesh`.
