import pytest
from pydantic import ValidationError
from app.schemas import RegistoPedido


def test_registo_normaliza_email_e_oculta_palavra_passe() -> None:
    pedido = RegistoPedido(
        nome="Alex",
        email="  ALUNO@EXEMPLO.PT ",
        palavra_passe="Abcdef1234",
    )

    assert pedido.email == "aluno@exemplo.pt"
    assert pedido.palavra_passe.get_secret_value() == "Abcdef1234"
    assert "Abcdef1234" not in repr(pedido)


def test_rejeita_palavra_passe_com_menos_de_10_caracteres() -> None:
    with pytest.raises(ValidationError):
        RegistoPedido(
            nome="Alex",
            email="aluno@exemplo.pt",
            palavra_passe="Curta123",
        )


def test_rejeita_email_invalido() -> None:
    with pytest.raises(ValidationError):
        RegistoPedido(
            nome="Alex",
            email="isto-nao-e-email",
            palavra_passe="Abcdef1234",
        )
