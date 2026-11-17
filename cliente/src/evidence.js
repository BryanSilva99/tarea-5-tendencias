export const dimensions = {
  exactitud: 'Exactitud', catalogo: 'Cumple el catálogo', contexto: 'Mantiene contexto', sin_inventar: 'Sin información inventada',
}

export function makeRecord(data, question, extra = {}) {
  return { ...data, pregunta: question, origen: 'chat', calidad: {}, notas_calidad: '', revisor: '', ...extra }
}

export function flatten(value, prefix = '', output = {}) {
  for (const [key, item] of Object.entries(value)) {
    const name = prefix ? `${prefix}.${key}` : key
    if (item && typeof item === 'object' && !Array.isArray(item)) flatten(item, name, output)
    else output[name] = Array.isArray(item) ? JSON.stringify(item) : item
  }
  return output
}

export function toCsv(records) {
  const rows = records.map((record) => flatten(record))
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))]
  function cell(value) {
    let text = value == null ? '' : String(value)
    // Evita ejecutar texto de preguntas/respuestas como fórmulas al abrir el CSV.
    if (/^[\s]*[=+\-@]/.test(text) || /^[\t\r\n]/.test(text)) text = `'${text}`
    return `"${text.replaceAll('"', '""')}"`
  }
  return [columns.map(cell).join(','), ...rows.map((row) => columns.map((key) => cell(row[key])).join(','))].join('\r\n')
}

export function exportEvidence(records, experiment, format) {
  const content = format === 'csv' ? '\ufeff' + toCsv(records) : JSON.stringify({
    formato: 'asistente-fisi-evidencia-v1', exportado_en: new Date().toISOString(),
    protocolo: 'Prueba secuencial de un usuario en equipo personal. Carga natural, sin forzar descarga ni precalentamiento. No es prueba de concurrencia ni validación de servidor institucional.',
    experimento: experiment, registros: records,
  }, null, 2)
  const url = URL.createObjectURL(new Blob([content], { type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `fisi-resultados-${new Date().toISOString().replaceAll(':', '-')}.${format}`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function summarize(records) {
  const groups = new Map()
  for (const record of records) {
    const key = JSON.stringify([record.modelo, record.razonamiento, record.parametros, record.catalogo_sha256, record.sistema_sha256])
    if (!groups.has(key)) groups.set(key, { modelo: record.modelo, razonamiento: record.razonamiento, parametros: record.parametros, records: [] })
    groups.get(key).records.push(record)
  }
  return [...groups.values()].map((group) => {
    const ok = group.records.filter((r) => !r.error && r.metricas)
    const total = ok.map((r) => r.metricas.tiempo_modelo_ms).filter(Number.isFinite)
    const generation = ok.filter((r) => Number.isFinite(r.metricas.tokens_salida) && r.metricas.generacion_ms > 0)
    return { ...group, validos: ok.length, errores: group.records.length - ok.length,
      total_ms: total.length ? total.reduce((a, b) => a + b, 0) / total.length : null,
      tokens_s: generation.length ? generation.reduce((sum, r) => sum + r.metricas.tokens_salida, 0) / (generation.reduce((sum, r) => sum + r.metricas.generacion_ms, 0) / 1000) : null,
      calidad: Object.fromEntries(Object.keys(dimensions).map((dimension) => {
        const scores = ok.map((r) => r.calidad?.[dimension]).filter((v) => typeof v === 'number')
        return [dimension, { revisados: scores.length, media: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null }]
      })),
    }
  })
}
