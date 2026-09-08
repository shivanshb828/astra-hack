"""Run through Blender's --python option; arguments follow --."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import scene_builder
import runtime


def embed_sources():
    for name in ['constraints.py','scene_builder.py','overlays.py','runtime.py']:
        block=bpy.data.texts.get(name) or bpy.data.texts.new(name)
        block.clear(); block.write((HERE/name).read_text())
        block.use_module=False
    readme=bpy.data.texts.get('START_HERE.txt') or bpy.data.texts.new('START_HERE.txt')
    readme.clear(); readme.write(
        'MISSIONPCB / EDITABLE CONSTRAINT DEMO\n\n'
        'Orbit, zoom and select individual components. One Blender unit = 1 mm.\n'
        'Results are a saved snapshot until recalculation.\n\n'
        'ENABLE INTERACTION: Open Scripting workspace, choose runtime.py in the\n'
        'Text Editor and press Run Script (Alt-P). Return to Layout.\n'
        'Press N over the 3D view, open MissionPCB, then Recalculate Constraints.\n'
        'The script is embedded; no add-on installation or global auto-run setting is needed.\n\n'
        'Use G X / G Y to move a selected component on the board.\n'
        'Move ECG_AFE_MissionPCB near Buck_PMIC_MissionPCB and recalculate to see FAIL.\n'
        'Restore it to X=-2, Y=4, Z=4.35 relative to its parent and recalculate.\n'
        'Or use Restore Seeded Demo to return to the verified fixture placements.\n'
        'Save edits explicitly. Report export does not save your .blend.\n\n'
        'The layout is an authored demo, not an AI optimizer or electrical solver.\n'
        'Heat/noise zones are approximate, without temperatures or EM field values.\n')


def manifest(directory,timings):
    scene=bpy.context.scene
    content=dict(generated_at=datetime.now().astimezone().isoformat(),blender_version=bpy.app.version_string,
        blender_build_hash=bpy.app.build_hash.decode(),python_version=platform.python_version(),
        os=platform.platform(),architecture=platform.machine(),render_engine=scene.render.engine,
        render_resolution=[scene.render.resolution_x,scene.render.resolution_y],
        geometry_revision=scene.get('validated_signature'),timings_seconds=timings,
        verification=scene.get('verification_notes','Not recorded'),files={})
    paths=list(HERE.glob('*.py'))+[HERE/'scene_config.json']
    paths += [directory/'missionpcb_lean_constraint_demo.blend',directory/'validation_results.json',directory/'validation_report.md']
    paths += list((directory/'renders').glob('*.png'))
    for path in paths:
        if path.exists():
            content['files'][str(path.relative_to(HERE)) if path.is_relative_to(HERE) else str(path)]=dict(
                bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (directory/'build_manifest.json').write_text(json.dumps(content,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['build','upgrade-ecg','recalculate','render'],default='build')
    parser.add_argument('--quality',choices=['preview','final'],default='preview')
    parser.add_argument('--output-dir',type=Path,default=HERE)
    parser.add_argument('--skip-render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    output=args.output_dir.resolve(); output.mkdir(parents=True,exist_ok=True)
    start=time.monotonic(); timings={}
    if args.mode=='build':
        config=json.loads((HERE/'scene_config.json').read_text())
        base=json.loads((HERE/'scene_config_generic.json').read_text()) if config.get('profile')=='ecg' else config
        scene_builder.build_scene(base)
        if config.get('profile')=='ecg':scene_builder.upgrade_ecg(config)
    elif 'config_json' not in bpy.context.scene:
        raise RuntimeError('Open the generated .blend for recalculate/render modes')
    if args.mode=='upgrade-ecg':
        scene_builder.upgrade_ecg(json.loads((HERE/'scene_config.json').read_text()))
    embed_sources()
    results=runtime.recalculate_constraints()
    for name,r in results.items():
        print('CONSTRAINT SUMMARY',name,[(x['category'],x['status']) for x in r['categories']],flush=True)
    if results['MissionPCB']['status']!='PASS':
        failing=[r for r in results['MissionPCB']['checks'] if r['status']!='PASS']
        raise RuntimeError('Corrected layout contains genuine violations: '+json.dumps(failing))
    scene=bpy.context.scene
    target=output/'missionpcb_lean_constraint_demo.blend'
    timings['build_and_validate']=time.monotonic()-start
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    if not args.skip_render and args.mode in ['build','upgrade-ecg','render']:
        folder=output/'renders' if args.quality=='final' else output/'renders'/'previews'
        folder.mkdir(parents=True,exist_ok=True)
        scene.render.resolution_percentage=100 if args.quality=='final' else 50
        if scene.render.engine=='BLENDER_EEVEE': scene.eevee.taa_render_samples=128 if args.quality=='final' else 48
        if scene.render.engine=='CYCLES': scene.cycles.samples=48 if args.quality=='final' else 12
        for camera,name in [('Camera_TopDown','top_down'),('Camera_Isometric','isometric')]:
            before=time.monotonic(); scene.camera=bpy.data.objects[camera]; scene_builder.face_camera(scene.camera)
            scene.render.filepath=str(folder/(name+'.png')); bpy.context.view_layer.update()
            bpy.ops.render.render(write_still=True)
            timings[name]=time.monotonic()-before
    scene.camera=bpy.data.objects['Camera_Isometric']; scene_builder.face_camera(scene.camera)
    scene.render.resolution_percentage=100
    runtime.export_results(output)
    if scene.get('profile')=='ecg':
        cache=output/'cache';cache.mkdir(exist_ok=True)
        seeds=[dict(name=o.name,component_id=o.get('component_id'),layout=o.get('layout_id'),
                    location=list(o['seed_location']),scale=list(o['seed_scale'])) for o in scene.objects if 'seed_location' in o]
        (cache/'verified_seed.json').write_text(json.dumps(dict(profile='ecg',generated_at=scene['validated_at'],
            geometry_revision=scene['validated_signature'],config=json.loads(scene['config_json']),
            seeds=seeds,results=json.loads(scene['results_json']),note='Precomputed fixture results. Recalculate actual geometry after edits.'),indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    manifest(output,timings)
    print('MISSIONPCB_ARTIFACTS',str(target),json.dumps(timings),flush=True)


if __name__=='__main__': main()
