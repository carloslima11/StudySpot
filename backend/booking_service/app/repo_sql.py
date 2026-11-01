from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.csp import PedidoEspera
from app.db import get_engine
from app.models import Base, ListaEspera, Reserva, ReservaSlot, Sala
from app.servico_reservas import ESTADOS_ATIVOS, ConflitoSlot

@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with get_sessionmaker()() as sessao:
        yield sessao


def criar_tabelas() -> None:
    Base.metadata.create_all(get_engine())


_CONSTRAINT_SLOT = "uq_reserva_slots_sala_slot"
_CONSTRAINT_CHAVE = "uq_reservas_utilizador_chave"


def _constraint_violada(exc: IntegrityError) -> str:
    diag = getattr(exc.orig, "diag", None)
    nome = getattr(diag, "constraint_name", None)
    if nome:
        return nome
    texto = str(exc.orig)
    for candidata in (_CONSTRAINT_SLOT, _CONSTRAINT_CHAVE):
        if candidata in texto:
            return candidata
    if "reserva_slots" in texto and "sala_id" in texto:
        return _CONSTRAINT_SLOT
    if "reservas" in texto and "chave_idempotencia" in texto:
        return _CONSTRAINT_CHAVE
    return ""


class RepositorioSQL:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def salas(self) -> list[Sala]:
        return list(self.sessao.scalars(select(Sala).order_by(Sala.id)))

    def reservas_ativas_nos_dias(self, dias: set[date]) -> list[Reserva]:
        if not dias:
            return []
        de = datetime.combine(min(dias), time.min)
        ate = datetime.combine(max(dias) + timedelta(days=1), time.min)
        consulta = select(Reserva).where(
            Reserva.estado.in_(ESTADOS_ATIVOS), Reserva.inicio >= de, Reserva.inicio < ate)
        return [r for r in self.sessao.scalars(consulta) if r.inicio.date() in dias]

    def reserva_por_chave(self, utilizador_id: int, chave: str) -> Optional[Reserva]:
        return self.sessao.scalars(select(Reserva).where(
            Reserva.utilizador_id == utilizador_id,
            Reserva.chave_idempotencia == chave)).first()

    def obter_reserva(self, reserva_id: int) -> Optional[Reserva]:
        return self.sessao.get(Reserva, reserva_id)

    def reservas_do_utilizador(self, utilizador_id: int) -> list[Reserva]:
        return list(self.sessao.scalars(
            select(Reserva).where(Reserva.utilizador_id == utilizador_id)
            .order_by(Reserva.inicio.desc())))

    def inserir_reserva(self, *, utilizador_id: int, sala_id: int, inicio: datetime,
                        fim: datetime, n_pessoas: int, chave_idempotencia: str,
                        slots: list[datetime]) -> Reserva:
        reserva = Reserva(
            utilizador_id=utilizador_id, sala_id=sala_id, inicio=inicio, fim=fim,
            n_pessoas=n_pessoas, estado="confirmada", chave_idempotencia=chave_idempotencia,
            slots=[ReservaSlot(sala_id=sala_id, slot_inicio=s) for s in slots])
        try:
            self.sessao.add(reserva)
            self.sessao.commit()
        except IntegrityError as exc:
            self.sessao.rollback()
            violada = _constraint_violada(exc)
            if violada == _CONSTRAINT_SLOT:
                raise ConflitoSlot() from exc
            if violada == _CONSTRAINT_CHAVE:
                existente = self.reserva_por_chave(utilizador_id, chave_idempotencia)
                if existente is not None:
                    return existente
            raise
        return reserva

    def cancelar_reserva(self, utilizador_id: int, reserva_id: int,
                         agora: datetime) -> Optional[Reserva]:
        reserva = self.sessao.scalars(
            select(Reserva).where(Reserva.id == reserva_id).with_for_update()).first()
        if reserva is None or reserva.utilizador_id != utilizador_id:
            self.sessao.rollback()
            return None
        if reserva.estado != "confirmada" or reserva.fim <= agora:
            self.sessao.rollback()
            return reserva
        reserva.estado = "cancelada"
        self.sessao.execute(delete(ReservaSlot).where(ReservaSlot.reserva_id == reserva.id))
        self.sessao.commit()
        return reserva

    def guardar_espera(self, utilizador_id: int, pedido: PedidoEspera) -> ListaEspera:
        espera = ListaEspera(
            utilizador_id=utilizador_id, n_pessoas=pedido.participantes,
            janela_inicio=pedido.janela_inicio, janela_fim=pedido.janela_fim,
            duracao=pedido.duracao_minutos, criado_em=pedido.criado_em, estado="ativa")
        self.sessao.add(espera)
        self.sessao.commit()
        return espera

    def espera_ativa(self) -> list[ListaEspera]:
        return list(self.sessao.scalars(
            select(ListaEspera).where(ListaEspera.estado == "ativa")
            .order_by(ListaEspera.criado_em, ListaEspera.id)))

    def marcar_espera_atendida(self, espera_id: int, reserva: Any) -> None:
        self._mudar_estado_espera(espera_id, "atendida")

    def marcar_espera_expirada(self, espera_id: int) -> None:
        self._mudar_estado_espera(espera_id, "expirada")

    def _mudar_estado_espera(self, espera_id: int, estado: str) -> None:
        espera = self.sessao.get(ListaEspera, espera_id)
        if espera is not None:
            espera.estado = estado
            self.sessao.commit()

    def libertar_sem_checkin(self, limite: datetime, agora: datetime) -> list[int]:
        consulta = (select(Reserva)
                    .where(Reserva.estado == "confirmada", Reserva.check_in_em.is_(None),
                           Reserva.inicio <= limite)
                    .with_for_update(skip_locked=True))
        reservas = list(self.sessao.scalars(consulta))
        ids = [r.id for r in reservas]
        if ids:
            for r in reservas:
                r.estado = "libertada"
            self.sessao.execute(delete(ReservaSlot).where(ReservaSlot.reserva_id.in_(ids)))
        self.sessao.commit()
        return ids

    def registar_checkin(self, reserva_id: int, sala_id: int, quando: datetime,
                         antecedencia: timedelta) -> Optional[Reserva]:
        consulta = (select(Reserva)
                    .where(Reserva.id == reserva_id, Reserva.sala_id == sala_id,
                           Reserva.estado == "confirmada",
                           Reserva.inicio <= quando + antecedencia, Reserva.fim > quando)
                    .with_for_update())
        reserva = self.sessao.scalars(consulta).first()
        if reserva is None:
            self.sessao.rollback()
            return None
        if reserva.check_in_em is None:
            reserva.check_in_em = quando
        self.sessao.commit()
        return reserva
