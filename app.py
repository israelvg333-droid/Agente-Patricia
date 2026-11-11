"""Punto de entrada de la interfaz grafica EVA.

Uso:
    python app.py                 # http://127.0.0.1:5000
    python app.py --port 8080 --open

La CLI original (`python main.py --audio ...`) sigue funcionando igual; ambos
caminos ejecutan el mismo pipeline y guardan en data/outputs/.
"""
from __future__ import annotations

import argparse
import threading
import webbrowser

from src.web.server import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interfaz grafica EVA (servidor local).")
    parser.add_argument("--host", default="127.0.0.1", help="Por defecto solo este equipo.")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--open", action="store_true", help="Abrir el navegador al iniciar."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app()
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}"
    print(f"\nEVA - interfaz disponible en {url}  (Ctrl+C para detener)\n")
    if args.open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    # threaded=True: las consultas de progreso se atienden mientras el worker analiza.
    app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
