import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app.core.config import Settings, get_settings
from app.csp import Alternativas, ConfigCSP
from app.deps import agora, get_cfg, get_locks, get_repo, utilizador_atual
from app.locks_redis import LocksRedis, RedisIndisponivel
from app.qr_checkin import gerar_token
from app.repo_sql import RepositorioSQL
from app.schemas import (AlternativasOut, CriacaoOut, HorarioAlternativo, QrOut, ReservaIn,
                         ReservaOut, SalaOut)
from app.servico_reservas import LockIndisponivel, criar_reserva, realocar_espera

router = APIRouter(prefix="/api")
log = logging.getLogger("studyspot.reservas")

_HTTP_POR_ESTADO = {"confirmada": 201, "duplicada": 200, "espera": 202, "recusada": 422}


def _alternativas(a: Alternativas | None) -> AlternativasOut | None:
    if a is None:
        return None
    return AlternativasOut(
        salas=[int(s) for s in a.salas],
        horarios=[HorarioAlternativo(sala_id=int(s), inicio=i, fim=f)
                  for s, i, f in a.horarios])


@router.get("/salas", response_model=list[SalaOut])
def listar_salas(repo: Annotated[RepositorioSQL, Depends(get_repo)],
                 _: Annotated[int, Depends(utilizador_atual)]):
    return [s for s in repo.salas() if s.ativa]


@router.get("/reservas/minhas", response_model=list[ReservaOut])
def minhas_reservas(repo: Annotated[RepositorioSQL, Depends(get_repo)],
                    utilizador_id: Annotated[int, Depends(utilizador_atual)]):
    return repo.reservas_do_utilizador(utilizador_id)


@router.post("/reservas", response_model=CriacaoOut)
def criar(pedido: ReservaIn, resposta: Response,
          utilizador_id: Annotated[int, Depends(utilizador_atual)],
          repo: Annotated[RepositorioSQL, Depends(get_repo)],
          locks: Annotated[LocksRedis, Depends(get_locks)],
          cfg: Annotated[ConfigCSP, Depends(get_cfg)],
          chave: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)]):
    try:
        res = criar_reserva(
            repo, locks, utilizador_id=utilizador_id, chave_idempotencia=chave,
            n_pessoas=pedido.n_pessoas, inicio=pedido.inicio, fim=pedido.fim,
            sala_id=pedido.sala_id, janela_fim=pedido.janela_fim, agora=agora(), cfg=cfg)
    except RedisIndisponivel:
        raise HTTPException(status_code=503, detail="Serviço temporariamente indisponível; "
                            "a reserva não foi confirmada.", headers={"Retry-After": "5"})
    except LockIndisponivel:
        raise HTTPException(status_code=409, detail="O horário está a ser reservado por "
                            "outro pedido; tente novamente.", headers={"Retry-After": "1"})
    resposta.status_code = _HTTP_POR_ESTADO[res.estado]
    return CriacaoOut(
        estado=res.estado,
        reserva=None if res.reserva is None else ReservaOut.model_validate(res.reserva),
        motivos=res.motivos, alternativas=_alternativas(res.alternativas))


@router.delete("/reservas/{reserva_id}", response_model=ReservaOut)
def cancelar(reserva_id: int,
             utilizador_id: Annotated[int, Depends(utilizador_atual)],
             repo: Annotated[RepositorioSQL, Depends(get_repo)],
             locks: Annotated[LocksRedis, Depends(get_locks)],
             cfg: Annotated[ConfigCSP, Depends(get_cfg)]):
    momento = agora()
    estado_antes = getattr(repo.obter_reserva(reserva_id), "estado", None)
    reserva = repo.cancelar_reserva(utilizador_id, reserva_id, momento)
    if reserva is None:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")
    if reserva.estado != "cancelada":
        raise HTTPException(status_code=409,
                            detail=f"Não é possível cancelar uma reserva {reserva.estado} "
                                   "ou que já terminou.")
    if estado_antes == "confirmada":
        try:
            realocar_espera(repo, locks, agora=momento, cfg=cfg)
        except Exception:
            log.exception("cancelamento feito, mas a realocação da lista de espera falhou")
    return reserva


@router.get("/reservas/{reserva_id}/qr", response_model=QrOut)
def qr_checkin(reserva_id: int,
               utilizador_id: Annotated[int, Depends(utilizador_atual)],
               repo: Annotated[RepositorioSQL, Depends(get_repo)],
               settings: Annotated[Settings, Depends(get_settings)]):
    segredo = settings.checkin_segredo.get_secret_value() if settings.checkin_segredo else ""
    if not segredo:
        raise HTTPException(status_code=503, detail="Check-in por QR code não configurado.")
    reserva = repo.obter_reserva(reserva_id)
    if reserva is None or reserva.utilizador_id != utilizador_id:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")
    momento = agora()
    if reserva.estado != "confirmada" or reserva.fim <= momento:
        raise HTTPException(status_code=409, detail="Esta reserva já não aceita check-in.")
    token = gerar_token(segredo.encode(), reserva.id, reserva.sala_id, momento,
                        timedelta(seconds=settings.qr_validade_segundos))
    return QrOut(token=token.texto, expira_em=token.expira_em, sala_id=reserva.sala_id,
                 check_in_feito=reserva.check_in_em is not None)
