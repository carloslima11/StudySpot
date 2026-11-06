import pytest

pytest.importorskip("sqlalchemy")

from datetime import datetime, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.csp import ConfigCSP, PedidoEspera, slots_ocupados
from app.models import Base, ReservaSlot, Sala
from app.repo_sql import RepositorioSQL
from app.servico_reservas import ConflitoSlot

CFG = ConfigCSP()


def dt(h, m=0):
    return datetime(2026, 10, 23, h, m)


def novo_repo():
    motor = create_engine("sqlite://", poolclass=StaticPool,
                          connect_args={"check_same_thread": False})
    Base.metadata.create_all(motor)
    sessao = Session(motor, expire_on_commit=False)
    sessao.add(Sala(id=1, nome="Sala 1", capacidade=4, abertura=time(8), fecho=time(22)))
    sessao.commit()
    return RepositorioSQL(sessao)


def inserir(repo, utilizador=1, ini=dt(10), fim=dt(11), chave="k-0001"):
    return repo.inserir_reserva(
        utilizador_id=utilizador, sala_id=1, inicio=ini, fim=fim, n_pessoas=2,
        chave_idempotencia=chave, slots=slots_ocupados(ini, fim, CFG))


def espera(repo, utilizador=1, ini=dt(9), fim=dt(13)):
    return repo.guardar_espera(utilizador, PedidoEspera(
        id="", estudante_id=str(utilizador), participantes=2, janela_inicio=ini,
        janela_fim=fim, duracao_minutos=60, criado_em=dt(8)))


def test_esperas_do_utilizador_e_sair():
    repo = novo_repo()
    minha, outra = espera(repo), espera(repo, utilizador=2)
    assert [e.id for e in repo.esperas_do_utilizador(1)] == [minha.id]
    assert repo.sair_espera(2, minha.id) is None
    assert repo.sair_espera(1, minha.id).id == minha.id
    assert repo.esperas_do_utilizador(1) == []
    assert [e.id for e in repo.espera_ativa()] == [outra.id]


def test_nao_sai_de_espera_ja_atendida():
    repo = novo_repo()
    e = espera(repo)
    repo.marcar_espera_atendida(e.id, None)
    assert repo.sair_espera(1, e.id).estado == "atendida"
    assert len(repo.esperas_do_utilizador(1)) == 1


def test_inserir_e_ler():
    repo = novo_repo()
    r = inserir(repo)
    assert repo.reserva_por_chave(1, "k-0001").id == r.id
    assert [x.id for x in repo.reservas_ativas_nos_dias({dt(0).date()})] == [r.id]
    assert repo.reservas_ativas_nos_dias({dt(0).date() + timedelta(days=1)}) == []


def test_slot_repetido_levanta_conflito():
    repo = novo_repo()
    inserir(repo)
    with pytest.raises(ConflitoSlot):
        inserir(repo, utilizador=2, ini=dt(10, 30), fim=dt(11, 30), chave="k-0002")
    assert len(repo.reservas_ativas_nos_dias({dt(0).date()})) == 1


def test_chave_repetida_devolve_a_reserva_existente():
    repo = novo_repo()
    r = inserir(repo)
    outra = inserir(repo, ini=dt(14), fim=dt(15))
    assert outra.id == r.id


def test_libertar_sem_checkin_apaga_slots_e_so_toca_em_quem_nao_fez_checkin():
    repo = novo_repo()
    sem = inserir(repo, utilizador=1, ini=dt(10), fim=dt(11), chave="k-0001")
    com = inserir(repo, utilizador=2, ini=dt(11), fim=dt(12), chave="k-0002")
    assert repo.registar_checkin(com.id, 1, dt(10, 50), timedelta(minutes=15)).id == com.id
    ids = repo.libertar_sem_checkin(limite=dt(11, 30), agora=dt(11, 30))
    assert ids == [sem.id]
    assert sem.estado == "libertada" and com.estado == "confirmada"
    inserir(repo, utilizador=3, ini=dt(10), fim=dt(11), chave="k-0003")


def test_checkin_fora_da_janela_nao_regista():
    repo = novo_repo()
    r = inserir(repo, ini=dt(10), fim=dt(11))
    assert repo.registar_checkin(r.id, 1, dt(9, 0), timedelta(minutes=15)) is None
    assert repo.registar_checkin(r.id, 2, dt(10, 5), timedelta(minutes=15)) is None
    assert repo.registar_checkin(r.id + 1, 1, dt(10, 5), timedelta(minutes=15)) is None
    assert repo.registar_checkin(r.id, 1, dt(10, 5), timedelta(minutes=15)).check_in_em == dt(10, 5)
    assert repo.registar_checkin(r.id, 1, dt(10, 9), timedelta(minutes=15)).check_in_em == dt(10, 5)


def test_cancelar_liberta_os_slots():
    repo = novo_repo()
    r = inserir(repo)
    cancelada = repo.cancelar_reserva(1, r.id, agora=dt(9))
    assert cancelada.estado == "cancelada"
    assert repo.reservas_ativas_nos_dias({dt(0).date()}) == []
    nova = inserir(repo, utilizador=2, chave="k-0002")
    assert nova.id != r.id


def test_cancelar_e_idempotente_e_so_pelo_dono():
    repo = novo_repo()
    r = inserir(repo)
    assert repo.cancelar_reserva(2, r.id, agora=dt(9)) is None
    assert repo.cancelar_reserva(1, 999, agora=dt(9)) is None
    assert repo.cancelar_reserva(1, r.id, agora=dt(9)).estado == "cancelada"
    assert repo.cancelar_reserva(1, r.id, agora=dt(9)).estado == "cancelada"


def test_nao_cancela_reserva_que_ja_terminou():
    repo = novo_repo()
    r = inserir(repo)
    assert repo.cancelar_reserva(1, r.id, agora=dt(11)).estado == "confirmada"


def test_base_de_dados_recusa_slot_duplicado_mesmo_sem_o_servico():
    from sqlalchemy.exc import IntegrityError

    repo = novo_repo()
    inserir(repo)
    outra = inserir(repo, utilizador=2, ini=dt(12), fim=dt(13), chave="k-0002")
    repo.sessao.add(ReservaSlot(reserva_id=outra.id, sala_id=1, slot_inicio=dt(10)))
    with pytest.raises(IntegrityError):
        repo.sessao.commit()
    repo.sessao.rollback()
