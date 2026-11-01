import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from contextlib import contextmanager
from datetime import datetime, time, timedelta
from types import SimpleNamespace

from pydantic import SecretStr

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.deps import get_cfg, get_locks, get_repo, utilizador_atual
from app.locks_redis import RedisIndisponivel
from app.main import app
from app.csp import ConfigCSP


class LocksFalsos:
    def __init__(self, erro=None):
        self.erro = erro

    @contextmanager
    def adquirir(self, chaves):
        if self.erro:
            raise self.erro
        yield


class RepoFalso:
    def __init__(self):
        self.reservas, self.espera, self.id = [], [], 0
        self._salas = [SimpleNamespace(id=1, nome="S1", capacidade=4, abertura=time(8),
                                       fecho=time(22), ativa=True)]

    def salas(self):
        return self._salas

    def reservas_ativas_nos_dias(self, dias):
        return [r for r in self.reservas if r.inicio.date() in dias]

    def reserva_por_chave(self, uid, chave):
        return next((r for r in self.reservas
                     if r.utilizador_id == uid and r.chave_idempotencia == chave), None)

    def inserir_reserva(self, *, utilizador_id, sala_id, inicio, fim, n_pessoas,
                        chave_idempotencia, slots):
        self.id += 1
        r = SimpleNamespace(id=self.id, utilizador_id=utilizador_id, sala_id=sala_id,
                            inicio=inicio, fim=fim, n_pessoas=n_pessoas, estado="confirmada",
                            chave_idempotencia=chave_idempotencia, check_in_em=None)
        self.reservas.append(r)
        return r

    def guardar_espera(self, utilizador_id, pedido):
        self.espera.append(pedido)

    def reservas_do_utilizador(self, uid):
        return [r for r in self.reservas if r.utilizador_id == uid]

    def obter_reserva(self, reserva_id):
        return next((r for r in self.reservas if r.id == reserva_id), None)

    def espera_ativa(self):
        return []

    def esperas_do_utilizador(self, uid):
        return [e for e in self.espera if getattr(e, "utilizador_id", None) == uid]

    def sair_espera(self, uid, espera_id):
        e = next((e for e in self.espera if getattr(e, "id", None) == espera_id), None)
        if e is None or e.utilizador_id != uid:
            return None
        if e.estado == "ativa":
            self.espera.remove(e)
        return e

    def cancelar_reserva(self, uid, reserva_id, agora):
        r = next((r for r in self.reservas if r.id == reserva_id), None)
        if r is None or r.utilizador_id != uid:
            return None
        if r.estado == "confirmada" and r.fim > agora:
            r.estado = "cancelada"
        return r


@pytest.fixture
def cliente():
    repo, locks = RepoFalso(), LocksFalsos()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_locks] = lambda: locks
    app.dependency_overrides[get_cfg] = lambda: ConfigCSP()
    app.dependency_overrides[utilizador_atual] = lambda: 7
    yield TestClient(app), repo, locks
    app.dependency_overrides.clear()


def corpo(**extra):
    d = {"n_pessoas": 2, "inicio": "2099-01-05T10:00:00", "fim": "2099-01-05T11:00:00"}
    d.update(extra)
    return d


def test_cria_reserva_e_e_idempotente(cliente):
    c, repo, _ = cliente
    r1 = c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0001"})
    assert r1.status_code == 201 and r1.json()["estado"] == "confirmada"
    r2 = c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0001"})
    assert r2.status_code == 200 and r2.json()["estado"] == "duplicada"
    assert len(repo.reservas) == 1


def test_sem_chave_de_idempotencia_e_422(cliente):
    c, _, _ = cliente
    assert c.post("/api/reservas", json=corpo()).status_code == 422


def test_lotacao_excedida_e_recusada_com_motivo(cliente):
    c, _, _ = cliente
    r = c.post("/api/reservas", json=corpo(n_pessoas=10, sala_id=1),
               headers={"Idempotency-Key": "chave-0002"})
    assert r.status_code in (202, 422) and r.json()["motivos"]


def test_redis_em_baixo_devolve_503_e_nao_confirma(cliente):
    c, repo, locks = cliente
    locks.erro = RedisIndisponivel("redis")
    r = c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0003"})
    assert r.status_code == 503 and repo.reservas == []


def test_fim_antes_do_inicio_e_422(cliente):
    c, _, _ = cliente
    r = c.post("/api/reservas", json=corpo(inicio="2099-01-05T11:00:00",
                                           fim="2099-01-05T10:00:00"),
               headers={"Idempotency-Key": "chave-0004"})
    assert r.status_code == 422


def test_cancelar_reserva(cliente):
    c, repo, _ = cliente
    r = c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0005"})
    reserva_id = r.json()["reserva"]["id"]
    resposta = c.delete(f"/api/reservas/{reserva_id}")
    assert resposta.status_code == 200 and resposta.json()["estado"] == "cancelada"
    assert c.delete(f"/api/reservas/{reserva_id}").status_code == 200


def test_cancelar_reserva_inexistente_ou_de_outro_e_404(cliente):
    c, repo, _ = cliente
    assert c.delete("/api/reservas/999").status_code == 404
    r = c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0006"})
    repo.reservas[0].utilizador_id = 99
    assert c.delete(f"/api/reservas/{r.json()['reserva']['id']}").status_code == 404


def test_qr_do_dono_valida_na_sala_certa(cliente):
    from app.qr_checkin import validar_token
    c, repo, _ = cliente
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        checkin_segredo=SecretStr("s" * 32), qr_validade_segundos=120)
    r = c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0007"})
    reserva_id = r.json()["reserva"]["id"]
    qr = c.get(f"/api/reservas/{reserva_id}/qr")
    assert qr.status_code == 200
    corpo_qr = qr.json()
    assert corpo_qr["sala_id"] == 1 and not corpo_qr["check_in_feito"]
    expira = datetime.fromisoformat(corpo_qr["expira_em"])
    assert validar_token(b"s" * 32, corpo_qr["token"], 1,
                         expira - timedelta(seconds=1)) == reserva_id
    repo.reservas[0].utilizador_id = 99
    assert c.get(f"/api/reservas/{reserva_id}/qr").status_code == 404


def test_qr_sem_segredo_configurado_e_503(cliente):
    c, _, _ = cliente
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        checkin_segredo=None, qr_validade_segundos=120)
    r = c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0008"})
    assert c.get(f"/api/reservas/{r.json()['reserva']['id']}/qr").status_code == 503


def test_ocupacao_do_dia_marca_as_minhas(cliente):
    c, repo, _ = cliente
    c.post("/api/reservas", json=corpo(), headers={"Idempotency-Key": "chave-0009"})
    repo.inserir_reserva(utilizador_id=99, sala_id=1, inicio=datetime(2099, 1, 5, 12),
                         fim=datetime(2099, 1, 5, 13), n_pessoas=2,
                         chave_idempotencia="outro-0001", slots=[])
    r = c.get("/api/salas/ocupacao", params={"dia": "2099-01-05"})
    assert r.status_code == 200
    assert sorted((o["minha"], o["inicio"][11:16]) for o in r.json()) == [(False, "12:00"), (True, "10:00")]
    assert c.get("/api/salas/ocupacao", params={"dia": "2099-01-06"}).json() == []


def test_lista_de_espera_ver_e_sair(cliente):
    c, repo, _ = cliente
    for i, (uid, estado) in enumerate([(7, "ativa"), (7, "atendida"), (99, "ativa")], start=1):
        repo.espera.append(SimpleNamespace(
            id=i, utilizador_id=uid, n_pessoas=2, janela_inicio=datetime(2099, 1, 5, 9),
            janela_fim=datetime(2099, 1, 5, 13), duracao=60, estado=estado,
            criado_em=datetime(2099, 1, 4, 20)))
    assert [e["id"] for e in c.get("/api/reservas/espera").json()] == [1, 2]
    assert c.delete("/api/reservas/espera/3").status_code == 404
    assert c.delete("/api/reservas/espera/2").status_code == 409
    assert c.delete("/api/reservas/espera/1").status_code == 204
    assert [e["id"] for e in c.get("/api/reservas/espera").json()] == [2]


def test_sem_sessao_e_401():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(auth_modo_dev=False)
    try:
        assert TestClient(app).get("/api/salas").status_code == 401
    finally:
        app.dependency_overrides.clear()
