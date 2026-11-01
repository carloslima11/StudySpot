from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.checkin_mqtt import topico_checkin, topico_resultado


def interpretar_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dispositivo de check-in por QR code.")
    p.add_argument("--sala", type=int, required=True)
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=11883)
    modo = p.add_mutually_exclusive_group()
    modo.add_argument("--token", help="publica só este token e termina")
    modo.add_argument("--camara", action="store_true", help="lê QR codes da câmara")
    p.add_argument("--camara-indice", type=int, default=0)
    p.add_argument("--espera", type=float, default=5.0,
                   help="segundos a aguardar a resposta do serviço")
    return p.parse_args(argv)


def leituras_teclado() -> Iterator[str]:
    for linha in sys.stdin:
        if linha.strip():
            yield linha.strip()


def leituras_camara(indice: int) -> Iterator[str]:
    import cv2
    camara = cv2.VideoCapture(indice)
    detetor = cv2.QRCodeDetector()
    ultimo, desde = "", 0.0
    try:
        while True:
            ok, imagem = camara.read()
            if not ok:
                time.sleep(0.2)
                continue
            texto, _, _ = detetor.detectAndDecode(imagem)
            if texto and (texto != ultimo or time.time() - desde > 5):
                ultimo, desde = texto, time.time()
                yield texto
    finally:
        camara.release()


def sinalizar(resultado: dict) -> None:
    simbolo = "VERDE" if resultado.get("ok") else "VERMELHO"
    print(f"[{simbolo}] {resultado.get('mensagem')}")


def executar(args: argparse.Namespace, leituras: Iterable[str],
             sinal: Callable[[dict], None] = sinalizar) -> None:
    import paho.mqtt.client as mqtt

    resposta = threading.Event()

    def ao_receber(_c, _d, mensagem):
        sinal(json.loads(mensagem.payload))
        resposta.set()

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    cliente.on_message = ao_receber
    cliente.connect(args.host, args.port, keepalive=30)
    cliente.subscribe(topico_resultado(args.sala), qos=1)
    cliente.loop_start()
    try:
        for token in leituras:
            resposta.clear()
            cliente.publish(topico_checkin(args.sala), token, qos=1).wait_for_publish(5)
            if not resposta.wait(args.espera):
                sinal({"ok": False, "mensagem": "Sem resposta do serviço."})
    finally:
        cliente.loop_stop()
        cliente.disconnect()


if __name__ == "__main__":
    argumentos = interpretar_argumentos()
    if argumentos.token:
        fonte: Iterable[str] = [argumentos.token]
    elif argumentos.camara:
        fonte = leituras_camara(argumentos.camara_indice)
    else:
        print(f"Sala {argumentos.sala}: à espera de leituras (Ctrl+C para sair)")
        fonte = leituras_teclado()
    executar(argumentos, fonte)
