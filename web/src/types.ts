// Mirrors src/missionpcb_app/schema.py. Kept hand-written and small rather
// than generated, so the field names stay reviewable next to the Python.

export type Status = 'pass' | 'fail' | 'warning' | 'unknown' | 'not_applicable'
export type Severity = 'blocker' | 'major' | 'minor' | 'info'
export type Method =
  | 'geometric_check'
  | 'analytical_estimate'
  | 'external_solver'
  | 'heuristic'
  | 'fixture'

export interface ComponentState {
  ref: string
  part_id: string
  pos_mm: [number, number]
  rotation_deg: number
  anchored: boolean
  kicad_ref: string | null
}

export interface BoardState {
  id: string
  length_mm: number
  width_mm: number
  thickness_mm: number
  origin_mm: [number, number, number]
  edge_margin_mm: number
  max_component_height_mm: number
  min_component_gap_mm: number
}

export interface EnclosureState {
  interior_length_mm: number
  interior_width_mm: number
  interior_height_mm: number
  wall_thickness_mm: number
  wall_keepout_mm: number
  openings: { id: string; face: string; center_mm: number }[]
}

export interface DesignState {
  schema_version: string
  design_id: string
  revision: number
  device_type: string
  name: string
  description: string
  board: BoardState
  enclosure: EnclosureState
  components: ComponentState[]
  missing_data: string[]
}

export interface VizInstruction {
  type:
    | 'highlight_components'
    | 'distance_measurement'
    | 'keepout_volume'
    | 'patient_contact_region'
    | 'scalar_field'
    | 'annotation'
    | 'focus_camera'
  frame: 'enclosure' | 'board_local'
  units: 'mm'
  component_refs: string[]
  from_mm: [number, number, number] | null
  to_mm: [number, number, number] | null
  center_mm: [number, number, number] | null
  radius_mm: number | null
  size_mm: [number, number] | null
  label: string | null
  color_rgb: [number, number, number] | null
  marker: 'x' | 'check' | null
  zone_kind: string | null
}

export interface AnalysisCheck {
  check_id: string
  design_revision: number
  category: string
  title: string
  status: Status
  severity: Severity
  component_refs: string[]
  measured_value: number | null
  measured_unit: string | null
  threshold_value: number | null
  threshold_comparison: string | null
  metric: string
  explanation: string
  method: Method
  input_assumptions: string[]
  missing_inputs: string[]
  rule_source: string
  suggested_actions: string[]
  viz: VizInstruction[]
}

export interface AnalysisResult {
  job_id: string
  design_id: string
  design_revision: number
  engine_version: string
  source: string
  created_at: string
  summary: Record<string, number>
  checks: AnalysisCheck[]
  zone_viz: VizInstruction[]
  warnings: string[]
  approximations: string[]
}

export interface HistoryEvent {
  event_id: string
  timestamp: string
  actor: string
  source: string
  base_revision: number
  result_revision: number
  summary: string
  user_request: string
  explanation: string
  changes: Record<string, unknown>[]
  component_refs: string[]
  analysis_job_id: string | null
}

export interface PartInfo {
  id: string
  name: string
  category: string
  length_mm: number
  width_mm: number
  height_mm: number
  heat_source: boolean
  noise_source: boolean
  sensitivity: string
  skin_contact: boolean
  heat_zone_radius_mm: number | null
  placement_notes: string
  datasheet_url: string | null
}

export interface Integrations {
  kicad: { name: string; status: string; detail: string }
  blender: {
    name: string
    status: string
    detail: string
    version: string | null
    asset_present: boolean
    asset_path: string | null
  }
  model: {
    mode: string
    configured: boolean
    label: string
    supported_commands: string[]
  }
}

export interface Proposal {
  proposal_id: string
  base_revision: number
  status: string
  user_request: string
  explanation: string
  changes: { ref: string; field: string; before: unknown; after: unknown }[]
  component_refs: string[]
}

export interface ChatOutcome {
  mode: string
  provider_label: string
  reply: string
  needs_clarification: boolean
  proposal?: Proposal
}

// Status is never encoded by colour alone: each carries a glyph and a label.
export const STATUS_GLYPH: Record<Status, string> = {
  pass: '✓',
  fail: '✕',
  warning: '!',
  unknown: '?',
  not_applicable: '–',
}

export const STATUS_LABEL: Record<Status, string> = {
  pass: 'Pass',
  fail: 'Fail',
  warning: 'Warning',
  unknown: 'Unknown',
  not_applicable: 'Not evaluated',
}

export const METHOD_LABEL: Record<Method, string> = {
  geometric_check: 'Geometric check (exact)',
  analytical_estimate: 'Analytical estimate',
  external_solver: 'External solver',
  heuristic: 'Heuristic (distance proxy)',
  fixture: 'Fixture / demo data',
}
