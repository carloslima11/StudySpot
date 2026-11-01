from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
                        PrimaryKeyConstraint, String, Time, UniqueConstraint, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ESTADOS_RESERVA = ("confirmada", "concluida", "cancelada", "libertada")
ESTADOS_ESPERA = ("ativa", "atendida", "expirada")


class Base(DeclarativeBase):
    pass


class Sala(Base):
    __tablename__ = "salas"
    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_salas_capacidade"),
        CheckConstraint("abertura < fecho", name="ck_salas_horario"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False)
    abertura: Mapped[time] = mapped_column(Time, nullable=False)
    fecho: Mapped[time] = mapped_column(Time, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Dispositivo(Base):
    __tablename__ = "dispositivos"
    __table_args__ = (UniqueConstraint("sala_id", name="uq_dispositivos_sala"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sala_id: Mapped[int] = mapped_column(ForeignKey("salas.id"), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (
        UniqueConstraint("utilizador_id", "chave_idempotencia",
                         name="uq_reservas_utilizador_chave"),
        CheckConstraint("estado IN ('confirmada', 'concluida', 'cancelada', 'libertada')",
                        name="ck_reservas_estado"),
        CheckConstraint("inicio < fim", name="ck_reservas_intervalo"),
        CheckConstraint("n_pessoas > 0", name="ck_reservas_n_pessoas"),
        Index("ix_reservas_sala_inicio", "sala_id", "inicio"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilizador_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sala_id: Mapped[int] = mapped_column(ForeignKey("salas.id"), nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fim: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    n_pessoas: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmada")
    chave_idempotencia: Mapped[str] = mapped_column(String(64), nullable=False)
    check_in_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now())

    sala: Mapped[Sala] = relationship()
    slots: Mapped[list["ReservaSlot"]] = relationship(
        back_populates="reserva", cascade="all, delete-orphan", passive_deletes=True)


class ReservaSlot(Base):

    __tablename__ = "reserva_slots"
    __table_args__ = (
        PrimaryKeyConstraint("reserva_id", "slot_inicio", name="pk_reserva_slots"),
        UniqueConstraint("sala_id", "slot_inicio", name="uq_reserva_slots_sala_slot"),
    )

    reserva_id: Mapped[int] = mapped_column(
        ForeignKey("reservas.id", ondelete="CASCADE"), nullable=False)
    sala_id: Mapped[int] = mapped_column(ForeignKey("salas.id"), nullable=False)
    slot_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    reserva: Mapped[Reserva] = relationship(back_populates="slots")


class ListaEspera(Base):
    __tablename__ = "lista_espera"
    __table_args__ = (
        CheckConstraint("estado IN ('ativa', 'atendida', 'expirada')",
                        name="ck_lista_espera_estado"),
        CheckConstraint("janela_inicio < janela_fim", name="ck_lista_espera_janela"),
        CheckConstraint("duracao > 0", name="ck_lista_espera_duracao"),
        CheckConstraint("n_pessoas > 0", name="ck_lista_espera_n_pessoas"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilizador_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    n_pessoas: Mapped[int] = mapped_column(Integer, nullable=False)
    janela_inicio: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    janela_fim: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duracao: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now())
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="ativa")
