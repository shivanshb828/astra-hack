import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Viewport from './Viewport'
import { api } from './api'
import {
  METHOD_LABEL,
  STATUS_GLYPH,
  STATUS_LABEL,
  type AnalysisCheck,
  type AnalysisResult,
  type ChatOutcome,
  type DesignState,
  type HistoryEvent,
  type Integrations,
  type PartInfo,
  type Status,
} from './types'

const VIEWS = [
  ['iso', 'Iso'],
  ['top', 'Top'],
  ['bottom', 'Bottom'],
  ['front', 'Front'],
  ['side', 'Side'],
  ['fit', 'Fit'],
] as const

export default function App() {
  const [design, setDesign] = useState<DesignState | null>(null)
  const [parts, setParts] = useState<Record<string, PartInfo>>({})
  const [integrations, setIntegrations] = useState<Integrations | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [stale, setStale] = useState(false)
  const [analysing, setAnalysing] = useState(false)
  const [history, setHistory] = useState<HistoryEvent[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [focusedCheck, setFocusedCheck] = useState<string | null>(null)
  const [rightTab, setRightTab] = useState<'component' | 'issue'>('component')
  const [drawer, setDrawer] = useState<'chat' | 'history' | null>('chat')
  const [chatLog, setChatLog] = useState<
    { role: 'user' | 'app'; text: string; outcome?: ChatOutcome }[]
  >([])
  const [chatInput, setChatInput] = useState('')
  const [banner, setBanner] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<Status | 'all'>('all')
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)

  const [show, setShow] = useState({
    board: true,
    enclosure: true,
    contact: true,
    overlays: true,
  })
  const [enclosureOpacity, setEnclosureOpacity] = useState(0.12)
  const [explode, setExplode] = useState(0)
  const [snapMm, setSnapMm] = useState(0)
  const [ortho, setOrtho] = useState(false)
  const [viewPreset, setViewPreset] = useState('iso')
  const [viewNonce, setViewNonce] = useState(0)

  // Guards against a slow job for an old revision landing on top of a newer
  // result. Every applied result must clear this bar.
  const newestRevision = useRef(0)

  const refreshHistory = useCallback(async () => {
    setHistory((await api.history()).events)
  }, [])

  const loadAnalysis = useCallback(async () => {
    const res = await api.analysis()
    if (res.result && res.result.design_revision >= newestRevision.current) {
      setAnalysis(res.result)
      setStale(res.stale)
    } else if (res.result) {
      setStale(true)
    }
  }, [])

  useEffect(() => {
    ;(async () => {
      const [d, p, i] = await Promise.all([
        api.design(),
        api.parts(),
        api.integrations(),
      ])
      setDesign(d.design)
      newestRevision.current = d.design.revision
      setParts(p.parts)
      setIntegrations(i)
      await loadAnalysis()
      await refreshHistory()
    })().catch((e) => setBanner(`Failed to load: ${e.message}`))
  }, [loadAnalysis, refreshHistory])

  /** Poll a job, then apply its result only if it is not for an older revision. */
  const pollJob = useCallback(
    async (jobId: string) => {
      setAnalysing(true)
      for (let i = 0; i < 60; i++) {
        const job = await api.job(jobId)
        if (job.status === 'done' && job.result) {
          if (job.result.design_revision >= newestRevision.current) {
            setAnalysis(job.result)
            setStale(job.stale)
          }
          setAnalysing(false)
          return
        }
        if (job.status === 'error') {
          setBanner('Analysis failed. See backend log.')
          setAnalysing(false)
          return
        }
        await new Promise((r) => setTimeout(r, 250))
      }
      setAnalysing(false)
    },
    [],
  )

  const commitEdit = useCallback(
    async (
      changes: { ref: string; field: string; after: unknown }[],
      source: string,
      summary: string,
    ) => {
      if (!design) return
      try {
        const res = await api.edit(design.revision, changes, source, summary)
        setDesign(res.design)
        newestRevision.current = res.design.revision
        setStale(true)
        setBanner(null)
        await refreshHistory()
        await pollJob(res.analysis_job_id)
      } catch (e: any) {
        if (e.status === 409) {
          setBanner(
            `Revision conflict: your edit was based on r${e.detail?.expected} but the design is at r${e.detail?.actual}. Reloading.`,
          )
          const d = await api.design()
          setDesign(d.design)
          newestRevision.current = d.design.revision
          await loadAnalysis()
        } else {
          setBanner(`Edit failed: ${JSON.stringify(e.detail ?? e.message)}`)
        }
      }
    },
    [design, pollJob, refreshHistory, loadAnalysis],
  )

  const runAnalysis = useCallback(async () => {
    const job = await api.analyze()
    await pollJob(job.job_id)
  }, [pollJob])

  const doUndo = async () => {
    try {
      const r = await api.undo()
      setDesign(r.design)
      newestRevision.current = r.design.revision
      await refreshHistory()
      await loadAnalysis()
    } catch (e: any) {
      setBanner(`Undo: ${JSON.stringify(e.detail ?? e.message)}`)
    }
  }

  const doRedo = async () => {
    try {
      const r = await api.redo()
      setDesign(r.design)
      newestRevision.current = r.design.revision
      await refreshHistory()
      await loadAnalysis()
    } catch (e: any) {
      setBanner(`Redo: ${JSON.stringify(e.detail ?? e.message)}`)
    }
  }

  const doRestore = async (revision: number) => {
    if (!design) return
    const r = await api.restore(revision, design.revision)
    setDesign(r.design)
    newestRevision.current = r.design.revision
    await refreshHistory()
    await loadAnalysis()
  }

  const sendChat = async () => {
    const message = chatInput.trim()
    if (!message) return
    setChatInput('')
    setChatLog((l) => [...l, { role: 'user', text: message }])
    const outcome = await api.chat(message)
    setChatLog((l) => [...l, { role: 'app', text: outcome.reply, outcome }])
  }

  const applyProposal = async (id: string) => {
    const r = await api.applyProposal(id)
    setDesign(r.design)
    newestRevision.current = r.design.revision
    setChatLog((l) => [...l, { role: 'app', text: `Applied. Now at revision ${r.design.revision}.` }])
    await refreshHistory()
    await loadAnalysis()
  }

  const rejectProposal = async (id: string) => {
    await api.rejectProposal(id)
    setChatLog((l) => [
      ...l,
      { role: 'app', text: 'Rejected. The design is unchanged.' },
    ])
  }

  const checks = analysis?.checks ?? []
  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    checks.forEach((x) => (c[x.status] = (c[x.status] ?? 0) + 1))
    return c
  }, [checks])

  const visibleChecks = useMemo(() => {
    const order: Status[] = ['fail', 'warning', 'unknown', 'not_applicable', 'pass']
    return checks
      .filter((c) => statusFilter === 'all' || c.status === statusFilter)
      .sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status))
  }, [checks, statusFilter])

  const selectedComp = design?.components.find((c) => c.ref === selected) ?? null
  const selectedPart = selectedComp ? parts[selectedComp.part_id] : null
  const selectedCheck = checks.find((c) => c.check_id === focusedCheck) ?? null

  if (!design) return <div className="boot">Loading MissionPCB…</div>

  return (
    <div className="app">
      <header className="toolbar">
        <div className="brand">
          <strong>MissionPCB</strong>
          <span className="muted">{design.name || design.design_id}</span>
        </div>
        <div className="chip">rev {design.revision}</div>
        <div className={`chip ${stale ? 'warn' : 'ok'}`}>
          {stale ? '! analysis stale' : '✓ analysis current'}
        </div>
        {analysing && <div className="chip">· running</div>}
        <div className="counts">
          {(['fail', 'warning', 'unknown', 'not_applicable', 'pass'] as Status[])
            .filter((s) => counts[s])
            .map((s) => (
              <span key={s} className={`tag ${s}`}>
                {STATUS_GLYPH[s]} {counts[s]} {STATUS_LABEL[s]}
              </span>
            ))}
        </div>
        <div className="spacer" />
        <button onClick={runAnalysis} disabled={analysing}>Analyze</button>
        <button onClick={doUndo}>Undo</button>
        <button onClick={doRedo}>Redo</button>
        <a className="btn" href="/api/design/export">Export</a>
      </header>

      {banner && (
        <div className="banner" onClick={() => setBanner(null)}>
          {banner} <span className="muted">(click to dismiss)</span>
        </div>
      )}

      <div className="body">
        <aside className={`left ${leftOpen ? '' : 'collapsed'}`}>
          <button className="collapse" onClick={() => setLeftOpen((v) => !v)}>
            {leftOpen ? '‹' : '›'}
          </button>
          {leftOpen && (
            <>
              <section>
                <h3>Components <span className="muted">{design.components.length}</span></h3>
                <ul className="list">
                  {design.components.map((c) => {
                    const p = parts[c.part_id]
                    const bad = checks.some(
                      (k) => k.status === 'fail' && k.component_refs.includes(c.ref),
                    )
                    return (
                      <li
                        key={c.ref}
                        className={selected === c.ref ? 'sel' : ''}
                        onClick={() => {
                          setSelected(c.ref)
                          setRightTab('component')
                          setRightOpen(true)
                        }}
                      >
                        <span className="ref">{c.ref}</span>
                        <span className="muted">{p?.name ?? c.part_id}</span>
                        {bad && <span className="tag fail">✕</span>}
                      </li>
                    )
                  })}
                </ul>
              </section>

              <section>
                <h3>Issues</h3>
                <div className="filters">
                  {(['all', 'fail', 'warning', 'unknown', 'not_applicable', 'pass'] as const).map(
                    (s) => (
                      <button
                        key={s}
                        className={statusFilter === s ? 'on' : ''}
                        onClick={() => setStatusFilter(s as Status | 'all')}
                      >
                        {s === 'all' ? 'All' : STATUS_LABEL[s as Status]}
                      </button>
                    ),
                  )}
                </div>
                <ul className="list">
                  {visibleChecks.map((c) => (
                    <li
                      key={c.check_id}
                      className={focusedCheck === c.check_id ? 'sel' : ''}
                      onClick={() => {
                        setFocusedCheck(c.check_id)
                        setRightTab('issue')
                        setRightOpen(true)
                        if (c.component_refs[0]) setSelected(c.component_refs[0])
                      }}
                    >
                      <span className={`tag ${c.status}`}>{STATUS_GLYPH[c.status]}</span>
                      <span className="ref">{c.title}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </aside>

        <main className="viewport">
          <div className="viewbar">
            {VIEWS.map(([k, label]) => (
              <button
                key={k}
                className={viewPreset === k ? 'on' : ''}
                onClick={() => {
                  setViewPreset(k)
                  setViewNonce((n) => n + 1)
                }}
              >
                {label}
              </button>
            ))}
            <span className="sep" />
            <button className={ortho ? 'on' : ''} onClick={() => setOrtho((v) => !v)}>
              {ortho ? 'Ortho' : 'Persp'}
            </button>
            <span className="sep" />
            {(['board', 'enclosure', 'overlays'] as const).map((k) => (
              <button
                key={k}
                className={show[k] ? 'on' : ''}
                onClick={() => setShow((s) => ({ ...s, [k]: !s[k] }))}
              >
                {k}
              </button>
            ))}
            <span className="sep" />
            <label>
              enclosure α
              <input
                type="range" min={0} max={0.6} step={0.02}
                value={enclosureOpacity}
                onChange={(e) => setEnclosureOpacity(+e.target.value)}
              />
            </label>
            <label>
              explode
              <input
                type="range" min={0} max={3} step={0.1}
                value={explode}
                onChange={(e) => setExplode(+e.target.value)}
              />
            </label>
            <label>
              snap
              <select value={snapMm} onChange={(e) => setSnapMm(+e.target.value)}>
                <option value={0}>off</option>
                <option value={0.5}>0.5 mm</option>
                <option value={1}>1 mm</option>
                <option value={5}>5 mm</option>
              </select>
            </label>
          </div>

          <Viewport
            design={design}
            parts={parts}
            analysis={analysis}
            analysisStale={stale}
            selected={selected}
            focusedCheck={focusedCheck}
            onSelect={(r) => {
              setSelected(r)
              if (r) setRightTab('component')
            }}
            onDragStart={() => setStale(true)}
            onDragEnd={(ref, pos) =>
              commitEdit(
                [{ ref, field: 'pos_mm', after: pos }],
                'drag',
                `Dragged ${ref} to (${pos[0]}, ${pos[1]}) mm`,
              )
            }
            show={show}
            enclosureOpacity={enclosureOpacity}
            explode={explode}
            snapMm={snapMm}
            ortho={ortho}
            viewNonce={viewNonce}
            viewPreset={viewPreset}
          />

          {explode > 0 && (
            <div className="floatnote">
              Exploded view is display-only — engineering positions are unchanged.
            </div>
          )}
        </main>

        <aside className={`right ${rightOpen ? '' : 'collapsed'}`}>
          <button className="collapse" onClick={() => setRightOpen((v) => !v)}>
            {rightOpen ? '›' : '‹'}
          </button>
          {rightOpen && (
            <>
              <div className="tabs">
                <button
                  className={rightTab === 'component' ? 'on' : ''}
                  onClick={() => setRightTab('component')}
                >
                  Component
                </button>
                <button
                  className={rightTab === 'issue' ? 'on' : ''}
                  onClick={() => setRightTab('issue')}
                >
                  Issue
                </button>
              </div>

              {rightTab === 'component' && (
                <div className="pane">
                  {!selectedComp && <p className="muted">Select a component.</p>}
                  {selectedComp && (
                    <>
                      <h3>{selectedComp.ref}</h3>
                      <p className="muted">{selectedPart?.name}</p>
                      <dl>
                        <dt>Part</dt><dd>{selectedComp.part_id}</dd>
                        <dt>Category</dt><dd>{selectedPart?.category ?? '—'}</dd>
                        <dt>Nominal size</dt>
                        <dd>
                          {selectedPart
                            ? `${selectedPart.length_mm} × ${selectedPart.width_mm} × ${selectedPart.height_mm} mm`
                            : 'unknown'}
                          <div className="hint">
                            From the parts catalogue. Moving a part never changes this.
                          </div>
                        </dd>
                        <dt>Flags</dt>
                        <dd>
                          {[
                            selectedPart?.heat_source && 'heat source',
                            selectedPart?.noise_source && 'noise source',
                            selectedPart?.skin_contact && 'skin contact',
                            selectedPart?.sensitivity !== 'none' &&
                              `sensitivity: ${selectedPart?.sensitivity}`,
                          ]
                            .filter(Boolean)
                            .join(', ') || 'none'}
                        </dd>
                      </dl>

                      <h4>Position (board-local mm)</h4>
                      <div className="numrow">
                        {(['x', 'y'] as const).map((axis, i) => (
                          <label key={axis}>
                            {axis}
                            <input
                              type="number" step={0.5}
                              value={selectedComp.pos_mm[i]}
                              onChange={(e) => {
                                const next: [number, number] = [...selectedComp.pos_mm]
                                next[i] = +e.target.value
                                commitEdit(
                                  [{ ref: selectedComp.ref, field: 'pos_mm', after: next }],
                                  'inspector',
                                  `Set ${selectedComp.ref} ${axis} to ${e.target.value} mm`,
                                )
                              }}
                            />
                          </label>
                        ))}
                        <label>
                          rot°
                          <input
                            type="number" step={90}
                            value={selectedComp.rotation_deg}
                            onChange={(e) =>
                              commitEdit(
                                [{
                                  ref: selectedComp.ref,
                                  field: 'rotation_deg',
                                  after: +e.target.value,
                                }],
                                'inspector',
                                `Rotated ${selectedComp.ref}`,
                              )
                            }
                          />
                        </label>
                      </div>
                      {selectedPart?.datasheet_url && (
                        <p>
                          <a href={selectedPart.datasheet_url} target="_blank" rel="noreferrer">
                            Datasheet source
                          </a>
                        </p>
                      )}
                    </>
                  )}
                </div>
              )}

              {rightTab === 'issue' && (
                <div className="pane">
                  {!selectedCheck && <p className="muted">Select an issue.</p>}
                  {selectedCheck && <IssuePanel check={selectedCheck} />}
                </div>
              )}

              <div className="pane integrations">
                <h4>Integrations</h4>
                {integrations && (
                  <ul className="list plain">
                    <li>
                      <span className={`tag ${integrations.blender.status === 'connected' ? 'pass' : 'unknown'}`}>
                        {integrations.blender.status === 'connected' ? '✓' : '?'}
                      </span>
                      Blender — {integrations.blender.version ?? 'not connected'}
                    </li>
                    <li>
                      <span className={`tag ${integrations.kicad.status === 'connected' ? 'pass' : 'unknown'}`}>
                        {integrations.kicad.status === 'connected' ? '✓' : '?'}
                      </span>
                      KiCad — {integrations.kicad.status === 'connected' ? 'connected' : 'Not connected'}
                    </li>
                    <li>
                      <span className="tag unknown">?</span>
                      Model — {integrations.model.mode === 'demo' ? 'Demo mode (no credentials)' : 'Provider configured'}
                    </li>
                  </ul>
                )}
                <button onClick={async () => {
                  setBanner('Running Blender export…')
                  const r = await api.blenderExport()
                  setBanner(r.ok ? 'Blender export complete.' : `Blender: ${r.reason}`)
                }}>
                  Re-export from Blender
                </button>
                <img className="render" src="/api/blender/render.png" alt="Latest Blender render of the current design" />
                <div className="hint">Blender render of the exported revision.</div>
              </div>
            </>
          )}
        </aside>
      </div>

      <footer className={`drawer ${drawer ? 'open' : ''}`}>
        <div className="drawer-tabs">
          <button className={drawer === 'chat' ? 'on' : ''} onClick={() => setDrawer(drawer === 'chat' ? null : 'chat')}>Chat</button>
          <button className={drawer === 'history' ? 'on' : ''} onClick={() => setDrawer(drawer === 'history' ? null : 'history')}>History <span className="muted">{history.length}</span></button>
          {integrations?.model.mode === 'demo' && drawer === 'chat' && (
            <span className="muted note">{integrations.model.label}</span>
          )}
        </div>

        {drawer === 'chat' && (
          <div className="drawer-body">
            <div className="chatlog">
              {chatLog.length === 0 && (
                <p className="muted">
                  Try: “Move the regulator 20 mm farther from the front end”.
                  Proposals change nothing until you apply them.
                </p>
              )}
              {chatLog.map((m, i) => (
                <div key={i} className={`msg ${m.role}`}>
                  <pre>{m.text}</pre>
                  {m.outcome?.proposal && (
                    <div className="proposal">
                      <strong>Proposed change</strong>
                      <ul>
                        {m.outcome.proposal.changes.map((c, j) => (
                          <li key={j}>
                            {c.ref}.{c.field}: {JSON.stringify(c.before)} → {JSON.stringify(c.after)}
                          </li>
                        ))}
                      </ul>
                      <button onClick={() => applyProposal(m.outcome!.proposal!.proposal_id)}>Apply</button>
                      <button onClick={() => rejectProposal(m.outcome!.proposal!.proposal_id)}>Reject</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="chatinput">
              <input
                value={chatInput}
                placeholder="Ask for a change…"
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendChat()}
              />
              <button onClick={sendChat}>Send</button>
            </div>
          </div>
        )}

        {drawer === 'history' && (
          <div className="drawer-body">
            <table className="history">
              <thead>
                <tr><th>When</th><th>Actor</th><th>Source</th><th>Rev</th><th>Change</th><th /></tr>
              </thead>
              <tbody>
                {[...history].reverse().map((e) => (
                  <tr key={e.event_id}>
                    <td className="muted">{new Date(e.timestamp).toLocaleTimeString()}</td>
                    <td>{e.actor}</td>
                    <td>{e.source}</td>
                    <td>r{e.base_revision}→r{e.result_revision}</td>
                    <td>
                      {e.summary}
                      {e.changes.map((c: any, i) => (
                        <div key={i} className="muted">
                          {c.ref ? `${c.ref}: ${JSON.stringify(c.before)} → ${JSON.stringify(c.after)}` : JSON.stringify(c)}
                        </div>
                      ))}
                    </td>
                    <td><button onClick={() => doRestore(e.result_revision)}>Restore</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </footer>
    </div>
  )
}

function IssuePanel({ check }: { check: AnalysisCheck }) {
  return (
    <>
      <h3>
        <span className={`tag ${check.status}`}>{STATUS_GLYPH[check.status]}</span>{' '}
        {check.title}
      </h3>
      <p className="muted">{check.check_id}</p>
      <dl>
        <dt>Status</dt><dd>{STATUS_LABEL[check.status]} · {check.severity}</dd>
        <dt>Category</dt><dd>{check.category.replace(/_/g, ' ')}</dd>
        {check.measured_value != null && (
          <>
            <dt>Measured</dt>
            <dd>
              {check.measured_value} {check.measured_unit}
              {check.threshold_value != null &&
                ` (needs ${check.threshold_comparison} ${check.threshold_value} ${check.measured_unit})`}
              {check.metric && <div className="hint">metric: {check.metric}</div>}
            </dd>
          </>
        )}
        <dt>Method</dt>
        <dd>
          {METHOD_LABEL[check.method]}
          {check.method === 'heuristic' && (
            <div className="hint">
              A placement heuristic, not a validated physical model.
            </div>
          )}
        </dd>
        <dt>Components</dt><dd>{check.component_refs.join(', ') || '—'}</dd>
      </dl>

      {check.explanation && <p>{check.explanation}</p>}

      {check.input_assumptions.length > 0 && (
        <>
          <h4>Assumptions</h4>
          <ul>{check.input_assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </>
      )}
      {check.missing_inputs.length > 0 && (
        <>
          <h4>Missing inputs</h4>
          <ul>{check.missing_inputs.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </>
      )}
      {check.suggested_actions.length > 0 && (
        <>
          <h4>Suggested actions</h4>
          <ul>{check.suggested_actions.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </>
      )}
      {check.rule_source && (
        <>
          <h4>Rule source</h4>
          <p className="muted">{check.rule_source}</p>
        </>
      )}
    </>
  )
}
