import { Canvas, ThreeEvent, useFrame, useThree } from '@react-three/fiber'
import { Grid, Line, OrbitControls, useGLTF } from '@react-three/drei'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
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
  onDragStart: () => void
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
  geometry,
  selected,
  highlighted,
  explode,
  snapMm,
  onSelect,
  onDragStart,
  onDragEnd,
}: {
  design: DesignState
  parts: Record<string, PartInfo>
  refName: string
  geometry: THREE.BufferGeometry | null
  selected: boolean
  highlighted: boolean
  explode: number
  snapMm: number
  onSelect: (r: string) => void
  onDragStart: () => void
  onDragEnd: (r: string, pos: [number, number]) => void
}) {
  const placed = componentCenter(design, refName, parts)
  const mesh = useRef<THREE.Mesh>(null)
  const { camera, gl } = useThree()
  const [dragging, setDragging] = useState(false)
  // Live position during a drag, so the visual updates immediately while the
  // committed design state waits for pointer-up.
  const [live, setLive] = useState<[number, number] | null>(null)

  useEffect(() => {
    if (!dragging) setLive(null)
  }, [design.revision, dragging])

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
    e.stopPropagation()
    onSelect(refName)
    setDragging(true)
    onDragStart()
    ;(e.target as Element)?.setPointerCapture?.(e.pointerId)
  }

  const onPointerMove = (e: ThreeEvent<PointerEvent>) => {
    if (!dragging) return
    e.stopPropagation()
    // Intersect the pointer ray with the board plane (scene Y = board top).
    const planeY = toScene([0, 0, placed.center[2]])[1]
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -planeY)
    const hit = new THREE.Vector3()
    if (!e.ray.intersectPlane(plane, hit)) return
    // Back out of scene space into board-local millimetres.
    let bx = hit.x / MM - design.board.origin_mm[0]
    let by = -hit.z / MM - design.board.origin_mm[1]
    if (snapMm > 0) {
      bx = Math.round(bx / snapMm) * snapMm
      by = Math.round(by / snapMm) * snapMm
    }
    setLive([Number(bx.toFixed(3)), Number(by.toFixed(3))])
  }

  const onPointerUp = (e: ThreeEvent<PointerEvent>) => {
    if (!dragging) return
    e.stopPropagation()
    setDragging(false)
    gl.domElement.style.cursor = 'auto'
    // Exactly one history event per drag, committed on release.
    if (live) onDragEnd(refName, live)
  }

  return (
    <mesh
      ref={mesh}
      position={pos}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerOver={() => (gl.domElement.style.cursor = 'grab')}
      onPointerOut={() => !dragging && (gl.domElement.style.cursor = 'auto')}
      geometry={geometry ?? undefined}
      scale={
        geometry
          ? [1, 1, 1]
          : [placed.size[0] * MM, placed.size[2] * MM, placed.size[1] * MM]
      }
      renderOrder={2}
    >
      {!geometry && <boxGeometry args={[1, 1, 1]} />}
      <meshStandardMaterial
        color={selected ? '#ffffff' : highlighted ? '#ff9d2e' : colour}
        emissive={selected ? '#3d7dff' : highlighted ? '#a3520f' : '#000000'}
        emissiveIntensity={selected ? 0.55 : highlighted ? 0.45 : 0}
        metalness={0.1}
        roughness={0.65}
      />
    </mesh>
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
  const gltf = useGLTF('/assets/ecg_patch.glb', true) as any

  // Map GLB objects to stable component ids by name. This is the asset
  // contract: components arrive individually addressable, not merged.
  const geoms = useMemo(() => {
    const out: Record<string, THREE.BufferGeometry> = {}
    gltf?.scene?.traverse?.((o: THREE.Object3D) => {
      const m = o as THREE.Mesh
      if (m.isMesh && m.geometry) out[o.name] = m.geometry
    })
    return out
  }, [gltf])

  const highlighted = useMemo(() => {
    if (!props.focusedCheck || !analysis) return new Set<string>()
    const c = analysis.checks.find((x) => x.check_id === props.focusedCheck)
    return new Set(c?.component_refs ?? [])
  }, [props.focusedCheck, analysis])

  const overlays = useMemo(() => {
    if (!show.overlays || !analysis) return []
    const focused = props.focusedCheck
      ? analysis.checks.filter((c) => c.check_id === props.focusedCheck)
      : analysis.checks.filter((c) => c.status === 'fail')
    return [...focused.flatMap((c) => c.viz), ...analysis.zone_viz]
  }, [analysis, show.overlays, props.focusedCheck])

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
          geometry={geoms[c.ref] ?? null}
          selected={props.selected === c.ref}
          highlighted={highlighted.has(c.ref)}
          explode={props.explode}
          snapMm={props.snapMm}
          onSelect={props.onSelect}
          onDragStart={props.onDragStart}
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

useGLTF.preload('/assets/ecg_patch.glb')
