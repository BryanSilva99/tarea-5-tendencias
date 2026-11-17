"""Configuración compartida del chat y de las pruebas de un solo usuario."""

from pydantic import BaseModel, Field

MODELO = "gpt-oss:20b"
MODELO_QWEN = "qwen3:4b-q4_K_M"
MODELOS = {MODELO: "gpt-oss · 20B", MODELO_QWEN: "Qwen3 · 4B · Q4_K_M"}
RAZONAMIENTOS = {
    MODELO: {"low": "Bajo", "medium": "Medio", "high": "Alto"},
    MODELO_QWEN: {"desactivado": "Desactivado", "activado": "Activado"},
}
RAZONAMIENTO_PREDETERMINADO = {MODELO: "medium", MODELO_QWEN: "activado"}
ENTORNO = "Equipo personal; ejecución local. Servidor institucional sin GPU pendiente de validar."


class Parametros(BaseModel):
    """Se envían explícitamente a los dos modelos y se guardan en la evidencia."""

    temperature: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)
    seed: int = Field(default=42, ge=0, le=2**31 - 1, strict=True)
    num_ctx: int = Field(default=8192, ge=4096, le=32768, strict=True)
    num_predict: int = Field(default=1024, ge=128, le=4096, strict=True)


def valor_razonamiento(modelo, modo=None):
    modo = RAZONAMIENTO_PREDETERMINADO[modelo] if modo is None else modo
    if modo not in RAZONAMIENTOS[modelo]:
        raise ValueError("Modo de razonamiento incompatible con el modelo.")
    return {"activado": True, "desactivado": False}.get(modo, modo)


def opciones_modelos():
    return [{
        "id": clave, "nombre": nombre,
        "razonamiento_predeterminado": RAZONAMIENTO_PREDETERMINADO[clave],
        "razonamientos": [{"id": modo, "nombre": etiqueta}
                          for modo, etiqueta in RAZONAMIENTOS[clave].items()],
    } for clave, nombre in MODELOS.items()]
