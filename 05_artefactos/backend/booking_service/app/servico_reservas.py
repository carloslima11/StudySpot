"""
servico_reservas.py - Cola entre o csp.py, o Redis e a base de dados.

Só dá pra testar pra semana quando trbalharea a serio
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, ContextManager, Iterable, Optional, Protocol

from app.csp import (Alternativas, ConfigCSP, MotorCSP, PedidoEspera, PedidoReserva,
                 Reserva, Sala, para_espera, slots_ocupados)

ESTADOS_ATIVOS = ("confirmada", "concluida")


class ConflitoSlot(Exception):

class LockIndisponivel(Exception):

class Locks(Protocol):
    def adquirir(self, chaves: list[str]) -> ContextManager[None]: ...

class Repositorio(Protocol):
    def salas(self) -> list[Any]: ...
    def reservas_ativas_nos_dias(self, dias: set[date]) -> list[Any]: ...
    def reserva_por_chave(self, utilizador_id: int, chave: str) -> Optional[Any]: ...
    def inserir_reserva(self, *, utilizador_id: int, sala_id: int, inicio: datetime,
                        fim: datetime, n_pessoas: int, chave_idempotencia: str,
                        slots: list[datetime]) -> Any: ...

    def guardar_espera(self, utilizador_id: int, pedido: PedidoEspera) -> Any: ...
    def espera_ativa(self) -> list[Any]: ...
    def marcar_espera_atendida(self, espera_id: int, reserva: Any) -> None: ...
    def marcar_espera_expirada(self, espera_id: int) -> None: ...
    def libertar_sem_checkin(self, limite: datetime, agora: datetime) -> list[int]: ...

def _local(t: datetime) -> datetime:
    if t.tzinfo is None:
        return t
    from zoneinfo import ZoneInfo
    return t.astimezone(ZoneInfo("Europe/Lisbon")).replace(tzinfo=None)


def sala_para_csp(s: Any) -> Sala:
    return Sala(id=str(s.id), capacidade=s.capacidade, abertura=s.abertura,
                fecho=s.fecho, ativa=s.ativa)


def reserva_para_csp(r: Any) -> Reserva:
    return Reserva(id=str(r.id), sala_id=str(r.sala_id), estudante_id=str(r.utilizador_id),
                   inicio=_local(r.inicio), fim=_local(r.fim))


def espera_para_csp(e: Any) -> PedidoEspera:
    return PedidoEspera(id=str(e.id), estudante_id=str(e.utilizador_id),
                        participantes=e.n_pessoas, janela_inicio=_local(e.janela_inicio),
                        janela_fim=_local(e.janela_fim), duracao_minutos=e.duracao,
                        criado_em=_local(e.criado_em))


def chaves_lock(sala_id: Any, slots: Iterable[datetime]) -> list[str]:

    return sorted(f"slot:{sala_id}:{s.isoformat()}" for s in slots)


def _dias_da_janela(p: PedidoEspera) -> set[date]:
    n = (p.janela_fim.date() - p.janela_inicio.date()).days
    return {p.janela_inicio.date() + timedelta(days=i) for i in range(n + 1)}


def _arredondar_para_cima(t: datetime, slot_minutos: int) -> datetime:
    base = t.replace(hour=0, minute=0, second=0, microsecond=0)
    minutos = t.hour * 60 + t.minute + (1 if (t.second or t.microsecond) else 0)
    blocos = -(-minutos // slot_minutos)  # divisão por excesso
    return base + timedelta(minutes=blocos * slot_minutos)

# Diagrama 3: criar reserva

@dataclass
class ResultadoCriacao:

    estado: str
    reserva: Any = None
    motivos: list[str] = field(default_factory=list)
    alternativas: Optional[Alternativas] = None


def criar_reserva(repo: Repositorio, locks: Locks, *, utilizador_id: int,
                  chave_idempotencia: str, n_pessoas: int, inicio: datetime,
                  fim: datetime, sala_id: Optional[int] = None, agora: datetime,
                  cfg: ConfigCSP = ConfigCSP(), max_tentativas: int = 3) -> ResultadoCriacao:
    # 1. Idempotência: um reenvio devolve o resultado anterior em vez de criar outra reserva(Salva pra krlh)
    existente = repo.reserva_por_chave(utilizador_id, chave_idempotencia)
    if existente is not None:
        return ResultadoCriacao("duplicada", reserva=existente)

    motor = MotorCSP(cfg)
    pedido = PedidoReserva(id="novo", estudante_id=str(utilizador_id), participantes=n_pessoas,
                           inicio=inicio, fim=fim, criado_em=agora,
                           sala_id=None if sala_id is None else str(sala_id))
    conflito = False
    for _ in range(max_tentativas):
        # 2. Ler o estado atual (cada volta relê: o conflito significa que mudou).
        salas = [sala_para_csp(s) for s in repo.salas()]
        fixas = [reserva_para_csp(r) for r in repo.reservas_ativas_nos_dias({inicio.date()})]
        # 3. Executar o CSP.
        res = motor.resolver([pedido], salas, fixas)
        if "novo" not in res.atribuicoes:
            conflito = False
            break
        escolhida = res.atribuicoes["novo"]
        slots = slots_ocupados(inicio, fim, cfg)
        # 4. Locks por slot (Redis) e INSERT (UNIQUE na BD como garantia final).
        with locks.adquirir(chaves_lock(escolhida, slots)):
            try:
                reserva = repo.inserir_reserva(
                    utilizador_id=utilizador_id, sala_id=int(escolhida), inicio=inicio,
                    fim=fim, n_pessoas=n_pessoas, chave_idempotencia=chave_idempotencia,
                    slots=slots)
            except ConflitoSlot:
                conflito = True       # alguém passou à frente: voltar a decidir
                continue
        return ResultadoCriacao("confirmada", reserva=reserva)

    # 5. Sem solução: motivos + alternativas; lista de espera só se valer a pena.
    if conflito:
        motivos = ["O horário foi ocupado por outro pedido em simultâneo."]
        entra_em_espera = True
    else:
        motivos = res.rejeitados["novo"]
        entra_em_espera = "novo" in res.lista_espera
    alternativas = motor.sugerir_alternativas(pedido, salas, fixas)
    if entra_em_espera:
        repo.guardar_espera(utilizador_id, para_espera(pedido))
        return ResultadoCriacao("espera", motivos=motivos, alternativas=alternativas)
    return ResultadoCriacao("recusada", motivos=motivos, alternativas=alternativas)

# Diagrama 4: libertação automática + realocação da lista de espera

@dataclass
class ResumoLibertacao:
    saltada: bool = False                                   # broker em baixo: não se fez nada
    libertadas: list[int] = field(default_factory=list)     # ids das reservas libertadas
    realocadas: list[tuple[int, Any]] = field(default_factory=list)  # (espera_id, reserva)
    expiradas: list[int] = field(default_factory=list)      # esperas cuja janela já passou


def libertar_e_realocar(repo: Repositorio, locks: Locks, *, agora: datetime,
                        tolerancia: timedelta = timedelta(minutes=15),
                        broker_saudavel: bool = True,
                        cfg: ConfigCSP = ConfigCSP()) -> ResumoLibertacao:
    resumo = ResumoLibertacao()

    if not broker_saudavel:
        resumo.saltada = True
        return resumo

    resumo.libertadas = repo.libertar_sem_checkin(limite=agora - tolerancia, agora=agora)

    minimo = _arredondar_para_cima(agora, cfg.slot_minutos)
    originais = {str(e.id): e for e in repo.espera_ativa()}
    pedidos: list[PedidoEspera] = []
    for e in originais.values():
        p = espera_para_csp(e)
        p = replace(p, janela_inicio=max(p.janela_inicio, minimo))
        if not p.inicios_possiveis(cfg):          # a duração já não cabe na janela restante
            repo.marcar_espera_expirada(e.id)
            resumo.expiradas.append(e.id)
            continue
        pedidos.append(p)
    if not pedidos:
        return resumo

    dias = set().union(*(_dias_da_janela(p) for p in pedidos))
    salas = [sala_para_csp(s) for s in repo.salas()]
    fixas = [reserva_para_csp(r) for r in repo.reservas_ativas_nos_dias(dias)]
    res = MotorCSP(cfg).resolver(pedidos, salas, fixas)

    for p in pedidos:
        if p.id not in res.atribuicoes:
            continue
        e = originais[p.id]
        inicio, fim = res.horarios[p.id]
        chave = f"espera-{p.id}"       # torna a tarefa idempotente se repetir a meio
        ja = repo.reserva_por_chave(e.utilizador_id, chave)
        if ja is not None:
            repo.marcar_espera_atendida(e.id, ja)
            continue
        slots = slots_ocupados(inicio, fim, cfg)
        with locks.adquirir(chaves_lock(res.atribuicoes[p.id], slots)):
            try:
                reserva = repo.inserir_reserva(
                    utilizador_id=e.utilizador_id, sala_id=int(res.atribuicoes[p.id]),
                    inicio=inicio, fim=fim, n_pessoas=e.n_pessoas,
                    chave_idempotencia=chave, slots=slots)
            except ConflitoSlot:
                continue
        repo.marcar_espera_atendida(e.id, reserva)
        resumo.realocadas.append((e.id, reserva))
    return resumo
