"""Muestreo opcional del equipo sin dependencias de monitorización.

RAM y GPU corresponden al sistema completo. Los máximos son muestras, no
picos continuos ni recursos atribuibles exclusivamente a una inferencia.
"""

import os
from functools import lru_cache
from pathlib import Path
import platform
import shutil
import subprocess
from threading import Event, Thread
from time import perf_counter

import httpx


def leer_ram():
    try:
        valores = {linea.split(':')[0]: int(linea.split()[1]) * 1024
                   for linea in Path('/proc/meminfo').read_text().splitlines()
                   if linea.startswith(('MemTotal:', 'MemAvailable:'))}
        return {"total_bytes": valores['MemTotal'],
                "usada_bytes": valores['MemTotal'] - valores['MemAvailable']}
    except (OSError, ValueError, KeyError):
        return None


def leer_gpu():
    if not shutil.which('nvidia-smi'):
        return None
    try:
        salida = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
             '--format=csv,noheader,nounits'], capture_output=True, text=True,
            timeout=1, check=True,
        ).stdout
        return [{"nombre": partes[0].strip(), "total_bytes": int(partes[1]) * 1024**2,
                 "usada_bytes": int(partes[2]) * 1024**2, "utilizacion_porcentaje": int(partes[3])}
                for linea in salida.splitlines() if (partes := linea.split(','))]
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def leer_cpu():
    try:
        valores = [int(v) for v in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]
        return sum(valores), valores[3] + valores[4]
    except (OSError, IndexError, ValueError):
        return None


def modelo_en_memoria(modelo):
    """Instantánea de Ollama; no se interpreta VRAM global como uso del modelo."""
    try:
        with httpx.Client(timeout=2) as cliente:
            datos = cliente.get('http://127.0.0.1:11434/api/ps').raise_for_status().json()
        for item in datos.get('models', []):
            if item.get('name', item.get('model')) == modelo:
                return {clave: item.get(clave) for clave in
                        ('name', 'digest', 'size', 'size_vram', 'context_length', 'details')}
    except (httpx.HTTPError, ValueError):
        pass
    return None


@lru_cache(maxsize=1)
def version_ollama():
    try:
        with httpx.Client(timeout=2) as cliente:
            return cliente.get('http://127.0.0.1:11434/api/version').raise_for_status().json().get('version')
    except (httpx.HTTPError, ValueError):
        return None


class MuestreoRecursos:
    intervalo = 0.5

    def __init__(self):
        self.muestras = []
        self.parar = Event()
        self.hilo = None
        self.cpu_anterior = None

    def tomar(self):
        cpu = leer_cpu()
        uso_cpu = None
        if cpu and self.cpu_anterior and cpu[0] > self.cpu_anterior[0]:
            total = cpu[0] - self.cpu_anterior[0]
            uso_cpu = 100 * (1 - (cpu[1] - self.cpu_anterior[1]) / total)
        self.cpu_anterior = cpu
        self.muestras.append({"transcurrido_ms": (perf_counter() - self.inicio) * 1000,
                              "cpu_sistema_porcentaje": uso_cpu,
                              "ram": leer_ram(), "gpu": leer_gpu()})

    def _ejecutar(self):
        while not self.parar.wait(self.intervalo):
            self.tomar()

    def __enter__(self):
        self.inicio = perf_counter()
        self.tomar()
        self.hilo = Thread(target=self._ejecutar, daemon=True)
        self.hilo.start()
        return self

    def __exit__(self, *_):
        self.parar.set()
        self.hilo.join()
        self.tomar()

    def resultado(self):
        ram = [m['ram']['usada_bytes'] for m in self.muestras if m['ram']]
        gpu = [g['usada_bytes'] for m in self.muestras for g in m['gpu'] or []]
        cpu = [m['cpu_sistema_porcentaje'] for m in self.muestras if m['cpu_sistema_porcentaje'] is not None]
        return {
            "alcance": "Equipo completo; no atribuible exclusivamente al modelo. Máximos muestreados.",
            "intervalo_s": self.intervalo,
            "cantidad_muestras": len(self.muestras),
            "cpu_sistema_max_porcentaje": max(cpu) if cpu else None,
            "ram_sistema_max_bytes": max(ram) if ram else None,
            "vram_dispositivo_max_bytes": max(gpu) if gpu else None,
            "muestras": self.muestras,
        }


def equipo_actual():
    return {"sistema": platform.platform(), "cpu": platform.processor(),
            "hilos_cpu": os.cpu_count(), "ram": leer_ram(), "gpu": leer_gpu()}
