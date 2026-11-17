import { useEffect, useRef, useState } from 'react'
import PerformanceMetrics, { duration } from './PerformanceMetrics'
import { dimensions, exportEvidence, makeRecord, summarize } from './evidence'

export default function EvaluationPanel({ models, model, reasoning, parameters, locked, onRunning, records, onRecord, onReview, experiment }) {
  const [bank, setBank] = useState(null)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState('')
  const [scope, setScope] = useState('ambos')
  const [repetitions, setRepetitions] = useState(1)
  const [selected, setSelected] = useState([])
  const [running, setRunning] = useState(false)
  const stop = useRef(false)
  const runningRef = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/evaluacion', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error('No se pudo cargar el banco de preguntas.')
      const data = await response.json()
      setBank(data)
      setSelected(data.casos.filter((item) => !item.revisar_referencias).map((item) => item.id))
    }).catch((cause) => { if (cause.name !== 'AbortError') setError(cause.message) })
    return () => controller.abort()
  }, [])

  async function run() {
    if (locked || runningRef.current || !selected.length || !Number.isInteger(repetitions) || repetitions < 1 || repetitions > 5) return
    runningRef.current = true
    stop.current = false
    setRunning(true)
    onRunning(true)
    setError('')
    const batch = crypto.randomUUID()
    const chosenModels = scope === 'ambos' ? models : models.filter((item) => item.id === model)
    const cases = bank.casos.filter((item) => selected.includes(item.id))
    let completed = 0
    const total = repetitions * chosenModels.length * cases.reduce((sum, item) => sum + item.turnos.length, 0)
    try {
      for (let repetition = 1; repetition <= repetitions; repetition++) {
        // Alterna el orden entre repeticiones; no hay solicitudes concurrentes.
        const order = repetition % 2 ? chosenModels : [...chosenModels].reverse()
        for (const current of order) {
          for (const test of cases) {
            let conversationId = null
            for (let turn = 0; turn < test.turnos.length; turn++) {
              if (stop.current) return
              const question = test.turnos[turn]
              setProgress(`${completed}/${total} · ${current.nombre} · ${test.id}, turno ${turn + 1}`)
              const context = { origen: 'evaluacion', lote_id: batch, banco_version: bank.version,
                caso_id: test.id, categoria: test.categoria, turno: turn + 1, repeticion: repetition,
                criterio: question.criterio, referencias: test.referencias }
              try {
                const requestStart = performance.now()
                const response = await fetch('/api/chat', {
                  method: 'POST', headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ mensaje: question.pregunta, modelo: current.id,
                    razonamiento: reasoning[current.id], parametros: parameters,
                    ...(conversationId ? { conversacion_id: conversationId } : {}) }),
                })
                const data = await response.json()
                data.latencia_cliente_ms = performance.now() - requestStart
                if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`)
                if (typeof data.respuesta !== 'string' || !data.conversacion_id) throw new Error('Respuesta inválida de la API.')
                conversationId = data.conversacion_id
                onRecord(makeRecord(data, question.pregunta, context))
                completed++
              } catch (cause) {
                onRecord(makeRecord({ registro_id: crypto.randomUUID(), fecha: new Date().toISOString(),
                  modelo: current.id, razonamiento: reasoning[current.id], parametros: parameters,
                  catalogo_sha256: experiment?.catalogo_sha256, sistema_sha256: experiment?.sistema_sha256,
                  entorno: experiment?.entorno, error: cause.message, metricas: null,
                }, question.pregunta, context))
                setError(`Falló ${test.id}: ${cause.message}. No se ejecutaron sus turnos dependientes.`)
                break
              }
            }
          }
        }
      }
    } finally {
      setProgress(`${stop.current ? 'Detenida' : 'Finalizada'}: ${completed} respuestas correctas HTTP de ${total} turnos previstos. La calidad requiere revisión humana.`)
      runningRef.current = false
      setRunning(false)
      onRunning(false)
    }
  }

  return <details className="evaluation">
    <summary>Evaluación y evidencia <span>{records.length} registros</span></summary>
    <div className="evaluation-content">
      <p>Ambos modelos se ejecutan en el equipo personal. Qwen3 es candidato para infraestructura económica; su desempeño en un servidor institucional sin GPU sigue pendiente.</p>
      <p>Prueba secuencial de un usuario. Usa los mismos parámetros, catálogo e instrucciones. La carga se deja natural y se registra; no se simulan concurrencia ni recursos de otro equipo.</p>
      <div className="evaluation-controls">
        <label>Modelos <select value={scope} disabled={locked} onChange={(e) => setScope(e.target.value)}><option value="ambos">Comparar ambos</option><option value="actual">Solo el seleccionado</option></select></label>
        <label>Repeticiones <input type="number" min="1" max="5" value={repetitions} disabled={locked} onChange={(e) => setRepetitions(Number(e.target.value))} /></label>
      </div>
      <p>Razonamiento del lote: {models.map((item) => `${item.nombre}: ${reasoning[item.id]}`).join(' · ')}. Configúralo en el selector de cada modelo antes de ejecutar.</p>
      {bank && <fieldset disabled={locked}><legend>Preguntas de evaluación ({bank.version})</legend>
        {bank.casos.map((test) => <label className="test-choice" key={test.id}>
          <input type="checkbox" checked={selected.includes(test.id)} disabled={test.revisar_referencias} onChange={(e) => setSelected((old) => e.target.checked ? [...old, test.id] : old.filter((id) => id !== test.id))} />
          <span>{test.categoria}: {test.turnos[0].pregunta} ({test.turnos.length} turno/s){test.revisar_referencias ? ' — revisar referencias del catálogo' : ''}</span>
        </label>)}
      </fieldset>}
      <div className="evaluation-actions">
        <button type="button" onClick={run} disabled={locked || !bank || !selected.length || !models.length || !Number.isInteger(repetitions) || repetitions < 1 || repetitions > 5}>Ejecutar evaluación</button>
        {running && <button type="button" onClick={() => { stop.current = true; setProgress('Se detendrá al terminar la respuesta en curso.') }}>Detener después de esta respuesta</button>}
        <button type="button" disabled={!records.length} onClick={() => exportEvidence(records, experiment, 'json')}>Exportar JSON</button>
        <button type="button" disabled={!records.length} onClick={() => exportEvidence(records, experiment, 'csv')}>Exportar CSV</button>
      </div>
      {progress && <p role="status">{progress}</p>}
      {error && <p className="evaluation-error" role="alert">{error}</p>}
      <p>Los registros sobreviven a «Nueva conversación», pero se pierden al recargar la página. Exporta antes de salir. En CSV se neutralizan posibles fórmulas; JSON conserva los textos originales.</p>
      {!!records.length && <>
        <h3>Rendimiento y calidad, por separado</h3>
        {summarize(records).map((group, index) => <div className="evaluation-group" key={index}>
          <strong>{group.modelo} · {group.razonamiento}</strong>
          <p>{group.validos} respuestas · {group.errores} errores · Total Ollama medio: {duration(group.total_ms)} · Velocidad agregada: {group.tokens_s == null ? 'No disponible' : `${group.tokens_s.toFixed(1)} tokens/s`}</p>
          <small>Configuración: {JSON.stringify(group.parametros)}. Solo se agrupan registros con iguales parámetros y huellas. Puede incluir cargas y respuestas de longitudes distintas.</small>
          <ul>{Object.entries(group.calidad).map(([key, item]) => <li key={key}>{dimensions[key]}: {item.media == null ? 'Sin revisión' : `${item.media.toFixed(2)}/2`} ({item.revisados} revisados)</li>)}</ul>
        </div>)}
        <h3>Revisión humana de calidad</h3>
        <p>0 = incorrecto; 1 = parcial; 2 = correcto. Deja «Pendiente» hasta revisar; usa N/A si no aplica. La velocidad no asigna puntaje de calidad.</p>
        {records.map((record) => <details className="review-record" key={record.registro_id}>
          <summary>{record.modelo} · {record.caso_id || 'Chat'} · {record.pregunta}</summary>
          <p><strong>Respuesta:</strong> {record.error || record.respuesta}</p>
          {record.criterio && <p><strong>Criterio:</strong> {record.criterio}</p>}
          {record.referencias && <pre>{JSON.stringify(record.referencias, null, 2)}</pre>}
          <PerformanceMetrics data={record} />
          {!record.error && <div className="quality-fields">
            {Object.entries(dimensions).map(([key, label]) => <label key={key}>{label}
              <select aria-label={`${label} ${record.registro_id}`} value={record.calidad?.[key] ?? ''} onChange={(e) => onReview(record.registro_id, { calidad: { ...record.calidad, [key]: e.target.value === '' ? null : e.target.value === 'na' ? 'na' : Number(e.target.value) } })}>
                <option value="">Pendiente</option><option value="na">N/A</option><option value="0">0 · Incorrecto</option><option value="1">1 · Parcial</option><option value="2">2 · Correcto</option>
              </select>
            </label>)}
            <label>Revisor <input value={record.revisor} onChange={(e) => onReview(record.registro_id, { revisor: e.target.value })} /></label>
            <label>Justificación <textarea rows="2" value={record.notas_calidad} onChange={(e) => onReview(record.registro_id, { notas_calidad: e.target.value })} /></label>
          </div>}
        </details>)}
      </>}
    </div>
  </details>
}
