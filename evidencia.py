"""Exportación de evidencia CLI, sin convertir ausencias en ceros."""

import csv
import io
import json
from pathlib import Path


def aplanar(datos, prefijo='', salida=None):
    salida = {} if salida is None else salida
    for clave, valor in datos.items():
        nombre = f'{prefijo}.{clave}' if prefijo else clave
        if isinstance(valor, dict):
            aplanar(valor, nombre, salida)
        else:
            salida[nombre] = json.dumps(valor, ensure_ascii=False) if isinstance(valor, list) else valor
    return salida


def celda_segura(valor):
    if isinstance(valor, str) and (valor.lstrip().startswith(('=', '+', '-', '@')) or valor.startswith(('\t', '\r', '\n'))):
        return "'" + valor
    return valor


def generar_csv(registros):
    filas = [aplanar(registro) for registro in registros]
    columnas = list(dict.fromkeys(clave for fila in filas for clave in fila))
    salida = io.StringIO(newline='')
    escritor = csv.DictWriter(salida, fieldnames=columnas)
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({clave: celda_segura(valor) for clave, valor in fila.items()})
    return salida.getvalue()


def guardar_evidencia(ruta, evidencia):
    ruta = Path(ruta).with_suffix('.json')
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix('.json.tmp')
    temporal.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2), encoding='utf-8')
    temporal.replace(ruta)
    ruta.with_suffix('.csv').write_text(generar_csv(evidencia['registros']), encoding='utf-8-sig')
