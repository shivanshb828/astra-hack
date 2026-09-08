import { Canvas, ThreeEvent, useFrame, useThree } from '@react-three/fiber'
import { Grid, Line, Html, OrbitControls } from '@react-three/drei'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { attentionRefs, dragPosition } from './attention'
import type { AnalysisResult, DesignState, PartInfo, VizInstruction } from './types'

// Engine data is millimetres, Z-up. The GLB was exported with glTF's Y-up
// convention, which maps Blender (x, y, z) to (x, z, -y). Both conversions
// happen here, at the rendering boundary, so engineering state upstream stays
// in one documented frame.
const MM = 0.001
export function toScene(p: [number, number, number]): [number, number, number] {
  return [p[0] * MM, p[2] * MM, -p[1] * MM]
}

const CATEGORY_COLOR: Record<string, string> = {
  sensor: '#19bfd9',
  processor: '#2b3350',
  wireless: '#8c40cc',
  power_regulator: '#f2731a',
  driver: '#d92626',
  battery: '#e5bf33',
  connector: '#d9b340',
  electrode: '#bfc4cc',
}

export interface ViewportProps {
  design: DesignState
  parts: Record<string, PartInfo>
  analysis: AnalysisResult | null
  analysisStale: boolean
  selected: string | null
  focusedCheck: string | null
  onSelect: (ref: string | null) => void
  onDragState: (active: boolean) => void
  onDragEnd: (ref: string, pos: [number, number]) => void
  show: { board: boolean; enclosure: boolean; contact: boolean; overlays: boolean }
  enclosureOpacity: number
  explode: number
  snapMm: number
  ortho: boolean
  viewNonce: number
  viewPreset: string
}

/** Enclosure-mm centre of a component, derived from design state + nominal dims. */
function componentCenter(
  design: DesignState,
  ref: string,
  parts: Record<string, PartInfo>,
): { center: [number, number, number]; size: [number, number, number] } | null {
  const comp = design.components.find((c) => c.ref === ref)
  if (!comp) return null
  const part = parts[comp.part_id]
  const [ox, oy, oz] = design.board.origin_mm
  // Rotation is restricted to 90-degree steps, so a quarter turn simply swaps
  // the footprint's extents rather than needing a real transform.
  const swap = ((comp.rotation_deg % 180) + 180) % 180 === 90
  const l = part?.length_mm ?? 4
  const w = part?.width_mm ?? 4
  const h = part?.height_mm ?? 1
  const sx = swap ? w : l
  const sy = swap ? l : w
  const z = oz + design.board.thickness_mm
  return {
    center: [ox + comp.pos_mm[0], oy + comp.pos_mm[1], z + h / 2],
    size: [sx, sy, h],
  }
}

function ComponentMesh({
  design,
  parts,
  refName,
  model,
  selected,
  highlighted,
  explode,
  snapMm,
  onSelect,
  onDragState,
  onDragEnd,
}: {
  design: DesignState
  parts: Record<string, PartInfo>
  refName: string
  model: THREE.Object3D | null
  selected: boolean
  highlighted: boolean
  explode: number
  snapMm: number
  onSelect: (r: string) => void
  onDragState: (active: boolean) => void
  onDragEnd: (r: string, pos: [number, number]) => void
}) {
  const placed = componentCenter(design, refName, parts)
  const mesh = useRef<THREE.Mesh>(null)
  const { gl, controls } = useThree() as any
  const activeDrag = useRef(false)
  const latestPos = useRef<[number, number] | null>(null)
  const grabOffset = useRef<[number, number]>([0, 0])
  const [dragging, setDragging] = useState(false)
  // Live position during a drag, so the visual updates immediately while the
  // committed design state waits for pointer-up.
  const [live, setLive] = useState<[number, number] | null>(null)

  useEffect(() => {
    if (!dragging) setLive(null)
  }, [design.revision, dragging])

  const displayModel = useMemo(() => {
    if (!model) return null
    const clone = model.clone(true)
    clone.updateMatrixWorld(true)
    const box = new THREE.Box3().setFromObject(clone)
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3())
    const wrapper = new THREE.Group()
    clone.position.sub(center)
    wrapper.add(clone)
    wrapper.scale.set((placed?.size[0] ?? 1) * MM / Math.max(size.x, 1e-9), (placed?.size[2] ?? 1) * MM / Math.max(size.y, 1e-9), (placed?.size[1] ?? 1) * MM / Math.max(size.z, 1e-9))
    // GLB remains cached; clone materials so selection never recolors another part.
    clone.traverse(o => {
      const m = o as THREE.Mesh
      if (!m.isMesh) return
      const tint = (mat: THREE.Material) => {
        const copy = mat.clone() as THREE.MeshStandardMaterial
        if (copy.emissive) {
          copy.emissive.set(selected ? '#1d4f99' : highlighted ? '#8a4100' : '#000000')
          copy.emissiveIntensity = selected || highlighted ? 0.35 : 0
        }
        return copy
      }
      m.material = Array.isArray(m.material) ? m.material.map(tint) : tint(m.material)
    })
    return wrapper
  }, [model, selected, highlighted, placed?.size.join(',')])
  useEffect(() => () => {
    displayModel?.traverse(o => {
      const m = o as THREE.Mesh
      if (m.isMesh) (Array.isArray(m.material) ? m.material : [m.material]).forEach(mat => mat.dispose())
    })
  }, [displayModel])

  if (!placed) return null
  const comp = design.components.find((c) => c.ref === refName)!
  const part = parts[comp.part_id]
  const colour = CATEGORY_COLOR[part?.category ?? ''] ?? '#8a8f99'

  const cx = live ? design.board.origin_mm[0] + live[0] : placed.center[0]
  const cy = live ? design.board.origin_mm[1] + live[1] : placed.center[1]
  // Exploded offset is display-only: it never reaches design state, so
  // inspecting a stack cannot change what the engine measures.
  const cz = placed.center[2] + explode * 6
  const pos = toScene([cx, cy, cz])

  const onPointerDown = (e: ThreeEvent<PointerEvent>) => {
    if (e.button !== 0) return
    e.stopPropagation()
    onSelect(refName)
    activeDrag.current = true
    latestPos.current = null
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -pos[1])
    const hit = e.ray.intersectPlane(plane, new THREE.Vector3())
    grabOffset.current = hit ? [hit.x / MM - design.board.origin_mm[0] - comp.pos_mm[0], -hit.z / MM - design.board.origin_mm[1] - comp.pos_mm[1]] : [0, 0]
    if (controls) controls.enabled = false
    setDragging(true)
    onDragState(true)
    ;(e.target as Element)?.setPointerCapture?.(e.pointerId)
  }

  const onPointerMove = (e: ThreeEvent<PointerEvent>) => {
    if (!activeDrag.current) return
    e.stopPropagation()
    // Intersect the pointer ray with the board plane (scene Y = board top).
    const planeY = pos[1]
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -planeY)
    const hit = new THREE.Vector3()
    if (!e.ray.intersectPlane(plane, hit)) return
    // Back out of scene space into board-local millimetres.
    let bx = hit.x / MM - design.board.origin_mm[0]
    let by = -hit.z / MM - design.board.origin_mm[1]
    const next = dragPosition([bx, by], grabOffset.current, snapMm)
    latestPos.current = next
    setLive(next)
  }

  const finishDrag = (e: ThreeEvent<PointerEvent>, cancelled = false) => {
    if (!activeDrag.current) return
    e.stopPropagation()
    activeDrag.current = false
    setDragging(false)
    if (controls) controls.enabled = true
    gl.domElement.style.cursor = 'auto'
    ;(e.target as Element)?.releasePointerCapture?.(e.pointerId)
    onDragState(false)
    const next = latestPos.current
    if (!cancelled && next && next.some((v, i) => v !== comp.pos_mm[i])) onDragEnd(refName, next)
    latestPos.current = null
  }

  return (
    <group
      position={pos}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={e => finishDrag(e)}
      onPointerCancel={e => finishDrag(e, true)}
      onPointerOver={() => (gl.domElement.style.cursor = 'grab')}
      onPointerOut={() => !dragging && (gl.domElement.style.cursor = 'auto')}
      renderOrder={2}
    >
      {displayModel && <primitive object={displayModel} />}
      {!displayModel && <mesh>
        <boxGeometry args={[placed.size[0] * MM, placed.size[2] * MM, placed.size[1] * MM]} />
        <meshStandardMaterial color={selected ? '#b9d1ff' : highlighted ? '#ff9d2e' : colour} />
      </mesh>}
      {(selected || highlighted) && <Html position={[0, placed.size[2] * MM / 2 + 0.002, 0]} center style={{ pointerEvents: 'none', whiteSpace: 'nowrap', color: '#fff', background: '#252d39', padding: '3px 6px', borderRadius: 4, fontSize: 11 }}>
        {refName}{highlighted ? ' · Needs attention' : ''}
      </Html>}

    </group>
  )
}

/** Typed instruction renderer. Unrecognised types are ignored, never executed. */
function Overlays({ items }: { items: VizInstruction[] }) {
  return (
    <group>
      {items.map((v, i) => {
        const colour = v.color_rgb
          ? new THREE.Color(v.color_rgb[0], v.color_rgb[1], v.color_rgb[2])
          : new THREE.Color('#e0483c')

        if (v.type === 'distance_measurement' && v.from_mm && v.to_mm) {
          return (
            <Line
              key={i}
              points={[toScene(v.from_mm), toScene(v.to_mm)]}
              color={colour}
              lineWidth={2}
            />
          )
        }
        if (v.type === 'keepout_volume' && v.center_mm) {
          const c = toScene(v.center_mm)
          if (v.radius_mm) {
            return (
              <mesh key={i} position={c} rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry
                  args={[v.radius_mm * MM * 0.97, v.radius_mm * MM, 64]}
                />
                <meshBasicMaterial
                  color={colour}
                  transparent
                  opacity={0.75}
                  side={THREE.DoubleSide}
                />
              </mesh>
            )
          }
          if (v.size_mm) {
            return (
              <mesh key={i} position={c}>
                <boxGeometry
                  args={[v.size_mm[0] * MM, 0.0015, v.size_mm[1] * MM]}
                />
                <meshBasicMaterial color={colour} transparent opacity={0.22} />
              </mesh>
            )
          }
        }
        return null
      })}
    </group>
  )
}

function CameraRig({
  design,
  preset,
  nonce,
}: {
  design: DesignState
  preset: string
  nonce: number
}) {
  const { camera, controls } = useThree() as any
  useEffect(() => {
    const e = design.enclosure
    const target = new THREE.Vector3(
      ...toScene([
        e.interior_length_mm / 2,
        e.interior_width_mm / 2,
        e.interior_height_mm / 2,
      ]),
    )
    const r =
      Math.max(e.interior_length_mm, e.interior_width_mm, e.interior_height_mm) * MM
    const dirs: Record<string, THREE.Vector3> = {
      iso: new THREE.Vector3(1, 0.85, 1),
      top: new THREE.Vector3(0, 1, 0.001),
      bottom: new THREE.Vector3(0, -1, 0.001),
      front: new THREE.Vector3(0, 0.05, 1),
      side: new THREE.Vector3(1, 0.05, 0),
      fit: new THREE.Vector3(1, 0.85, 1),
    }
    const dir = (dirs[preset] ?? dirs.iso).clone().normalize()
    camera.position.copy(target.clone().add(dir.multiplyScalar(r * 1.5)))
    camera.lookAt(target)
    camera.updateProjectionMatrix()
    if (controls) {
      controls.target.copy(target)
      controls.update()
    }
  }, [preset, nonce, design.design_id])
  return null
}

function Scene(props: ViewportProps) {
  const { design, parts, analysis, show, enclosureOpacity } = props
  const [models, setModels] = useState<Record<string, THREE.Object3D>>({})
  useEffect(() => {
    let active = true
    new GLTFLoader().load('/assets/ecg_patch.glb', gltf => {
      if (!active) return
      const next: Record<string, THREE.Object3D> = {}
      for (const c of design.components) {
        const model = gltf.scene.getObjectByName(c.ref)
        if (model) next[c.ref] = model
      }
      setModels(next)
    }, undefined, () => { if (active) setModels({}) })
    return () => { active = false }
  }, [design.design_id])

  const highlighted = useMemo(() => attentionRefs(analysis, props.analysisStale, props.focusedCheck), [props.focusedCheck, analysis, props.analysisStale])

  const overlays = useMemo(() => {
    if (!show.overlays || !analysis || props.analysisStale) return []
    const focused = props.focusedCheck
      ? analysis.checks.filter((c) => c.check_id === props.focusedCheck)
      : analysis.checks.filter((c) => c.status === 'fail' || c.status === 'warning')
    return [...focused.flatMap((c) => c.viz), ...analysis.zone_viz]
  }, [analysis, show.overlays, props.focusedCheck, props.analysisStale])

  const e = design.enclosure
  const b = design.board

  return (
    <>
      <ambientLight intensity={0.75} />
      <directionalLight position={[0.15, 0.3, 0.2]} intensity={2.1} />
      <directionalLight position={[-0.2, 0.15, -0.1]} intensity={0.7} />

      <CameraRig design={design} preset={props.viewPreset} nonce={props.viewNonce} />

      {show.board && (
        <mesh
          position={toScene([
            b.origin_mm[0] + b.length_mm / 2,
            b.origin_mm[1] + b.width_mm / 2,
            b.origin_mm[2] + b.thickness_mm / 2,
          ])}
        >
          <boxGeometry
            args={[b.length_mm * MM, b.thickness_mm * MM, b.width_mm * MM]}
          />
          <meshStandardMaterial color="#1d5c30" roughness={0.8} />
        </mesh>
      )}

      {design.components.map((c) => (
        <ComponentMesh
          key={c.ref}
          design={design}
          parts={parts}
          refName={c.ref}
          model={models[c.ref] ?? null}
          selected={props.selected === c.ref}
          highlighted={highlighted.has(c.ref)}
          explode={props.explode}
          snapMm={props.snapMm}
          onSelect={props.onSelect}
          onDragState={props.onDragState}
          onDragEnd={props.onDragEnd}
        />
      ))}

      <Overlays items={overlays} />

      {/* Enclosure is drawn last and never receives pointer events, so a
          transparent shell cannot block picking the parts inside it. */}
      {show.enclosure && (
        <mesh
          position={toScene([
            e.interior_length_mm / 2,
            e.interior_width_mm / 2,
            e.interior_height_mm / 2,
          ])}
          raycast={() => null}
          renderOrder={10}
        >
          <boxGeometry
            args={[
              e.interior_length_mm * MM,
              e.interior_height_mm * MM,
              e.interior_width_mm * MM,
            ]}
          />
          <meshStandardMaterial
            color="#9fb0c4"
            transparent
            opacity={enclosureOpacity}
            depthWrite={false}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}

      <Grid
        args={[0.4, 0.4]}
        position={[0.05, -0.001, -0.02]}
        cellSize={0.005}
        sectionSize={0.025}
        cellColor="#333a45"
        sectionColor="#48525f"
        fadeDistance={0.55}
        infiniteGrid={false}
      />
      <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
    </>
  )
}

export default function Viewport(props: ViewportProps) {
  return (
    <Canvas
      camera={{ position: [0.12, 0.09, 0.12], fov: 42, near: 0.001, far: 20 }}
      orthographic={props.ortho}
      onPointerMissed={() => props.onSelect(null)}
      gl={{ antialias: true }}
      style={{ background: '#11141a' }}
    >
      <Suspense fallback={null}>
        <Scene {...props} />
      </Suspense>
    </Canvas>
  )
}
