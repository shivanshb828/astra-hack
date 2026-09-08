"""Run once inside the open canonical Blender scene. Local file IPC, no sockets in Blender."""
from pathlib import Path
import json,math,time,traceback
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
IPC=ROOT/'bridge';PUBLIC=ROOT/'public'
IPC.mkdir(exist_ok=True);PUBLIC.mkdir(exist_ok=True)
RUNTIME=bpy.data.texts['runtime.py'].as_module()
IDS={'MCU','Sensor','RF','Regulator','Driver','Battery'}


def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,allow_nan=False));temp.replace(path)


def objects():
    return {o['component_id']:o for o in bpy.context.scene.objects if o.get('role')=='component' and o.get('layout_id')=='MissionPCB'}


def export_meshes():
    root=bpy.data.objects['Root_MissionPCB'];frame=root.matrix_world.inverted();items=[]
    allowed={'pcb','component','patient_component','battery_pack','conductor'}
    for obj in bpy.context.scene.objects:
        if obj.get('layout_id')!='MissionPCB' or obj.get('role') not in allowed:continue
        if obj.type not in ('MESH','CURVE'):continue
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles();matrix=frame@obj.matrix_world
            center=matrix.translation
            positions=[];normals=[];colors=[]
            normal=matrix.to_3x3().inverted().transposed()
            for triangle in mesh.loop_triangles:
                mat=obj.data.materials[triangle.material_index] if len(obj.data.materials)>triangle.material_index else None
                color=list(mat.diffuse_color[:3]) if mat else [.3,.4,.45]
                n=(normal@triangle.normal).normalized()
                for index in triangle.vertices:
                    v=matrix@mesh.vertices[index].co-center
                    positions.extend(v);normals.extend(n);colors.extend(color)
            items.append({'name':obj.name,'ref':obj.get('component_id') if obj.get('role')=='component' else None,'positions':positions,'normals':normals,'colors':colors,'position':list(center),'rotation':obj.rotation_euler.z,'movable':obj.get('role')=='component'})
        finally:evaluated.to_mesh_clear()
    atomic(PUBLIC/'model.json',{'units':'mm','items':items})


def state(ack=None):
    scene=bpy.context.scene
    if scene.get('constraints_stale') or RUNTIME.signature()!=scene.get('validated_signature'):RUNTIME.recalculate_constraints()
    p=json.loads(scene['engine_results_json']);root=bpy.data.objects['Root_MissionPCB']
    result={'heartbeat':time.time(),'signature':RUNTIME.signature(),'revision':p['revision'],'result':p['results']['MissionPCB'],'parts':[]}
    for ref,obj in objects().items():
        record=json.loads(obj.get('catalog_record_json','{}'))
        result['parts'].append({'ref':ref,'name':record.get('mpn',ref),'position':list((root.matrix_world.inverted()@obj.matrix_world).translation),'rotation':obj.rotation_euler.z,'dimensions':list(obj.dimensions),'catalog':record,'geometry_basis':obj.get('geometry_basis','')})
    if ack:result['ack']=ack
    elif (IPC/'state.json').exists():result['ack']=json.loads((IPC/'state.json').read_text()).get('ack')
    atomic(IPC/'state.json',result)
    return result


def process():
    cmdfile=IPC/'command.json';ack=None
    if cmdfile.exists():
        command=json.loads(cmdfile.read_text());cmdfile.unlink()
        ack={'id':command.get('id'),'ok':False}
        old={o.name:(o.location.copy(),o.rotation_euler.copy()) for o in objects().values()}
        try:
            if time.time()-command['created']>10:raise ValueError('Command expired')
            if command['base_signature']!=RUNTIME.signature():raise ValueError('Scene changed; refresh before moving')
            if command['action']=='move':
                ref=command['ref'];x=command['x'];y=command['y']
                if ref not in IDS or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>100 for v in (x,y)):raise ValueError('Invalid component position')
                obj=objects()[ref];obj.location.x=x;obj.location.y=y
            elif command['action']=='reset':
                for obj in objects().values():obj.location=obj['seed_location'];obj.rotation_euler=(0,0,0)
            elif command['action']!='validate':raise ValueError('Unsupported action')
            bpy.context.view_layer.update();RUNTIME.recalculate_constraints();ack['ok']=True
        except Exception as error:
            for name,(loc,rot) in old.items():bpy.data.objects[name].location=loc;bpy.data.objects[name].rotation_euler=rot
            bpy.context.view_layer.update();ack['error']=str(error)
    try:state(ack)
    except Exception as error:atomic(IPC/'state.json',{'heartbeat':time.time(),'error':str(error),'ack':ack})
    return .5


def start():
    assert bpy.context.scene.get('use_upstream_engine'),'Install the engine bridge first'
    previous=bpy.app.driver_namespace.get('missionpcb_web_timer')
    if previous and bpy.app.timers.is_registered(previous):bpy.app.timers.unregister(previous)
    export_meshes();process()
    bpy.app.driver_namespace['missionpcb_web_timer']=process
    bpy.app.timers.register(process,first_interval=.5,persistent=False)
    print('MISSIONPCB_WEB_LINK_READY',ROOT,flush=True)


if __name__=='__main__':start()
