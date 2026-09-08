import { useEffect, useRef, useState } from 'react'
import { api } from './api'

type Msg = {
  role: 'user' | 'astra'
  text: string
  proposalId?: string
}

export default function App() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [autoMode, setAutoMode] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('Connecting...')
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    api
      .widgetMonitor()
      .then((res) => {
        const kicad = res.integrations.kicad.status === 'connected' ? 'KiCad ready' : 'KiCad offline'
        const model = res.integrations.model.configured ? 'model ready' : 'local fallback'
        setStatus(`${kicad} · ${model}`)
      })
      .catch(() => setStatus('Backend offline'))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    setMessages((items) => [...items, { role: 'user', text }])
    try {
      const res = await api.widgetSend(text, autoMode)
      const outcome = res.outcome
      const proposal = outcome.proposal
      const applied = res.auto_applied ? '\n\nApplied in KiCad.' : ''
      const next = proposal && !res.auto_applied
        ? '\n\nReview this move, then press Apply.'
        : ''
      setMessages((items) => [
        ...items,
        {
          role: 'astra',
          text: `${outcome.reply}${next}${applied}`,
          proposalId: proposal?.proposal_id,
        },
      ])
      const monitor = await api.widgetMonitor()
      const last = monitor.latest_kicad_reload?.mutation
      if (last?.ref) {
        setStatus(`KiCad updated · ${last.ref} moved`)
      }
    } catch (e: any) {
      setMessages((items) => [
        ...items,
        { role: 'astra', text: `I could not reach the widget backend: ${e.message}` },
      ])
    } finally {
      setBusy(false)
    }
  }

  const apply = async (proposalId: string) => {
    setBusy(true)
    try {
      const res = await api.applyProposal(proposalId)
      const kicad = res.native_tool?.kicad
      setMessages((items) => [
        ...items,
        {
          role: 'astra',
          text: kicad?.synced
            ? 'Applied. I updated the KiCad board file; reload KiCad if prompted.'
            : 'Applied to the design state. KiCad did not report a matching native footprint.',
        },
      ])
      setStatus(kicad?.synced ? 'KiCad updated' : `Design rev ${res.design.revision}`)
    } catch (e: any) {
      setMessages((items) => [...items, { role: 'astra', text: `Apply failed: ${e.message}` }])
    } finally {
      setBusy(false)
    }
  }

  const annotate = async (ref: string, note: string) => {
    setBusy(true)
    try {
      const res = await api.annotateKicad(ref, note)
      setMessages((items) => [
        ...items,
        { role: 'astra', text: `Marked ${res.ref} in KiCad: ${res.note}` },
      ])
      setStatus(`KiCad marked · ${res.ref}`)
    } catch (e: any) {
      setMessages((items) => [...items, { role: 'astra', text: `Mark failed: ${e.message}` }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="artifact-shell">
      <section className="astra-widget" aria-label="Astra KiCad widget">
        <header>
          <div className="mark">A</div>
          <div>
            <strong>Astra KiCad</strong>
            <span>{status}</span>
          </div>
          <label className="auto" title="When enabled, safe proposals are applied immediately instead of waiting for Apply.">
            <input
              type="checkbox"
              checked={autoMode}
              onChange={(event) => setAutoMode(event.target.checked)}
            />
            Auto-apply
          </label>
        </header>

        <div className="promptbar">
          <button onClick={() => annotate('AFE', 'sensitive analog front end')} disabled={busy}>
            Mark AFE
          </button>
          <button onClick={() => annotate('BUCK', 'switching regulator noise source')} disabled={busy}>
            Mark BUCK
          </button>
          <button onClick={() => annotate('CELL', 'verify battery height and safety')} disabled={busy}>
            Mark CELL
          </button>
        </div>

        <div className="thread">
          {messages.length === 0 && (
            <div className="empty">
              <span>Ask Astra to inspect or change the open KiCad board.</span>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={index} className={`bubble ${message.role}`}>
              <p>{message.text}</p>
              {message.proposalId && (
                <button onClick={() => apply(message.proposalId!)} disabled={busy}>
                  Apply
                </button>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault()
            send()
          }}
        >
          <textarea
            value={input}
            rows={2}
            placeholder="Build a rechargeable 7-day ECG patch for continuous patient monitoring."
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                send()
              }
            }}
          />
          <button type="submit" disabled={busy || !input.trim()}>
            {busy ? '...' : 'Send'}
          </button>
        </form>
      </section>
    </main>
  )
}
