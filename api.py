"""Capa HTTP del asistente; reutiliza el flujo original de main.py."""

from copy import deepcopy
from threading import Lock
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from httpx import TimeoutException
from ollama import ResponseError
from pydantic import BaseModel, Field, field_validator

from main import mensajes, responder

app = FastAPI(title="Asistente FISI", version="0.1.0")
conversaciones = {}
bloqueo = Lock()


class Consulta(BaseModel):
    mensaje: str = Field(min_length=1, examples=["Quiero hacer una rectificación."])
    conversacion_id: UUID | None = None

    @field_validator("mensaje")
    @classmethod
    def validar_mensaje(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("El mensaje no puede estar vacío.")
        return valor


class Respuesta(BaseModel):
    conversacion_id: UUID
    respuesta: str


@app.get("/health")
def health():
    """Comprueba que la API está activa; no consulta el modelo."""
    return {"estado": "ok"}


@app.post("/chat", response_model=Respuesta)
def chat(consulta: Consulta):
    """Omite conversacion_id para empezar o reutilízalo para continuar."""
    with bloqueo:
        conversacion_id = consulta.conversacion_id or uuid4()
        if consulta.conversacion_id is not None and conversacion_id not in conversaciones:
            raise HTTPException(status_code=404, detail="Conversación no encontrada.")

        # Guarda el turno solo cuando Ollama haya respondido correctamente.
        historial = deepcopy(conversaciones.get(conversacion_id, mensajes))
        try:
            texto = responder(consulta.mensaje, historial)
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
                detail="Ollama no pudo procesar la consulta. Revisa el servicio y el modelo gpt-oss:20b.",
            ) from exc

        conversaciones[conversacion_id] = historial
        return Respuesta(conversacion_id=conversacion_id, respuesta=texto)
