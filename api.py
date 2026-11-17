"""Capa HTTP del asistente; reutiliza el flujo original de main.py."""

from copy import deepcopy
from datetime import datetime, timezone
import os
import platform
from threading import Lock
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from httpx import TimeoutException
from ollama import ResponseError
from pydantic import BaseModel, Field, field_validator

from main import (MODELO, MODELOS, CATALOGO_SHA256, SISTEMA_SHA256,
                  catalogo, generar_respuesta, mensajes)
from experimento import (ENTORNO, Parametros, RAZONAMIENTO_PREDETERMINADO,
                         opciones_modelos, valor_razonamiento)
from telemetria import MuestreoRecursos, equipo_actual, modelo_en_memoria, version_ollama
from evaluacion import banco_preguntas

app = FastAPI(title="Asistente FISI", version="0.1.0")
conversaciones = {}
bloqueo = Lock()


class Consulta(BaseModel):
    mensaje: str = Field(min_length=1, examples=[
                         "Quiero hacer una rectificación."])
    conversacion_id: UUID | None = None
    modelo: str | None = None
    razonamiento: str | None = None
    parametros: Parametros | None = None

    @field_validator("modelo")
    @classmethod
    def validar_modelo(cls, valor):
        if valor is not None and valor not in MODELOS:
            raise ValueError("Modelo no permitido. Consulta /modelo para ver las opciones.")
        return valor

    @field_validator("mensaje")
    @classmethod
    def validar_mensaje(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El mensaje no puede estar vacío.")
        return valor


class Metricas(BaseModel):
    tiempo_respuesta_ms: float = Field(ge=0)
    tiempo_modelo_ms: float | None = Field(default=None, ge=0)
    carga_modelo_ms: float | None = Field(default=None, ge=0)
    procesamiento_prompt_ms: float | None = Field(default=None, ge=0)
    generacion_ms: float | None = Field(default=None, ge=0)
    tokens_entrada: int | None = Field(default=None, ge=0)
    tokens_salida: int | None = Field(default=None, ge=0)
    tokens_por_segundo: float | None = Field(default=None, ge=0)


class Respuesta(BaseModel):
    registro_id: UUID
    fecha: datetime
    conversacion_id: UUID
    respuesta: str
    modelo: str
    metricas: Metricas
    razonamiento: str
    parametros: Parametros
    catalogo_sha256: str
    sistema_sha256: str
    entorno: str
    equipo: dict
    recursos: dict
    ollama: dict


def metricas_respuesta(respuesta, inicio):
    """Ollama informa duraciones en nanosegundos; no estima datos ausentes."""
    def milisegundos(campo):
        valor = getattr(respuesta, campo, None)
        return valor / 1_000_000 if valor is not None else None

    tokens = getattr(respuesta, "eval_count", None)
    duracion = getattr(respuesta, "eval_duration", None)
    return Metricas(
        tiempo_respuesta_ms=(perf_counter() - inicio) * 1000,
        tiempo_modelo_ms=milisegundos("total_duration"),
        carga_modelo_ms=milisegundos("load_duration"),
        procesamiento_prompt_ms=milisegundos("prompt_eval_duration"),
        generacion_ms=milisegundos("eval_duration"),
        tokens_entrada=getattr(respuesta, "prompt_eval_count", None),
        tokens_salida=tokens,
        tokens_por_segundo=(tokens * 1_000_000_000 / duracion
                            if tokens is not None and duracion and duracion > 0 else None),
    )


@app.get("/health")
def health():
    """Comprueba que la API está activa; no consulta el modelo."""
    return {"estado": "ok"}


@app.post("/chat", response_model=Respuesta)
def chat(consulta: Consulta):
    """Omite conversacion_id para empezar o reutilízalo para continuar."""
    inicio = perf_counter()
    with bloqueo:
        conversacion_id = consulta.conversacion_id or uuid4()
        if consulta.conversacion_id is not None and conversacion_id not in conversaciones:
            raise HTTPException(
                status_code=404, detail="Conversación no encontrada.")

        conversacion = conversaciones.get(conversacion_id)
        modelo_elegido = consulta.modelo or (conversacion["modelo"] if conversacion else MODELO)
        if conversacion and modelo_elegido != conversacion["modelo"]:
            raise HTTPException(
                status_code=409,
                detail="Para cambiar de modelo, inicia una nueva conversación.",
            )

        razonamiento = consulta.razonamiento if consulta.razonamiento is not None else (
            conversacion["razonamiento"] if conversacion else RAZONAMIENTO_PREDETERMINADO[modelo_elegido])
        try:
            valor_razonamiento(modelo_elegido, razonamiento)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        parametros = consulta.parametros or (conversacion["parametros"] if conversacion else Parametros())
        if conversacion and (razonamiento != conversacion["razonamiento"]
                             or parametros != conversacion["parametros"]):
            raise HTTPException(status_code=409, detail="Inicia una nueva conversación para cambiar la configuración.")

        # Guarda el turno solo cuando Ollama haya respondido correctamente.
        historial = deepcopy(conversacion["mensajes"] if conversacion else mensajes)
        residente_antes = modelo_en_memoria(modelo_elegido)
        try:
            with MuestreoRecursos() as recursos:
                respuesta = generar_respuesta(consulta.mensaje, historial, modelo_elegido,
                                              razonamiento, parametros)
        except ConnectionError as exc:
            raise HTTPException(
                status_code=503, detail="No se pudo conectar con Ollama."
            ) from exc
        except TimeoutException as exc:
            raise HTTPException(
                status_code=504, detail="Ollama tardó demasiado en responder."
            ) from exc
        except ResponseError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Ollama no pudo procesar la consulta. Revisa el servicio y el modelo {modelo_elegido}.",
            ) from exc

        residente_despues = modelo_en_memoria(modelo_elegido)
        version = version_ollama()
        metricas = metricas_respuesta(respuesta, inicio)
        conversaciones[conversacion_id] = {
            "mensajes": historial, "modelo": modelo_elegido,
            "razonamiento": razonamiento, "parametros": parametros,
        }
        primera_muestra = recursos.muestras[0] if recursos.muestras else {}
        return Respuesta(
            registro_id=uuid4(), fecha=datetime.now(timezone.utc),
            conversacion_id=conversacion_id,
            respuesta=respuesta.message.content,
            modelo=getattr(respuesta, "model", None) or modelo_elegido,
            metricas=metricas,
            razonamiento=razonamiento, parametros=parametros,
            catalogo_sha256=CATALOGO_SHA256, sistema_sha256=SISTEMA_SHA256,
            entorno=ENTORNO,
            equipo={"sistema": platform.platform(),
                    "hilos_cpu": os.cpu_count(),
                    "ram": primera_muestra.get('ram'), "gpu": primera_muestra.get('gpu')},
            recursos=recursos.resultado(),
            ollama={
                "version": version,
                "duraciones_ns": {campo: getattr(respuesta, campo, None) for campo in
                                  ('total_duration', 'load_duration', 'prompt_eval_duration', 'eval_duration')},
                "done_reason": getattr(respuesta, 'done_reason', None),
                "razonamiento_emitido": bool(getattr(respuesta.message, 'thinking', None)),
                "modelo_antes": residente_antes,
                "modelo_despues": residente_despues,
            },
        )


@app.get("/modelo")
def modelo():
    """Informa el modelo predeterminado y las opciones permitidas sin cargarlos."""
    return {
        "modelo": MODELO,
        "modelos": opciones_modelos(),
    }


@app.get("/experimento")
def experimento():
    return {"entorno": ENTORNO, "equipo": equipo_actual(),
            "ollama_version": version_ollama(),
            "catalogo_sha256": CATALOGO_SHA256, "sistema_sha256": SISTEMA_SHA256,
            "catalogo_texto": catalogo, "mensaje_sistema": mensajes[0],
            "parametros": Parametros().model_dump(), "concurrencia_probada": False,
            "servidor_institucional_probado": False}


@app.get("/evaluacion")
def evaluacion():
    """Referencias resueltas desde el mismo catálogo; no se pasan al LLM."""
    return banco_preguntas()
