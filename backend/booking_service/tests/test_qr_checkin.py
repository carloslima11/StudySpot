from datetime import datetime, timedelta

import pytest

from app.qr_checkin import TokenInvalido, gerar_token, validar_token

SEGREDO = b"segredo-de-teste-com-32-bytes!!!"
AGORA = datetime(2026, 10, 28, 10, 0)


def test_token_valido_devolve_a_reserva():
    t = gerar_token(SEGREDO, 42, 3, AGORA)
    assert t.expira_em == AGORA + timedelta(minutes=2)
    assert validar_token(SEGREDO, t.texto, 3, AGORA + timedelta(seconds=90)) == 42


def test_token_nao_tem_dados_pessoais():
    texto = gerar_token(SEGREDO, 42, 3, AGORA).texto
    assert texto.split(".")[:2] == ["SS1", "42"]


def test_recusas():
    t = gerar_token(SEGREDO, 42, 3, AGORA).texto
    casos = [
        (SEGREDO, t, 4, AGORA),
        (SEGREDO, t, 3, AGORA + timedelta(minutes=3)),
        (b"outro-segredo", t, 3, AGORA),
        (SEGREDO, t.replace("SS1.42.", "SS1.43."), 3, AGORA),
        (SEGREDO, "nao e um token", 3, AGORA),
        (SEGREDO, "SS1.x.y.z", 3, AGORA),
    ]
    for segredo, texto, sala, quando in casos:
        with pytest.raises(TokenInvalido):
            validar_token(segredo, texto, sala, quando)
