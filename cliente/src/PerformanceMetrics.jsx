const numbers = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1 })

export function duration(ms) {
  if (!Number.isFinite(ms)) return 'No disponible'
  return ms < 1000 ? `${numbers.format(ms)} ms` : `${numbers.format(ms / 1000)} s`
}

function memory(bytes) {
  return Number.isFinite(bytes) ? `${numbers.format(bytes / 1024**3)} GiB` : 'No disponible'
}

export default function PerformanceMetrics({ data }) {
  if (!data?.metricas) return null
  const m = data.metricas
  const speed = Number.isFinite(m.tokens_por_segundo) ? `${numbers.format(m.tokens_por_segundo)} tokens/s` : 'Velocidad no disponible'
  const items = [
    ['Modelo utilizado', data.modelo], ['Razonamiento solicitado', data.razonamiento],
    ['Duración total en Ollama', duration(m.tiempo_modelo_ms)],
    ['Latencia de la API', duration(m.tiempo_respuesta_ms)],
    ['Carga del modelo', duration(m.carga_modelo_ms)],
    ['Evaluación del prompt', duration(m.procesamiento_prompt_ms)],
    ['Generación', duration(m.generacion_ms)],
    ['Tokens de entrada', m.tokens_entrada ?? 'No disponible'],
    ['Tokens generados', m.tokens_salida ?? 'No disponible'],
    ['Velocidad de generación', speed],
    ['CPU del sistema: máximo muestreado', Number.isFinite(data.recursos?.cpu_sistema_max_porcentaje) ? `${numbers.format(data.recursos.cpu_sistema_max_porcentaje)} %` : 'No disponible'],
    ['RAM del sistema: máximo muestreado', memory(data.recursos?.ram_sistema_max_bytes)],
    ['VRAM del dispositivo: máximo muestreado', memory(data.recursos?.vram_dispositivo_max_bytes)],
    ['VRAM del modelo según Ollama (al terminar)', memory(data.ollama?.modelo_despues?.size_vram)],
    ['Finalización', data.ollama?.done_reason || 'No disponible'],
  ]
  return (
    <details className="performance">
      <summary><span className="performance-label">Rendimiento</span>
        <span>Total Ollama: {duration(m.tiempo_modelo_ms)}</span><span>{speed}</span>
      </summary>
      <div className="performance-panel">
        <dl>{items.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value ?? 'No disponible'}</dd></div>)}</dl>
        {data.ollama?.done_reason === 'length' && <strong className="truncated">Respuesta limitada por el máximo de tokens. Revisar completitud.</strong>}
        <small>Velocidad = tokens generados / segundos de generación. La duración total incluye carga y prompt; la latencia de la API también incluye cola y monitorización. Los tokenizadores son distintos y los tokens generados pueden incluir razonamiento. RAM/VRAM globales incluyen otras aplicaciones; los máximos son muestreados, no consumo exclusivo del modelo.</small>
        <small>Parámetros: {JSON.stringify(data.parametros)}<br />Catálogo: {data.catalogo_sha256}<br />Sistema: {data.sistema_sha256}<br />{data.entorno}</small>
      </div>
    </details>
  )
}
