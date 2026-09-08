import * as T from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';
const host=document.getElementById('cadViewport');const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setClearColor(0xe9ede9);host.appendChild(renderer.domElement);
const scene=new T.Scene(),camera=new T.PerspectiveCamera(36,1,.1,1000);camera.position.set(55,125,98);const controls=new OrbitControls(camera,renderer.domElement);controls.minDistance=45;controls.maxDistance=230;
scene.add(new T.HemisphereLight(0xffffff,0x647564,2.5));const sun=new T.DirectionalLight(0xffffff,2.3);sun.position.set(20,70,40);scene.add(sun);
const roots=[],marks=new T.Group();scene.add(marks);let latest={revision:0,selected:null,findings:revisions[0].findings};
function render(){renderer.render(scene,camera)}controls.addEventListener('change',render);
new ResizeObserver(()=>{renderer.setSize(host.clientWidth,host.clientHeight);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();render()}).observe(host);
function update(){roots.forEach((g,i)=>g.visible=i===(latest.revision===2?1:0));while(marks.children.length){const m=marks.children[0];marks.remove(m);m.geometry.dispose();m.material.dispose()}const subjects=new Set(latest.findings.filter(f=>f.status==='fail').flatMap(f=>f.target));for(const part of parts){if(!subjects.has(part.id)&&part.id!==latest.selected)continue;const xy=revisions[latest.revision].placements[part.id];const ring=new T.Mesh(new T.RingGeometry(3.6,4,64),new T.MeshBasicMaterial({color:part.id===latest.selected?0x158c80:0xe45b40,transparent:true,opacity:.75,side:T.DoubleSide,depthTest:false}));ring.rotation.x=-Math.PI/2;ring.position.set(xy[0]-36,2.5,19-xy[1]);ring.renderOrder=5;marks.add(ring)}render()}
window.addEventListener('missionpcb-view',e=>{latest=e.detail;update()});
try{for(const file of ['initial','improved']){const gltf=await new GLTFLoader().loadAsync('./assets/cached/'+file+'.glb');gltf.scene.scale.setScalar(1000);gltf.scene.position.set(-136,0,-119);scene.add(gltf.scene);roots.push(gltf.scene)}update()}catch(e){host.append(Object.assign(document.createElement('p'),{textContent:'Cached model failed to load: '+e.message}))}
