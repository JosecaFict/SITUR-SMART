"""Configuracion de gunicorn. Se carga sola al arrancar desde esta carpeta.

El comando de Railway (``gunicorn config.wsgi:application --bind 0.0.0.0:$PORT``)
no cambia: las opciones de la linea de comandos tienen prioridad sobre este
archivo, y este solo agrega lo que faltaba.

- Hilos: con el worker ``sync`` por omision se atendia una peticion a la vez, y
  una consulta lenta (el asistente IA, un reporte, Stripe) bloqueaba al resto.
- Un solo proceso a proposito: los limites por usuario (throttling) y la cache
  viven en la memoria del proceso y se multiplicarian con varios procesos.
- Timeout: 30 s por omision cortaba peticiones legitimas que esperan a un
  servicio externo. Cada servicio tiene ademas su propio timeout.
"""

import os

workers = int(os.getenv("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "90"))
graceful_timeout = 30
