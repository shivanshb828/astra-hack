import type {
  AnalysisResult,
  ChatOutcome,
  DesignState,
  HistoryEvent,
  Integrations,
  PartInfo,
} from './types'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail: unknown = await res.text()
    try {
      detail = JSON.parse(detail as string).detail ?? detail
    } catch {
      /* plain-text error body */
    }
    throw Object.assign(new Error(`${res.status}`), { status: res.status, detail })
  }
  return res.json() as Promise<T>
}

export const api = {
  design: () =>
    req<{ design: DesignState; current_revision: number; revisions: number[] }>(
      '/api/design',
    ),

  parts: () => req<{ parts: Record<string, PartInfo>; warnings: string[] }>('/api/parts'),

  integrations: () => req<Integrations>('/api/integrations'),

  /** Revision-checked. Throws with status 409 when the base is stale. */
  edit: (
    baseRevision: number,
    changes: { ref: string; field: string; after: unknown }[],
    source = 'inspector',
    summary = '',
  ) =>
    req<{ design: DesignState; analysis_job_id: string }>('/api/design/edit', {
      method: 'POST',
      body: JSON.stringify({
        base_revision: baseRevision,
        changes,
        source,
        summary,
      }),
    }),

  analyze: () =>
    req<{ job_id: string; design_revision: number }>('/api/design/analyze', {
      method: 'POST',
    }),

  job: (id: string) =>
    req<{
      status: string
      design_revision: number
      current_revision: number
      stale: boolean
      result?: AnalysisResult
    }>(`/api/jobs/${id}`),

  analysis: () =>
    req<{ result: AnalysisResult | null; stale: boolean; current_revision: number }>(
      '/api/design/analysis',
    ),

  history: () => req<{ events: HistoryEvent[] }>('/api/design/history'),

  undo: () => req<{ design: DesignState }>('/api/design/undo', { method: 'POST' }),
  redo: () => req<{ design: DesignState }>('/api/design/redo', { method: 'POST' }),

  restore: (revision: number, baseRevision: number) =>
    req<{ design: DesignState }>('/api/design/restore', {
      method: 'POST',
      body: JSON.stringify({ revision, base_revision: baseRevision }),
    }),

  chat: (message: string) =>
    req<ChatOutcome>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  applyProposal: (id: string) =>
    req<{
      design: DesignState
      native_tool?: {
        kicad?: {
          synced: boolean
          changes: unknown[]
        }
      }
    }>(`/api/proposals/${id}/apply`, { method: 'POST' }),

  rejectProposal: (id: string) =>
    req<{ status: string }>(`/api/proposals/${id}/reject`, { method: 'POST' }),

  blenderExport: () =>
    req<{ ok: boolean; reason?: string; log?: string }>('/api/blender/export', {
      method: 'POST',
    }),

  kicadDrc: () =>
    req<{ ok: boolean; status?: string; detail?: string }>('/api/kicad/drc', {
      method: 'POST',
      body: JSON.stringify({ board: '' }),
    }),

  kicadFootprints: () =>
    req<{
      board: string
      footprints: { ref: string; position_mm: [number, number]; rotation_deg: number }[]
    }>('/api/kicad/footprints'),

  moveKicadFootprint: (ref: string, xMm: number, yMm: number, rotationDeg?: number) =>
    req<{
      changed: boolean
      ref: string
      before: { position_mm: [number, number]; rotation_deg: number }
      after: { position_mm: [number, number]; rotation_deg: number }
    }>('/api/kicad/footprints/move', {
      method: 'POST',
      body: JSON.stringify({
        ref,
        x_mm: xMm,
        y_mm: yMm,
        rotation_deg: rotationDeg,
      }),
    }),

  widgetSend: (message: string, autoMode: boolean) =>
    req<{
      outcome: ChatOutcome
      auto_applied: boolean
      apply_result?: {
        design: DesignState
        native_tool?: {
          kicad?: {
            synced: boolean
            changes: unknown[]
          }
        }
      }
    }>('/api/widget/send', {
      method: 'POST',
      body: JSON.stringify({ message, auto_mode: autoMode }),
    }),

  widgetMonitor: () =>
    req<{
      ok: boolean
      design_revision: number
      integrations: Integrations
      latest_kicad_reload: null | {
        mutation?: {
          ref?: string
        }
      }
    }>('/api/widget/monitor'),
}
