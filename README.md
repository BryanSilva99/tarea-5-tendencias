# Tarea 5 Tendencias — Asistente FISI

Aplicación de chat para consultar trámites de matrícula de la FISI. Incluye una interfaz web en React, una API HTTP con FastAPI y un asistente con dos modelos locales seleccionables mediante Ollama: `gpt-oss:20b` y `qwen3:4b-q4_K_M`.

La prueba de concepto evalúa la viabilidad de un chatbot universitario con **un LLM local y una única base JSON, sin RAG**. GPT-OSS representa el escenario de equipo personal con aceleración GPU; Qwen3 es el candidato ligero para una futura infraestructura económica de la FISI. **Ambos se prueban inicialmente en la misma computadora personal**. Esto no valida un servidor institucional sin GPU ni su capacidad de concurrencia.

El asistente responde en español, conserva el contexto de cada conversación y utiliza como única fuente el catálogo `tramites_fisi.json`. Ambos modelos reciben exactamente el mismo mensaje de sistema y catálogo; sus huellas SHA-256 quedan en los resultados. El catálogo incluye rectificación, matrícula extemporánea y anulación/reserva. No requiere una clave de API de OpenAI ni una base de datos.

Consulta [EVALUACION.md](EVALUACION.md) para el protocolo, la rúbrica de calidad, la interpretación de recursos y los límites de las conclusiones.

## Contenido

- [Arquitectura y estructura](#arquitectura-y-estructura)
- [Requisitos](#requisitos)
- [Instalación inicial](#instalación-inicial)
- [Levantar la aplicación completa](#levantar-la-aplicación-completa)
- [Usar el chat](#usar-el-chat)
- [Consumir la API](#consumir-la-api)
- [Ejecutar por consola](#ejecutar-por-consola)
- [Pruebas y compilación](#pruebas-y-compilación)
- [Evaluación y exportación de evidencia](#evaluación-y-exportación-de-evidencia)
- [Solución de problemas](#solución-de-problemas)
- [Configuración y límites](#configuración-y-límites)

## Arquitectura y estructura

```text
Navegador → React / Vite → FastAPI → Ollama → gpt-oss:20b / qwen3:4b-q4_K_M
             :5173        :8000     :11434
```

El navegador envía solicitudes a `/api/chat` en el mismo origen del cliente. Vite elimina `/api` y las reenvía a `http://127.0.0.1:8000/chat`. La API reutiliza las instrucciones, el catálogo y la función de respuesta de `main.py`.

```text
.
├── README.md                 # Instalación, uso y diagnóstico
├── .gitignore                # Exclusión de archivos locales
├── pyproject.toml            # Dependencias Python
├── uv.lock                   # Versiones resueltas de Python
├── main.py                   # Asistente, instrucciones y consola
├── api.py                    # Endpoints HTTP e historiales
├── tramites_fisi.json         # Catálogo del asistente
├── solicitudes.http          # Peticiones para VS Code REST Client
├── test_api.py               # Pruebas con Ollama simulado
├── experimento.py            # Modelos, razonamiento y parámetros compartidos
├── telemetria.py              # CPU/RAM/GPU del equipo y residencia de Ollama
├── evaluacion.py              # Referencias de evaluación resueltas desde el catálogo
├── preguntas_evaluacion.json  # Preguntas y rúbricas; no es otra base de conocimiento
├── evaluar.py                 # Ejecución secuencial reproducible por CLI
├── evidencia.py               # Exportación JSON y CSV para CLI
├── EVALUACION.md              # Protocolo y alcance de las conclusiones
└── cliente/
    ├── package.json          # Dependencias y comandos del cliente
    ├── package-lock.json     # Versiones resueltas de Node
    ├── vite.config.js        # Puertos y proxy hacia FastAPI
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx           # Interfaz de chat
        └── styles.css
```

## Requisitos

| Herramienta | Requisito |
| --- | --- |
| Git | Para clonar el repositorio |
| Python | 3.14 o superior, según `pyproject.toml` |
| uv | Para instalar Python y las dependencias del servidor |
| Node.js y npm | Node 20 desde 20.19.0, o Node 22 desde 22.12.0 y versiones superiores compatibles con Vite |
| Ollama | Instalado y disponible en `127.0.0.1:11434` |
| Modelos | `gpt-oss:20b` y `qwen3:4b-q4_K_M`, descargados mediante Ollama |

Se necesita Internet para instalar herramientas, dependencias y descargar el modelo. La inferencia se realiza localmente. El modelo ocupa varios GB en disco y necesita memoria suficiente para cargarse; el tiempo de respuesta depende del equipo.

Instala [Git](https://git-scm.com/downloads), [Node.js](https://nodejs.org/en/download), [uv](https://docs.astral.sh/uv/getting-started/installation/) y [Ollama](https://ollama.com/download) según las instrucciones oficiales para tu sistema operativo.

Comprueba las herramientas:

```bash
git --version
uv --version
node --version
npm --version
ollama --version
```

## Instalación inicial

### 1. Clonar el repositorio

```bash
git clone https://github.com/BryanSilva99/tarea-5-tendencias.git
cd tarea-5-tendencias
```

La carpeta con `api.py` y `pyproject.toml` es la raíz. Los siguientes comandos parten de esa carpeta, salvo que se indique `cd cliente`.

### 2. Instalar Python y las dependencias de la API

```bash
uv python install 3.14
uv sync --locked --python 3.14
```

`uv` crea `.venv` y utiliza las versiones de `uv.lock`. No hace falta activar el entorno manualmente: `uv run` lo utiliza.

### 3. Instalar las dependencias del cliente

```bash
cd cliente
npm ci
cd ..
```

`npm ci` instala las versiones de `package-lock.json`.

### 4. Descargar el modelo

Abre Ollama. Si no está ejecutándose como aplicación o servicio, inicia el servidor en una terminal y déjala abierta:

```bash
ollama serve
```

En otra terminal descarga el modelo y comprueba que está instalado:

```bash
ollama pull gpt-oss:20b
ollama pull qwen3:4b-q4_K_M
ollama list
```

No inicies una segunda instancia de `ollama serve` si ya está activo. La descarga solo se necesita la primera vez o para actualizar el modelo. Consulta la [referencia oficial de comandos de Ollama](https://docs.ollama.com/cli).

## Levantar la aplicación completa

Deben estar activos **Ollama, la API y el cliente**. Ejecutar solamente `npm run dev` abre la interfaz, pero no permite obtener respuestas del asistente.

### Terminal 1: Ollama

Si ya funciona como servicio o aplicación, mantenlo activo. En caso contrario:

```bash
ollama serve
```

Comprueba su conexión desde otra terminal:

```bash
curl http://127.0.0.1:11434/api/tags
```

Debe responder con una lista que incluya `gpt-oss:20b`. En PowerShell de Windows puedes usar `curl.exe` en lugar de `curl` para estos ejemplos.

### Terminal 2: API FastAPI

Desde la raíz del proyecto:

```bash
uv run uvicorn api:app --host 127.0.0.1 --port 8000
```

Espera `Application startup complete` y deja la terminal abierta.

- Estado: <http://127.0.0.1:8000/health>
- Documentación interactiva: <http://127.0.0.1:8000/docs>

Comprueba la API:

```bash
curl http://127.0.0.1:8000/health
```

Respuesta esperada:

```json
{"estado":"ok"}
```

Este endpoint solo verifica FastAPI; **no comprueba Ollama ni carga el modelo**.

### Terminal 3: cliente React

Desde la raíz del proyecto:

```bash
cd cliente
npm run dev
```

Abre **<http://127.0.0.1:5173/>** y deja la terminal abierta mientras uses la aplicación.

### Comprobar la conexión completa

Envía «Quiero hacer una rectificación.» en la interfaz. También puedes verificar cliente → API → Ollama desde Bash o Zsh:

```bash
curl http://127.0.0.1:5173/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"mensaje":"Quiero hacer una rectificación."}'
```

La primera consulta puede tardar más mientras se carga el modelo. Una respuesta correcta incluye `conversacion_id` y `respuesta`.

### Detener y volver a iniciar

Pulsa `Ctrl+C` en las terminales del cliente y de FastAPI. Si ejecutaste Ollama manualmente con `ollama serve`, puedes detenerlo con `Ctrl+C` en su terminal.

En la siguiente sesión, inicia nuevamente los tres servicios. No hace falta repetir las instalaciones ni descargar el modelo si ya está disponible.

## Usar el chat

1. Escribe una pregunta o pulsa una sugerencia inicial.
2. Pulsa **Enter** o el botón de enviar. **Shift + Enter** agrega una línea.
3. Espera mientras aparece «El asistente está pensando…».
4. Continúa la conversación para precisar tu consulta.
5. Pulsa **Nueva conversación** para empezar otro chat.

Ejemplos:

- «Quiero hacer una rectificación.»
- «Quiero cambiarme de sección.»
- «¿Qué requisitos necesito para rectificar?»
- «¿Cómo hago el trámite?»

El cliente conserva el identificador para los siguientes mensajes. Al recargar la página comienza otro chat. Si una solicitud falla, recupera el texto para que puedas reenviarlo.

El selector **Modelo**, debajo de la cabecera, permite alternar entre **gpt-oss · 20B** y **Qwen3 · 4B · Q4_K_M**. Cambiar de modelo inicia una conversación nueva. El selector se bloquea mientras se obtiene una respuesta. El modelo predeterminado es `gpt-oss:20b`.

La interfaz presenta solo el chat, el selector de modelo y las métricas por respuesta. Los controles de razonamiento, parámetros y evaluación están ocultos. La API aplica los valores predeterminados: razonamiento medio para GPT-OSS y **activado para Qwen3**. La configuración sigue registrándose con cada respuesta y puede ajustarse por API o CLI.

Debajo de cada respuesta, **Rendimiento** muestra el tiempo de respuesta, la velocidad en tokens por segundo y los tokens generados. Pulsa esa fila para ver el modelo utilizado en ese turno, los tokens de entrada y los tiempos de carga, procesamiento de entrada y generación. El primer mensaje tras cambiar de modelo puede tardar más por la carga en memoria.

Las duraciones de Ollama se convierten de nanosegundos a milisegundos. La velocidad se calcula como `eval_count / (eval_duration / 1 000 000 000)`. El tiempo de la API incluye la espera en cola y la consulta a Ollama, pero no la red del navegador. Los tokens de entrada incluyen instrucciones, catálogo e historial; los tokens generados son los que reporta Ollama y pueden incluir razonamiento interno. Los campos que Ollama omita aparecen como «No disponible». Estas métricas describen la ejecución, no la precisión de las respuestas.

## Consumir la API

### Endpoints

| Método | Ruta | Función |
| --- | --- | --- |
| GET | `/health` | Comprobar que FastAPI responde |
| GET | `/modelo` | Consultar modelos y sus opciones de razonamiento sin cargarlos |
| GET | `/experimento` | Consultar entorno, hardware, parámetros y copia del catálogo/sistema con sus huellas |
| GET | `/evaluacion` | Consultar preguntas, criterios y referencias del mismo catálogo para revisión humana |
| POST | `/chat` | Iniciar o continuar una conversación |
| GET | `/docs` | Probar la API desde Swagger UI |
| GET | `/openapi.json` | Consultar el esquema de la API |

### Iniciar una conversación

```bash
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"mensaje":"Quiero hacer una rectificación."}'
```

Ejemplo de respuesta; el identificador y el texto generado pueden variar:

```json
{
  "conversacion_id": "7646a444-00df-455a-a9e9-3efb0683cb34",
  "respuesta": "¿Qué necesitas cambiar en tu matrícula?",
  "modelo": "gpt-oss:20b",
  "metricas": {
    "tiempo_respuesta_ms": 3500.0,
    "tiempo_modelo_ms": 3000.0,
    "carga_modelo_ms": 200.0,
    "procesamiento_prompt_ms": 800.0,
    "generacion_ms": 2000.0,
    "tokens_entrada": 1200,
    "tokens_salida": 80,
    "tokens_por_segundo": 40.0
  }
}
```

### Continuar la conversación

Sustituye el UUID del ejemplo por el `conversacion_id` que recibiste realmente:

```bash
curl http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"mensaje":"Quiero cambiarme de sección.","conversacion_id":"7646a444-00df-455a-a9e9-3efb0683cb34"}'
```

Omite `conversacion_id` para empezar un chat independiente. El mensaje debe ser texto y no puede estar vacío.

Para elegir Qwen3, envía `"modelo": "qwen3:4b-q4_K_M"` en el cuerpo de `/chat`. Puedes añadir `"razonamiento": "activado"` o `"desactivado"` y `"parametros": {"temperature": 0.2, "seed": 42, "num_ctx": 8192, "num_predict": 1024}`. GPT-OSS acepta `low`, `medium` o `high`. La respuesta registra la configuración, fecha, identificador de evidencia, métricas, duraciones originales, recursos y huellas.

Si omites configuración al iniciar, se usan los valores predeterminados; si la omites al continuar, se conserva la de la conversación. Solo se aceptan los dos modelos y razonamientos configurados. Cambiar la configuración de un mismo `conversacion_id` devuelve 409: empieza sin identificador para cambiarla.

Los ejemplos multilínea usan Bash o Zsh. En Windows también puedes probar el JSON directamente en `/docs`, Postman o Insomnia. `solicitudes.http` incluye peticiones para la extensión REST Client de VS Code.

### Errores HTTP

| Código | Significado | Acción |
| --- | --- | --- |
| 422 | Mensaje, UUID o modelo inválido | Revisar el JSON y los modelos permitidos |
| 404 | Conversación inexistente | Empezar sin `conversacion_id` |
| 409 | Cambio de modelo dentro de una conversación | Empezar sin `conversacion_id` |
| 503 | No se puede conectar con Ollama | Comprobar el puerto 11434 |
| 504 | Tiempo de espera agotado | Revisar recursos del equipo y reintentar |
| 502 | Ollama rechazó la consulta | Revisar el servicio, el modelo y los registros de la API |

Los turnos fallidos no se incorporan al historial de la API.

## Ejecutar por consola

Con Ollama activo y el modelo instalado, desde la raíz:

```bash
uv run python main.py
```

Escribe tus preguntas después de `Estudiante:`. Usa `/salir` para terminar. Este modo no necesita FastAPI ni React. En HTTP, `/salir` no es un comando especial.

## Pruebas y compilación

### Pruebas de la API

```bash
uv run python -m unittest -v test_api.py
```

Las pruebas simulan Ollama y verifican el historial, la separación de conversaciones, la selección y conservación de configuración, el mensaje de sistema idéntico, los errores, los endpoints, la consola y las métricas. Para incluir los sensores ausentes y la exportación CSV:

```bash
uv run python -m unittest -v test_api.py test_telemetria.py test_evidencia.py
```

No requieren cargar los modelos ni iniciar servicios.

Para comprobar los cálculos de comparación y la exportación del frontend, sin dependencias adicionales:

```bash
cd cliente
npm test
```

## Evaluación y exportación de evidencia

El panel de evaluación no se muestra en la interfaz simplificada. El banco y la exportación siguen disponibles por CLI contra la misma API. Cada caso empieza una conversación independiente; los turnos de contexto comparten su identificador. Los lotes son secuenciales. Desde la raíz:

```bash
uv run python evaluar.py --salida resultados/evaluacion.json
```

Se guardan JSON y CSV tras cada respuesta. Revisa las respuestas contra los criterios y fragmentos del catálogo y completa manualmente los puntajes, el revisor y la justificación en el JSON. Ejemplo con repeticiones y razonamiento explícito:

```bash
uv run python evaluar.py --repeticiones 3 --razonamiento-gpt low --razonamiento-qwen desactivado --salida resultados/comparacion.json
```

Usa `uv run python evaluar.py --help` para seleccionar casos, modelos, semilla, contexto, temperatura y límite de generación. Ninguna ejecución califica automáticamente la precisión ni prueba concurrencia.

### Compilar el cliente

```bash
cd cliente
npm run build
npm run preview
```

La compilación genera `cliente/dist`. La vista previa se abre en <http://127.0.0.1:4173/> y también necesita FastAPI y Ollama activos. `preview` permite revisar la compilación localmente.

Si sirves `dist` desde otro servidor, configura el reenvío de `/api/*` hacia FastAPI eliminando el prefijo `/api`, como hace `vite.config.js`. Publicar solo los archivos estáticos no inicia FastAPI ni Ollama.

## Solución de problemas

### La interfaz abre, pero no responde o muestra un error sobre Ollama

Comprueba cada servicio por separado:

```bash
curl http://127.0.0.1:11434/api/tags
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:5173/
```

- Si falla el primero, abre Ollama o ejecuta `ollama serve`.
- Si Ollama responde y falla el segundo, inicia la API desde la raíz con `uv run uvicorn api:app --host 127.0.0.1 --port 8000`. **Ollama activo no implica que FastAPI esté activo.**
- Si falla el tercero, ejecuta `npm run dev` dentro de `cliente`.
- Si los tres responden, revisa que `ollama list` incluya `gpt-oss:20b` y prueba una consulta completa. Los endpoints de estado no verifican la generación.

Después de corregir la causa, recarga el cliente y reenvía la pregunta. Revisa los registros de las terminales de FastAPI y Vite si persiste.

### El modelo no aparece o se muestra «model not found»

```bash
ollama pull gpt-oss:20b
ollama list
```

### El puerto está ocupado

Puede haber otra instancia activa. Comprueba su URL y reutilízala, o detén el proceso anterior desde su terminal. Vite usa puertos estrictos y no cambia automáticamente de `5173` o `4173`. Si cambias el puerto de FastAPI, actualiza también `proxy.target` en `cliente/vite.config.js`.

### La primera respuesta demora

Ollama debe cargar el modelo en memoria. Espera la respuesta y revisa la memoria disponible y los registros si falla. `ollama ps` muestra los modelos cargados; una lista vacía antes de la primera consulta no significa que el servicio esté apagado.

### Error de versión de Python o Node.js

Instala Python con `uv python install 3.14` y ejecuta `uv sync --locked --python 3.14`. Comprueba `node --version` y usa una versión compatible con los requisitos iniciales; después ejecuta `npm ci` dentro de `cliente`.

### Conversación no encontrada después de reiniciar FastAPI

Los historiales viven en memoria. Pulsa **Nueva conversación** o envía una petición sin `conversacion_id`.

## Configuración y límites

- **Modelos y dirección de Ollama:** definidos en `main.py`. `MODELO` establece el predeterminado y `MODELOS` las opciones del selector. Python apunta explícitamente a `http://127.0.0.1:11434`; el proyecto no lee un archivo `.env` para cambiarlo. La consola usa el modelo predeterminado.
- **Puertos y proxy:** definidos en `cliente/vite.config.js`. La configuración actual utiliza la misma máquina para los tres servicios.
- **Catálogo:** `tramites_fisi.json` se carga al iniciar Python. Reinicia la API tras modificarlo. Se envía completo al asistente; no hay búsqueda web ni base vectorial.
- **Alcance de los datos:** las respuestas dependen del catálogo incluido. Revisa sus datos y fuentes antes de usarlo para otro período académico.
- **Historial:** se guarda en memoria, separado por UUID, y se pierde al reiniciar FastAPI. Ejecuta un solo proceso de Uvicorn, sin `--workers`, para mantener un único conjunto de conversaciones.
- **Procesamiento:** las consultas HTTP se atienden en orden mediante un bloqueo. La respuesta llega completa; no hay transmisión progresiva de tokens.
- **Uso local:** no se incluye autenticación ni almacenamiento persistente. Los servidores se enlazan a `127.0.0.1`.
- **Archivos publicados:** se incluyen los archivos de bloqueo. `.venv`, `node_modules`, `dist`, cachés y configuración local se excluyen mediante `.gitignore`.
