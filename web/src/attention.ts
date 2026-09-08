import type { AnalysisResult } from './types'

export function attentionRefs(analysis: AnalysisResult | null, stale: boolean, focused: string | null) {
  if (!analysis || stale) return new Set<string>()
  return new Set(analysis.checks
    .filter(c => focused ? c.check_id === focused : c.status === 'fail' || c.status === 'warning')
    .flatMap(c => c.component_refs))
}

/** Keep the original grab point under the cursor, in board-local millimetres. */
export function dragPosition(hit: [number, number], offset: [number, number], snap: number): [number, number] {
  return hit.map((n, i) => {
    const value = n - offset[i]
    return Number((snap > 0 ? Math.round(value / snap) * snap : value).toFixed(3))
  }) as [number, number]
}
