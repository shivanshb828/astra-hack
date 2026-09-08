"""Create the workbench derivative from an existing saved ECG demo."""
from pathlib import Path
import json
import sys
import time
import bpy

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import runtime
import scene_builder
import environment_builder


def main():
    started=time.monotonic();out=HERE/'workbench';out.mkdir(exist_ok=True)
    baseline=Path(bpy.data.filepath)
    if not baseline.exists() or bpy.context.scene.get('profile')!='ecg':raise RuntimeError('Load the saved ECG baseline first.')
    for name in ['constraints','scene_builder','overlays','runtime','environment_builder']:
        text=bpy.data.texts.get(name+'.py') or bpy.data.texts.new(name+'.py');text.clear();text.write((HERE/(name+'.py')).read_text());text.use_module=False
    before_signature=runtime.signature()
    before_snapshots={name:runtime.extract_scene_snapshot(name) for name in ['Naive','MissionPCB']}
    before_results=runtime.recalculate_constraints()
    environment_builder.build_environment()
    after_signature=runtime.signature()
    after_snapshots={name:runtime.extract_scene_snapshot(name) for name in ['Naive','MissionPCB']}
    assert before_signature==after_signature,'Environment changed validated geometry signature'
    assert before_snapshots==after_snapshots,'Environment changed geometry snapshots'
    assert runtime.recalculate_constraints()==before_results,'Environment changed rule results'
    count=len(bpy.data.objects);runtime.recalculate_constraints();assert count==len(bpy.data.objects),'Recalculation leaked objects'
    props=list(bpy.data.collections[environment_builder.COLLECTION].objects)
    prop=next(o for o in props if o.type=='MESH');old=prop.location.copy();prop.location.x+=20;bpy.context.view_layer.update()
    assert runtime.signature()==after_signature,'Prop motion changed signature'
    assert {name:runtime.extract_scene_snapshot(name) for name in ['Naive','MissionPCB']}==after_snapshots
    prop.location=old;bpy.context.view_layer.update()
    scene=bpy.context.scene;scene.camera=bpy.data.objects['Camera_Workbench'];scene_builder.face_camera(scene.camera)
    scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
    scene.render.engine='BLENDER_EEVEE';scene.eevee.taa_render_samples=64
    scene.render.threads_mode='FIXED';scene.render.threads=4
    renders=out/'renders';renders.mkdir(exist_ok=True);scene.render.filepath=str(renders/'workbench.png')
    before_render=time.monotonic();bpy.ops.render.render(write_still=True);render_seconds=time.monotonic()-before_render
    runtime.export_results(out)
    report=out/'validation_report.md'
    report.write_text(report.read_text().replace('missionpcb_lean_constraint_demo.blend','missionpcb_ecg_workbench.blend').replace('- renders/top_down.png\n- renders/isometric.png','- renders/workbench.png'))
    scene['verification_notes']='Workbench geometry isolation verified: identical snapshots/signature/results; prop motion ignored; repeated recalculation stable. Baseline ECG tests run separately.'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'missionpcb_ecg_workbench.blend'))
    verification=dict(baseline=str(baseline),artifact=str(out/'missionpcb_ecg_workbench.blend'),
        geometry_signature_unchanged=True,snapshots_unchanged=True,results_unchanged=True,
        prop_motion_ignored=True,recalculation_stable=True,environment_objects=len(props),
        mesh_vertices=sum(len(o.data.vertices) for o in props if o.type=='MESH'),
        added_lights=sum(o.type=='LIGHT' for o in props),render_engine=scene.render.engine,
        render_resolution=[1920,1080],render_seconds=render_seconds,total_seconds=time.monotonic()-started,
        baseline_statuses={name:[r['status'] for r in value['categories']] for name,value in before_results.items()})
    (out/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    (out/'README.md').write_text('# MissionPCB ECG workbench\n\nA decorative warm oak electronics desk around the unchanged ECG demonstration.\n\nOpen `missionpcb_ecg_workbench.blend`, or use `Open ECG Workbench.command` in the parent folder to activate embedded controls. The scene and code work offline.\n\nThe mat, meter in standby, tools, solder reel, and notebook are decorative objects, excluded from every validation rule. No additional lights, textures, physics simulation, or online dependencies are used.\n\nThe original saved demo remains unchanged. The component envelopes and geometric proxy limitations from that demo still apply.\n\nSee `verification.json`, `validation_report.md`, and `renders/workbench.png`.\n')
    print('WORKBENCH_BUILD_PASS',json.dumps(verification),flush=True)

if __name__=='__main__':main()
