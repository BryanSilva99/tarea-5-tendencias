from pathlib import Path

from ollama import Client

catalogo = Path(__file__).with_name("tramites_fisi.json").read_text(
    encoding="utf-8"
)

cliente = Client(host="http://127.0.0.1:11434")

mensajes = [
    {
        "role": "system",
        "content": (
            "Eres un asistente de trámites de matrícula de la FISI. "
            "Responde en español. Usa el historial para entender qué quiere el alumno "
            "y el catálogo como única fuente de datos sobre los trámites.\n\n"

            "Aplica estas reglas en orden:\n"
            "1. Si el alumno solo dice que quiere hacer un trámite, haz una sola "
            "pregunta para saber qué necesita resolver. Aunque reconozcas el trámite, "
            "en ese turno responde únicamente con la pregunta, sin mostrar la ficha.\n"
            "2. Si el alumno responde a una pregunta de aclaración, contesta solo "
            "sobre el caso que acaba de precisar. Si está en casos_especificos, "
            "usa ese campo primero. Menciona pasos, requisitos, canal o plazo "
            "solo si el alumno los pide.\n"
            "3. Si el alumno pregunta si puede hacer un cambio, responde si puede "
            "solicitarlo y menciona solo la condición aplicable. Si pregunta por "
            "el plazo, el canal o los requisitos, responde solo sobre ese dato. "
            "Enumera pasos únicamente si pide cómo hacer el trámite.\n"
            "4. Empieza con la respuesta directa a la pregunta del alumno. "
            "Si el dato solicitado falta, vale null o figura como pendiente de confirmar, "
            "di en una frase qué dato no puedes confirmar. "
            "No sustituyas ese dato por el de otro semestre o por el cronograma general.\n"
            "5. Si incluyes un enlace, copia una URL exacta de las fuentes de la "
            "ficha. Si el alumno pide un enlace directo que el catálogo no contiene, "
            "dile que no tienes ese enlace.\n\n"
            "Conserva la redacción de los plazos cuando parafrasearlos cambie su sentido. "
            "Describe las condiciones y la autorización requerida sin prometer la aprobación.\n"

            "Ejemplo de primer turno:\n"
            "Alumno: Quiero hacer una rectificación.\n"
            "Asistente: ¿Qué necesitas cambiar en tu matrícula?\n\n"

            f"Catálogo completo:\n{catalogo}"
        ),
    }
]


def responder(pregunta, historial):
    historial.append({"role": "user", "content": pregunta})
    respuesta = cliente.chat(
        model="gpt-oss:20b",
        messages=historial,
        stream=False,
    )
    texto = respuesta.message.content  # pylint: disable=no-member
    historial.append({"role": "assistant", "content": texto})
    return texto


def main():
    print("Asistente FISI. Escribe /salir para terminar.")

    while True:
        pregunta = input("\nEstudiante: ").strip()

        if pregunta.lower() == "/salir":
            break

        if not pregunta:
            continue

        texto = responder(pregunta, mensajes)
        print(f"\nAsistente: {texto}")


if __name__ == "__main__":
    main()
