import logging
import json
import secrets
import pyotp
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.cache import get_redis
from app.core.config import Settings, get_settings
from app.core.ratelimit import bloqueado, limpar_tentativas, registar_falha
from app.core.security import (
    cifrar_segredo_totp,
    decifrar_segredo_totp,
    gerar_hash_palavra_passe,
    gerar_segredo_totp,
    verificar_codigo_totp,
    verificar_palavra_passe,
)
from app.core.sessions import criar_sessao, obter_sessao
from app.db import get_db
from app.models import SegredoTOTP, Utilizador
from app.routes.health import MENSAGEM_INDISPONIVEL
from app.schemas import (
    ConfirmarTOTPRequest,
    DesafioLoginResposta,
    LoginPedido,
    LoginTOTPRequest,
    RegistoPedido,
    RegistoResposta,
    SessaoResposta,
    UtilizadorResposta,
)

router = APIRouter()
logger = logging.getLogger(__name__)
TTL_CONFIRMAR_TOTP = 15 * 60
TTL_DESAFIO_LOGIN = 5 * 60


def _ip_cliente(request: Request) -> str:
    return request.headers.get("x-real-ip") or (
        request.client.host if request.client else "desconhecido"
    )


def _indisponivel() -> HTTPException:
    return HTTPException(status_code=503, detail=MENSAGEM_INDISPONIVEL)


def _erro_login() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="E-mail, palavra-passe ou código inválido.",
    )


@router.post("/registo", response_model=RegistoResposta, status_code=201)
def registar(
    pedido: RegistoPedido,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> RegistoResposta:
    try:
        if not redis.ping():
            raise RedisError("O Redis não confirmou o ping.")
    except RedisError:
        logger.warning("Registo indisponível: falha no Redis.")
        raise HTTPException(
            status_code=503,
            detail=MENSAGEM_INDISPONIVEL,
        ) from None

    try:
        existente = db.scalar(
            select(Utilizador.id).where(Utilizador.email == pedido.email)
        )
        if existente is not None:
            raise HTTPException(
                status_code=409,
                detail="Já existe uma conta com este e-mail.",
            )

        segredo = gerar_segredo_totp()
        cifrado, nonce = cifrar_segredo_totp(
            segredo,
            settings.totp_encryption_key.get_secret_value(),
        )
        utilizador = Utilizador(
            nome=pedido.nome,
            email=pedido.email,
            palavra_passe_hash=gerar_hash_palavra_passe(
                pedido.palavra_passe.get_secret_value()
            ),
            perfil="estudante",
        )
        db.add(utilizador)
        db.flush()
        db.add(
            SegredoTOTP(
                utilizador_id=utilizador.id,
                segredo_cifrado=cifrado,
                nonce=nonce,
                confirmado=False,
            )
        )
        token_confirmacao = secrets.token_urlsafe(32)
        redis.set(
            f"confirmacao_totp:{token_confirmacao}",
            str(utilizador.id),
            ex=TTL_CONFIRMAR_TOTP,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe uma conta com este e-mail.",
        ) from None
    except RedisError:
        db.rollback()
        logger.warning("Registo indisponível: falha no Redis.")
        raise _indisponivel() from None
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Registo indisponível: falha no PostgreSQL.")
        raise HTTPException(
            status_code=503,
            detail=MENSAGEM_INDISPONIVEL,
        ) from None

    uri = pyotp.TOTP(segredo, digits=6, interval=30).provisioning_uri(
        name=utilizador.email,
        issuer_name="StudySpot",
    )
    return RegistoResposta(
        utilizador_id=utilizador.id,
        token_confirmacao=token_confirmacao,
        uri_configuracao_totp=uri,
    )


@router.post("/totp/confirmar")
def confirmar_totp(
    pedido: ConfirmarTOTPRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    try:
        valor = redis.get(
            f"confirmacao_totp:{pedido.token_confirmacao.get_secret_value()}")
    except RedisError:
        logger.warning("Confirmação TOTP indisponível: falha no Redis.")
        raise _indisponivel() from None
    if valor is None:
        raise HTTPException(
            status_code=401, detail="Código de confirmação inválido ou expirado.")
    if isinstance(valor, bytes):
        valor = valor.decode("utf-8")
    try:
        utilizador_id = int(valor)
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Código de confirmação inválido ou expirado.") from None

    try:
        utilizador = db.scalar(
            select(Utilizador).where(Utilizador.id ==
                                     utilizador_id).with_for_update()
        )
        segredo_guardado = db.get(SegredoTOTP, utilizador_id)
        if utilizador is None or segredo_guardado is None or segredo_guardado.confirmado:
            raise HTTPException(
                status_code=401, detail="Código de confirmação inválido ou expirado.")
        segredo = decifrar_segredo_totp(
            segredo_guardado.segredo_cifrado,
            segredo_guardado.nonce,
            settings.totp_encryption_key.get_secret_value(),
        )
        passo = verificar_codigo_totp(segredo, pedido.codigo)
        if passo is None:
            raise HTTPException(
                status_code=401, detail="Código de confirmação inválido ou expirado.")
        segredo_guardado.confirmado = True
        utilizador.ultimo_passo_totp = passo
        db.commit()
        redis.delete(
            f"confirmacao_totp:{pedido.token_confirmacao.get_secret_value()}")
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.warning("Confirmação TOTP indisponível: falha no PostgreSQL.")
        raise _indisponivel() from None

    return {"estado": "confirmado"}


@router.post("/login", response_model=DesafioLoginResposta, status_code=202)
def iniciar_login(
    pedido: LoginPedido,
    request: Request,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> DesafioLoginResposta:
    email = str(pedido.email)
    ip = _ip_cliente(request)
    try:
        restante = bloqueado(redis, email, ip)
        if restante:
            raise HTTPException(
                status_code=429,
                detail="Demasiadas tentativas. Tenta novamente dentro de 15 minutos.",
                headers={"Retry-After": str(restante)},
            )
        utilizador = db.scalar(
            select(Utilizador).where(Utilizador.email == email))
        if utilizador is None:
            registar_falha(redis, email, ip)
            logger.info("Tentativa de autenticação falhada.")
            raise _erro_login()
        segredo_totp = db.get(SegredoTOTP, utilizador.id)
        if (
            not utilizador.ativo
            or not verificar_palavra_passe(
                pedido.palavra_passe.get_secret_value(),
                utilizador.palavra_passe_hash,
            )
            or segredo_totp is None
            or not segredo_totp.confirmado
        ):
            registar_falha(redis, email, ip)
            logger.info("Tentativa de autenticação falhada.")
            raise _erro_login()
        token_desafio = secrets.token_urlsafe(32)
        redis.set(
            f"desafio_login:{token_desafio}",
            json.dumps({"utilizador_id": utilizador.id,
                       "email": email, "ip": ip}),
            ex=TTL_DESAFIO_LOGIN,
        )
    except HTTPException:
        raise
    except (RedisError, SQLAlchemyError):
        logger.warning("Login indisponível: falha numa dependência.")
        raise _indisponivel() from None
    return DesafioLoginResposta(token_desafio=token_desafio)


@router.post("/login/totp", response_model=SessaoResposta)
def concluir_login(
    pedido: LoginTOTPRequest,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> SessaoResposta:
    chave_desafio = f"desafio_login:{pedido.token_desafio.get_secret_value()}"
    try:
        valor = redis.get(chave_desafio)
    except RedisError:
        logger.warning("Login indisponível: falha no Redis.")
        raise _indisponivel() from None
    if valor is None:
        raise _erro_login()
    if isinstance(valor, bytes):
        valor = valor.decode("utf-8")
    try:
        desafio = json.loads(valor)
        utilizador_id = int(desafio["utilizador_id"])
        email = str(desafio["email"])
        ip = str(desafio["ip"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        redis.delete(chave_desafio)
        raise _erro_login() from None

    try:
        restante = bloqueado(redis, email, ip)
        if restante:
            raise HTTPException(
                status_code=429,
                detail="Demasiadas tentativas. Tenta novamente dentro de 15 minutos.",
                headers={"Retry-After": str(restante)},
            )
        utilizador = db.scalar(
            select(Utilizador).where(Utilizador.id ==
                                     utilizador_id).with_for_update()
        )
        segredo_guardado = db.get(SegredoTOTP, utilizador_id)
        if (
            utilizador is None
            or not utilizador.ativo
            or segredo_guardado is None
            or not segredo_guardado.confirmado
        ):
            registar_falha(redis, email, ip)
            raise _erro_login()

        segredo = decifrar_segredo_totp(
            segredo_guardado.segredo_cifrado,
            segredo_guardado.nonce,
            settings.totp_encryption_key.get_secret_value(),
        )
        passo = verificar_codigo_totp(segredo, pedido.codigo)
        if passo is None or (
            utilizador.ultimo_passo_totp is not None
            and passo <= utilizador.ultimo_passo_totp
        ):
            registar_falha(redis, email, ip)
            logger.info("Tentativa de autenticação falhada.")
            raise _erro_login()
        utilizador.ultimo_passo_totp = passo
        db.commit()
        limpar_tentativas(redis, email, ip)
        redis.delete(chave_desafio)
        token = criar_sessao(redis, utilizador.id,
                             utilizador.perfil, utilizador.email)
    except HTTPException:
        db.rollback()
        raise
    except (RedisError, SQLAlchemyError):
        db.rollback()
        logger.warning("Login indisponível: falha numa dependência.")
        raise _indisponivel() from None

    return SessaoResposta(
        token=token,
        utilizador_id=utilizador.id,
        email=utilizador.email,
        perfil=utilizador.perfil,
    )


def _token_bearer(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Sessão inválida ou em falta.")
    return authorization.removeprefix("Bearer ").strip()


@router.post("/logout", status_code=204)
def terminar_sessao(
    authorization: str | None = Header(default=None),
    redis: Redis = Depends(get_redis),
) -> None:
    token = _token_bearer(authorization)
    try:
        redis.delete(f"sessao:{token}")
    except RedisError:
        logger.warning("Logout indisponível: falha no Redis.")
        raise _indisponivel() from None


@router.get("/eu", response_model=UtilizadorResposta)
def utilizador_atual(
    authorization: str | None = Header(default=None),
    redis: Redis = Depends(get_redis),
) -> UtilizadorResposta:
    token = _token_bearer(authorization)
    try:
        dados = obter_sessao(redis, token)
    except RedisError:
        logger.warning("Validação de sessão indisponível: falha no Redis.")
        raise _indisponivel() from None
    if dados is None:
        raise HTTPException(
            status_code=401, detail="Sessão inválida ou expirada.")
    return UtilizadorResposta(
        utilizador_id=int(dados["utilizador_id"]),
        email=str(dados["email"]),
        perfil=str(dados["perfil"]),
    )
