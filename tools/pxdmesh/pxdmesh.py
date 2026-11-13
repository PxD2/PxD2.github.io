"""PXD Mesh: PXD2's compact 3D format for stores, CAD and scans.

One command turns a model (GLB, glTF, OBJ, STL, PLY, a Revopoint scan export) into a .pxdm (what stores serve,
loaded by /pxd/pxdmesh.js) plus a .pxdm.glb (the same model as a plain GLB for Blender, Unreal, slicers):
  - geometry compressed with meshopt (positions quantized to 14 bits, normals 10, UVs 12: below what a screen or a
    3D printer can show), decoded on the GPU-side in the browser by a 20 KB decoder PXD2 hosts itself
  - textures re-encoded to WebP at quality 92 (keeps the look; never resized)
  - never simplified: no triangle is removed, so the shape stays exactly the scan or the CAD design
  - the whole file deflated once more (.pxdm): browsers inflate it natively, no extra download
  - a sidecar .pxdm.json: SHA-256 (so Lit and PXDZ can share it by hash), sizes, triangle count, and the CAD source
    (STEP, F3D, SCAD, DXF ...) kept alongside, xz-compressed, so the editable design travels with the mesh
It is still a standard GLB with standard extensions, so every 3D tool, model-viewer, three.js and Unreal can open it.

    python tools/pxdmesh/pxdmesh.py pack scan.glb                      # -> scan.pxdm + scan.pxdm.glb + scan.pxdm.json
    python tools/pxdmesh/pxdmesh.py pack chair.obj --cad chair.step
    python tools/pxdmesh/pxdmesh.py pack-dir models/ -o store/assets    # a whole store; writes assets.json
Needs Node.js (for gltf-transform, fetched by npx on first use) and, for OBJ/STL/PLY, `pip install trimesh`.
"""
import argparse, hashlib, json, lzma, os, shutil, subprocess, sys, tempfile, zlib

GLTF_TRANSFORM = ["npx", "--yes", "@gltf-transform/cli@4"]
MESH_IN = (".glb", ".gltf", ".obj", ".stl", ".ply", ".off", ".dae", ".3mf")
CAD_IN = (".step", ".stp", ".iges", ".igs", ".f3d", ".scad", ".dxf", ".fcstd", ".sldprt", ".stl")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tool(args):
    exe = shutil.which("npx") or shutil.which("npx.cmd")
    if not exe:
        sys.exit("PXD Mesh needs Node.js (npx). Install it from nodejs.org, then run again.")
    r = subprocess.run([exe] + GLTF_TRANSFORM[1:] + args, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[-800:])


def to_glb(src, tmp):
    if src.lower().endswith((".glb", ".gltf")):
        return src
    try:
        import trimesh
    except ImportError:
        sys.exit("OBJ/STL/PLY input needs: pip install trimesh")
    out = os.path.join(tmp, "in.glb")
    trimesh.load(src, force="scene").export(out)
    return out


def counts(glb):
    try:
        import trimesh
        sc = trimesh.load(glb, force="scene")
        tris = sum(len(g.faces) for g in sc.geometry.values() if hasattr(g, "faces"))
        verts = sum(len(g.vertices) for g in sc.geometry.values() if hasattr(g, "vertices"))
        return {"triangles": int(tris), "vertices": int(verts)}
    except Exception:  # noqa: BLE001
        return {}


def pack(src, outdir=None, cad=None, name=None):
    src = os.path.abspath(src)
    base = name or os.path.splitext(os.path.basename(src))[0]
    outdir = outdir or os.path.dirname(src)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, base + ".pxdm.glb")
    with tempfile.TemporaryDirectory() as tmp:
        glb = to_glb(src, tmp)
        stats = counts(glb)
        mid = os.path.join(tmp, "mid.glb")
        # 1) textures to WebP at high quality first (rewriting a file decodes meshopt, so geometry goes last)
        try:
            tool(["webp", glb, mid, "--quality", "92"])
        except RuntimeError:
            shutil.copyfile(glb, mid)
        # 2) clean + meshopt geometry, no simplification, no texture resize
        tool(["optimize", mid, out, "--compress", "meshopt", "--simplify", "false", "--texture-compress", "false"])
    # 3) the PXD layer: the whole GLB deflated once more (meshopt output is built to be squeezed again).
    #    Browsers undo it natively (DecompressionStream), so there is no extra decoder to download.
    raw = open(out, "rb").read()
    co = zlib.compressobj(9, zlib.DEFLATED, -15, 9)
    pxdm = out[:-4]                      # name.pxdm (the compact file stores serve); name.pxdm.glb stays for 3D tools
    with open(pxdm, "wb") as f:
        f.write(co.compress(raw) + co.flush())
    meta = {"type": "pxd-mesh/1", "file": os.path.basename(pxdm), "glb": os.path.basename(out), "sha256": sha(pxdm),
            "bytes": os.path.getsize(pxdm), "glb_bytes": os.path.getsize(out), "glb_sha256": sha(out),
            "source": os.path.basename(src), "source_bytes": os.path.getsize(src), "source_sha256": sha(src),
            "compression": {"geometry": "EXT_meshopt_compression (quantized)", "textures": "EXT_texture_webp q92",
                            "outer": "deflate-raw", "simplified": False},
            **stats}
    if cad:
        cad_out = os.path.join(outdir, base + os.path.splitext(cad)[1].lower() + ".xz")
        with open(cad, "rb") as f, lzma.open(cad_out, "wb", preset=9 | lzma.PRESET_EXTREME) as g:
            shutil.copyfileobj(f, g)
        meta["cad"] = {"file": os.path.basename(cad_out), "source": os.path.basename(cad), "bytes": os.path.getsize(cad_out),
                       "source_bytes": os.path.getsize(cad), "sha256": sha(cad)}
    json.dump(meta, open(os.path.join(outdir, base + ".pxdm.json"), "w"), indent=2)
    ratio = meta["source_bytes"] / max(meta["bytes"], 1)
    print(f"{os.path.basename(src)}: {meta['source_bytes']:,} -> {meta['bytes']:,} bytes ({ratio:.1f}x smaller)"
          + (f", {stats['triangles']:,} triangles kept" if stats.get("triangles") else ""))
    return meta


def pack_dir(d, outdir):
    items, cads = [], {}
    for f in sorted(os.listdir(d)):
        b, ext = os.path.splitext(f)
        if ext.lower() in CAD_IN and ext.lower() != ".stl":
            cads[b] = os.path.join(d, f)
    for f in sorted(os.listdir(d)):
        b, ext = os.path.splitext(f)
        if ext.lower() in MESH_IN and not f.endswith(".pxdm.glb"):
            try:
                items.append(pack(os.path.join(d, f), outdir, cads.get(b)))
            except RuntimeError as e:
                print(f"{f}: skipped ({e})")
    total_in = sum(i["source_bytes"] for i in items); total_out = sum(i["bytes"] for i in items)
    idx = {"type": "pxd-mesh-index/1", "assets": items, "source_bytes": total_in, "bytes": total_out}
    json.dump(idx, open(os.path.join(outdir, "assets.json"), "w"), indent=2)
    print(f"{len(items)} models: {total_in:,} -> {total_out:,} bytes ({total_in / max(total_out, 1):.1f}x smaller) · {outdir}/assets.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pack"); p.add_argument("model"); p.add_argument("-o", "--out"); p.add_argument("--cad"); p.add_argument("--name")
    d = sp.add_parser("pack-dir"); d.add_argument("folder"); d.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    if a.cmd == "pack":
        pack(a.model, a.out, a.cad, a.name)
    else:
        pack_dir(a.folder, a.out)


if __name__ == "__main__":
    main()
