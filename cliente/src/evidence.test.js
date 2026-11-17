import assert from 'node:assert/strict'
import { test } from 'node:test'
import { summarize, toCsv } from './evidence.js'

test('la velocidad agregada usa tiempo de generación y no la duración total', () => {
  const rows = [
    { modelo: 'qwen', razonamiento: 'desactivado', metricas: { tiempo_modelo_ms: 10000, generacion_ms: 1000, tokens_salida: 10 }, calidad: { exactitud: 2, contexto: 'na' } },
    { modelo: 'qwen', razonamiento: 'desactivado', metricas: { tiempo_modelo_ms: 20000, generacion_ms: 3000, tokens_salida: 20 }, calidad: { exactitud: 0 } },
    { modelo: 'qwen', razonamiento: 'desactivado', error: 'Sin conexión', metricas: null },
  ]
  const [result] = summarize(rows)
  assert.equal(result.total_ms, 15000)
  assert.equal(result.tokens_s, 7.5)
  assert.equal(result.errores, 1)
  assert.equal(result.calidad.exactitud.media, 1)
  assert.equal(result.calidad.exactitud.revisados, 2)
  assert.equal(result.calidad.contexto.media, null)
})

test('no agrupa configuraciones o catálogos diferentes ni inventa métricas', () => {
  const records = [
    { modelo: 'gpt', razonamiento: 'low', catalogo_sha256: 'a', parametros: { seed: 1 } },
    { modelo: 'gpt', razonamiento: 'medium', catalogo_sha256: 'a', parametros: { seed: 1 } },
    { modelo: 'gpt', razonamiento: 'low', catalogo_sha256: 'b', parametros: { seed: 1 } },
    { modelo: 'gpt', razonamiento: 'low', catalogo_sha256: 'a', parametros: { seed: 2 } },
  ]
  const groups = summarize(records)
  assert.equal(groups.length, 4)
  assert.ok(groups.every((g) => g.tokens_s === null && g.total_ms === null))
})

test('CSV protege fórmulas, conserva comillas y no convierte null en cero', () => {
  const csv = toCsv([{ pregunta: '=1+1', respuesta: 'Texto, "citado"\ny otra línea', metricas: { tokens_por_segundo: null, tokens_salida: 0 } }])
  assert.ok(csv.includes('"\'=1+1"'))
  assert.ok(csv.includes('"Texto, ""citado""\ny otra línea"'))
  assert.ok(csv.includes('"","0"'))
})
