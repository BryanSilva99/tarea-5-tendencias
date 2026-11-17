"""Verifica el contrato HTTP sin ejecutar el modelo de Ollama."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from httpx import ReadTimeout
from ollama import ResponseError
from ollama import ChatResponse

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
        self.mock_recursos = patch.object(api, 'MuestreoRecursos')
        self.mock_memoria = patch.object(api, 'modelo_en_memoria', return_value=None)
        muestreo = self.mock_recursos.start().return_value.__enter__.return_value
        muestreo.muestras = []
        muestreo.resultado.return_value = {'muestras': [], 'cantidad_muestras': 0}
        self.mock_memoria.start()
        self.addCleanup(self.mock_recursos.stop)
        self.addCleanup(self.mock_memoria.stop)
        version = patch.object(api, 'version_ollama', return_value='simulado')
        version.start()
        self.addCleanup(version.stop)

    def responder(self, **kwargs):
        self.llamadas.append(deepcopy(kwargs))
        return ChatResponse(
            model=kwargs["model"],
            message={"role": "assistant", "content": "Respuesta del asistente"},
            total_duration=3_000_000_000,
            load_duration=200_000_000,
            prompt_eval_duration=800_000_000,
            eval_duration=2_000_000_000,
            prompt_eval_count=1200,
            eval_count=80,
        )

    def test_metricas_de_ollama_y_modelo_utilizado(self):
        with patch.object(api, "perf_counter", side_effect=[10.0, 13.5]):
            datos = self.client.post("/chat", json={"mensaje": "Hola"}).json()
        self.assertEqual(datos["modelo"], "gpt-oss:20b")
        self.assertEqual(datos["metricas"], {
            "tiempo_respuesta_ms": 3500.0,
            "tiempo_modelo_ms": 3000.0,
            "carga_modelo_ms": 200.0,
            "procesamiento_prompt_ms": 800.0,
            "generacion_ms": 2000.0,
            "tokens_entrada": 1200,
            "tokens_salida": 80,
            "tokens_por_segundo": 40.0,
        })

    def test_metricas_ausentes_y_duracion_cero(self):
        for campos in ({}, {"eval_count": 80, "eval_duration": 0},
                       {"eval_count": 0, "eval_duration": 1_000_000_000}):
            with self.subTest(campos=campos):
                respuesta = ChatResponse(
                    model="modelo-real:latest",
                    message={"role": "assistant", "content": "Hola"},
                    **campos,
                )
                with patch.object(main.cliente, "chat", return_value=respuesta):
                    resultado = self.client.post("/chat", json={"mensaje": "Hola"})
                self.assertEqual(resultado.status_code, 200)
                datos = resultado.json()
                self.assertEqual(datos["modelo"], "modelo-real:latest")
                self.assertGreaterEqual(datos["metricas"]["tiempo_respuesta_ms"], 0)
                self.assertIsNone(datos["metricas"]["tokens_entrada"])
                self.assertEqual(datos["metricas"]["tokens_por_segundo"],
                                 0.0 if campos.get("eval_duration") else None)

    def test_consola_conserva_respuesta_de_texto(self):
        historial = deepcopy(main.mensajes)
        self.assertEqual(main.responder("Hola", historial), "Respuesta del asistente")
        self.assertEqual(historial[-1]["role"], "assistant")

    def test_conserva_prompt_modelo_e_historial(self):
        primera = self.client.post("/chat", json={"mensaje": "  Quiero rectificar.  "})
        self.assertEqual(primera.status_code, 200)
        datos = primera.json()
        self.assertEqual(datos["respuesta"], "Respuesta del asistente")
        self.assertEqual(self.llamadas[0], {
            "model": "gpt-oss:20b",
            "messages": main.mensajes + [{"role": "user", "content": "Quiero rectificar."}],
            "stream": False,
            "think": "medium",
            "options": api.Parametros().model_dump(),
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

    def test_selecciona_qwen_y_conserva_el_modelo_en_siguientes_turnos(self):
        primera = self.client.post("/chat", json={
            "mensaje": "Hola", "modelo": main.MODELO_QWEN,
        })
        self.assertEqual(primera.status_code, 200)
        datos = primera.json()
        self.assertEqual(datos["modelo"], main.MODELO_QWEN)
        self.assertEqual(self.llamadas[0]["model"], main.MODELO_QWEN)
        self.assertIs(self.llamadas[0]["think"], True)
        self.assertEqual(datos["razonamiento"], "activado")
        self.assertEqual(self.llamadas[0]["messages"][0], main.mensajes[0])
        self.assertEqual(datos["metricas"]["tokens_por_segundo"], 40.0)

        segunda = self.client.post("/chat", json={
            "mensaje": "Continúa", "conversacion_id": datos["conversacion_id"],
        })
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json()["modelo"], main.MODELO_QWEN)
        self.assertEqual(self.llamadas[1]["model"], main.MODELO_QWEN)
        self.assertEqual(len(self.llamadas[1]["messages"]), 4)

    def test_cambio_de_modelo_exige_una_conversacion_nueva(self):
        datos = self.client.post("/chat", json={"mensaje": "Hola"}).json()
        historial = deepcopy(api.conversaciones)
        respuesta = self.client.post("/chat", json={
            "mensaje": "Otra pregunta", "modelo": main.MODELO_QWEN,
            "conversacion_id": datos["conversacion_id"],
        })
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(len(self.llamadas), 1)
        self.assertEqual(api.conversaciones, historial)

        nueva = self.client.post("/chat", json={
            "mensaje": "Otra pregunta", "modelo": main.MODELO_QWEN,
        })
        self.assertEqual(nueva.status_code, 200)
        self.assertNotEqual(nueva.json()["conversacion_id"], datos["conversacion_id"])
        self.assertEqual(len(self.llamadas[1]["messages"]), 2)

    def test_fallo_de_qwen_no_guarda_conversacion_y_menciona_modelo_correcto(self):
        with patch.object(main.cliente, "chat", side_effect=ResponseError("No instalado", status_code=404)):
            respuesta = self.client.post("/chat", json={
                "mensaje": "Hola", "modelo": main.MODELO_QWEN,
            })
        self.assertEqual(respuesta.status_code, 502)
        self.assertIn(main.MODELO_QWEN, respuesta.json()["detail"])
        self.assertEqual(api.conversaciones, {})

    def test_rechaza_peticion_invalida_sin_llamar_al_modelo(self):
        for cuerpo in ({}, {"mensaje": ""}, {"mensaje": "  "}, {"mensaje": 123},
                       {"mensaje": "Hola", "modelo": "modelo-no-permitido"},
                       {"mensaje": "Hola", "modelo": ""},
                       {"mensaje": "Hola", "modelo": 123},
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
        self.assertEqual(self.client.get("/modelo").json(), {
            "modelo": main.MODELO,
            "modelos": api.opciones_modelos(),
        })
        self.assertEqual(self.client.get("/docs").status_code, 200)
        esquema = self.client.get("/openapi.json").json()
        self.assertIn("/chat", esquema["paths"])
        self.assertEqual(self.llamadas, [])

    def test_mismo_sistema_catalogo_y_parametros_para_ambos_modelos(self):
        from hashlib import sha256
        resultados = []
        for modelo in main.MODELOS:
            datos = self.client.post('/chat', json={'mensaje': '¿Qué documentos necesito?', 'modelo': modelo}).json()
            resultados.append(datos)
        self.assertEqual(self.llamadas[0]['messages'][0], self.llamadas[1]['messages'][0])
        self.assertEqual(self.llamadas[0]['options'], self.llamadas[1]['options'])
        self.assertEqual(resultados[0]['catalogo_sha256'], sha256(main.catalogo.encode()).hexdigest())
        self.assertEqual(resultados[0]['sistema_sha256'], resultados[1]['sistema_sha256'])
        self.assertEqual(resultados[0]['ollama']['duraciones_ns']['total_duration'], 3_000_000_000)

    def test_razonamiento_y_parametros_se_conservan_en_historial(self):
        datos = self.client.post('/chat', json={
            'mensaje': 'Hola', 'modelo': main.MODELO_QWEN, 'razonamiento': 'activado',
            'parametros': {'temperature': 0, 'seed': 7, 'num_ctx': 16384, 'num_predict': 2048},
        }).json()
        self.assertIs(self.llamadas[-1]['think'], True)
        self.assertEqual(datos['razonamiento'], 'activado')
        self.assertEqual(self.llamadas[-1]['options']['seed'], 7)
        siguiente = self.client.post('/chat', json={'mensaje': 'Continúa', 'conversacion_id': datos['conversacion_id']})
        self.assertEqual(siguiente.status_code, 200)
        self.assertIs(self.llamadas[-1]['think'], True)
        self.assertEqual(siguiente.json()['parametros'], datos['parametros'])
        for cambios in ({'razonamiento': 'desactivado'}, {'parametros': {'seed': 2}}):
            resultado = self.client.post('/chat', json={
                'mensaje': 'Otra', 'conversacion_id': datos['conversacion_id'], **cambios})
            self.assertEqual(resultado.status_code, 409)
        self.assertEqual(len(self.llamadas), 2)

    def test_rechaza_razonamiento_incompatible_y_parametros_invalidos(self):
        for cambios in ({'razonamiento': 'desactivado'}, {'razonamiento': ''},
                        {'razonamiento': 'inexistente'}, {'parametros': {'temperature': 3}},
                        {'parametros': {'num_ctx': 100}}, {'parametros': {'seed': 1.5}},
                        {'parametros': {'num_predict': -1}}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.client.post('/chat', json={'mensaje': 'Hola', **cambios}).status_code, 422)
        self.assertEqual(self.llamadas, [])

    def test_banco_de_evaluacion_usa_el_catalogo_y_no_inyecta_respuestas(self):
        import json
        banco = self.client.get('/evaluacion').json()
        self.assertEqual(banco['catalogo_sha256'], main.CATALOGO_SHA256)
        self.assertEqual(len(banco['casos']), 10)
        costo = next(c for c in banco['casos'] if c['id'] == 'costo')
        fuente = json.loads(main.catalogo)['tramites'][2]['casos_especificos']['costo_reserva']
        self.assertEqual(costo['referencias']['casos_especificos.costo_reserva'], fuente)
        self.assertEqual(self.llamadas, [])

    def test_experimento_no_afirma_validacion_institucional_ni_concurrencia(self):
        with patch.object(api, 'equipo_actual', return_value={'gpu': None}):
            datos = self.client.get('/experimento').json()
        self.assertIs(datos['concurrencia_probada'], False)
        self.assertIs(datos['servidor_institucional_probado'], False)
        self.assertEqual(datos['mensaje_sistema'], main.mensajes[0])
        self.assertEqual(datos['catalogo_texto'], main.catalogo)

    def test_referencias_ausentes_se_distinguen_de_un_null_explicito(self):
        import json
        import evaluacion
        catalogo = json.loads(main.catalogo)
        del catalogo['tramites'][2]['casos_especificos']['costo_reserva']
        with patch.object(evaluacion, 'catalogo', json.dumps(catalogo)):
            banco = self.client.get('/evaluacion').json()
        self.assertTrue(next(c for c in banco['casos'] if c['id'] == 'costo')['revisar_referencias'])
        self.assertFalse(next(c for c in banco['casos'] if c['id'] == 'canal_desconocido')['revisar_referencias'])


if __name__ == "__main__":
    unittest.main()
