from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LISBOA = ZoneInfo("Europe/Lisbon")


def _para_hora_local(t: datetime) -> datetime:
    if t.tzinfo is None:
        return t
    return t.astimezone(LISBOA).replace(tzinfo=None)


class ReservaIn(BaseModel):
    n_pessoas: int = Field(gt=0, le=1000)
    inicio: datetime
    fim: datetime
    sala_id: Optional[int] = Field(default=None, gt=0)
    janela_fim: Optional[datetime] = None

    @field_validator("inicio", "fim", "janela_fim")
    @classmethod
    def _local(cls, v: Optional[datetime]) -> Optional[datetime]:
        return None if v is None else _para_hora_local(v)

    @model_validator(mode="after")
    def _intervalo(self) -> "ReservaIn":
        if self.inicio >= self.fim:
            raise ValueError("O fim tem de ser posterior ao início.")
        if self.inicio.date() != self.fim.date():
            raise ValueError("A reserva tem de terminar no mesmo dia em que começa.")
        if self.janela_fim is not None and (
                self.janela_fim <= self.fim or self.janela_fim.date() != self.inicio.date()):
            raise ValueError("A janela de espera tem de terminar depois do fim, no mesmo dia.")
        return self


class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sala_id: int
    inicio: datetime
    fim: datetime
    n_pessoas: int
    estado: str
    check_in_em: Optional[datetime] = None


class SalaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    capacidade: int
    abertura: time
    fecho: time
    ativa: bool


class OcupacaoOut(BaseModel):
    sala_id: int
    inicio: datetime
    fim: datetime
    minha: bool


class HorarioAlternativo(BaseModel):
    sala_id: int
    inicio: datetime
    fim: datetime


class AlternativasOut(BaseModel):
    salas: list[int] = []
    horarios: list[HorarioAlternativo] = []


class EsperaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    n_pessoas: int
    janela_inicio: datetime
    janela_fim: datetime
    duracao: int
    estado: str
    criado_em: datetime


class QrOut(BaseModel):
    token: str
    expira_em: datetime
    sala_id: int
    check_in_feito: bool


class CriacaoOut(BaseModel):
    estado: str
    reserva: Optional[ReservaOut] = None
    motivos: list[str] = []
    alternativas: Optional[AlternativasOut] = None
