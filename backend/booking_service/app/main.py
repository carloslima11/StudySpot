import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.deps import _cliente_redis, agora
from app.locks_redis import LocksRedis
from app.repo_sql import criar_tabelas, get_sessionmaker
from app.routes import bookings
from app.routes.health import MENSAGEM_INDISPONIVEL, router as health_router
from app.tarefas import ciclo_periodico

log = logging.getLogger("studyspot")


def _iniciar_mqtt(settings):
    segredo = settings.checkin_segredo.get_secret_value() if settings.checkin_segredo else ""
    if not segredo:
        log.warning("MQTT_ATIVO=true mas CHECKIN_SEGREDO está vazio; check-in desligado.")
        return None
    from app.checkin_mqtt import SubscritorCheckin
    subscritor = SubscritorCheckin(
        settings.mqtt_host, settings.mqtt_port, settings.mqtt_topico_checkin,
        get_sessionmaker(), agora, segredo.encode(),
        antecedencia=timedelta(minutes=settings.antecedencia_checkin_minutos))
    subscritor.iniciar()
    return subscritor


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        criar_tabelas()
        if settings.semear_salas:
            from app.seed import semear
            semear()
    except Exception:
        log.exception("Não foi possível criar as tabelas; a base de dados está acessível?")

    subscritor = _iniciar_mqtt(settings) if settings.mqtt_ativo else None
    tarefa = None
    if settings.tarefa_periodica_ativa:
        locks = LocksRedis(_cliente_redis(), ttl_ms=settings.lock_ttl_ms)
        broker_saudavel = (lambda: subscritor.ligado) if subscritor else (lambda: False)
        tarefa = asyncio.create_task(
            ciclo_periodico(get_sessionmaker(), locks, agora, settings, broker_saudavel))
    try:
        yield
    finally:
        if tarefa:
            tarefa.cancel()
            with suppress(asyncio.CancelledError):
                await tarefa
        if subscritor:
            subscritor.parar()


app = FastAPI(title="StudySpot - Serviço de reservas", lifespan=lifespan)
app.include_router(health_router)
app.include_router(bookings.router)


@app.exception_handler(OperationalError)
async def postgres_indisponivel(
    request: Request,
    exc: OperationalError,
) -> JSONResponse:
    log.warning(
        "Pedido indisponível devido a falha operacional do PostgreSQL "
        "(método=%s, SQLSTATE=%s).",
        request.method,
        getattr(exc.orig, "sqlstate", "desconhecido"),
    )
    return JSONResponse(
        status_code=503,
        content={"detail": MENSAGEM_INDISPONIVEL},
        headers={"Retry-After": "5"},
    )
