# Protocolo de evaluación — Asistente FISI, Tarea 5

## Pregunta y alcance

¿Es viable responder consultas universitarias con un LLM local y el catálogo completo `tramites_fisi.json` en el mensaje de sistema, sin RAG, embeddings ni búsqueda vectorial?

Se comparan GPT-OSS 20B y Qwen3 4B Q4_K_M inicialmente en la misma computadora personal. El primero representa el escenario de un equipo personal con aceleración GPU; el segundo es un candidato para evaluar posteriormente en infraestructura institucional económica. La residencia en VRAM se registra desde Ollama y no se supone que todo el modelo está en GPU.

No se ha validado aquí un servidor institucional sin GPU. Tampoco se realiza una prueba de carga. Que una respuesta funcione o que varias peticiones se encolen no acredita atender a 20 usuarios simultáneos, con una RTX 3060 ni con otro equipo.

## Condiciones que se conservan

- Un solo catálogo y un mismo mensaje de sistema construido en `main.py`. Se guardan sus SHA-256 y una copia en los metadatos JSON de exportación. No se incorporan respuestas esperadas al prompt.
- Los mismos valores explícitos de temperatura, semilla, contexto y límite de generación. Se guardan en cada respuesta. Una semilla común no garantiza determinismo entre modelos/hardware.
- GPT-OSS acepta razonamiento `low`, `medium` y `high`; Qwen3 acepta activado/desactivado. Los valores no son niveles equivalentes entre familias. Comparar configuraciones explícitas, sin atribuir al modelo diferencias causadas por razonamiento.
- Cada caso arranca un historial independiente. Los turnos del caso de contexto reutilizan la conversación. Los historiales generados pueden divergir entre modelos; se conservan las respuestas y el orden de los turnos.
- Los lotes son secuenciales y alternan el orden de modelos entre repeticiones. Cerrar otras aplicaciones exigentes y evitar consultas externas mientras se mide ayuda a reducir interferencias.
- Se deja la **carga natural** de Ollama: no se descarga ni precalienta artificialmente cada caso. Se registran carga y residencia antes/después. Separar análisis de primera carga y respuestas residentes; no declarar una ejecución «fría» o «caliente» solo por su posición.

Valores iniciales actuales: temperatura 0,2; semilla 42; contexto 8192 tokens; límite 1024 tokens generados. GPT-OSS: medio. Qwen3: activado. Las evidencias históricas conservan el modo usado en su ejecución; no se modifican al cambiar el predeterminado. El contexto debe cubrir instrucciones, catálogo e historial; el razonamiento puede consumir el límite de salida. `done_reason=length` señala una salida limitada, no una respuesta necesariamente completa. Si crece el JSON o el historial, revisar el contexto y repetir ambos modelos con el mismo límite.

## Rendimiento

| Campo | Interpretación |
|---|---|
| `metricas.tiempo_modelo_ms` | `total_duration / 1e6`: duración total que reporta Ollama |
| `metricas.carga_modelo_ms` | `load_duration / 1e6` |
| `metricas.procesamiento_prompt_ms` | `prompt_eval_duration / 1e6` |
| `metricas.generacion_ms` | `eval_duration / 1e6` |
| `metricas.tokens_salida` | `eval_count` de Ollama; puede incluir razonamiento |
| `metricas.tokens_por_segundo` | `eval_count / (eval_duration / 1e9)`; usa solo generación |
| `metricas.tiempo_respuesta_ms` | Tramo de ejecución de la API: incluye cola, inferencia y monitorización; excluye red del cliente y serialización final |
| `latencia_cliente_ms` | Solicitud y lectura de JSON medidas en el navegador o CLI |
| `ollama.duraciones_ns` | Duraciones originales sin conversión |

Si falta un dato, se conserva `null`/«No disponible». Una duración de generación cero no se convierte en velocidad infinita. La velocidad agregada usa suma de tokens / suma de segundos de generación; no es una medida de exactitud. Los modelos usan tokenizadores diferentes, así que tokens/s no equivale a comparar palabras/s. Las duraciones parciales no tienen por qué sumar exactamente el total debido al procesamiento adicional de Ollama.

Los sensores usan biblioteca estándar: `/proc/meminfo`, `/proc/stat` y, si existe, `nvidia-smi`. Se toma una muestra inicial, periódicas con intervalo de espera de 0,5 s y una final. El coste de leer sensores añade sobrecarga a la API; los tiempos internos de Ollama se conservan por separado. El periodo real entre muestras incluye el coste de lectura y puede superar 0,5 s. No son picos continuos ni una medición de energía.

CPU, RAM y VRAM muestreadas corresponden al **equipo completo**, incluidas otras aplicaciones. GPU incluye nombre, memoria y porcentaje de utilización. La VRAM global no es la VRAM exclusiva del LLM. `ollama.modelo_despues.size_vram` registra la instantánea de memoria del modelo según `/api/ps`; no representa su pico. En plataformas sin sensores compatibles se exporta `null`, sin estimar consumo. No se mide consumo eléctrico ni se deducen costos por usuario.

Referencias técnicas: [respuesta de chat de Ollama](https://docs.ollama.com/api/chat), [controles de razonamiento](https://docs.ollama.com/capabilities/thinking), [modelos residentes y VRAM](https://docs.ollama.com/api/ps).

## Calidad

`preguntas_evaluacion.json` contiene 10 casos y 12 turnos: aclaración inicial, documentos, plazos específicos frente al cronograma general, canal desconocido, vacantes desconocidas, costo de reserva, contexto multivuelta, autorización, periodos no cubiertos y enlaces no disponibles.

Los fragmentos para el revisor se resuelven desde el catálogo cargado, sin una segunda fuente factual. Si se cambia el catálogo, revisar la vigencia de las preguntas y criterios, y volver a exportar sus referencias. No se consulta la web para completar los datos universitarios durante la inferencia. La prueba mide fidelidad al catálogo, no certifica que su contenido esté oficialmente vigente.

La revisión humana puntúa cada dimensión por respuesta:

| Dimensión | 0 — Incorrecto | 1 — Parcial | 2 — Correcto |
|---|---|---|---|
| Exactitud | Contradice el dato aplicable | Respuesta incompleta o ambigua | Responde correctamente lo solicitado |
| Uso del catálogo | Mezcla trámites/periodos o usa datos ajenos | Omite una condición relevante | Conserva datos, alcance y condiciones |
| Contexto | Pierde o interpreta mal el referente | Mantiene solo parte del contexto | Resuelve el seguimiento correctamente |
| Ausencia de información inventada | Inventa requisitos, fechas, enlaces o aprobaciones | Expresa una certeza no sustentada | Se limita al catálogo y reconoce lo desconocido |

Usar N/A cuando la dimensión no aplique (por ejemplo, contexto en una pregunta aislada). Dejar pendiente hasta revisar. Registrar revisor y justificación; no convertir pendientes/N/A en ceros. Las medias de cada dimensión se calculan solo sobre puntajes numéricos revisados, mostrando su cantidad. No se aplica un evaluador LLM ni una coincidencia de palabras como supuesto indicador de precisión.

## Ejecución, exportación y conclusiones

1. Iniciar Ollama, FastAPI y React según README; comprobar los dos modelos instalados.
2. La interfaz simplificada oculta razonamiento, parámetros y evaluación. Para comparar configuraciones, usar las opciones de `evaluar.py --help`. Empezar con una repetición para comprobar el flujo; usar más para estudiar variabilidad.
3. Ejecutar `uv run python evaluar.py --repeticiones 3 --salida resultados/comparacion.json`. Se mantienen todos los turnos del caso de contexto. La CLI guarda JSON y CSV tras cada respuesta. Los fallos se guardan como errores, sin métricas ficticias; se omiten turnos dependientes del caso fallido.
4. Revisar calidad contra las referencias y completar los puntajes, revisor y justificación en el JSON exportado.

JSON conserva muestras, textos originales, configuración, criterios y metadatos. CSV aplana campos con puntos y serializa listas como JSON; protege texto que podría interpretarse como fórmula. La clave `registro_id` permite identificar respuestas y `lote_id` los lotes. Los archivos de CLI pueden revisarse editando `calidad`, `notas_calidad` y `revisor` en el JSON; los puntajes iniciales están pendientes.

Recomendar infraestructura exige considerar **calidad y rendimiento** juntos. Un resultado rápido con invenciones no cumple el objetivo. El muestreo personal sirve para seleccionar un candidato; después se necesita ejecutar la misma batería en el servidor propuesto, con CPU/RAM/GPU reales, y realizar una prueba de carga independiente si habrá varios usuarios. No extrapolar capacidades de concurrencia ni calidad por número de parámetros o tokens/s.
