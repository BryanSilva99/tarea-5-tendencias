import { useEffect, useLayoutEffect, useRef, useState } from 'react'

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M20 11.5a8 8 0 0 1-8 8H5l-3 2v-10a9 9 0 0 1 18 0Z" />
      <path d="M7 10h8M7 14h5" strokeLinecap="round" />
    </svg>
  )
}

const suggestions = [
  'Quiero hacer una rectificación.',
  '¿Qué requisitos necesito para rectificar?',
  '¿Puedo cambiarme de sección?',
]

function errorMessage(status) {
  if (status === 404) return 'Esta conversación ya no está disponible. Pulsa «Nueva conversación» para empezar de nuevo.'
  if (status === 503) return 'El asistente no está disponible en este momento. Comprueba que Ollama esté activo e inténtalo otra vez.'
  if (status === 504) return 'El asistente tardó demasiado en responder. Puedes volver a enviar tu pregunta.'
  if (status === 502) return 'No se pudo obtener una respuesta del asistente. Comprueba que la API y Ollama estén activos.'
  return 'No se pudo enviar el mensaje. Comprueba que la API esté activa e inténtalo de nuevo.'
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [conversationId, setConversationId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)
  const bottomRef = useRef(null)
  const sendingRef = useRef(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, busy, error])

  useEffect(() => {
    if (!busy) inputRef.current?.focus()
  }, [busy])

  useLayoutEffect(() => {
    const input = inputRef.current
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, 144)}px`
  }, [draft])

  async function sendMessage(text = draft) {
    const message = text.trim()
    if (!message || sendingRef.current) return

    sendingRef.current = true
    setBusy(true)
    setError('')
    setDraft('')
    const userMessage = { id: crypto.randomUUID(), role: 'user', text: message }
    setMessages((previous) => [...previous, userMessage])

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mensaje: message,
          ...(conversationId ? { conversacion_id: conversationId } : {}),
        }),
      })
      if (!response.ok) throw new Error(errorMessage(response.status))

      const data = await response.json()
      if (typeof data.respuesta !== 'string' || typeof data.conversacion_id !== 'string') {
        throw new Error('El asistente devolvió una respuesta inesperada. Inténtalo de nuevo.')
      }
      setConversationId(data.conversacion_id)
      setMessages((previous) => [...previous, {
        id: crypto.randomUUID(), role: 'assistant', text: data.respuesta,
      }])
    } catch (cause) {
      // La API tampoco guarda los turnos fallidos: permite reintentar sin duplicarlos.
      setMessages((previous) => previous.filter((item) => item.id !== userMessage.id))
      setDraft(message)
      setError(cause instanceof TypeError ? errorMessage() : cause.message)
    } finally {
      sendingRef.current = false
      setBusy(false)
    }
  }

  function newConversation() {
    if (sendingRef.current) return
    setMessages([])
    setConversationId(null)
    setDraft('')
    setError('')
    inputRef.current?.focus()
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-icon"><ChatIcon /></span>
          <div><h1>Asistente FISI</h1><p>Trámites de matrícula</p></div>
        </div>
        <button className="new-chat" onClick={newConversation} disabled={busy}>
          <span aria-hidden="true">＋</span><span>Nueva conversación</span>
        </button>
      </header>

      <main className="thread" aria-label="Conversación">
        {messages.length === 0 && !busy && (
          <section className="welcome">
            <span className="welcome-icon"><ChatIcon /></span>
            <p className="eyebrow">TU ASISTENTE DE MATRÍCULA</p>
            <h2>¿En qué te ayudo hoy?</h2>
            <p className="intro">Pregúntame sobre tus trámites de la FISI.<br />Podemos resolver tus dudas, un mensaje a la vez.</p>
            <div className="suggestions">
              {suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => sendMessage(suggestion)}>{suggestion}<span aria-hidden="true">↗</span></button>
              ))}
            </div>
          </section>
        )}

        <div className="messages" role="log" aria-label="Mensajes" aria-live="polite" aria-relevant="additions">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id} aria-label={message.role === 'user' ? 'Tú' : 'Asistente FISI'}>
              {message.role === 'assistant' && <span className="message-icon"><ChatIcon /></span>}
              <div className="message-body">
                <span className="message-author">{message.role === 'user' ? 'Tú' : 'Asistente FISI'}</span>
                <p>{message.text}</p>
              </div>
            </article>
          ))}
          {busy && (
            <div className="thinking" role="status">
              <span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>
              El asistente está pensando…
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </main>

      <footer className="footer">
        {error && <p className="error" role="alert">{error}</p>}
        <form className="composer" onSubmit={(event) => { event.preventDefault(); sendMessage() }} aria-label="Enviar un mensaje">
          <label className="sr-only" htmlFor="message">Tu mensaje</label>
          <textarea
            id="message"
            ref={inputRef}
            rows={1}
            placeholder="Escribe tu pregunta…"
            value={draft}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form.requestSubmit()
              }
            }}
          />
          <button className="send" type="submit" disabled={busy || !draft.trim()} aria-label="Enviar mensaje" title="Enviar mensaje">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
        </form>
        <p className="composer-hint">Enter para enviar <span>·</span> Shift + Enter para una nueva línea</p>
      </footer>
    </div>
  )
}
