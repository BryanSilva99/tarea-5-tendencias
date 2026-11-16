"""Verifica el contrato HTTP sin ejecutar el modelo de Ollama."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from httpx import ReadTimeout
from ollama import ResponseError

import api
import main


class ApiTests(unittest.TestCase):
    def setUp(self):
        api.conversaciones.clear()
        self.client = TestClient(api.app)
        self.llamadas = []
        self.mock_chat = patch.object(main.cliente, "chat", side_effect=self.responder)
        self.mock_chat.start()
        self.addCleanup(self.mock_chat.stop)
        self.addCleanup(self.client.close)

    def responder(self, **kwargs):
        self.llamadas.append(deepcopy(kwargs))
        return SimpleNamespace(message=SimpleNamespace(content="Respuesta del asistente"))

    def test_conserva_prompt_modelo_e_historial(self):
        primera = self.client.post("/chat", json={"mensaje": "  Quiero rectificar.  "})
        self.assertEqual(primera.status_code, 200)
        datos = primera.json()
        self.assertEqual(datos["respuesta"], "Respuesta del asistente")
        self.assertEqual(self.llamadas[0], {
            "model": "gpt-oss:20b",
            "messages": main.mensajes + [{"role": "user", "content": "Quiero rectificar."}],
            "stream": False,
        })

        segunda = self.client.post("/chat", json={
            "mensaje": "Cambiar de sección.",
            "conversacion_id": datos["conversacion_id"],
        })
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()["conversacion_id"], datos["conversacion_id"])
        self.assertEqual(self.llamadas[1]["messages"], main.mensajes + [
            {"role": "user", "content": "Quiero rectificar."},
            {"role": "assistant", "content": "Respuesta del asistente"},
            {"role": "user", "content": "Cambiar de sección."},
        ])

    def test_separa_conversaciones(self):
        primera = self.client.post("/chat", json={"mensaje": "Primera consulta"}).json()
        segunda = self.client.post("/chat", json={"mensaje": "Otra consulta"}).json()
        self.assertNotEqual(primera["conversacion_id"], segunda["conversacion_id"])
        self.assertEqual(len(self.llamadas[1]["messages"]), 2)
        self.assertEqual(len(main.mensajes), 1)

    def test_rechaza_peticion_invalida_sin_llamar_al_modelo(self):
        for cuerpo in ({}, {"mensaje": ""}, {"mensaje": "  "}, {"mensaje": 123},
                       {"mensaje": "Hola", "conversacion_id": "invalido"}):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(self.client.post("/chat", json=cuerpo).status_code, 422)
        self.assertEqual(self.llamadas, [])

    def test_conversacion_inexistente(self):
        respuesta = self.client.post("/chat", json={
            "mensaje": "Hola",
            "conversacion_id": "7646a444-00df-455a-a9e9-3efb0683cb34",
        })
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self.llamadas, [])

    def test_fallo_de_ollama_no_contamina_el_historial(self):
        datos = self.client.post("/chat", json={"mensaje": "Hola"}).json()
        cuerpo = {"mensaje": "Consulta fallida", "conversacion_id": datos["conversacion_id"]}
        for error, estado in (
            (ConnectionError("Ollama desconectado"), 503),
            (ReadTimeout("Tiempo agotado"), 504),
            (ResponseError("Modelo no encontrado", status_code=404), 502),
        ):
            with self.subTest(estado=estado), patch.object(main.cliente, "chat", side_effect=error):
                respuesta = self.client.post("/chat", json=cuerpo)
                self.assertEqual(respuesta.status_code, estado)

        self.client.post("/chat", json={
            "mensaje": "Reintento", "conversacion_id": datos["conversacion_id"],
        })
        self.assertEqual(len(self.llamadas[-1]["messages"]), 4)
        self.assertNotIn("Consulta fallida", str(self.llamadas[-1]))

    def test_health_y_documentacion_no_llaman_al_modelo(self):
        self.assertEqual(self.client.get("/health").json(), {"estado": "ok"})
        self.assertEqual(self.client.get("/docs").status_code, 200)
        esquema = self.client.get("/openapi.json").json()
        self.assertIn("/chat", esquema["paths"])
        self.assertEqual(self.llamadas, [])


if __name__ == "__main__":
    unittest.main()
