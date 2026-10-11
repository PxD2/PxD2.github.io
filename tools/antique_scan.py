"""PXD Antiques scan-to-listing: Revopoint scan in, live AR listing out.

On base1, after scanning a piece and exporting it from Revo Studio (OBJ/PLY/STL/GLB/FBX):

    python tools/antique_scan.py "C:\\Scans\\lamp.obj" --id brass-lamp --title "Brass table lamp" ^
        --shop smiths-antiques --category Lighting --price 245 --height-cm 62 --era "c. 1925" ^
        --condition "Rewired, original shade"

What it does (Blender in the background, no clicks):
  1. Imports the scan, joins the pieces, removes loose fragments.
  2. Stands it upright on the floor, centred, and scales it to its REAL size from the
     height you measured (so View in your room shows it at true size).
  3. Reduces it to a phone-friendly size (default 80k faces) and keeps its colours.
  4. Exports antiques/models/<id>.glb and adds or updates the piece in antiques/catalog.json,
     with width/height/depth measured from the scaled model.
Then push the repo, and the piece is live at pxd2.github.io/antiques/#/item/<id>.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CATALOG = os.path.join(ROOT, "antiques", "catalog.json")
MODELS = os.path.join(ROOT, "antiques", "models")

try:
    import bpy  # running inside Blender
except ImportError:
    bpy = None


def blender_part(src, out, height_cm, faces):
    import bmesh
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(src)[1].lower()
    importers = {
        ".obj": lambda: bpy.ops.wm.obj_import(filepath=src),
        ".ply": lambda: bpy.ops.wm.ply_import(filepath=src),
        ".stl": lambda: bpy.ops.wm.stl_import(filepath=src),
        ".glb": lambda: bpy.ops.import_scene.gltf(filepath=src),
        ".gltf": lambda: bpy.ops.import_scene.gltf(filepath=src),
        ".fbx": lambda: bpy.ops.import_scene.fbx(filepath=src),
    }
    if ext not in importers:
        raise SystemExit(f"Unsupported scan format {ext}. Export OBJ, PLY, STL, GLB or FBX from Revo Studio.")
    importers[ext]()
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("No mesh found in the scan file.")
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # drop small loose fragments (scan noise): keep islands with >= 1% of the vertices
    bm = bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
    seen, islands = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, isl = [v], []
        seen.add(v.index)
        while stack:
            cur = stack.pop(); isl.append(cur)
            for e in cur.link_edges:
                w = e.other_vert(cur)
                if w.index not in seen:
                    seen.add(w.index); stack.append(w)
        islands.append(isl)
    keep = max(len(i) for i in islands) * 0.01
    bmesh.ops.delete(bm, geom=[v for i in islands if len(i) < keep for v in i], context="VERTS")
    bm.to_mesh(obj.data); bm.free()

    # Revopoint exports are Z-up in Blender after import; measure, scale to real height, sit on floor
    dims = obj.dimensions
    if height_cm:
        s = (height_cm / 100.0) / max(dims.z, 1e-6)
        obj.scale = (s, s, s)
        bpy.ops.object.transform_apply(scale=True)
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    minz = min(p.z for p in bb); cx = sum(p.x for p in bb) / 8; cy = sum(p.y for p in bb) / 8
    obj.location = (-cx, -cy, -minz)
    bpy.ops.object.transform_apply(location=True)

    n = len(obj.data.polygons)
    if faces and n > faces:
        m = obj.modifiers.new("web", "DECIMATE"); m.ratio = faces / n
        bpy.ops.object.modifier_apply(modifier="web")
    bpy.ops.object.shade_smooth()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=False, export_yup=True,
                              export_draco_mesh_compression_enable=False)
    d = obj.dimensions
    with open(out + ".dims.json", "w") as f:  # width (x), height (z), depth (y) in cm
        json.dump([round(d.x * 100), round(d.z * 100), round(d.y * 100)], f)
    print(f"Exported {out}: {len(obj.data.polygons)} faces, {d.x*100:.0f} x {d.z*100:.0f} x {d.y*100:.0f} cm")


def find_blender():
    for p in (os.environ.get("BLENDER"), r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
              r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe", r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
              "blender"):
        if p and (os.path.isfile(p) or p == "blender"):
            return p
    raise SystemExit("Blender not found. Set the BLENDER environment variable to blender.exe.")


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scan"); ap.add_argument("--id", required=True); ap.add_argument("--title", required=True)
    ap.add_argument("--shop", required=True); ap.add_argument("--category", required=True)
    ap.add_argument("--price", type=float); ap.add_argument("--height-cm", type=float, required=True)
    ap.add_argument("--era", default=""); ap.add_argument("--condition", default=""); ap.add_argument("--description", default="")
    ap.add_argument("--faces", type=int, default=80000)
    a = ap.parse_args()
    out = os.path.join(MODELS, a.id + ".glb")
    cmd = [find_blender(), "-b", "--factory-startup", "-P", os.path.abspath(__file__), "--", "--blender",
           os.path.abspath(a.scan), out, str(a.height_cm), str(a.faces)]
    if subprocess.run(cmd).returncode != 0 or not os.path.isfile(out):
        raise SystemExit("Blender step failed; see the messages above.")
    dims = json.load(open(out + ".dims.json")); os.remove(out + ".dims.json")
    cat = json.load(open(CATALOG, encoding="utf-8"))
    if not any(s["id"] == a.shop for s in cat["shops"]):
        raise SystemExit(f"Shop '{a.shop}' isn't in catalog.json yet. Add it under \"shops\" first.")
    item = {"id": a.id, "shop": a.shop, "status": "available", "title": a.title, "category": a.category,
            "era": a.era, "price": a.price, "dims_cm": dims, "condition": a.condition,
            "description": a.description, "model": f"models/{a.id}.glb", "pay": {}}
    cat["items"] = [i for i in cat["items"] if i["id"] != a.id] + [item]
    json.dump(cat, open(CATALOG, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    mb = os.path.getsize(out) / 1e6
    print(f"Listed '{a.title}' ({dims[0]} x {dims[1]} x {dims[2]} cm, {mb:.1f} MB). Push to publish:")
    print(f"  https://pxd2.github.io/antiques/#/item/{a.id}")
    if mb > 15:
        print("  Note: over 15 MB loads slowly on phones; rerun with --faces 40000.")


if __name__ == "__main__":
    if bpy is not None and "--blender" in sys.argv:
        args = sys.argv[sys.argv.index("--blender") + 1:]
        blender_part(args[0], args[1], float(args[2]), int(args[3]))
    else:
        main()
