"""Ejecuta preguntas secuenciales contra la misma API que usa React.

Ejemplo: uv run python evaluar.py --salida resultados/prueba.json
No califica automáticamente la calidad ni simula concurrencia.
"""

import argparse
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import httpx

from evidencia import guardar_evidencia
from experimento import MODELO, MODELO_QWEN, Parametros, RAZONAMIENTO_PREDETERMINADO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api', default='http://127.0.0.1:8000')
    parser.add_argument('--modelos', nargs='+', choices=[MODELO, MODELO_QWEN], default=[MODELO, MODELO_QWEN])
    parser.add_argument('--razonamiento-gpt', choices=['low', 'medium', 'high'], default=RAZONAMIENTO_PREDETERMINADO[MODELO])
    parser.add_argument('--razonamiento-qwen', choices=['activado', 'desactivado'], default=RAZONAMIENTO_PREDETERMINADO[MODELO_QWEN])
    parser.add_argument('--repeticiones', type=int, choices=range(1, 6), default=1)
    parser.add_argument('--casos', nargs='+', help='Identificadores del banco; omitir para ejecutar todos.')
    parser.add_argument('--temperatura', type=float, default=0.2)
    parser.add_argument('--semilla', type=int, default=42)
    parser.add_argument('--contexto', type=int, default=8192)
    parser.add_argument('--max-tokens', type=int, default=1024)
    parser.add_argument('--salida', default='resultados/evaluacion.json')
    args = parser.parse_args()
    parametros = Parametros(temperature=args.temperatura, seed=args.semilla,
                            num_ctx=args.contexto, num_predict=args.max_tokens).model_dump()
    modos = {MODELO: args.razonamiento_gpt, MODELO_QWEN: args.razonamiento_qwen}
    lote_id = str(uuid4())
    with httpx.Client(base_url=args.api, timeout=300) as cliente:
        experimento = cliente.get('/experimento').raise_for_status().json()
        banco = cliente.get('/evaluacion').raise_for_status().json()
        if args.casos and set(args.casos) - {caso['id'] for caso in banco['casos']}:
            parser.error('Hay identificadores de casos desconocidos.')
        casos = [caso for caso in banco['casos'] if not args.casos or caso['id'] in args.casos]
        if any(caso['revisar_referencias'] for caso in casos):
            parser.error('Revisa las referencias del banco tras modificar el catálogo.')
        evidencia = {
            'formato': 'asistente-fisi-evidencia-v1',
            'exportado_en': datetime.now(timezone.utc).isoformat(),
            'protocolo': 'Un usuario, solicitudes secuenciales, equipo personal. Carga natural sin descargar ni precalentar. No prueba concurrencia ni servidor institucional.',
            'experimento': experimento, 'registros': [],
        }
        guardar_evidencia(args.salida, evidencia)
        for repeticion in range(1, args.repeticiones + 1):
            orden = args.modelos if repeticion % 2 else list(reversed(args.modelos))
            for modelo in orden:
                for caso in casos:
                    conversacion_id = None
                    for turno, pregunta in enumerate(caso['turnos'], 1):
                        contexto = dict(origen='evaluacion', lote_id=lote_id, banco_version=banco['version'],
                                        caso_id=caso['id'], categoria=caso['categoria'], turno=turno,
                                        repeticion=repeticion, criterio=pregunta['criterio'],
                                        referencias=caso['referencias'], pregunta=pregunta['pregunta'],
                                        calidad={}, notas_calidad='', revisor='')
                        cuerpo = dict(mensaje=pregunta['pregunta'], modelo=modelo,
                                      razonamiento=modos[modelo], parametros=parametros)
                        if conversacion_id:
                            cuerpo['conversacion_id'] = conversacion_id
                        print(f'{modelo} · {caso["id"]} · turno {turno} · repetición {repeticion}', flush=True)
                        inicio = perf_counter()
                        try:
                            datos = cliente.post('/chat', json=cuerpo).raise_for_status().json()
                            datos['latencia_cliente_ms'] = (perf_counter() - inicio) * 1000
                            conversacion_id = datos['conversacion_id']
                            evidencia['registros'].append({**datos, **contexto})
                        except (httpx.HTTPError, ValueError, KeyError) as error:
                            evidencia['registros'].append({**contexto, 'registro_id': str(uuid4()),
                                'fecha': datetime.now(timezone.utc).isoformat(),
                                'modelo': modelo, 'razonamiento': modos[modelo], 'parametros': parametros,
                                'error': str(error), 'metricas': None,
                                'catalogo_sha256': experimento['catalogo_sha256'],
                                'sistema_sha256': experimento['sistema_sha256'], 'entorno': experimento['entorno']})
                            guardar_evidencia(args.salida, evidencia)
                            print(f'ERROR: {error}; se omiten los turnos dependientes.', flush=True)
                            break
                        guardar_evidencia(args.salida, evidencia)
    print(f'Evidencia JSON y CSV guardada en {args.salida}. Calidad pendiente de revisión humana.')


if __name__ == '__main__':
    main()
