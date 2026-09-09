"""Editable concept housing sized from native PCB geometry and an adopted brief.

Mechanical concepts are labelled; they never fabricate KiCad nets or medical validation.
"""
import bpy,bmesh,json,math
from mathutils import Vector
from pathlib import Path
import assembly
from pcb_presentation import finish

def outline(w,h,r):
 r=min(r,w/2,h/2);points=[]
 for cx,cy,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
  for i in range(13):
   a=math.radians(start+i*90/12);points.append((cx+r*math.cos(a),cy+r*math.sin(a)))
 return points

def shape(name,rings,parent,mat,role,caps=True):
 n=len(rings[0][0]);vertices=[(x,y,z) for ring,z in rings for x,y in ring];faces=[]
 for j in range(len(rings)-1):faces.extend((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for i in range(n))
 if caps:faces.extend([tuple(reversed(range(n))),tuple((len(rings)-1)*n+i for i in range(n))])
 else:faces.extend(((len(rings)-1)*n+i,(len(rings)-1)*n+(i+1)%n,(i+1)%n,i) for i in range(n))
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj);obj.parent=parent;mesh.materials.append(mat)
 obj['mechanical_role']=role;obj['provenance']='Editable mechanical concept; dimensions derived from board geometry and explicit profile'
 return obj

def _box(name,location,size,parent,mat,role):
 obj=assembly.box(name,location,size,parent);obj.data.materials.clear();obj.data.materials.append(mat);obj['mechanical_role']=role
 bevel=obj.modifiers.new('Moulded edge radius','BEVEL');bevel.width=min(size)/5;bevel.segments=3
 return obj

def _remove_generated(root):
 for obj in list(root.children_recursive)+[root]:bpy.data.objects.remove(obj,do_unlink=True)

def _strap(body,device,width=20,thickness=1.1):
 """A ribbon follows radial samples of the supplied mesh at the mounting height."""
 lo,hi=assembly.bounds(body);device_lo,device_hi=assembly.bounds(device);z=(device_lo.z+device_hi.z)/2
 center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,z));radius=max(hi.x-lo.x,hi.y-lo.y)*.8;tree=assembly.world_bvh(body)
 ring=[];fallback=0
 for index in range(128):
  angle=index*math.tau/128;direction=Vector((math.cos(angle),math.sin(angle),0));origin=center+radius*direction
  hits=[tree.ray_cast(origin+Vector((0,0,dz)),-direction,radius*2)[0] for dz in (-width/2,0,width/2)]
  hits=[hit for hit in hits if hit is not None]
  hit=max(hits,key=lambda point:(point-center).dot(direction)) if hits else None
  if hit is not None:hit=Vector((hit.x,hit.y,z))
  if hit is None:
   fallback+=1;hit=center+Vector((direction.x*(hi.x-lo.x)/2,direction.y*(hi.y-lo.y)/2,0))
  ring.append(hit+direction*2)
 root=assembly.empty('Body strap · sampled fit concept','strap',device);root['asset_role']='attachment';root['generated_housing']=True
 root['source']='Radial cross-section of selected body CAD; 2 mm nominal offset. No pressure/tension/material simulation.'
 root['fallback_samples']=fallback
 inv=device.matrix_world.inverted();vertices=[]
 for point in ring:
  radial=(point-center).normalized()
  vertices.extend(inv@(point+Vector((0,0,dz))+radial*depth) for depth,dz in [(0,-width/2),(0,width/2),(thickness,width/2),(thickness,-width/2)])
 faces=[]
 for i in range(len(ring)):
  j=(i+1)%len(ring)
  faces.extend((4*i+k,4*j+k,4*j+(k+1)%4,4*i+(k+1)%4) for k in range(4))
 mesh=bpy.data.meshes.new('Sampled strap ribbon');mesh.from_pydata(vertices,[],faces);mesh.update()
 obj=bpy.data.objects.new('Soft strap · concept',mesh);obj['outside_mounting_pocket']=True;bpy.context.scene.collection.objects.link(obj);obj.parent=root;obj.data.materials.append(finish('Strap · woven graphite',(.035,.054,.065,1),0,.88))
 for polygon in mesh.polygons:polygon.use_smooth=True
 return root

def generate(profile):
 if not isinstance(profile,dict) or profile.get('status')!='adopted':raise ValueError('Adopt the device profile before generating its housing.')
 kind=profile.get('device_kind','general');mount=profile.get('mount','unspecified');attachment=profile.get('attachment','unspecified')
 if mount not in ('chest','head','wrist','unspecified') or attachment not in ('adhesive','strap','unspecified'):raise ValueError('Unknown mount or attachment.')
 scene=bpy.context.scene;items=assembly.objects();board=items.get('board');device=items.get('device');body=assembly.body_object()
 if not board or not device:raise ValueError('Import the actual KiCad PCB first.')
 if mount=='head' and body and 'chest' in (body.name+' '+body.get('source','')).lower():raise ValueError('The selected CAD contains only a chest. Import a full body or head CAD model for a head-mounted design.')
 import native_views
 native_views.restore();bpy.context.view_layer.update();lo,hi=assembly.bounds(board,device.matrix_world);board_size=hi-lo
 settings=profile.get('housing',{});wall=float(settings.get('wall_mm',1.5));clearance=float(settings.get('clearance_mm',1));floor=float(settings.get('floor_mm',1.5));lid_thickness=float(settings.get('lid_mm',1.2))
 if any(not math.isfinite(n) or not .3<=n<=10 for n in (wall,clearance,floor,lid_thickness)):raise ValueError('Housing dimensions must be finite values from 0.3 to 10 mm.')
 # The existing catalogue supplies an envelope, not a verified cell manufacturer's CAD.
 include_cell=kind=='ecg'
 cell_size=Vector((16,30,3.2));gap=2
 ext_lo=lo.copy();ext_hi=hi.copy()
 if include_cell:ext_hi.x+=gap+cell_size.x
 required=ext_hi-ext_lo+Vector((2*clearance,2*clearance,clearance))
 interior=profile.get('interior_mm')
 size=Vector((float(interior['length']),float(interior['width']),float(interior['height']))) if interior else required
 if any(not math.isfinite(v) or v<=0 or v>1000 for v in size):raise ValueError('Interior dimensions must be positive millimetres, up to 1000 mm.')
 center=(ext_lo+ext_hi)/2;center.z=lo.z-floor-.7
 # Preserve supplied/previous CAD as a hidden reference, never delete it.
 for identifier in ('generated-housing','cached-cell','strap'):
  old=items.get(identifier)
  if old and old.get('generated_housing'):_remove_generated(old)
 old=items.get('enclosure')
 if old and not old.get('generated_housing'):
  world=old.matrix_world.copy();old.parent=None;old.matrix_world=world;old['asset_role']='reference_product'
  for obj in [old,*old.children_recursive]:obj.hide_render=True;obj.hide_set(True)
 root=assembly.empty('Housing · '+str(profile.get('device_name',kind.upper())),'generated-housing',device);root.location=center
 root['asset_role']='product';root['generated_housing']=True;root['source']='Derived from native PCB bounds and adopted device profile';root['interior_mm']=list(size);root['dimensions_derived']=not bool(interior)
 scene['active_enclosure_id']='generated-housing';scene['device_profile']=json.dumps(profile)
 inner=outline(size.x,size.y,5);outer=outline(size.x+2*wall,size.y+2*wall,5+wall);top=floor+size.z
 plastic=finish('Housing · matte ceramic polymer',(.66,.75,.8,1),.02,.36)
 base=shape('Enclosure base · hollow', [(inner,floor),(inner,top),(outer,top),(outer,0)],root,plastic,'base')
 lid=shape('Inspection lid · separate editable part',[(outer,top+.12),(outer,top+lid_thickness)],root,finish('Housing · transparent inspection lid',(.72,.85,.88,.16),0,.2),'lid')
 lid['assembly_id']='housing-lid';lid['asset_role']='mechanical';lid['source']='Transparent inspection finish; not an asserted production material'
 lid_mat=lid.data.materials[0]
 if hasattr(lid_mat,'surface_render_method'):lid_mat.surface_render_method='DITHERED'
 gasket_outer=outline(size.x+wall,size.y+wall,5+wall/2);gasket_inner=outline(size.x+.2,size.y+.2,5.1)
 shape('Gasket seat · unqualified sealing concept',[(gasket_inner,top-.1),(gasket_inner,top+.08),(gasket_outer,top+.08),(gasket_outer,top-.1)],root,finish('Gasket · graphite',(.025,.04,.042,1),0,.78),'gasket',caps=False)
 # Supports stop at the underside of the unmodified PCB; no drilled holes are invented.
 for x in (lo.x+.9,hi.x-.9):
  for y in (lo.y+4,hi.y-4):
   _box('PCB edge support · retention concept',(x-center.x,y-center.y,floor+.35),(2,4,.7),root,plastic,'support')
 region_center=[center.x,center.y,center.z+floor+size.z/2]
 assembly.region('board-bay',region_center,list(size),'Housing interior from adopted profile; measured native board and component geometry','device');board['assigned_region']='region-board-bay'
 if include_cell:
  cell=assembly.empty('150 mAh cell envelope · cached dimensions','cached-cell',device);cell['generated_housing']=True;cell['asset_role']='energy_storage';cell['source']='parts/ecg-patch-parts.json: bat-lipo-150mah, 30 × 16 × 3.2 mm. Cell make/model and CAD are unverified.'
  cell.location=(hi.x+gap+cell_size.x/2,(lo.y+hi.y)/2,lo.z+cell_size.z/2)
  _box('LiPo pouch · envelope', (0,0,0),list(cell_size),cell,finish('Cell · aluminium laminate',(.36,.41,.46,1),.7,.31),'cell_envelope')
  _box('Cell protection strip · concept',(0,-cell_size.y/2+1,.15),(cell_size.x,2,cell_size.z+.2),cell,finish('Cell · insulation',(.74,.5,.055,1),0,.4),'cell_insulation')
  cell['assigned_region']='region-board-bay'
 if attachment=='adhesive':
  sheet=outline(size.x+2*wall+10,size.y+2*wall+8,10)
  shape('Adhesive carrier · material unqualified',[(sheet,-.45),(sheet,0)],root,finish('Adhesive · pale silicone concept',(.46,.63,.69,1),0,.64),'adhesive')
 if kind=='ecg':
  for x in (-size.x*.30,size.x*.30):
   bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=6.5,depth=.25)
   obj=bpy.context.object;obj.name='ECG electrode area · concept only';obj.parent=root;obj.location=(x,0,-.6);obj.data.materials.append(finish('Electrode · concept contact',(.34,.4,.42,1),.6,.35));obj['mechanical_role']='electrode_concept';obj['source']='Placement concept; material, wiring and patient protection not verified'
 bpy.context.view_layer.update()
 if body and mount in ('chest','head','wrist'):
  blo,bhi=assembly.bounds(body);height=bhi.z-blo.z
  ratio={'chest':.743,'head':.92,'wrist':.50}[mount]
  x=(blo.x+bhi.x)/2 if mount!='wrist' else blo.x*.8+bhi.x*.2
  z=blo.z+height*ratio;tree=assembly.world_bvh(body)
  hit=tree.ray_cast(Vector((x,blo.y-500,z)),Vector((0,1,0)),1000)[0]
  if hit is None:
   candidates=[obj.matrix_world@v.co for obj in assembly.meshes(body) for v in obj.data.vertices]
   hit=min(candidates,key=lambda point:(point.x-x)**2+(point.z-z)**2)
  target=assembly.region(mount,list(hit+Vector((0,-15,0))),[max(130,size.x+2*wall+12),max(75,size.y+2*wall+12),30],'Concept mounting volume on selected body surface; verify anatomical landmark manually')
  target.rotation_euler.x=math.pi/2;target['body_id']=body['assembly_id']
  bpy.context.view_layer.update()
  assembly.place('device',target['assembly_id'])
  tree=assembly.world_bvh(body);normal=target.matrix_world.to_quaternion()@Vector((0,0,1))
  for _ in range(40):
   if not assembly.world_bvh(device).overlap(tree):break
   device.location+=normal*.5;target.location+=normal*.5;bpy.context.view_layer.update()
 if attachment=='strap':
  if body:_strap(body,device)
  else:scene['strap_pending']='Import and select body CAD to generate a fitted strap.'
 scene['design_gaps']=json.dumps(['PCB copper routing and electrical connectivity are not generated.','L1 has no native KiCad package model.','Cell is a catalogue envelope; manufacturer CAD and battery safety are unverified.']+(['Electrode areas are conceptual; acquisition wiring and patient protection are not validated.'] if kind=='ecg' else [])+['Pogo charging and sealing need a defined contact part and verified enclosure opening.'])
 assembly.record('Generated editable housing from '+('explicit interior dimensions' if interior else 'native PCB/component bounds plus clearances')+'; adopted '+mount+' / '+attachment+' profile')
 result=assembly.check();native_views.view('assembly')
 return 'Generated editable base, lid, gasket seat and PCB supports'+(', cached cell envelope' if include_cell else '')+'. '+result
