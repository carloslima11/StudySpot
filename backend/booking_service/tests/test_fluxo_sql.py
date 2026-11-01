import pytest

pytest.importorskip("sqlalchemy")

from contextlib import contextmanager
from datetime import datetime, time, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, ListaEspera, Reserva, ReservaSlot, Sala
from app.repo_sql import RepositorioSQL
from app.servico_reservas import criar_reserva, libertar_e_realocar, realocar_espera


def dt(h, m=0):
    return datetime(2026, 10, 28, h, m)


class LocksFalsos:
    @contextmanager
    def adquirir(self, chaves):
        yield


def novo_repo():
    motor = create_engine("sqlite://", poolclass=StaticPool,
                          connect_args={"check_same_thread": False})
    Base.metadata.create_all(motor)
    sessao = Session(motor, expire_on_commit=False)
    sessao.add(Sala(id=1, nome="Sala 1", capacidade=4, abertura=time(8), fecho=time(22)))
    sessao.commit()
    return RepositorioSQL(sessao)


def reservar(repo, utilizador, chave, ini=dt(10), fim=dt(11), **extra):
    return criar_reserva(repo, LocksFalsos(), utilizador_id=utilizador, chave_idempotencia=chave,
                         n_pessoas=2, inicio=ini, fim=fim, agora=dt(9), **extra)


def test_reserva_confirmada_e_repetida_devolve_a_mesma():
    repo = novo_repo()
    r1 = reservar(repo, 1, "chave-0001")
    r2 = reservar(repo, 1, "chave-0001")
    assert r1.estado == "confirmada" and r2.estado == "duplicada"
    assert r2.reserva.id == r1.reserva.id
    assert len(repo.sessao.scalars(select(ReservaSlot)).all()) == 2


def test_sala_ocupada_vai_para_a_lista_de_espera():
    repo = novo_repo()
    reservar(repo, 1, "chave-0001")
    r = reservar(repo, 2, "chave-0002")
    assert r.estado == "espera"
    assert repo.sessao.scalars(select(ListaEspera)).one().estado == "ativa"


def test_no_show_liberta_e_realoca_a_lista_de_espera():
    repo = novo_repo()
    primeira = reservar(repo, 1, "chave-0001").reserva
    assert reservar(repo, 2, "chave-0002", janela_fim=dt(14)).estado == "espera"

    resumo = libertar_e_realocar(repo, LocksFalsos(), agora=dt(10, 20))

    assert resumo.libertadas == [primeira.id]
    assert len(resumo.realocadas) == 1
    nova = repo.sessao.scalars(select(Reserva).where(Reserva.utilizador_id == 2)).one()
    assert (nova.inicio, nova.fim) == (dt(10, 30), dt(11, 30))
    assert repo.sessao.get(Reserva, primeira.id).estado == "libertada"
    assert repo.sessao.scalars(select(ListaEspera)).one().estado == "atendida"

    repetido = libertar_e_realocar(repo, LocksFalsos(), agora=dt(10, 25))
    assert repetido.libertadas == [] and repetido.realocadas == []


def test_reserva_com_checkin_nao_e_libertada():
    repo = novo_repo()
    primeira = reservar(repo, 1, "chave-0001").reserva
    reservar(repo, 2, "chave-0002", janela_fim=dt(14))
    repo.registar_checkin(primeira.id, 1, dt(10, 2), timedelta(minutes=15))

    resumo = libertar_e_realocar(repo, LocksFalsos(), agora=dt(10, 20))

    assert resumo.libertadas == []
    assert repo.sessao.get(Reserva, primeira.id).estado == "confirmada"
    nova = repo.sessao.scalars(select(Reserva).where(Reserva.utilizador_id == 2)).one()
    assert nova.inicio == dt(11)


def test_espera_sem_janela_extra_expira_depois_do_no_show():
    repo = novo_repo()
    reservar(repo, 1, "chave-0001")
    reservar(repo, 2, "chave-0002")

    resumo = libertar_e_realocar(repo, LocksFalsos(), agora=dt(10, 20))

    assert len(resumo.expiradas) == 1 and resumo.realocadas == []


def test_cancelamento_passa_a_vaga_a_lista_de_espera():
    repo = novo_repo()
    primeira = reservar(repo, 1, "chave-0001").reserva
    assert reservar(repo, 2, "chave-0002").estado == "espera"

    repo.cancelar_reserva(1, primeira.id, agora=dt(9, 10))
    resumo = realocar_espera(repo, LocksFalsos(), agora=dt(9, 10))

    assert len(resumo.realocadas) == 1
    nova = repo.sessao.scalars(select(Reserva).where(Reserva.utilizador_id == 2)).one()
    assert (nova.inicio, nova.fim, nova.estado) == (dt(10), dt(11), "confirmada")
