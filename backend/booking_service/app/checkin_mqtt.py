from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from app.qr_checkin import TokenInvalido, validar_token

log = logging.getLogger("studyspot.checkin")

TOPICO_BASE = "studyspot/salas"


class EventoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class EventoCheckin:
    sala_id: int
    token: str


@dataclass(frozen=True)
class ResultadoCheckin:
    ok: bool
    mensagem: str
    reserva_id: Optional[int] = None


def topico_checkin(sala_id: int) -> str:
    return f"{TOPICO_BASE}/{sala_id}/checkin"


def topico_resultado(sala_id: int) -> str:
    return f"{topico_checkin(sala_id)}/resultado"


def interpretar_evento(topico: str, payload: bytes | str) -> EventoCheckin:
    partes = topico.split("/")
    if len(partes) != 4 or "/".join(partes[:2]) != TOPICO_BASE or partes[3] != "checkin":
        raise EventoInvalido(f"tópico inesperado: {topico!r}")
    try:
        sala_id = int(partes[2])
        texto = payload.decode() if isinstance(payload, bytes) else payload
    except (ValueError, UnicodeDecodeError) as exc:
        raise EventoInvalido(f"evento inválido: {exc}") from exc
    texto = texto.strip()
    if texto.startswith("{"):
        try:
            texto = json.loads(texto)["token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise EventoInvalido(f"payload inválido: {exc}") from exc
    if not isinstance(texto, str) or not texto.strip():
        raise EventoInvalido("token em falta")
    return EventoCheckin(sala_id=sala_id, token=texto.strip())


def processar_checkin(repo, evento: EventoCheckin, segredo: bytes, agora: datetime,
                      antecedencia: timedelta = timedelta(minutes=15)) -> ResultadoCheckin:
    try:
        reserva_id = validar_token(segredo, evento.token, evento.sala_id, agora)
    except TokenInvalido as exc:
        return ResultadoCheckin(False, str(exc))
    reserva = repo.registar_checkin(reserva_id, evento.sala_id, agora, antecedencia)
    if reserva is None:
        return ResultadoCheckin(False, "Sem reserva ativa nesta sala para agora.", reserva_id)
    return ResultadoCheckin(True, "Check-in registado.", reserva_id)


class SubscritorCheckin:
    def __init__(self, host: str, port: int, topico: str, fabrica_sessao: Callable,
                 agora: Callable[[], datetime], segredo: bytes,
                 antecedencia: timedelta = timedelta(minutes=15),
                 criar_repo: Optional[Callable] = None) -> None:
        import paho.mqtt.client as mqtt
        self._host, self._port, self._topico = host, port, topico
        self._fabrica_sessao, self._agora, self._segredo = fabrica_sessao, agora, segredo
        self._antecedencia = antecedencia
        self._criar_repo = criar_repo
        self._ligado = threading.Event()
        self._cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._cliente.reconnect_delay_set(min_delay=1, max_delay=30)
        self._cliente.on_connect = self._ao_ligar
        self._cliente.on_disconnect = self._ao_desligar
        self._cliente.on_message = self._ao_receber

    @property
    def ligado(self) -> bool:
        return self._ligado.is_set()

    def iniciar(self) -> None:
        self._cliente.connect_async(self._host, self._port, keepalive=30)
        self._cliente.loop_start()

    def parar(self) -> None:
        self._cliente.loop_stop()
        try:
            self._cliente.disconnect()
        except Exception:
            pass
        self._ligado.clear()

    def _ao_ligar(self, cliente, _dados, _flags, reason_code, _props=None) -> None:
        if getattr(reason_code, "is_failure", False):
            log.warning("ligação ao broker recusada: %s", reason_code)
            return
        cliente.subscribe(self._topico, qos=1)
        self._ligado.set()
        log.info("ligado ao broker MQTT, a ouvir %s", self._topico)

    def _ao_desligar(self, _cliente, _dados, _flags, _reason_code=None, _props=None) -> None:
        self._ligado.clear()
        log.warning("ligação ao broker MQTT perdida")

    def _ao_receber(self, cliente, _dados, mensagem) -> None:
        try:
            evento = interpretar_evento(mensagem.topic, mensagem.payload)
        except EventoInvalido as exc:
            log.warning("evento ignorado: %s", exc)
            return
        try:
            with self._fabrica_sessao() as sessao:
                repo = self._criar_repo(sessao) if self._criar_repo else _repo_sql(sessao)
                resultado = processar_checkin(repo, evento, self._segredo, self._agora(),
                                              self._antecedencia)
        except Exception:
            log.exception("falha a processar o check-in na sala %s", evento.sala_id)
            resultado = ResultadoCheckin(False, "Erro interno; tente novamente.")
        log.info("check-in sala %s: %s", evento.sala_id, resultado.mensagem)
        cliente.publish(topico_resultado(evento.sala_id), json.dumps(asdict(resultado)), qos=1)


def _repo_sql(sessao: Any):
    from app.repo_sql import RepositorioSQL
    return RepositorioSQL(sessao)
