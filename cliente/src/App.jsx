import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import PerformanceMetrics from './PerformanceMetrics'

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
  if (status === 409) return 'Para cambiar la configuración, pulsa «Nueva conversación» y vuelve a enviar tu pregunta.'
  if (status === 422) return 'La configuración no es válida para el modelo seleccionado.'
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
  const [model, setModel] = useState(null)
  const [models, setModels] = useState([])
  const [modelUnavailable, setModelUnavailable] = useState(false)
  const [modelNotice, setModelNotice] = useState('')
  const locked = busy
  const inputRef = useRef(null)
  const bottomRef = useRef(null)
  const sendingRef = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    async function loadModel() {
      try {
        const response = await fetch('/api/modelo', { signal: controller.signal })
        if (!response.ok) throw new Error('Modelo no disponible')
        const data = await response.json()
        if (!Array.isArray(data.modelos) || !data.modelos.length
          || data.modelos.some((item) => typeof item.id !== 'string' || typeof item.nombre !== 'string')
          || !data.modelos.some((item) => item.id === data.modelo)) throw new Error('Modelo no disponible')
        setModels(data.modelos)
        setModel((current) => current || data.modelo)
      } catch (cause) {
        if (cause.name !== 'AbortError') setModelUnavailable(true)
      }
    }
    loadModel()
    return () => controller.abort()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, busy, error])

  useEffect(() => {
    if (!locked) inputRef.current?.focus()
  }, [locked, model])

  useLayoutEffect(() => {
    const input = inputRef.current
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, 144)}px`
  }, [draft])

  async function sendMessage(text = draft) {
    const message = text.trim()
    if (!message || !model || sendingRef.current) return

    sendingRef.current = true
    setBusy(true)
    setError('')
    setDraft('')
    const userMessage = { id: crypto.randomUUID(), role: 'user', text: message }
    setMessages((previous) => [...previous, userMessage])

    try {
      const requestStart = performance.now()
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mensaje: message,
          modelo: model,
          ...(conversationId ? { conversacion_id: conversationId } : {}),
        }),
      })
      if (!response.ok) throw new Error(errorMessage(response.status))

      const data = await response.json()
      data.latencia_cliente_ms = performance.now() - requestStart
      if (typeof data.respuesta !== 'string' || typeof data.conversacion_id !== 'string') {
        throw new Error('El asistente devolvió una respuesta inesperada. Inténtalo de nuevo.')
      }
      setConversationId(data.conversacion_id)
      setMessages((previous) => [...previous, {
        id: crypto.randomUUID(), role: 'assistant', text: data.respuesta,
        model: data.modelo, metrics: data.metricas,
        data,
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
    setModelNotice('')
    inputRef.current?.focus()
  }

  function changeModel(event) {
    if (sendingRef.current) return
    const selected = models.find((item) => item.id === event.target.value)
    if (!selected || selected.id === model) return
    newConversation()
    setModel(selected.id)
    setModelNotice(`Nueva conversación con ${selected.nombre}.`)
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-icon"><ChatIcon /></span>
          <div>
            <h1>Asistente FISI</h1><p>Tarea 5 · LLM local + catálogo JSON</p>
          </div>
        </div>
        <button className="new-chat" onClick={newConversation} disabled={locked}>
          <span aria-hidden="true">＋</span><span>Nueva conversación</span>
        </button>
      </header>

      <div className="model-toolbar">
        <label className="model-badge" htmlFor="model">
          <span>Modelo</span>
          <select id="model" value={model || ''} onChange={changeModel} disabled={locked || !models.length} aria-describedby="model-hint">
            {!models.length && <option value="">{modelUnavailable ? 'No disponible' : 'Consultando…'}</option>}
            {models.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
          </select>
        </label>
        <span className="model-hint" id="model-hint" role="status">
          {modelUnavailable ? 'No se pudieron cargar los modelos. Recarga la página.'
            : modelNotice || 'Cambiar de modelo inicia una nueva conversación.'}
        </span>
      </div>

      <main className="thread" aria-label="Conversación">
        {messages.length === 0 && !busy && (
          <section className="welcome">
            <span className="welcome-icon"><ChatIcon /></span>
            <p className="eyebrow">TU ASISTENTE DE MATRÍCULA</p>
            <h2>¿En qué te ayudo hoy?</h2>
            <p className="intro">Pregúntame sobre tus trámites de la FISI.<br />Podemos resolver tus dudas, un mensaje a la vez.</p>
            <div className="suggestions">
              {suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => sendMessage(suggestion)} disabled={locked || !model}>{suggestion}<span aria-hidden="true">↗</span></button>
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
                {message.role === 'assistant' && <PerformanceMetrics data={message.data} />}
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
            disabled={locked || !model}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form.requestSubmit()
              }
            }}
          />
          <button className="send" type="submit" disabled={locked || !model || !draft.trim()} aria-label="Enviar mensaje" title="Enviar mensaje">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
        </form>
        <p className="composer-hint">Enter para enviar <span>·</span> Shift + Enter para una nueva línea</p>
      </footer>
    </div>
  )
}
