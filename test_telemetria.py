"""Verifica ausencia de sensores y agregación de muestras, sin necesitar GPU."""
import unittest
from unittest.mock import patch

from telemetria import MuestreoRecursos, leer_ram, leer_gpu


class TelemetriaTests(unittest.TestCase):
    def test_sensores_ausentes_no_inventan_valores(self):
        with patch('telemetria.Path.read_text', side_effect=OSError), patch('telemetria.shutil.which', return_value=None):
            self.assertIsNone(leer_ram())
            self.assertIsNone(leer_gpu())

    def test_maximos_son_muestras_y_no_se_confunden_con_consumo_del_modelo(self):
        muestreo = MuestreoRecursos()
        muestreo.muestras = [
            {'ram': {'usada_bytes': 100}, 'gpu': [{'usada_bytes': 30}], 'cpu_sistema_porcentaje': None},
            {'ram': {'usada_bytes': 120}, 'gpu': [{'usada_bytes': 20}], 'cpu_sistema_porcentaje': 0},
        ]
        resultado = muestreo.resultado()
        self.assertEqual(resultado['ram_sistema_max_bytes'], 120)
        self.assertEqual(resultado['vram_dispositivo_max_bytes'], 30)
        self.assertEqual(resultado['cpu_sistema_max_porcentaje'], 0)
        self.assertEqual(resultado['cantidad_muestras'], 2)
        self.assertIn('no atribuible', resultado['alcance'])


if __name__ == '__main__':
    unittest.main()
