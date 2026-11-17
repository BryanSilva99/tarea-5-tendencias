import csv
import io
import unittest

from evidencia import generar_csv


class EvidenciaTests(unittest.TestCase):
    def test_csv_preserva_textos_multilinea_y_ausencias_y_neutraliza_formulas(self):
        csv_texto = generar_csv([
            {'pregunta': '=1+1', 'respuesta': 'Texto, con "comillas"\ny salto',
             'metricas': {'tokens_por_segundo': None, 'tokens_salida': 0}},
            {'pregunta': 'Otra', 'error': 'No disponible', 'metricas': None},
        ])
        filas = list(csv.DictReader(io.StringIO(csv_texto)))
        self.assertEqual(filas[0]['pregunta'], "'=1+1")
        self.assertEqual(filas[0]['respuesta'], 'Texto, con "comillas"\ny salto')
        self.assertEqual(filas[0]['metricas.tokens_por_segundo'], '')
        self.assertEqual(filas[0]['metricas.tokens_salida'], '0')
        self.assertEqual(filas[1]['error'], 'No disponible')


if __name__ == '__main__':
    unittest.main()
