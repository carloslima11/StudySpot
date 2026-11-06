import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.routes.health import MENSAGEM_INDISPONIVEL, router as health_router
from app.routes.auth import router as auth_router

logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(health_router)

app.include_router(auth_router, prefix="/api/auth")


@app.exception_handler(OperationalError)
async def postgres_indisponivel(
    request: Request,
    exc: OperationalError,
) -> JSONResponse:
    logger.warning(
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
