# Primera ejecución real en equipo personal

Fecha de exportación: 2026-11-17T01:05:03.894746+00:00. Una repetición por modelo; 10 casos, 12 turnos por modelo, 24 respuestas sin errores HTTP.

Los registros originales están en [JSON](poc-equipo-personal.json) y [CSV](poc-equipo-personal.csv). Son mediciones reales de un flujo secuencial, no pruebas de concurrencia ni de un servidor institucional.

Equipo: NVIDIA GeForce RTX 5070, aproximadamente 12 GiB de VRAM, 31,1 GiB de RAM; Linux. Ambos modelos usaron aceleración GPU en esta máquina. La residencia exacta y las muestras del equipo están dentro de cada registro.

Configuración común: temperatura 0,2; semilla 42; contexto 8192; máximo de generación 1024. Carga natural, sin forzar descarga ni precalentamiento.

| Modelo | Razonamiento | Respuestas | Total Ollama medio | Mediana | Velocidad agregada de generación |
|---|---|---:|---:|---:|---:|
| gpt-oss:20b | medium | 12 | 6.05 s | 6.78 s | 55.02 tokens/s |
| qwen3:4b-q4_K_M | desactivado | 12 | 0.69 s | 0.39 s | 149.89 tokens/s |

Estos promedios incluyen casos de distintas longitudes y cargas. Los modos de razonamiento y tokenizadores son distintos; las cifras no establecen una comparación de calidad ni un ganador universal.

## Observaciones para revisión de calidad

Los puntajes se mantienen pendientes de revisión humana. La velocidad no se usó para asignarlos.

- En `requisitos`, Qwen3 respondió con otra pregunta en lugar de enumerar los documentos solicitados. Revisar exactitud y seguimiento de instrucciones.
- En `contexto`, primer turno, Qwen3 pidió el motivo de anulación en lugar de responder la consulta sobre presentar solo anulación.
- En `contexto`, segundo turno, GPT-OSS extendió la restricción explícita de reserva para ingresantes a una afirmación sobre anulación. Revisar si esa generalización está sustentada por el catálogo.
- En `otro_periodo`, ambos reconocieron la ausencia de información de 2028-I y añadieron datos históricos de 2026-II. Revisar pertinencia y cumplimiento de la instrucción sobre datos desconocidos.

Estas observaciones describen esta ejecución y sus respuestas; no son porcentajes de precisión ni un sustituto de la rúbrica.

## Trazabilidad y siguiente validación

Catálogo SHA-256: `b9700e388c5bc8972b7895c6d505e906694ee20f93d62ef254052a85fdafbf00`.

Sistema SHA-256: `268a05783d77fdc1e0e3d1443e4cf0f7daee95647839b8a1d7f1a8230e51a8b4`.

Se verificó que las 24 respuestas comparten ambas huellas y los parámetros comunes. JSON incluye copia del catálogo y mensaje de sistema, criterios, versiones y muestras de recursos. `size_vram` es una instantánea del modelo, mientras los sensores globales también incluyen otras aplicaciones.

Qwen3 sigue siendo un candidato ligero. Antes de recomendar el servidor institucional hay que completar la revisión de calidad, repetir las mediciones y ejecutar esta batería en el hardware económico propuesto. La prueba de carga multiusuario es un trabajo independiente.
