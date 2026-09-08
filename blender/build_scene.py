"""Build the MissionPCB Blender scene from engine results, and export a GLB.

This is the Blender bridge described in the build brief. It consumes
``validation_results.json`` through the documented contract (enclosure-mm
coordinates, ``component_positions``, ``zone_overlays``) and produces assets the
web viewport loads. It never re-derives geometry or re-runs any check: every
number here comes from the constraint engine.

Run headless::

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        --python blender/build_scene.py -- \
        --results out/app_scene/validation_results.json \
        --blend blender/out/ecg_patch.blend \
        --glb web/public/assets/ecg_patch.glb \
        --render blender/out/render.png

Object naming is the mapping contract: every product mesh is named exactly for
its stable component ref (``AFE``, ``LIPO``, ...), plus ``BOARD`` and
``ENCLOSURE``. The web client keys off those names, so components stay
individually addressable rather than arriving as one merged model.

Product geometry and presentation objects are kept in separate collections.
Only ``01_Product`` is exported, so Blender's cameras, lights and overlay
gizmos never clutter the web viewport -- the application draws its own labels
and dashboards as web UI.
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

MM = 0.001  # engine emits millimetres; Blender works in metres

PRODUCT_COLLECTION = "01_Product"
PRESENTATION_COLLECTION = "02_Presentation"

# Category -> viewport base colour. Presentation only; nothing here feeds a rule.
CATEGORY_COLOR = {
    "sensor": (0.10, 0.75, 0.85, 1.0),
    "processor": (0.15, 0.18, 0.30, 1.0),
    "wireless": (0.55, 0.25, 0.80, 1.0),
    "power_regulator": (0.95, 0.45, 0.10, 1.0),
    "driver": (0.85, 0.15, 0.15, 1.0),
    "battery": (0.90, 0.75, 0.20, 1.0),
    "connector": (0.85, 0.70, 0.25, 1.0),
    "electrode": (0.75, 0.78, 0.82, 1.0),
}
DEFAULT_COLOR = (0.6, 0.6, 0.62, 1.0)


def argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def reset_scene():
    """Start from a genuinely empty scene, not Blender's default cube."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for block in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights,
                  bpy.data.materials):
        for item in list(block):
            block.remove(item)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"

    for name in (PRODUCT_COLLECTION, PRESENTATION_COLLECTION):
        coll = bpy.data.collections.new(name)
        scene.collection.children.link(coll)


def material(name, rgba, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = "BLEND"
    return mat


def add_box(name, collection, center_mm, size_mm, rgba, alpha=1.0):
    """Add a named box. ``center_mm`` is the box centre in enclosure mm."""
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = f"{name}_mesh"
    obj.scale = tuple(max(v, 0.001) * MM for v in size_mm)
    obj.location = tuple(v * MM for v in center_mm)
    obj.data.materials.append(material(f"mat_{name}", rgba, alpha))

    # Re-link so the object lives only in its intended collection.
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    bpy.data.collections[collection].objects.link(obj)
    return obj


def build_product(results):
    """Enclosure, board and one addressable mesh per component."""
    enclosure = results.get("enclosure_mm") or {}
    board = results.get("board_mm") or {}

    # The results contract does not carry enclosure/board extents, so they are
    # passed in alongside via --layout. Both are optional: absent means the
    # caller only wants component geometry.
    if enclosure:
        li, wi, hi = enclosure["length"], enclosure["width"], enclosure["height"]
        add_box(
            "ENCLOSURE", PRODUCT_COLLECTION,
            (li / 2.0, wi / 2.0, hi / 2.0), (li, wi, hi),
            (0.35, 0.37, 0.40, 1.0), alpha=0.18,
        )

    if board:
        bl, bw, bt = board["length"], board["width"], board["thickness"]
        ox, oy, oz = board["origin"]
        add_box(
            "BOARD", PRODUCT_COLLECTION,
            (ox + bl / 2.0, oy + bw / 2.0, oz + bt / 2.0), (bl, bw, bt),
            (0.11, 0.35, 0.18, 1.0),
        )

    for pos in results["component_positions"]:
        ref = pos["ref"]
        x, y, z = pos["enclosure_xyz_mm"]
        sx, sy, sz = pos["size_mm"]
        colour = CATEGORY_COLOR.get(pos.get("category"), DEFAULT_COLOR)
        obj = add_box(ref, PRODUCT_COLLECTION, (x, y, z + sz / 2.0),
                      (sx, sy, sz), colour)

        # Custom properties travel into the GLB as object extras, so the web
        # client can read engineering flags without a second lookup.
        obj["component_ref"] = ref
        obj["part_id"] = pos.get("part_id", "")
        obj["category"] = pos.get("category", "")
        obj["heat_source"] = bool(pos.get("heat_source"))
        obj["noise_source"] = bool(pos.get("noise_source"))
        obj["sensitivity"] = pos.get("sensitivity", "none")
        obj["skin_contact"] = bool(pos.get("skin_contact"))


def product_bounds():
    """World-space min/max corners of the product collection, in metres.

    The view layer is flushed first: ``location``/``scale`` were set by direct
    assignment, and until the depsgraph catches up ``matrix_world`` still holds
    the identity, which reads every part as an unscaled 1 m cube.
    """
    bpy.context.view_layer.update()
    corners = [
        obj.matrix_world @ Vector(c)
        for obj in bpy.data.collections[PRODUCT_COLLECTION].objects
        for c in obj.bound_box
    ]
    if not corners:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners),
                 min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners),
                 max(c.z for c in corners)))
    return lo, hi


def aim(obj, target):
    """Point an object's -Z axis at ``target`` (Blender camera/light forward)."""
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def build_presentation(results):
    """Cameras and lights. Never exported; the web app draws its own overlays.

    Framing is computed from the actual product bounds rather than hardcoded:
    the patch is only ~100 x 40 x 7 mm, so a guessed camera misses it entirely
    and renders an empty frame.
    """
    lo, hi = product_bounds()
    center = (lo + hi) / 2.0
    radius = max((hi - lo).length / 2.0, 0.001)

    views = {
        # Back off along the view direction by enough to contain the bounds.
        "Camera_Isometric": Vector((-1.0, -1.0, 0.85)),
        "Camera_TopDown": Vector((0.0, 0.0, 1.0)),
        "Camera_Side": Vector((0.0, -1.0, 0.12)),
    }
    for name, direction in views.items():
        cam_data = bpy.data.cameras.new(name)
        cam_data.lens = 50.0
        cam = bpy.data.objects.new(name, cam_data)
        bpy.data.collections[PRESENTATION_COLLECTION].objects.link(cam)
        # 3.2x the bounding radius keeps the whole device inside a 50 mm lens.
        cam.location = center + direction.normalized() * radius * 3.2
        aim(cam, center)

    bpy.context.scene.camera = bpy.data.objects["Camera_Isometric"]

    # Two area lights sized to the device. Wattage is derived from the lighting
    # distance rather than fixed: irradiance falls off as 1/d^2, so a constant
    # energy that suits a 1 m prop blows out a 100 mm patch completely.
    light_distance = radius * 4.0
    for name, offset, irradiance in (
        ("Key", Vector((-0.6, -0.8, 1.0)), 2.5),
        ("Fill", Vector((0.9, -0.3, 0.5)), 0.8),
    ):
        light_data = bpy.data.lights.new(name, type="AREA")
        light_data.energy = irradiance * 4.0 * math.pi * light_distance ** 2
        light_data.size = radius * 2.0
        light = bpy.data.objects.new(name, light_data)
        light.location = center + offset.normalized() * light_distance
        bpy.data.collections[PRESENTATION_COLLECTION].objects.link(light)
        aim(light, center)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.16, 0.17, 0.19, 1.0)
    bg.inputs[1].default_value = 1.0
    bpy.context.scene.world = world


def export_glb(path):
    """Export product geometry only, as individually addressable objects."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.collections[PRODUCT_COLLECTION].objects:
        obj.select_set(True)

    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,        # glTF convention; the client converts back
        export_extras=True,     # carries component_ref and the flags above
    )
    return path


def render_still(path, samples=48, resolution=(1280, 800)):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"      # EEVEE needs a GL context -b may lack
    scene.cycles.samples = samples
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--layout", help="layout JSON, for enclosure/board extents")
    ap.add_argument("--blend")
    ap.add_argument("--glb")
    ap.add_argument("--render")
    ap.add_argument("--samples", type=int, default=48)
    args = ap.parse_args(argv_after_ddash())

    with open(args.results) as fh:
        results = json.load(fh)

    # Fold the enclosure/board extents in from the layout, since the results
    # contract carries components and overlays but not the shell they sit in.
    if args.layout:
        with open(args.layout) as fh:
            layout = json.load(fh)
        interior = (layout.get("enclosure") or {}).get("interior_mm") or {}
        if interior:
            results["enclosure_mm"] = {
                "length": interior["length"],
                "width": interior["width"],
                "height": interior["height"],
            }
        board = layout.get("board") or {}
        size = board.get("size_mm") or {}
        if size:
            results["board_mm"] = {
                "length": size["length"],
                "width": size["width"],
                "thickness": size.get("thickness", 1.6),
                "origin": board.get("origin_mm", [0, 0, 0]),
            }

    reset_scene()
    build_product(results)
    build_presentation(results)

    product = bpy.data.collections[PRODUCT_COLLECTION].objects
    print(f"[scene] {len(product)} product objects: "
          f"{', '.join(sorted(o.name for o in product))}")

    if args.blend:
        os.makedirs(os.path.dirname(args.blend) or ".", exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
        print(f"[blend] {args.blend}")
    if args.glb:
        print(f"[glb] {export_glb(os.path.abspath(args.glb))}")
    if args.render:
        print(f"[render] {render_still(os.path.abspath(args.render), args.samples)}")


if __name__ == "__main__":
    main()
