"""Banco de preguntas y referencias para revisión humana, nunca otro prompt."""

from copy import deepcopy
import json
from pathlib import Path

from main import catalogo, CATALOGO_SHA256


def banco_preguntas():
    banco = json.loads(Path(__file__).with_name('preguntas_evaluacion.json').read_text(encoding='utf-8'))
    tramites = {tramite['id']: tramite for tramite in json.loads(catalogo)['tramites']}
    for caso in banco['casos']:
        tramite = tramites.get(caso['tramite'])
        referencias = {}
        revisar = tramite is None
        for ruta in caso['campos']:
            valor = tramite
            for parte in ruta.split('.'):
                if not isinstance(valor, dict) or parte not in valor:
                    revisar = True
                    valor = None
                    break
                valor = valor[parte]
            referencias[ruta] = deepcopy(valor)
        caso['referencias'] = referencias
        caso['revisar_referencias'] = revisar
    return {**banco, 'catalogo_sha256': CATALOGO_SHA256,
            'metodo_calidad': 'Revisión humana: 0 incorrecto, 1 parcial, 2 correcto; N/A cuando no aplique. Sin puntaje automático.'}
