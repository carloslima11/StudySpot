"""Testes do servico_reservas.py com uma BD e locks em memória.
Correr a partir de 05_artefactos/backend/booking_service:  python -m pytest -v"""

from contextlib import contextmanager
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest  # noqa: F401  (o ficheiro também corre com o executor mínimo)

from app.servico_reservas import (ESTADOS_ATIVOS, ConflitoSlot, LockIndisponivel,
                              criar_reserva, libertar_e_realocar)
from app.csp import ConfigCSP, slots_ocupados

DIA = (2026, 10, 20)
CFG = ConfigCSP()


def dt(h, m=0):
    return datetime(*DIA, h, m)


class LocksFake:
    def __init__(self, indisponivel=False):
        self.pedidos, self.indisponivel = [], indisponivel

    @contextmanager
    def adquirir(self, chaves):
        if self.indisponivel:
            raise LockIndisponivel("redis em baixo")
        self.pedidos.append(list(chaves))
        yield


class RepoFake:
    """BD em memória que reproduz o UNIQUE (sala_id, slot_inicio)."""

    def __init__(self, salas, tem_hook=None):
        self._salas = salas
        self.reservas, self.espera, self.slots = [], [], set()
        self._id = 100
        self.antes_de_inserir = tem_hook  # simula outro pedido a passar à frente

    def _novo_id(self):
        self._id += 1
        return self._id

    def adicionar(self, utilizador_id, sala_id, inicio, fim, check_in=None, chave=None):
        r = SimpleNamespace(id=self._novo_id(), utilizador_id=utilizador_id, sala_id=sala_id,
                            inicio=inicio, fim=fim, n_pessoas=2, estado="confirmada",
                            chave_idempotencia=chave or f"auto-{self._id}", check_in_em=check_in)
        self.reservas.append(r)
        self.slots |= {(sala_id, s) for s in slots_ocupados(inicio, fim, CFG)}
        return r

    def adicionar_espera(self, utilizador_id, ini, fim, dur, criado):
        e = SimpleNamespace(id=self._novo_id(), utilizador_id=utilizador_id, n_pessoas=2,
                            janela_inicio=ini, janela_fim=fim, duracao=dur,
                            criado_em=criado, estado="ativa")
        self.espera.append(e)
        return e

    # --- contrato Repositorio ---
    def salas(self):
        return self._salas

    def reservas_ativas_nos_dias(self, dias):
        return [r for r in self.reservas
                if r.estado in ESTADOS_ATIVOS and r.inicio.date() in dias]

    def reserva_por_chave(self, utilizador_id, chave):
        return next((r for r in self.reservas
                     if r.utilizador_id == utilizador_id and r.chave_idempotencia == chave), None)

    def inserir_reserva(self, *, utilizador_id, sala_id, inicio, fim, n_pessoas,
                        chave_idempotencia, slots):
        if self.antes_de_inserir:
            self.antes_de_inserir(self)
        if any((sala_id, s) in self.slots for s in slots):
            raise ConflitoSlot()
        r = self.adicionar(utilizador_id, sala_id, inicio, fim, chave=chave_idempotencia)
        r.n_pessoas = n_pessoas
        return r

    def guardar_espera(self, utilizador_id, pedido):
        return self.adicionar_espera(utilizador_id, pedido.janela_inicio, pedido.janela_fim,
                                     pedido.duracao_minutos, pedido.criado_em)

    def espera_ativa(self):
        return sorted((e for e in self.espera if e.estado == "ativa"), key=lambda e: e.criado_em)

    def marcar_espera_atendida(self, espera_id, reserva):
        next(e for e in self.espera if e.id == espera_id).estado = "atendida"

    def marcar_espera_expirada(self, espera_id):
        next(e for e in self.espera if e.id == espera_id).estado = "expirada"

    def libertar_sem_checkin(self, limite, agora):
        ids = []
        for r in self.reservas:
            if (r.estado == "confirmada" and r.check_in_em is None
                    and r.inicio < limite and r.fim > agora):
                r.estado = "libertada"
                self.slots -= {(r.sala_id, s) for s in slots_ocupados(r.inicio, r.fim, CFG)}
                ids.append(r.id)
        return ids


def sala(id, cap=4, ativa=True):
    return SimpleNamespace(id=id, nome=f"S{id}", capacidade=cap, abertura=time(8),
                           fecho=time(22), ativa=ativa)


def criar(repo, locks=None, **kw):
    base = dict(utilizador_id=7, chave_idempotencia="k1", n_pessoas=2, inicio=dt(10),
                fim=dt(11), agora=datetime(2026, 10, 19, 9))
    base.update(kw)
    return criar_reserva(repo, locks or LocksFake(), **base)


# ---------------------- diagrama 3: criar reserva ----------------------

def test_confirma_e_grava_reserva_com_slots_e_locks_ordenados():
    repo, locks = RepoFake([sala(1)]), LocksFake()
    r = criar(repo, locks, inicio=dt(10), fim=dt(11, 30))
    assert r.estado == "confirmada" and r.reserva.sala_id == 1
    assert repo.slots == {(1, dt(10)), (1, dt(10, 30)), (1, dt(11))}
    assert len(locks.pedidos[0]) == 3 and locks.pedidos[0] == sorted(locks.pedidos[0])


def test_idempotencia_reenvio_nao_duplica():
    repo = RepoFake([sala(1)])
    a = criar(repo)
    b = criar(repo)
    assert a.estado == "confirmada" and b.estado == "duplicada"
    assert b.reserva.id == a.reserva.id and len(repo.reservas) == 1


def test_sala_ocupada_vai_para_espera_com_alternativas():
    repo = RepoFake([sala(1)])
    repo.adicionar(9, 1, dt(10), dt(11))
    r = criar(repo)
    assert r.estado == "espera" and len(repo.espera) == 1
    assert r.motivos and r.alternativas.horarios[0][0] == "1"
    assert repo.espera[0].duracao == 60


def test_pedido_impossivel_e_recusado_e_nao_entra_em_espera():
    repo = RepoFake([sala(1)])
    r = criar(repo, n_pessoas=50)
    assert r.estado == "recusada" and repo.espera == [] and "comporta" in r.motivos[0]


def test_corrida_conflito_de_slot_e_decidido_de_novo_noutra_sala():
    def outro_passa_a_frente(repo):
        repo.antes_de_inserir = None
        repo.adicionar(9, 1, dt(10), dt(11))       # toma a sala 1 antes do nosso INSERT
    repo = RepoFake([sala(1), sala(2)], tem_hook=outro_passa_a_frente)
    r = criar(repo)
    assert r.estado == "confirmada" and r.reserva.sala_id == 2


def test_corrida_sem_tentativas_restantes_vai_para_espera():
    def outro_passa_a_frente(repo):
        repo.adicionar(9, 1, dt(10), dt(11))
    repo = RepoFake([sala(1)], tem_hook=outro_passa_a_frente)
    r = criar(repo, max_tentativas=1)
    assert r.estado == "espera" and "simultâneo" in r.motivos[0]


def test_lock_indisponivel_falha_segura_sem_gravar():
    repo = RepoFake([sala(1)])
    with pytest.raises(LockIndisponivel):
        criar(repo, LocksFake(indisponivel=True))
    assert repo.reservas == [] and repo.slots == set()


# ---------------------- diagrama 4: libertar e realocar ----------------------

AGORA = dt(10, 20)


def cenario_fantasma():
    repo = RepoFake([sala(1)])
    fantasma = repo.adicionar(1, 1, dt(10), dt(11))            # sem check-in
    e = repo.adicionar_espera(2, dt(10), dt(12), 60, datetime(2026, 10, 19, 9))
    return repo, fantasma, e


def test_liberta_fantasma_e_realoca_a_lista_de_espera():
    repo, fantasma, e = cenario_fantasma()
    r = libertar_e_realocar(repo, LocksFake(), agora=AGORA)
    assert r.libertadas == [fantasma.id] and fantasma.estado == "libertada"
    assert len(r.realocadas) == 1
    nova = r.realocadas[0][1]
    # nunca atribui hora no passado: 10:20 arredonda para 10:30
    assert (nova.sala_id, nova.inicio, nova.fim) == (1, dt(10, 30), dt(11, 30))
    assert e.estado == "atendida"


def test_reserva_com_checkin_nao_e_libertada():
    repo = RepoFake([sala(1)])
    com_checkin = repo.adicionar(1, 1, dt(10), dt(11), check_in=dt(10, 2))
    e = repo.adicionar_espera(2, dt(10), dt(11), 30, datetime(2026, 10, 19, 9))  # janela toda ocupada
    r = libertar_e_realocar(repo, LocksFake(), agora=AGORA)
    assert r.libertadas == [] and com_checkin.estado == "confirmada"
    assert r.realocadas == [] and e.estado == "ativa"


def test_espera_aproveita_vaga_livre_mesmo_sem_libertacoes():
    repo = RepoFake([sala(1)])
    repo.adicionar(1, 1, dt(10), dt(11), check_in=dt(10, 2))
    e = repo.adicionar_espera(2, dt(10), dt(12), 60, datetime(2026, 10, 19, 9))
    r = libertar_e_realocar(repo, LocksFake(), agora=AGORA)
    assert r.libertadas == [] and r.realocadas[0][1].inicio == dt(11) and e.estado == "atendida"


def test_broker_em_baixo_nao_liberta_nada():
    repo, fantasma, e = cenario_fantasma()
    r = libertar_e_realocar(repo, LocksFake(), agora=AGORA, broker_saudavel=False)
    assert r.saltada and fantasma.estado == "confirmada" and e.estado == "ativa"


def test_espera_com_janela_ultrapassada_expira():
    repo = RepoFake([sala(1)])
    e = repo.adicionar_espera(2, dt(10), dt(11), 30, datetime(2026, 10, 19, 9))
    r = libertar_e_realocar(repo, LocksFake(), agora=dt(10, 50))   # 11:00 + 30 min > 11:00
    assert r.expiradas == [e.id] and e.estado == "expirada" and r.realocadas == []


def test_tarefa_repetida_e_idempotente():
    repo, fantasma, e = cenario_fantasma()
    libertar_e_realocar(repo, LocksFake(), agora=AGORA)
    n = len(repo.reservas)
    r2 = libertar_e_realocar(repo, LocksFake(), agora=AGORA)
    assert len(repo.reservas) == n and r2.realocadas == []


def test_perde_a_corrida_na_realocacao_continua_em_espera():
    repo, fantasma, e = cenario_fantasma()

    def outro_passa_a_frente(repo):
        repo.antes_de_inserir = None
        repo.adicionar(9, 1, dt(10, 30), dt(11, 30))
    repo.antes_de_inserir = outro_passa_a_frente
    r = libertar_e_realocar(repo, LocksFake(), agora=AGORA)
    assert r.realocadas == [] and e.estado == "ativa"


def test_realocacao_por_ordem_de_chegada():
    repo = RepoFake([sala(1)])
    repo.adicionar(1, 1, dt(10), dt(11))
    mais_velha = repo.adicionar_espera(2, dt(10), dt(11, 30), 60, datetime(2026, 10, 19, 9, 0))
    mais_nova = repo.adicionar_espera(3, dt(10), dt(11, 30), 60, datetime(2026, 10, 19, 9, 5))
    libertar_e_realocar(repo, LocksFake(), agora=dt(10, 20))
    assert mais_velha.estado == "atendida" and mais_nova.estado == "ativa"
