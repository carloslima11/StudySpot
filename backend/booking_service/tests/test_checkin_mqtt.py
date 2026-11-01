import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.checkin_mqtt import (EventoCheckin, EventoInvalido, interpretar_evento,
                              processar_checkin, topico_checkin, topico_resultado)
from app.qr_checkin import gerar_token

SEGREDO = b"segredo-de-teste-com-32-bytes!!!"
AGORA = datetime(2026, 10, 28, 10, 0)


def test_topicos():
    assert topico_checkin(3) == "studyspot/salas/3/checkin"
    assert topico_resultado(3) == "studyspot/salas/3/checkin/resultado"


def test_aceita_token_em_texto_ou_json():
    assert interpretar_evento(topico_checkin(3), b"SS1.1.2.abc") == EventoCheckin(3, "SS1.1.2.abc")
    assert interpretar_evento(topico_checkin(3), '{"token": " SS1.x "}').token == "SS1.x"


def test_eventos_invalidos_sao_recusados():
    maus = [
        ("studyspot/salas/1/outro", b"SS1"),
        ("studyspot/salas/1/checkin/resultado", b"SS1"),
        ("studyspot/salas/abc/checkin", b"SS1"),
        ("studyspot/salas/1/checkin", b"   "),
        ("studyspot/salas/1/checkin", b'{"sem_token": 1}'),
        ("studyspot/salas/1/checkin", b'{"token": 5}'),
        ("studyspot/salas/1/checkin", b"\xff\xfe"),
    ]
    for topico, payload in maus:
        with pytest.raises(EventoInvalido):
            interpretar_evento(topico, payload)


class RepoCheckin:
    def __init__(self, reserva):
        self.reserva, self.chamadas = reserva, []

    def registar_checkin(self, reserva_id, sala_id, quando, antecedencia):
        self.chamadas.append((reserva_id, sala_id, quando, antecedencia))
        return self.reserva


def token(reserva_id=5, sala_id=1, quando=AGORA):
    return gerar_token(SEGREDO, reserva_id, sala_id, quando).texto


def test_qr_valido_regista_o_checkin():
    repo = RepoCheckin(SimpleNamespace(id=5))
    r = processar_checkin(repo, EventoCheckin(1, token()), SEGREDO, AGORA, timedelta(minutes=10))
    assert r.ok and r.reserva_id == 5
    assert repo.chamadas == [(5, 1, AGORA, timedelta(minutes=10))]


def test_qr_de_outra_sala_e_recusado_sem_tocar_na_bd():
    repo = RepoCheckin(SimpleNamespace(id=5))
    r = processar_checkin(repo, EventoCheckin(2, token(sala_id=1)), SEGREDO, AGORA)
    assert not r.ok and repo.chamadas == []


def test_qr_expirado_e_recusado():
    repo = RepoCheckin(SimpleNamespace(id=5))
    r = processar_checkin(repo, EventoCheckin(1, token()), SEGREDO, AGORA + timedelta(minutes=5))
    assert not r.ok and "expirado" in r.mensagem and repo.chamadas == []


def test_qr_valido_mas_sem_reserva_ativa():
    r = processar_checkin(RepoCheckin(None), EventoCheckin(1, token()), SEGREDO, AGORA)
    assert not r.ok and r.reserva_id == 5


def test_dispositivo_interpreta_os_argumentos():
    caminho = Path(__file__).resolve().parents[1] / "scripts" / "dispositivo_qr.py"
    spec = importlib.util.spec_from_file_location("dispositivo_qr", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    args = modulo.interpretar_argumentos(["--sala", "1", "--token", "SS1.a.b.c"])
    assert (args.sala, args.token, args.port, args.camara) == (1, "SS1.a.b.c", 11883, False)
    with pytest.raises(SystemExit):
        modulo.interpretar_argumentos(["--sala", "1", "--token", "x", "--camara"])
